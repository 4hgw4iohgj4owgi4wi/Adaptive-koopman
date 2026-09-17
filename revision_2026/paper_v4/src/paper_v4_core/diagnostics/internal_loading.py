"""Separate payload wrench, grasp-nullspace load and connector pair power."""
from __future__ import annotations

import numpy as np

from ..plant.four_vehicle_common import rotation
from ..plant.internal_force import decompose_planar_point_forces, tension_load_proxies


def decompose(force_payload_body_n, anchor_body_m, payload_yaw_rad, connector_relative_velocity_world_mps):
    force_body = np.asarray(force_payload_body_n, dtype=float).reshape(4, 2)
    result = decompose_planar_point_forces(force_body, anchor_body_m)
    force_world = force_body @ rotation(float(payload_yaw_rad)).T
    relative_velocity = np.asarray(connector_relative_velocity_world_mps, dtype=float).reshape(4, 2)
    pair_power = -np.sum(force_world * relative_velocity, axis=1)
    return {
        "wrench_n_nm": result["generalized_payload_wrench"],
        "motion_force_vector_n": result["motion_force_vector"],
        "internal_force_vector_n": result["internal_force_vector"],
        "internal_force_norm_n": result["internal_force_norm_n"],
        "null_residual_n_nm": result["null_residual"],
        "connector_pair_power_w": pair_power,
        **tension_load_proxies(force_body),
    }
