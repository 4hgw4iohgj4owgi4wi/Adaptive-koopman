from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .connector_adapter import DELTA_S_M, VectorConnector
from .connector_r3 import ConnectorR3Params
from .internal_force import decompose_planar_point_forces, diagonal_tension_modes, legacy_q_fr_q_lr, tension_load_proxies
from .load_transfer import config_from_model, solve_payload_support_loads


@dataclass(frozen=True)
class VehicleParams:
    mass_kg: float = 1200.0
    yaw_inertia_kgm2: float = 1800.0
    lf_m: float = 1.2
    lr_m: float = 1.3
    cf_nprad: float = 55000.0
    cr_nprad: float = 60000.0
    mu: float = 0.9
    gravity_mps2: float = 9.81


@dataclass(frozen=True)
class PayloadParams:
    mass_kg: float = 2000.0
    length_m: float = 5.0
    width_m: float = 2.0
    cog_height_m: float = 1.2
    gravity_mps2: float = 9.81

    @property
    def yaw_inertia_kgm2(self) -> float:
        return self.mass_kg * (self.length_m**2 + self.width_m**2) / 12.0


@dataclass(frozen=True)
class ModelParams:
    vehicle: VehicleParams = VehicleParams()
    payload: PayloadParams = PayloadParams()
    connector: ConnectorR3Params = ConnectorR3Params(smoothing_width_m=DELTA_S_M)
    vehicle_anchor_body_m: tuple = ((-0.4, -0.25), (-0.4, 0.25), (0.4, -0.25), (0.4, 0.25))

    @property
    def payload_anchor_body_m(self) -> np.ndarray:
        return np.asarray([
            [0.5 * self.payload.length_m, 0.5 * self.payload.width_m],
            [0.5 * self.payload.length_m, -0.5 * self.payload.width_m],
            [-0.5 * self.payload.length_m, 0.5 * self.payload.width_m],
            [-0.5 * self.payload.length_m, -0.5 * self.payload.width_m],
        ])


def rotation(yaw: float) -> np.ndarray:
    c, s = np.cos(yaw), np.sin(yaw)
    return np.asarray([[c, -s], [s, c]])


def cross_z(rate: float, vector: np.ndarray) -> np.ndarray:
    return rate * np.asarray([-vector[1], vector[0]])


