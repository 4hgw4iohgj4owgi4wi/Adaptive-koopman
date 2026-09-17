from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import numpy as np

from audit_icr_fix import (
    actuator_attribution,
    audit_trajectory as audit_trajectory_legacy_metrics,
    compare_common_fields,
    write_csv,
)


COUNTERFACTUAL_MODES = frozenset({"A0", "A1"})
DEPLOYMENT_MODES = frozenset({"A2", "A3"})


def _first_true(mask: np.ndarray) -> tuple[int, ...] | None:
    locations = np.argwhere(np.asarray(mask, dtype=bool))
    return None if not len(locations) else tuple(int(value) for value in locations[0])


def _domain_event(
    *,
    identity: dict,
    arrays: Mapping[str, np.ndarray],
    gate: str,
    values: np.ndarray,
    mask: np.ndarray,
    threshold: float,
    protocol: dict,
) -> dict | None:
    location = _first_true(mask)
    if location is None:
        return None
    sample = int(location[0])
    substep = int(location[1]) if len(location) == 3 else None
    vehicle = int(location[-1]) if len(location) >= 2 else None
    time_s = float(np.asarray(arrays["time_s"], dtype=float)[sample])
    if substep is not None:
        time_s = time_s - float(protocol["k2"]["model_step_s"]) + (
            substep + 1
        ) * float(protocol["k2"]["plant_step_s"])
    return {
        "trajectory_id": identity["trajectory_id"],
        "direction": identity["direction"],
        "plant": identity["plant"],
        "actuator_mode": identity["actuator_mode"],
        "gate": gate,
        "threshold": float(threshold),
        "first_sample_index": sample,
        "first_substep_index": substep,
        "vehicle_index_zero_based": vehicle,
        "vehicle_index_one_based": None if vehicle is None else vehicle + 1,
        "first_time_s": time_s,
        "phase": str(np.asarray(arrays["command_phase"]).astype(str)[sample]),
        "distance_m": float(np.asarray(arrays["distance_m"], dtype=float)[sample]),
        "first_value": float(np.asarray(values, dtype=float)[location]),
        "peak_abs_or_max": float(np.max(np.abs(np.asarray(values, dtype=float)))),
        "valid_interval_end_sample_exclusive": sample,
        "valid_interval_end_time_s": float(
            np.asarray(arrays["time_s"], dtype=float)[max(sample - 1, 0)]
        ),
    }


def counterfactual_domain_events(
    identity: dict,
    arrays: Mapping[str, np.ndarray],
    summary: dict,
    protocol: dict,
) -> list[dict]:
    """Return every first deployment-domain violation without hiding the raw trajectory."""

    rate_limit = float(protocol["actuator"]["rate_max_radps"])
    angle_limit = float(np.deg2rad(protocol["actuator"]["angle_max_deg"]))
    tire_limit = float(protocol["f3"]["tire_raw_utilization_max"])
    support_limit = float(protocol["f3"]["support_min_atol_n"])
    params = json.loads(summary["params_json"])["values"]
    connector_limit = float(params["connector"]["ultimate_force_n"])
    rate = np.abs(np.asarray(arrays["actual_steering_rate_substeps_radps"], dtype=float))
    angle = np.abs(np.asarray(arrays["actual_steering_substeps_rad"], dtype=float))
    tire = np.asarray(arrays["tire_raw_utilization"], dtype=float)
    support = np.asarray(arrays["payload_support_load4_n"], dtype=float)
    connector = np.linalg.norm(
        np.asarray(arrays["force_payload_body_n"], dtype=float), axis=2
    )
    candidates = (
        ("actuator_rate", rate, rate > rate_limit, rate_limit),
        ("actuator_angle", angle, angle > angle_limit + float(protocol["f3"]["angle_atol_rad"]), angle_limit),
        ("tire", tire, tire > tire_limit, tire_limit),
        ("support_nonnegative", support, support < support_limit, support_limit),
        ("connector_ultimate", connector, connector > connector_limit, connector_limit),
    )
    return [
        event
        for gate, values, mask, threshold in candidates
        if (
            event := _domain_event(
                identity=identity,
                arrays=arrays,
                gate=gate,
                values=values,
                mask=mask,
                threshold=threshold,
                protocol=protocol,
            )
        )
        is not None
    ]


