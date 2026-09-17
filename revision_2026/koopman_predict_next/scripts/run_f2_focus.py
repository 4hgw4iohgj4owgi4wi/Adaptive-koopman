from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "plant"))
sys.path.insert(0, str(ROOT / "scripts"))

from contracts import write_json
from generate_data import resolved_params, simulate_trajectory
from load_transfer import (
    SupportLiftOutsideEnvelope,
    config_from_model,
    solve_payload_support_loads,
)
from scenarios import ScenarioSpec


MIRROR = np.asarray([1, 0, 3, 2])


def relative_error(candidate: np.ndarray, reference: np.ndarray) -> float:
    candidate = np.asarray(candidate, dtype=float)
    reference = np.asarray(reference, dtype=float)
    if candidate.shape != reference.shape:
        return float("inf")
    return float(np.max(np.abs(candidate - reference) / np.maximum(np.abs(reference), 1.0)))


def run(project: Path, protocol: dict, run_dir: Path) -> dict:
    started = time.perf_counter()
    output = run_dir / "f2"
    output.mkdir(parents=True, exist_ok=False)
    params = resolved_params(910020, protocol)
    config = config_from_model(params)
    static = solve_payload_support_loads(np.zeros(2), config, enabled=True)
    expected_static = params.payload.mass_kg * params.payload.gravity_mps2 / 4.0
    static_relative_error = float(
        np.max(
            np.abs(static["payload_support_load_n"] - expected_static)
            / max(expected_static, 1.0)
        )
    )
    probes = []
    constraint_relative_max = 0.0
    for acceleration in (
        np.asarray([1.0, 0.0]),
        np.asarray([-1.0, 0.0]),
        np.asarray([0.0, 1.0]),
        np.asarray([0.0, -1.0]),
        np.asarray([0.7, -0.6]),
    ):
        result = solve_payload_support_loads(acceleration, config, enabled=True)
        constraint_relative_max = max(
            constraint_relative_max,
            float(np.max(result["constraint_relative_residual"])),
        )
        probes.append(
            {
                "acceleration_body_mps2": acceleration.tolist(),
                "support_load_n": result["payload_support_load_n"].tolist(),
                "constraint_residual": result["constraint_residual"].tolist(),
            }
        )
    lateral_left = np.asarray(probes[2]["support_load_n"], dtype=float)
    lateral_right = np.asarray(probes[3]["support_load_n"], dtype=float)
    longitudinal_accel = np.asarray(probes[0]["support_load_n"], dtype=float)
    longitudinal_brake = np.asarray(probes[1]["support_load_n"], dtype=float)
    direction_passed = bool(
        lateral_left[[1, 3]].sum() > lateral_left[[0, 2]].sum()
        and lateral_right[[0, 2]].sum() > lateral_right[[1, 3]].sum()
        and longitudinal_accel[[2, 3]].sum() > longitudinal_accel[[0, 1]].sum()
        and longitudinal_brake[[0, 1]].sum() > longitudinal_brake[[2, 3]].sum()
    )
    mirror_error_n = float(np.max(np.abs(lateral_left[MIRROR] - lateral_right)))
    lift_detected = False
    try:
        solve_payload_support_loads(np.asarray([100.0, 100.0]), config, enabled=True)
    except SupportLiftOutsideEnvelope:
        lift_detected = True
    write_json(output / "analytic_support_probes.json", {"probes": probes})

    parent = protocol["parent_p2"]
    manifest_path = project / Path(parent["run_root"]) / "p2" / "data_manifest.csv"
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as stream:
        manifest = list(csv.DictReader(stream))
    wanted = str(protocol["f2"]["replay_parent_trajectory_id"])
    row = next(item for item in manifest if item["trajectory_id"] == wanted)
    raw_path = project / Path(parent["data_root"]) / Path(row["raw_path"]).name
    with np.load(raw_path, allow_pickle=False) as source:
        reference = {key: source[key].copy() for key in source.files}
    replay_params = resolved_params(int(row["seed"]), protocol)
    spec = ScenarioSpec("D2", row["direction"], None, 100.0, True)
    replay_summary, candidate = simulate_trajectory(
        spec,
        row["law"],
        int(row["seed"]),
        replay_params,
        protocol,
        actuator_mode="dynamic",
        load_transfer_enabled=False,
    )
    comparisons = {
        "state30_relative": relative_error(candidate["state30"], reference["state30"]),
        "tire_raw_utilization_relative": relative_error(
            candidate["tire_raw_utilization"], reference["tire_raw_utilization"]
        ),
        "force_payload_body_relative": relative_error(
            candidate["force_payload_body_n"], reference["force_payload_body_n"]
        ),
        "time_relative": relative_error(candidate["time_s"], reference["time_s"]),
        "distance_relative": relative_error(candidate["distance_m"], reference["distance_m"]),
    }
    replay_relative_max = max(comparisons.values())
    np.savez_compressed(output / "minimal_replay_focus.npz", **candidate)
    write_json(
        output / "minimal_replay_comparison.json",
        {
            "parent_trajectory_id": int(row["trajectory_id"]),
            "parent_raw_path": str(raw_path),
            "candidate_status": replay_summary["status"],
            "candidate_sample_count": replay_summary["sample_count"],
            "reference_sample_count": int(len(reference["time_s"])),
            "comparisons": comparisons,
        },
    )
    f2 = protocol["f2"]
    finite = bool(
        replay_summary["finite"]
        and all(np.all(np.isfinite(value)) for value in candidate.values() if np.asarray(value).dtype.kind not in {"O", "U", "S"})
    )
    passed = bool(
        static_relative_error <= float(f2["static_relative_atol"])
        and constraint_relative_max <= float(f2["constraint_relative_atol"])
        and direction_passed
        and mirror_error_n <= 1.0e-9
        and lift_detected
        and replay_summary["status"] == "PASS"
        and replay_relative_max <= float(f2["replay_relative_atol"])
        and finite
    )
    complete = {
        "stage": "F2",
        "passed": passed,
        "static_relative_error": static_relative_error,
        "constraint_relative_residual_max": constraint_relative_max,
        "direction_contract_passed": direction_passed,
        "mirror_error_n": mirror_error_n,
        "negative_support_lift_detected": lift_detected,
        "load_off_parent_replay_relative_max": replay_relative_max,
        "load_off_parent_replay_components": comparisons,
        "load_off_parent_replay_finite": finite,
        "runtime_s": time.perf_counter() - started,
        "artifacts": {
            "analytic_support_probes": str(output / "analytic_support_probes.json"),
            "minimal_replay": str(output / "minimal_replay_focus.npz"),
            "minimal_replay_comparison": str(output / "minimal_replay_comparison.json"),
        },
    }
    if not passed:
        complete.update(
            {
                "repair_code": "F2_SUPPORT_OR_REPLAY_CONTRACT_FAILED",
                "next_action": "Inspect support signs/conservation and the first parent replay difference; do not run F3.",
            }
        )
    write_json(output / "complete.json", complete)
    return complete
