from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scenarios import (
    SCENARIOS,
    ScenarioSpec,
    audit_predict_pilot_identities,
    build_predict_pilot_identities,
    command_for,
    scenario_specs,
)


ROOT = Path(__file__).resolve().parents[1]


def _command(spec: ScenarioSpec, time_s: float):
    return command_for(spec, time_s, 0.0, None, None)


def test_all_twelve_specs_durations_directions_and_members() -> None:
    specs = scenario_specs(list(SCENARIOS))
    assert set(spec.scenario for spec in specs) == set(SCENARIOS)
    assert len(specs) == 21
    d9 = [spec for spec in specs if spec.scenario == "D9"]
    assert {(spec.direction, spec.member) for spec in d9} == {("none", "A"), ("none", "B")}
    assert {spec.duration_s for spec in d9} == {6.0}
    assert {spec.duration_s for spec in specs if spec.scenario == "D11"} == {10.0}


def test_new_scenario_boundaries_mirror_and_zero_mean_offsets() -> None:
    d3_left = ScenarioSpec("D3", "left", 8.0, None, True)
    d3_right = ScenarioSpec("D3", "right", 8.0, None, True)
    assert _command(d3_left, 1.0).virtual_front_deg == 0.0
    assert _command(d3_left, 2.0).virtual_front_deg == 4.0
    assert _command(d3_left, 6.0).virtual_front_deg == 4.0
    assert _command(d3_left, 7.0).virtual_front_deg == 0.0
    assert _command(d3_right, 3.0).virtual_front_deg == -_command(d3_left, 3.0).virtual_front_deg

    d4_left = ScenarioSpec("D4", "left", 8.0, None, True)
    d4_right = ScenarioSpec("D4", "right", 8.0, None, True)
    for time_s in (1.0, 2.0, 3.0, 4.0, 5.0):
        assert np.isclose(
            _command(d4_right, time_s).virtual_front_deg,
            -_command(d4_left, time_s).virtual_front_deg,
            atol=1e-15,
        )

    d7 = ScenarioSpec("D7", "none", 6.0, None, False)
    assert sum(_command(d7, 2.0).vehicle_accel_offset_mps2) == 0.0
    np.testing.assert_allclose(
        _command(d7, 4.0).vehicle_accel_offset_mps2,
        -np.asarray(_command(d7, 2.0).vehicle_accel_offset_mps2),
    )
    d8_left = ScenarioSpec("D8", "left", 6.0, None, True)
    d8_right = ScenarioSpec("D8", "right", 6.0, None, True)
    np.testing.assert_allclose(
        _command(d8_right, 2.0).vehicle_steer_offset_deg,
        -np.asarray(_command(d8_left, 2.0).vehicle_steer_offset_deg),
    )
    for member in ("A", "B"):
        d9 = ScenarioSpec("D9", "none", 6.0, None, False, member)
        primary = _command(d9, 2.0)
        reverse = _command(d9, 4.0)
        assert abs(sum(primary.vehicle_accel_offset_mps2)) <= 1e-15
        assert abs(sum(primary.vehicle_steer_offset_deg)) <= 1e-15
        np.testing.assert_allclose(reverse.vehicle_accel_offset_mps2, -np.asarray(primary.vehicle_accel_offset_mps2))
        np.testing.assert_allclose(reverse.vehicle_steer_offset_deg, -np.asarray(primary.vehicle_steer_offset_deg))


def test_d11_fade_and_mirror() -> None:
    left = ScenarioSpec("D11", "left", 10.0, None, True)
    right = ScenarioSpec("D11", "right", 10.0, None, True)
    assert _command(left, 0.0).virtual_front_deg == 0.0
    assert _command(left, 10.0).virtual_front_deg == 0.0
    for time_s in (0.5, 2.0, 8.0, 9.5):
        assert np.isclose(
            _command(right, time_s).virtual_front_deg,
            -_command(left, time_s).virtual_front_deg,
            atol=1e-15,
        )
        assert np.isclose(
            _command(right, time_s).acceleration_mps2,
            _command(left, time_s).acceleration_mps2,
            atol=1e-15,
        )


def test_dry_run_expands_exactly_126_unique_identities() -> None:
    protocol = json.loads(
        (ROOT / "config" / "protocol_predict_next.json").read_text(encoding="utf-8")
    )
    rows = build_predict_pilot_identities(protocol)
    audit = audit_predict_pilot_identities(rows, protocol)
    assert audit == {
        "passed": True,
        "trajectory_count": 126,
        "unique_identity_count": 126,
        "base_family_count": 36,
        "scenario_count": 12,
        "raw_files_written": 0,
    }

