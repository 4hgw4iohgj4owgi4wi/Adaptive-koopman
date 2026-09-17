from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from event_substep import EventSubstepConfig, advance_outer_step
from four_vehicle_common import ModelParams, connector_diagnostics, initialize_state, split_state


def q99_state():
    params = ModelParams(); state = initialize_state(params, 1.5); vehicles, payload = split_state(state)
    speed = 0.2006325726682664
    directions = params.payload_anchor_body_m / np.linalg.norm(params.payload_anchor_body_m, axis=1)[:, None]
    for index, contact_time in enumerate((0.0008, 0.0010, 0.0012, 0.0014)):
        vehicles[index, :2] += directions[index] * (params.connector.free_play_m - speed * contact_time)
        vehicles[index, 3:5] = payload[3:5] + speed * directions[index]
    state[:24] = vehicles.ravel()
    return params, state


def test_action_reaction_and_internal_null():
    params, state = q99_state(); diag = connector_diagnostics(state, params, "R3")
    assert np.max(np.abs(diag["action_reaction_residual_n"])) < 1e-12
    assert np.linalg.norm(diag["internal_null_residual"]) < 1e-8 * max(1.0, diag["internal_force_norm_n"])
    assert abs(sum(diag["payload_moment_nm"]) - diag["payload_moment_total_nm"]) < 1e-12


def test_vector_event_solver_records_q99_contacts_without_subminimum_steps():
    params, state = q99_state()
    _, audit = advance_outer_step(state, np.zeros((4, 2)), "R3", params, 0.002, "ES", EventSubstepConfig())
    assert audit["status"] == "PASS"
    assert audit["min_physical_dt_s"] >= 2e-6
    contact_ids = {event["connector_id"] for event in audit["events"] if event["surface"] == "contact"}
    assert contact_ids == {0, 1, 2, 3}

