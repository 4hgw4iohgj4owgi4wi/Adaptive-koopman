from __future__ import annotations

import numpy as np

from icr_metrics import icr_geometry_residual, icr_steering_residual


MIRROR = np.asarray([1, 0, 3, 2])


def test_straight_and_feedforward_icr_residuals() -> None:
    velocity = np.tile([2.0, 0.0], (4, 1))
    geometry = icr_geometry_residual(velocity, np.zeros(4))
    assert geometry["max_abs_mps"] == 0.0
    speed = np.asarray([2.0, 2.1, 1.9, 2.05])
    yaw_rate = 0.25
    wheelbase = 2.5
    feedforward = np.arctan2(wheelbase * yaw_rate, speed)
    result = icr_steering_residual(speed, yaw_rate, wheelbase, feedforward)
    assert float(result["max_abs_mps"]) <= 2.0e-16


def test_clipping_creates_nonzero_icr_and_mirror_maps_vehicle_order() -> None:
    speed = np.asarray([2.0, 2.1, 1.9, 2.05])
    yaw_rate = 0.6
    angle = np.full(4, np.deg2rad(15.0))
    left = icr_steering_residual(speed, yaw_rate, 2.5, angle)
    right = icr_steering_residual(speed[MIRROR], -yaw_rate, 2.5, -angle[MIRROR])
    assert float(left["max_abs_mps"]) > 0.0
    np.testing.assert_allclose(
        np.asarray(left["signed_per_vehicle_mps"])[MIRROR]
        + np.asarray(right["signed_per_vehicle_mps"]),
        0.0,
        atol=1.0e-15,
        rtol=0.0,
    )
    assert abs(float(left["max_abs_mps"]) - float(right["max_abs_mps"])) <= 1.0e-15
