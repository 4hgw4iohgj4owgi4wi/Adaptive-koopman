from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
MODES = ("A0", "A1", "A2", "A3")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refuse to write empty CSV: {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as source:
        return {key: source[key].copy() for key in source.files}


def _as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _stats(values: np.ndarray, threshold: float) -> dict:
    series = np.asarray(values, dtype=float).reshape(-1)
    if series.size == 0 or not np.all(np.isfinite(series)):
        raise ValueError("independent residual series must be finite and non-empty")
    absolute = np.abs(series)
    return {
        "peak_mps": float(np.max(absolute)),
        "p95_mps": float(np.percentile(absolute, 95.0)),
        "rms_mps": float(np.sqrt(np.mean(series**2))),
        "fraction_gt_0p5": float(np.mean(absolute > threshold)),
    }


def independent_icr(
    target_speed_mps: np.ndarray,
    target_yaw_rate_radps: np.ndarray | float,
    wheelbase_m: float,
    wheel_angle_rad: np.ndarray,
    threshold_mps: float = 0.5,
) -> dict:
    """Independent v*tan(delta)-L*r implementation; imports no project metric code."""

    speed = np.asarray(target_speed_mps, dtype=float)
    angle = np.asarray(wheel_angle_rad, dtype=float)
    yaw = np.asarray(target_yaw_rate_radps, dtype=float)
    if speed.shape[-1:] != (4,) or angle.shape[-1:] != (4,):
        raise ValueError("independent ICR requires four vehicle values")
    if speed.shape != angle.shape:
        speed = np.broadcast_to(speed, angle.shape)
    if yaw.ndim == 0:
        yaw = np.full(angle.shape[:-1], float(yaw))
    if yaw.shape != angle.shape[:-1]:
        raise ValueError("yaw-rate endpoint does not match steering endpoint")
    if not np.isfinite(wheelbase_m) or wheelbase_m <= 0.0:
        raise ValueError("wheelbase must be finite and positive")
    signed = speed * np.tan(angle) - wheelbase_m * yaw[..., None]
    series = np.max(np.abs(signed), axis=-1)
    return {"signed4_mps": signed, "series_mps": series, **_stats(series, threshold_mps)}


def _rotation(yaw: float) -> np.ndarray:
    c, s = np.cos(yaw), np.sin(yaw)
    return np.asarray([[c, -s], [s, c]], dtype=float)


def _wrap(angle: np.ndarray) -> np.ndarray:
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


def _payload_anchors(values: dict) -> np.ndarray:
    length = float(values["payload"]["length_m"])
    width = float(values["payload"]["width_m"])
    return np.asarray(
        [
            [0.5 * length, 0.5 * width],
            [0.5 * length, -0.5 * width],
            [-0.5 * length, 0.5 * width],
            [-0.5 * length, -0.5 * width],
        ]
    )


def _request_layers(
    state30: np.ndarray, virtual_front_deg: float, virtual_rear_deg: float, params: dict
) -> dict:
    """Independent copy of the registered G0/G1/G2 mathematics, not its code path."""

    values = params["values"]
    vehicles = np.asarray(state30, dtype=float)[:24].reshape(4, 6)
    payload = np.asarray(state30, dtype=float)[24:]
    payload_anchors = _payload_anchors(values)
    vehicle_anchors = np.asarray(values["vehicle_anchor_body_m"], dtype=float)
    array_wheelbase = float(values["payload"]["length_m"])
    front = np.deg2rad(float(virtual_front_deg))
    rear = np.deg2rad(float(virtual_rear_deg))
    denominator = np.tan(front) - np.tan(rear)
    payload_speed = max(float(payload[3]), 0.0)
    if abs(denominator) < 1.0e-10:
        headings = np.zeros(4)
        speed = np.full(4, payload_speed)
        yaw_rate = 0.0
        g0 = np.zeros(4)
    else:
        y_icr = array_wheelbase / denominator
        x_icr = 0.5 * array_wheelbase - y_icr * np.tan(front)
        yaw_rate = payload_speed / y_icr
        headings = np.zeros(4)
        for _ in range(8):
            centers = np.vstack(
                [
                    payload_anchors[index]
                    - _rotation(float(headings[index])) @ vehicle_anchors[index]
                    for index in range(4)
                ]
            )
            velocity = yaw_rate * np.column_stack(
                [y_icr - centers[:, 1], centers[:, 0] - x_icr]
            )
            next_headings = np.arctan2(velocity[:, 1], velocity[:, 0])
            if np.max(np.abs(_wrap(next_headings - headings))) < 1.0e-12:
                headings = next_headings
                break
            headings = next_headings
        centers = np.vstack(
            [
                payload_anchors[index]
                - _rotation(float(headings[index])) @ vehicle_anchors[index]
                for index in range(4)
            ]
        )
        velocity = yaw_rate * np.column_stack(
            [y_icr - centers[:, 1], centers[:, 0] - x_icr]
        )
        speed = np.linalg.norm(velocity, axis=1)
        wheelbase = float(values["vehicle"]["lf_m"] + values["vehicle"]["lr_m"])
        g0 = np.arctan2(wheelbase * yaw_rate, np.maximum(speed, 1.0e-9))
        signed_speed = np.sum(
            velocity * np.column_stack([np.cos(headings), np.sin(headings)]), axis=1
        )
        g0 = np.where(signed_speed >= 0.0, g0, -g0)
    heading_error = _wrap(payload[2] + headings - vehicles[:, 2])
    g1 = g0 + 2.0 * heading_error
    g2 = np.clip(g1, -np.deg2rad(15.0), np.deg2rad(15.0))
    return {"speed_mps": speed, "yaw_rate_radps": yaw_rate, "G0": g0, "G1": g1, "G2": g2}


def validate_units(params: dict) -> dict:
    expected = {
        "vehicle.lf_m": "m",
        "vehicle.lr_m": "m",
        "payload.length_m": "m",
        "payload.width_m": "m",
        "payload.mass_kg": "kg",
        "payload.gravity_mps2": "m/s^2",
        "connector.ultimate_force_n": "N",
    }
    units = dict(params.get("units", {}))
    issues = [
        f"{name}: expected {unit}, found {units.get(name)!r}"
        for name, unit in expected.items()
        if units.get(name) != unit
    ]
    return {"passed": not issues, "issues": issues}


def validate_shapes(arrays: Mapping[str, np.ndarray], protocol: dict) -> dict:
    count = len(np.asarray(arrays.get("time_s", [])))
    substeps = int(protocol["actuator"]["substeps_per_request"])
    expected = {
        "time_s": (count,),
        "distance_m": (count,),
        "state30": (count, 30),
        "requested_control4x2": (count, 4, 2),
        "actual_steering_rad": (count, 4),
        "actual_steering_substeps_rad": (count, substeps, 4),
        "actual_steering_rate_substeps_radps": (count, substeps, 4),
        "icr_target_speed4_mps": (count, 4),
        "icr_target_yaw_rate_radps": (count,),
        "tire_raw_utilization": (count, 4),
        "payload_support_load4_n": (count, 4),
        "support_constraint_relative_residual3": (count, 3),
        "force_payload_body_n": (count, 4, 2),
        "internal_force_vector_n": (count, 8),
        "command_phase": (count,),
    }
    issues = []
    for name, shape in expected.items():
        if name not in arrays:
            issues.append(f"missing:{name}")
        elif tuple(np.asarray(arrays[name]).shape) != shape:
            issues.append(f"shape:{name}:{np.asarray(arrays[name]).shape}!={shape}")
    return {"passed": count > 1 and not issues, "sample_count": count, "issues": issues}


def _grasp_matrix(anchors: np.ndarray) -> np.ndarray:
    matrix = np.zeros((3, 8))
    matrix[0, 0::2] = 1.0
    matrix[1, 1::2] = 1.0
    matrix[2, 0::2] = -anchors[:, 1]
    matrix[2, 1::2] = anchors[:, 0]
    return matrix


def _stretch_series(force: np.ndarray) -> np.ndarray:
    front = force[:, 0] + force[:, 1]
    rear = force[:, 2] + force[:, 3]
    left = force[:, 0] + force[:, 2]
    right = force[:, 1] + force[:, 3]
    return np.column_stack(
        [
            0.5 * np.maximum(0.0, front[:, 0] - rear[:, 0]),
            0.5 * np.maximum(0.0, left[:, 1] - right[:, 1]),
        ]
    )


def _switching_stretch(identity: dict, arrays: Mapping[str, np.ndarray], protocol: dict) -> list[dict]:
    phase = np.asarray(arrays["command_phase"]).astype(str)
    force = np.asarray(arrays["force_payload_body_n"], dtype=float)
    tension = _stretch_series(force)
    dt_s = float(protocol["k2"]["model_step_s"])
    steps = int(round(float(protocol["f3"]["switching_window_s"]) / dt_s))
    starts = [
        index
        for index in range(1, len(phase))
        if phase[index] != phase[index - 1]
        and phase[index] in {"STEP_PRIMARY", "STEP_REVERSE", "DECEL"}
    ]
    rows = []
    for number, start in enumerate(starts, start=1):
        stop = min(start + steps, len(phase))
        segment = tension[start:stop]
        rows.append(
            {
                **identity,
                "switch_number": number,
                "phase": phase[start],
                "start_sample_index": start,
                "start_time_s": float(arrays["time_s"][start]),
                "window_end_sample_exclusive": stop,
                "window_duration_s": float((stop - start) * dt_s),
                "front_rear_abs_impulse_ns": float(np.sum(np.abs(segment[:, 0])) * dt_s),
                "left_right_abs_impulse_ns": float(np.sum(np.abs(segment[:, 1])) * dt_s),
                "front_rear_peak_n": float(np.max(segment[:, 0])),
                "left_right_peak_n": float(np.max(segment[:, 1])),
            }
        )
    return rows


def independent_compare_common_fields(
    candidate: Mapping[str, np.ndarray], reference: Mapping[str, np.ndarray]
) -> dict:
    excluded_prefixes = (
        "request_g0_", "request_g1_", "request_g2_", "request_heading_",
        "request_feedback_", "request_clip_", "icr_g0_", "icr_g1_", "icr_g2_",
    )
    common = sorted(
        key
        for key in set(candidate) & set(reference)
        if key != "actuator_mode" and not key.startswith(excluded_prefixes)
    )
    maximum = 0.0
    first = None
    compared = 0
    for key in common:
        left, right = np.asarray(candidate[key]), np.asarray(reference[key])
        if left.shape != right.shape:
            return {"common_field_count": compared, "max_abs": 1.0e300, "first_different": {"field": key, "reason": "shape"}}
        if left.dtype.kind in {"O", "U", "S"} or right.dtype.kind in {"O", "U", "S"}:
            error = 0.0 if np.array_equal(left.astype(str), right.astype(str)) else 1.0e300
            index = None
        else:
            difference = np.abs(left.astype(float) - right.astype(float))
            error = float(np.max(difference)) if difference.size else 0.0
            index = list(np.unravel_index(int(np.argmax(difference)), difference.shape)) if difference.size and error else None
        compared += 1
        maximum = max(maximum, error)
        if error and first is None:
            first = {"field": key, "max_abs": error, "index": index}
    return {"common_field_count": compared, "max_abs": maximum, "first_different": first}


def independent_physics(
    identity: dict,
    arrays: Mapping[str, np.ndarray],
    summary: dict,
    protocol: dict,
    parent: Mapping[str, np.ndarray] | None,
) -> tuple[dict, list[dict]]:
    params = json.loads(str(summary["params_json"]))
    values = params["values"]
    shapes = validate_shapes(arrays, protocol)
    units = validate_units(params)
    time_s = np.asarray(arrays["time_s"], dtype=float)
    dt_s = float(protocol["k2"]["model_step_s"])
    time_grid_error = float(np.max(np.abs(np.diff(time_s) - dt_s)))
    finite = all(
        np.all(np.isfinite(value))
        for value in arrays.values()
        if np.asarray(value).dtype.kind not in {"O", "U", "S"}
    )
    wheelbase = float(values["vehicle"]["lf_m"] + values["vehicle"]["lr_m"])
    actual = independent_icr(
        arrays["icr_target_speed4_mps"], arrays["icr_target_yaw_rate_radps"],
        wheelbase, arrays["actual_steering_rad"],
        float(protocol["f3"]["diagnostic_icr_threshold_mps"]),
    )
    rate_peak = float(np.max(np.abs(arrays["actual_steering_rate_substeps_radps"])))
    angle_peak = float(np.max(np.abs(arrays["actual_steering_substeps_rad"])))
    tire_peak = float(np.max(np.asarray(arrays["tire_raw_utilization"], dtype=float)))
    support = np.asarray(arrays["payload_support_load4_n"], dtype=float)
    support_min = float(np.min(support))
    expected_support = float(values["payload"]["mass_kg"] * values["payload"]["gravity_mps2"])
    support_sum_residual = float(np.max(np.abs(np.sum(support, axis=1) - expected_support)))
    force = np.asarray(arrays["force_payload_body_n"], dtype=float)
    connector_peak = float(np.max(np.linalg.norm(force, axis=2)))
    # Raw stores only payload-side force. The connector contract defines the vehicle
    # side as its exact negative; this check is limited to that registered contract.
    action_reaction = float(np.max(np.linalg.norm(force + (-force), axis=2)))
    anchors = _payload_anchors(values)
    grasp = _grasp_matrix(anchors)
    pinv = np.linalg.pinv(grasp, rcond=1.0e-12)
    flat_force = force.reshape(len(force), 8)
    wrench = flat_force @ grasp.T
    motion = wrench @ pinv.T
    internal = flat_force - motion
    null = internal @ grasp.T
    internal_null = float(np.max(np.linalg.norm(null, axis=1)))
    internal_peak = float(np.max(np.linalg.norm(internal, axis=1)))
    internal_relative = internal_null / max(internal_peak, 1.0)
    recorded_internal_error = float(
        np.max(np.abs(internal - np.asarray(arrays["internal_force_vector_n"], dtype=float)))
    )
    parent_comparison = None if parent is None else independent_compare_common_fields(arrays, parent)
    row = {
        **identity,
        "shape_contract_passed": shapes["passed"],
        "unit_contract_passed": units["passed"],
        "contract_issues": json.dumps(shapes["issues"] + units["issues"]),
        "finite": bool(finite),
        "time_grid_max_abs_s": time_grid_error,
        "actual_icr_peak_mps": actual["peak_mps"],
        "actual_icr_p95_mps": actual["p95_mps"],
        "actual_icr_rms_mps": actual["rms_mps"],
        "actual_icr_fraction_gt_0p5": actual["fraction_gt_0p5"],
        "actual_rate_peak_radps": rate_peak,
        "actual_angle_peak_rad": angle_peak,
        "tire_raw_utilization_max": tire_peak,
        "support_min_n": support_min,
        "support_sum_residual_max_n": support_sum_residual,
        "connector_force_peak_n": connector_peak,
        "action_reaction_max_n": action_reaction,
        "internal_null_relative": internal_relative,
        "internal_vector_recompute_max_abs_n": recorded_internal_error,
        "a3_parent_common_max_abs": None if parent_comparison is None else parent_comparison["max_abs"],
    }
    return row, _switching_stretch(identity, arrays, protocol)


def independent_aggregate(rows: list[dict], file_checks: list[dict], protocol: dict) -> dict:
    expected = {
        (direction, plant["name"], mode)
        for direction in protocol["n2"]["directions"]
        for plant in protocol["n2"]["plants"]
        for mode in protocol["n2"]["mathematical_mode_order"]
    }
    identities = [(row["direction"], row["plant"], row["actuator_mode"]) for row in rows]
    actual = set(identities)
    missing, unexpected = sorted(expected - actual), sorted(actual - expected)
    duplicate_count = len(identities) - len(actual)
    contract_failures = [row["trajectory_id"] for row in rows if not row["shape_contract_passed"] or not row["unit_contract_passed"] or not row["finite"]]
    hash_failures = [row["trajectory_id"] for row in file_checks if not row["passed"]]
    passed = not missing and not unexpected and duplicate_count == 0 and not contract_failures and not hash_failures and len(rows) == 16
    return {
        "passed": passed,
        "expected_count": 16,
        "actual_count": len(rows),
        "missing_identities": missing,
        "unexpected_identities": unexpected,
        "duplicate_identity_count": duplicate_count,
        "contract_failure_ids": contract_failures,
        "hash_failure_ids": hash_failures,
    }


def _independent_request_attribution(protocol: dict, output: Path) -> dict:
    parent = protocol["parent_f3"]
    manifest_path = PROJECT / Path(parent["run_root"]) / Path(parent["manifest_relpath"])
    manifest = _read_csv(manifest_path)
    raw_root = PROJECT / Path(parent["data_root"])
    threshold = float(protocol["f3"]["diagnostic_icr_threshold_mps"])
    rows, file_checks = [], []
    g0_max, g2_max = 0.0, 0.0
    for manifest_row in manifest:
        raw_path = raw_root / Path(manifest_row["raw_path"]).name
        actual_sha = _sha256(raw_path) if raw_path.exists() else None
        file_checks.append({"trajectory_id": int(manifest_row["trajectory_id"]), "expected_sha256": manifest_row["raw_file_sha256"], "actual_sha256": actual_sha, "passed": actual_sha == manifest_row["raw_file_sha256"]})
        if actual_sha != manifest_row["raw_file_sha256"]:
            continue
        arrays = _load_npz(raw_path)
        params = json.loads(str(arrays["params_json"].item()))
        wheelbase = float(params["values"]["vehicle"]["lf_m"] + params["values"]["vehicle"]["lr_m"])
        layer_series = {layer: [] for layer in ("G0", "G1", "G2")}
        request_difference = 0.0
        for index in range(len(arrays["time_s"])):
            state = arrays["initial_state30"] if index == 0 else arrays["state30"][index - 1]
            layers = _request_layers(state, arrays["virtual_front_deg"][index], arrays["virtual_rear_deg"][index], params)
            for layer in ("G0", "G1", "G2"):
                result = independent_icr(layers["speed_mps"], layers["yaw_rate_radps"], wheelbase, layers[layer], threshold)
                layer_series[layer].append(float(result["series_mps"]))
            request_difference = max(request_difference, float(np.max(np.abs(layers["G2"] - arrays["requested_control4x2"][index, :, 1]))))
        metrics = {layer: _stats(np.asarray(values), threshold) for layer, values in layer_series.items()}
        identity = {key: manifest_row[key] for key in ("trajectory_id", "base_family_id", "split", "seed", "direction", "plant", "law", "load_mode")}
        for layer in ("G0", "G1", "G2"):
            rows.append({**identity, "layer": layer, **metrics[layer], "g2_parent_request_max_abs_rad": request_difference})
        g0_max = max(g0_max, metrics["G0"]["peak_mps"])
        g2_max = max(g2_max, request_difference)
    _write_csv(output / "independent_request_attribution.csv", rows)
    manifest_sha = _sha256(manifest_path)
    passed = bool(
        len(manifest) == int(parent["expected_trajectory_count"])
        and len(rows) == 3 * len(manifest)
        and manifest_sha == parent["manifest_sha256"]
        and all(item["passed"] for item in file_checks)
        and g0_max <= float(protocol["f3"]["geometry_residual_atol_mps"])
        and g2_max <= float(protocol["f3"]["g2_parent_request_atol_rad"])
    )
    return {"passed": passed, "parent_trajectory_count": len(manifest), "row_count": len(rows), "g0_peak_max_mps": g0_max, "g2_parent_request_max_abs_rad": g2_max, "manifest_sha256": manifest_sha, "file_checks": file_checks, "rows": rows}


def compare_records(
    primary: list[dict], independent: list[dict], key_fields: tuple[str, ...],
    metrics: Mapping[str, float], group: str,
) -> dict:
    primary_map = {tuple(str(row[field]) for field in key_fields): row for row in primary}
    independent_map = {tuple(str(row[field]) for field in key_fields): row for row in independent}
    rows = []
    for key in sorted(set(primary_map) | set(independent_map)):
        left, right = primary_map.get(key), independent_map.get(key)
        for metric, atol in metrics.items():
            missing = left is None or right is None or metric not in left or metric not in right
            if missing:
                pvalue = None if left is None else left.get(metric)
                ivalue = None if right is None else right.get(metric)
                difference, passed = None, False
            elif left[metric] in {None, "", "None"} and right[metric] in {None, "", "None"}:
                pvalue = ivalue = None
                difference, passed = 0.0, True
            else:
                pvalue, ivalue = float(left[metric]), float(right[metric])
                difference = abs(pvalue - ivalue)
                passed = bool(np.isfinite(difference) and difference <= float(atol))
            rows.append({"group": group, "identity": json.dumps(key), "metric": metric, "primary": pvalue, "independent": ivalue, "abs_difference": difference, "atol": float(atol), "passed": passed})
    return {"passed": bool(rows) and all(row["passed"] for row in rows), "rows": rows}


def _parent_seed_arrays(protocol: dict) -> dict[tuple[str, str], dict[str, np.ndarray]]:
    parent = protocol["parent_f3"]
    manifest_path = PROJECT / Path(parent["run_root"]) / Path(parent["manifest_relpath"])
    raw_root = PROJECT / Path(parent["data_root"])
    output = {}
    for row in _read_csv(manifest_path):
        if int(row["seed"]) == int(protocol["n2"]["seed"]) and row["load_mode"] == "L1":
            output[(row["direction"], row["plant"])] = _load_npz(raw_root / Path(row["raw_path"]).name)
    if len(output) != 4:
        raise RuntimeError(f"independent parent lookup expected four identities, found {sorted(output)}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Formula-independent recomputation of frozen N2 evidence.")
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--data-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    protocol_path = Path(args.protocol).resolve()
    manifest_path = Path(args.data_manifest).resolve()
    primary_output = manifest_path.parent
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    protocol = _read_json(protocol_path)
    tolerances = protocol["independent_recompute_tolerances"]
    manifest_rows = _read_csv(manifest_path)
    parents = _parent_seed_arrays(protocol)
    physics_rows, stretch_rows, file_checks = [], [], []
    for manifest_row in manifest_rows:
        raw_path = Path(manifest_row["raw_path"])
        if not raw_path.exists():
            raw_path = primary_output / "raw" / raw_path.name
        meta_path = raw_path.with_suffix(".meta.json")
        actual_sha = _sha256(raw_path) if raw_path.exists() else None
        check = {"trajectory_id": int(manifest_row["trajectory_id"]), "expected_sha256": manifest_row["raw_file_sha256"], "actual_sha256": actual_sha, "meta_exists": meta_path.exists(), "passed": actual_sha == manifest_row["raw_file_sha256"] and meta_path.exists()}
        file_checks.append(check)
        if not check["passed"]:
            continue
        identity = {
            "trajectory_id": int(manifest_row["trajectory_id"]),
            "base_family_id": manifest_row["base_family_id"],
            "seed": int(manifest_row["seed"]),
            "scenario": manifest_row["scenario"],
            "direction": manifest_row["direction"],
            "plant": manifest_row["plant"],
            "law": manifest_row["law"],
            "load_mode": manifest_row["load_mode"],
            "load_transfer_enabled": _as_bool(manifest_row["load_transfer_enabled"]),
            "actuator_mode": manifest_row["actuator_mode"],
            "replay_hash_match": _as_bool(manifest_row["replay_hash_match"]),
        }
        arrays, summary = _load_npz(raw_path), _read_json(meta_path)
        parent = parents[(identity["direction"], identity["plant"])] if identity["actuator_mode"] == "A3" else None
        row, switches = independent_physics(identity, arrays, summary, protocol, parent)
        physics_rows.append(row)
        stretch_rows.extend(switches)
    aggregate = independent_aggregate(physics_rows, file_checks, protocol)
    request = _independent_request_attribution(protocol, output)
    _write_csv(output / "independent_physics.csv", physics_rows)
    _write_csv(output / "independent_stretch_switching_impulse.csv", stretch_rows)
    _write_json(output / "aggregate.json", aggregate)

    comparisons = []
    physics_comparison = compare_records(
        _read_csv(primary_output / "physics_audit.csv"), physics_rows,
        ("direction", "plant", "actuator_mode"),
        {
            "actual_icr_peak_mps": tolerances["icr_mps_abs"],
            "actual_icr_p95_mps": tolerances["icr_mps_abs"],
            "actual_icr_rms_mps": tolerances["icr_mps_abs"],
            "actual_icr_fraction_gt_0p5": tolerances["fraction_abs"],
            "actual_rate_peak_radps": tolerances["rate_radps_abs"],
            "actual_angle_peak_rad": tolerances["angle_rad_abs"],
            "tire_raw_utilization_max": tolerances["tire_abs"],
            "support_min_n": tolerances["support_n_abs"],
            "support_sum_residual_max_n": tolerances["support_n_abs"],
            "connector_force_peak_n": tolerances["force_n_abs"],
            "action_reaction_max_n": tolerances["force_n_abs"],
            "internal_null_relative": tolerances["relative_abs"],
            "a3_parent_common_max_abs": tolerances["parent_common_abs"],
        }, "physics",
    )
    comparisons.extend(physics_comparison["rows"])
    request_comparison = compare_records(
        _read_csv(primary_output / "request_attribution.csv"), request["rows"],
        ("trajectory_id", "layer"),
        {"peak_mps": tolerances["icr_mps_abs"], "p95_mps": tolerances["icr_mps_abs"], "rms_mps": tolerances["icr_mps_abs"], "fraction_gt_0p5": tolerances["fraction_abs"], "g2_parent_request_max_abs_rad": tolerances["angle_rad_abs"]},
        "request",
    )
    comparisons.extend(request_comparison["rows"])
    stretch_comparison = compare_records(
        _read_csv(primary_output / "stretch_switching_impulse.csv"), stretch_rows,
        ("direction", "plant", "actuator_mode", "switch_number"),
        {"front_rear_abs_impulse_ns": tolerances["impulse_ns_abs"], "left_right_abs_impulse_ns": tolerances["impulse_ns_abs"], "front_rear_peak_n": tolerances["force_n_abs"], "left_right_peak_n": tolerances["force_n_abs"]},
        "stretch",
    )
    comparisons.extend(stretch_comparison["rows"])
    _write_csv(output / "primary_independent_comparison.csv", comparisons)
    comparison = {
        "passed": physics_comparison["passed"] and request_comparison["passed"] and stretch_comparison["passed"],
        "row_count": len(comparisons),
        "failure_count": sum(not row["passed"] for row in comparisons),
        "first_failure": next((row for row in comparisons if not row["passed"]), None),
        "max_finite_abs_difference": max((float(row["abs_difference"]) for row in comparisons if row["abs_difference"] is not None and np.isfinite(float(row["abs_difference"]))), default=0.0),
    }
    _write_json(output / "comparison_summary.json", comparison)
    passed = bool(aggregate["passed"] and request["passed"] and comparison["passed"])
    complete = {
        "passed": passed,
        "status": "PASS" if passed else "BLOCKED_DIAGNOSTIC_INTEGRITY",
        "script_sha256": _sha256(Path(__file__).resolve()),
        "protocol_sha256": _sha256(protocol_path),
        "data_manifest_sha256": _sha256(manifest_path),
        "trajectory_count": len(physics_rows),
        "file_checks": file_checks,
        "aggregate": aggregate,
        "request": {key: value for key, value in request.items() if key not in {"rows", "file_checks"}},
        "parent_request_file_mismatch_count": sum(not row["passed"] for row in request["file_checks"]),
        "comparison": comparison,
        "raw_action_reaction_limit": "payload force only; vehicle side reconstructed by registered exact-negative connector contract",
    }
    _write_json(output / "complete.json", complete)
    print(json.dumps(complete, ensure_ascii=False, allow_nan=False), flush=True)
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
