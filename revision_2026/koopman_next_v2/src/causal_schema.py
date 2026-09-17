from __future__ import annotations


SCHEMA_ID = "koopman_next_causal_relative_v3"
SCHEMA_V4_ID = "koopman_v2_hybrid_actuator_causal_v4"


def field(name: str, dimension: int, unit: str, frame: str, time: str, role: str) -> dict:
    return {
        "name": name,
        "dimension": int(dimension),
        "unit": unit,
        "frame": frame,
        "time": time,
        "role": role,
    }


def relative_field_names() -> list[str]:
    names = ["payload_vx_mps", "payload_vy_mps", "payload_yaw_rate_radps"]
    for index in range(4):
        names.extend(
            [
                f"vehicle_{index}_rho_x_m",
                f"vehicle_{index}_rho_y_m",
                f"vehicle_{index}_sin_delta_yaw",
                f"vehicle_{index}_cos_delta_yaw",
            ]
        )
    for index in range(4):
        names.extend(
            [
                f"vehicle_{index}_relative_center_vx_payload_mps",
                f"vehicle_{index}_relative_center_vy_payload_mps",
                f"vehicle_{index}_relative_yaw_rate_radps",
            ]
        )
    for index in range(4):
        names.extend(
            [
                f"connector_{index}_displacement_x_payload_m",
                f"connector_{index}_displacement_y_payload_m",
                f"connector_{index}_anchor_relative_vx_payload_mps",
                f"connector_{index}_anchor_relative_vy_payload_mps",
            ]
        )
    if len(names) != 47 or len(names) != len(set(names)):
        raise AssertionError("relative field registry drift")
    return names


def build_schema_v3() -> dict:
    inputs = [
        field("physical_state30_k", 30, "fieldwise_si", "mixed_registered", "t_k", "model_input"),
        field("relative_state47_k", 47, "fieldwise_si", "payload_and_relative", "t_k", "model_input"),
        field("payload_pose_context3_k", 3, "m,m,rad", "world", "t_k", "reconstruction_context"),
        field("force_endpoint8_k", 8, "N", "payload_body_at_t_k", "t_k", "model_input"),
        field("force_mean8_prev", 8, "N", "payload_body_at_t_k", "interval_(t_k-1,t_k]", "model_input"),
        field("force_rate8_prev", 8, "N/s", "payload_body_at_t_k", "interval_history_at_t_k", "model_input"),
        field("event_counts16_prev", 16, "count", "connector_surface_direction", "interval_(t_k-1,t_k]", "gate_input"),
        field("contact_fraction4_prev", 4, "1", "connector", "interval_(t_k-1,t_k]", "gate_input"),
        field("smoothing_fraction4_prev", 4, "1", "connector", "interval_(t_k-1,t_k]", "gate_input"),
        field("smoothing_weight_mean4_prev", 4, "1", "connector", "interval_(t_k-1,t_k]", "gate_input"),
        field("force_active_mask4_k", 4, "bool", "connector", "t_k", "gate_input"),
        field("u8_k", 8, "m/s^2,rad", "vehicle_body", "applied_[t_k,t_k+1]", "control_input"),
        field("delta_u8_k", 8, "m/s^2,rad", "vehicle_body", "available_at_t_k", "control_input"),
        field("parameter_vector_k", 10, "fieldwise_si", "model_configuration", "known_at_t_k", "audit_only"),
    ]
    labels = [
        field("physical_state30_k1", 30, "fieldwise_si", "mixed_registered", "t_k+1", "label_only"),
        field("relative_state47_k1", 47, "fieldwise_si", "payload_and_relative", "t_k+1", "label_only"),
        field("force_endpoint8_k1", 8, "N", "payload_body_at_t_k+1", "t_k+1", "label_only"),
        field("force_mean8_next", 8, "N", "payload_body_at_t_k+1", "interval_(t_k,t_k+1]", "label_only"),
        field("force_impulse8_next_world", 8, "N*s", "world", "interval_(t_k,t_k+1]", "label_only"),
        field("internal_force8_next", 8, "N", "payload_body_at_t_k+1", "interval_(t_k,t_k+1]", "label_only"),
        field("tension_proxy2_next", 2, "N", "payload_body_at_t_k+1", "interval_(t_k,t_k+1]", "label_only"),
        field("event_counts16_next", 16, "count", "connector_surface_direction", "interval_(t_k,t_k+1]", "supervision_only"),
        field("contact_fraction4_next", 4, "1", "connector", "interval_(t_k,t_k+1]", "supervision_only"),
        field("smoothing_fraction4_next", 4, "1", "connector", "interval_(t_k,t_k+1]", "supervision_only"),
    ]
    names = [item["name"] for item in inputs + labels]
    if len(names) != len(set(names)):
        raise ValueError("duplicate causal schema fields")
    if any(item["role"] in {"model_input", "gate_input", "control_input"} and "next" in item["name"] for item in inputs):
        raise ValueError("future field registered as input")
    return {
        "schema_id": SCHEMA_ID,
        "relative_dimension": 47,
        "relative_fields": relative_field_names(),
        "inputs": inputs,
        "labels": labels,
        "network_fields": [
            field("network_mask", 0, "bool", "network", "network_stage_only", "not_used_in_clean_training"),
            field("network_aoi", 0, "s", "network", "network_stage_only", "not_used_in_clean_training"),
        ],
        "causal_contract": "Inputs describe t_k, completed interval (t_k-1,t_k], and known u_k. Labels describe t_k+1 and interval (t_k,t_k+1].",
    }