def audit_trajectory(
    identity: dict,
    arrays: Mapping[str, np.ndarray],
    summary: dict,
    protocol: dict,
    parent_comparison: dict | None,
) -> dict:
    """Split evidence integrity from deployment feasibility by actuator identity."""

    legacy = audit_trajectory_legacy_metrics(
        identity, arrays, summary, protocol, parent_comparison
    )
    legacy.pop("passed", None)
    if {
        "actual_steering_substeps_rad",
        "payload_support_load4_n",
    }.issubset(arrays) and "params_json" in summary:
        params = json.loads(summary["params_json"])["values"]
        support = np.asarray(arrays["payload_support_load4_n"], dtype=float)
        expected_support_n = float(
            params["payload"]["mass_kg"] * params["payload"]["gravity_mps2"]
        )
        legacy["actual_angle_peak_rad"] = float(
            np.max(
                np.abs(
                    np.asarray(arrays["actual_steering_substeps_rad"], dtype=float)
                )
            )
        )
        legacy["support_sum_residual_max_n"] = float(
            np.max(np.abs(np.sum(support, axis=1) - expected_support_n))
        )
    else:
        for required in ("actual_angle_peak_rad", "support_sum_residual_max_n"):
            if required not in legacy:
                raise KeyError(f"semantic stub or raw evidence is missing {required}")
    mode = str(identity["actuator_mode"])
    if mode not in COUNTERFACTUAL_MODES | DEPLOYMENT_MODES:
        raise ValueError(f"unknown actuator mode: {mode}")
    diagnostic_names = tuple(protocol["gate_semantics"]["diagnostic_hard_all_modes"])
    diagnostic_gates = {
        name: bool(legacy[f"gate_{name}"]) for name in diagnostic_names
    }
    if mode == "A3":
        diagnostic_gates["a3_parent_common_fields"] = bool(
            legacy["gate_a3_parent_common_fields"]
        )
    diagnostic_passed = all(diagnostic_gates.values())
    events = counterfactual_domain_events(identity, arrays, summary, protocol)

    actual_deployment_gates = {
        "actuator_rate": float(legacy["actual_rate_peak_radps"])
        <= float(protocol["actuator"]["rate_max_radps"])
        + float(protocol["f3"]["rate_atol_radps"]),
        "actuator_angle": bool(legacy["gate_actuator_angle"]),
        "tire": bool(legacy["gate_tire"]),
        "support_nonnegative": bool(legacy["gate_support_nonnegative"]),
        "connector_ultimate": bool(legacy["gate_connector_ultimate"]),
        "a3_parent_common_fields": bool(legacy["gate_a3_parent_common_fields"]),
    }
    if mode in COUNTERFACTUAL_MODES:
        deployment_names: tuple[str, ...] = ()
        deployment_feasibility = "NOT_APPLICABLE"
        deployment_passed = None
    elif mode == "A2":
        deployment_names = tuple(protocol["gate_semantics"]["a2_deployment_hard"])
        deployment_passed = all(actual_deployment_gates[name] for name in deployment_names)
        deployment_feasibility = "PASS" if deployment_passed else "FAIL"
    else:
        deployment_names = tuple(protocol["gate_semantics"]["a3_deployment_hard"])
        deployment_passed = all(actual_deployment_gates[name] for name in deployment_names)
        deployment_feasibility = "PASS" if deployment_passed else "FAIL"

    stage_blocking = bool(
        not diagnostic_passed
        or (mode in DEPLOYMENT_MODES and deployment_feasibility == "FAIL")
    )
    counterfactual_ood = bool(mode in COUNTERFACTUAL_MODES and events)
    if not diagnostic_passed:
        semantic_status = "BLOCKED_DIAGNOSTIC_INTEGRITY"
    elif mode in DEPLOYMENT_MODES and deployment_feasibility == "FAIL":
        semantic_status = "BLOCKED_PHYSICAL_BASELINE"
    elif counterfactual_ood:
        semantic_status = "PASS_DIAGNOSTIC_WITH_COUNTERFACTUAL_OOD"
    else:
        semantic_status = "PASS"
    return {
        **legacy,
        "diagnostic_integrity": "PASS" if diagnostic_passed else "FAIL",
        "diagnostic_failed_gates": json.dumps(
            [name for name, passed in diagnostic_gates.items() if not passed]
        ),
        "deployment_feasibility": deployment_feasibility,
        "deployment_failed_gates": json.dumps(
            [
                name
                for name in deployment_names
                if not actual_deployment_gates[name]
            ]
        ),
        "counterfactual_ood": counterfactual_ood,
        "counterfactual_domain_event_count": len(events),
        "valid_interval_end_sample_exclusive": min(
            [event["valid_interval_end_sample_exclusive"] for event in events],
            default=len(np.asarray(arrays["time_s"])),
        ),
        "semantic_status": semantic_status,
        "stage_blocking": stage_blocking,
        **{
            f"deployment_report_{name}": passed
            for name, passed in actual_deployment_gates.items()
        },
    }


