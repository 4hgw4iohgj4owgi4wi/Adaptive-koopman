from __future__ import annotations

import numpy as np

from causal_schema import build_schema_focus
from data_adapter import (
    INPUT_KEYS_FOCUS,
    LABEL_KEYS_FOCUS,
    build_sample_focus,
    causal_input_digest_focus,
)
from four_vehicle_common import ModelParams
from test_schema_v4 import synthetic_v4_arrays


def focus_arrays(params: ModelParams) -> dict[str, np.ndarray]:
    arrays = synthetic_v4_arrays(params)
    count = len(arrays["time_s"])
    static = params.payload.mass_kg * params.payload.gravity_mps2 / 4.0
    arrays.update(
        {
            "virtual_front_deg": np.zeros(count),
            "virtual_rear_deg": np.zeros(count),
            "payload_support_load4_n": np.full((count, 4), static),
            "vehicle_total_normal_load4_n": np.full(
                (count, 4), params.vehicle.mass_kg * params.vehicle.gravity_mps2 + static
            ),
            "payload_accel_body2_mps2": np.zeros((count, 2)),
            "icr_geometry_residual_mps": np.zeros(count),
            "icr_request_residual_mps": np.zeros(count),
            "icr_actual_residual_mps": np.zeros(count),
            "load_transfer_enabled": np.asarray(True),
        }
    )
    return arrays


def test_focus_schema_roles_and_no_future_actual_or_fz_leakage() -> None:
    schema = build_schema_focus()
    assert {item["name"] for item in schema["inputs"]} == set(INPUT_KEYS_FOCUS)
    assert {item["name"] for item in schema["labels"]} == set(LABEL_KEYS_FOCUS)
    params = ModelParams()
    arrays = focus_arrays(params)
    index = 3
    sample = build_sample_focus(
        arrays,
        index,
        params,
        law="R3",
        expected_step_s=0.020,
        plant_step_s=0.002,
    )
    changed = {key: np.asarray(value).copy() for key, value in arrays.items()}
    changed["actual_steering_rad"][index + 1] += 0.8
    changed["payload_support_load4_n"][index + 1] += 9000.0
    changed["vehicle_total_normal_load4_n"][index + 1] += 9000.0
    changed["payload_accel_body2_mps2"][index + 1] += 20.0
    changed_sample = build_sample_focus(
        changed,
        index,
        params,
        law="R3",
        expected_step_s=0.020,
        plant_step_s=0.002,
    )
    assert causal_input_digest_focus(changed_sample) == causal_input_digest_focus(sample)
    assert not np.array_equal(
        changed_sample["payload_support_load4_k1"], sample["payload_support_load4_k1"]
    )
