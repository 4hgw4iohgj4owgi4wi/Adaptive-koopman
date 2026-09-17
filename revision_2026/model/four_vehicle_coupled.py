"""Planar four-vehicle, four-connector and payload coupled dynamics."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


NAMES = ("FL", "FR", "RL", "RR")


@dataclass(frozen=True)
class VehicleParams:
    mass_kg: float = 1200.0
    yaw_inertia_kgm2: float = 1800.0
    lf_m: float = 1.2
    lr_m: float = 1.3
    cf_nprad: float = 55000.0
    cr_nprad: float = 60000.0
    mu: float = 0.90
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
class ConnectorParams:
    stiffness_npm: float = 30000.0
    damping_nspm: float = 3500.0
    free_play_m: float = 0.002
    rated_force_n: float = 12000.0
    ultimate_force_n: float = 15000.0


@dataclass(frozen=True)
class ModelParams:
    vehicle: VehicleParams = VehicleParams()
    payload: PayloadParams = PayloadParams()
    connector: ConnectorParams = ConnectorParams()
    vehicle_anchor_body_m: tuple = (
        (-0.40, -0.25),
        (-0.40, +0.25),
        (+0.40, -0.25),
        (+0.40, +0.25),
    )

    @property
    def payload_anchor_body_m(self) -> np.ndarray:
        p = self.payload
        return np.array(
            [
                [+0.5 * p.length_m, +0.5 * p.width_m],
                [+0.5 * p.length_m, -0.5 * p.width_m],
                [-0.5 * p.length_m, +0.5 * p.width_m],
                [-0.5 * p.length_m, -0.5 * p.width_m],
            ],
            dtype=float,
        )


def rotation(yaw: float) -> np.ndarray:
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([[c, -s], [s, c]], dtype=float)


def cross_z(rate: float, vector: np.ndarray) -> np.ndarray:
    return float(rate) * np.array([-vector[1], vector[0]], dtype=float)


def cross2(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def initialize_state(params: ModelParams, speed_mps: float = 2.0) -> np.ndarray:
    """Return joint state [4x vehicle six-state, payload six-state]."""
    payload = np.array([0.0, 0.0, 0.0, speed_mps, 0.0, 0.0], dtype=float)
    vehicles = np.zeros((4, 6), dtype=float)
    anchors_l = params.payload_anchor_body_m
    anchors_v = np.asarray(params.vehicle_anchor_body_m, dtype=float)
    for i in range(4):
        vehicles[i, :2] = anchors_l[i] - anchors_v[i]
        vehicles[i, 2] = 0.0
        vehicles[i, 3] = speed_mps
    return np.concatenate([vehicles.reshape(-1), payload])


def split_state(state: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(state, dtype=float)
    if values.shape != (30,):
        raise ValueError(f"joint state must have shape (30,), got {values.shape}")
    return values[:24].reshape(4, 6), values[24:]


def connector_diagnostics(state: np.ndarray, params: ModelParams) -> dict[str, np.ndarray]:
    vehicles, payload = split_state(state)
    anchors_l = params.payload_anchor_body_m
    anchors_v = np.asarray(params.vehicle_anchor_body_m, dtype=float)
    rp = rotation(payload[2])
    p_center = payload[:2]
    v_center = rp @ payload[3:5]
    p_anchor = np.empty((4, 2))
    v_anchor = np.empty((4, 2))
    vehicle_anchor = np.empty((4, 2))
    vehicle_anchor_v = np.empty((4, 2))
    for i in range(4):
        arm_l = rp @ anchors_l[i]
        p_anchor[i] = p_center + arm_l
        v_anchor[i] = v_center + cross_z(payload[5], arm_l)
        rv = rotation(vehicles[i, 2])
        arm_v = rv @ anchors_v[i]
        vehicle_anchor[i] = vehicles[i, :2] + arm_v
        vehicle_anchor_v[i] = rv @ vehicles[i, 3:5] + cross_z(vehicles[i, 5], arm_v)

    displacement = vehicle_anchor - p_anchor
    relative_velocity = vehicle_anchor_v - v_anchor
    norm = np.linalg.norm(displacement, axis=1)
    force_payload_world = np.zeros((4, 2), dtype=float)
    penetration = np.maximum(norm - params.connector.free_play_m, 0.0)
    normal_speed = np.zeros(4, dtype=float)
    damping_power = np.zeros(4, dtype=float)
    for i in range(4):
        if penetration[i] <= 0.0:
            continue
        normal = displacement[i] / max(norm[i], 1.0e-12)
        normal_speed[i] = float(relative_velocity[i] @ normal)
        loading_speed = max(normal_speed[i], 0.0)
        magnitude = (
            params.connector.stiffness_npm * penetration[i]
            + params.connector.damping_nspm * loading_speed
        )
        force_payload_world[i] = magnitude * normal
        damping_power[i] = params.connector.damping_nspm * loading_speed**2

    force_payload_body = force_payload_world @ rp
    force_vehicle_world = -force_payload_world
    force_vehicle_body = np.vstack(
        [force_vehicle_world[i] @ rotation(vehicles[i, 2]) for i in range(4)]
    )
    force_norm = np.linalg.norm(force_payload_world, axis=1)
    payload_moment = np.array(
        [cross2(rp @ anchors_l[i], force_payload_world[i]) for i in range(4)]
    )
    vehicle_moment = np.array(
        [cross2(rotation(vehicles[i, 2]) @ anchors_v[i], force_vehicle_world[i]) for i in range(4)]
    )
    return {
        "displacement_world_m": displacement,
        "penetration_m": penetration,
        "normal_speed_mps": normal_speed,
        "damping_power_w": damping_power,
        "force_payload_world_n": force_payload_world,
        "force_payload_body_n": force_payload_body,
        "force_vehicle_world_n": force_vehicle_world,
        "force_vehicle_body_n": force_vehicle_body,
        "force_norm_n": force_norm,
        "payload_moment_nm": payload_moment,
        "vehicle_moment_nm": vehicle_moment,
        "rated_exceeded": force_norm >= params.connector.rated_force_n,
        "ultimate_exceeded": force_norm >= params.connector.ultimate_force_n,
    }


def tire_force(state: np.ndarray, acceleration: float, steering: float, support_fz: float, params: VehicleParams) -> dict:
    _, _, _, vx, vy, yaw_rate = state
    speed = max(abs(float(vx)), 0.5)
    alpha_f = float(steering) - np.arctan2(vy + params.lf_m * yaw_rate, speed)
    alpha_r = -np.arctan2(vy - params.lr_m * yaw_rate, speed)
    fy_f = params.cf_nprad * alpha_f
    fy_r = params.cr_nprad * alpha_r
    fx = (params.mass_kg + support_fz / params.gravity_mps2) * float(acceleration)
    fy = fy_f + fy_r
    mz = params.lf_m * fy_f - params.lr_m * fy_r
    capacity = params.mu * (params.mass_kg * params.gravity_mps2 + max(float(support_fz), 0.0))
    utilization_raw = np.hypot(fx, fy) / max(capacity, 1.0e-12)
    scale = min(1.0, 1.0 / max(utilization_raw, 1.0e-12))
    return {
        "force_body_n": np.array([fx * scale, fy * scale]),
        "yaw_moment_nm": mz * scale,
        "utilization": float(utilization_raw * scale),
        "raw_utilization": float(utilization_raw),
    }


def system_derivative(state: np.ndarray, controls: np.ndarray, params: ModelParams) -> tuple[np.ndarray, dict]:
    vehicles, payload = split_state(state)
    controls = np.asarray(controls, dtype=float)
    if controls.shape != (4, 2):
        raise ValueError("controls must be [acceleration, steering] with shape (4,2)")
    conn = connector_diagnostics(state, params)
    nominal_support = params.payload.mass_kg * params.payload.gravity_mps2 / 4.0
    derivatives_v = np.empty_like(vehicles)
    tire = []
    for i in range(4):
        td = tire_force(vehicles[i], controls[i, 0], controls[i, 1], nominal_support, params.vehicle)
        tire.append(td)
        force = td["force_body_n"] + conn["force_vehicle_body_n"][i]
        x, y, yaw, vx, vy, r = vehicles[i]
        rv = rotation(yaw)
        world_velocity = rv @ np.array([vx, vy])
        derivatives_v[i] = np.array(
            [
                world_velocity[0],
                world_velocity[1],
                r,
                force[0] / params.vehicle.mass_kg + r * vy,
                force[1] / params.vehicle.mass_kg - r * vx,
                (td["yaw_moment_nm"] + conn["vehicle_moment_nm"][i]) / params.vehicle.yaw_inertia_kgm2,
            ]
        )

    rp = rotation(payload[2])
    force_payload_world = np.sum(conn["force_payload_world_n"], axis=0)
    accel_payload_world = force_payload_world / params.payload.mass_kg
    accel_payload_body = rp.T @ accel_payload_world
    vx_l, vy_l, r_l = payload[3], payload[4], payload[5]
    world_velocity_l = rp @ np.array([vx_l, vy_l])
    derivative_l = np.array(
        [
            world_velocity_l[0],
            world_velocity_l[1],
            r_l,
            accel_payload_body[0] + r_l * vy_l,
            accel_payload_body[1] - r_l * vx_l,
            np.sum(conn["payload_moment_nm"]) / params.payload.yaw_inertia_kgm2,
        ]
    )
    return np.concatenate([derivatives_v.reshape(-1), derivative_l]), {
        "connectors": conn,
        "tire": tire,
        "payload_accel_body_mps2": accel_payload_body,
    }


def rk4_step(state: np.ndarray, controls: np.ndarray, dt: float, params: ModelParams) -> np.ndarray:
    def rhs(values: np.ndarray) -> np.ndarray:
        return system_derivative(values, controls, params)[0]
    k1 = rhs(state)
    k2 = rhs(state + 0.5 * dt * k1)
    k3 = rhs(state + 0.5 * dt * k2)
    k4 = rhs(state + dt * k3)
    output = state + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    if not np.all(np.isfinite(output)):
        raise FloatingPointError("non-finite coupled state")
    return output


def support_loads(payload_accel_body: np.ndarray, params: ModelParams) -> np.ndarray:
    """Quasi-static four-point Fz auxiliary; not a third planar connector force."""
    p = params.payload
    static = p.mass_kg * p.gravity_mps2 / 4.0
    d_long = p.mass_kg * payload_accel_body[0] * p.cog_height_m / max(2.0 * p.length_m, 1.0e-9)
    d_lat = p.mass_kg * payload_accel_body[1] * p.cog_height_m / max(2.0 * p.width_m, 1.0e-9)
    return np.array(
        [static - d_long - d_lat, static - d_long + d_lat, static + d_long - d_lat, static + d_long + d_lat]
    )


def aggregate_diagnostics(state: np.ndarray, controls: np.ndarray, params: ModelParams) -> dict:
    vehicles, payload = split_state(state)
    _, aux = system_derivative(state, controls, params)
    conn = aux["connectors"]
    masses = np.array([params.vehicle.mass_kg] * 4 + [params.payload.mass_kg])
    positions = np.vstack([vehicles[:, :2], payload[:2]])
    velocities = np.vstack(
        [rotation(vehicles[i, 2]) @ vehicles[i, 3:5] for i in range(4)]
        + [rotation(payload[2]) @ payload[3:5]]
    )
    com = np.sum(masses[:, None] * positions, axis=0) / np.sum(masses)
    vcom = np.sum(masses[:, None] * velocities, axis=0) / np.sum(masses)
    inertias = np.array([params.vehicle.yaw_inertia_kgm2] * 4 + [params.payload.yaw_inertia_kgm2])
    rates = np.r_[vehicles[:, 5], payload[5]]
    arms = positions - com
    inertia_system = np.sum(inertias + masses * np.sum(arms**2, axis=1))
    angular_momentum = np.sum(inertias * rates) + sum(
        masses[i] * cross2(arms[i], velocities[i] - vcom) for i in range(5)
    )
    fbody = conn["force_payload_body_n"]
    q_fr = 0.5 * ((fbody[0, 0] + fbody[1, 0]) - (fbody[2, 0] + fbody[3, 0]))
    q_lr = 0.5 * ((fbody[0, 1] + fbody[2, 1]) - (fbody[1, 1] + fbody[3, 1]))
    internal_force_residual = np.sum(conn["force_payload_world_n"] + conn["force_vehicle_world_n"], axis=0)
    return {
        "connectors": conn,
        "payload_accel_body_mps2": aux["payload_accel_body_mps2"],
        "support_fz_n": support_loads(aux["payload_accel_body_mps2"], params),
        "system_com_m": com,
        "system_yaw_rate_radps": float(angular_momentum / max(inertia_system, 1.0e-12)),
        "q_front_rear_n": float(q_fr),
        "q_left_right_n": float(q_lr),
        "internal_force_residual_n": internal_force_residual,
        "tire_utilization": np.array([item["utilization"] for item in aux["tire"]]),
    }