def cross2(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def split_state(state: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    state = np.asarray(state, dtype=float)
    if state.shape != (30,):
        raise ValueError("state shape must be 30")
    return state[:24].reshape(4, 6), state[24:]


def initialize_state(params: ModelParams, speed_mps: float = 2.0) -> np.ndarray:
    payload = np.asarray([0.0, 0.0, 0.0, speed_mps, 0.0, 0.0], dtype=float)
    vehicles = np.zeros((4, 6), dtype=float)
    for index in range(4):
        vehicles[index, :2] = params.payload_anchor_body_m[index] - np.asarray(params.vehicle_anchor_body_m[index])
        vehicles[index, 3] = speed_mps
    return np.r_[vehicles.ravel(), payload]


def connector_kinematics(state: np.ndarray, params: ModelParams) -> dict:
    vehicles, payload = split_state(state)
    payload_rotation = rotation(payload[2])
    payload_anchor = np.empty((4, 2))
    payload_anchor_velocity = np.empty((4, 2))
    vehicle_anchor = np.empty((4, 2))
    vehicle_anchor_velocity = np.empty((4, 2))
    payload_cog_velocity_world = payload_rotation @ payload[3:5]
    for index in range(4):
        payload_arm = payload_rotation @ params.payload_anchor_body_m[index]
        payload_anchor[index] = payload[:2] + payload_arm
        payload_anchor_velocity[index] = payload_cog_velocity_world + cross_z(payload[5], payload_arm)
        vehicle_rotation = rotation(vehicles[index, 2])
        vehicle_arm = vehicle_rotation @ np.asarray(params.vehicle_anchor_body_m[index])
        vehicle_anchor[index] = vehicles[index, :2] + vehicle_arm
        vehicle_anchor_velocity[index] = vehicle_rotation @ vehicles[index, 3:5] + cross_z(vehicles[index, 5], vehicle_arm)
    displacement = vehicle_anchor - payload_anchor
    relative_velocity = vehicle_anchor_velocity - payload_anchor_velocity
    distance = np.linalg.norm(displacement, axis=1)
    normal = displacement / np.maximum(distance[:, None], 1e-12)
    return {
        "payload_anchor_world_m": payload_anchor,
        "vehicle_anchor_world_m": vehicle_anchor,
        "displacement_world_m": displacement,
        "relative_velocity_world_mps": relative_velocity,
        "signed_gap_m": distance - params.connector.free_play_m,
        "normal_world": normal,
        "normal_speed_mps": np.sum(relative_velocity * normal, axis=1),
    }


def signed_connector_gaps(state: np.ndarray, params: ModelParams) -> np.ndarray:
    return connector_kinematics(state, params)["signed_gap_m"]


def connector_event_surfaces(state: np.ndarray, params: ModelParams) -> np.ndarray:
    gaps = signed_connector_gaps(state, params)
    return np.column_stack([gaps, gaps - params.connector.smoothing_width_m])


def connector_diagnostics(state: np.ndarray, params: ModelParams, law: str) -> dict:
    vehicles, payload = split_state(state)
    kinematics = connector_kinematics(state, params)
    result = VectorConnector(law, params.connector).evaluate(
        kinematics["displacement_world_m"], kinematics["relative_velocity_world_mps"]
    )
    payload_rotation = rotation(payload[2])
    payload_force_body = result["force_payload_world_n"] @ payload_rotation
    vehicle_force_body = np.vstack([
        result["force_vehicle_world_n"][index] @ rotation(vehicles[index, 2]) for index in range(4)
    ])
    payload_moment = np.asarray([
        cross2(payload_rotation @ params.payload_anchor_body_m[index], result["force_payload_world_n"][index])
        for index in range(4)
    ])
    vehicle_moment = np.asarray([
        cross2(rotation(vehicles[index, 2]) @ np.asarray(params.vehicle_anchor_body_m[index]), result["force_vehicle_world_n"][index])
        for index in range(4)
    ])
    decomposition = decompose_planar_point_forces(payload_force_body, params.payload_anchor_body_m)
    common_origin_moment = np.asarray([cross2(kinematics["payload_anchor_world_m"][i],result["force_payload_world_n"][i])+cross2(kinematics["vehicle_anchor_world_m"][i],result["force_vehicle_world_n"][i]) for i in range(4)])
    force_angle=np.arctan2(payload_force_body[:,1],payload_force_body[:,0]);force_active=result["applied_force_n"]>=50.0
    tension=tension_load_proxies(payload_force_body)
    return {
        **kinematics, **result,
        "force_payload_body_n": payload_force_body,
        "force_vehicle_body_n": vehicle_force_body,
        "force_norm_n": result["applied_force_n"],
        "payload_moment_nm": payload_moment,
        "payload_moment_total_nm": float(np.sum(payload_moment)),
        "vehicle_moment_nm": vehicle_moment,
        "action_reaction_residual_n": result["force_payload_world_n"] + result["force_vehicle_world_n"],
        "internal_force_vector_n": decomposition["internal_force_vector"],
        "internal_force_norm_n": decomposition["internal_force_norm_n"],
        "motion_force_vector_n": decomposition["motion_force_vector"],
        "generalized_payload_wrench": decomposition["generalized_payload_wrench"],
        "grasp_rank": decomposition["grasp_rank"],
        "grasp_condition": decomposition["grasp_condition"],
        "internal_null_residual": decomposition["null_residual"],
        "q": legacy_q_fr_q_lr(payload_force_body),
        "diagonal_tension_modes_n": diagonal_tension_modes(payload_force_body),
        "common_origin_internal_moment_residual_nm": common_origin_moment,
        "force_direction_body_rad": np.where(force_active,force_angle,0.0),
        "force_active_mask": force_active,
        "force_direction_status": np.where(force_active,"ACTIVE","INACTIVE"),
        **tension,
    }


def tire_force(state: np.ndarray, acceleration: float, steering: float, support_n: float, params: VehicleParams) -> dict:
    _, _, _, vx, vy, yaw_rate = state
    speed = max(abs(vx), 0.5)
    alpha_front = steering - np.arctan2(vy + params.lf_m * yaw_rate, speed)
    alpha_rear = -np.arctan2(vy - params.lr_m * yaw_rate, speed)
    fy_front = params.cf_nprad * alpha_front
    fy_rear = params.cr_nprad * alpha_rear
    fx = (params.mass_kg + support_n / params.gravity_mps2) * acceleration
    fy = fy_front + fy_rear
    moment = params.lf_m * fy_front - params.lr_m * fy_rear
    cap = params.mu * (params.mass_kg * params.gravity_mps2 + max(support_n, 0.0))
    utilization = np.hypot(fx, fy) / max(cap, 1e-12)
    scale = min(1.0, 1.0 / max(utilization, 1e-12))
    return {"force_body_n": np.asarray([fx * scale, fy * scale]), "yaw_moment_nm": moment * scale,
            "raw_force_body_n":np.asarray([fx,fy]),"raw_yaw_moment_nm":moment,
            "raw_utilization":utilization,"applied_utilization":utilization*scale,"scale":scale,"saturated":bool(scale<1.0)}


def assemble_derivative(
    state: np.ndarray,
    controls: np.ndarray,
    params: ModelParams,
    law: str,
    include_connector: bool = True,
    load_transfer_enabled: bool = False,
) -> tuple[np.ndarray, dict]:
    """Assemble connector -> payload acceleration -> support load -> tire dynamics."""

    vehicles, payload = split_state(state)
    controls = np.asarray(controls, dtype=float).reshape(4, 2)
    connector = connector_diagnostics(state, params, law)
    payload_rotation = rotation(payload[2])
    payload_force_world = (
        np.sum(connector["force_payload_world_n"], axis=0)
        if include_connector
        else np.zeros(2)
    )
    payload_accel_body = payload_rotation.T @ (
        payload_force_world / params.payload.mass_kg
    )
    support = solve_payload_support_loads(
        payload_accel_body,
        config_from_model(params),
        enabled=load_transfer_enabled,
    )
    support_loads = np.asarray(support["payload_support_load_n"], dtype=float)
    total_normal_loads = (
        params.vehicle.mass_kg * params.vehicle.gravity_mps2 + support_loads
    )

    vehicle_derivative = np.empty_like(vehicles)
    tires = []
    connector_dx = np.zeros(30)
    for index in range(4):
        tire = tire_force(
            vehicles[index],
            controls[index, 0],
            controls[index, 1],
            float(support_loads[index]),
            params.vehicle,
        )
        tires.append(tire)
        connector_force = (
            connector["force_vehicle_body_n"][index]
            if include_connector
            else np.zeros(2)
        )
        connector_moment = (
            connector["vehicle_moment_nm"][index] if include_connector else 0.0
        )
        _, _, yaw, vx, vy, yaw_rate = vehicles[index]
        velocity_world = rotation(yaw) @ np.asarray([vx, vy])
        vehicle_derivative[index] = [
            velocity_world[0],
            velocity_world[1],
            yaw_rate,
            (tire["force_body_n"][0] + connector_force[0]) / params.vehicle.mass_kg
            + yaw_rate * vy,
            (tire["force_body_n"][1] + connector_force[1]) / params.vehicle.mass_kg
            - yaw_rate * vx,
            (tire["yaw_moment_nm"] + connector_moment)
            / params.vehicle.yaw_inertia_kgm2,
        ]
        base = 6 * index
        connector_dx[base + 3] = (
            connector["force_vehicle_body_n"][index, 0] / params.vehicle.mass_kg
        )
        connector_dx[base + 4] = (
            connector["force_vehicle_body_n"][index, 1] / params.vehicle.mass_kg
        )
        connector_dx[base + 5] = (
            connector["vehicle_moment_nm"][index]
            / params.vehicle.yaw_inertia_kgm2
        )

    vx, vy, yaw_rate = payload[3:6]
    velocity_world = payload_rotation @ payload[3:5]
    payload_moment = connector["payload_moment_total_nm"] if include_connector else 0.0
    payload_derivative = np.asarray(
        [
            velocity_world[0],
            velocity_world[1],
            yaw_rate,
            payload_accel_body[0] + yaw_rate * vy,
            payload_accel_body[1] - yaw_rate * vx,
            payload_moment / params.payload.yaw_inertia_kgm2,
        ]
    )
    full = np.r_[vehicle_derivative.ravel(), payload_derivative]
    connector_dx[27:29] = payload_accel_body
    connector_dx[29] = (
        connector["payload_moment_total_nm"] / params.payload.yaw_inertia_kgm2
    )
    return full, {
        "connectors": connector,
        "tire": tires,
        "payload_accel_body_mps2": payload_accel_body,
        "payload_support_load_n": support_loads,
        "vehicle_total_normal_load_n": total_normal_loads,
        "support_constraint_target": np.asarray(support["constraint_target"], dtype=float),
        "support_constraint_residual": np.asarray(support["constraint_residual"], dtype=float),
        "support_constraint_relative_residual": np.asarray(
            support["constraint_relative_residual"], dtype=float
        ),
        "minimum_support_load_n": float(support["minimum_support_load_n"]),
        "load_transfer_enabled": bool(load_transfer_enabled),
        "connector_derivative": connector_dx,
        "include_connector": include_connector,
    }


def system_derivative(
    state: np.ndarray,
    controls: np.ndarray,
    params: ModelParams,
    law: str,
    load_transfer_enabled: bool = False,
) -> tuple[np.ndarray, dict]:
    return assemble_derivative(
        state,
        controls,
        params,
        law,
        True,
        load_transfer_enabled=load_transfer_enabled,
    )


def rk4_step(
    state: np.ndarray,
    controls: np.ndarray,
    dt: float,
    params: ModelParams,
    law: str,
    load_transfer_enabled: bool = False,
) -> np.ndarray:
    def rhs(value: np.ndarray) -> np.ndarray:
        return system_derivative(
            value,
            controls,
            params,
            law,
            load_transfer_enabled=load_transfer_enabled,
        )[0]
    k1 = rhs(state); k2 = rhs(state + 0.5 * dt * k1); k3 = rhs(state + 0.5 * dt * k2); k4 = rhs(state + dt * k3)
    output = state + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    if not np.all(np.isfinite(output)):
        raise FloatingPointError("nonfinite four-vehicle state")
    return output

