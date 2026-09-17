import numpy as np

from four_vehicle_coupled import ModelParams, connector_diagnostics, initialize_state, system_derivative


def main() -> None:
    params = ModelParams()
    state = initialize_state(params)
    zero = connector_diagnostics(state, params)
    assert np.allclose(zero["force_norm_n"], 0.0)

    displaced = state.copy()
    displaced[0] += 0.01
    diag = connector_diagnostics(displaced, params)
    assert diag["force_payload_world_n"][0, 0] > 0.0
    assert np.allclose(diag["force_payload_world_n"] + diag["force_vehicle_world_n"], 0.0)
    assert abs(diag["vehicle_moment_nm"][0]) > 0.0

    controls = np.zeros((4, 2))
    derivative, _ = system_derivative(displaced, controls, params)
    vehicles_d = derivative[:24].reshape(4, 6)
    payload_d = derivative[24:]
    assert vehicles_d[0, 3] < 0.0
    assert payload_d[3] > 0.0
    assert abs(vehicles_d[0, 5]) > 0.0
    print("PASS: zero-clearance, direction, action-reaction, vehicle/payload/yaw coupling")


if __name__ == "__main__":
    main()
