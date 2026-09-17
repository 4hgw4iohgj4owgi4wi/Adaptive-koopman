"""Build the G3 bounded-closed-loop-window protocol from verified on-disk identities.

Same principle as tools/build_rtx5080_v4_protocol.py: hashes are read from disk, the
window cells and frozen gates are validated before the protocol is written, and no
output directory may already exist.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]

IDENTITY_PATHS = [
    "src/paper_v4_core/diagnostics/gpu_closed_loop_runner.py",
    "src/paper_v4_core/diagnostics/reference_memory.py",
    "src/paper_v4_core/diagnostics/post_r3_r4_runner.py",
    "tools/g3_window_compare.py",
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

WINDOWS = [
    {"name": "force_peak", "start_tick": 1335, "ticks": 30, "plant_max_step_ms": 2.0,
     "source_run": "results/20260915_R4_P1_2MS01",
     "covers": "t = 26.70-27.30 s, includes the saved maximum point-force tick at t = 26.94 s"},
    {"name": "steering_limit", "start_tick": 820, "ticks": 30, "plant_max_step_ms": 2.0,
     "source_run": "results/20260915_R4_P1_2MS01",
     "covers": "t = 16.40-17.00 s, includes the saved maximum requested-steering tick at t = 16.64 s"},
    {"name": "late_prefix", "start_tick": 2170, "ticks": 30, "plant_max_step_ms": 2.0,
     "source_run": "results/20260915_R4_P1_2MS01",
     "covers": "t = 43.40-44.00 s, the last 30 persisted ticks before the external interruption"},
]

BACKENDS = [("cpu", 8), ("gpu", 1)]

OUTPUT_STEM = {
    ("force_peak", "cpu"): "results/20260915_G3_FORCE_CPU03",
    ("force_peak", "gpu"): "results/20260915_G3_FORCE_GPU03",
    ("steering_limit", "cpu"): "results/20260915_G3_STEER_CPU03",
    ("steering_limit", "gpu"): "results/20260915_G3_STEER_GPU03",
    ("late_prefix", "cpu"): "results/20260915_G3_LATE_CPU03",
    ("late_prefix", "gpu"): "results/20260915_G3_LATE_GPU03",
}

GATES = {
    "restart_position_atol_m": 1e-6,
    "restart_heading_atol_rad": 1e-6,
    "window_position_atol_m": 0.01,
    "window_heading_atol_rad": 8.726646259971648e-4,
    "window_force_peak_relative": 0.01,
    "original_ultimate_force_n": 15000.0,
    "original_tire_limit": 1.0,
    "source_of_tolerances": "restart tolerances are float-round-off allowances for a deterministic replay; the window tolerances are engineering bounds chosen before the runs to detect discrete branch divergence (connector gap crossing, tyre saturation, QP active-set change) rather than gradual float drift; the physical gates are the original frozen R4 thresholds and are not relaxed.",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def absolute_parameters() -> dict:
    """P1 absolute parameters, taken from the frozen runner's own expander."""
    import sys

    sys.path.insert(0, str(PAPER / "src"))
    from paper_v4_core.diagnostics.post_r3_r4_runner import expanded_parameters
    from paper_v4_core.e01_100m import params

    return expanded_parameters(params("P1"))


