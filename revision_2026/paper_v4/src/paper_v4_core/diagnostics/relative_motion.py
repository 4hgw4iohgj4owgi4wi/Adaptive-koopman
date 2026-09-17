"""Payload-frame relative configuration diagnostics from recorded full states."""
from __future__ import annotations

import numpy as np

from ..plant.four_vehicle_common import connector_kinematics, rotation, split_state


def wrap(angle):
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


def extract(state, params, q_star, beta_star):
    vehicles, payload = split_state(np.asarray(state, dtype=float))
    rc = rotation(payload[2])
    g = (vehicles[:, :2] - payload[:2]) @ rc
    vehicle_velocity_world = np.vstack([rotation(v[2]) @ v[3:5] for v in vehicles])
    payload_velocity_world = rc @ payload[3:5]
    relative_velocity_body = (vehicle_velocity_world - payload_velocity_world) @ rc
    relative_velocity_body -= payload[5] * np.column_stack((-g[:, 1], g[:, 0]))
    kine = connector_kinematics(state, params)
    return {
        "g_body_m": g,
        "e_g_m": g - np.asarray(q_star, dtype=float),
        "e_beta_rad": wrap(vehicles[:, 2] - payload[2] - np.asarray(beta_star, dtype=float)),
        "relative_velocity_body_mps": relative_velocity_body,
        "connector_gap_m": np.asarray(kine["signed_gap_m"], dtype=float),
        "connector_normal_speed_mps": np.asarray(kine["normal_speed_mps"], dtype=float),
        "connector_relative_velocity_world_mps": np.asarray(kine["relative_velocity_world_mps"], dtype=float),
    }
