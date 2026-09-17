from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from audit_physics_v2 import audit_array_contracts


def synthetic_contract() -> tuple[dict[str, np.ndarray], dict, dict]:
    root = Path(__file__).resolve().parents[1]
    protocol = json.loads(
        (root / "config" / "protocol_v2.json").read_text(encoding="utf-8")
    )
    count = 520
    phase = np.asarray(
        ["ACCEL_TO_30M"] * 10
        + ["STEP_PRIMARY"] * 250
        + ["STEP_REVERSE"] * 250
        + ["DECEL"] * 10
    )
    front = np.zeros(count)
    rear = np.zeros(count)
    front[phase == "STEP_PRIMARY"] = 5.0
    rear[phase == "STEP_PRIMARY"] = -2.5
    front[phase == "STEP_REVERSE"] = -5.0
    rear[phase == "STEP_REVERSE"] = 2.5
    acceleration = np.zeros(count)
    acceleration[phase == "ACCEL_TO_30M"] = 0.25
    arrays = {
        "time_s": np.arange(1, count + 1, dtype=float) * 0.020,
        "actual_steering_substeps_rad": np.zeros((count, 10, 4)),
        "actual_steering_rate_substeps_radps": np.zeros((count, 10, 4)),
        "tire_raw_utilization": np.full((count, 4), 0.8),
        "requested_icr_residual_mps": np.zeros(count),
        "actual_steering_icr_residual_mps": np.zeros(count),
        "command_phase": phase,
        "virtual_front_deg": front,
        "virtual_rear_deg": rear,
        "base_acceleration_mps2": acceleration,
    }
    summary = {
        "status": "PASS",
        "distance_m": 100.01,
        "distance_overshoot_m": 0.01,
        "internal_null_max_n": 0.0,
        "internal_force_peak_n": 10.0,
        "action_reaction_max_n": 0.0,
        "force_peak_n": 100.0,
        "rated_force_exceeded": False,
        "ultimate_force_exceeded": False,
    }
    return arrays, summary, protocol


def test_fault_injection_detects_rate_and_tire_failures() -> None:
    arrays, summary, protocol = synthetic_contract()
    good = audit_array_contracts(arrays, summary, protocol, "dynamic")
    assert good["passed"]
    bad_rate = {key: np.asarray(value).copy() for key, value in arrays.items()}
    bad_rate["actual_steering_rate_substeps_radps"][7, 3, 1] = 1.21
    rate_result = audit_array_contracts(bad_rate, summary, protocol, "dynamic")
    assert not rate_result["gates"]["rate"]
    bad_tire = {key: np.asarray(value).copy() for key, value in arrays.items()}
    bad_tire["tire_raw_utilization"][11, 2] = 0.91
    tire_result = audit_array_contracts(bad_tire, summary, protocol, "dynamic")
    assert not tire_result["gates"]["tire_raw_utilization"]
