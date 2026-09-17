from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np

from dataset import nonoverlap_window_indices


CORE_VARIABLE_KEYS = (
    "relative_state47_k",
    "force_endpoint8_k",
    "force_mean8_prev",
    "force_rate8_prev",
    "u8_k",
    "delta_u8_k",
)


def classify_windows(arrays: dict[str, np.ndarray], steps: int) -> list[dict]:
    rows: list[dict] = []
    for start, stop in nonoverlap_window_indices(len(arrays["time_s"]), steps):
        events = np.asarray(arrays["event_counts16"][start:stop], dtype=float)
        smoothing = np.asarray(arrays["smoothing_fraction"][start:stop], dtype=float)
        controls = np.asarray(arrays["control4x2"][start:stop], dtype=float)
        yaw_rate = np.asarray(arrays["state30"][start:stop, 29], dtype=float)
        event_active = bool(np.any(events > 0.0) or np.any(smoothing > 0.0))
        steering_active = bool(np.max(np.abs(controls[:, :, 1])) > np.deg2rad(0.5))
        acceleration_active = bool(np.max(np.abs(controls[:, :, 0])) > 0.05)
        yaw_active = bool(np.max(np.abs(yaw_rate)) > 0.02)
        if event_active:
            label = "event"
        elif steering_active or acceleration_active or yaw_active:
            label = "maneuver"
        else:
            label = "steady"
        rows.append(
            {
                "start": start,
                "stop": stop,
                "class": label,
                "event_count": int(np.sum(events)),
                "smoothing_exposure": float(np.mean(smoothing)),
                "max_abs_steering_rad": float(np.max(np.abs(controls[:, :, 1]))),
                "max_abs_acceleration_mps2": float(np.max(np.abs(controls[:, :, 0]))),
            }
        )
    return rows


def schema_audit(combined: dict[str, np.ndarray], constant_atol: float) -> dict:
    unexpected_constants: list[str] = []
    checked_dimensions = 0
    nonfinite_count = 0
    wrong_scale_fields: list[str] = []
    bounds = {
        "relative_state47_k": 1.0e3,
        "force_endpoint8_k": 2.0e4,
        "force_mean8_prev": 2.0e4,
        "force_rate8_prev": 1.0e7,
        "u8_k": 10.0,
        "delta_u8_k": 10.0,
    }
    for key in CORE_VARIABLE_KEYS:
        values = np.asarray(combined[key], dtype=float)
        flat = values.reshape(values.shape[0], -1)
        checked_dimensions += flat.shape[1]
        nonfinite_count += int(np.size(flat) - np.sum(np.isfinite(flat)))
        span = np.ptp(flat, axis=0)
        unexpected_constants.extend(f"{key}[{index}]" for index in np.flatnonzero(span <= constant_atol))
        if np.max(np.abs(flat)) > bounds[key]:
            wrong_scale_fields.append(key)
    return {
        "checked_core_dimension_count": checked_dimensions,
        "unexpected_constant_count": len(unexpected_constants),
        "unexpected_constant_fields": unexpected_constants,
        "nonfinite_count": nonfinite_count,
        "wrong_scale_field_count": len(wrong_scale_fields),
        "wrong_scale_fields": wrong_scale_fields,
        "excluded_by_contract": [
            "physical_state30_k/global pose is reconstructed context",
            "parameter_vector_k/audit-only and some parameters intentionally fixed",
            "event supervision fields/sparse categorical counts",
            "network fields/not used in clean training",
        ],
    }


def build_coverage(
    trajectories: list[tuple[dict, dict[str, np.ndarray]]],
    combined_by_plant: dict[str, dict[str, np.ndarray]],
    protocol: dict,
) -> dict:
    config = protocol["k2"]
    class_counts = Counter()
    split_class_counts: dict[str, Counter] = defaultdict(Counter)
    scenario_class_counts: dict[str, Counter] = defaultdict(Counter)
    direction_counts = Counter()
    natural_event_scenarios = set()
    trajectory_rows = []
    for identity, arrays in trajectories:
        windows = classify_windows(arrays, int(config["window_steps"]))
        counts = Counter(row["class"] for row in windows)
        class_counts.update(counts)
        split_class_counts[str(identity["split"])].update(counts)
        scenario_class_counts[str(identity["scenario"])].update(counts)
        if identity["direction"] in {"left", "right"}:
            direction_counts[str(identity["direction"])] += len(windows)
        if identity["scenario"] in config["natural_event_scenarios"] and counts["event"] > 0:
            natural_event_scenarios.add(str(identity["scenario"]))
        trajectory_rows.append(
            {
                "trajectory_id": int(identity["trajectory_id"]),
                "scenario": identity["scenario"],
                "direction": identity["direction"],
                "plant": identity["plant"],
                "split": identity["split"],
                "window_count": len(windows),
                "steady_windows": counts["steady"],
                "maneuver_windows": counts["maneuver"],
                "event_windows": counts["event"],
            }
        )
    schema_by_plant = {
        plant: schema_audit(combined, float(config["schema_constant_atol"]))
        for plant, combined in combined_by_plant.items()
    }
    left = direction_counts["left"]
    right = direction_counts["right"]
    imbalance = abs(left - right) / max(left + right, 1)
    class_gate = all(class_counts[name] > 0 for name in ("steady", "maneuver", "event"))
    natural_gate = set(config["natural_event_scenarios"]).issubset(natural_event_scenarios)
    schema_gate = all(
        audit["unexpected_constant_count"] == 0
        and audit["nonfinite_count"] == 0
        and audit["wrong_scale_field_count"] == 0
        for audit in schema_by_plant.values()
    )
    hard_gate = bool(class_gate and natural_gate and imbalance <= float(config["left_right_imbalance_max"]) and schema_gate)
    return {
        "hard_gate_passed": hard_gate,
        "window_steps": int(config["window_steps"]),
        "classification": {
            "event": "any event count or smoothing exposure inside the non-overlapping window",
            "maneuver": "no event and steering>0.5 deg, |acceleration|>0.05 m/s^2, or |payload yaw rate|>0.02 rad/s",
            "steady": "no event and none of the maneuver thresholds active",
        },
        "class_counts": dict(class_counts),
        "split_class_counts": {key: dict(value) for key, value in split_class_counts.items()},
        "scenario_class_counts": {key: dict(value) for key, value in scenario_class_counts.items()},
        "direction_window_counts": dict(direction_counts),
        "left_right_imbalance": imbalance,
        "left_right_imbalance_limit": float(config["left_right_imbalance_max"]),
        "natural_event_scenarios": sorted(natural_event_scenarios),
        "required_natural_event_scenarios": list(config["natural_event_scenarios"]),
        "schema_by_plant": schema_by_plant,
        "gates": {
            "three_classes_nonzero": class_gate,
            "all_three_natural_scenarios_have_events": natural_gate,
            "left_right_balance": imbalance <= float(config["left_right_imbalance_max"]),
            "schema": schema_gate,
        },
        "trajectory_rows": trajectory_rows,
    }
