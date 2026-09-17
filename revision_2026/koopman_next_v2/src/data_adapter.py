from __future__ import annotations

import hashlib
from typing import Mapping

import numpy as np

from relative_coordinates import encode_relative
from actuator_rollout import rollout_actuator_interval
from steering_actuator import SteeringActuatorConfig


INPUT_KEYS = (
    "physical_state30_k",
    "relative_state47_k",
    "payload_pose_context3_k",
    "force_endpoint8_k",
    "force_mean8_prev",
    "force_rate8_prev",
    "event_counts16_prev",
    "contact_fraction4_prev",
    "smoothing_fraction4_prev",
    "smoothing_weight_mean4_prev",
    "force_active_mask4_k",
    "u8_k",
    "delta_u8_k",
    "parameter_vector_k",
)


LABEL_KEYS = (
    "physical_state30_k1",
    "relative_state47_k1",
    "force_endpoint8_k1",
    "force_mean8_next",
    "force_impulse8_next_world",
    "internal_force8_next",
    "tension_proxy2_next",
    "event_counts16_next",
    "contact_fraction4_next",
    "smoothing_fraction4_next",
)


INPUT_KEYS_V4 = (
    "physical_state30_k",
    "relative_state47_k",
    "actual_steering4_k",
    "hybrid_state51_k",
    "payload_pose_context3_k",
    "force_endpoint8_k",
    "force_mean8_prev",
    "force_rate8_prev",
    "event_counts16_prev",
    "contact_fraction4_prev",
    "smoothing_fraction4_prev",
    "smoothing_weight_mean4_prev",
    "force_active_mask4_k",
    "acceleration_request4_k",
    "steering_request4_k",
    "actuator_error4_k",
    "actual_steering_rate4_prev",
    "actual_steering_mean4_k",
    "u_act8_k",
    "delta_u_req8_k",
    "actuator_rate_limited4_k",
    "actuator_angle_limited4_k",
    "actuator_config3_k",
    "parameter_vector_k",
)


LABEL_KEYS_V4 = (
    "physical_state30_k1",
    "relative_state47_k1",
    "actual_steering4_k1",
    "actual_steering_rate4_next",
    "force_endpoint8_k1",
    "force_mean8_next",
    "force_impulse8_next_world",
    "internal_force8_next",
    "tension_proxy2_next",
    "event_counts16_next",
    "contact_fraction4_next",
    "smoothing_fraction4_next",
)


def parameter_vector(params: object) -> np.ndarray:
    return np.asarray(
        [
            params.vehicle.mass_kg,
            params.vehicle.yaw_inertia_kgm2,
            params.vehicle.mu,
            params.payload.mass_kg,
            params.payload.length_m,
            params.payload.width_m,
            params.connector.stiffness_npm,
            params.connector.damping_nspm,
            params.connector.free_play_m,
            params.connector.smoothing_width_m,
        ],
        dtype=float,
    )


def require_raw_arrays(arrays: Mapping[str, np.ndarray]) -> None:
    required = {
        "time_s",
        "state30",
        "control4x2",
        "force_payload_body_n",
        "force_active_mask",
        "force_interval_mean_body_n",
        "force_interval_impulse_world_ns",
        "internal_force_interval_mean_n",
        "tension_proxy_interval_mean_n",
        "contact_fraction",
        "smoothing_fraction",
        "smoothing_weight_mean",
        "event_counts16",
    }
    missing = sorted(required - set(arrays))
    if missing:
        raise KeyError(f"missing raw arrays: {missing}")


