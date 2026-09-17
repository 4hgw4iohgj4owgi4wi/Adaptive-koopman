"""Adapter between TF14 Frenet-state controllers and the coupled physical plant.

This module intentionally contains no controller logic.  It maps the controller's
array-level command through the common-ICR allocator and advances the same
four-vehicle/four-connector/payload plant used by the model acceptance tests.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

from four_vehicle_coupled import (
    ModelParams,
    aggregate_diagnostics,
    rk4_step,
    rotation,
    split_state,
)
from steering_allocator import AllocationConfig, allocate_controls, wrap


@dataclass(frozen=True)
class CoupledAdapterConfig:
    substep_s: float = 0.002
    # Split the legacy equivalent steer into a 4WS pair while preserving its
    # small-angle curvature: delta_f-delta_r ~= delta_equivalent.
    virtual_front_scale: float = 2.0 / 3.0
    virtual_rear_ratio: float = -0.5
    heading_gain: float = 2.0
    speed_gain: float = 0.8
    max_vehicle_steering_deg: float = 15.0
    max_zero_sum_accel_mps2: float = 0.8


class FrenetMap:
    """Numerical road centreline reconstructed from s and curvature samples."""

    def __init__(self, s_ref: np.ndarray, curvature_ref: np.ndarray):
        s_raw = np.asarray(s_ref, dtype=float).reshape(-1)
        k_raw = np.asarray(curvature_ref, dtype=float).reshape(-1)
        if s_raw.size < 2 or k_raw.size != s_raw.size:
            raise ValueError("s_ref and curvature_ref must be equal-length arrays with at least two samples")
        finite = np.isfinite(s_raw) & np.isfinite(k_raw)
        s_raw, k_raw = s_raw[finite], k_raw[finite]
        order = np.argsort(s_raw, kind="stable")
        s_raw, k_raw = s_raw[order], k_raw[order]
        keep = np.r_[True, np.diff(s_raw) > 1.0e-10]
        s_unique = s_raw[keep]
        k_unique = k_raw[keep]
        if s_unique.size < 2:
            raise ValueError("reference progress must contain at least two distinct values")
        # Payload references end at the payload centre, while front/rear carrier
        # centres legitimately lie beyond those endpoints.  Straight padding
        # prevents endpoint clipping from becoming a false completion failure.
        pad_m = 20.0
        self.s = np.r_[s_unique[0] - pad_m, s_unique, s_unique[-1] + pad_m]
        self.kappa = np.r_[0.0, k_unique, 0.0]

        ds = np.diff(self.s)
        heading = np.zeros_like(self.s)
        heading[1:] = np.cumsum(0.5 * (self.kappa[:-1] + self.kappa[1:]) * ds)
        heading_mid = 0.5 * (heading[:-1] + heading[1:])
        x = np.zeros_like(self.s)
        y = np.zeros_like(self.s)
        x[1:] = np.cumsum(np.cos(heading_mid) * ds)
        y[1:] = np.cumsum(np.sin(heading_mid) * ds)
        self.heading = heading
        self.x = x
        self.y = y

    def frame(self, s_query: float) -> tuple[np.ndarray, float, float]:
        sq = float(np.clip(s_query, self.s[0], self.s[-1]))
        centre = np.array(
            [np.interp(sq, self.s, self.x), np.interp(sq, self.s, self.y)], dtype=float
        )
        heading = float(np.interp(sq, self.s, self.heading))
        kappa = float(np.interp(sq, self.s, self.kappa))
        return centre, heading, kappa

    def to_world(self, frenet_state: np.ndarray) -> np.ndarray:
        s, ey, epsi, vx, vy, yaw_rate = np.asarray(frenet_state, dtype=float)
        centre, heading, _ = self.frame(float(s))
        normal = np.array([-math.sin(heading), math.cos(heading)], dtype=float)
        pos = centre + float(ey) * normal
        return np.array([pos[0], pos[1], heading + float(epsi), vx, vy, yaw_rate], dtype=float)

    def to_frenet(self, world_state: np.ndarray) -> np.ndarray:
        state = np.asarray(world_state, dtype=float)
        pos = state[:2]
        dist2 = (self.x - pos[0]) ** 2 + (self.y - pos[1]) ** 2
        idx = int(np.argmin(dist2))
        heading0 = float(self.heading[idx])
        tangent = np.array([math.cos(heading0), math.sin(heading0)], dtype=float)
        normal = np.array([-tangent[1], tangent[0]], dtype=float)
        centre0 = np.array([self.x[idx], self.y[idx]], dtype=float)
        offset = pos - centre0
        s_est = float(np.clip(self.s[idx] + offset @ tangent, self.s[0], self.s[-1]))
        centre, heading, _ = self.frame(s_est)
        tangent = np.array([math.cos(heading), math.sin(heading)], dtype=float)
        normal = np.array([-tangent[1], tangent[0]], dtype=float)
        offset = pos - centre
        # One tangential correction materially reduces nearest-sample quantisation.
        s_est = float(np.clip(s_est + offset @ tangent, self.s[0], self.s[-1]))
        centre, heading, _ = self.frame(s_est)
        normal = np.array([-math.sin(heading), math.cos(heading)], dtype=float)
        ey = float((pos - centre) @ normal)
        epsi = float(wrap(state[2] - heading))
        return np.array([s_est, ey, epsi, state[3], state[4], state[5]], dtype=float)


def initialize_joint_state(
    team_frenet_state: np.ndarray,
    path: FrenetMap,
    params: ModelParams,
) -> np.ndarray:
    """Start with all four physical connectors at zero displacement."""
    payload = path.to_world(np.asarray(team_frenet_state, dtype=float))
    vehicles = np.zeros((4, 6), dtype=float)
    payload_rot = rotation(payload[2])
    vehicle_anchors = np.asarray(params.vehicle_anchor_body_m, dtype=float)
    for i in range(4):
        vehicles[i, :2] = payload[:2] + payload_rot @ (
            params.payload_anchor_body_m[i] - vehicle_anchors[i]
        )
        vehicles[i, 2] = payload[2]
        vehicles[i, 3:5] = payload[3:5]
        vehicles[i, 5] = payload[5]
    return np.r_[vehicles.reshape(-1), payload]


def frenet_states(state: np.ndarray, path: FrenetMap) -> tuple[np.ndarray, np.ndarray]:
    vehicles, payload = split_state(state)
    local = np.vstack([path.to_frenet(vehicle) for vehicle in vehicles])
    return local, path.to_frenet(payload)


def physical_history_row(
    state: np.ndarray,
    controls: np.ndarray,
    params: ModelParams,
    *,
    step: int,
) -> dict:
    diag = aggregate_diagnostics(state, controls, params)
    conn = diag["connectors"]
    fbody = np.asarray(conn["force_payload_body_n"], dtype=float)
    total = np.sum(fbody, axis=0)
    moments = np.asarray(conn["payload_moment_nm"], dtype=float)
    displacement = np.asarray(conn["displacement_world_m"], dtype=float)
    vehicles, payload = split_state(state)
    displacement_body = displacement @ rotation(payload[2])
    force_norm = np.asarray(conn["force_norm_n"], dtype=float)
    return {
        "step": int(step),
        "fx_payload": float(total[0]),
        "fy_payload": float(total[1]),
        "mz_payload": float(np.sum(moments)),
        "corner_normal_loads": np.asarray(diag["support_fz_n"], dtype=float).tolist(),
        "connector_fx_body_n": fbody[:, 0].tolist(),
        "connector_fy_body_n": fbody[:, 1].tolist(),
        "connector_force_n": force_norm.tolist(),
        "connector_force_peak_n": float(np.max(force_norm)),
        "connector_force_p99_proxy_n": float(np.percentile(force_norm, 99.0)),
        "rated_exceeded": bool(np.any(conn["rated_exceeded"])),
        "ultimate_exceeded": bool(np.any(conn["ultimate_exceeded"])),
        "q_front_rear_n": float(diag["q_front_rear_n"]),
        "q_left_right_n": float(diag["q_left_right_n"]),
        "system_yaw_rate_radps": float(diag["system_yaw_rate_radps"]),
        "internal_force_residual_n": np.asarray(diag["internal_force_residual_n"], dtype=float).tolist(),
        "tire_utilization": np.asarray(diag["tire_utilization"], dtype=float).tolist(),
        "max_abs_ds": float(np.max(np.abs(displacement_body[:, 0]))),
        "max_abs_dey": float(np.max(np.abs(displacement_body[:, 1]))),
        "max_abs_dpsi": float(np.max(np.abs(wrap(vehicles[:, 2] - payload[2])))),
        "rms_rel": float(np.sqrt(np.mean(np.sum(displacement_body**2, axis=1)))),
    }


def advance_joint_state(
    state: np.ndarray,
    team_input_delta_ax: np.ndarray,
    dt: float,
    params: ModelParams,
    config: CoupledAdapterConfig | None = None,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Project [steering, acceleration] onto common ICR and advance the plant."""
    cfg = config or CoupledAdapterConfig()
    u = np.asarray(team_input_delta_ax, dtype=float)
    virtual_front_deg = float(np.rad2deg(cfg.virtual_front_scale * u[0]))
    virtual_rear_deg = float(cfg.virtual_rear_ratio * virtual_front_deg)
    allocator_cfg = AllocationConfig(
        heading_gain=cfg.heading_gain,
        speed_gain=cfg.speed_gain,
        max_steering_deg=cfg.max_vehicle_steering_deg,
        max_zero_sum_accel_mps2=cfg.max_zero_sum_accel_mps2,
    )
    controls, target = allocate_controls(
        state,
        base_acceleration_mps2=float(u[1]),
        virtual_front_deg=virtual_front_deg,
        virtual_rear_deg=virtual_rear_deg,
        params=params,
        config=allocator_cfg,
    )
    n_sub = max(1, int(math.ceil(float(dt) / max(float(cfg.substep_s), 1.0e-6))))
    sub_dt = float(dt) / n_sub
    next_state = np.asarray(state, dtype=float).copy()
    for _ in range(n_sub):
        next_state = rk4_step(next_state, controls, sub_dt, params)
    target = dict(target)
    target["virtual_front_deg"] = virtual_front_deg
    target["virtual_rear_deg"] = virtual_rear_deg
    target["substeps"] = int(n_sub)
    return next_state, controls, target


def summarize_physical_history(rows: list[dict], params: ModelParams) -> dict:
    if not rows:
        return {}
    connector = np.asarray([row["connector_force_n"] for row in rows], dtype=float)
    opening = np.asarray(
        [[row["q_front_rear_n"], row["q_left_right_n"]] for row in rows], dtype=float
    )
    tire = np.asarray([row["tire_utilization"] for row in rows], dtype=float)
    residual = np.asarray([row["internal_force_residual_n"] for row in rows], dtype=float)
    return {
        "connector_force_peak_n": float(np.max(connector)),
        "connector_force_p99_n": float(np.percentile(connector, 99.0)),
        "opening_peak_n": float(np.max(np.abs(opening))),
        "opening_p99_n": float(np.percentile(np.abs(opening), 99.0)),
        "tire_utilization_peak": float(np.max(tire)),
        "internal_force_residual_peak_n": float(np.max(np.linalg.norm(residual, axis=1))),
        "rated_force_n": float(params.connector.rated_force_n),
        "ultimate_force_n": float(params.connector.ultimate_force_n),
        "rated_exceeded": bool(np.max(connector) >= params.connector.rated_force_n),
        "ultimate_exceeded": bool(np.max(connector) >= params.connector.ultimate_force_n),
    }
