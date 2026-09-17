from __future__ import annotations


SCHEMA_ID = "koopman_next_causal_relative_v3"
SCHEMA_V4_ID = "koopman_v2_hybrid_actuator_causal_v4"
SCHEMA_FOCUS_ID = "koopman_focus_hybrid_icr_support_causal_v1"
SCHEMA_ICR_ID = "koopman_icr_fix_actuator_sidecar_causal_v1"
SCHEMA_PREDICT_VARIANT_ID = "koopman_predict_next_variant_causal_v1"


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


def build_schema_focus() -> dict:
    """V4 state plus analytic current ICR and four-car payload-support context."""

    base = build_schema_v4()
    inputs = list(base["inputs"]) + [
        field("payload_support_load4_k", 4, "N", "payload_support_FL_FR_RL_RR", "t_k", "analytic_context"),
        field("vehicle_total_normal_load4_k", 4, "N", "vehicle_FL_FR_RL_RR", "t_k", "analytic_context"),
        field("payload_accel_body2_k", 2, "m/s^2", "payload_body", "t_k", "analytic_context"),
        field("icr_geom_k", 1, "m/s", "payload_target_geometry", "t_k_and_known_u_k", "diagnostic_input"),
        field("icr_request_k", 1, "m/s", "vehicle_wheel_request", "t_k_and_known_u_k", "diagnostic_input"),
        field("icr_actual_k", 1, "m/s", "vehicle_actual_wheel", "t_k_and_known_u_k", "diagnostic_input"),
    ]
    labels = list(base["labels"]) + [
        field("payload_support_load4_k1", 4, "N", "payload_support_FL_FR_RL_RR", "t_k+1", "label_only"),
        field("vehicle_total_normal_load4_k1", 4, "N", "vehicle_FL_FR_RL_RR", "t_k+1", "label_only"),
        field("payload_accel_body2_k1", 2, "m/s^2", "payload_body", "t_k+1", "label_only"),
        field("icr_geom_k1", 1, "m/s", "payload_target_geometry", "t_k+1", "label_only"),
        field("icr_request_k1", 1, "m/s", "vehicle_wheel_request", "t_k+1", "label_only"),
        field("icr_actual_k1", 1, "m/s", "vehicle_actual_wheel", "t_k+1", "label_only"),
    ]
    names = [item["name"] for item in inputs + labels]
    if len(names) != len(set(names)):
        raise ValueError("duplicate focus causal schema fields")
    if any(item["time"] == "t_k+1" for item in inputs):
        raise ValueError("future focus field registered as input")
    return {
        **base,
        "schema_id": SCHEMA_FOCUS_ID,
        "inputs": inputs,
        "labels": labels,
        "causal_contract": (
            "Current support loads and ICR diagnostics are recomputed from t_k state, "
            "completed history, and known u_k. Future actual steering and support loads "
            "are labels only and never read as model inputs."
        ),
    }


def build_schema_icr() -> dict:
    """Focus schema plus the causal steering-actuator sidecar and gate context."""

    base = build_schema_focus()
    inputs = list(base["inputs"]) + [
        field(
            "actuator_sidecar20_k",
            20,
            "rad,rad/s,rad,bool,bool",
            "vehicle_front_wheel",
            "available_at_t_k",
            "analytic_state",
        ),
        field(
            "actuator_gate8_k",
            8,
            "rad,rad,m/s,bool,bool",
            "vehicle_front_wheel_and_array",
            "available_at_t_k",
            "gate_input",
        ),
    ]
    labels = list(base["labels"])
    names = [item["name"] for item in inputs + labels]
    if len(names) != len(set(names)):
        raise ValueError("duplicate ICR causal schema fields")
    if any(item["time"] == "t_k+1" for item in inputs):
        raise ValueError("future ICR field registered as input")
    return {
        **base,
        "schema_id": SCHEMA_ICR_ID,
        "inputs": inputs,
        "labels": labels,
        "actuator_sidecar_definition": (
            "[delta_act4, delta_rate4, delta_req_minus_act4, "
            "rate_mask4, angle_mask4]"
        ),
        "actuator_gate_definition": (
            "[abs_delta_request4, request_tracking_l2, actual_icr, "
            "max_rate_mask, max_angle_mask]"
        ),
        "causal_contract": (
            "All ICR sidecar inputs are available at t_k or analytically propagated "
            "from t_k and known held requests. Future measured steering remains label-only."
        ),
    }


