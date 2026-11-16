"""Exact bounded state-vector simulator and explicitly assumed resource arithmetic."""
import bisect
import math
import random
from .records import dumps, require, validate

LIMITATIONS = (
    "Ideal small-circuit simulation and declared resource accounting only. No noise, "
    "fault-tolerant compilation, error correction, decoding, routing, magic-state "
    "factory scheduling, or hardware execution is implemented. Runtime ratios "
    "compare declared timings, not measured quantum speedup. A passing quality "
    "check does not establish quantum advantage, utility-scale feasibility or DARPA compliance."
)


def probabilities(circuit):
    n = circuit["qubits"]
    state = [0j] * (2**n)
    state[0] = 1+0j
    for gate in circuit["gates"]:
        mask = 1 << gate["target"]
        for i in range(len(state)):
            if i & mask:
                continue
            j = i | mask
            if gate["gate"] == "h":
                a, b = state[i], state[j]
                state[i], state[j] = (a+b)/math.sqrt(2), (a-b)/math.sqrt(2)
            elif gate["gate"] == "x":
                state[i], state[j] = state[j], state[i]
            elif gate["gate"] == "z":
                state[j] = -state[j]
            elif i & (1 << gate["control"]):
                state[i], state[j] = state[j], state[i]
    weights = [abs(a)**2 for a in state]
    total = sum(weights)
    require(math.isfinite(total) and abs(total-1) < 1e-9, "state normalization failed")
    return {format(i, f"0{n}b"): p/total for i, p in enumerate(weights) if p > 0}


def sample(probs, shots, seed):
    rng = random.Random(seed)
    keys = sorted(probs)
    cumulative, total = [], 0.0
    for key in keys:
        total += probs[key]
        cumulative.append(total)
    cumulative[-1] = 1.0
    counts = {}
    for _ in range(shots):
        key = keys[min(bisect.bisect_right(cumulative, rng.random()), len(keys)-1)]
        counts[key] = counts.get(key, 0) + 1
    return counts


def tvd(p, q):
    return min(1.0, .5 * sum(abs(p.get(k, 0)-q.get(k, 0)) for k in p.keys() | q.keys()))


def estimate(resources, shots):
    if resources is None:
        return {"status": "no-data"}
    r = resources
    cycles = r["logical_depth"] * r["cycles_per_layer"]
    locations = r["logical_qubits"] * cycles * shots
    quantum_s = cycles * r["cycle_time_us"] * 1e-6 * shots
    result = {"status": "assumption-based", "physical_qubits": r["logical_qubits"] * r["physical_qubits_per_logical"] + r["factory_physical_qubits"],
              "cycles_per_shot": cycles, "logical_qubit_cycle_locations_all_shots": locations,
              "estimated_quantum_s": quantum_s,
              "estimated_workflow_s": r["classical_pre_s"] + quantum_s + r["classical_post_s"],
              "failure_union_bound_all_shots": min(1.0, locations * r["logical_error_per_qubit_cycle"]),
              "assumption_reference": r["assumption_reference"]}
    dumps(result)
    require(result["estimated_workflow_s"] > 0, "estimated runtime underflowed to zero")
    return result


def analyze(record):
    r = validate(record)
    probs = probabilities(r["circuit"])
    counts = sample(probs, r["shots"], r["seed"])
    sampled = {k: v/r["shots"] for k, v in counts.items()}
    observed = r.get("observations")
    observations = {"status": "no-data"}
    if observed is not None:
        distance = tvd({k: v/r["shots"] for k, v in observed["counts"].items()}, r["expected_probabilities"])
        observations = {"status": "declared-observations", "data_kind": r["data_kind"], "tvd": distance,
                        "quality_met": distance <= r["quality_tvd_limit"]}
    resource = estimate(r.get("resources"), r["shots"])
    baseline = r.get("classical_baseline")
    comparison = {"status": "no-data", "declared_runtime_ratio": None}
    if baseline is not None and resource["status"] != "no-data":
        comparison["status"] = "not-comparable"
        quality = observations.get("quality_met", tvd(sampled, r["expected_probabilities"]) <= r["quality_tvd_limit"])
        if baseline["same_problem_and_quality"] and quality and baseline["tvd"] <= r["quality_tvd_limit"]:
            comparison = {"status": "declared-comparable", "declared_runtime_ratio": baseline["runtime_s"]/resource["estimated_workflow_s"],
                          "interpretation": "Classical declared runtime / quantum estimated workflow runtime; not a speedup measurement"}
    result = {"analysis": "ideal-circuit-and-resource-accounting-v1", "runner_version": "0.1.0",
              "input_data_kind": r["data_kind"], "simulation_kind": "ideal-statevector",
              "bit_order": "q0 is least significant; strings read q[n-1]...q0",
              "ideal_probabilities": probs, "sampled_counts": counts,
              "ideal_tvd": tvd(probs, r["expected_probabilities"]),
              "sampled_tvd": tvd(sampled, r["expected_probabilities"]),
              "sampled_quality_met": tvd(sampled, r["expected_probabilities"]) <= r["quality_tvd_limit"],
              "observations": observations, "resources": resource, "baseline_comparison": comparison,
              "limitations": LIMITATIONS}
    dumps(result)
    return result
