from __future__ import annotations

import json
from pathlib import Path

from connector_r3 import ConnectorR3Params


PARAMETER_UNITS = {
    "stiffness_npm": "N/m",
    "damping_nspm": "N*s/m",
    "free_play_m": "m",
    "smoothing_width_m": "m",
    "rated_force_n": "N",
    "ultimate_force_n": "N",
}

SCHEMA_ID = "r3_4_force_interval_v2"
STATE_SETS = {"S1_team": 12, "S2_four": 30, "S3_deform": 46, "S4_force_in": 64}


def _field(name: str, unit: str, frame: str, time: str = "t_k", role: str = "input_and_label") -> dict:
    return {"name": name, "unit": unit, "frame": frame, "time": time, "role": role}


def _six_state(prefix: str, frame: str) -> list[dict]:
    return [
        _field(f"{prefix}_x_m", "m", "world"),
        _field(f"{prefix}_y_m", "m", "world"),
        _field(f"{prefix}_yaw_rad", "rad", "world"),
        _field(f"{prefix}_vx_mps", "m/s", frame),
        _field(f"{prefix}_vy_mps", "m/s", frame),
        _field(f"{prefix}_yaw_rate_radps", "rad/s", frame),
    ]


def _side_array(name: str, dimension: int, unit: str, frame: str, time: str = "completed_interval_e_k") -> dict:
    return {
        "name": name,
        "dimension": dimension,
        "unit": unit,
        "frame": frame,
        "time": time,
        "role": "causal_side_input",
    }


def build_schema(state_set: str = "S4_force_in") -> dict:
    requested = state_set
    if state_set == "S4_force_event":
        state_set = "S4_force_in"
    if state_set not in STATE_SETS:
        raise ValueError(f"unknown state_set: {requested}")

    payload = _six_state("payload", "payload_body")
    team_aggregate = [
        _field("team_vehicle_x_mean_m", "m", "world"),
        _field("team_vehicle_y_mean_m", "m", "world"),
        _field("team_vehicle_yaw_circular_mean_rad", "rad", "world"),
        _field("team_vehicle_speed_mean_mps", "m/s", "vehicle_body"),
        _field("team_vehicle_lateral_speed_mean_mps", "m/s", "vehicle_body"),
        _field("team_vehicle_yaw_rate_mean_radps", "rad/s", "vehicle_body"),
    ]
    s1 = payload + team_aggregate
    s2 = sum((_six_state(f"vehicle_{index}", "vehicle_body") for index in range(4)), []) + payload
    deformation = [
        _field(f"deformation_{index}_{axis}_m", "m", "world", role="input")
        for index in range(4)
        for axis in ("x", "y")
    ] + [
        _field(f"relative_velocity_{index}_{axis}_mps", "m/s", "world", role="input")
        for index in range(4)
        for axis in ("x", "y")
    ]
    s3 = s2 + deformation
    historical_force = [
        _field(
            f"force_body_{index}_{axis}_n",
            "N",
            "payload_body",
            "completed_interval_e_k",
            "causal_input",
        )
        for index in range(4)
        for axis in ("x", "y")
    ]
    legacy_q = [
        _field("q_fr_n", "N", "payload_body", "completed_interval_e_k", "causal_input"),
        _field("q_lr_n", "N", "payload_body", "completed_interval_e_k", "causal_input"),
    ]
    force_rate = [
        _field(
            f"force_rate_body_{index}_{axis}_nps",
            "N/s",
            "payload_body",
            "completed_interval_e_k",
            "causal_input",
        )
        for index in range(4)
        for axis in ("x", "y")
    ]
    states = {
        "S1_team": s1,
        "S2_four": s2,
        "S3_deform": s3,
        "S4_force_in": s3 + historical_force + legacy_q + force_rate,
    }
    fields = states[state_set]
    if len(fields) != STATE_SETS[state_set]:
        raise AssertionError(f"{state_set} dimension drift: {len(fields)}")
    names = [item["name"] for item in fields]
    if len(names) != len(set(names)):
        raise ValueError("duplicate schema fields")

    side_arrays = [
        _side_array("internal_force8", 8, "N", "payload_body"),
        _side_array("tension_proxy2", 2, "N", "payload_body"),
        _side_array("force_interval_mean8", 8, "N", "world"),
        _side_array("force_interval_impulse8", 8, "N*s", "world"),
        _side_array("contact_fraction4", 4, "1", "connector"),
        _side_array("smoothing_fraction4", 4, "1", "connector"),
        _side_array("smoothing_weight_mean4", 4, "1", "connector"),
        _side_array("event_counts16", 16, "count", "connector_surface_direction"),
        _side_array("force_active_mask4", 4, "bool", "connector", "t_k"),
        _side_array("network_mask", 0, "bool", "network", "network_stage_only"),
        _side_array("network_aoi", 0, "s", "network", "network_stage_only"),
    ]
    controls = [
        {"name": f"vehicle_{index}_{kind}", "unit": unit, "frame": "vehicle_body", "time": "u_k"}
        for index in range(4)
        for kind, unit in (("acceleration_mps2", "m/s^2"), ("steering_rad", "rad"))
    ]
    return {
        "schema_id": SCHEMA_ID,
        "requested_state_set": requested,
        "state_set": state_set,
        "dimension": len(fields),
        "fields": fields,
        "control_dimension": len(controls),
        "controls": controls,
        "side_arrays": side_arrays,
    }


def params_from_delta_freeze(path: Path) -> ConnectorR3Params:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not data.get("passed") or data.get("development_read") or data.get("confirm_read"):
        raise ValueError("R3 parameters require a passed train-only R0 freeze")
    return ConnectorR3Params(smoothing_width_m=float(data["smoothing_width_m"]))