def build_schema_v4() -> dict:
    """Hybrid 47-state plus analytic four-actuator causal interface."""

    inputs = [
        field("physical_state30_k", 30, "fieldwise_si", "mixed_registered", "t_k", "model_input"),
        field("relative_state47_k", 47, "fieldwise_si", "payload_and_relative", "t_k", "model_input"),
        field("actual_steering4_k", 4, "rad", "vehicle_front_wheel", "t_k", "analytic_state"),
        field("hybrid_state51_k", 51, "fieldwise_si", "relative_plus_actuator", "t_k", "model_input"),
        field("payload_pose_context3_k", 3, "m,m,rad", "world", "t_k", "reconstruction_context"),
        field("force_endpoint8_k", 8, "N", "payload_body_at_t_k", "t_k", "model_input"),
        field("force_mean8_prev", 8, "N", "payload_body_at_t_k", "interval_(t_k-1,t_k]", "model_input"),
        field("force_rate8_prev", 8, "N/s", "payload_body_at_t_k", "interval_history_at_t_k", "model_input"),
        field("event_counts16_prev", 16, "count", "connector_surface_direction", "interval_(t_k-1,t_k]", "gate_input"),
        field("contact_fraction4_prev", 4, "1", "connector", "interval_(t_k-1,t_k]", "gate_input"),
        field("smoothing_fraction4_prev", 4, "1", "connector", "interval_(t_k-1,t_k]", "gate_input"),
        field("smoothing_weight_mean4_prev", 4, "1", "connector", "interval_(t_k-1,t_k]", "gate_input"),
        field("force_active_mask4_k", 4, "bool", "connector", "t_k", "gate_input"),
        field("acceleration_request4_k", 4, "m/s^2", "vehicle_body", "held_[t_k,t_k+1]", "control_input"),
        field("steering_request4_k", 4, "rad", "vehicle_front_wheel", "held_[t_k,t_k+1]", "control_input"),
        field("actuator_error4_k", 4, "rad", "vehicle_front_wheel", "available_at_t_k", "gate_input"),
        field("actual_steering_rate4_prev", 4, "rad/s", "vehicle_front_wheel", "interval_(t_k-1,t_k]", "gate_input"),
        field("actual_steering_mean4_k", 4, "rad", "vehicle_front_wheel", "analytic_rollout_[t_k,t_k+1]", "control_input"),
        field("u_act8_k", 8, "m/s^2,rad", "vehicle_body", "analytic_applied_[t_k,t_k+1]", "control_input"),
        field("delta_u_req8_k", 8, "m/s^2,rad", "vehicle_body", "available_at_t_k", "control_input"),
        field("actuator_rate_limited4_k", 4, "bool", "vehicle_front_wheel", "analytic_rollout_[t_k,t_k+1]", "gate_input"),
        field("actuator_angle_limited4_k", 4, "bool", "vehicle_front_wheel", "analytic_rollout_[t_k,t_k+1]", "gate_input"),
        field("actuator_config3_k", 3, "s,rad/s,rad", "model_configuration", "known_at_t_k", "audit_only"),
        field("parameter_vector_k", 10, "fieldwise_si", "model_configuration", "known_at_t_k", "audit_only"),
    ]
    labels = [
        field("physical_state30_k1", 30, "fieldwise_si", "mixed_registered", "t_k+1", "label_only"),
        field("relative_state47_k1", 47, "fieldwise_si", "payload_and_relative", "t_k+1", "label_only"),
        field("actual_steering4_k1", 4, "rad", "vehicle_front_wheel", "t_k+1", "label_only"),
        field("actual_steering_rate4_next", 4, "rad/s", "vehicle_front_wheel", "interval_(t_k,t_k+1]", "label_only"),
        field("force_endpoint8_k1", 8, "N", "payload_body_at_t_k+1", "t_k+1", "label_only"),
        field("force_mean8_next", 8, "N", "payload_body_at_t_k+1", "interval_(t_k,t_k+1]", "label_only"),
        field("force_impulse8_next_world", 8, "N*s", "world", "interval_(t_k,t_k+1]", "label_only"),
        field("internal_force8_next", 8, "N", "payload_body_at_t_k+1", "interval_(t_k,t_k+1]", "label_only"),
        field("tension_proxy2_next", 2, "N", "payload_body_at_t_k+1", "interval_(t_k,t_k+1]", "label_only"),
        field("event_counts16_next", 16, "count", "connector_surface_direction", "interval_(t_k,t_k+1]", "supervision_only"),
        field("contact_fraction4_next", 4, "1", "connector", "interval_(t_k,t_k+1]", "supervision_only"),
        field("smoothing_fraction4_next", 4, "1", "connector", "interval_(t_k,t_k+1]", "supervision_only"),
    ]
    names = [item["name"] for item in inputs + labels]
    if len(names) != len(set(names)):
        raise ValueError("duplicate v4 causal schema fields")
    if any("next" in item["name"] for item in inputs):
        raise ValueError("future field registered as v4 input")
    return {
        "schema_id": SCHEMA_V4_ID,
        "relative_dimension": 47,
        "hybrid_dimension": 51,
        "relative_fields": relative_field_names(),
        "inputs": inputs,
        "labels": labels,
        "causal_contract": (
            "Future request controls are known. Future actual steering is never read; "
            "it is propagated from delta_act_k by the frozen analytic actuator."
        ),
    }
