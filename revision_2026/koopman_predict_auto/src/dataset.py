from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import numpy as np

from data_adapter import INPUT_KEYS, LABEL_KEYS, build_sample


NUMERIC_SAMPLE_KEYS = INPUT_KEYS + LABEL_KEYS


def trajectory_samples(
    arrays: dict[str, np.ndarray],
    params: object,
    *,
    expected_step_s: float,
    step_atol_s: float,
) -> dict[str, np.ndarray]:
    samples = [
        build_sample(
            arrays,
            index,
            params,
            expected_step_s=expected_step_s,
            step_atol_s=step_atol_s,
        )
        for index in range(1, len(arrays["time_s"]) - 1)
    ]
    if not samples:
        raise ValueError("trajectory has no causal samples")
    result = {key: np.asarray([sample[key] for sample in samples]) for key in NUMERIC_SAMPLE_KEYS}
    result["sample_time_s"] = np.asarray([sample["sample_time_s"] for sample in samples], dtype=float)
    result["target_time_s"] = np.asarray([sample["target_time_s"] for sample in samples], dtype=float)
    result["source_index"] = np.asarray([sample["source_index"] for sample in samples], dtype=int)
    return result


def concatenate_trajectories(entries: Iterable[tuple[dict, dict[str, np.ndarray]]]) -> dict[str, np.ndarray]:
    buckets: dict[str, list[np.ndarray]] = defaultdict(list)
    for identity, arrays in entries:
        count = len(arrays["sample_time_s"])
        for key, value in arrays.items():
            buckets[key].append(np.asarray(value))
        buckets["trajectory_id"].append(np.full(count, int(identity["trajectory_id"]), dtype=int))
        buckets["base_family_id"].append(np.full(count, str(identity["base_family_id"])))
        buckets["split"].append(np.full(count, str(identity["split"])))
        buckets["scenario"].append(np.full(count, str(identity["scenario"])))
        buckets["direction"].append(np.full(count, str(identity["direction"])))
        buckets["plant"].append(np.full(count, str(identity["plant"])))
    if not buckets:
        raise ValueError("no trajectories to concatenate")
    return {key: np.concatenate(values, axis=0) for key, values in buckets.items()}


