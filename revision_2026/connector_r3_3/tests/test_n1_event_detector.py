from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connector_adapter import DELTA_S_M, VectorConnector
from connector_r3 import ConnectorR3Params, connector_force_r3
from event_substep import detect_callable_events


def test_double_crossing_and_simultaneous_grouping():
    double = detect_callable_events(lambda t: np.asarray([2500.0 * (t - 0.0002) * (t - 0.0008)]), 0.0, 0.001, surfaces_m=(0.0,), probe_step_s=0.001)
    assert sum(len(group["events"]) for group in double) == 2
    simultaneous = detect_callable_events(lambda t: np.full(4, -0.001 + t), 0.0, 0.0015, surfaces_m=(0.0,))
    assert len(simultaneous) == 1
    assert len(simultaneous[0]["events"]) == 4


def test_vector_r3_matches_frozen_formula():
    params = ConnectorR3Params(smoothing_width_m=DELTA_S_M)
    displacement = np.asarray([[params.free_play_m + q, 0.0] for q in (-1e-5, 0.0, 1e-10, DELTA_S_M / 2, DELTA_S_M, 2 * DELTA_S_M)])
    velocity = np.asarray([[v, 0.0] for v in (-1.0, 0.0, 0.25, 1.0, -0.25, 0.1)])
    frozen = connector_force_r3(displacement, velocity, params)
    adapted = VectorConnector("R3", params).evaluate(displacement, velocity)
    np.testing.assert_allclose(adapted["applied_force_n"], frozen.applied_force_n, rtol=0.0, atol=2e-12)
    np.testing.assert_allclose(adapted["force_payload_world_n"], frozen.force_payload_world_n, rtol=0.0, atol=2e-12)

