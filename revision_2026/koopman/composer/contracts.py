from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class PredictionBundle:
    state_s3: np.ndarray
    state_main: np.ndarray
    point_force: np.ndarray
    payload_load: np.ndarray
    force_rate: np.ndarray
    finite_mask: np.ndarray
    expert_name: str
    metadata: dict[str, Any] = field(default_factory=dict)


def validate_bundle(bundle: PredictionBundle, horizon: int = 20) -> None:
    expected = {
        "state_s3": (horizon, 46), "state_main": (horizon, 30),
        "point_force": (horizon, 4, 2), "payload_load": (horizon, 2),
        "force_rate": (horizon, 4, 2), "finite_mask": (horizon,),
    }
    for name, shape in expected.items():
        value = np.asarray(getattr(bundle, name))
        if value.shape != shape:
            raise ValueError(f"{bundle.expert_name}/{name}: {value.shape} != {shape}")
    if bundle.expert_name not in {"K0", "K1", "K4", "K5F2"}:
        raise ValueError(f"unknown expert {bundle.expert_name}")
    finite = np.asarray(bundle.finite_mask, dtype=bool)
    joined = np.c_[bundle.state_s3, bundle.state_main,
                   bundle.point_force.reshape(horizon, 8), bundle.payload_load,
                   bundle.force_rate.reshape(horizon, 8)]
    if np.any(finite & ~np.all(np.isfinite(joined), axis=1)):
        raise ValueError(f"{bundle.expert_name}: finite mask contradicts values")

