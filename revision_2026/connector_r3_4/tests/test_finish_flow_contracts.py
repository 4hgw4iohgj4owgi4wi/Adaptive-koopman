from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from event_substep import EventSubstepConfig, _vehicle_step_size, advance_outer_step
from four_vehicle_common import ModelParams, connector_diagnostics, initialize_state, split_state
from paired_maneuvers_r3 import scenario_command
from schema_r3 import build_schema


def _q99_state():
    params = ModelParams()
    state = initialize_state(params, 1.5)
    vehicles, payload = split_state(state)
    speed = 0.2006325726682664
    directions = params.payload_anchor_body_m / np.linalg.norm(params.payload_anchor_body_m, axis=1)[:, None]
    for index, contact_time in enumerate((0.0008, 0.0010, 0.0012, 0.0014)):
        vehicles[index, :2] += directions[index] * (params.connector.free_play_m - speed * contact_time)
        vehicles[index, 3:5] = payload[3:5] + speed * directions[index]
    state[:24] = vehicles.ravel()
    return params, state


def test_finish_schema_dimensions_units_and_side_arrays():
    for state_set, dimension in (("S1_team", 12), ("S2_four", 30), ("S3_deform", 46), ("S4_force_in", 64)):
        schema = build_schema(state_set)
        assert schema["dimension"] == dimension
        assert len(schema["fields"]) == dimension
        assert all(field["unit"] != "mixed_si" for field in schema["fields"])
    alias = build_schema("S4_force_event")
    assert alias["state_set"] == "S4_force_in" and alias["dimension"] == 64
    side = {item["name"]: item["dimension"] for item in alias["side_arrays"]}
    assert side == {
        "internal_force8": 8,
        "tension_proxy2": 2,
        "force_interval_mean8": 8,
        "force_interval_impulse8": 8,
        "contact_fraction4": 4,
        "smoothing_fraction4": 4,
        "smoothing_weight_mean4": 4,
        "event_counts16": 16,
        "force_active_mask4": 4,
        "network_mask": 0,
        "network_aoi": 0,
    }
    with pytest.raises(ValueError):
        build_schema("unknown")


def test_finish_directional_commands_are_zero_mean_distinct_and_seeded():
    names = ("connector_longitudinal", "connector_lateral", "connector_diagonal_1", "connector_diagonal_2")
    vectors = []
    for name in names:
        command = scenario_command(name, 0.75, seed=0)
        accel = np.asarray(command.vehicle_accel_offset_mps2)
        steer = np.asarray(command.vehicle_steer_offset_deg)
        assert abs(np.sum(accel)) <= 1e-15
        assert abs(np.sum(steer)) <= 1e-15
        vectors.append(np.r_[accel, steer])
        inactive = scenario_command(name, 0.25, seed=0)
        np.testing.assert_allclose(inactive.vehicle_accel_offset_mps2, 0.0)
        np.testing.assert_allclose(inactive.vehicle_steer_offset_deg, 0.0)
    assert len({tuple(vector) for vector in vectors}) == 4
    assert scenario_command(names[0], 0.75, seed=1).vehicle_accel_offset_mps2 != scenario_command(names[0], 0.75, seed=0).vehicle_accel_offset_mps2


def test_finish_inactive_force_direction_is_numeric_with_mask():
    params = ModelParams()
    diagnostics = connector_diagnostics(initialize_state(params), params, "R3")
    assert np.all(np.isfinite(diagnostics["force_direction_body_rad"]))
    assert not np.any(diagnostics["force_active_mask"])


def test_finish_vehicle_candidate_origin_and_interval_audit_contract():
    params, state = _q99_state()
    config = EventSubstepConfig()
    zone_state = state.copy()
    vehicles, _ = split_state(zone_state)
    directions = params.payload_anchor_body_m / np.linalg.norm(params.payload_anchor_body_m, axis=1)[:, None]
    vehicles[:, :2] += directions * (0.2006325726682664 * 0.0006)
    zone_state[:24] = vehicles.ravel()
    _, origin, unresolved = _vehicle_step_size(zone_state, 0.002, params, config, config.probe_step_s)
    assert origin == "ZONE_RESOLUTION" and not unresolved
    _, audit = advance_outer_step(state, np.zeros((4, 2)), "R3", params, 0.002, "ES", config)
    assert audit["status"] == "PASS"
    assert any(record["selection_cause"] == "EVENT_ROOT" for record in audit["step_records"])
    assert all(record["candidate_origin"] in {"OUTER_REMAINDER", "PROBE_LIMIT", "ZONE_RESOLUTION"} for record in audit["step_records"])
    required = {
        "force_payload_body_n",
        "force_interval_impulse_world_ns",
        "internal_force_vector_n",
        "tension_x_n",
        "tension_y_n",
        "force_direction_body_rad",
        "force_active_mask",
        "force_start_n",
        "force_midpoint_n",
        "force_endpoint_n",
        "force_peak_n",
        "tire_raw_utilization",
        "tire_saturated",
    }
    for segment in audit["interval_segments"]:
        assert required <= set(segment)
        expected_peak = np.max(
            np.asarray([segment["force_start_n"], segment["force_midpoint_n"], segment["force_endpoint_n"]]),
            axis=0,
        )
        np.testing.assert_allclose(segment["force_peak_n"], expected_peak)
        assert np.all(np.isfinite(segment["force_direction_body_rad"]))
