from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np


REQUIRED_RAW_FIELDS = (
    "time_s",
    "state30",
    "requested_control4x2",
    "actual_steering_rad",
    "actual_steering_rate_substeps_radps",
    "actuator_rate_limited_mask",
    "actuator_angle_limited_mask",
    "force_payload_body_n",
    "force_direction_body_rad",
    "force_active_mask",
    "internal_force_vector_n",
    "tension_proxy_n",
    "vehicle_fxyz_body4x3_n",
    "vehicle_yaw_rate4_radps",
    "payload_yaw_rate_radps",
    "system_yaw_rate_radps",
    "payload_support_load4_n",
    "vehicle_total_normal_load4_n",
    "support_constraint_relative_residual3",
    "tire_raw_utilization",
    "action_reaction_residual4x2_n",
    "internal_null_residual3_n",
    "event_counts16",
    "smoothing_fraction",
    "command_phase",
)


def classify_window(
    arrays: dict[str, np.ndarray], start: int, stop: int, protocol: dict
) -> str:
    events = np.asarray(arrays["event_counts16"][start:stop], dtype=float)
    smoothing = np.asarray(arrays["smoothing_fraction"][start:stop], dtype=float)
    request = np.asarray(arrays["requested_control4x2"][start:stop], dtype=float)
    base_acceleration = np.asarray(arrays["base_acceleration_mps2"][start:stop], dtype=float)
    virtual_front = np.deg2rad(
        np.asarray(arrays["virtual_front_deg"][start:stop], dtype=float)
    )
    virtual_rear = np.deg2rad(
        np.asarray(arrays["virtual_rear_deg"][start:stop], dtype=float)
    )
    config = protocol["window"]
    acceleration_signal = np.c_[base_acceleration, request[:, :, 0]]
    steering_signal = np.c_[virtual_front, virtual_rear, request[:, :, 1]]
    if np.any(events > 0.0) or np.any(smoothing > 0.0):
        return "connector_event"
    # A smooth, active command is a maneuver; it is not a switch merely because
    # adjacent floating-point samples differ.  A switch requires a one-sample
    # command change larger than the already-frozen activity threshold.  The
    # numerical tolerance remains a floor rather than the semantic threshold.
    numerical_floor = float(config["control_change_atol"])
    acceleration_switch = max(
        numerical_floor, float(config["acceleration_active_mps2"])
    )
    steering_switch = max(
        numerical_floor, float(config["steering_active_rad"])
    )
    if acceleration_signal.shape[0] > 1 and (
        np.any(np.abs(np.diff(acceleration_signal, axis=0)) > acceleration_switch)
        or np.any(np.abs(np.diff(steering_signal, axis=0)) > steering_switch)
    ):
        return "switch"
    if (
        np.max(np.abs(acceleration_signal))
        > float(config["acceleration_active_mps2"])
        or np.max(np.abs(steering_signal)) > float(config["steering_active_rad"])
    ):
        return "maneuver"
    return "steady"


def window_ledger(identity: dict, arrays: dict[str, np.ndarray], protocol: dict) -> list[dict]:
    steps = int(protocol["window"]["steps"])
    rows = []
    for start in range(0, len(arrays["time_s"]) - steps + 1, steps):
        stop = start + steps
        rows.append(
            {
                "trajectory_id": int(identity["trajectory_id"]),
                "base_family_id": str(identity["base_family_id"]),
                "split": str(identity.get("split", "pilot")),
                "scenario": str(identity["scenario"]),
                "direction": str(identity["direction"]),
                "member": str(identity.get("member", "none")),
                "plant": str(identity["plant"]),
                "start": start,
                "stop_exclusive": stop,
                "steps": steps,
                "class": classify_window(arrays, start, stop, protocol),
                "within_single_trajectory": True,
            }
        )
    return rows


def direction_signal(identity: dict, arrays: dict[str, np.ndarray]) -> np.ndarray:
    """Return the frozen signed excitation used by a directional scenario."""

    if str(identity["scenario"]) == "D8":
        steering = np.asarray(arrays["requested_control4x2"], dtype=float)[:, :, 1]
        return steering @ np.asarray([1.0, -1.0, 1.0, -1.0])
    return np.asarray(arrays["virtual_front_deg"], dtype=float)


