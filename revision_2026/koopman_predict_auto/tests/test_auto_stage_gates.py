from pathlib import Path

import pytest

from contracts import (
    StageDecision,
    assert_stage_allowed,
    decide_stage_status,
    require_stage_transition,
)
from physics_audit import classify_window, coverage_audit, direction_signal
import numpy as np


@pytest.mark.parametrize("kind", ["physics", "causality", "data_identity", "raw_missing"])
def test_hard_gate_fault_injection_blocks_and_does_not_create_next_stage(tmp_path: Path, kind: str):
    next_stage = tmp_path / "n5"
    decision = decide_stage_status(
        hard_gates={"injected": False}, failure_kinds={"injected": kind}
    )
    assert decision is StageDecision.BLOCKED_HUMAN_REQUIRED
    if decision in {StageDecision.PASS_CONTINUE, StageDecision.PASS_WITH_WARNING_CONTINUE}:
        next_stage.mkdir()
    assert not next_stage.exists()


def test_only_registered_non_scientific_failure_is_repairable():
    assert decide_stage_status(
        hard_gates={"path": False}, failure_kinds={"path": "path"}
    ) is StageDecision.REPAIR_CURRENT_STAGE
    assert decide_stage_status(
        hard_gates={"unknown": False}, failure_kinds={"unknown": "unclassified"}
    ) is StageDecision.BLOCKED_HUMAN_REQUIRED


def test_transition_table_and_forbidden_boundary():
    require_stage_transition("N4-S", "N4")
    with pytest.raises(PermissionError):
        require_stage_transition("N4", "N6")
    for forbidden in ("C1", "K1", "MPC", "NETWORK", "DOS", "CONFIRM"):
        with pytest.raises(PermissionError):
            assert_stage_allowed(forbidden)


def test_d8_direction_uses_internal_steering_pattern_not_zero_virtual_front():
    steering = np.zeros((3, 4, 2))
    steering[1:, :, 1] = np.deg2rad([0.8, -0.8, 0.8, -0.8])
    arrays = {"requested_control4x2": steering, "virtual_front_deg": np.zeros(3)}
    signal = direction_signal({"scenario": "D8"}, arrays)
    assert signal[1] > 0.0


def test_window_coverage_accepts_priority_connector_event_for_dynamic_scenarios():
    protocol = {"scenarios": {"order": [f"D{i}" for i in range(12)]}}
    rows = []
    for scenario in protocol["scenarios"]["order"]:
        rows.append({"scenario": scenario, "window_counts": {"steady" if scenario == "D0" else "connector_event": 1}})
    assert coverage_audit(rows, protocol)["passed"]


def test_window_classifier_separates_smooth_maneuver_from_step_switch():
    count = 20
    arrays = {
        "event_counts16": np.zeros((count, 16)),
        "smoothing_fraction": np.zeros((count, 4)),
        "requested_control4x2": np.zeros((count, 4, 2)),
        "base_acceleration_mps2": np.linspace(0.10, 0.20, count),
        "virtual_front_deg": np.zeros(count),
        "virtual_rear_deg": np.zeros(count),
    }
    protocol = {
        "window": {
            "control_change_atol": 1.0e-12,
            "acceleration_active_mps2": 0.05,
            "steering_active_rad": np.deg2rad(0.5),
        }
    }
    assert classify_window(arrays, 0, count, protocol) == "maneuver"
    arrays["base_acceleration_mps2"][10:] += 0.10
    assert classify_window(arrays, 0, count, protocol) == "switch"
