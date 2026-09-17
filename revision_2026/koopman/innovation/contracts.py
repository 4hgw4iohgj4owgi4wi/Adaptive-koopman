from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class HorizonBatch:
    x0_s3: np.ndarray
    u_future: np.ndarray
    y_state: np.ndarray
    y_force: np.ndarray
    y_load: np.ndarray
    mask: np.ndarray
    trajectory_id: np.ndarray
    start_index: np.ndarray


@dataclass
class InnovationPrediction:
    state: np.ndarray
    point_force: np.ndarray
    payload_load: np.ndarray
    regime_weight: np.ndarray
    uncertainty: np.ndarray
    finite_mask: np.ndarray


def validate_batch(batch: HorizonBatch) -> None:
    b = len(batch.x0_s3)
    expected = {"x0_s3": (b, 46), "u_future": (b, 20, 8), "y_state": (b, 20, 30),
                "y_force": (b, 20, 4, 2), "y_load": (b, 20, 2), "mask": (b, 20),
                "trajectory_id": (b,), "start_index": (b,)}
    for key, shape in expected.items():
        value = np.asarray(getattr(batch, key))
        if value.shape != shape: raise ValueError(f"{key}: {value.shape} != {shape}")
        if key not in ("trajectory_id",) and not np.all(np.isfinite(value)): raise ValueError(f"{key}: non-finite")


def validate_prediction(pred: InnovationPrediction, batch: int, modes: int) -> None:
    expected = {"state": (batch, 20, 30), "point_force": (batch, 20, 4, 2),
                "payload_load": (batch, 20, 2), "regime_weight": (batch, 20, modes),
                "uncertainty": (batch, 20, 3), "finite_mask": (batch, 20)}
    for key, shape in expected.items():
        value = np.asarray(getattr(pred, key))
        if value.shape != shape: raise ValueError(f"{key}: {value.shape} != {shape}")

