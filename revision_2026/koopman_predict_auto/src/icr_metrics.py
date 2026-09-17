from __future__ import annotations

import numpy as np


def icr_geometry_residual(
    point_velocity_payload_body_mps: np.ndarray,
    relative_heading_rad: np.ndarray,
) -> dict:
    """Target-velocity common-ICR residual; this does not inspect wheel angles."""

    velocity = np.asarray(point_velocity_payload_body_mps, dtype=float).reshape(4, 2)
    heading = np.asarray(relative_heading_rad, dtype=float).reshape(4)
    normals = np.column_stack([-np.sin(heading), np.cos(heading)])
    signed = np.sum(velocity * normals, axis=1)
    return {"signed_per_vehicle_mps": signed, "max_abs_mps": float(np.max(np.abs(signed)))}


def icr_steering_residual(
    target_speed_mps: np.ndarray,
    target_yaw_rate_radps: float,
    wheelbase_m: float,
    wheel_angle_rad: np.ndarray,
) -> dict:
    """Wheel-angle residual v_i*tan(delta_i)-L*r for request or actual steering."""

    speed = np.asarray(target_speed_mps, dtype=float).reshape(4)
    angle = np.asarray(wheel_angle_rad, dtype=float)
    if angle.shape[-1] != 4:
        raise ValueError("wheel_angle_rad must end in four vehicle angles")
    if not np.all(np.isfinite(speed)) or not np.isfinite(target_yaw_rate_radps):
        raise ValueError("non-finite ICR target")
    if not np.isfinite(wheelbase_m) or wheelbase_m <= 0.0:
        raise ValueError("wheelbase_m must be positive")
    signed = speed * np.tan(angle) - float(wheelbase_m) * float(target_yaw_rate_radps)
    return {
        "signed_per_vehicle_mps": signed,
        "max_abs_mps": np.max(np.abs(signed), axis=-1),
    }


def summarize_residual(values_mps: np.ndarray, threshold_mps: float = 0.5) -> dict:
    values = np.asarray(values_mps, dtype=float).reshape(-1)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("residual series must be finite and non-empty")
    absolute = np.abs(values)
    return {
        "peak_mps": float(np.max(absolute)),
        "p95_mps": float(np.percentile(absolute, 95.0)),
        "rms_mps": float(np.sqrt(np.mean(values**2))),
        "fraction_above_threshold": float(np.mean(absolute > float(threshold_mps))),
        "threshold_mps": float(threshold_mps),
    }