def normalization_from_train(combined: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    split = np.asarray(combined["split"]).astype(str)
    mask = split == "train"
    if not np.any(mask) or np.any(split[mask] != "train"):
        raise ValueError("normalization must have non-empty train-only rows")
    keys = (
        "relative_state47_k",
        "force_endpoint8_k",
        "force_mean8_prev",
        "force_rate8_prev",
        "u8_k",
        "delta_u8_k",
    )
    output: dict[str, np.ndarray] = {
        "source_split": np.asarray("train"),
        "source_row_count": np.asarray(int(np.sum(mask))),
    }
    for key in keys:
        values = np.asarray(combined[key], dtype=float)[mask]
        mean = np.mean(values, axis=0)
        scale = np.std(values, axis=0)
        output[f"{key}_mean"] = mean
        output[f"{key}_scale"] = np.maximum(scale, 1.0e-12)
    return output


def nonoverlap_window_indices(length: int, steps: int) -> list[tuple[int, int]]:
    if steps <= 0:
        raise ValueError("window steps must be positive")
    return [(start, start + steps) for start in range(0, length - steps + 1, steps)]


def validate_base_family_split_contract(
    base_family_id: np.ndarray,
    split: np.ndarray,
) -> dict[str, int | bool]:
    """Enforce base-family grouping before any sample/window split is used."""

    families = np.asarray(base_family_id).astype(str)
    splits = np.asarray(split).astype(str)
    if families.ndim != 1 or splits.ndim != 1 or families.shape != splits.shape:
        raise ValueError("base_family_id and split must be equal-length vectors")
    if families.size == 0:
        raise ValueError("empty family split ledger")
    family_to_splits: dict[str, set[str]] = defaultdict(set)
    for family, selected_split in zip(families, splits, strict=True):
        if not family or not selected_split:
            raise ValueError("blank family or split")
        family_to_splits[family].add(selected_split)
    leaking = {
        family: sorted(values)
        for family, values in family_to_splits.items()
        if len(values) != 1
    }
    if leaking:
        raise ValueError(f"base families cross splits: {leaking}")
    return {
        "passed": True,
        "row_count": int(families.size),
        "base_family_count": len(family_to_splits),
        "cross_split_family_count": 0,
    }


def normalization_from_visible_train(
    combined: dict[str, np.ndarray],
    keys: tuple[str, ...] | list[str],
) -> dict[str, np.ndarray]:
    """Fit normalization on train rows and reject premature confirm exposure."""

    splits = np.asarray(combined["split"]).astype(str)
    if np.any(splits == "confirm"):
        raise ValueError("confirm rows are invisible before the confirmation stage")
    mask = splits == "train"
    if not np.any(mask):
        raise ValueError("normalization requires non-empty train rows")
    output: dict[str, np.ndarray] = {
        "source_split": np.asarray("train"),
        "source_row_count": np.asarray(int(np.sum(mask))),
    }
    for key in keys:
        values = np.asarray(combined[key], dtype=float)
        if values.shape[0] != splits.size:
            raise ValueError(f"normalization field row mismatch: {key}")
        selected = values[mask]
        output[f"{key}_mean"] = np.mean(selected, axis=0)
        output[f"{key}_scale"] = np.maximum(np.std(selected, axis=0), 1.0e-12)
    return output


def trajectory_window_records(
    *,
    trajectory_id: str | int,
    source_index: np.ndarray,
    control_signal: np.ndarray,
    connector_event_signal: np.ndarray,
    steps: int,
    control_change_atol: float = 1.0e-12,
) -> list[dict[str, int | str | bool]]:
    """Create non-overlapping within-trajectory windows and causal class labels."""

    indices = np.asarray(source_index, dtype=int)
    control = np.asarray(control_signal, dtype=float)
    connector = np.asarray(connector_event_signal, dtype=float)
    if indices.ndim != 1 or control.shape[0] != indices.size or connector.shape[0] != indices.size:
        raise ValueError("window inputs must share their first dimension")
    if indices.size and not np.all(np.diff(indices) == 1):
        raise ValueError("source indices are not one contiguous trajectory")
    rows: list[dict[str, int | str | bool]] = []
    for start, stop in nonoverlap_window_indices(indices.size, steps):
        segment = control[start:stop]
        event_segment = connector[start:stop]
        has_connector_event = bool(np.any(np.abs(event_segment) > 0.0))
        has_control_change = bool(
            segment.shape[0] > 1
            and np.any(np.abs(np.diff(segment, axis=0)) > control_change_atol)
        )
        has_maneuver = bool(np.any(np.abs(segment) > control_change_atol))
        if has_connector_event:
            category = "connector_event"
        elif has_control_change:
            category = "switching"
        elif has_maneuver:
            category = "maneuver"
        else:
            category = "steady"
        rows.append(
            {
                "trajectory_id": str(trajectory_id),
                "start_row": int(start),
                "stop_row_exclusive": int(stop),
                "source_index_start": int(indices[start]),
                "source_index_end": int(indices[stop - 1]),
                "steps": int(steps),
                "category": category,
                "within_single_trajectory": True,
            }
        )
    return rows


def prediction_cache_from_raw(
    arrays: dict[str, np.ndarray], params: object, protocol: dict
) -> dict[str, np.ndarray]:
    """Build one method-neutral N5 cache from a single raw trajectory."""

    from actuator_rollout import rollout_actuator_step
    from physics_audit import classify_window
    from relative_coordinates import encode_relative
    from steering_actuator import SteeringActuatorConfig

    state30 = np.asarray(arrays["state30"], dtype=float)
    relative = np.asarray(
        [encode_relative(state, params)["relative_state47"] for state in state30],
        dtype=float,
    )
    actual = np.asarray(arrays["actual_steering_rad"], dtype=float)
    requested = np.asarray(arrays["requested_control4x2"], dtype=float)
    virtual = np.c_[
        np.asarray(arrays["base_acceleration_mps2"], dtype=float),
        np.deg2rad(np.asarray(arrays["virtual_front_deg"], dtype=float)),
        np.deg2rad(np.asarray(arrays["virtual_rear_deg"], dtype=float)),
    ]
    control7 = np.c_[virtual[1:], requested[1:, :, 1]]
    actuator_config = SteeringActuatorConfig(
        tau_delta_s=float(protocol["actuator"]["tau_delta_s"]),
        rate_max_radps=float(protocol["actuator"]["rate_max_radps"]),
        angle_max_rad=float(np.deg2rad(protocol["actuator"]["angle_max_deg"])),
    )
    analytic_next = []
    rate_masks = []
    angle_masks = []
    for index in range(len(actual) - 1):
        result = rollout_actuator_step(
            actual[index],
            requested[index + 1, :, 1],
            model_step_s=float(protocol["actuator"]["model_step_s"]),
            plant_step_s=float(protocol["actuator"]["plant_step_s"]),
            config=actuator_config,
        )
        analytic_next.append(result["delta_act_k1_rad"])
        rate_masks.append(np.any(result["rate_limited_substeps"], axis=0))
        angle_masks.append(np.any(result["angle_limited_substeps"], axis=0))
    steps = int(protocol["window"]["steps"])
    starts = np.arange(0, len(relative) - steps, steps, dtype=int)
    classes = np.asarray(
        [classify_window(arrays, int(start), int(start + steps), protocol) for start in starts]
    )
    cache = {
        "relative_state47": relative,
        "actual_steering4": actual,
        "control7": control7,
        "analytic_actual_next4": np.asarray(analytic_next, dtype=float),
        "analytic_rate_mask4": np.asarray(rate_masks, dtype=bool),
        "analytic_angle_mask4": np.asarray(angle_masks, dtype=bool),
        "force_payload_body8": np.asarray(arrays["force_payload_body_n"], dtype=float).reshape(-1, 8),
        "internal_force8": np.asarray(arrays["internal_force_vector_n"], dtype=float),
        "vehicle_yaw_rate4": np.asarray(arrays["vehicle_yaw_rate4_radps"], dtype=float),
        "payload_yaw_rate": np.asarray(arrays["payload_yaw_rate_radps"], dtype=float),
        "system_yaw_rate": np.asarray(arrays["system_yaw_rate_radps"], dtype=float),
        "window_start": starts,
        "window_class": classes,
    }
    for key, value in cache.items():
        array = np.asarray(value)
        if array.dtype.kind not in {"U", "S", "O"} and not np.all(np.isfinite(array)):
            raise ValueError(f"non-finite prediction cache field: {key}")
    analytic_error = float(
        np.max(np.abs(cache["analytic_actual_next4"] - actual[1:]))
    )
    if analytic_error > float(protocol["actuator"]["endpoint_atol_rad"]):
        raise ValueError(f"analytic actuator cache mismatch: {analytic_error}")
    return cache
