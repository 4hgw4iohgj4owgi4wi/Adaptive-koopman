import numpy as np

from four_vehicle_coupled import ModelParams, initialize_state
from steering_allocator import allocate_controls, kinematic_targets


def main() -> None:
    params = ModelParams()
    straight = kinematic_targets(5.0, 0.0, 0.0, params)
    assert np.allclose(straight["relative_heading_rad"], 0.0)
    assert np.allclose(straight["feedforward_steering_rad"], 0.0)
    assert np.allclose(straight["speed_mps"], 5.0)

    left = kinematic_targets(5.0, np.deg2rad(4.0), np.deg2rad(-2.0), params)
    right = kinematic_targets(5.0, np.deg2rad(-4.0), np.deg2rad(2.0), params)
    assert np.max(np.abs(left["normal_velocity_residual_mps"])) < 1.0e-10
    assert np.max(np.abs(right["normal_velocity_residual_mps"])) < 1.0e-10
    assert np.all(left["feedforward_steering_rad"] > 0.0)
    assert np.all(right["feedforward_steering_rad"] < 0.0)
    mirror = np.array([1, 0, 3, 2])
    assert np.allclose(left["relative_heading_rad"], -right["relative_heading_rad"][mirror], atol=2.0e-3)
    assert np.allclose(left["speed_mps"], right["speed_mps"][mirror], rtol=2.0e-3)

    state = initialize_state(params, speed_mps=5.0)
    controls, targets = allocate_controls(state, 0.0, 4.0, -2.0, params)
    assert abs(np.mean(controls[:, 0])) < 1.0e-12
    assert np.all(np.isfinite(controls))
    assert targets["icr_payload_body_m"][1] > 0.0
    print("PASS: straight, common-ICR no-slip, mirror symmetry, same-sign yaw feedforward, zero-sum speed allocation")


if __name__ == "__main__":
    main()
