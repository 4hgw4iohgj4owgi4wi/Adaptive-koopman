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
