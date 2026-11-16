import assert from 'node:assert/strict';
import fs from 'node:fs';
import{analyze,validate,probabilities,sample,PythonRandom,parseCircuit,outcomeCsv}from'../model.mjs';
const r=JSON.parse(fs.readFileSync(new URL('../demo.json',import.meta.url),'utf8'));
const a=analyze(r);assert.deepEqual(a.sampled_counts,{'00':2008,'11':2088});assert.equal(a.ideal_tvd,0);assert.equal(a.resources.physical_qubits,2000);assert.ok(Math.abs(a.resources.estimated_workflow_s-.10192)<1e-12);assert.equal(a.observations.status,'no-data');
assert.equal(new PythonRandom(42).random(),.6394267984578837);assert.equal(new PythonRandom(0).random(),.8444218515250481);
assert.deepEqual(probabilities({qubits:3,gates:parseCircuit('H 0\nCX 0 1\nCX 1 2')}),{'000':.5,'111':.5});assert.equal(probabilities({qubits:1,gates:parseCircuit('H 0\nZ 0\nH 0')})['1'],1);assert.deepEqual(probabilities({qubits:3,gates:parseCircuit('X 2')}),{'100':1});
assert.throws(()=>parseCircuit('H nope'));assert.throws(()=>parseCircuit('CX 0'));assert.throws(()=>parseCircuit('T 0'));
for(let mutate of [r=>r.id='../escape',r=>r.shots=0,r=>r.seed=true,r=>r.circuit.qubits=13,r=>r.circuit.gates[1].control=1,r=>r.expected_probabilities={'00':.1},r=>r.data_kind='experimental',r=>r.resources.cycle_time_us=Infinity]){let bad=structuredClone(r);mutate(bad);assert.throws(()=>validate(bad))}
let notComparable=structuredClone(r);notComparable.classical_baseline.same_problem_and_quality=false;assert.equal(analyze(notComparable).baseline_comparison.declared_runtime_ratio,null);
let missing=structuredClone(r);missing.resources=null;missing.classical_baseline=null;assert.equal(analyze(missing).resources.status,'no-data');
let large=structuredClone(r);large.resources.logical_qubits=1e12;assert.throws(()=>analyze(large),/precision/);
assert.ok(outcomeCsv(r,a).includes('00,0.5,0.5,2008,'));assert.deepEqual(sample({'0':.5,'1':.5},100,7),sample({'0':.5,'1':.5},100,7));
console.log('Web quantum-state, sampling, resource, validation, comparison, missing-data and CSV checks passed.');
