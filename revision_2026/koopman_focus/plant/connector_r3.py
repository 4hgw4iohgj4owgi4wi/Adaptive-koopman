from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


LAW_VERSION = "plant_r3_boundary_regularized"
STRENGTH_SOURCE = "numerical_legacy_unverified"


@dataclass(frozen=True)
class ConnectorR3Params:
    law_version: str = LAW_VERSION
    stiffness_npm: float = 30000.0
    damping_nspm: float = 3500.0
    free_play_m: float = 0.002
    smoothing_width_m: float = 1.0e-4
    rated_force_n: float = 12000.0
    ultimate_force_n: float = 15000.0
    strength_source: str = STRENGTH_SOURCE


@dataclass(frozen=True)
class ConnectorResult:
    distance_m: np.ndarray
    penetration_m: np.ndarray
    normal_world: np.ndarray
    normal_speed_mps: np.ndarray
    smoothing_weight: np.ndarray
    elastic_force_n: np.ndarray
    damping_force_n: np.ndarray
    raw_force_n: np.ndarray
    applied_force_n: np.ndarray
    force_payload_world_n: np.ndarray
    force_vehicle_world_n: np.ndarray
    elastic_energy_j: np.ndarray
    damping_power_w: np.ndarray
    contact_active_raw: np.ndarray
    load_active_effective: np.ndarray
    rated_force_exceeded: np.ndarray
    ultimate_force_exceeded: np.ndarray


def smoothing_weight(penetration_m: np.ndarray, width_m: float) -> np.ndarray:
    if not np.isfinite(width_m) or width_m <= 0.0:
        raise ValueError("smoothing_width_m must be positive and finite")
    delta = np.asarray(penetration_m, dtype=float)
    s = np.clip(delta / width_m, 0.0, 1.0)
    return np.where(delta <= 0.0, 0.0, np.where(delta >= width_m, 1.0, 3.0 * s**2 - 2.0 * s**3))


def connector_force_r3(
    displacement_world: np.ndarray,
    relative_velocity_world: np.ndarray,
    params: ConnectorR3Params,
) -> ConnectorResult:
    d = np.asarray(displacement_world, dtype=float)
    v = np.asarray(relative_velocity_world, dtype=float)
    if d.shape != v.shape or d.shape[-1] != 2:
        raise ValueError("displacement and velocity must share [...,2] shape")
    numeric = (
        params.stiffness_npm,
        params.damping_nspm,
        params.free_play_m,
        params.smoothing_width_m,
        params.rated_force_n,
        params.ultimate_force_n,
    )
    if any((not np.isfinite(x) or x < 0.0) for x in numeric) or params.smoothing_width_m == 0.0:
        raise ValueError("finite nonnegative connector parameters and positive smoothing width required")
    if params.ultimate_force_n < params.rated_force_n:
        raise ValueError("ultimate force must not be below rated force")

    distance = np.linalg.norm(d, axis=-1)
    normal = d / np.maximum(distance[..., None], 1.0e-12)
    penetration = np.maximum(distance - params.free_play_m, 0.0)
    vn = np.sum(v * normal, axis=-1)
    g = smoothing_weight(penetration, params.smoothing_width_m)
    loading_speed = np.maximum(vn, 0.0)
    elastic = params.stiffness_npm * penetration
    damping = params.damping_nspm * g * loading_speed
    raw = elastic + damping
    applied = raw  # no cap: caller stops when the numerical ultimate boundary is reached
    fp = applied[..., None] * normal
    energy = 0.5 * params.stiffness_npm * penetration**2
    dissipation = params.damping_nspm * g * loading_speed**2
    return ConnectorResult(
        distance_m=distance,
        penetration_m=penetration,
        normal_world=normal,
        normal_speed_mps=vn,
        smoothing_weight=g,
        elastic_force_n=elastic,
        damping_force_n=damping,
        raw_force_n=raw,
        applied_force_n=applied,
        force_payload_world_n=fp,
        force_vehicle_world_n=-fp,
        elastic_energy_j=energy,
        damping_power_w=dissipation,
        contact_active_raw=penetration > 0.0,
        load_active_effective=raw >= 50.0,
        rated_force_exceeded=raw >= params.rated_force_n,
        ultimate_force_exceeded=raw >= params.ultimate_force_n,
    )


def params_from_dict(value: dict[str, Any]) -> ConnectorR3Params:
    return ConnectorR3Params(**{k: value[k] for k in ConnectorR3Params.__dataclass_fields__ if k in value})