def aggregate_stage(rows: list[dict], events: list[dict], protocol: dict) -> dict:
    expected = {
        (direction, plant["name"], mode)
        for direction in protocol["n2"]["directions"]
        for plant in protocol["n2"]["plants"]
        for mode in protocol["n2"]["mathematical_mode_order"]
    }
    actual = {
        (str(row["direction"]), str(row["plant"]), str(row["actuator_mode"]))
        for row in rows
    }
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    duplicate_count = len(rows) - len(actual)
    diagnostic_failures = [
        row for row in rows if row["diagnostic_integrity"] != "PASS"
    ]
    deployment_failures = [
        row
        for row in rows
        if row["actuator_mode"] in DEPLOYMENT_MODES
        and row["deployment_feasibility"] != "PASS"
    ]
    counterfactual_ood_count = sum(bool(row["counterfactual_ood"]) for row in rows)
    if missing or unexpected or duplicate_count:
        status = "BLOCKED_DIAGNOSTIC_INTEGRITY"
    elif diagnostic_failures:
        status = "BLOCKED_DIAGNOSTIC_INTEGRITY"
    elif deployment_failures:
        status = "BLOCKED_PHYSICAL_BASELINE"
    elif counterfactual_ood_count:
        status = "PASS_DIAGNOSTIC_WITH_COUNTERFACTUAL_OOD"
    else:
        status = "PASS"
    return {
        "stage_status": status,
        "stage_passed": status in {"PASS", "PASS_DIAGNOSTIC_WITH_COUNTERFACTUAL_OOD"},
        "trajectory_count": len(rows),
        "expected_trajectory_count": len(expected),
        "missing_identities": missing,
        "unexpected_identities": unexpected,
        "duplicate_identity_count": duplicate_count,
        "diagnostic_failure_count": len(diagnostic_failures),
        "deployment_failure_count": len(deployment_failures),
        "counterfactual_ood_trajectory_count": counterfactual_ood_count,
        "counterfactual_domain_event_count": len(events),
        "a3_parent_common_max_abs": max(
            float(row["a3_parent_common_max_abs"])
            for row in rows
            if row["actuator_mode"] == "A3"
        ),
        "g0_peak_max_mps": max(float(row["g0_peak_mps"]) for row in rows),
    }


def audit_run(
    trajectories: list[tuple[dict, dict[str, np.ndarray], dict]],
    protocol: dict,
    parent_arrays: dict[tuple[str, str], dict[str, np.ndarray]],
    output: Path,
) -> dict:
    rows: list[dict] = []
    comparisons: list[dict] = []
    events: list[dict] = []
    switching_stretch_rows: list[dict] = []
    for identity, arrays, summary in trajectories:
        comparison = None
        if identity["actuator_mode"] == "A3":
            comparison = compare_common_fields(
                arrays, parent_arrays[(identity["direction"], identity["plant"])]
            )
            comparisons.append({**identity, **comparison})
        row = audit_trajectory(identity, arrays, summary, protocol, comparison)
        rows.append(row)
        if identity["actuator_mode"] in COUNTERFACTUAL_MODES:
            events.extend(counterfactual_domain_events(identity, arrays, summary, protocol))
        phase = np.asarray(arrays["command_phase"]).astype(str)
        tension = np.asarray(arrays["tension_proxy_n"], dtype=float)
        dt_s = float(protocol["k2"]["model_step_s"])
        window_steps = int(
            round(float(protocol["f3"]["switching_window_s"]) / dt_s)
        )
        starts = [
            index
            for index in range(1, len(phase))
            if phase[index] != phase[index - 1]
            and phase[index] in {"STEP_PRIMARY", "STEP_REVERSE", "DECEL"}
        ]
        for switch_number, start in enumerate(starts, start=1):
            stop = min(start + window_steps, len(phase))
            segment = tension[start:stop]
            switching_stretch_rows.append(
                {
                    **identity,
                    "switch_number": switch_number,
                    "phase": phase[start],
                    "start_sample_index": start,
                    "start_time_s": float(arrays["time_s"][start]),
                    "window_end_sample_exclusive": stop,
                    "window_duration_s": float((stop - start) * dt_s),
                    "front_rear_abs_impulse_ns": float(
                        np.sum(np.abs(segment[:, 0])) * dt_s
                    ),
                    "left_right_abs_impulse_ns": float(
                        np.sum(np.abs(segment[:, 1])) * dt_s
                    ),
                    "front_rear_peak_n": float(np.max(segment[:, 0])),
                    "left_right_peak_n": float(np.max(segment[:, 1])),
                }
            )
    write_csv(output / "physics_audit.csv", rows)
    write_csv(output / "a3_parent_comparison.csv", comparisons)
    if events:
        write_csv(output / "counterfactual_domain_events.csv", events)
    else:
        (output / "counterfactual_domain_events.csv").write_text(
            "trajectory_id,direction,plant,actuator_mode,gate\n", encoding="utf-8-sig"
        )
    modes, contributions = actuator_attribution(rows)
    write_csv(output / "actuator_attribution.csv", modes)
    write_csv(output / "actuator_contributions.csv", contributions)
    write_csv(output / "stretch_switching_impulse.csv", switching_stretch_rows)
    result = aggregate_stage(rows, events, protocol)
    (output / "audit_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return result
