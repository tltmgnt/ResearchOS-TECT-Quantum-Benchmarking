# ResearchOS TECT — Quantum Benchmarking and Fault-Tolerant Systems Evaluation

Independent research workspace aligned with DARPA QBI research goals, supporting reproducible quantum benchmarks, declared-assumption fault-tolerant resource accounting, computational workflow evaluation, and evidence-linked assessment of utility-scale quantum computing approaches.

This standalone repository does not depend on the SynQuaNon or heterogeneous integration projects. TECT remains the project identifier without an assumed expansion.

## Working implementation

- Exact, bounded ideal state-vector simulation of H, X, Z and CX circuits, with documented bit order and seeded finite-shot sampling.
- Expected-distribution comparisons using total variation distance (TVD), plus separately declared observations and evidence references.
- Transparent physical-qubit, runtime and failure-budget arithmetic based on user-supplied logical resource assumptions.
- Classical baseline comparisons gated on declared problem/quality comparability; ratios are explicitly not measured quantum speedup.
- Validated JSON records, SHA-256 evidence checks, captured evidence files, reproducible JSON/CSV/Markdown results, and portable bundle verification.

This is a research software foundation. It does not implement hardware execution, noise models, error-correcting codes, fault-tolerant compilation, or a utility-scale quantum computer. The small benchmark is classically simulable and demonstrates no quantum advantage. Resource overheads are assumed, not derived from a code or architecture. No DARPA affiliation, award, eligibility, endorsement, or application status is claimed.

## Quick start

Python 3.10 or newer. No third-party runtime dependencies. From the repository root:

```bash
python -m researchos_qbi validate examples/bell-synthetic.json
python -m researchos_qbi run examples/bell-synthetic.json --output runs/bell
python -m researchos_qbi verify runs/bell
python -m researchos_qbi report runs/bell
python -m unittest discover -s tests -v
```

Optional installation enables `researchos-qbi`:

```bash
python -m pip install .
researchos-qbi --help
```

The synthetic Bell example produces ideal probabilities 0.5 for `00` and `11`, and seeded samples approximating them. Its illustrative assumptions imply 2,000 physical qubits and 0.10192 s total estimated workflow time. These are accounting fixtures, not experimentally calibrated requirements. The fictional classical baseline takes 0.001 s; its declared-runtime ratio is less than one and establishes no advantage.

Use a new output directory per run. Existing directories are rejected. Local bundles are ignored by Git.

## Your benchmark workflow

1. Copy the example and assign a unique ID, owner, hypothesis, workload reference, input basis, seed, shots and circuit.
2. Supply an independently justified expected output distribution and owner-defined quality threshold. Omitted bitstrings have probability zero.
3. Optionally supply resource assumptions, with a versioned derivation/reference. Missing assumptions remain `no-data`. Their workload correspondence must be reviewed by the researcher.
4. Add a classical baseline only when problem instance, output quality, workload count and timing scope are explicit. A declared comparability flag is not independent validation.
5. For observed counts, include acquisition method and evidence IDs. Experimental records require observed counts and evidence references. The simulator still runs separately as an ideal classical calculation.
6. Put evidence under the record directory, use `researchos-qbi hash <file>`, and declare each relative path, digest, description and evidence ID.
7. Validate, run, verify, and review the report and limitations. Keep calibration, hardware/compiler versions, sampling plans and uncertainty analysis with your evidence.

Evidence paths cannot escape the record directory, including through symlinks. The runner captures verified file bytes so bundles can be checked independently of the original locations. Checksum matching does not establish authenticity or scientific validity. Keep unpublished partner data and credentials out of this public repository.

## Bundle output

| File | Contents |
| --- | --- |
| `record.json` | Exact original input bytes |
| `results.json` | Ideal probabilities, sampled counts/TVD, declared observations, resource accounting, baseline comparison and limitations |
| `outcomes.csv` | Expected/ideal probabilities, sampled counts and optional observed counts |
| `report.md` | Human-readable findings with explicit input basis and limitations |
| `evidence/0000.bin`, … | Captured original evidence bytes |
| `manifest.json` | Artifact hashes, evidence mapping and Python version |

`verify` checks artifact digests, evidence-to-record hashes, and reproduction of numerical results, report and CSV. It is not a signed audit trail. Identical inputs and runtime produce identical bundles; manifests record the Python version. See reproducibility limits in [the model documentation](docs/MODEL.md).

## Documentation and verification

- [Record contract](docs/RECORDS.md)
- [Simulator and resource model](docs/MODEL.md)
- [QBI-aligned research plan](docs/RESEARCH_PLAN.md)
- [Primary sources and submission context](docs/SOURCES.md)
- [Contributing](CONTRIBUTING.md)

CI installs the package, runs the test suite, exercises the complete example workflow and uploads its synthetic bundle on Python 3.10–3.13. The existing [license](LICENSE) is preserved.

## Interactive browser app

The `web/` directory contains a responsive benchmark studio with circuit preview, background-worker simulation, probability charts, resource/baseline inputs, a local record library, JSON/CSV/Markdown exports, and SHA-256 evidence comparison. Serve with `python -m http.server 8000 --directory web` and open `http://localhost:8000`. Run web model checks with `node web/tests/model.test.mjs`. Use localhost or HTTPS for modules, workers and Web Crypto.

The browser implements Python-compatible integer-seeded MT19937 sampling; parity tests compare complete results against Python across multiple seeds/circuits. Derived resource integers beyond JavaScript's safe integer range are rejected with a direction to use the Python CLI. Numerical boundary differences may still occur across runtimes.

Records stay on the current browser and origin. Export regularly; no cross-device, GitHub or CLI synchronization is configured. Record JSON exports work with the CLI. Web result/report exports are summaries, not CLI evidence bundles. Original evidence files are never uploaded or retained by the app, and imported records do not re-verify them. The form creates synthetic/simulation records; hardware observation records can be imported with their evidence declarations and original files retained for CLI verification.

Private hosted app: https://researchos-tect-quantum-benchmarking.troturn31.chatgpt.site
