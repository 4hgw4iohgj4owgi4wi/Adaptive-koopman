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
