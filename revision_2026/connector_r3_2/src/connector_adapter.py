from __future__ import annotations

from dataclasses import asdict

from connector_r3 import ConnectorR3Params
from connector_v1 import ConnectorV1Params, scalar_force_v1


DELTA_S_M = 0.0001776170305060031


class ScalarConnector:
    """One-dimensional adapter preserving the frozen V1 and R3 force laws."""

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
        # Scalar specialization of the frozen vector R3 implementation.  The
        # algebra and thresholds are identical; N1 checks it pointwise against
        # connector_force_r3 so this optimization cannot silently drift.
        penetration = max(float(penetration_m), 0.0)
        speed = float(normal_speed_mps)
        s = min(max(penetration / self.params.smoothing_width_m, 0.0), 1.0)
        weight = 0.0 if penetration <= 0.0 else (1.0 if penetration >= self.params.smoothing_width_m else 3.0 * s**2 - 2.0 * s**3)
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
