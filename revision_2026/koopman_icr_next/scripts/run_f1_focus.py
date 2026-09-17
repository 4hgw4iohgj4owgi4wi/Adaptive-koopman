from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "plant"))
sys.path.insert(0, str(ROOT / "scripts"))

from causal_schema import build_schema_focus
from contracts import write_json
from data_adapter import (
    INPUT_KEYS_FOCUS,
    LABEL_KEYS_FOCUS,
    build_sample_focus,
    causal_input_digest_focus,
)
from generate_data import resolved_params
from icr_metrics import icr_geometry_residual, icr_steering_residual, summarize_residual


MIRROR = np.asarray([1, 0, 3, 2])


def write_csv(path: Path, rows: list[dict]) -> None:
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def recovery_times(values: np.ndarray, phases: np.ndarray, dt_s: float, threshold: float) -> list[float | None]:
    values = np.asarray(values, dtype=float)
    phases = np.asarray(phases).astype(str)
    switch_indices = [
        index
        for index in range(1, len(phases))
        if phases[index] != phases[index - 1]
        and phases[index] in {"STEP_PRIMARY", "STEP_REVERSE", "DECEL"}
    ]
    output: list[float | None] = []
    for start in switch_indices:
        found = next(
            (index for index in range(start, len(values)) if abs(values[index]) <= threshold),
            None,
        )
        output.append(None if found is None else float((found - start) * dt_s))
    return output


def _trajectory_metrics(arrays: dict[str, np.ndarray], params: object) -> dict:
    from four_vehicle_common import split_state
    from steering_allocator import kinematic_targets

    count = len(arrays["time_s"])
    geom = np.empty(count)
    request = np.empty(count)
    actual = np.empty(count)
    actual_interval = np.empty(count)
    geom_signed = np.empty((count, 4))
    request_signed = np.empty((count, 4))
    actual_signed = np.empty((count, 4))
    wheelbase = float(params.vehicle.lf_m + params.vehicle.lr_m)
    for index in range(count):
        start_state = (
            np.asarray(arrays["initial_state30"], dtype=float)
            if index == 0
            else np.asarray(arrays["state30"][index - 1], dtype=float)
        )
        _, payload = split_state(start_state)
        target = kinematic_targets(
            max(float(payload[3]), 0.0),
            np.deg2rad(float(arrays["virtual_front_deg"][index])),
            np.deg2rad(float(arrays["virtual_rear_deg"][index])),
            params,
        )
        g = icr_geometry_residual(
            target["point_velocity_payload_body_mps"], target["relative_heading_rad"]
        )
        q = icr_steering_residual(
            target["speed_mps"],
            float(target["yaw_rate_radps"]),
            wheelbase,
            arrays["requested_control4x2"][index, :, 1],
        )
        a = icr_steering_residual(
            target["speed_mps"],
            float(target["yaw_rate_radps"]),
            wheelbase,
            arrays["actual_steering_rad"][index],
        )
        sub = icr_steering_residual(
            target["speed_mps"],
            float(target["yaw_rate_radps"]),
            wheelbase,
            arrays["actual_steering_substeps_rad"][index],
        )
        geom[index] = float(g["max_abs_mps"])
        request[index] = float(q["max_abs_mps"])
        actual[index] = float(a["max_abs_mps"])
        actual_interval[index] = float(np.max(sub["max_abs_mps"]))
        geom_signed[index] = g["signed_per_vehicle_mps"]
        request_signed[index] = q["signed_per_vehicle_mps"]
        actual_signed[index] = a["signed_per_vehicle_mps"]
    return {
        "geom": geom,
        "request": request,
        "actual": actual,
        "actual_interval": actual_interval,
        "geom_signed": geom_signed,
        "request_signed": request_signed,
        "actual_signed": actual_signed,
    }