def validate_model_time_grid(
    arrays: Mapping[str, np.ndarray], *, expected_step_s: float, step_atol_s: float = 1.0e-9
) -> dict[str, float | int]:
    require_raw_arrays(arrays)
    if not np.isfinite(expected_step_s) or expected_step_s <= 0.0:
        raise ValueError(f"invalid expected model step={expected_step_s}")
    if not np.isfinite(step_atol_s) or step_atol_s < 0.0:
        raise ValueError(f"invalid model-step tolerance={step_atol_s}")
    time_s = np.asarray(arrays["time_s"], dtype=float)
    if time_s.ndim != 1 or time_s.size < 3:
        raise ValueError(f"invalid time grid shape={time_s.shape}")
    steps = np.diff(time_s)
    finite_positive = np.isfinite(steps) & (steps > 0.0)
    on_grid = finite_positive & (np.abs(steps - expected_step_s) <= step_atol_s)
    if not np.all(on_grid):
        bad = np.flatnonzero(~on_grid)
        preview = bad[:8].tolist()
        raise ValueError(
            "off-grid trajectory time grid: "
            f"{bad.size}/{steps.size} intervals fail {expected_step_s} +/- {step_atol_s} s; "
            f"first_bad_interval_indices={preview}; step_min={np.nanmin(steps)}; step_max={np.nanmax(steps)}"
        )
    return {
        "interval_count": int(steps.size),
        "step_min_s": float(np.min(steps)),
        "step_max_s": float(np.max(steps)),
        "max_abs_error_s": float(np.max(np.abs(steps - expected_step_s))),
    }


def build_sample(
    arrays: Mapping[str, np.ndarray],
    index: int,
    params: object,
    *,
    expected_step_s: float,
    step_atol_s: float = 1.0e-9,
) -> dict[str, np.ndarray | float | int]:
    validate_model_time_grid(arrays, expected_step_s=expected_step_s, step_atol_s=step_atol_s)
    count = len(arrays["time_s"])
    if not 1 <= index < count - 1:
        raise IndexError(f"index must satisfy 1 <= index < {count - 1}")
    dt_previous = float(arrays["time_s"][index] - arrays["time_s"][index - 1])
    dt_prediction = float(arrays["time_s"][index + 1] - arrays["time_s"][index])
    for role, actual in (("previous", dt_previous), ("prediction", dt_prediction)):
        if not np.isfinite(actual) or actual <= 0.0:
            raise ValueError(f"invalid {role} interval dt={actual}")
        if abs(actual - expected_step_s) > step_atol_s:
            raise ValueError(
                f"off-grid {role} interval dt={actual}; "
                f"expected {expected_step_s} +/- {step_atol_s} s"
            )
    state_k = np.asarray(arrays["state30"][index], dtype=float)
    state_k1 = np.asarray(arrays["state30"][index + 1], dtype=float)
    relative_k = encode_relative(state_k, params)
    relative_k1 = encode_relative(state_k1, params)
    force_mean_prev = np.asarray(arrays["force_interval_mean_body_n"][index], dtype=float)
    force_mean_before_prev = np.asarray(arrays["force_interval_mean_body_n"][index - 1], dtype=float)
    control_k = np.asarray(arrays["control4x2"][index + 1], dtype=float)
    control_previous = np.asarray(arrays["control4x2"][index], dtype=float)
    sample = {
        "physical_state30_k": state_k.copy(),
        "relative_state47_k": relative_k["relative_state47"].copy(),
        "payload_pose_context3_k": relative_k["payload_pose_context3"].copy(),
        "force_endpoint8_k": np.asarray(arrays["force_payload_body_n"][index], dtype=float).ravel().copy(),
        "force_mean8_prev": force_mean_prev.ravel().copy(),
        "force_rate8_prev": ((force_mean_prev - force_mean_before_prev) / dt_previous).ravel(),
        "event_counts16_prev": np.asarray(arrays["event_counts16"][index], dtype=float).copy(),
        "contact_fraction4_prev": np.asarray(arrays["contact_fraction"][index], dtype=float).copy(),
        "smoothing_fraction4_prev": np.asarray(arrays["smoothing_fraction"][index], dtype=float).copy(),
        "smoothing_weight_mean4_prev": np.asarray(arrays["smoothing_weight_mean"][index], dtype=float).copy(),
        "force_active_mask4_k": np.asarray(arrays["force_active_mask"][index], dtype=bool).copy(),
        "u8_k": control_k.ravel().copy(),
        "delta_u8_k": (control_k - control_previous).ravel(),
        "parameter_vector_k": parameter_vector(params),
        "physical_state30_k1": state_k1.copy(),
        "relative_state47_k1": relative_k1["relative_state47"].copy(),
        "force_endpoint8_k1": np.asarray(arrays["force_payload_body_n"][index + 1], dtype=float).ravel().copy(),
        "force_mean8_next": np.asarray(arrays["force_interval_mean_body_n"][index + 1], dtype=float).ravel().copy(),
        "force_impulse8_next_world": np.asarray(arrays["force_interval_impulse_world_ns"][index + 1], dtype=float).ravel().copy(),
        "internal_force8_next": np.asarray(arrays["internal_force_interval_mean_n"][index + 1], dtype=float).copy(),
        "tension_proxy2_next": np.asarray(arrays["tension_proxy_interval_mean_n"][index + 1], dtype=float).copy(),
        "event_counts16_next": np.asarray(arrays["event_counts16"][index + 1], dtype=float).copy(),
        "contact_fraction4_next": np.asarray(arrays["contact_fraction"][index + 1], dtype=float).copy(),
        "smoothing_fraction4_next": np.asarray(arrays["smoothing_fraction"][index + 1], dtype=float).copy(),
        "sample_time_s": float(arrays["time_s"][index]),
        "target_time_s": float(arrays["time_s"][index + 1]),
        "previous_interval_s": dt_previous,
        "prediction_interval_s": dt_prediction,
        "source_index": int(index),
    }
    for key in INPUT_KEYS + LABEL_KEYS:
        value = np.asarray(sample[key])
        if not np.all(np.isfinite(value)):
            raise ValueError(f"non-finite sample field: {key}")
    return sample