def validate_schema_icr_next_contract(schema: dict) -> dict:
    """Reject duplicate or future-leaking roles before future N3 work begins."""

    inputs = list(schema.get("inputs", []))
    labels = list(schema.get("labels", []))
    names = [item.get("name") for item in inputs + labels]
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("schema contains an unnamed field")
    if len(names) != len(set(names)):
        raise ValueError("schema contains duplicate physical fields")
    leaking = [
        item["name"]
        for item in inputs
        if item.get("time") == "t_k+1"
        or item.get("role") in {"label", "label_only", "supervision_only"}
    ]
    if leaking:
        raise ValueError(f"future/label fields registered as inputs: {leaking}")
    required = {"actual_steering4_k", "actuator_sidecar20_k", "actuator_gate8_k"}
    missing = sorted(required - {item["name"] for item in inputs})
    if missing:
        raise ValueError(f"missing causal actuator fields: {missing}")
    return {
        "passed": True,
        "input_count": len(inputs),
        "label_count": len(labels),
        "duplicate_physical_feature_count": 0,
        "future_input_count": 0,
    }


def predict_field(
    name: str,
    shape: tuple[int, ...],
    unit: str,
    endpoint: str,
    role: str,
    source: str,
    physical_components: tuple[str, ...],
) -> dict:
    """Register an N3 field with explicit shape, endpoint and provenance."""

    if not shape or any(int(value) <= 0 for value in shape):
        raise ValueError(f"invalid field shape for {name}: {shape}")
    return {
        "name": str(name),
        "shape": [int(value) for value in shape],
        "dimension": int(__import__("math").prod(shape)),
        "unit": str(unit),
        "endpoint": str(endpoint),
        "role": str(role),
        "source": str(source),
        "physical_components": list(physical_components),
    }


