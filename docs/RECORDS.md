# Record contract v1

The executable contract is `researchos_qbi/records.py`. Unknown metadata is retained. JSON duplicate keys, NaN and Infinity are rejected. Booleans cannot stand in for numeric fields.

| Field | Contract |
| --- | --- |
| `schema_version` | Integer 1 |
| `id` | 1–80 lowercase letters/digits/underscores/hyphens; starts alphanumeric |
| `title`, `owner`, `hypothesis`, `workload_reference` | Nonempty strings |
| `data_kind` | synthetic, simulation, or experimental; describes declared inputs, never changes simulator into hardware execution |
| `seed` | Integer 0 through 2³²−1 |
| `shots` | Integer 1 through 1,000,000; observation count total must match |
| `circuit` | Object containing `qubits` and ordered `gates`; see model limits |
| `expected_probabilities` | Bitstring-to-probability object; width equals circuit qubits; probabilities sum to one |
| `quality_tvd_limit` | Finite number in [0,1], owner-defined |
| `observations` | Optional/null object with `counts`, nonempty acquisition `method`, and `evidence_ids` |
| `resources` | Optional/null object with resource assumptions below |
| `classical_baseline` | Optional/null declared timing/quality record below |
| `evidence` | Array of declarations, possibly empty for nonexperimental inputs |

Each gate has lowercase `gate` (h, x, z or cx), integer `target`, and for cx an integer `control` different from the target. Qubit indices must be in range.

## Resource assumptions

Required when `resources` is an object:

| Key | Unit / condition |
| --- | --- |
| `logical_qubits` | Positive integer, at least circuit register size |
| `logical_depth` | Positive integer assumed resource layers per shot |
| `cycles_per_layer` | Positive integer |
| `physical_qubits_per_logical` | Positive integer |
| `factory_physical_qubits` | Nonnegative integer |
| `cycle_time_us` | Positive finite microseconds |
| `classical_pre_s`, `classical_post_s` | Nonnegative finite seconds for the entire workload |
| `logical_error_per_qubit_cycle` | Finite probability in [0,1], assumed per-location bound |
| `assumption_reference` | Nonempty versioned source/derivation reference |

Resource integer fields are limited to 10¹². Derived nonfinite values and runtime underflow to zero are rejected.

## Baseline and observations

`classical_baseline` requires positive finite `runtime_s`, finite `tvd` in [0,1], a boolean `same_problem_and_quality`, and nonempty `method` and `reference`. Document hardware, software, workload count, timing boundary, uncertainty and comparable output quality in its metadata/evidence. The runner does not execute or time a classical solver.

Observed count keys must match circuit bit width, values must be nonnegative integers, and their sum must equal `shots`. An experimental record requires counts and evidence; its observations must reference at least one declared evidence ID. Nonexperimental observations retain their stated input basis. Simulator-generated counts remain separate in all results.

## Evidence declarations

Every entry requires unique nonempty `id`, unique relative `path`, lowercase 64-character `sha256`, and nonempty `description`. Place files below the record directory. Absolute paths, drive paths, traversal and resolved symlinks outside the directory fail. Use `researchos-qbi hash <file>` to obtain the digest.

Captured bundle filenames are generated and mapped back to evidence IDs in the manifest. Keep raw counts, acquisition/processing protocol, hardware calibration, compiler revision, timing records and baseline evidence where available. Do not fabricate missing measurements or evidence; omission is reported as no-data where supported.
