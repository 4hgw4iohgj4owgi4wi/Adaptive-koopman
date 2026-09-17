"""T2-T4 force-chain verification for all four connectors."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import replace
import numpy as np

from four_vehicle_coupled import (
    ModelParams,
    aggregate_diagnostics,
    connector_diagnostics,
    cross2,
    initialize_state,
    rotation,
    split_state,
    system_derivative,
)


NAMES = ("FL", "FR", "RL", "RR")
DIRECTIONS = {
    "+x": np.array([1.0, 0.0]),
    "-x": np.array([-1.0, 0.0]),
    "+y": np.array([0.0, 1.0]),
    "-y": np.array([0.0, -1.0]),
}


def displaced_state(params: ModelParams, changes: dict[int, np.ndarray], velocity_changes=None) -> np.ndarray:
    state = initialize_state(params, speed_mps=2.0)
    velocity_changes = {} if velocity_changes is None else velocity_changes
    for index, displacement_world in changes.items():
        state[6 * index : 6 * index + 2] += displacement_world
    for index, velocity_world in velocity_changes.items():
        yaw = state[6 * index + 2]
        state[6 * index + 3 : 6 * index + 5] += rotation(yaw).T @ velocity_world
    return state


def assert_close(actual, expected, tolerance=1.0e-9, label="value") -> None:
    if not np.allclose(actual, expected, rtol=1.0e-9, atol=tolerance):
        raise AssertionError(f"{label}: actual={actual}, expected={expected}")


def run(output: Path) -> dict:
    params = ModelParams()
    params_connector_off = replace(
        params,
        connector=replace(params.connector, free_play_m=10.0),
    )
    controls = np.zeros((4, 2), dtype=float)
    cases = []
    max_action_reaction = 0.0
    max_vehicle_derivative_error = 0.0
    max_payload_force_error = 0.0
    max_payload_moment_error = 0.0

    # T2 and T3: four points x four directions x loading/unloading velocity.
    for index, name in enumerate(NAMES):
        for direction_name, direction in DIRECTIONS.items():
            for velocity_sign in (+1.0, -1.0):
                displacement = 0.012 * direction
                relative_velocity = velocity_sign * 0.20 * direction
                state = displaced_state(
                    params,
                    {index: displacement},
                    {index: relative_velocity},
                )
                conn = connector_diagnostics(state, params)
                active = np.flatnonzero(conn["force_norm_n"] > 1.0e-9)
                assert np.array_equal(active, np.array([index]))
                force_payload = conn["force_payload_world_n"][index]
                force_vehicle = conn["force_vehicle_world_n"][index]
                if float(force_payload @ direction) <= 0.0:
                    raise AssertionError(f"wrong force direction for {name}/{direction_name}")
                action_error = float(np.linalg.norm(force_payload + force_vehicle))
                max_action_reaction = max(max_action_reaction, action_error)
                assert action_error <= 1.0e-9
                assert conn["damping_power_w"][index] >= 0.0
                if velocity_sign < 0.0:
                    assert_close(conn["damping_power_w"][index], 0.0, label="unloading damping power")

                derivative, _ = system_derivative(state, controls, params)
                derivative_off, _ = system_derivative(state, controls, params_connector_off)
                vehicle_derivative = (
                    derivative[:24].reshape(4, 6)[index]
                    - derivative_off[:24].reshape(4, 6)[index]
                )
                force_body = conn["force_vehicle_body_n"][index]
                expected_dvx = force_body[0] / params.vehicle.mass_kg
                expected_dvy = force_body[1] / params.vehicle.mass_kg
                expected_dr = conn["vehicle_moment_nm"][index] / params.vehicle.yaw_inertia_kgm2
                error = max(
                    abs(vehicle_derivative[3] - expected_dvx),
                    abs(vehicle_derivative[4] - expected_dvy),
                    abs(vehicle_derivative[5] - expected_dr),
                )
                max_vehicle_derivative_error = max(max_vehicle_derivative_error, error)
                assert error <= 1.0e-9
                cases.append(
                    {
                        "vehicle": name,
                        "direction": direction_name,
                        "velocity_sign": velocity_sign,
                        "force_norm_n": float(conn["force_norm_n"][index]),
                        "force_angle_deg": float(np.rad2deg(np.arctan2(force_payload[1], force_payload[0]))),
                        "damping_power_w": float(conn["damping_power_w"][index]),
                        "action_reaction_error_n": action_error,
                        "vehicle_derivative_error": error,
                    }
                )

    # Loading force must exceed unloading force for identical deformation.
    for name in NAMES:
        for direction_name in DIRECTIONS:
            pair = [c for c in cases if c["vehicle"] == name and c["direction"] == direction_name]
            loading = next(c for c in pair if c["velocity_sign"] > 0)
            unloading = next(c for c in pair if c["velocity_sign"] < 0)
            assert loading["force_norm_n"] > unloading["force_norm_n"]

    # T4 patterns: net longitudinal, net lateral, pure yaw and two opening modes.
    pattern_vectors = {
        "net_x": {i: 0.012 * np.array([1.0, 0.0]) for i in range(4)},
        "net_y": {i: 0.012 * np.array([0.0, 1.0]) for i in range(4)},
        "front_rear_open": {
            0: np.array([0.012, 0.0]), 1: np.array([0.012, 0.0]),
            2: np.array([-0.012, 0.0]), 3: np.array([-0.012, 0.0]),
        },
        "left_right_open": {
            0: np.array([0.0, 0.012]), 2: np.array([0.0, 0.012]),
            1: np.array([0.0, -0.012]), 3: np.array([0.0, -0.012]),
        },
    }
    anchors = params.payload_anchor_body_m
    pure_yaw = {}
    for i, arm in enumerate(anchors):
        tangent = np.array([-arm[1], arm[0]])
        pure_yaw[i] = 0.012 * tangent / np.linalg.norm(tangent)
    pattern_vectors["pure_yaw"] = pure_yaw

    patterns = {}
    for pattern, changes in pattern_vectors.items():
        state = displaced_state(params, changes)
        derivative, _ = system_derivative(state, controls, params)
        diag = aggregate_diagnostics(state, controls, params)
        conn = diag["connectors"]
        _, payload = split_state(state)
        payload_derivative = derivative[24:]
        net_force_world = np.sum(conn["force_payload_world_n"], axis=0)
        expected_accel_body = rotation(payload[2]).T @ (net_force_world / params.payload.mass_kg)
        expected_yaw_accel = np.sum(conn["payload_moment_nm"]) / params.payload.yaw_inertia_kgm2
        force_error = float(np.max(np.abs(payload_derivative[3:5] - expected_accel_body)))
        moment_error = float(abs(payload_derivative[5] - expected_yaw_accel))
        max_payload_force_error = max(max_payload_force_error, force_error)
        max_payload_moment_error = max(max_payload_moment_error, moment_error)
        assert force_error <= 1.0e-9
        assert moment_error <= 1.0e-9
        assert diag["internal_force_residual_n"].max() <= 1.0e-9
        patterns[pattern] = {
            "net_force_world_n": net_force_world.tolist(),
            "net_moment_nm": float(np.sum(conn["payload_moment_nm"])),
            "q_front_rear_n": diag["q_front_rear_n"],
            "q_left_right_n": diag["q_left_right_n"],
            "force_reconstruction_error": force_error,
            "moment_reconstruction_error": moment_error,
        }

    assert np.linalg.norm(patterns["front_rear_open"]["net_force_world_n"]) <= 1.0e-9
    assert patterns["front_rear_open"]["q_front_rear_n"] > 0.0
    assert np.linalg.norm(patterns["left_right_open"]["net_force_world_n"]) <= 1.0e-9
    assert patterns["left_right_open"]["q_left_right_n"] > 0.0
    assert np.linalg.norm(patterns["pure_yaw"]["net_force_world_n"]) <= 1.0e-9
    assert patterns["pure_yaw"]["net_moment_nm"] > 0.0

    report = {
        "passed": True,
        "connector_cases": len(cases),
        "max_action_reaction_error_n": max_action_reaction,
        "max_vehicle_derivative_error": max_vehicle_derivative_error,
        "max_payload_force_reconstruction_error": max_payload_force_error,
        "max_payload_moment_reconstruction_error": max_payload_moment_error,
        "patterns": patterns,
        "cases": cases,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "force.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    report = run(Path(__file__).resolve().parent / "force_test")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
