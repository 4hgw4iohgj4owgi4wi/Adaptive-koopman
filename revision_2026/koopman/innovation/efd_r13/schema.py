from __future__ import annotations


def contract() -> dict:
    return {
        "state_dim": 46, "control_dim": 8, "horizon": 20,
        "corner_order": ["FL", "FR", "RL", "RR"],
        "state_slices": {"vehicle_payload_core": [0, 30], "connector_disp": [30, 38], "connector_vel": [38, 46]},
        "frames": {"positions_yaw": "world", "body_velocities": "respective body",
                   "connector_disp_vel_force": "payload body"},
        "connector": {"d_definition": "vehicle_anchor-payload_anchor", "force_side": "payload",
                      "stiffness_npm": 30000., "damping_nspm": 3500., "free_play_m": .002,
                      "damping": "only penetration>0 and max(v dot n,0)", "tangential": False},
        "mirror": {"corner_permutation": [1, 0, 3, 2], "vector_parity": [1, -1],
                   "yaw_yawrate_steer_parity": -1},
        "physical_scales": {"world_position_m": 100., "yaw_rad": 3.141592653589793,
                            "body_speed_mps": 5., "yaw_rate_radps": 1.,
                            "connector_disp_m": .05, "connector_vel_mps": 1., "force_q_N": 8000.},
    }


def validate(value: dict) -> None:
    assert value["state_dim"] == 46 and value["control_dim"] == 8 and value["horizon"] == 20
    assert value["corner_order"] == ["FL", "FR", "RL", "RR"]
    assert value["state_slices"] == {"vehicle_payload_core": [0, 30], "connector_disp": [30, 38], "connector_vel": [38, 46]}
    assert value["connector"]["d_definition"] == "vehicle_anchor-payload_anchor"
    assert value["physical_scales"]["connector_disp_m"] == .05
