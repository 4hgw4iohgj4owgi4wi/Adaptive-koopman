from __future__ import annotations

from dataclasses import asdict

import numpy as np

from .connector_r3 import ConnectorR3Params
from .connector_v1 import ConnectorV1Params, scalar_force_v1


DELTA_S_M = 0.0001776170305060031


class ScalarConnector:
    """One-dimensional adapter preserving the frozen V1 and R3 algebra."""

    def __init__(self, law: str):
        self.law = law.upper()
        if self.law == "V1":
            self.params = ConnectorV1Params(smoothing_width_m=DELTA_S_M)
        elif self.law == "R3":
            self.params = ConnectorR3Params(smoothing_width_m=DELTA_S_M)
        else:
            raise ValueError(f"unknown connector law: {law}")

    def evaluate(self, penetration_m: float, normal_speed_mps: float) -> dict[str, float | bool]:
        if self.law == "V1":
            return scalar_force_v1(penetration_m, normal_speed_mps, self.params)
        penetration = max(float(penetration_m), 0.0)
        speed = float(normal_speed_mps)
        s = min(max(penetration / self.params.smoothing_width_m, 0.0), 1.0)
        weight = 0.0 if penetration <= 0.0 else (
            1.0 if penetration >= self.params.smoothing_width_m else 3.0 * s**2 - 2.0 * s**3
        )
        elastic = self.params.stiffness_npm * penetration
        damping = self.params.damping_nspm * weight * max(speed, 0.0)
        force = elastic + damping
        return {
            "force_n": force,
            "elastic_n": elastic,
            "damping_n": damping,
            "elastic_energy_j": 0.5 * self.params.stiffness_npm * penetration**2,
            "damping_power_w": self.params.damping_nspm * weight * max(speed, 0.0) ** 2,
            "smoothing_weight": weight,
            "contact_active": penetration > 0.0,
            "ultimate_exceeded": force >= self.params.ultimate_force_n,
        }

    def metadata(self) -> dict:
        return {"law": self.law, **asdict(self.params)}


class VectorConnector:
    """Fair four-point V1/R3 interface in world coordinates."""

    def __init__(self, law: str, params: ConnectorR3Params | None = None):
        self.law = law.upper()
        if self.law not in {"V1", "R3"}:
            raise ValueError(f"unknown connector law: {law}")
        self.params = params or ConnectorR3Params(smoothing_width_m=DELTA_S_M)

    def evaluate(self, displacement_world_m: np.ndarray, relative_velocity_world_mps: np.ndarray) -> dict:
        displacement = np.asarray(displacement_world_m, dtype=float)
        velocity = np.asarray(relative_velocity_world_mps, dtype=float)
        if displacement.shape != velocity.shape or displacement.ndim != 2 or displacement.shape[1] != 2:
            raise ValueError("displacement and velocity must share [n,2] shape")
        distance = np.linalg.norm(displacement, axis=1)
        normal = displacement / np.maximum(distance[:, None], 1e-12)
        signed_gap = distance - self.params.free_play_m
        penetration = np.maximum(signed_gap, 0.0)
        normal_speed = np.sum(velocity * normal, axis=1)
        if self.law == "V1":
            weight = (penetration > 0.0).astype(float)
        else:
            s = np.clip(penetration / self.params.smoothing_width_m, 0.0, 1.0)
            weight = np.where(
                penetration <= 0.0,
                0.0,
                np.where(penetration >= self.params.smoothing_width_m, 1.0, 3.0 * s**2 - 2.0 * s**3),
            )
        elastic = self.params.stiffness_npm * penetration
        damping = self.params.damping_nspm * weight * np.maximum(normal_speed, 0.0)
        force_norm = elastic + damping
        force_payload = force_norm[:, None] * normal
        return {
            "law": self.law,
            "distance_m": distance,
            "signed_gap_m": signed_gap,
            "penetration_m": penetration,
            "normal_world": normal,
            "normal_speed_mps": normal_speed,
            "smoothing_weight": weight,
            "elastic_force_n": elastic,
            "damping_force_n": damping,
            "raw_force_n": force_norm,
            "applied_force_n": force_norm.copy(),
            "force_payload_world_n": force_payload,
            "force_vehicle_world_n": -force_payload,
            "elastic_energy_j": 0.5 * self.params.stiffness_npm * penetration**2,
            "damping_power_w": self.params.damping_nspm * weight * np.maximum(normal_speed, 0.0) ** 2,
            "contact_active": penetration > 0.0,
            "rated_force_exceeded": force_norm >= self.params.rated_force_n,
            "ultimate_force_exceeded": force_norm >= self.params.ultimate_force_n,
        }


