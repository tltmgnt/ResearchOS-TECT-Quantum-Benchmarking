"""Versioned record contract and strict JSON handling."""
import hashlib
import json
import math
import re
from pathlib import Path


class ValidationError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ValidationError(message)


def dumps(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"


def parse_json(data):
    def constant(value):
        raise ValidationError(f"non-finite JSON constant: {value}")
    def unique(pairs):
        result = {}
        for k, v in pairs:
            require(k not in result, f"duplicate JSON key: {k}")
            result[k] = v
        return result
    return json.loads(data, parse_constant=constant, object_pairs_hook=unique)


def read_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def text(v, name):
    require(isinstance(v, str) and bool(v.strip()), f"{name} must be a nonempty string")


def integer(v, name, minimum=0, maximum=10**12):
    require(type(v) is int and minimum <= v <= maximum, f"{name} must be an integer in [{minimum}, {maximum}]")


def number(v, name, positive=False):
    require(type(v) in (int, float), f"{name} must be numeric")
    try:
        finite = math.isfinite(v)
    except OverflowError:
        finite = False
    require(finite and (v > 0 if positive else v >= 0), f"{name} must be finite and {'positive' if positive else 'nonnegative'}")


def safe_path(value):
    text(value, "evidence path")
    require(not Path(value).is_absolute() and "\\" not in value and not re.match(r"^[A-Za-z]:", value)
            and not any(p in (".", "..") for p in value.split("/")), "evidence path must be relative without traversal")
    return Path(value)


def evidence_bytes(root, path):
    root = Path(root).resolve()
    dest = (root / safe_path(path)).resolve()
    require(dest.is_relative_to(root), "evidence resolves outside record directory")
    return dest.read_bytes()


def validate(r):
    require(isinstance(r, dict), "record must be an object")
    require(type(r.get("schema_version")) is int and r["schema_version"] == 1, "schema_version must be integer 1")
    require(isinstance(r.get("id"), str) and bool(re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", r["id"])), "invalid record id")
    for k in ("title", "owner", "hypothesis", "workload_reference"):
        text(r.get(k), k)
    require(r.get("data_kind") in ("synthetic", "simulation", "experimental"), "invalid data_kind")
    integer(r.get("seed"), "seed", 0, 2**32-1)
    integer(r.get("shots"), "shots", 1, 1000000)
    circuit = r.get("circuit")
    require(isinstance(circuit, dict), "circuit must be an object")
    integer(circuit.get("qubits"), "qubits", 1, 12)
    n = circuit["qubits"]
    gates = circuit.get("gates")
    require(isinstance(gates, list) and len(gates) <= 10000, "gates must be an array of at most 10000 operations")
    require((2**n)*len(gates) <= 20000000, "circuit exceeds 20 million state-amplitude gate operations")
    for g in gates:
        require(isinstance(g, dict) and g.get("gate") in ("h", "x", "z", "cx"), "supported gates: h, x, z, cx")
        integer(g.get("target"), "gate target", 0, n-1)
        if g["gate"] == "cx":
            integer(g.get("control"), "gate control", 0, n-1)
            require(g["control"] != g["target"], "CX control and target must differ")
    expected = r.get("expected_probabilities")
    require(isinstance(expected, dict) and bool(expected), "expected_probabilities must be a nonempty object")
    for bits, p in expected.items():
        require(isinstance(bits, str) and bool(re.fullmatch(r"[01]{%d}" % n, bits)), "invalid expected bitstring")
        number(p, "expected probability")
        require(p <= 1, "probability must not exceed 1")
    require(math.isclose(sum(expected.values()), 1, abs_tol=1e-12, rel_tol=0), "expected probabilities must sum to 1")
    number(r.get("quality_tvd_limit"), "quality_tvd_limit")
    require(r["quality_tvd_limit"] <= 1, "quality_tvd_limit must be <= 1")
    evidence = r.get("evidence")
    require(isinstance(evidence, list), "evidence must be an array")
    refs, paths = set(), set()
    for e in evidence:
        require(isinstance(e, dict), "evidence entry must be an object")
        text(e.get("id"), "evidence id")
        text(e.get("description"), "evidence description")
        safe_path(e.get("path"))
        require(e["id"] not in refs and e["path"] not in paths, "duplicate evidence id or path")
        refs.add(e["id"])
        paths.add(e["path"])
        require(isinstance(e.get("sha256"), str) and bool(re.fullmatch(r"[a-f0-9]{64}", e["sha256"])), "invalid evidence sha256")
    observed = r.get("observations")
    if observed is not None:
        require(isinstance(observed, dict) and isinstance(observed.get("counts"), dict) and bool(observed["counts"]), "observations requires counts")
        for bits, count in observed["counts"].items():
            require(isinstance(bits, str) and bool(re.fullmatch(r"[01]{%d}" % n, bits)), "invalid observed bitstring")
            integer(count, "observed count", 0, r["shots"])
        require(sum(observed["counts"].values()) == r["shots"], "observed counts must sum to shots")
        text(observed.get("method"), "observation method")
        links = observed.get("evidence_ids")
        require(isinstance(links, list) and all(isinstance(x, str) and x in refs for x in links), "unknown observation evidence reference")
        if r["data_kind"] == "experimental":
            require(bool(links), "experimental observations require evidence references")
    if r["data_kind"] == "experimental":
        require(bool(evidence) and observed is not None, "experimental records require evidence and observed counts")
    resources = r.get("resources")
    if resources is not None:
        require(isinstance(resources, dict), "resources must be an object or null")
        for k in ("logical_qubits", "logical_depth", "cycles_per_layer", "physical_qubits_per_logical"):
            integer(resources.get(k), k, 1)
        integer(resources.get("factory_physical_qubits"), "factory_physical_qubits")
        number(resources.get("cycle_time_us"), "cycle_time_us", True)
        for k in ("classical_pre_s", "classical_post_s", "logical_error_per_qubit_cycle"):
            number(resources.get(k), k)
        require(resources["logical_error_per_qubit_cycle"] <= 1, "logical error probability must be <= 1")
        text(resources.get("assumption_reference"), "assumption_reference")
        require(resources["logical_qubits"] >= n, "resource logical_qubits cannot be smaller than benchmark qubits")
    baseline = r.get("classical_baseline")
    if baseline is not None:
        require(isinstance(baseline, dict), "classical_baseline must be an object or null")
        number(baseline.get("runtime_s"), "baseline runtime_s", True)
        number(baseline.get("tvd"), "baseline tvd")
        require(baseline["tvd"] <= 1, "baseline tvd must be <= 1")
        text(baseline.get("method"), "baseline method")
        text(baseline.get("reference"), "baseline reference")
        require(type(baseline.get("same_problem_and_quality")) is bool, "baseline comparability flag must be boolean")
    return r