def run(project: Path, protocol: dict, run_dir: Path) -> dict:
    started = time.perf_counter()
    output = run_dir / "f1"
    output.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment["KOOPMAN_PROJECT_ROOT"] = str(project)
    pytest_result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", str(ROOT / "tests"), "-q"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    (output / "pytest_stdout.txt").write_text(pytest_result.stdout, encoding="utf-8")
    (output / "pytest_stderr.txt").write_text(pytest_result.stderr, encoding="utf-8")

    parent = protocol["parent_p2"]
    manifest_path = project / Path(parent["run_root"]) / "p2" / "data_manifest.csv"
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as stream:
        manifest = list(csv.DictReader(stream))
    raw_root = project / Path(parent["data_root"])
    tolerance = protocol["f1"]
    threshold = float(tolerance["diagnostic_threshold_mps"])
    dt_s = float(protocol["k2"]["model_step_s"])
    rows = []
    series = {}
    recorded_actual_error = 0.0
    recorded_geometry_error = 0.0
    a0_request_actual_error = 0.0
    causal_passed = False
    schema = build_schema_focus()
    first_augmented = None
    first_params = None
    first_law = None
    for row in manifest:
        path = raw_root / Path(row["raw_path"]).name
        with np.load(path, allow_pickle=False) as source:
            arrays = {key: source[key].copy() for key in source.files}
        params = resolved_params(int(row["seed"]), protocol)
        metrics = _trajectory_metrics(arrays, params)
        recorded_actual_error = max(
            recorded_actual_error,
            float(
                np.max(
                    np.abs(
                        metrics["actual_interval"]
                        - np.asarray(arrays["actual_steering_icr_residual_mps"], dtype=float)
                    )
                )
            ),
        )
        recorded_geometry_error = max(
            recorded_geometry_error,
            float(
                np.max(
                    np.abs(
                        metrics["geom"]
                        - np.asarray(arrays["requested_icr_residual_mps"], dtype=float)
                    )
                )
            ),
        )
        if row["actuator_mode"] == "instant":
            a0_request_actual_error = max(
                a0_request_actual_error,
                float(np.max(np.abs(metrics["request"] - metrics["actual"]))),
            )
        request_stats = summarize_residual(metrics["request"], threshold)
        actual_stats = summarize_residual(metrics["actual"], threshold)
        request_recovery = recovery_times(
            metrics["request"], arrays["command_phase"], dt_s, threshold
        )
        actual_recovery = recovery_times(
            metrics["actual"], arrays["command_phase"], dt_s, threshold
        )
        identity = {
            "trajectory_id": int(row["trajectory_id"]),
            "base_family_id": row["base_family_id"],
            "seed": int(row["seed"]),
            "direction": row["direction"],
            "plant": row["plant"],
            "law": row["law"],
            "actuator_mode": row["actuator_mode"],
        }
        rows.append(
            {
                **identity,
                "geom_peak_mps": float(np.max(metrics["geom"])),
                "request_peak_mps": request_stats["peak_mps"],
                "request_p95_mps": request_stats["p95_mps"],
                "request_rms_mps": request_stats["rms_mps"],
                "request_fraction_gt_0p5": request_stats["fraction_above_threshold"],
                "actual_peak_mps": actual_stats["peak_mps"],
                "actual_p95_mps": actual_stats["p95_mps"],
                "actual_rms_mps": actual_stats["rms_mps"],
                "actual_fraction_gt_0p5": actual_stats["fraction_above_threshold"],
                "request_recovery_s": json.dumps(request_recovery),
                "actual_recovery_s": json.dumps(actual_recovery),
            }
        )
        key = (row["base_family_id"], row["plant"], row["actuator_mode"], row["direction"])
        series[key] = metrics
        if first_augmented is None:
            static = params.payload.mass_kg * params.payload.gravity_mps2 / 4.0
            count = len(arrays["time_s"])
            arrays.update(
                {
                    "payload_support_load4_n": np.full((count, 4), static),
                    "vehicle_total_normal_load4_n": np.full(
                        (count, 4), params.vehicle.mass_kg * params.vehicle.gravity_mps2 + static
                    ),
                    "payload_accel_body2_mps2": np.zeros((count, 2)),
                    "icr_geometry_residual_mps": metrics["geom"],
                    "icr_request_residual_mps": metrics["request"],
                    "icr_actual_residual_mps": metrics["actual"],
                    "load_transfer_enabled": np.asarray(False),
                }
            )
            first_augmented = arrays
            first_params = params
            first_law = row["law"]

    mirror_rows = []
    mirror_max = 0.0
    mirror_missing = 0
    bases = sorted({(key[0], key[1], key[2]) for key in series})
    for base, plant, mode in bases:
        left = series.get((base, plant, mode, "left"))
        right = series.get((base, plant, mode, "right"))
        if left is None or right is None or len(left["geom"]) != len(right["geom"]):
            mirror_missing += 1
            continue
        errors = {
            "geom_scalar": float(np.max(np.abs(left["geom"] - right["geom"]))),
            "request_scalar": float(np.max(np.abs(left["request"] - right["request"]))),
            "actual_scalar": float(np.max(np.abs(left["actual"] - right["actual"]))),
            "request_signed": float(
                np.max(np.abs(left["request_signed"][:, MIRROR] + right["request_signed"]))
            ),
            "actual_signed": float(
                np.max(np.abs(left["actual_signed"][:, MIRROR] + right["actual_signed"]))
            ),
        }
        mirror_max = max(mirror_max, *errors.values())
        mirror_rows.append(
            {"base_family_id": base, "plant": plant, "actuator_mode": mode, **errors}
        )

    if first_augmented is not None:
        index = min(5, len(first_augmented["time_s"]) - 2)
        sample = build_sample_focus(
            first_augmented,
            index,
            first_params,
            law=first_law,
            expected_step_s=dt_s,
            plant_step_s=float(protocol["k2"]["plant_step_s"]),
        )
        changed = {key: np.asarray(value).copy() for key, value in first_augmented.items()}
        changed["actual_steering_rad"][index + 1] += 0.7
        changed["payload_support_load4_n"][index + 1] += 9000.0
        changed["vehicle_total_normal_load4_n"][index + 1] += 9000.0
        changed["payload_accel_body2_mps2"][index + 1] += 20.0
        changed_sample = build_sample_focus(
            changed,
            index,
            first_params,
            law=first_law,
            expected_step_s=dt_s,
            plant_step_s=float(protocol["k2"]["plant_step_s"]),
        )
        causal_passed = causal_input_digest_focus(sample) == causal_input_digest_focus(changed_sample)

    write_csv(output / "icr_trajectory_metrics.csv", rows)
    write_csv(output / "icr_mirror_metrics.csv", mirror_rows)
    schema_passed = bool(
        {item["name"] for item in schema["inputs"]} == set(INPUT_KEYS_FOCUS)
        and {item["name"] for item in schema["labels"]} == set(LABEL_KEYS_FOCUS)
    )
    geom_peak = max(float(row["geom_peak_mps"]) for row in rows)
    passed = bool(
        pytest_result.returncode == 0
        and len(rows) == 24
        and geom_peak <= float(tolerance["geometry_residual_atol_mps"])
        and recorded_actual_error <= float(tolerance["recompute_atol_mps"])
        and a0_request_actual_error <= float(tolerance["recompute_atol_mps"])
        and mirror_missing == 0
        and mirror_max <= float(tolerance["mirror_atol_mps"])
        and causal_passed
        and schema_passed
    )
    complete = {
        "stage": "F1",
        "passed": passed,
        "pytest_returncode": pytest_result.returncode,
        "trajectory_count": len(rows),
        "geometry_residual_peak_mps": geom_peak,
        "legacy_geometry_field_recompute_max_abs_mps": recorded_geometry_error,
        "actual_interval_recompute_max_abs_mps": recorded_actual_error,
        "a0_request_actual_max_abs_mps": a0_request_actual_error,
        "mirror_pair_count": len(mirror_rows),
        "mirror_missing_count": mirror_missing,
        "mirror_max_abs_mps": mirror_max,
        "future_actual_fz_causal_digest_unchanged": causal_passed,
        "schema_focus_passed": schema_passed,
        "request_peak_range_mps": [
            min(float(row["request_peak_mps"]) for row in rows),
            max(float(row["request_peak_mps"]) for row in rows),
        ],
        "actual_peak_range_mps": [
            min(float(row["actual_peak_mps"]) for row in rows),
            max(float(row["actual_peak_mps"]) for row in rows),
        ],
        "runtime_s": time.perf_counter() - started,
        "artifacts": {
            "trajectory_metrics": str(output / "icr_trajectory_metrics.csv"),
            "mirror_metrics": str(output / "icr_mirror_metrics.csv"),
            "pytest_stdout": str(output / "pytest_stdout.txt"),
        },
    }
    if not passed:
        complete.update(
            {
                "repair_code": "F1_ICR_OR_CAUSAL_CONTRACT_FAILED",
                "next_action": "Inspect ICR recomputation, mirror rows and causal tests; do not run F2.",
            }
        )
    write_json(output / "complete.json", complete)
    return complete
