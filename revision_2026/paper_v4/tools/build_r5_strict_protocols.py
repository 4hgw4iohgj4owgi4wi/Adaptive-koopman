"""Build versioned protocols for the R5 strict solver chain.

Stages are deliberately sequential.  N0 is frozen only after the strict baseline has
completed its audit and figure QA; N1 is frozen only after N0; the total gate is frozen
only after all three runs.  This prevents a protocol from claiming future evidence.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


PAPER = Path(__file__).resolve().parents[1]
PROTOCOL = PAPER / "protocol"
SETTINGS = {
    "eps_abs": 1e-6,
    "eps_rel": 1e-6,
    "scaled_termination": False,
    "max_iter": 4000,
    "polishing": True,
}
TOLERANCES = {
    "requested_steering_acceptance_tolerance_rad": 1e-6,
    "applied_steering_machine_tolerance_rad": 1e-12,
}

BASELINE_PROTOCOL = "protocol/R5_STRICT_BASELINE_P0_2MS_GPU_20260917_v2.json"
PROBE_PROTOCOL = "protocol/R5_STRICT_SOLVER_PROBE_20260917_v1.json"
N0_PROTOCOL = "protocol/R5_STRICT_N0_GPU_20260917_v2.json"
N1_PROTOCOL = "protocol/R5_STRICT_N1_GPU_20260917_v2.json"
GATE_PROTOCOL = "protocol/R5_INFORMATION_GATE_20260917_v3.json"

BASELINE_RUN = "results/20260917_R5_STRICT_BASELINE_P0_2MS_GPU02"
N0_RUN = "results/20260917_R5_STRICT_N0_GPU02"
N1_RUN = "results/20260917_R5_STRICT_N1_GPU02"
N0_NO_OP = "analysis/20260917_R5_STRICT_N0_NO_OP_01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(PAPER)).replace("\\", "/")


def identity(paths: list[str]) -> list[dict]:
    records = []
    for item in dict.fromkeys(paths):
        path = PAPER / item
        if not path.is_file():
            raise FileNotFoundError(item)
        records.append({"path": item, "sha256": sha(path)})
    return records


def write(rel_path: str, payload: dict) -> dict:
    path = PAPER / rel_path
    if path.exists():
        raise FileExistsError("REFUSING_TO_OVERWRITE_PROTOCOL:" + rel_path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": rel_path, "sha256": sha(path)}


COMMON_COMPUTE = [
    "src/paper_v4_core/controllers/physical_tracking_pilot.py",
    "src/paper_v4_core/gpu_port/__init__.py",
    "src/paper_v4_core/gpu_port/physics_torch.py",
    "src/paper_v4_core/gpu_port/rollout_batch.py",
    "src/paper_v4_core/gpu_port/gpu_worker.py",
    "src/paper_v4_core/gpu_port/ipc_backend.py",
    "src/paper_v4_core/plant/four_vehicle_common.py",
    "src/paper_v4_core/plant/connector_adapter.py",
    "src/paper_v4_core/plant/connector_r3.py",
    "src/paper_v4_core/plant/internal_force.py",
    "src/paper_v4_core/plant/load_transfer.py",
    "src/paper_v4_core/plant/event_substep.py",
    "src/paper_v4_core/e01_100m.py",
    "src/paper_v4_core/pilot_runner.py",
    "src/paper_v4_core/reference_geometry.py",
    "src/paper_v4_core/references.py",
    "src/paper_v4_core/failure_boundary.py",
]


def build_initial() -> list[dict]:
    preflight_path = PAPER / "analysis/20260917_R5_STRICT_PREFLIGHT_01/preflight.json"
    preflight_manifest_path = PAPER / "analysis/20260917_R5_STRICT_PREFLIGHT_01/figure_manifest.json"
    probe_path = PAPER / "analysis/20260917_R5_STRICT_SOLVER_PROBE_01/probe.json"
    probe_manifest_path = PAPER / "analysis/20260917_R5_STRICT_SOLVER_PROBE_01/figure_manifest.json"
    for item in (preflight_path, preflight_manifest_path, probe_path, probe_manifest_path, PAPER / PROBE_PROTOCOL):
        if not item.is_file():
            raise FileNotFoundError("S2_EVIDENCE_NOT_READY:" + rel(item))
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    preflight_manifest = json.loads(preflight_manifest_path.read_text(encoding="utf-8"))
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    probe_manifest = json.loads(probe_manifest_path.read_text(encoding="utf-8"))
    if preflight.get("status") != "PASS_R5_STRICT_PREFLIGHT":
        raise ValueError("S2_PREFLIGHT_NOT_PASS")
    if preflight_manifest.get("figure_status") != "PASS_VISUAL_QA":
        raise ValueError("S2_PREFLIGHT_FIGURE_NOT_PASS")
    if probe.get("status") != "PASS_R5_STRICT_SOLVER_PROBE":
        raise ValueError("S2_SOLVER_PROBE_NOT_PASS")
    if probe_manifest.get("figure_status") != "PASS_VISUAL_QA":
        raise ValueError("S2_SOLVER_PROBE_FIGURE_NOT_PASS")
    if probe.get("protocol_sha256") != sha(PAPER / PROBE_PROTOCOL):
        raise ValueError("S2_SOLVER_PROBE_PROTOCOL_IDENTITY_MISMATCH")

    base = json.loads((PROTOCOL / "R4_P0_2MS_GPU_20260916_v2.json").read_text(encoding="utf-8"))
    base["protocol_id"] = "R5-STRICT-BASELINE-P0-2MS-GPU-v2"
    base["authorization"] = ("User instruction 2026-09-17: verify the repairs and update the MD to guide execution; "
                             "freezing this protocol does not claim that the full-route run has started.")
    base["run"]["output"] = BASELINE_RUN
    base["run"]["deadline_hours"] = 5.0
    base["solver_settings"] = copy.deepcopy(SETTINGS)
    base["acceptance_tolerances"] = copy.deepcopy(TOLERANCES)
    base["role"] = "R5 strict same-backend P0 baseline; full state, no measurement noise"
    base["strict_chain"] = {
        "order": 1,
        "next": N0_PROTOCOL,
        "release_rule": "COMPLETED 2379/2379, single-run audit PASS, PNG/SVG and figure QA PASS",
        "old_results_are_read_only": True,
    }
    base["s2_evidence"] = {
        "preflight": {"path": rel(preflight_path), "sha256": sha(preflight_path), "status": preflight["status"]},
        "preflight_figure_manifest": {"path": rel(preflight_manifest_path), "sha256": sha(preflight_manifest_path),
                                      "figure_status": preflight_manifest["figure_status"]},
        "solver_probe_protocol": {"path": PROBE_PROTOCOL, "sha256": sha(PAPER / PROBE_PROTOCOL)},
        "solver_probe": {"path": rel(probe_path), "sha256": sha(probe_path), "status": probe["status"]},
        "solver_probe_figure_manifest": {"path": rel(probe_manifest_path), "sha256": sha(probe_manifest_path),
                                         "figure_status": probe_manifest["figure_status"]},
        "claim_boundary": "The fixed-QP probe advances no plant trajectory; S3 remains a required full-route run.",
    }
    base["preconditions"] = {
        "strict_chain_readiness": "READY_TO_START_S3_BASELINE",
        "s0_environment": {
            "python": "3.11.14",
            "osqp": "1.1.1",
            "numpy": "2.0.1",
            "scipy": "1.17.1",
            "torch": "2.12.0.dev20260304+cu128",
            "cuda_device": "NVIDIA GeForce RTX 5080",
        },
        "s1_source_repairs_compiled": True,
        "s2_preflight_pass": True,
        "s2_solver_probe_pass": True,
        "output_does_not_exist_when_frozen": not (PAPER / BASELINE_RUN).exists(),
        "total_ticks": 2379,
    }
    base.pop("analysis_plan", None)
    base.pop("decision_after_completion", None)
    base["controller_identity"]["current_sha256"] = sha(PAPER / "src/paper_v4_core/controllers/physical_tracking_pilot.py")
    baseline_identity = [
        "src/paper_v4_core/diagnostics/full_route_gpu_runner.py",
        "src/paper_v4_core/diagnostics/gpu_closed_loop_runner.py",
        *COMMON_COMPUTE,
        "tools/r4_single_run_audit.py",
        "tools/r4_cell_figure.py",
        PROBE_PROTOCOL,
        rel(preflight_path),
        rel(preflight_manifest_path),
        rel(probe_path),
        rel(probe_manifest_path),
        "analysis/20260915_G3_RESTART_EQUIVALENCE_02/g3_restart_equivalence.json",
        "analysis/20260915_G3B_DIVERGENCE_MECHANISM_01/g3_divergence_mechanism.json",
        "protocol/G3_RESTART_EQUIVALENCE_20260915_v4.json",
        "protocol/G3B_DIVERGENCE_MECHANISM_20260915_v1.json",
        "results/20260915_RTX5080_G0_G2_05/qualification.json",
        "gpu_platform_decision_20260916.md",
        "qp_rate_penalty_sign_defect_20260916.md",
        "analysis/20260916_RATE_PENALTY_FIX_VERIFY_01/rate_penalty_fix_verify.json",
    ]
    base["identity_files"] = identity(baseline_identity)

    return [write(BASELINE_PROTOCOL, base)]


def require_run_evidence(run: str, protocol: str) -> list[str]:
    paths = [
        protocol,
        f"{run}/metrics.json",
        f"{run}/raw.npz",
        f"{run}/single_run_audit.json",
        f"{run}/figures/figure_manifest.json",
    ]
    for item in paths:
        if not (PAPER / item).is_file():
            raise FileNotFoundError("PREREQUISITE_NOT_READY:" + item)
    audit = json.loads((PAPER / f"{run}/single_run_audit.json").read_text(encoding="utf-8"))
    manifest = json.loads((PAPER / f"{run}/figures/figure_manifest.json").read_text(encoding="utf-8"))
    if audit.get("status") != "PASS_SINGLE_RUN_AUDIT":
        raise ValueError("PREREQUISITE_AUDIT_NOT_PASS:" + run)
    if manifest.get("figure_status") != "PASS_VISUAL_QA":
        raise ValueError("PREREQUISITE_FIGURE_NOT_PASS:" + run)
    return paths


def r5_template(noise: str, output: str, order: int) -> dict:
    old_name = "R5_N0_GPU_20260916_v1.json" if noise == "none" else "R5_N1_GPU_20260916_v1.json"
    data = json.loads((PROTOCOL / old_name).read_text(encoding="utf-8"))
    data["protocol_id"] = f"R5-STRICT-{'N0-noiseless' if noise == 'none' else 'N1-basic-noise-seed5105'}-GPU-v2"
    data["authorization"] = "Sequential strict-chain release under R5_STRICT_CHAIN_EXECUTION_20260917.md."
    data["run"]["output"] = output
    data["run"]["deadline_hours"] = 5.0
    data["solver_settings"] = copy.deepcopy(SETTINGS)
    data["acceptance_tolerances"] = copy.deepcopy(TOLERANCES)
    data["strict_chain"] = {
        "order": order,
        "previous": BASELINE_PROTOCOL if order == 2 else N0_PROTOCOL,
        "next": N1_PROTOCOL if order == 2 else GATE_PROTOCOL,
        "release_rule": "Prior run audit PASS and figure QA PASS; current run must then meet the same two independent gates.",
        "old_results_are_read_only": True,
    }
    data.pop("launch_defect_record", None)
    data.pop("refrozen_reason", None)
    return data


def build_n0() -> list[dict]:
    data = r5_template("none", N0_RUN, 2)
    prerequisites = require_run_evidence(BASELINE_RUN, BASELINE_PROTOCOL)
    data["noiseless_no_op_gate"]["baseline"] = BASELINE_RUN
    data["identity_files"] = identity([
        "src/paper_v4_core/r5_runner.py",
        "src/paper_v4_core/information/legal_information.py",
        "src/paper_v4_core/r5_information_tests.py",
        "src/paper_v4_core/diagnostics/full_route_gpu_runner.py",
        *COMMON_COMPUTE,
        "tools/r5_single_run_audit.py",
        "tools/r4_cell_figure.py",
        "tools/r5_strict_no_op_gate.py",
        "results/20260916_R5_CONTRACT_TESTS_01/r5_information_tests.json",
        *prerequisites,
    ])
    return [write(N0_PROTOCOL, data)]


def build_n1() -> list[dict]:
    data = r5_template("basic", N1_RUN, 3)
    prerequisites = require_run_evidence(N0_RUN, N0_PROTOCOL)
    no_op_report = PAPER / N0_NO_OP / "no_op.json"
    no_op_manifest = PAPER / N0_NO_OP / "figure_manifest.json"
    for item in (no_op_report, no_op_manifest):
        if not item.is_file():
            raise FileNotFoundError("PREREQUISITE_NOT_READY:" + rel(item))
    no_op = json.loads(no_op_report.read_text(encoding="utf-8"))
    no_op_figure = json.loads(no_op_manifest.read_text(encoding="utf-8"))
    if no_op.get("status") != "PASS_R5_STRICT_N0_NO_OP":
        raise ValueError("PREREQUISITE_N0_NO_OP_NOT_PASS")
    if no_op_figure.get("figure_status") != "PASS_VISUAL_QA":
        raise ValueError("PREREQUISITE_N0_NO_OP_FIGURE_NOT_PASS")
    data["strict_chain"]["n0_no_op_evidence"] = {
        "report": {"path": rel(no_op_report), "sha256": sha(no_op_report), "status": no_op["status"]},
        "figure_manifest": {"path": rel(no_op_manifest), "sha256": sha(no_op_manifest),
                            "figure_status": no_op_figure["figure_status"]},
    }
    data["identity_files"] = identity([
        "src/paper_v4_core/r5_runner.py",
        "src/paper_v4_core/information/legal_information.py",
        "src/paper_v4_core/r5_information_tests.py",
        "src/paper_v4_core/diagnostics/full_route_gpu_runner.py",
        *COMMON_COMPUTE,
        "tools/r5_single_run_audit.py",
        "tools/r4_cell_figure.py",
        "tools/r5_strict_no_op_gate.py",
        "results/20260916_R5_CONTRACT_TESTS_01/r5_information_tests.json",
        rel(no_op_report),
        rel(no_op_manifest),
        *prerequisites,
    ])
    return [write(N1_PROTOCOL, data)]


def build_gate() -> list[dict]:
    evidence = []
    for run, protocol in ((BASELINE_RUN, BASELINE_PROTOCOL), (N0_RUN, N0_PROTOCOL), (N1_RUN, N1_PROTOCOL)):
        evidence.extend(require_run_evidence(run, protocol))
    data = json.loads((PROTOCOL / "R5_INFORMATION_GATE_20260917_v2.json").read_text(encoding="utf-8"))
    data["protocol_id"] = "R5-information-gate-v3-strict-chain"
    data["output"] = "analysis/20260917_R5_STRICT_INFORMATION_GATE_01"
    data["inputs"].update({"baseline": BASELINE_RUN, "n0": N0_RUN, "n1": N1_RUN})
    data["no_op_gate"]["excluded_with_reason"] = {}
    data["no_op_gate"].pop("measured_preview", None)
    data["solver_settings"] = copy.deepcopy(SETTINGS)
    data["acceptance_tolerances"] = copy.deepcopy(TOLERANCES)
    data["identity_files"] = identity([
        "tools/r5_information_gate.py",
        "tools/r5_information_figures.py",
        "results/20260916_R5_CONTRACT_TESTS_01/r5_information_tests.json",
        *sorted(set(evidence)),
    ])
    data["supersedes_protocol"] = {
        "path": "protocol/R5_INFORMATION_GATE_20260917_v2.json",
        "sha256": sha(PROTOCOL / "R5_INFORMATION_GATE_20260917_v2.json"),
        "reason": "v2 points to an aborted baseline, pins a stale N1 identity and does not consume the strict three-run audit/figure chain.",
    }
    return [write(GATE_PROTOCOL, data)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("initial", "n0", "n1", "gate"), required=True)
    args = parser.parse_args()
    builders = {"initial": build_initial, "n0": build_n0, "n1": build_n1, "gate": build_gate}
    records = builders[args.stage]()
    print(json.dumps({"status": "PASS_PROTOCOLS_FROZEN", "stage": args.stage, "protocols": records}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
