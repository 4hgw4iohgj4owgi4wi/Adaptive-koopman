from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from causal_schema import build_schema_v3
from data_adapter import INPUT_KEYS, LABEL_KEYS, build_sample, causal_input_digest
from four_vehicle_common import ModelParams, connector_kinematics, initialize_state, rotation as upstream_rotation
from relative_coordinates import G3_SLICE, decode_absolute, encode_relative, rotation


def nontrivial_state(params: ModelParams) -> np.ndarray:
    state = initialize_state(params, 2.3)
    vehicles = state[:24].reshape(4, 6)
    vehicles[:, 0] += np.asarray([0.12, -0.08, 0.05, -0.04])
    vehicles[:, 1] += np.asarray([0.04, -0.03, 0.02, -0.01])
    vehicles[:, 2] = np.asarray([0.08, 0.05, -0.03, -0.06])
    vehicles[:, 3] += np.asarray([0.2, -0.1, 0.05, -0.03])
    vehicles[:, 4] = np.asarray([0.06, -0.04, 0.02, -0.01])
    vehicles[:, 5] = np.asarray([0.12, 0.09, 0.04, 0.02])
    state[24:] = np.asarray([0.3, -0.2, 0.04, 2.2, 0.03, 0.07])
    return state


def synthetic_arrays(params: ModelParams) -> dict[str, np.ndarray]:
    count = 6
    base = nontrivial_state(params)
    states = np.stack([base.copy() for _ in range(count)])
    states[:, 0::6] += np.arange(count)[:, None] * 0.04
    states[:, 24] += np.arange(count) * 0.04
    controls = np.arange(count * 8, dtype=float).reshape(count, 4, 2) * 1.0e-3
    shape42 = (count, 4, 2)
    return {
        "time_s": np.arange(count, dtype=float) * 0.020,
        "state30": states,
        "control4x2": controls,
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


def test_schema_has_explicit_causal_roles_and_dimensions() -> None:
    schema = build_schema_v3()
    assert schema["relative_dimension"] == 47
    assert len(schema["relative_fields"]) == 47
    inputs = {item["name"]: item for item in schema["inputs"]}
    labels = {item["name"]: item for item in schema["labels"]}
    assert set(INPUT_KEYS) == set(inputs)
    assert set(LABEL_KEYS) == set(labels)
    assert inputs["u8_k"]["time"] == "applied_[t_k,t_k+1]"
    assert labels["event_counts16_next"]["role"] == "supervision_only"
    assert all("next" not in name for name in inputs)


def test_relative_roundtrip_and_rigid_transform_invariance() -> None:
    params = ModelParams()
    state = nontrivial_state(params)
    encoded = encode_relative(state, params)
    decoded = decode_absolute(encoded["relative_state47"], encoded["payload_pose_context3"])
    np.testing.assert_allclose(decoded, state, rtol=0.0, atol=1.0e-12)
    angle = 0.31
    translation = np.asarray([5.0, -9.0])
    transformed = state.copy()
    world_rotation = rotation(angle)
    for offset in (0, 6, 12, 18, 24):
        transformed[offset : offset + 2] = world_rotation @ state[offset : offset + 2] + translation
        transformed[offset + 2] += angle
    transformed_encoded = encode_relative(transformed, params)
    np.testing.assert_allclose(
        transformed_encoded["relative_state47"], encoded["relative_state47"], rtol=0.0, atol=1.0e-12
    )


def test_anchor_geometry_matches_frozen_connector_kinematics() -> None:
    params = ModelParams()
    state = nontrivial_state(params)
    encoded = encode_relative(state, params)
    upstream = connector_kinematics(state, params)
    payload_rotation = upstream_rotation(state[26])
    expected_d = upstream["displacement_world_m"] @ payload_rotation
    expected_v = upstream["relative_velocity_world_mps"] @ payload_rotation
    np.testing.assert_allclose(encoded["connector_displacement_payload_m"], expected_d, atol=1.0e-12)
    np.testing.assert_allclose(encoded["anchor_relative_velocity_payload_mps"], expected_v, atol=1.0e-12)
    expected_g3 = np.c_[expected_d, expected_v].ravel()
    np.testing.assert_allclose(encoded["relative_state47"][G3_SLICE], expected_g3, atol=1.0e-12)


def test_adapter_uses_known_future_control_but_not_future_truth() -> None:
    params = ModelParams()
    arrays = synthetic_arrays(params)
    index = 2
    sample = build_sample(arrays, index, params, expected_step_s=0.020)
    np.testing.assert_array_equal(sample["u8_k"], arrays["control4x2"][index + 1].ravel())
    changed = {key: value.copy() for key, value in arrays.items()}
    changed["state30"][index + 1] += 7.0
    changed["force_payload_body_n"][index + 1] += 11.0
    changed["force_interval_mean_body_n"][index + 1] += 13.0
    changed["event_counts16"][index + 1] += 17.0
    changed_sample = build_sample(changed, index, params, expected_step_s=0.020)
    assert causal_input_digest(changed_sample) == causal_input_digest(sample)
    assert not np.array_equal(changed_sample["physical_state30_k1"], sample["physical_state30_k1"])
    assert not np.array_equal(changed_sample["force_mean8_next"], sample["force_mean8_next"])
    assert not np.array_equal(changed_sample["event_counts16_next"], sample["event_counts16_next"])


def test_params_are_required_and_explicitly_propagated() -> None:
    params = ModelParams()
    arrays = synthetic_arrays(params)
    with pytest.raises(TypeError):
        build_sample(arrays, 2)  # type: ignore[misc]
    changed_params = replace(
        params,
        payload=replace(params.payload, length_m=params.payload.length_m * 0.95),
        connector=replace(params.connector, stiffness_npm=params.connector.stiffness_npm * 1.1),
    )
    original = build_sample(arrays, 2, params, expected_step_s=0.020)
    changed = build_sample(arrays, 2, changed_params, expected_step_s=0.020)
    assert not np.array_equal(original["parameter_vector_k"], changed["parameter_vector_k"])
    assert not np.array_equal(original["relative_state47_k"], changed["relative_state47_k"])


def test_adapter_rejects_mixed_or_off_grid_model_steps() -> None:
    params = ModelParams()
    arrays = synthetic_arrays(params)
    arrays["time_s"][2] = arrays["time_s"][1] + 0.006
    with pytest.raises(ValueError, match="off-grid trajectory time grid"):
        build_sample(arrays, 2, params, expected_step_s=0.020)
    with pytest.raises(ValueError, match="off-grid trajectory time grid"):
        build_sample(arrays, 1, params, expected_step_s=0.020)
