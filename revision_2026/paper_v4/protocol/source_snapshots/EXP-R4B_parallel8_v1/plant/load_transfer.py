from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class SupportLiftOutsideEnvelope(RuntimeError):
    def __init__(self, loads_n: np.ndarray, acceleration_body_mps2: np.ndarray):
        self.loads_n = np.asarray(loads_n, dtype=float).copy()
        self.acceleration_body_mps2 = np.asarray(acceleration_body_mps2, dtype=float).copy()
        super().__init__(
            "SUPPORT_LIFT_OUTSIDE_ENVELOPE: "
            f"min_support_n={float(np.min(self.loads_n))}, "
            f"payload_accel_body_mps2={self.acceleration_body_mps2.tolist()}"
        )


@dataclass(frozen=True)
class SupportLoadConfig:
    payload_mass_kg: float
    payload_cog_height_m: float
    gravity_mps2: float
    support_points_body_m: tuple[tuple[float, float], ...]
    negative_load_atol_n: float = -1.0e-9

    def matrix(self) -> np.ndarray:
        points = np.asarray(self.support_points_body_m, dtype=float)
        if points.shape != (4, 2) or not np.all(np.isfinite(points)):
            raise ValueError("support points must be finite 4x2 coordinates")
        matrix = np.vstack([np.ones(4), points[:, 0], points[:, 1]])
        if np.linalg.matrix_rank(matrix) != 3:
            raise ValueError("support geometry matrix must have rank three")
        return matrix

    def validate(self) -> None:
        if self.payload_mass_kg <= 0.0 or self.payload_cog_height_m < 0.0:
            raise ValueError("invalid payload mass or CoG height")
        if self.gravity_mps2 <= 0.0:
            raise ValueError("gravity must be positive")
        self.matrix()


def config_from_model(params: object) -> SupportLoadConfig:
    config = SupportLoadConfig(
        payload_mass_kg=float(params.payload.mass_kg),
        payload_cog_height_m=float(params.payload.cog_height_m),
        gravity_mps2=float(params.payload.gravity_mps2),
        support_points_body_m=tuple(
            tuple(map(float, row)) for row in np.asarray(params.payload_anchor_body_m, dtype=float)
        ),
    )
    config.validate()
    return config


def solve_payload_support_loads(
    acceleration_body_mps2: np.ndarray,
    config: SupportLoadConfig,
    *,
    enabled: bool,
) -> dict:
    """Minimum-deviation four-support allocation in payload FL,FR,RL,RR order."""

    config.validate()
    acceleration = np.asarray(acceleration_body_mps2, dtype=float).reshape(2)
    if not np.all(np.isfinite(acceleration)):
        raise ValueError("payload acceleration must be finite")
    matrix = config.matrix()
    total = config.payload_mass_kg * config.gravity_mps2
    static = np.full(4, total / 4.0, dtype=float)
    target = np.asarray(
        [
            total,
            -config.payload_mass_kg * config.payload_cog_height_m * acceleration[0],
            -config.payload_mass_kg * config.payload_cog_height_m * acceleration[1],
        ],
        dtype=float,
    )
    if enabled:
        gram = matrix @ matrix.T
        loads = static + matrix.T @ np.linalg.solve(gram, target - matrix @ static)
    else:
        loads = static.copy()
        target = matrix @ static
    if not np.all(np.isfinite(loads)):
        raise FloatingPointError("non-finite support load")
    if float(np.min(loads)) < config.negative_load_atol_n:
        raise SupportLiftOutsideEnvelope(loads, acceleration)
    if np.any(loads < 0.0):
        loads = np.maximum(loads, 0.0)
    residual = matrix @ loads - target
    scale = np.maximum(np.abs(target), np.asarray([total, total, total], dtype=float))
    relative = np.abs(residual) / np.maximum(scale, 1.0)
    return {
        "payload_support_load_n": loads,
        "static_support_load_n": static,
        "constraint_target": target,
        "constraint_residual": residual,
        "constraint_relative_residual": relative,
        "minimum_support_load_n": float(np.min(loads)),
        "enabled": bool(enabled),
        "status": "PASS",
    }