def audit_trajectory(
    identity: dict,
    arrays: dict[str, np.ndarray],
    summary: dict,
    protocol: dict,
    *,
    replay_hash_match: bool,
) -> dict:
    gates_config = protocol["physics_gates"]
    missing = sorted(set(REQUIRED_RAW_FIELDS) - set(arrays))
    numeric = [
        np.asarray(value)
        for value in arrays.values()
        if np.asarray(value).dtype.kind not in {"O", "U", "S"}
    ]
    finite = not missing and all(np.all(np.isfinite(value)) for value in numeric)
    time_s = np.asarray(arrays["time_s"], dtype=float)
    steps = np.diff(time_s)
    expected_count = (
        None
        if identity["scenario"] == "D2"
        else int(round(float(identity["duration_s"]) / float(protocol["k2"]["model_step_s"])))
    )
    completion = bool(
        summary["status"] == "PASS"
        and (
            float(summary["distance_m"]) >= float(identity["distance_target_m"])
            if identity.get("distance_target_m") is not None
            else len(time_s) == expected_count
        )
    )
    internal = np.asarray(arrays["internal_force_vector_n"], dtype=float)
    internal_null = np.asarray(arrays["internal_null_residual3_n"], dtype=float)
    internal_relative = float(np.max(np.linalg.norm(internal_null, axis=1))) / max(
        float(np.max(np.linalg.norm(internal, axis=1))), 1.0
    )
    vehicle_yaw = np.asarray(arrays["vehicle_yaw_rate4_radps"], dtype=float)
    payload_yaw = np.asarray(arrays["payload_yaw_rate_radps"], dtype=float)
    params = __import__("json").loads(summary["params_json"])["values"]
    vehicle_inertia = float(params["vehicle"]["yaw_inertia_kgm2"])
    payload_mass = float(params["payload"]["mass_kg"])
    payload_inertia = payload_mass * (
        float(params["payload"]["length_m"]) ** 2
        + float(params["payload"]["width_m"]) ** 2
    ) / 12.0
    recomputed_system_yaw = (
        vehicle_inertia * np.sum(vehicle_yaw, axis=1) + payload_inertia * payload_yaw
    ) / (4.0 * vehicle_inertia + payload_inertia)
    system_yaw_error = float(
        np.max(
            np.abs(
                recomputed_system_yaw
                - np.asarray(arrays["system_yaw_rate_radps"], dtype=float)
            )
        )
    )
    signed_excitation = direction_signal(identity, arrays)
    nonzero_front = np.flatnonzero(np.abs(signed_excitation) > 1.0e-9)
    if identity["direction"] == "left":
        direction_passed = bool(
            nonzero_front.size and signed_excitation[nonzero_front[0]] > 0.0
        )
    elif identity["direction"] == "right":
        direction_passed = bool(
            nonzero_front.size and signed_excitation[nonzero_front[0]] < 0.0
        )
    else:
        direction_passed = True
    gates = {
        "field_complete": not missing,
        "finite": finite,
        "time_grid": bool(
            steps.size
            and np.all(steps > 0.0)
            and np.max(np.abs(steps - float(protocol["k2"]["model_step_s"])))
            <= float(gates_config["time_step_atol_s"])
        ),
        "completion": completion,
        "replay": bool(replay_hash_match),
        "action_reaction": float(
            np.max(np.abs(np.asarray(arrays["action_reaction_residual4x2_n"], dtype=float)))
        )
        <= float(gates_config["action_reaction_atol_n"]),
        "internal_null": internal_relative
        <= float(gates_config["internal_null_relative_atol"]),
        "support_nonnegative": float(
            np.min(np.asarray(arrays["payload_support_load4_n"], dtype=float))
        )
        >= float(gates_config["support_min_atol_n"]),
        "support_conservation": float(
            np.max(
                np.abs(
                    np.asarray(
                        arrays["support_constraint_relative_residual3"], dtype=float
                    )
                )
            )
        )
        <= float(gates_config["support_constraint_relative_atol"]),
        "tire": float(np.max(np.asarray(arrays["tire_raw_utilization"], dtype=float)))
        <= float(gates_config["tire_raw_utilization_max"]),
        "connector_ultimate": not bool(summary["ultimate_force_exceeded"]),
        "actuator_rate": float(
            np.max(
                np.abs(
                    np.asarray(arrays["actual_steering_rate_substeps_radps"], dtype=float)
                )
            )
        )
        <= float(protocol["actuator"]["rate_max_radps"])
        + float(gates_config["actuator_rate_atol_radps"]),
        "actuator_angle": float(
            np.max(np.abs(np.asarray(arrays["actual_steering_rad"], dtype=float)))
        )
        <= np.deg2rad(float(protocol["actuator"]["angle_max_deg"]))
        + float(gates_config["actuator_angle_atol_rad"]),
        "system_yaw_definition": system_yaw_error <= 1.0e-12,
        "direction": direction_passed,
    }
    windows = window_ledger(identity, arrays, protocol)
    return {
        **identity,
        "passed": all(gates.values()),
        "failed_gates": [key for key, passed in gates.items() if not passed],
        "sample_count": len(time_s),
        "runtime_s": float(summary["runtime_s"]),
        "force_peak_n": float(np.max(np.linalg.norm(arrays["force_payload_body_n"], axis=2))),
        "tire_raw_utilization_max": float(
            np.max(np.asarray(arrays["tire_raw_utilization"], dtype=float))
        ),
        "support_min_n": float(
            np.min(np.asarray(arrays["payload_support_load4_n"], dtype=float))
        ),
        "internal_null_relative": internal_relative,
        "action_reaction_max_n": float(
            np.max(np.abs(np.asarray(arrays["action_reaction_residual4x2_n"], dtype=float)))
        ),
        "actuator_rate_peak_radps": float(
            np.max(np.abs(arrays["actual_steering_rate_substeps_radps"]))
        ),
        "actuator_angle_peak_rad": float(np.max(np.abs(arrays["actual_steering_rad"]))),
        "rate_mask_fraction": float(np.mean(arrays["actuator_rate_limited_mask"])),
        "angle_mask_fraction": float(np.mean(arrays["actuator_angle_limited_mask"])),
        "system_yaw_definition_max_abs_radps": system_yaw_error,
        "window_counts": dict(Counter(row["class"] for row in windows)),
        **{f"gate_{key}": bool(value) for key, value in gates.items()},
    }


