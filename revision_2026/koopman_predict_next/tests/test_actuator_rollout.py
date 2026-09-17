from __future__ import annotations

import numpy as np

from actuator_rollout import rollout_actuator_horizon, rollout_actuator_step
from steering_actuator import SteeringActuatorConfig, step_actuator


def _manual(initial: np.ndarray, requests: np.ndarray, config: SteeringActuatorConfig) -> np.ndarray:
    actual = np.asarray(initial, dtype=float).copy()
    endpoints = []
    for request in requests:
        for _ in range(10):
            actual = step_actuator(request, actual, 0.002, config)["delta_act_next_rad"]
        endpoints.append(actual.copy())
    return np.asarray(endpoints)


def test_one_step_matches_manual_unlimited_decay() -> None:
    config = SteeringActuatorConfig(rate_max_radps=100.0, angle_max_rad=2.0)
    initial = np.asarray([0.0, 0.03, -0.02, 0.01])
    request = np.asarray([0.04, -0.02, 0.01, -0.03])
    result = rollout_actuator_step(
        initial,
        request,
        model_step_s=0.020,
        plant_step_s=0.002,
        config=config,
    )
    expected = request + np.exp(-0.020 / config.tau_delta_s) * (initial - request)
    np.testing.assert_allclose(result["delta_act_k1_rad"], expected, rtol=0.0, atol=2e-16)
    assert not np.any(result["rate_limited_substeps"])
    assert not np.any(result["angle_limited_substeps"])


def test_rate_angle_limits_and_positive_negative_switch() -> None:
    config = SteeringActuatorConfig()
    requests = np.vstack(
        [
            np.full((6, 4), 1.0),
            np.full((7, 4), -1.0),
            np.full((7, 4), np.deg2rad(15.0)),
        ]
    )
    result = rollout_actuator_horizon(
        np.zeros(4),
        requests,
        model_step_s=0.020,
        plant_step_s=0.002,
        config=config,
    )
    assert np.any(result["rate_limited_intervals"])
    assert np.max(np.abs(result["delta_rate_substeps_radps"])) <= 1.2 + 1e-12
    assert np.max(np.abs(result["delta_act_endpoints_rad"])) <= np.deg2rad(15.0) + 1e-12
    np.testing.assert_allclose(
        result["delta_act_endpoints_rad"],
        _manual(np.zeros(4), requests, config),
        rtol=0.0,
        atol=0.0,
    )
    angle_case = rollout_actuator_horizon(
        np.zeros(4),
        np.ones((20, 4)),
        model_step_s=0.020,
        plant_step_s=0.002,
        config=config,
    )
    assert np.any(angle_case["angle_limited_intervals"])
    np.testing.assert_allclose(
        angle_case["delta_act_endpoints_rad"][-1],
        np.full(4, np.deg2rad(15.0)),
        rtol=0.0,
        atol=0.0,
    )


def test_twenty_step_horizon_matches_repeated_frozen_a3() -> None:
    config = SteeringActuatorConfig()
    phase = np.linspace(-0.25, 0.25, 20)
    requests = np.column_stack([phase, -phase, 0.5 * phase, -0.5 * phase])
    initial = np.asarray([0.03, -0.02, 0.01, -0.01])
    result = rollout_actuator_horizon(
        initial,
        requests,
        model_step_s=0.020,
        plant_step_s=0.002,
        config=config,
    )
    np.testing.assert_allclose(
        result["delta_act_endpoints_rad"],
        _manual(initial, requests, config),
        rtol=0.0,
        atol=0.0,
    )
    assert result["delta_act_endpoints_rad"].shape == (20, 4)
