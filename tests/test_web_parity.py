"""Protect web/Python circuit, seeded sampling and accounting parity."""
import copy
import json
from pathlib import Path
import random
import shutil
import subprocess
import unittest
from researchos_qbi.model import analyze
from researchos_qbi.records import read_json

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is required for web parity verification')
class WebParityTests(unittest.TestCase):
    def test_circuit_seed_and_resource_parity(self):
        base = read_json(ROOT/'examples/bell-synthetic.json')
        cases = []
        for seed in (0,1,42,123456789,4294967295):
            r = copy.deepcopy(base)
            r['seed'] = seed
            cases.append(r)
        rng = random.Random(15)
        for n in range(1,7):
            r = copy.deepcopy(base)
            r['resources'] = None
            r['classical_baseline'] = None
            r['circuit'] = {'qubits':n,'gates':[]}
            r['expected_probabilities'] = {'0'*n:1}
            for _ in range(20):
                gate = rng.choice(['h','x','z','cx'] if n>1 else ['h','x','z'])
                target = rng.randrange(n)
                op = {'gate':gate,'target':target}
                if gate == 'cx':
                    op['control'] = rng.choice([i for i in range(n) if i != target])
                r['circuit']['gates'].append(op)
            cases.append(r)
        script = "import fs from 'node:fs';import{analyze}from './web/model.mjs';console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(analyze)))"
        result = json.loads(subprocess.check_output(['node','--input-type=module','-e',script],input=json.dumps(cases),text=True,cwd=ROOT))
        def compare(actual, expected):
            if isinstance(expected,dict):
                self.assertEqual(actual.keys(),expected.keys())
                for k in expected:
                    compare(actual[k],expected[k])
            elif isinstance(expected,list):
                self.assertEqual(len(actual),len(expected))
                for a,b in zip(actual,expected):
                    compare(a,b)
            elif type(expected) is float:
                self.assertAlmostEqual(actual,expected,places=12)
            else:
                self.assertEqual(actual,expected)
        for r,web in zip(cases,result):
            with self.subTest(seed=r['seed'],qubits=r['circuit']['qubits']):
                compare(web,analyze(r))
