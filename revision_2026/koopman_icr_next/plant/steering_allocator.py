"""Common-ICR allocation for four car-like carrier vehicles."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from four_vehicle_common import ModelParams, rotation, split_state


@dataclass(frozen=True)
class AllocationConfig:
    heading_gain: float = 2.0
    speed_gain: float = 0.8
    max_steering_deg: float = 15.0
    max_zero_sum_accel_mps2: float = 0.8
    straight_eps_rad: float = 1.0e-8


def wrap(angle: np.ndarray | float) -> np.ndarray | float:
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


def virtual_4ws_icr(front_rad: float, rear_rad: float, array_wheelbase_m: float) -> np.ndarray | None:
    denominator = np.tan(front_rad) - np.tan(rear_rad)
    if abs(denominator) < 1.0e-10:
        return None
    y_icr = array_wheelbase_m / denominator
    x_icr = 0.5 * array_wheelbase_m - y_icr * np.tan(front_rad)
    return np.array([x_icr, y_icr], dtype=float)


def nominal_vehicle_centers_payload_body(params: ModelParams, relative_headings: np.ndarray) -> np.ndarray:
    """Vehicle CG locations that make vehicle and payload anchors coincide."""
    anchors_l = params.payload_anchor_body_m
    anchors_v = np.asarray(params.vehicle_anchor_body_m, dtype=float)
    centers = np.empty((4, 2), dtype=float)
    for i in range(4):
        centers[i] = anchors_l[i] - rotation(float(relative_headings[i])) @ anchors_v[i]
    return centers


def kinematic_targets(
    payload_forward_speed_mps: float,
    virtual_front_rad: float,
    virtual_rear_rad: float,
    params: ModelParams,
) -> dict:
    """Map virtual 4WS angles to four module headings, speeds and feedforward steer."""
    array_wheelbase = params.payload.length_m
    icr = virtual_4ws_icr(virtual_front_rad, virtual_rear_rad, array_wheelbase)
    if icr is None:
        headings = np.zeros(4, dtype=float)
        centers = nominal_vehicle_centers_payload_body(params, headings)
        return {
            "icr_payload_body_m": np.array([np.nan, np.inf]),
            "relative_heading_rad": headings,
            "speed_mps": np.full(4, max(float(payload_forward_speed_mps), 0.0)),
            "feedforward_steering_rad": np.zeros(4),
            "point_velocity_payload_body_mps": np.tile([max(float(payload_forward_speed_mps), 0.0), 0.0], (4, 1)),
            "normal_velocity_residual_mps": np.zeros(4),
            "yaw_rate_radps": 0.0,
            "vehicle_centers_payload_body_m": centers,
        }

    yaw_rate = float(payload_forward_speed_mps / icr[1])
    # Iterate because each nonzero vehicle heading rotates its off-center anchor.
    headings = np.zeros(4, dtype=float)
    for _ in range(8):
        centers = nominal_vehicle_centers_payload_body(params, headings)
        point_velocity = yaw_rate * np.column_stack(
            [icr[1] - centers[:, 1], centers[:, 0] - icr[0]]
        )
        next_headings = np.arctan2(point_velocity[:, 1], point_velocity[:, 0])
        if np.max(np.abs(wrap(next_headings - headings))) < 1.0e-12:
            headings = next_headings
            break
        headings = next_headings
    centers = nominal_vehicle_centers_payload_body(params, headings)
    point_velocity = yaw_rate * np.column_stack([icr[1] - centers[:, 1], centers[:, 0] - icr[0]])
    speeds = np.linalg.norm(point_velocity, axis=1)
    wheelbase = params.vehicle.lf_m + params.vehicle.lr_m
    feedforward = np.arctan2(wheelbase * yaw_rate, np.maximum(speeds, 1.0e-9))
    tangents = np.column_stack([np.cos(headings), np.sin(headings)])
    normals = np.column_stack([-np.sin(headings), np.cos(headings)])
    signed_speed = np.sum(point_velocity * tangents, axis=1)
    feedforward = np.where(signed_speed >= 0.0, feedforward, -feedforward)
    normal_residual = np.sum(point_velocity * normals, axis=1)
    return {
        "icr_payload_body_m": icr,
        "relative_heading_rad": headings,
        "speed_mps": speeds,
        "feedforward_steering_rad": feedforward,
        "point_velocity_payload_body_mps": point_velocity,
        "normal_velocity_residual_mps": normal_residual,
        "yaw_rate_radps": yaw_rate,
        "vehicle_centers_payload_body_m": centers,
    }


def request_variants(
    state: np.ndarray,
    virtual_front_deg: float,
    virtual_rear_deg: float,
    params: ModelParams,
    config: AllocationConfig | None = None,
) -> dict:
    """Return the frozen request-layer attribution G0/G1/G2.

    G0 is common-ICR feedforward, G1 adds the existing per-vehicle heading
    feedback, and G2 applies the existing independent steering clip.  The
    arithmetic is deliberately the same as the parent allocator so G2 can be
    compared point-for-point with the frozen F3 request.
    """

    cfg = config or AllocationConfig()
    vehicles, payload = split_state(state)
    targets = kinematic_targets(
        payload_forward_speed_mps=max(float(payload[3]), 0.0),
        virtual_front_rad=np.deg2rad(virtual_front_deg),
        virtual_rear_rad=np.deg2rad(virtual_rear_deg),
        params=params,
    )
    desired_world_yaw = payload[2] + targets["relative_heading_rad"]
    heading_error = wrap(desired_world_yaw - vehicles[:, 2])
    g0 = targets["feedforward_steering_rad"]
    g1 = g0 + cfg.heading_gain * heading_error
    steering_limit = np.deg2rad(cfg.max_steering_deg)
    g2 = np.clip(g1, -steering_limit, steering_limit)
    return {
        **targets,
        "desired_world_yaw_rad": desired_world_yaw,
        "heading_error_rad": heading_error,
        "g0_steering_rad": np.asarray(g0, dtype=float).copy(),
        "g1_steering_rad": np.asarray(g1, dtype=float).copy(),
        "g2_steering_rad": np.asarray(g2, dtype=float).copy(),
        "feedback_delta_rad": np.asarray(g1 - g0, dtype=float).copy(),
        "clip_delta_rad": np.asarray(g2 - g1, dtype=float).copy(),
        "steering_clipped": np.abs(g1 - g2) > 1.0e-15,
    }


def allocate_controls(
    state: np.ndarray,
    base_acceleration_mps2: float,
    virtual_front_deg: float,
    virtual_rear_deg: float,
    params: ModelParams,
    config: AllocationConfig | None = None,
) -> tuple[np.ndarray, dict]:
    cfg = config or AllocationConfig()
    vehicles, payload = split_state(state)
    targets = request_variants(
        state, virtual_front_deg, virtual_rear_deg, params, cfg
    )
    desired_world_yaw = targets["desired_world_yaw_rad"]
    heading_error = targets["heading_error_rad"]
    steering_raw = targets["g1_steering_rad"]
    steering = targets["g2_steering_rad"]

    correction = cfg.speed_gain * (targets["speed_mps"] - vehicles[:, 3])
    correction -= np.mean(correction)
    correction = np.clip(correction, -cfg.max_zero_sum_accel_mps2, cfg.max_zero_sum_accel_mps2)
    correction -= np.mean(correction)
    controls = np.column_stack([base_acceleration_mps2 + correction, steering])
    targets["desired_world_yaw_rad"] = desired_world_yaw
    targets["heading_error_rad"] = heading_error
    targets["allocated_acceleration_mps2"] = controls[:, 0]
    targets["allocated_steering_rad"] = steering
    targets["unclipped_steering_rad"] = steering_raw
    targets["steering_clipped"] = np.abs(steering_raw-steering)>1e-15
    targets["steering_clipped_fraction"] = float(np.mean(targets["steering_clipped"]))
    targets["max_normal_velocity_residual_mps"] = float(np.max(np.abs(targets["normal_velocity_residual_mps"])))
    return controls, targets
