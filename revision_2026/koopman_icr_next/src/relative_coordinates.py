from __future__ import annotations

import numpy as np


G0_SLICE = slice(0, 3)
G1_SLICE = slice(3, 19)
G2_SLICE = slice(19, 31)
G3_SLICE = slice(31, 47)
RELATIVE_DIMENSION = 47
MIRROR_INDEX = np.asarray([1, 0, 3, 2], dtype=int)


def rotation(angle: float) -> np.ndarray:
    cosine = np.cos(angle)
    sine = np.sin(angle)
    return np.asarray([[cosine, -sine], [sine, cosine]])


def wrap_angle(angle: np.ndarray | float) -> np.ndarray | float:
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


def cross_z(rate: float, arm: np.ndarray) -> np.ndarray:
    return float(rate) * np.asarray([-arm[1], arm[0]])


def split_state(state30: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    state = np.asarray(state30)
    if state.shape != (30,):
        raise ValueError(f"state30 must have shape (30,), found {state.shape}")
    return state[:24].reshape(4, 6), state[24:30]


def encode_relative(state30: np.ndarray, params: object) -> dict[str, np.ndarray]:
    vehicles, payload = split_state(state30)
    payload_rotation = rotation(float(payload[2]))
    payload_velocity_world = payload_rotation @ payload[3:5]
    payload_anchors = np.asarray(params.payload_anchor_body_m, dtype=float)
    vehicle_anchors = np.asarray(params.vehicle_anchor_body_m, dtype=float)
    if payload_anchors.shape != (4, 2) or vehicle_anchors.shape != (4, 2):
        raise ValueError("connector anchors must both have shape (4, 2)")

    rho = np.empty((4, 2), dtype=float)
    heading_sincos = np.empty((4, 2), dtype=float)
    relative_velocity = np.empty((4, 2), dtype=float)
    relative_yaw_rate = np.empty(4, dtype=float)
    rho_dot = np.empty((4, 2), dtype=float)
    displacement_body = np.empty((4, 2), dtype=float)
    anchor_relative_velocity_body = np.empty((4, 2), dtype=float)

    payload_anchor_position_world = np.empty((4, 2), dtype=float)
    payload_anchor_velocity_world = np.empty((4, 2), dtype=float)
    vehicle_anchor_position_world = np.empty((4, 2), dtype=float)
    vehicle_anchor_velocity_world = np.empty((4, 2), dtype=float)
    for index, vehicle in enumerate(vehicles):
        vehicle_rotation = rotation(float(vehicle[2]))
        vehicle_velocity_world = vehicle_rotation @ vehicle[3:5]
        rho[index] = payload_rotation.T @ (vehicle[:2] - payload[:2])
        delta_heading = float(wrap_angle(vehicle[2] - payload[2]))
        heading_sincos[index] = (np.sin(delta_heading), np.cos(delta_heading))
        relative_velocity[index] = payload_rotation.T @ (
            vehicle_velocity_world - payload_velocity_world
        )
        relative_yaw_rate[index] = vehicle[5] - payload[5]
        rho_dot[index] = relative_velocity[index] - cross_z(payload[5], rho[index])

        payload_arm_world = payload_rotation @ payload_anchors[index]
        vehicle_arm_world = vehicle_rotation @ vehicle_anchors[index]
        payload_anchor_position_world[index] = payload[:2] + payload_arm_world
        vehicle_anchor_position_world[index] = vehicle[:2] + vehicle_arm_world
        payload_anchor_velocity_world[index] = payload_velocity_world + cross_z(
            payload[5], payload_arm_world
        )
        vehicle_anchor_velocity_world[index] = vehicle_velocity_world + cross_z(
            vehicle[5], vehicle_arm_world
        )
        displacement_body[index] = payload_rotation.T @ (
            vehicle_anchor_position_world[index] - payload_anchor_position_world[index]
        )
        anchor_relative_velocity_body[index] = payload_rotation.T @ (
            vehicle_anchor_velocity_world[index] - payload_anchor_velocity_world[index]
        )

    g0 = payload[3:6].astype(float, copy=True)
    g1 = np.c_[rho, heading_sincos].ravel()
    g2 = np.c_[relative_velocity, relative_yaw_rate].ravel()
    g3 = np.c_[displacement_body, anchor_relative_velocity_body].ravel()
    relative = np.r_[g0, g1, g2, g3]
    if relative.shape != (RELATIVE_DIMENSION,):
        raise AssertionError(relative.shape)
    return {
        "relative_state47": relative,
        "payload_pose_context3": payload[:3].astype(float, copy=True),
        "rho_payload_m": rho,
        "heading_sincos": heading_sincos,
        "relative_center_velocity_payload_mps": relative_velocity,
        "rho_dot_payload_mps": rho_dot,
        "relative_yaw_rate_radps": relative_yaw_rate,
        "connector_displacement_payload_m": displacement_body,
        "anchor_relative_velocity_payload_mps": anchor_relative_velocity_body,
        "payload_anchor_position_world_m": payload_anchor_position_world,
        "vehicle_anchor_position_world_m": vehicle_anchor_position_world,
        "payload_anchor_velocity_world_mps": payload_anchor_velocity_world,
        "vehicle_anchor_velocity_world_mps": vehicle_anchor_velocity_world,
    }


def decode_absolute(relative_state47: np.ndarray, payload_pose_context3: np.ndarray) -> np.ndarray:
    relative = np.asarray(relative_state47, dtype=float)
    context = np.asarray(payload_pose_context3, dtype=float)
    if relative.shape != (RELATIVE_DIMENSION,):
        raise ValueError(f"relative state must have shape ({RELATIVE_DIMENSION},)")
    if context.shape != (3,):
        raise ValueError("payload pose context must have shape (3,)")
    payload = np.r_[context, relative[G0_SLICE]]
    payload_rotation = rotation(float(payload[2]))
    payload_velocity_world = payload_rotation @ payload[3:5]
    g1 = relative[G1_SLICE].reshape(4, 4)
    g2 = relative[G2_SLICE].reshape(4, 3)
    vehicles = np.empty((4, 6), dtype=float)
    for index in range(4):
        rho = g1[index, :2]
        sine, cosine = g1[index, 2:4]
        delta_heading = np.arctan2(sine, cosine)
        yaw = float(wrap_angle(payload[2] + delta_heading))
        position_world = payload[:2] + payload_rotation @ rho
        velocity_world = payload_velocity_world + payload_rotation @ g2[index, :2]
        velocity_body = rotation(yaw).T @ velocity_world
        vehicles[index] = np.r_[
            position_world,
            yaw,
            velocity_body,
            payload[5] + g2[index, 2],
        ]
    return np.r_[vehicles.ravel(), payload]


def geometry_consistency(relative_state47: np.ndarray, decoded_state30: np.ndarray, params: object) -> dict:
    encoded = encode_relative(decoded_state30, params)
    relative = np.asarray(relative_state47, dtype=float)
    return {
        "g1_max_abs": float(np.max(np.abs(encoded["relative_state47"][G1_SLICE] - relative[G1_SLICE]))),
        "g2_max_abs": float(np.max(np.abs(encoded["relative_state47"][G2_SLICE] - relative[G2_SLICE]))),
        "g3_max_abs": float(np.max(np.abs(encoded["relative_state47"][G3_SLICE] - relative[G3_SLICE]))),
    }

