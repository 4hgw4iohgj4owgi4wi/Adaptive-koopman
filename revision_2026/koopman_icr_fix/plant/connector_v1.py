from __future__ import annotations

from dataclasses import dataclass


LAW_VERSION = "plant_v1_discontinuous_damping"


@dataclass(frozen=True)
class ConnectorV1Params:
    stiffness_npm: float = 30000.0
    damping_nspm: float = 3500.0
    free_play_m: float = 0.002
    smoothing_width_m: float = 0.0001776170305060031
    rated_force_n: float = 12000.0
    ultimate_force_n: float = 15000.0


def scalar_force_v1(penetration_m: float, normal_speed_mps: float, params: ConnectorV1Params):
    """Return force components for the frozen V1 law without force clipping."""
    penetration = max(float(penetration_m), 0.0)
    loading_speed = max(float(normal_speed_mps), 0.0)
    active = penetration > 0.0
    elastic = params.stiffness_npm * penetration if active else 0.0
    damping = params.damping_nspm * loading_speed if active else 0.0
    force = elastic + damping
    return {
        "force_n": force,
        "elastic_n": elastic,
        "damping_n": damping,
        "elastic_energy_j": 0.5 * params.stiffness_npm * penetration**2,
        "damping_power_w": damping * loading_speed,
        "smoothing_weight": 1.0 if active else 0.0,
        "contact_active": active,
        "ultimate_exceeded": force >= params.ultimate_force_n,
    }

