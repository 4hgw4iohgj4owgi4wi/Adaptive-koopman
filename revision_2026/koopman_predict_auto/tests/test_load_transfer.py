from __future__ import annotations

import numpy as np
import pytest

from four_vehicle_common import ModelParams
from load_transfer import (
    SupportLiftOutsideEnvelope,
    config_from_model,
    solve_payload_support_loads,
)


MIRROR = np.asarray([1, 0, 3, 2])


def test_static_support_and_constraints() -> None:
    params = ModelParams()
    config = config_from_model(params)
    result = solve_payload_support_loads(np.zeros(2), config, enabled=True)
    expected = params.payload.mass_kg * params.payload.gravity_mps2 / 4.0
    np.testing.assert_allclose(result["payload_support_load_n"], expected, rtol=1.0e-15, atol=0.0)
    assert np.max(np.abs(result["constraint_relative_residual"])) <= 1.0e-15


def test_direction_and_mirror_contracts() -> None:
    config = config_from_model(ModelParams())
    lateral_left = solve_payload_support_loads(np.asarray([0.0, 1.0]), config, enabled=True)[
        "payload_support_load_n"
    ]
    lateral_right = solve_payload_support_loads(np.asarray([0.0, -1.0]), config, enabled=True)[
        "payload_support_load_n"
    ]
    assert lateral_left[[1, 3]].sum() > lateral_left[[0, 2]].sum()
    np.testing.assert_allclose(lateral_left[MIRROR], lateral_right, atol=1.0e-12, rtol=0.0)
    acceleration = solve_payload_support_loads(np.asarray([1.0, 0.0]), config, enabled=True)[
        "payload_support_load_n"
    ]
    braking = solve_payload_support_loads(np.asarray([-1.0, 0.0]), config, enabled=True)[
        "payload_support_load_n"
    ]
    assert acceleration[[2, 3]].sum() > acceleration[[0, 1]].sum()
    assert braking[[0, 1]].sum() > braking[[2, 3]].sum()


def test_disabled_is_exact_static_and_lift_is_not_silently_clipped() -> None:
    params = ModelParams()
    config = config_from_model(params)
    disabled = solve_payload_support_loads(np.asarray([4.0, -3.0]), config, enabled=False)
    expected = params.payload.mass_kg * params.payload.gravity_mps2 / 4.0
    np.testing.assert_array_equal(disabled["payload_support_load_n"], np.full(4, expected))
    with pytest.raises(SupportLiftOutsideEnvelope):
        solve_payload_support_loads(np.asarray([100.0, 100.0]), config, enabled=True)