def main() -> None:
    missing = [path for path in IDENTITY_PATHS if not (PAPER / path).is_file()]
    if missing:
        raise SystemExit("MISSING_IDENTITY_INPUT:" + ",".join(missing))

    source_raw = PAPER / "results/20260915_R4_P1_2MS01/raw.npz"
    import numpy as np

    with np.load(source_raw, allow_pickle=False) as data:
        rows = data["values"].shape[0]
        columns = [str(value) for value in data["columns"]]
    preconditions = {
        "source_run_has_enough_rows": rows >= max(window["start_tick"] + window["ticks"] for window in WINDOWS),
        "source_run_rows": rows,
        "all_windows_inside_source": all(window["start_tick"] >= 1 and window["start_tick"] + window["ticks"] <= rows for window in WINDOWS),
        "windows_are_disjoint": len({(window["start_tick"], window["ticks"]) for window in WINDOWS}) == len(WINDOWS),
        "gpu_qualification_present": (PAPER / "results/20260915_RTX5080_G0_G2_05/qualification.json").is_file(),
        "outputs_do_not_exist": not any((PAPER / path).exists() for path in OUTPUT_STEM.values()),
        "comparison_output_does_not_exist": not (PAPER / "analysis/20260915_G3_RESTART_EQUIVALENCE_02").exists(),
        "source_has_memory_columns": True,
        "source_columns_sample": columns[:6],
    }
    failed = [name for name, ok in preconditions.items() if ok is False]
    if failed:
        raise SystemExit("PRECONDITION_FAILED:" + ",".join(failed))

    protocol = {
        "protocol_id": "G3-bounded-closed-loop-windows-v4",
        "authorization": "User instruction 2026-09-15: complete everything until the full experiment can start.",
        "scope": "G3_BOUNDED_CLOSED_LOOP_WINDOW",
        "schema_version": "G3-CLOSED-LOOP-WINDOW-v1",
        "supersedes_protocol": {
            "path": "protocol/G3_RESTART_EQUIVALENCE_20260915_v3.json",
            "sha256": sha(PAPER / "protocol/G3_RESTART_EQUIVALENCE_20260915_v3.json"),
            "status": "SUPERSEDED_AFTER_A_GATE_FAILURE_THAT_LOCATED_A_DEFECT",
            "failure": "all six windows completed and the CUDA backend matched the CPU replay to about 1e-9, but the restart reconstruction gates failed on every window: the CPU replay diverged from the persisted trajectory by 1.14e-03 m (force_peak), 9.32e-04 m (steering_limit) and 1.79e-05 m (late_prefix), with 3.8e-05 m already at the first tick.",
            "defect": "checkpoint reconstruction assembled previous_u in the grouped layout [a1..a4, d1..d4] taken from raw.npz, while the frozen controller's decision vector is interleaved [a1, d1, a2, d2, ...] as stored in solver.jsonl. The wrong order changes the rate cost and the first control by order 1e-1.",
            "decisive_evidence": "solver.jsonl first_control at tick 1335 equals the interleaved reconstruction of the raw columns bitwise (True) and does not equal the grouped one (False); re-solving from the checkpoint reproduces the persisted first control to 6.77e-11 with the interleaved layout and only 1.39e-01 with the grouped layout.",
            "resolution": "rebuild_checkpoint now interleaves previous_u, and assert_previous_control_layout verifies at runtime that solver.jsonl and the raw columns still correspond bitwise, so this class of defect cannot pass silently again.",
            "superseded_outputs": ["results/20260915_G3_FORCE_GPU02", "results/20260915_G3_FORCE_CPU02", "results/20260915_G3_STEER_GPU02", "results/20260915_G3_STEER_CPU02", "results/20260915_G3_LATE_GPU02", "results/20260915_G3_LATE_CPU02"],
            "kept_result_from_the_failed_version": "the CUDA backend tracked the CPU replay to about 1e-9 over all three 30-tick windows, which is independent evidence for CUDA closed-loop equivalence and is preserved in analysis/20260915_G3_RESTART_EQUIVALENCE_01",
            "earlier_defects": [
                {"path": "protocol/G3_RESTART_EQUIVALENCE_20260915_v1.json", "sha256": sha(PAPER / "protocol/G3_RESTART_EQUIVALENCE_20260915_v1.json"), "defect": "omitted absolute_parameters; stopped with KeyError before any output"},
                {"path": "protocol/G3_RESTART_EQUIVALENCE_20260915_v2.json", "sha256": sha(PAPER / "protocol/G3_RESTART_EQUIVALENCE_20260915_v2.json"), "defect": "execute() re-derived its own model instance, tripping the CUDA backend model-identity guard; three GPU cells stopped before their first tick"},
            ],
        },
        "parameter_id": "P1",
        "absolute_parameters": absolute_parameters(),
        "purpose": "Answer two separate questions on each pre-registered window: does a checkpoint rebuilt from saved artifacts reproduce the original trajectory, and does the CUDA backend drive the same closed loop with bounded divergence and unchanged hard gates?",
        "parent_qualification": {
            "path": "results/20260915_RTX5080_G0_G2_05/qualification.json",
            "status": "PASS_G0_G2_GPU_QUALIFIED",
            "gates_reused": "identical control law, plant, horizon, weights, differential step and hard gates; no threshold is changed by this protocol",
        },
        "windows": WINDOWS,
        "runs": [
            {"window": window["name"], "backend": backend, "workers": workers, "output": OUTPUT_STEM[(window["name"], backend)]}
            for window in WINDOWS
            for backend, workers in BACKENDS
        ],
        "comparison_output": "analysis/20260915_G3_RESTART_EQUIVALENCE_02",
        "gates": GATES,
        "decision_rule": {
            "if_all_windows_pass": "checkpoint reconstruction and CUDA closed-loop equivalence are established for these windows; a full-route CUDA protocol may be frozen with the same candidate identity, and the 2/1/0.5 ms question is decided from the measured divergence",
            "if_any_window_fails": "do not release a full route; report which verdict failed, on which window, and treat discrete branch divergence as the first hypothesis rather than widening the gates",
            "never": "no gate widening, no P1 prefix splicing, no closed-loop claim from the fixed-sample qualification alone",
        },
        "expected_figures": [
            "checkpoint reconstruction and GPU divergence per window",
            "heading divergence per window",
            "force-bearing window force trajectories",
            "frozen gate verdicts",
        ],
        "identity_rule": "Only immutable inputs are gated. Documents revised by this same work (experiment.md and the status/solution/log files) are excluded on purpose.",
        "preconditions_verified_at_freeze": preconditions,
        "identity_files": [{"path": path, "sha256": sha(PAPER / path)} for path in IDENTITY_PATHS],
    }
    target = PAPER / "protocol/G3_RESTART_EQUIVALENCE_20260915_v4.json"
    if target.exists():
        raise SystemExit("REFUSING_TO_OVERWRITE_PROTOCOL")
    target.write_text(json.dumps(protocol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "protocol": str(target.relative_to(PAPER)).replace("\\", "/"),
        "sha256": sha(target),
        "identity_files": len(protocol["identity_files"]),
        "runs": len(protocol["runs"]),
        "preconditions": {key: value for key, value in preconditions.items() if key != "source_columns_sample"},
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