def causal_input_digest(sample: Mapping[str, object]) -> str:
    digest = hashlib.sha256()
    for key in INPUT_KEYS:
        value = np.ascontiguousarray(np.asarray(sample[key]))
        digest.update(key.encode("utf-8"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


def _scalar_array(arrays: Mapping[str, np.ndarray], key: str) -> float:
    value = np.asarray(arrays[key], dtype=float)
    if value.size != 1 or not np.all(np.isfinite(value)):
        raise ValueError(f"invalid scalar raw field: {key}")
    return float(value.reshape(-1)[0])


def build_sample_v4(
    arrays: Mapping[str, np.ndarray],
    index: int,
    params: object,
    *,
    expected_step_s: float,
    plant_step_s: float,
    step_atol_s: float = 1.0e-9,
) -> dict[str, np.ndarray | float | int]:
    """Build a causal v4 sample without reading future actual steering as input."""

    required = {
        "requested_control4x2",
        "actual_steering_rad",
        "actual_steering_rate_radps",
        "actuator_tau_delta_s",
        "actuator_rate_max_radps",
        "actuator_angle_max_rad",
    }
    missing = sorted(required - set(arrays))
    if missing:
        raise KeyError(f"missing v4 raw arrays: {missing}")
    base = build_sample(
        arrays,
        index,
        params,
        expected_step_s=expected_step_s,
        step_atol_s=step_atol_s,
    )
    request = np.asarray(arrays["requested_control4x2"][index + 1], dtype=float)
    previous_request = np.asarray(arrays["requested_control4x2"][index], dtype=float)
    actual_k = np.asarray(arrays["actual_steering_rad"][index], dtype=float)
    if request.shape != (4, 2) or actual_k.shape != (4,):
        raise ValueError("invalid v4 request or actuator state shape")
    actuator_config = SteeringActuatorConfig(
        tau_delta_s=_scalar_array(arrays, "actuator_tau_delta_s"),
        rate_max_radps=_scalar_array(arrays, "actuator_rate_max_radps"),
        angle_max_rad=_scalar_array(arrays, "actuator_angle_max_rad"),
    )
    substeps = int(round(expected_step_s / plant_step_s))
    if abs(substeps * plant_step_s - expected_step_s) > step_atol_s:
        raise ValueError("model interval is not an integer number of actuator substeps")
    analytic = rollout_actuator_interval(
        actual_k,
        request[:, 1],
        plant_step_s=plant_step_s,
        substeps=substeps,
        config=actuator_config,
    )
    actual_mean = analytic["delta_act_mean_rad"]
    u_act = np.column_stack([request[:, 0], actual_mean])
    relative_k = np.asarray(base["relative_state47_k"], dtype=float)
    sample = {
        **base,
        "actual_steering4_k": actual_k.copy(),
        "hybrid_state51_k": np.r_[relative_k, actual_k],
        "acceleration_request4_k": request[:, 0].copy(),
        "steering_request4_k": request[:, 1].copy(),
        "actuator_error4_k": (request[:, 1] - actual_k).copy(),
        "actual_steering_rate4_prev": np.asarray(
            arrays["actual_steering_rate_radps"][index], dtype=float
        ).copy(),
        "actual_steering_mean4_k": actual_mean.copy(),
        "u_act8_k": u_act.ravel(),
        "delta_u_req8_k": (request - previous_request).ravel(),
        "actuator_rate_limited4_k": np.any(
            analytic["rate_limited_substeps"], axis=0
        ),
        "actuator_angle_limited4_k": np.any(
            analytic["angle_limited_substeps"], axis=0
        ),
        "actuator_config3_k": np.asarray(
            [
                actuator_config.tau_delta_s,
                actuator_config.rate_max_radps,
                actuator_config.angle_max_rad,
            ]
        ),
        "actual_steering4_k1": np.asarray(
            arrays["actual_steering_rad"][index + 1], dtype=float
        ).copy(),
        "actual_steering_rate4_next": np.asarray(
            arrays["actual_steering_rate_radps"][index + 1], dtype=float
        ).copy(),
    }
    for key in INPUT_KEYS_V4 + LABEL_KEYS_V4:
        value = np.asarray(sample[key])
        if not np.all(np.isfinite(value)):
            raise ValueError(f"non-finite v4 sample field: {key}")
    return sample


def causal_input_digest_v4(sample: Mapping[str, object]) -> str:
    digest = hashlib.sha256()
    for key in INPUT_KEYS_V4:
        value = np.ascontiguousarray(np.asarray(sample[key]))
        digest.update(key.encode("utf-8"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


def validate_force_interfaces(arrays: Mapping[str, np.ndarray], index: int, params: object) -> dict:
    from internal_force import decompose_planar_point_forces, legacy_q_fr_q_lr, tension_load_proxies

    force = np.asarray(arrays["force_payload_body_n"][index], dtype=float).reshape(4, 2)
    vehicle_force = -force
    decomposition = decompose_planar_point_forces(force, params.payload_anchor_body_m)
    tension = tension_load_proxies(force)
    recorded_wrench = np.asarray(arrays["payload_wrench"][index], dtype=float)
    recorded_internal = np.asarray(arrays["internal_force_vector_n"][index], dtype=float)
    recorded_tension = np.asarray(arrays["tension_proxy_n"][index], dtype=float)
    return {
        "action_reaction_max_n": float(np.max(np.abs(force + vehicle_force))),
        "payload_wrench_max_abs": float(np.max(np.abs(decomposition["generalized_payload_wrench"] - recorded_wrench))),
        "internal_force_max_abs_n": float(np.max(np.abs(decomposition["internal_force_vector"] - recorded_internal))),
        "internal_null_norm": float(np.linalg.norm(decomposition["null_residual"])),
        "tension_max_abs_n": float(
            np.max(
                np.abs(
                    np.asarray([tension["tension_x_n"], tension["tension_y_n"]])
                    - recorded_tension
                )
            )
        ),
        "q": legacy_q_fr_q_lr(force),
    }