def build_schema_variant(variant: str) -> dict:
    """Build the frozen S0/S1/S2 causal interface without duplicate state fields.

    S0 exposes the 47-dimensional relative state.  S1 replaces that state field
    with one 51-dimensional relative-plus-actual-steering field.  S2 keeps the
    S1 state and adds only quantities analytically propagated from the current
    measured steering and known request sequence.  Future measured steering is
    never an input.
    """

    selected = str(variant).upper()
    if selected not in {"S0", "S1", "S2"}:
        raise ValueError(f"unknown predict schema variant: {variant}")
    common_controls = [
        predict_field(
            "virtual_control3_k",
            (3,),
            "m/s^2,rad,rad",
            "known_at_t_k_for_[t_k,t_k+1]",
            "control_input",
            "scenario_command_and_recorded_virtual_request",
            ("acceleration_request", "virtual_front", "virtual_rear"),
        ),
        predict_field(
            "steering_request4_k",
            (4,),
            "rad",
            "known_at_t_k_for_[t_k,t_k+1]",
            "control_input",
            "requested_control4x2[index+1,:,steering]",
            tuple(f"vehicle_{index}_steering_request" for index in range(4)),
        ),
    ]
    if selected == "S0":
        state = predict_field(
            "state47_k",
            (47,),
            "fieldwise_si",
            "t_k",
            "model_state",
            "relative_coordinates.encode_relative(state30[index])",
            tuple(relative_field_names()),
        )
        label = predict_field(
            "state47_k1",
            (47,),
            "fieldwise_si",
            "t_k+1_label_only",
            "label_only",
            "relative_coordinates.encode_relative(state30[index+1])",
            tuple(name.replace("_k", "_k1") for name in relative_field_names()),
        )
        inputs = [state, *common_controls]
        labels = [label]
    else:
        state = predict_field(
            "hybrid_state51_k",
            (51,),
            "fieldwise_si",
            "t_k",
            "model_state",
            "relative_state47_k_plus_actual_steering_rad[index]",
            tuple(relative_field_names())
            + tuple(f"vehicle_{index}_actual_steering" for index in range(4)),
        )
        label = predict_field(
            "hybrid_state51_k1",
            (51,),
            "fieldwise_si",
            "t_k+1_label_only",
            "label_only",
            "relative_state47_k1_plus_actual_steering_rad[index+1]",
            tuple(name.replace("_k", "_k1") for name in relative_field_names())
            + tuple(f"vehicle_{index}_actual_steering_k1" for index in range(4)),
        )
        inputs = [state, *common_controls]
        labels = [label]
        if selected == "S2":
            inputs.extend(
                [
                    predict_field(
                        "analytic_actual_steering4_k1",
                        (4,),
                        "rad",
                        "known_at_t_k_via_A3_rollout",
                        "analytic_control_sidecar",
                        "A3(current_actual_steering,known_request)",
                        tuple(
                            f"vehicle_{index}_analytic_actual_steering_k1"
                            for index in range(4)
                        ),
                    ),
                    predict_field(
                        "analytic_rate_mask4_k",
                        (4,),
                        "bool",
                        "known_at_t_k_via_A3_rollout",
                        "analytic_gate_context",
                        "A3_rate_clip_mask_from_current_and_known_request",
                        tuple(f"vehicle_{index}_analytic_rate_mask" for index in range(4)),
                    ),
                    predict_field(
                        "analytic_angle_mask4_k",
                        (4,),
                        "bool",
                        "known_at_t_k_via_A3_rollout",
                        "analytic_gate_context",
                        "A3_angle_clip_mask_from_current_and_known_request",
                        tuple(f"vehicle_{index}_analytic_angle_mask" for index in range(4)),
                    ),
                ]
            )
    schema = {
        "schema_id": f"{SCHEMA_PREDICT_VARIANT_ID}_{selected.lower()}",
        "variant": selected,
        "inputs": inputs,
        "labels": labels,
        "rollout_contract": (
            "measured_request_only"
            if selected == "S0"
            else "measured_actual_state"
            if selected == "S1"
            else "measured_actual_state_plus_causal_A3_analytic_rollout"
        ),
    }
    schema["contract_audit"] = validate_schema_variant_contract(schema)
    return schema


def validate_schema_variant_contract(schema: dict) -> dict:
    inputs = list(schema.get("inputs", []))
    labels = list(schema.get("labels", []))
    names = [item.get("name") for item in inputs + labels]
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("predict schema contains unnamed fields")
    if len(names) != len(set(names)):
        raise ValueError("predict schema contains duplicate field names")
    components: list[str] = []
    leaking = []
    for item in inputs:
        components.extend(str(value) for value in item.get("physical_components", []))
        source = str(item.get("source", "")).lower()
        endpoint = str(item.get("endpoint", "")).lower()
        role = str(item.get("role", "")).lower()
        if "future_measured" in source or role in {"label", "label_only"}:
            leaking.append(item["name"])
        if "t_k+1" in endpoint and not endpoint.startswith("known_at_t_k"):
            leaking.append(item["name"])
        shape = tuple(int(value) for value in item.get("shape", []))
        if not shape or __import__("math").prod(shape) != int(item.get("dimension", -1)):
            raise ValueError(f"shape/dimension mismatch: {item}")
    duplicates = sorted({value for value in components if components.count(value) > 1})
    if duplicates:
        raise ValueError(f"duplicate physical components in predict inputs: {duplicates}")
    if leaking:
        raise ValueError(f"future measured fields in predict inputs: {sorted(set(leaking))}")
    return {
        "passed": True,
        "variant": schema.get("variant"),
        "input_count": len(inputs),
        "label_count": len(labels),
        "input_dimension": sum(int(item["dimension"]) for item in inputs),
        "duplicate_physical_feature_count": 0,
        "future_measured_input_count": 0,
    }
