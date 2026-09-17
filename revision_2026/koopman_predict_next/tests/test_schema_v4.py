from __future__ import annotations

import numpy as np

from actuator_rollout import rollout_actuator_interval
from causal_schema import build_schema_v4
from data_adapter import (
    INPUT_KEYS_V4,
    LABEL_KEYS_V4,
    build_sample_v4,
    causal_input_digest_v4,
)
from four_vehicle_common import ModelParams, initialize_state
from steering_actuator import SteeringActuatorConfig


def synthetic_v4_arrays(params: ModelParams) -> dict[str, np.ndarray]:
    count = 7
    states = np.stack([initialize_state(params, 2.0) for _ in range(count)])
    states[:, 0::6] += np.arange(count)[:, None] * 0.04
    states[:, 24] += np.arange(count) * 0.04
    requested = np.zeros((count, 4, 2), dtype=float)
    requested[:, :, 0] = np.arange(count)[:, None] * 0.01
    requested[:, :, 1] = np.linspace(-0.12, 0.12, count)[:, None]
    config = SteeringActuatorConfig()
    actual = np.zeros((count, 4), dtype=float)
    rates = np.zeros((count, 4), dtype=float)
    means = np.zeros((count, 4), dtype=float)
    state = np.zeros(4, dtype=float)
    for index in range(count):
        rollout = rollout_actuator_interval(
            state,
            requested[index, :, 1],
            plant_step_s=0.002,
            substeps=10,
            config=config,
        )
        state = rollout["delta_act_k1_rad"]
        actual[index] = state
        rates[index] = rollout["delta_rate_substeps_radps"][-1]
        means[index] = rollout["delta_act_mean_rad"]
    control = requested.copy()
    control[:, :, 1] = means
    shape42 = (count, 4, 2)
    return {
        "time_s": np.arange(1, count + 1, dtype=float) * 0.020,
        "state30": states,
        "control4x2": control,
        "requested_control4x2": requested,
        "actual_steering_rad": actual,
        "actual_steering_rate_radps": rates,
        "actuator_tau_delta_s": np.asarray(config.tau_delta_s),
        "actuator_rate_max_radps": np.asarray(config.rate_max_radps),
        "actuator_angle_max_rad": np.asarray(config.angle_max_rad),
        "force_payload_body_n": np.zeros(shape42),
        "force_active_mask": np.zeros((count, 4), dtype=bool),
        "force_interval_mean_body_n": np.zeros(shape42),
        "force_interval_impulse_world_ns": np.zeros(shape42),
        "internal_force_interval_mean_n": np.zeros((count, 8)),
        "tension_proxy_interval_mean_n": np.zeros((count, 2)),
        "contact_fraction": np.zeros((count, 4)),
        "smoothing_fraction": np.zeros((count, 4)),
        "smoothing_weight_mean": np.zeros((count, 4)),
        "event_counts16": np.zeros((count, 16)),
    }


def test_schema_v4_dimensions_and_roles() -> None:
    schema = build_schema_v4()
    assert schema["relative_dimension"] == 47
    assert schema["hybrid_dimension"] == 51
    assert {item["name"] for item in schema["inputs"]} == set(INPUT_KEYS_V4)
    assert {item["name"] for item in schema["labels"]} == set(LABEL_KEYS_V4)
    assert all("next" not in item["name"] for item in schema["inputs"])


def test_v4_analytic_sidecar_and_no_future_actual_truth_leakage() -> None:
    params = ModelParams()
    arrays = synthetic_v4_arrays(params)
    index = 3
    sample = build_sample_v4(
        arrays, index, params, expected_step_s=0.020, plant_step_s=0.002
    )
    assert np.asarray(sample["hybrid_state51_k"]).shape == (51,)
    np.testing.assert_array_equal(
        sample["steering_request4_k"], arrays["requested_control4x2"][index + 1, :, 1]
    )
    changed = {key: np.asarray(value).copy() for key, value in arrays.items()}
    changed["state30"][index + 1] += 7.0
    changed["actual_steering_rad"][index + 1] += 0.7
    changed["actual_steering_rate_radps"][index + 1] += 8.0
    changed["control4x2"][index + 1, :, 1] += 0.5
    changed["force_payload_body_n"][index + 1] += 11.0
    changed["force_interval_mean_body_n"][index + 1] += 13.0
    changed["event_counts16"][index + 1] += 17.0
    changed_sample = build_sample_v4(
        changed, index, params, expected_step_s=0.020, plant_step_s=0.002
    )
    assert causal_input_digest_v4(changed_sample) == causal_input_digest_v4(sample)
    assert not np.array_equal(
        changed_sample["actual_steering4_k1"], sample["actual_steering4_k1"]
    )
