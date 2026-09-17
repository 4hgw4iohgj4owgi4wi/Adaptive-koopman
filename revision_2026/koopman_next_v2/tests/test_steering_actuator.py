from __future__ import annotations

import numpy as np
import pytest

from actuator_rollout import rollout_actuator_interval
from steering_actuator import SteeringActuatorConfig, step_actuator


CFG = SteeringActuatorConfig(
    tau_delta_s=0.12,
    rate_max_radps=1.2,
    angle_max_rad=float(np.deg2rad(15.0)),
)


def test_two_millisecond_exact_update_without_rate_limit() -> None:
    request = np.full(4, 0.01)
    actual = np.zeros(4)
    result = step_actuator(request, actual, 0.002, CFG)
    expected = request * (1.0 - np.exp(-0.002 / 0.12))
    np.testing.assert_allclose(result["delta_act_next_rad"], expected, rtol=0.0, atol=1.0e-15)
    assert not np.any(result["rate_limited_mask"])


def test_rate_limit_and_twenty_millisecond_bound() -> None:
    request = np.full(4, np.deg2rad(15.0))
    result = rollout_actuator_interval(
        np.zeros(4), request, plant_step_s=0.002, substeps=10, config=CFG
    )
    np.testing.assert_allclose(result["delta_act_k1_rad"], 0.024, rtol=0.0, atol=1.0e-15)
    assert np.max(np.abs(result["delta_rate_substeps_radps"])) <= 1.2 + 1.0e-15
    assert np.all(result["rate_limited_substeps"])


def test_constant_request_is_monotone_and_angle_bounded() -> None:
    actual = np.zeros(4)
    request = np.full(4, 10.0)
    history = []
    for _ in range(200):
        result = step_actuator(request, actual, 0.002, CFG)
        actual = result["delta_act_next_rad"]
        history.append(actual.copy())
    values = np.asarray(history)
    assert np.all(np.diff(values, axis=0) >= -1.0e-15)
    assert np.max(np.abs(values)) <= CFG.angle_max_rad + 1.0e-15
    np.testing.assert_allclose(values[-1], CFG.angle_max_rad, rtol=0.0, atol=1.0e-15)


def test_left_right_mirror_and_deterministic_reload(tmp_path) -> None:
    request = np.asarray([0.2, 0.18, -0.1, -0.12])
    actual = np.asarray([0.03, 0.02, -0.01, -0.02])
    left = rollout_actuator_interval(
        actual, request, plant_step_s=0.002, substeps=10, config=CFG
    )
    right = rollout_actuator_interval(
        -actual, -request, plant_step_s=0.002, substeps=10, config=CFG
    )
    np.testing.assert_allclose(
        right["delta_act_substeps_rad"],
        -left["delta_act_substeps_rad"],
        rtol=0.0,
        atol=1.0e-15,
    )
    path = tmp_path / "actuator_state.npz"
    np.savez(path, state=left["delta_act_k1_rad"])
    with np.load(path, allow_pickle=False) as saved:
        replay_a = rollout_actuator_interval(
            saved["state"], request, plant_step_s=0.002, substeps=10, config=CFG
        )
        replay_b = rollout_actuator_interval(
            saved["state"], request, plant_step_s=0.002, substeps=10, config=CFG
        )
    for key in replay_a:
        assert np.array_equal(replay_a[key], replay_b[key])


def test_invalid_config_and_shape_are_rejected() -> None:
    with pytest.raises(ValueError):
        step_actuator(
            np.zeros(4),
            np.zeros(4),
            0.002,
            SteeringActuatorConfig(tau_delta_s=0.0),
        )
    with pytest.raises(ValueError, match="shape mismatch"):
        step_actuator(np.zeros(3), np.zeros(4), 0.002, CFG)
