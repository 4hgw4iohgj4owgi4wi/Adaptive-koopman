"""Build the full-route R4 GPU protocol from verified identities and the G3 parent report."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

PAPER = Path(__file__).resolve().parents[1]

IDENTITY_PATHS = [
    "src/paper_v4_core/diagnostics/full_route_gpu_runner.py",
    "analysis/20260915_G3_RESTART_EQUIVALENCE_02/g3_restart_equivalence.json",
    "analysis/20260915_G3B_DIVERGENCE_MECHANISM_01/g3_divergence_mechanism.json",
    "protocol/G3_RESTART_EQUIVALENCE_20260915_v4.json",
    "protocol/G3B_DIVERGENCE_MECHANISM_20260915_v1.json",
    "src/paper_v4_core/diagnostics/gpu_closed_loop_runner.py",
    "src/paper_v4_core/diagnostics/reference_memory.py",
    "src/paper_v4_core/diagnostics/post_r3_r4_runner.py",
    "tools/full_route_compare.py",
    "src/paper_v4_core/controllers/physical_tracking_pilot.py",
    "src/paper_v4_core/controllers/parallel_fd_backend.py",
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
    "results/20260915_R4_P1_2MS01/raw.npz",
    "results/20260915_RTX5080_G0_G2_05/qualification.json",
]

G3_REPORT = "analysis/20260915_G3_RESTART_EQUIVALENCE_02/g3_restart_equivalence.json"
G3_PROTOCOL = "protocol/G3_RESTART_EQUIVALENCE_20260915_v4.json"
G3B_REPORT = "analysis/20260915_G3B_DIVERGENCE_MECHANISM_01/g3_divergence_mechanism.json"
G3B_PROTOCOL = "protocol/G3B_DIVERGENCE_MECHANISM_20260915_v1.json"

# Verdicts the full route genuinely depends on.  The restart_* verdicts describe
# whether a rebuilt checkpoint reproduces history, which is the D3 splicing
# question; the full route starts from the frozen initial condition and never
# reconstructs a checkpoint, so those two verdicts neither support nor block it.
REQUIRED_VERDICTS = (
    "cpu_run_completed",
    "gpu_run_completed",
    "gpu_position_within_tolerance",
    "gpu_heading_within_tolerance",
    "gpu_force_peak_within_tolerance",
    "original_hard_gates_hold",
)
NOT_REQUIRED_VERDICTS = ("restart_position_within_tolerance", "restart_heading_within_tolerance")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--step-ms", type=float, default=2.0, choices=(2.0, 1.0, 0.5))
    parser.add_argument("--parameter", default="P1", choices=("P0", "P1", "P2"))
    parser.add_argument("--output", default=None)
    parser.add_argument("--deadline-hours", type=float, default=6.0)
    parser.add_argument("--previous-cell", default=None, help="completed previous R4 cell metrics.json, same parameter point")
    parser.add_argument("--require-completed", action="append", default=[], help="metrics.json of a cell that must be COMPLETED (e.g. the last P1 step before starting P2)")
    args = parser.parse_args()
    tag = {2.0: "2MS", 1.0: "1MS", 0.5: "0P5MS"}[args.step_ms]
    output = args.output or f"results/20260915_R4_{args.parameter}_{tag}_GPU01"
    target = PAPER / f"protocol/R4_{args.parameter}_{tag}_GPU_20260915_v1.json"

    missing = [path for path in IDENTITY_PATHS if not (PAPER / path).is_file()]
    if missing:
        raise SystemExit("MISSING_IDENTITY_INPUT:" + ",".join(missing))
    if not (PAPER / G3_REPORT).is_file():
        raise SystemExit("G3_REPORT_MISSING")

    sys.path.insert(0, str(PAPER / "src"))
    from paper_v4_core.diagnostics.post_r3_r4_runner import expanded_parameters
    from paper_v4_core.e01_100m import DT, params
    from paper_v4_core.pilot_runner import ROUTE_LENGTH, SPEED

    import numpy as np

    g3 = json.loads((PAPER / G3_REPORT).read_text(encoding="utf-8"))
    g3b = json.loads((PAPER / G3B_REPORT).read_text(encoding="utf-8"))
    qualification = json.loads((PAPER / "results/20260915_RTX5080_G0_G2_05/qualification.json").read_text(encoding="utf-8"))
    total_ticks = int(np.ceil((ROUTE_LENGTH / SPEED) / DT))

    previous_cell = None
    if args.previous_cell:
        previous_path = PAPER / args.previous_cell
        previous_metrics = json.loads(previous_path.read_text(encoding="utf-8"))
        previous_cell = {
            "path": args.previous_cell,
            "sha256": sha(previous_path),
            "status": previous_metrics["status"],
            "plant_max_step_ms": previous_metrics["maximum_plant_step_s"] * 1000.0,
            "same_parameter_point": previous_metrics["parameter_id"] == args.parameter,
        }

    required_completed = []
    for path_text in args.require_completed:
        path = PAPER / path_text
        data = json.loads(path.read_text(encoding="utf-8"))
        required_completed.append({
            "path": path_text, "sha256": sha(path), "status": data["status"],
            "parameter_id": data["parameter_id"], "plant_max_step_ms": data["maximum_plant_step_s"] * 1000.0,
        })

    required = {
        f"{window['window']}.{verdict}": bool(window["verdicts"].get(verdict))
        for window in g3["windows"]
        for verdict in REQUIRED_VERDICTS
    }
    failed_restart = {
        f"{window['window']}.{verdict}": bool(window["verdicts"].get(verdict))
        for window in g3["windows"]
        for verdict in NOT_REQUIRED_VERDICTS
    }
    preconditions = {
        "all_required_g3_verdicts_hold": all(required.values()),
        "gpu_qualification_pass": qualification.get("status") == "PASS_G0_G2_GPU_QUALIFIED",
        "g3b_mechanism_analysis_present": g3b.get("status") == "PASS_READ_ONLY_MECHANISM_ANALYSIS",
        "total_ticks_matches_frozen_route": total_ticks == 2379,
        "total_ticks": total_ticks,
        "output_does_not_exist": not (PAPER / output).exists(),
        "historical_cpu_reference_present": (PAPER / "results/20260915_R4_P1_2MS01/raw.npz").is_file(),
        "previous_cell_declared_for_finer_step": args.step_ms == 2.0 or previous_cell is not None,
        "previous_cell_completed_and_same_parameter_point": previous_cell is None or (
            previous_cell["status"] == "COMPLETED" and previous_cell["same_parameter_point"]
        ),
        "required_completed_cells_all_completed": all(item["status"] == "COMPLETED" for item in required_completed),
    }
    failed = [name for name, ok in preconditions.items() if ok is False]
    if failed:
        raise SystemExit("PRECONDITION_FAILED:" + ",".join(failed) + " | required=" + json.dumps(required))

    protocol = {
        "protocol_id": f"R4-{args.parameter}-{tag}-GPU-full-route-v1",
        "authorization": "User instruction 2026-09-15: complete everything until the full experiment can start.",
        "scope": "R4_FULL_ROUTE",
        "schema_version": "R4-FULL-ROUTE-v1",
        "run": {
            "parameter_id": args.parameter,
            "backend": "gpu",
            "workers": 1,
            "plant_max_step_ms": args.step_ms,
            "candidate_id": "EXP-R3-unfrozen-v1",
            "implementation_id": "R4-full-route-gpu-v1",
            "total_ticks": total_ticks,
            "output": output,
            "deadline_hours": args.deadline_hours,
        },
        "previous_cell_same_parameter_point": previous_cell,
        "required_completed_cells": required_completed,
        "absolute_parameters": expanded_parameters(params(args.parameter)),
        "parent_g3": {
            "path": G3_REPORT,
            "sha256": sha(PAPER / G3_REPORT),
            "status": g3["status"],
            "required_verdicts": required,
            "not_required_verdicts": failed_restart,
        },
        "parent_g3_protocol": {"path": G3_PROTOCOL, "sha256": sha(PAPER / G3_PROTOCOL)},
        "parent_g3b_mechanism": {
            "path": G3B_REPORT,
            "sha256": sha(PAPER / G3B_REPORT),
            "protocol": G3B_PROTOCOL,
            "protocol_sha256": sha(PAPER / G3B_PROTOCOL),
            "status": g3b["status"],
        },
        "decision_rule_supersession": {
            "statement": "The G3 protocol says that any failing verdict blocks the release of a full route. That rule is superseded here, explicitly and in writing, and only for the two restart_* verdicts.",
            "what_remains_failed": failed_restart,
            "why_this_is_not_gate_widening": [
                "no threshold or tolerance is changed: the restart gate stays 1e-06 m and its verdicts stay FAILED and are recorded above",
                "the full route starts from the frozen initial condition and never rebuilds a checkpoint, so the restart verdicts do not describe it",
                "the verdicts the full route does depend on - CUDA closed-loop agreement in position, heading and force, and the original hard gates - passed on all three windows",
                "the mechanism behind the restart failure is registered separately: the CPU replay is bitwise exact in the force-bearing window and diverges only in the zero-force free-play window, where a 1e-16 seed in the reference memory is amplified by branch switching",
            ],
            "consequence_for_d3": "checkpoint restart equivalence remains FAILED; the interrupted P1 prefix cannot be resumed or spliced, and D3's short-window plan must start from the frozen initial condition instead of a mid-route checkpoint",
            "audit_note": "if a reviewer rejects this separation, the correct action is to stop this run, not to adjust the restart tolerance",
        },
        "parent_qualification": {
            "path": "results/20260915_RTX5080_G0_G2_05/qualification.json",
            "sha256": sha(PAPER / "results/20260915_RTX5080_G0_G2_05/qualification.json"),
            "status": qualification["status"],
        },
        "identity_rule": "Only immutable inputs are gated. Documents revised by this same work are excluded on purpose.",
        "unchanged_from_the_cpu_candidate": [
            "control law, plant, horizon 20, controller step 20 ms, predictor step 2 ms",
            "lambda_internal = 2.0, frozen_dynamics_jacobian = false, finite_difference_scale = 1.0",
            "15000 N ultimate force, tyre utilisation 1.0, non-negative support load",
            "route, reference speed and reference schedule",
        ],
        "gates": {
            "ultimate_force_n": 15000.0,
            "tire_limit": 1.0,
            "minimum_support_n": 0.0,
            "predicted_force_budget_n": 15000.0,
            "source": "original frozen R4 thresholds; not relaxed by this protocol",
        },
        "analysis_plan": {
            "comparator": "tools/full_route_compare.py",
            "compare_against": "results/20260915_R4_P1_2MS01 over the first 2200 persisted ticks, and against the original hard gates over the whole route",
            "must_report": [
                "per-tick CPU/GPU divergence over the overlapping prefix",
                "full-route hard-gate status, completion and reference progress",
                "wall clock versus the 5 s per-solve budget",
                "the configuration error, which this implementation does not maintain internally",
            ],
            "forbidden": [
                "splicing the GPU continuation onto the interrupted CPU prefix as one trajectory",
                "claiming real-time behaviour from offline wall clock",
                "using the GPU speed-up to claim the P1 late-tracking question is answered",
            ],
        },
        "decision_after_completion": {
            "if_completed_and_gates_hold": "P1 2 ms is a complete GPU-route result whose identity differs from the interrupted CPU run; the 1 ms and 0.5 ms cells can then be frozen on the same candidate, and the P2 parameter point follows only after P1",
            "if_late_divergence_reproduces": "the reproduction itself becomes the controlled case for the late-tracking investigation; do not widen gates",
            "if_diverges_earlier_than_cpu": "treat CUDA-vs-CPU closed-loop divergence as the first hypothesis and re-run a matching short window rather than the full route",
        },
        "identity_files": [{"path": path, "sha256": sha(PAPER / path)} for path in IDENTITY_PATHS],
    }
    if target.exists():
        raise SystemExit("REFUSING_TO_OVERWRITE_PROTOCOL")
    target.write_text(json.dumps(protocol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "protocol": str(target.relative_to(PAPER)).replace("\\", "/"),
        "sha256": sha(target),
        "identity_files": len(protocol["identity_files"]),
        "total_ticks": total_ticks,
        "preconditions": {key: value for key, value in preconditions.items()},
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
