from __future__ import annotations

import numpy as np
import pytest

from causal_schema import build_schema_icr
from four_vehicle_common import ModelParams, initialize_state, split_state
from steering_actuator import SteeringActuatorConfig, step_actuator, step_actuator_mode
from steering_allocator import (
    AllocationConfig,
    allocate_controls,
    kinematic_targets,
    request_variants,
    wrap,
)


def test_g2_reproduces_frozen_parent_arithmetic_pointwise() -> None:
    params = ModelParams()
    state = initialize_state(params, 2.3)
    state[[2, 8, 14, 20]] += np.asarray([0.01, -0.02, 0.03, -0.04])
    cfg = AllocationConfig()
    variants = request_variants(state, 5.0, -2.5, params, cfg)
    vehicles, payload = split_state(state)
    targets = kinematic_targets(
        max(float(payload[3]), 0.0), np.deg2rad(5.0), np.deg2rad(-2.5), params
    )
    desired = payload[2] + targets["relative_heading_rad"]
    raw = targets["feedforward_steering_rad"] + cfg.heading_gain * wrap(
        desired - vehicles[:, 2]
    )
    expected = np.clip(
        raw, -np.deg2rad(cfg.max_steering_deg), np.deg2rad(cfg.max_steering_deg)
    )
    assert np.max(np.abs(variants["g0_steering_rad"] - targets["feedforward_steering_rad"])) == 0.0
    assert np.max(np.abs(variants["g1_steering_rad"] - raw)) == 0.0
    assert np.max(np.abs(variants["g2_steering_rad"] - expected)) == 0.0
    controls, allocation = allocate_controls(state, 0.0, 5.0, -2.5, params, cfg)
    assert np.max(np.abs(controls[:, 1] - expected)) == 0.0
    assert np.max(np.abs(allocation["allocated_steering_rad"] - expected)) == 0.0


def test_request_variants_left_right_mirror() -> None:
    params = ModelParams()
    state = initialize_state(params, 2.0)
    left = request_variants(state, 5.0, -2.5, params)
    right = request_variants(state, -5.0, 2.5, params)
    mirror = np.asarray([1, 0, 3, 2])
    for key in ("g0_steering_rad", "g1_steering_rad", "g2_steering_rad"):
        assert np.max(np.abs(left[key][mirror] + right[key])) <= 1.0e-12


def test_a3_calls_parent_actuator_exactly() -> None:
    config = SteeringActuatorConfig()
    request = np.asarray([0.2, -0.2, 0.1, -0.1])
    actual = np.asarray([0.01, -0.02, 0.03, -0.04])
    parent = step_actuator(request, actual, 0.002, config)
    a3 = step_actuator_mode(request, actual, 0.002, config, "A3")
    for key in parent:
        assert np.array_equal(parent[key], a3[key])


def test_a0_a1_a2_contracts_and_illegal_mode() -> None:
    config = SteeringActuatorConfig()
    request = np.full(4, 0.2)
    actual = np.zeros(4)
    a0 = step_actuator_mode(request, actual, 0.002, config, "A0")
    a1 = step_actuator_mode(request, actual, 0.002, config, "A1")
    a2 = step_actuator_mode(request, actual, 0.002, config, "A2")
    assert np.array_equal(a0["delta_act_next_rad"], request)
    assert np.all(a1["delta_act_next_rad"] < request)
    assert np.max(np.abs(a2["delta_rate_radps"])) <= config.rate_max_radps
    assert np.all(a2["rate_limited_mask"])
    with pytest.raises(ValueError):
        step_actuator_mode(request, actual, 0.002, config, "A4")


def test_icr_schema_has_only_causal_sidecar_inputs() -> None:
    schema = build_schema_icr()
    names = [field["name"] for field in schema["inputs"]]
    assert "actuator_sidecar20_k" in names
    assert "actuator_gate8_k" in names
    assert all(field["time"] != "t_k+1" for field in schema["inputs"])
