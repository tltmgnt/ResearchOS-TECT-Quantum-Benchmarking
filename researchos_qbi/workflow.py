"""Portable benchmark bundles with captured evidence and recomputation checks."""
import csv
import io
import platform
import re
import shutil
import tempfile
from pathlib import Path
from .records import dumps, evidence_bytes, parse_json, read_json, require, sha, validate
from .model import analyze


def verify_evidence(record, root):
    captured = []
    for item in record["evidence"]:
        data = evidence_bytes(root, item["path"])
        require(sha(data) == item["sha256"], f"evidence checksum mismatch: {item['path']}")
        captured.append((item, data))
    return captured


def report(record, result):
    resources = result["resources"]
    lines = [f"# {record['id']}", "", record["title"], "",
             f"Input basis: **{record['data_kind']}**. Simulator output: **ideal-statevector**.", "",
             result["limitations"], "", f"Shots: {record['shots']}; seed: {record['seed']}.",
             f"Ideal TVD: {result['ideal_tvd']:.6g}; sampled TVD: {result['sampled_tvd']:.6g}.",
             f"Sampled quality criterion met: {result['sampled_quality_met']} (owner-defined limit {record['quality_tvd_limit']:g}).",
             "", f"Hardware/declared observations: {result['observations']['status']}.", "",
             "## Resource accounting", ""]
    if resources["status"] == "no-data":
        lines.append("No resource assumptions supplied. Estimates remain no-data.")
    else:
        lines += [f"- Assumed physical qubits: {resources['physical_qubits']}",
                  f"- Estimated total workflow time: {resources['estimated_workflow_s']:.6g} s",
                  f"- Failure union bound across all shots: {resources['failure_union_bound_all_shots']:.6g}",
                  "- These are declared-assumption calculations, not compiled or measured fault-tolerant resources."]
    if result["observations"]["status"] != "no-data":
        observed = result["observations"]
        lines += ["", f"Declared observation TVD: {observed['tvd']:.6g}; quality criterion met: {observed['quality_met']} ({observed['data_kind']} inputs)."]
    lines += ["", f"Baseline comparison: {result['baseline_comparison']['status']}."]
    ratio = result["baseline_comparison"]["declared_runtime_ratio"]
    if ratio is not None:
        lines.append(f"Declared classical / estimated quantum runtime ratio: {ratio:.6g}. This is not measured speedup.")
    lines += ["", "## Outcome distribution", "", "| Bitstring | Ideal probability | Sampled count |", "| --- | ---: | ---: |"]
    for bits in sorted(result["ideal_probabilities"].keys() | record["expected_probabilities"].keys()):
        lines.append(f"| {bits} | {result['ideal_probabilities'].get(bits, 0):.8g} | {result['sampled_counts'].get(bits, 0)} |")
    return "\n".join(lines) + "\n"


def outcome_csv(record, result):
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["bitstring", "expected_probability", "ideal_probability", "sampled_count", "observed_count"])
    observed = record.get("observations")
    keys = result["ideal_probabilities"].keys() | record["expected_probabilities"].keys()
    if observed:
        keys |= observed["counts"].keys()
    for bits in sorted(keys):
        writer.writerow([bits, record["expected_probabilities"].get(bits, 0), result["ideal_probabilities"].get(bits, 0), result["sampled_counts"].get(bits, 0), observed["counts"].get(bits, 0) if observed else ""])
    return buf.getvalue()


def run(path, output):
    path, output = Path(path), Path(output)
    require(not output.exists(), "output exists; use a new run directory")
    raw = path.read_bytes()
    record = validate(parse_json(raw.decode("utf-8")))
    captured = verify_evidence(record, path.parent)
    result = analyze(record)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".researchos-", dir=output.parent))
    try:
        (staging / "record.json").write_bytes(raw)
        (staging / "results.json").write_text(dumps(result), encoding="utf-8")
        (staging / "report.md").write_text(report(record, result), encoding="utf-8")
        (staging / "outcomes.csv").write_text(outcome_csv(record, result), encoding="utf-8")
        for i, (_, data) in enumerate(captured):
            dest = staging / "evidence" / f"{i:04d}.bin"
            dest.parent.mkdir(exist_ok=True)
            dest.write_bytes(data)
        files = {p.relative_to(staging).as_posix(): sha(p.read_bytes()) for p in sorted(staging.rglob("*")) if p.is_file()}
        manifest = {"schema_version": 1, "files": files, "python_version": platform.python_version(),
                    "evidence_map": [{"id": e["id"], "bundle_path": f"evidence/{i:04d}.bin"} for i, (e, _) in enumerate(captured)]}
        (staging / "manifest.json").write_text(dumps(manifest), encoding="utf-8")
        output.mkdir()
        for p in staging.iterdir():
            shutil.move(str(p), output / p.name)
    finally:
        shutil.rmtree(staging)
    return result


def verify_bundle(root):
    root = Path(root)
    m = read_json(root / "manifest.json")
    require(isinstance(m, dict) and m.get("schema_version") == 1, "invalid manifest")
    files = m.get("files")
    require(isinstance(files, dict) and {"record.json", "results.json", "report.md", "outcomes.csv"} <= files.keys(), "incomplete manifest")
    for name, expected in files.items():
        require(isinstance(expected, str) and bool(re.fullmatch(r"[a-f0-9]{64}", expected)), "invalid manifest digest")
        require(sha(evidence_bytes(root, name)) == expected, f"bundle checksum mismatch: {name}")
    record = validate(read_json(root / "record.json"))
    result = analyze(record)
    require(read_json(root / "results.json") == result, "numerical results do not reproduce")
    require((root / "report.md").read_text(encoding="utf-8") == report(record, result), "report does not reproduce")
    # Text newline translation is normalized before comparing CSV exports.
    actual_csv = (root / "outcomes.csv").read_text(encoding="utf-8")
    require(actual_csv == outcome_csv(record, result).replace("\r\n", "\n"), "CSV does not reproduce")
    mapping = [{"id": e["id"], "bundle_path": f"evidence/{i:04d}.bin"} for i, e in enumerate(record["evidence"])]
    require(m.get("evidence_map") == mapping, "invalid evidence map")
    for entry, original in zip(mapping, record["evidence"]):
        require(entry["bundle_path"] in files, "evidence absent from manifest")
        require(sha(evidence_bytes(root, entry["bundle_path"])) == original["sha256"], "captured evidence no longer matches record")
    return m
