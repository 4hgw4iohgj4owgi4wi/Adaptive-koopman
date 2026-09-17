from __future__ import annotations

import numpy as np

from actuator_rollout import rollout_actuator_interval
from causal_schema import build_schema_variant
from data_adapter import build_sample_variant, causal_input_digest_variant
from four_vehicle_common import ModelParams, initialize_state
from steering_actuator import SteeringActuatorConfig


def _arrays(params: ModelParams, count: int = 25) -> dict[str, np.ndarray]:
    states = np.stack([initialize_state(params, 2.0) for _ in range(count)])
    states[:, 0::6] += np.arange(count)[:, None] * 0.04
    states[:, 24] += np.arange(count) * 0.04
    requested = np.zeros((count, 4, 2), dtype=float)
    requested[:, :, 0] = 0.1
    requested[:, :, 1] = np.linspace(-0.1, 0.1, count)[:, None]
    config = SteeringActuatorConfig()
    actual = np.zeros((count, 4), dtype=float)
    rates = np.zeros((count, 4), dtype=float)
    means = np.zeros((count, 4), dtype=float)
    actuator_state = np.zeros(4, dtype=float)
    for row in range(count):
        result = rollout_actuator_interval(
            actuator_state,
            requested[row, :, 1],
            plant_step_s=0.002,
            substeps=10,
            config=config,
        )
        actuator_state = result["delta_act_k1_rad"]
        actual[row] = actuator_state
        rates[row] = result["delta_rate_substeps_radps"][-1]
        means[row] = result["delta_act_mean_rad"]
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
        "base_acceleration_mps2": np.full(count, 0.1),
        "virtual_front_deg": np.linspace(-2.0, 2.0, count),
        "virtual_rear_deg": np.linspace(1.0, -1.0, count),
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


def test_variant_field_ledgers_are_explicit_and_unique() -> None:
    expected_dimensions = {"S0": 54, "S1": 58, "S2": 70}
    for variant, dimension in expected_dimensions.items():
        schema = build_schema_variant(variant)
        audit = schema["contract_audit"]
        assert audit["passed"]
        assert audit["input_dimension"] == dimension
        assert audit["duplicate_physical_feature_count"] == 0
        assert audit["future_measured_input_count"] == 0
        for item in schema["inputs"] + schema["labels"]:
            assert item["unit"] and item["shape"] and item["source"]
            assert int(np.prod(item["shape"])) == item["dimension"]


def test_future_measured_actuator_tampering_does_not_change_inputs() -> None:
    params = ModelParams()
    arrays = _arrays(params)
    index = 2
    changed = {key: np.asarray(value).copy() for key, value in arrays.items()}
    changed["actual_steering_rad"][index + 1 : index + 21] += 0.75
    changed["actual_steering_rate_radps"][index + 1 : index + 21] -= 4.0
    for variant in ("S0", "S1", "S2"):
        original = build_sample_variant(
            arrays,
            index,
            params,
            variant=variant,
            expected_step_s=0.020,
            plant_step_s=0.002,
        )
        tampered = build_sample_variant(
            changed,
            index,
            params,
            variant=variant,
            expected_step_s=0.020,
            plant_step_s=0.002,
        )
        assert causal_input_digest_variant(original, variant) == causal_input_digest_variant(
            tampered, variant
        )
        if variant != "S0":
            assert not np.array_equal(original["hybrid_state51_k1"], tampered["hybrid_state51_k1"])
