import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from researchos_qbi.model import analyze, estimate, probabilities, sample, tvd
from researchos_qbi.records import ValidationError, dumps, read_json, sha, validate
from researchos_qbi.workflow import run, verify_bundle, verify_evidence

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/bell-synthetic.json'


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.r = read_json(EXAMPLE)

    def test_bell_and_ghz(self):
        bell = probabilities(self.r['circuit'])
        self.assertAlmostEqual(bell['00'], .5)
        self.assertAlmostEqual(bell['11'], .5)
        self.assertEqual(len(bell), 2)
        ghz = {'qubits':3,'gates':[{'gate':'h','target':0},{'gate':'cx','control':0,'target':1},{'gate':'cx','control':1,'target':2}]}
        self.assertEqual(set(probabilities(ghz)), {'000','111'})
        self.assertAlmostEqual(probabilities(ghz)['111'], .5)

    def test_bit_order_and_interference(self):
        self.assertEqual(probabilities({'qubits':3,'gates':[{'gate':'x','target':2}]}), {'100':1})
        hzh = {'qubits':1,'gates':[{'gate':'h','target':0},{'gate':'z','target':0},{'gate':'h','target':0}]}
        self.assertAlmostEqual(probabilities(hzh)['1'], 1)
        hh = {'qubits':1,'gates':[{'gate':'h','target':0},{'gate':'h','target':0}]}
        self.assertAlmostEqual(probabilities(hh)['0'], 1)
        reverse_control = {'qubits':2,'gates':[{'gate':'x','target':1},{'gate':'cx','control':1,'target':0}]}
        self.assertEqual(probabilities(reverse_control), {'11':1})

    def test_seeded_shots_and_distance(self):
        p = probabilities(self.r['circuit'])
        a = sample(p, 4096, 42)
        self.assertEqual(a, sample(p, 4096, 42))
        self.assertEqual(sum(a.values()), 4096)
        self.assertEqual(set(a), {'00','11'})
        self.assertLess(abs(a['00']/4096-.5), .05)
        self.assertEqual(tvd({'0':1},{'1':1}), 1)
        self.assertEqual(tvd({'0':1},{'0':1}), 0)

    def test_resource_arithmetic(self):
        result = estimate(self.r['resources'],4096)
        self.assertEqual(result['physical_qubits'],2000)
        self.assertEqual(result['cycles_per_shot'],20)
        self.assertAlmostEqual(result['estimated_quantum_s'],.08192)
        self.assertAlmostEqual(result['estimated_workflow_s'],.10192)
        self.assertAlmostEqual(result['failure_union_bound_all_shots'],.00016384)
        self.r['resources']['logical_error_per_qubit_cycle'] = 1
        self.assertEqual(estimate(self.r['resources'],4096)['failure_union_bound_all_shots'],1)

    def test_no_data_stays_missing(self):
        self.r['resources'] = None
        self.r['classical_baseline'] = None
        result = analyze(self.r)
        self.assertEqual(result['resources']['status'],'no-data')
        self.assertEqual(result['observations']['status'],'no-data')
        self.assertIsNone(result['baseline_comparison']['declared_runtime_ratio'])

    def test_baseline_comparability_and_quality(self):
        result = analyze(self.r)
        self.assertAlmostEqual(result['baseline_comparison']['declared_runtime_ratio'],.001/.10192)
        self.r['classical_baseline']['same_problem_and_quality'] = False
        self.assertEqual(analyze(self.r)['baseline_comparison']['status'],'not-comparable')
        self.r['classical_baseline']['same_problem_and_quality'] = True
        self.r['classical_baseline']['tvd'] = 1
        self.assertIsNone(analyze(self.r)['baseline_comparison']['declared_runtime_ratio'])
        self.r['classical_baseline']['tvd'] = 0
        self.r['expected_probabilities'] = {'01':1}
        self.assertFalse(analyze(self.r)['sampled_quality_met'])
        self.assertIsNone(analyze(self.r)['baseline_comparison']['declared_runtime_ratio'])

    def test_invalid_records(self):
        mutations = [lambda r:r.update(schema_version=True),lambda r:r.update(id='../escape'),
                     lambda r:r.update(seed=True),lambda r:r.update(shots=0),
                     lambda r:r['circuit'].update(qubits=13),lambda r:r['circuit']['gates'][1].update(control=1),
                     lambda r:r['circuit']['gates'][0].update(gate='unknown'),
                     lambda r:r.update(expected_probabilities={'0':1}),lambda r:r.update(expected_probabilities={'00':.1}),
                     lambda r:r.update(quality_tvd_limit=float('nan')),lambda r:r.update(data_kind='experimental'),
                     lambda r:r['resources'].update(cycle_time_us=0),lambda r:r['resources'].update(logical_qubits=1),
                     lambda r:r['classical_baseline'].update(same_problem_and_quality='yes')]
        for mutate in mutations:
            record = copy.deepcopy(self.r)
            mutate(record)
            with self.subTest(record=record),self.assertRaises(ValidationError):
                validate(record)

    def test_json_rejects_duplicates_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'bad.json'
            for text in ('{"shots":1,"shots":2}','{"x":NaN}','{"x":Infinity}'):
                path.write_text(text)
                with self.assertRaises(ValidationError):
                    read_json(path)

    def test_evidence_and_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = b'fixture only, not real hardware evidence'
            (root/'counts.csv').write_bytes(data)
            self.r['evidence'] = [{'id':'raw','path':'counts.csv','sha256':sha(data),'description':'Fixture'}]
            self.r['observations'] = {'counts':{'00':2048,'11':2048},'method':'Fixture only','evidence_ids':['raw']}
            self.r['data_kind'] = 'experimental'
            validate(self.r)
            verify_evidence(self.r,root)
            self.assertEqual(analyze(self.r)['observations']['tvd'],0)
            p = root/'record.json'
            p.write_text(dumps(self.r))
            run(p,root/'run')
            (root/'counts.csv').unlink()
            verify_bundle(root/'run')
            (root/'run/evidence/0000.bin').write_bytes(b'changed')
            with self.assertRaises(ValidationError):
                verify_bundle(root/'run')

    def test_missing_bad_evidence_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'raw').write_bytes(b'actual')
            self.r['evidence'] = [{'id':'e','path':'raw','sha256':sha(b'wrong'),'description':'Fixture'}]
            with self.assertRaises(ValidationError):
                verify_evidence(validate(self.r),root)
            for path in ('../outside','/etc/passwd','C:\\absolute'):
                self.r['evidence'][0]['path'] = path
                with self.assertRaises(ValidationError):
                    validate(self.r)
            (root/'link').symlink_to(root.parent)
            self.r['evidence'][0]['path'] = 'link/outside'
            with self.assertRaises(ValidationError):
                verify_evidence(validate(self.r),root)

    def test_bundle_reproduction_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b = Path(tmp)/'a',Path(tmp)/'b'
            run(EXAMPLE,a)
            run(EXAMPLE,b)
            self.assertEqual({p.relative_to(a):p.read_bytes() for p in a.rglob('*') if p.is_file()},
                             {p.relative_to(b):p.read_bytes() for p in b.rglob('*') if p.is_file()})
            verify_bundle(a)
            with self.assertRaises(ValidationError):
                run(EXAMPLE,a)
            result = read_json(a/'results.json')
            result['sampled_tvd'] = 1
            (a/'results.json').write_text(dumps(result))
            manifest = read_json(a/'manifest.json')
            manifest['files']['results.json'] = sha((a/'results.json').read_bytes())
            (a/'manifest.json').write_text(dumps(manifest))
            with self.assertRaises(ValidationError):
                verify_bundle(a)

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = str(Path(tmp)/'run')
            for args in (['validate',str(EXAMPLE)],['run',str(EXAMPLE),'--output',output],['verify',output],['report',output]):
                p = subprocess.run([sys.executable,'-m','researchos_qbi',*args],capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)
            failed = subprocess.run([sys.executable,'-m','researchos_qbi','validate',str(Path(tmp)/'missing')],capture_output=True,text=True)
            self.assertEqual(failed.returncode,1)
            self.assertIn('error:',failed.stderr)


if __name__ == '__main__':
    unittest.main()