def mirror_audit(
    trajectories: list[tuple[dict, dict[str, np.ndarray]]], protocol: dict
) -> dict:
    groups: dict[tuple[str, str, str], dict[str, dict[str, np.ndarray]]] = defaultdict(dict)
    for identity, arrays in trajectories:
        if identity["direction"] in {"left", "right"}:
            key = (identity["scenario"], identity["parameter_family"], identity["plant"])
            groups[key][identity["direction"]] = arrays
    rows = []
    mirror_index = np.asarray([1, 0, 3, 2])
    for key, directions in groups.items():
        if set(directions) != {"left", "right"}:
            continue
        left, right = directions["left"], directions["right"]
        count = min(len(left["time_s"]), len(right["time_s"]))
        if key[0] == "D8":
            # D8 reverses an internal lateral shear command at fixed endpoints;
            # it is a polarity pair, not a global left/right path reflection.
            lf = -np.asarray(left["force_payload_body_n"][:count])
        else:
            lf = np.asarray(left["force_payload_body_n"][:count])[:, mirror_index] * np.asarray([1.0, -1.0])
        rf = np.asarray(right["force_payload_body_n"][:count])
        scale = max(float(np.max(np.abs(np.r_[lf.ravel(), rf.ravel()]))), 1.0)
        force_relative = float(np.max(np.abs(lf - rf))) / scale
        yaw_relative = float(
            np.max(
                np.abs(
                    np.asarray(left["system_yaw_rate_radps"][:count])
                    + np.asarray(right["system_yaw_rate_radps"][:count])
                )
            )
        ) / max(
            float(
                np.max(
                    np.abs(
                        np.r_[
                            left["system_yaw_rate_radps"][:count],
                            right["system_yaw_rate_radps"][:count],
                        ]
                    )
                )
            ),
            1.0e-9,
        )
        error = max(force_relative, yaw_relative)
        rows.append(
            {
                "scenario": key[0],
                "parameter_family": key[1],
                "plant": key[2],
                "force_relative_error": force_relative,
                "system_yaw_relative_error": yaw_relative,
                "max_relative_error": error,
                "passed": error <= float(protocol["physics_gates"]["mirror_relative_atol"]),
            }
        )
    return {
        "passed": bool(rows) and all(row["passed"] for row in rows),
        "pair_count": len(rows),
        "max_relative_error": max((row["max_relative_error"] for row in rows), default=float("inf")),
        "rows": rows,
    }


def coverage_audit(audit_rows: list[dict], protocol: dict) -> dict:
    dynamic = {"maneuver", "switch", "connector_event"}
    required = {scenario: set(dynamic) for scenario in protocol["scenarios"]["order"]}
    required["D0"] = {"steady"}
    required["D3"].add("steady")
    available: dict[str, set[str]] = defaultdict(set)
    for row in audit_rows:
        available[row["scenario"]].update(
            name for name, count in row["window_counts"].items() if int(count) > 0
        )
    scenario_rows = []
    for scenario in protocol["scenarios"]["order"]:
        expected = required[scenario]
        passed = bool(expected & available[scenario])
        scenario_rows.append(
            {
                "scenario": scenario,
                "accepted_classes": sorted(expected),
                "available_classes": sorted(available[scenario]),
                "passed": passed,
            }
        )
    return {"passed": all(row["passed"] for row in scenario_rows), "rows": scenario_rows}
