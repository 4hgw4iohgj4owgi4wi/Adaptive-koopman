"""N2 force-first communication protection with the frozen M1/S5 predictor.

This runner deliberately leaves the failed K4/M3 branch untouched.  It compares
the previously evaluated N1 receiver against a small, causal safety filter that
uses the frozen K2 ``S3-U1-lifted`` model (the K4 ``M1 fixed S5-operational``
contract) to forecast connector and payload differential loads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from channel import generate_trace
from four_vehicle_coupled import (
    ModelParams,
    aggregate_diagnostics,
    connector_diagnostics,
    initialize_state,
    rk4_step,
    rotation,
    split_state,
)
from steering_allocator import AllocationConfig, allocate_controls


CONTROL_PERIOD_S = 0.02
DT_S = 0.002
CONTROL_STEPS = int(round(CONTROL_PERIOD_S / DT_S))
ROOT = Path(__file__).resolve().parents[2]
S5_PATH = ROOT / "revision_2026" / "koopman" / "k2" / "linear" / "models" / "S3-U1-lifted.npz"
NORMALIZER_PATH = ROOT / "revision_2026" / "koopman" / "k3" / "development" / "normalizers.npz"
S5_SHA256 = "A3EA666624E3A01BCE2B173881990906BE1B1A2EEF10465FC82AC92C813757E3"
NORMALIZER_SHA256 = "0902E2544EE16FD4138BF642802C06CF627C8EF3F501CBAE87B3111249395DD5"

# Operational envelopes are intentionally below the provisional 12 kN connector
# reference.  They are controller design limits, not material safety certificates.
FORECAST_CONNECTOR_LIMIT_N = 3000.0
FORECAST_LOAD_LIMIT_N = 1200.0
FORECAST_HORIZON = 5
RECOVERY_HOLD_TICKS = 25
N2_ALPHAS = np.asarray([1.0, 0.75, 0.50, 0.25, 0.0], dtype=float)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


class FixedS5:
    """Read-only runtime for the frozen M1 fixed S5-operational model."""

    def __init__(self) -> None:
        if file_sha256(S5_PATH) != S5_SHA256:
            raise RuntimeError("frozen S5 model hash mismatch")
        if file_sha256(NORMALIZER_PATH) != NORMALIZER_SHA256:
            raise RuntimeError("S5 normalizer hash mismatch")
        with np.load(S5_PATH, allow_pickle=False) as source:
            self.metadata = json.loads(str(source["metadata_json"].item()))
            self.x_mean = np.asarray(source["x_mean"], dtype=float)
            self.x_std = np.asarray(source["x_std"], dtype=float)
            self.u_mean = np.asarray(source["u_mean"], dtype=float)
            self.u_std = np.asarray(source["u_std"], dtype=float)
            self.transition = np.asarray(source["transition"], dtype=float)
            self.decode_force = np.asarray(source["decode_force"], dtype=float)
        with np.load(NORMALIZER_PATH, allow_pickle=False) as source:
            self.force_mean = np.asarray(source["force_mean"], dtype=float)
            self.force_std = np.asarray(source["force_std"], dtype=float)
            normal_s3_mean = np.asarray(source["s3_mean"], dtype=float)
            normal_s3_std = np.asarray(source["s3_std"], dtype=float)
            normal_u1_mean = np.asarray(source["u1_mean"], dtype=float)
            normal_u1_std = np.asarray(source["u1_std"], dtype=float)
        expected = {
            "name": "S3-U1-lifted",
            "state_key": "s3_deform",
            "input_key": "u1_four",
            "state_dim": 46,
            "input_dim": 8,
            "lift_dim": 93,
        }
        if any(self.metadata.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"unexpected S5 contract: {self.metadata}")
        differences = [
            np.max(np.abs(self.x_mean - normal_s3_mean)),
            np.max(np.abs(self.x_std - normal_s3_std)),
            np.max(np.abs(self.u_mean - normal_u1_mean)),
            np.max(np.abs(self.u_std - normal_u1_std)),
        ]
        if max(differences) > 2.0e-5:
            raise RuntimeError(f"S5/normalizer moment mismatch: {differences}")

    @staticmethod
    def _basis(x_norm: np.ndarray) -> np.ndarray:
        clipped = np.clip(x_norm, -8.0, 8.0)
        return np.concatenate([np.ones((x_norm.shape[0], 1)), x_norm, clipped * clipped], axis=1)

    @staticmethod
    def _s3(state: np.ndarray, params: ModelParams) -> np.ndarray:
        vehicles, payload = split_state(state)
        conn = connector_diagnostics(state, params)
        payload_rotation = rotation(payload[2])
        displacement_body = np.asarray(conn["displacement_world_m"], dtype=float) @ payload_rotation
        payload_anchor_velocity = np.empty((4, 2), dtype=float)
        vehicle_anchor_velocity = np.empty((4, 2), dtype=float)
        payload_center_velocity = payload_rotation @ payload[3:5]
        for index in range(4):
            payload_arm = payload_rotation @ params.payload_anchor_body_m[index]
            payload_anchor_velocity[index] = payload_center_velocity + payload[5] * np.array(
                [-payload_arm[1], payload_arm[0]]
            )
            vehicle_rotation = rotation(vehicles[index, 2])
            vehicle_arm = vehicle_rotation @ np.asarray(params.vehicle_anchor_body_m[index], dtype=float)
            vehicle_anchor_velocity[index] = vehicle_rotation @ vehicles[index, 3:5] + vehicles[index, 5] * np.array(
                [-vehicle_arm[1], vehicle_arm[0]]
            )
        relative_velocity_body = (vehicle_anchor_velocity - payload_anchor_velocity) @ payload_rotation
        return np.r_[np.asarray(state, dtype=float), displacement_body.reshape(-1), relative_velocity_body.reshape(-1)]

    def forecast(self, state: np.ndarray, control_sets: np.ndarray, params: ModelParams) -> dict[str, np.ndarray]:
        controls = np.asarray(control_sets, dtype=float)
        if controls.ndim != 3 or controls.shape[1:] != (4, 2):
            raise ValueError(f"expected [candidate,4,2] controls, got {controls.shape}")
        x_norm = (self._s3(state, params) - self.x_mean) / self.x_std
        z = np.repeat(self._basis(x_norm[None, :]), controls.shape[0], axis=0)
        u_norm = (controls.reshape(controls.shape[0], 8) - self.u_mean) / self.u_std
        max_connector = np.zeros(controls.shape[0], dtype=float)
        max_load = np.zeros(controls.shape[0], dtype=float)
        for _ in range(FORECAST_HORIZON):
            z = np.concatenate([z, u_norm], axis=1) @ self.transition
            force = z @ self.decode_force * self.force_std + self.force_mean
            point_force = force[:, :8].reshape(-1, 4, 2)
            max_connector = np.maximum(max_connector, np.max(np.linalg.norm(point_force, axis=2), axis=1))
            max_load = np.maximum(max_load, np.max(np.abs(force[:, 8:10]), axis=1))
        score = np.maximum(
            max_connector / FORECAST_CONNECTOR_LIMIT_N,
            max_load / FORECAST_LOAD_LIMIT_N,
        )
        if not all(np.all(np.isfinite(value)) for value in (max_connector, max_load, score)):
            raise FloatingPointError("non-finite S5 force forecast")
        return {"connector_n": max_connector, "load_n": max_load, "score": score}


def wrap(angle: np.ndarray) -> np.ndarray:
    return (angle + np.pi) % (2.0 * np.pi) - np.pi


def stage_command(distance: float, t: float, turn_start: float | None, decel: float | None, speed: float):
    if distance < 30.0:
        return "accelerate", 0.5, 0.0, 0.0, turn_start, decel
    if turn_start is None:
        turn_start = t
    elapsed = t - turn_start
    if elapsed < 5.0:
        return "step_positive", 0.0, 4.0, -2.0, turn_start, decel
    if elapsed < 10.0:
        return "step_negative", 0.0, -4.0, 2.0, turn_start, decel
    if decel is None:
        decel = float(np.clip(-speed**2 / (2.0 * max(100.0 - distance, 0.5)), -2.0, -0.1))
    return "decelerate", decel, 0.0, 0.0, turn_start, decel


def blocks(state: np.ndarray) -> list[np.ndarray]:
    vehicles, payload = split_state(state)
    return [vehicles[i].copy() for i in range(4)] + [payload.copy()]


def assemble(block_list: list[np.ndarray]) -> np.ndarray:
    return np.concatenate([np.vstack(block_list[:4]).reshape(-1), block_list[4]])


def predict_block(block: np.ndarray, age_s: float) -> np.ndarray:
    predicted = np.asarray(block, dtype=float).copy()
    yaw = float(predicted[2])
    c, s = np.cos(yaw), np.sin(yaw)
    world_velocity = np.array(
        [c * predicted[3] - s * predicted[4], s * predicted[3] + c * predicted[4]]
    )
    predicted[:2] += world_velocity * age_s
    predicted[2] = float(wrap(np.array([predicted[2] + predicted[5] * age_s]))[0])
    return predicted


def trace_sha256(trace: dict) -> str:
    rows = []
    for tick in sorted(trace["sends"]):
        for event in trace["sends"][tick]:
            rows.append(
                [
                    int(tick),
                    int(event["receiver"]),
                    int(event["sender"]),
                    int(event["sequence"]),
                    int(event["sent_tick"]),
                    int(event["arrival_tick"]),
                ]
            )
    payload = json.dumps(rows, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def simulate(
    condition: str,
    seed: int,
    protection: str = "none",
    predictor: FixedS5 | None = None,
) -> dict:
    if protection not in {"none", "n1", "n2"}:
        raise ValueError(protection)
    if protection == "n2" and predictor is None:
        raise ValueError("N2 requires the frozen S5 predictor")
    params = ModelParams()
    max_time_s = 60.0
    max_control_ticks = int(np.ceil(max_time_s / CONTROL_PERIOD_S)) + 10
    trace = generate_trace(condition, seed, max_control_ticks)
    state = initialize_state(params, speed_mps=2.0)
    knowledge = [[block.copy() for block in blocks(state)] for _ in range(4)]
    sent_tick = np.zeros((4, 5), dtype=int)
    latest_sequence = np.full((4, 5), -1, dtype=int)
    queue: dict[int, list[dict]] = {}
    controls = np.zeros((4, 2), dtype=float)
    t = 0.0
    distance = 0.0
    turn_start = None
    decel = None
    control_tick = 0
    records = []
    force_samples = []
    q_samples = []
    max_force = 0.0
    max_formation = 0.0
    max_aoi = 0
    max_internal = 0.0
    rejected_stale = 0
    fallback_receiver_ticks = 0
    previous_quality = np.ones(4, dtype=float)
    recovery_hold = np.zeros(4, dtype=int)
    n2_filter_receiver_ticks = 0
    n2_alpha_samples = []
    forecast_connector_samples = []
    forecast_load_samples = []
    tick_maximum_aoi = 0
    tick_fallback_receivers = 0
    tick_protection_active_receivers = 0
    tick_n2_alpha_mean = 1.0

    while distance < 100.0 and t < max_time_s:
        vehicles, payload = split_state(state)
        speed = float(np.linalg.norm(payload[3:5]))
        stage, accel, front, rear, turn_start, decel = stage_command(distance, t, turn_start, decel, speed)
        if int(round(t / DT_S)) % CONTROL_STEPS == 0:
            true_blocks = blocks(state)
            for event in trace["sends"].get(control_tick, []):
                packet = dict(event)
                packet["data"] = true_blocks[event["sender"]].copy()
                queue.setdefault(event["arrival_tick"], []).append(packet)
            # Protected receivers reject stale reordered packets; unprotected accepts all.
            for packet in queue.pop(control_tick, []):
                receiver, sender = packet["receiver"], packet["sender"]
                if protection in {"n1", "n2"} and packet["sequence"] <= latest_sequence[receiver, sender]:
                    rejected_stale += 1
                    continue
                knowledge[receiver][sender] = packet["data"]
                sent_tick[receiver, sender] = packet["sent_tick"]
                latest_sequence[receiver, sender] = packet["sequence"]
            rows = []
            tick_aois = []
            tick_fallback = 0
            tick_active = 0
            tick_alphas = []
            for receiver in range(4):
                view_blocks = [item.copy() for item in knowledge[receiver]]
                view_blocks[receiver] = true_blocks[receiver]
                remote_aoi = control_tick - sent_tick[receiver]
                remote_aoi[receiver] = 0
                maximum_aoi = int(np.max(remote_aoi))
                quality = float(np.exp(-maximum_aoi / 10.0))
                config = AllocationConfig()
                if protection in {"n1", "n2"}:
                    for sender in range(5):
                        if sender == receiver:
                            continue
                        view_blocks[sender] = predict_block(
                            view_blocks[sender],
                            float(remote_aoi[sender]) * CONTROL_PERIOD_S,
                        )
                    if maximum_aoi > 10:
                        config = AllocationConfig(
                            speed_gain=0.0,
                            max_steering_deg=12.0,
                            max_zero_sum_accel_mps2=0.4,
                        )
                        fallback_receiver_ticks += 1
                        tick_fallback += 1
                    else:
                        config = AllocationConfig(
                            speed_gain=0.8 * quality,
                            max_zero_sum_accel_mps2=0.8 * max(quality, 0.5),
                        )
                view = assemble(view_blocks)
                candidate, _ = allocate_controls(view, accel, front, rear, params, config=config)
                command = candidate[receiver].copy()

                if protection == "n2":
                    if maximum_aoi > 3:
                        recovery_hold[receiver] = RECOVERY_HOLD_TICKS
                    elif recovery_hold[receiver] > 0:
                        recovery_hold[receiver] -= 1
                    n2_active = bool(maximum_aoi > 0 or recovery_hold[receiver] > 0)
                    alpha = 1.0
                    if n2_active:
                        tick_active += 1
                        safe_config = AllocationConfig(
                            speed_gain=0.0,
                            max_steering_deg=10.0,
                            max_zero_sum_accel_mps2=0.0,
                        )
                        safe_candidate, _ = allocate_controls(
                            view, accel, front, rear, params, config=safe_config
                        )
                        control_sets = (
                            N2_ALPHAS[:, None, None] * candidate[None, :, :]
                            + (1.0 - N2_ALPHAS[:, None, None]) * safe_candidate[None, :, :]
                        )
                        forecast = predictor.forecast(view, control_sets, params)
                        feasible = (
                            (forecast["connector_n"] <= FORECAST_CONNECTOR_LIMIT_N)
                            & (forecast["load_n"] <= FORECAST_LOAD_LIMIT_N)
                        )
                        feasible_indices = np.flatnonzero(feasible)
                        selected = int(feasible_indices[0]) if feasible_indices.size else int(np.argmin(forecast["score"]))
                        alpha = float(N2_ALPHAS[selected])
                        command = control_sets[selected, receiver].copy()
                        forecast_connector_samples.append(float(forecast["connector_n"][selected]))
                        forecast_load_samples.append(float(forecast["load_n"][selected]))
                        if alpha < 1.0:
                            n2_filter_receiver_ticks += 1
                    tick_alphas.append(alpha)
                    n2_alpha_samples.append(alpha)
                    if n2_active or previous_quality[receiver] < 0.999:
                        accel_step = 0.08
                        steer_step = np.deg2rad(0.5)
                        command[0] = np.clip(
                            command[0],
                            controls[receiver, 0] - accel_step,
                            controls[receiver, 0] + accel_step,
                        )
                        command[1] = np.clip(
                            command[1],
                            controls[receiver, 1] - steer_step,
                            controls[receiver, 1] + steer_step,
                        )
                elif protection == "n1" and (quality < 0.999 or previous_quality[receiver] < 0.999):
                    accel_step = 0.20
                    steer_step = np.deg2rad(2.0)
                    command[0] = np.clip(command[0], controls[receiver, 0] - accel_step, controls[receiver, 0] + accel_step)
                    command[1] = np.clip(command[1], controls[receiver, 1] - steer_step, controls[receiver, 1] + steer_step)
                rows.append(command)
                previous_quality[receiver] = quality
                tick_aois.append(maximum_aoi)
            controls = np.asarray(rows)
            aoi = control_tick - sent_tick
            aoi[np.arange(4), np.arange(4)] = 0
            max_aoi = max(max_aoi, int(np.max(aoi)))
            tick_maximum_aoi = max(tick_aois, default=0)
            tick_fallback_receivers = tick_fallback
            tick_protection_active_receivers = tick_active if protection == "n2" else tick_fallback
            tick_n2_alpha_mean = float(np.mean(tick_alphas)) if tick_alphas else 1.0
            control_tick += 1

        diag = aggregate_diagnostics(state, controls, params)
        conn = diag["connectors"]
        current_force = np.asarray(conn["force_norm_n"])
        force_samples.extend(current_force.tolist())
        q_samples.extend([diag["q_front_rear_n"], diag["q_left_right_n"]])
        max_force = max(max_force, float(np.max(current_force)))
        max_formation = max(
            max_formation,
            float(np.max(np.linalg.norm(conn["displacement_world_m"], axis=1))),
        )
        max_internal = max(max_internal, float(np.linalg.norm(diag["internal_force_residual_n"])))
        if int(round(t / DT_S)) % CONTROL_STEPS == 0:
            force_body = np.asarray(conn["force_payload_body_n"], dtype=float)
            records.append(
                {
                    "t_s": t,
                    "distance_m": distance,
                    "stage": stage,
                    "payload": payload.copy(),
                    "vehicles": vehicles.copy(),
                    "peak_force_n": float(np.max(current_force)),
                    "connector_force_n": current_force.copy(),
                    "connector_force_body_n": force_body.copy(),
                    "connector_direction_deg": np.rad2deg(np.arctan2(force_body[:, 1], force_body[:, 0])),
                    "q_front_rear_n": float(diag["q_front_rear_n"]),
                    "q_left_right_n": float(diag["q_left_right_n"]),
                    "q_abs_n": float(max(abs(diag["q_front_rear_n"]), abs(diag["q_left_right_n"]))),
                    "vehicle_yaw_rate_radps": vehicles[:, 5].copy(),
                    "payload_yaw_rate_radps": float(payload[5]),
                    "system_yaw_rate_radps": float(diag["system_yaw_rate_radps"]),
                    "max_aoi_ticks": int(tick_maximum_aoi),
                    "fallback_receivers": int(tick_fallback_receivers),
                    "protection_active_receivers": int(tick_protection_active_receivers),
                    "n2_alpha_mean": float(tick_n2_alpha_mean),
                }
            )
        next_state = rk4_step(state, controls, DT_S, params)
        _, next_payload = split_state(next_state)
        next_speed = float(np.linalg.norm(next_payload[3:5]))
        distance += 0.5 * (speed + next_speed) * DT_S
        state = next_state
        t += DT_S

    _, payload = split_state(state)
    tick_force = np.asarray([row["peak_force_n"] for row in records], dtype=float)
    tick_active = np.asarray([row["protection_active_receivers"] for row in records], dtype=int)
    force_rate = np.abs(np.diff(tick_force)) / CONTROL_PERIOD_S
    recovery_jumps = []
    for index in range(1, tick_active.size):
        if tick_active[index - 1] > 0 and tick_active[index] == 0:
            stop = min(index + RECOVERY_HOLD_TICKS, tick_force.size)
            recovery_jumps.append(float(np.max(np.abs(tick_force[index:stop] - tick_force[index - 1]))))
    return {
        "condition": condition,
        "seed": seed,
        "protection": protection,
        "completed": bool(distance >= 99.9),
        "distance_m": distance,
        "time_s": t,
        "final_speed_mps": float(np.linalg.norm(payload[3:5])),
        "peak_connector_force_n": max_force,
        "p95_connector_force_n": float(np.percentile(force_samples, 95)),
        "p99_connector_force_n": float(np.percentile(force_samples, 99)),
        "p99_abs_opening_proxy_n": float(np.percentile(np.abs(q_samples), 99)),
        "p99_force_rate_nps": float(np.percentile(force_rate, 99)) if force_rate.size else 0.0,
        "max_recovery_force_jump_n": float(max(recovery_jumps, default=0.0)),
        "recovery_event_count": int(len(recovery_jumps)),
        "max_formation_displacement_m": max_formation,
        "max_internal_force_residual_n": max_internal,
        "max_aoi_ticks": max_aoi,
        "packet_delivery_ratio": trace["packet_delivery_ratio"],
        "mean_delay_ticks_delivered": trace["mean_delay_ticks_delivered"],
        "trace_sha256": trace_sha256(trace),
        "rejected_stale_packets": rejected_stale,
        "fallback_receiver_ticks": fallback_receiver_ticks,
        "n2_filter_receiver_ticks": n2_filter_receiver_ticks,
        "n2_alpha_mean": float(np.mean(n2_alpha_samples)) if n2_alpha_samples else 1.0,
        "s5_forecast_connector_max_n": float(max(forecast_connector_samples, default=0.0)),
        "s5_forecast_load_max_n": float(max(forecast_load_samples, default=0.0)),
        "state_finite": bool(np.all(np.isfinite(state))),
        "records": records,
    }


def clean_reference_error(result: dict, clean: dict) -> dict:
    ref = clean["records"]
    cur = result["records"]
    n = min(len(ref), len(cur))
    if n == 0:
        return {"payload_position_rmse_m": np.nan, "payload_yaw_rmse_rad": np.nan, "vehicle_position_rmse_m": np.nan}
    payload_pos = []
    payload_yaw = []
    vehicle_pos = []
    for index in range(n):
        payload_pos.append(np.linalg.norm(cur[index]["payload"][:2] - ref[index]["payload"][:2]))
        payload_yaw.append(float(wrap(np.array([cur[index]["payload"][2] - ref[index]["payload"][2]]))[0]))
        vehicle_pos.extend(np.linalg.norm(cur[index]["vehicles"][:, :2] - ref[index]["vehicles"][:, :2], axis=1).tolist())
    return {
        "payload_position_rmse_m": float(np.sqrt(np.mean(np.square(payload_pos)))),
        "payload_yaw_rmse_rad": float(np.sqrt(np.mean(np.square(payload_yaw)))),
        "vehicle_position_rmse_m": float(np.sqrt(np.mean(np.square(vehicle_pos)))),
    }


def strip_records(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "records"}


def json_default(value):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=json_default) + "\n",
        encoding="utf-8",
    )


def summarize(rows: list[dict], method: str, condition: str) -> dict:
    selected = [row for row in rows if row["protection"] == method and row["condition"] == condition]
    metric_map = {
        "peak_force_mean_n": "peak_connector_force_n",
        "p99_force_mean_n": "p99_connector_force_n",
        "load_p99_mean_n": "p99_abs_opening_proxy_n",
        "force_rate_p99_mean_nps": "p99_force_rate_nps",
        "recovery_jump_mean_n": "max_recovery_force_jump_n",
        "recovery_events_mean": "recovery_event_count",
        "payload_rmse_mean_m": "payload_position_rmse_m",
        "payload_yaw_rmse_mean_rad": "payload_yaw_rmse_rad",
        "vehicle_rmse_mean_m": "vehicle_position_rmse_m",
        "filter_ticks_mean": "n2_filter_receiver_ticks",
        "alpha_mean": "n2_alpha_mean",
    }
    result = {
        "n": len(selected),
        "completion_rate": float(np.mean([row["completed"] for row in selected])),
        "finite_rate": float(np.mean([row["state_finite"] for row in selected])),
        "max_internal_force_residual_n": float(max(row["max_internal_force_residual_n"] for row in selected)),
        "max_connector_force_n": float(max(row["peak_connector_force_n"] for row in selected)),
    }
    for output_key, source_key in metric_map.items():
        result[output_key] = float(np.mean([row[source_key] for row in selected]))
    return result


def relative(candidate: float, baseline: float) -> float:
    return candidate / max(abs(baseline), 1.0e-12) - 1.0


def plot_comparison(report: dict, output: Path) -> None:
    metrics = [
        ("payload_rmse_change_fraction", "payload RMSE"),
        ("force_p99_change_fraction", "connector P99"),
        ("load_p99_change_fraction", "load P99"),
        ("force_rate_change_fraction", "force-rate P99"),
    ]
    conditions = ("medium", "heavy")
    x = np.arange(len(metrics))
    width = 0.36
    fig, ax = plt.subplots(figsize=(12, 5.8))
    for offset, condition in zip((-width / 2, width / 2), conditions):
        values = [100.0 * report["comparison"][condition][key] for key, _ in metrics]
        ax.bar(x + offset, values, width, label=condition)
    ax.axhline(0.0, color="black", lw=0.8)
    ax.axhline(5.0, color="tab:red", lw=0.8, ls="--", label="+5% non-worse gate")
    ax.set_xticks(x, [label for _, label in metrics], rotation=15)
    ax.set_ylabel("N2 relative to N1 (%)")
    ax.set_title("N2 fixed-S5 force-first protection: five paired seeds")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend()
    ax.text(
        0.01,
        0.02,
        "Recovery jump excluded: no identifiable N2 protection-exit event in heavy trace.",
        transform=ax.transAxes,
        fontsize=9,
        color="tab:red",
    )
    fig.tight_layout()
    fig.savefig(output / "compare.png", dpi=220)
    plt.close(fig)


def plot_dynamics(result: dict, output: Path) -> None:
    records = result["records"]
    t = np.asarray([row["t_s"] for row in records], dtype=float)
    force = np.asarray([row["connector_force_body_n"] for row in records], dtype=float)
    q = np.asarray([[row["q_front_rear_n"], row["q_left_right_n"]] for row in records], dtype=float)
    vehicle_yaw = np.asarray([row["vehicle_yaw_rate_radps"] for row in records], dtype=float)
    payload_yaw = np.asarray([row["payload_yaw_rate_radps"] for row in records], dtype=float)
    system_yaw = np.asarray([row["system_yaw_rate_radps"] for row in records], dtype=float)
    aoi = np.asarray([row["max_aoi_ticks"] for row in records], dtype=float)
    alpha = np.asarray([row["n2_alpha_mean"] for row in records], dtype=float)
    labels = ("FL", "FR", "RL", "RR")
    fig, axes = plt.subplots(5, 1, figsize=(14, 13), sharex=True)
    for index, label in enumerate(labels):
        axes[0].plot(t, force[:, index, 0], label=label)
        axes[1].plot(t, force[:, index, 1], label=label)
    axes[0].set_ylabel("Fx [N]")
    axes[0].set_title("Four connector horizontal force directions")
    axes[1].set_ylabel("Fy [N]")
    axes[1].set_title("Four connector vertical-in-plane force directions")
    axes[0].legend(ncol=4)
    axes[1].legend(ncol=4)
    axes[2].plot(t, q[:, 0], label="Q_FR")
    axes[2].plot(t, q[:, 1], label="Q_LR")
    axes[2].axhline(FORECAST_LOAD_LIMIT_N, color="tab:red", ls="--", lw=0.8)
    axes[2].axhline(-FORECAST_LOAD_LIMIT_N, color="tab:red", ls="--", lw=0.8)
    axes[2].set_ylabel("load [N]")
    axes[2].set_title("Payload differential tensile-load proxies")
    axes[2].legend()
    for index, label in enumerate(labels):
        axes[3].plot(t, vehicle_yaw[:, index], lw=0.9, alpha=0.7, label=f"{label} yaw")
    axes[3].plot(t, payload_yaw, color="black", lw=1.5, label="payload yaw")
    axes[3].plot(t, system_yaw, color="tab:red", lw=1.2, ls="--", label="system yaw")
    axes[3].set_ylabel("yaw rate [rad/s]")
    axes[3].legend(ncol=3)
    axes[4].step(t, aoi, where="post", label="max AoI [ticks]")
    axes[4].step(t, alpha, where="post", label="mean S5 blend alpha")
    axes[4].set_ylabel("network / filter")
    axes[4].set_xlabel("time [s]")
    axes[4].legend()
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.suptitle(f"N2 heavy trace, seed {result['seed']}: force directions, load and yaw")
    fig.tight_layout()
    fig.savefig(output / "heavy_dynamics.png", dpi=220)
    plt.close(fig)


def save_case(result: dict, output: Path) -> None:
    records = result["records"]
    np.savez_compressed(
        output,
        time_s=np.asarray([row["t_s"] for row in records], dtype=float),
        connector_force_body_n=np.asarray([row["connector_force_body_n"] for row in records], dtype=float),
        connector_direction_deg=np.asarray([row["connector_direction_deg"] for row in records], dtype=float),
        q_front_rear_n=np.asarray([row["q_front_rear_n"] for row in records], dtype=float),
        q_left_right_n=np.asarray([row["q_left_right_n"] for row in records], dtype=float),
        vehicle_yaw_rate_radps=np.asarray([row["vehicle_yaw_rate_radps"] for row in records], dtype=float),
        payload_yaw_rate_radps=np.asarray([row["payload_yaw_rate_radps"] for row in records], dtype=float),
        system_yaw_rate_radps=np.asarray([row["system_yaw_rate_radps"] for row in records], dtype=float),
        max_aoi_ticks=np.asarray([row["max_aoi_ticks"] for row in records], dtype=int),
        n2_alpha_mean=np.asarray([row["n2_alpha_mean"] for row in records], dtype=float),
    )


def write_stop(output: Path, report: dict) -> None:
    failed = [key for key, value in report["gate"].items() if not value]
    text = [
        "# N2停止与解决方案",
        "",
        "## 停止结论",
        "",
        "固定S5受力优先保护未通过预注册门，停止进入单移线、回头弯和后续DoS矩阵。",
        "",
        f"失败门：`{', '.join(failed)}`。",
        "",
        "## 解决顺序",
        "",
        "1. 不在3101–3105证据种子上继续调阈值；若重启，另建development网络种子与独立confirm种子。",
        "2. 若连接力/载荷仍恶化，将分布式单车独立blend改为共享可行域或显式四车一致性约束，避免各车滤波决策不一致。",
        "3. 若跟踪恶化，保留S5力约束但对纵向加速度和转角使用不同松弛变量，做预注册Pareto搜索。",
        "4. 若恢复冲击失败，把AoI滞环、恢复斜率和力变化率共同放入优化，不再只靠固定命令限幅。",
        "5. 暂定12/15 kN只能作为仿真参考；取得连接器与货物材料参数前不能作实际撕裂安全结论。",
        "",
        "## 完整数值",
        "",
        "```json",
        json.dumps({"gate": report["gate"], "comparison": report["comparison"]}, ensure_ascii=False, indent=2),
        "```",
    ]
    (output / "solutions.md").write_text("\n".join(text) + "\n", encoding="utf-8")


def run_smoke(output: Path, predictor: FixedS5) -> dict:
    seed = 3199
    rows = []
    detail = {}
    clean_reference = simulate("clean", seed, "n1", predictor)
    for method in ("n1", "n2"):
        for condition in ("clean", "heavy"):
            result = clean_reference if (method, condition) == ("n1", "clean") else simulate(condition, seed, method, predictor)
            result.update(clean_reference_error(result, clean_reference))
            rows.append(strip_records(result))
            detail[(method, condition)] = result
    gate = {
        "model_hash_exact": file_sha256(S5_PATH) == S5_SHA256,
        "normalizer_hash_exact": file_sha256(NORMALIZER_PATH) == NORMALIZER_SHA256,
        "trace_equal_clean": detail[("n1", "clean")]["trace_sha256"] == detail[("n2", "clean")]["trace_sha256"],
        "trace_equal_heavy": detail[("n1", "heavy")]["trace_sha256"] == detail[("n2", "heavy")]["trace_sha256"],
        "clean_transparent": detail[("n2", "clean")]["payload_position_rmse_m"] <= 1.0e-9,
        "all_complete_finite": all(row["completed"] and row["state_finite"] for row in rows),
    }
    report = {"stage": "N2_smoke_code_only", "seed": seed, "gate": gate, "passed": all(gate.values()), "runs": rows}
    write_json(output / "smoke.json", report)
    plot_dynamics(detail[("n2", "heavy")], output)
    save_case(detail[("n2", "heavy")], output / "smoke_heavy.npz")
    return report


def run_full(output: Path, predictor: FixedS5) -> dict:
    seeds = [3101, 3102, 3103, 3104, 3105]
    methods = ("n1", "n2")
    conditions = ("clean", "medium", "heavy")
    rows = []
    showcase = {}
    for seed in seeds:
        clean_reference = simulate("clean", seed, "n1", predictor)
        for method in methods:
            for condition in conditions:
                result = clean_reference if (method, condition) == ("n1", "clean") else simulate(
                    condition, seed, method, predictor
                )
                result.update(clean_reference_error(result, clean_reference))
                rows.append(strip_records(result))
                if seed == 3101 and condition == "heavy":
                    showcase[method] = result
                print(
                    json.dumps(
                        {
                            "seed": seed,
                            "condition": condition,
                            "method": method,
                            "completed": result["completed"],
                            "rmse_m": result["payload_position_rmse_m"],
                            "force_p99_n": result["p99_connector_force_n"],
                            "load_p99_n": result["p99_abs_opening_proxy_n"],
                        }
                    ),
                    flush=True,
                )
    summary = {
        method: {condition: summarize(rows, method, condition) for condition in conditions}
        for method in methods
    }
    comparison = {}
    for condition in ("medium", "heavy"):
        baseline = summary["n1"][condition]
        candidate = summary["n2"][condition]
        comparison[condition] = {
            "payload_rmse_change_fraction": relative(candidate["payload_rmse_mean_m"], baseline["payload_rmse_mean_m"]),
            "force_p99_change_fraction": relative(candidate["p99_force_mean_n"], baseline["p99_force_mean_n"]),
            "load_p99_change_fraction": relative(candidate["load_p99_mean_n"], baseline["load_p99_mean_n"]),
            "force_rate_change_fraction": relative(candidate["force_rate_p99_mean_nps"], baseline["force_rate_p99_mean_nps"]),
            "recovery_jump_change_fraction": relative(candidate["recovery_jump_mean_n"], baseline["recovery_jump_mean_n"]),
        }

    trace_equal = all(
        len({row["trace_sha256"] for row in rows if row["seed"] == seed and row["condition"] == condition}) == 1
        for seed in seeds
        for condition in conditions
    )
    clean_transparent = summary["n2"]["clean"]["payload_rmse_mean_m"] <= 1.0e-9
    all_physical = all(
        row["completed"]
        and row["state_finite"]
        and row["peak_connector_force_n"] < 12000.0
        and row["max_internal_force_residual_n"] <= 1.0e-9
        for row in rows
    )
    historical = json.loads(
        (Path(__file__).resolve().parent / "protect" / "protect.json").read_text(encoding="utf-8")
    )["protected_summary"]
    historical_differences = []
    for condition in conditions:
        for new_key, old_key in (
            ("p99_force_mean_n", "p99_force_mean_n"),
            ("load_p99_mean_n", "opening_p99_mean_n"),
            ("payload_rmse_mean_m", "payload_position_rmse_mean_m"),
        ):
            historical_differences.append(abs(summary["n1"][condition][new_key] - historical[condition][old_key]))
    historical_reproduced = max(historical_differences, default=0.0) <= 1.0e-9
    heavy_benefit = (
        comparison["heavy"]["force_p99_change_fraction"] <= -0.10
        or comparison["heavy"]["load_p99_change_fraction"] <= -0.10
    )
    gate = {
        "shared_trace_exact": trace_equal,
        "historical_N1_reproduced": historical_reproduced,
        "clean_transparent": clean_transparent,
        "all_complete_finite_and_physical": all_physical,
        "medium_force_p99_not_worse_5pct": comparison["medium"]["force_p99_change_fraction"] <= 0.05,
        "medium_load_p99_not_worse_5pct": comparison["medium"]["load_p99_change_fraction"] <= 0.05,
        "heavy_force_p99_not_worse_5pct": comparison["heavy"]["force_p99_change_fraction"] <= 0.05,
        "heavy_load_p99_not_worse_5pct": comparison["heavy"]["load_p99_change_fraction"] <= 0.05,
        "heavy_tracking_not_worse_10pct": comparison["heavy"]["payload_rmse_change_fraction"] <= 0.10,
        "heavy_force_rate_not_worse_5pct": comparison["heavy"]["force_rate_change_fraction"] <= 0.05,
        "heavy_recovery_observed_in_both": (
            summary["n1"]["heavy"]["recovery_events_mean"] > 0.0
            and summary["n2"]["heavy"]["recovery_events_mean"] > 0.0
        ),
        "heavy_recovery_jump_not_worse_5pct": comparison["heavy"]["recovery_jump_change_fraction"] <= 0.05,
        "heavy_force_or_load_improves_10pct": heavy_benefit,
    }
    report = {
        "stage": "N2_fixed_S5_force_first_100m",
        "predictor_contract": {
            "name": "M1 fixed S5-operational / S3-U1-lifted",
            "model_sha256": file_sha256(S5_PATH),
            "normalizer_sha256": file_sha256(NORMALIZER_PATH),
            "forecast_horizon_steps": FORECAST_HORIZON,
            "connector_operational_limit_n": FORECAST_CONNECTOR_LIMIT_N,
            "load_operational_limit_n": FORECAST_LOAD_LIMIT_N,
            "limits_are_material_certification": False,
        },
        "seeds": seeds,
        "conditions": conditions,
        "summary": summary,
        "comparison": comparison,
        "historical_N1_max_abs_difference": float(max(historical_differences, default=0.0)),
        "gate": gate,
        "passed": all(gate.values()),
        "interpretation_limit": "Q_FR/Q_LR are differential tensile-load proxies; no material tear verdict is possible without material and joint data.",
        "runs": rows,
    }
    write_json(output / "report.json", report)
    plot_comparison(report, output)
    plot_dynamics(showcase["n2"], output)
    save_case(showcase["n1"], output / "heavy_seed3101_n1.npz")
    save_case(showcase["n2"], output / "heavy_seed3101_n2.npz")
    if not report["passed"]:
        write_stop(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    if args.smoke == args.full:
        parser.error("choose exactly one of --smoke or --full")
    output = Path(__file__).resolve().parent / "n2"
    output.mkdir(parents=True, exist_ok=True)
    predictor = FixedS5()
    report = run_smoke(output, predictor) if args.smoke else run_full(output, predictor)
    print(json.dumps({"stage": report["stage"], "passed": report["passed"], "gate": report["gate"]}, indent=2))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
