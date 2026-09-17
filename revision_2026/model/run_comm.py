"""C0 unprotected communication-degradation diagnosis on the 100 m maneuver."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from channel import CONDITIONS, generate_trace
from four_vehicle_coupled import ModelParams, aggregate_diagnostics, initialize_state, rk4_step, split_state
from steering_allocator import AllocationConfig, allocate_controls


CONTROL_PERIOD_S = 0.02
DT_S = 0.002
CONTROL_STEPS = int(round(CONTROL_PERIOD_S / DT_S))


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


def simulate(condition: str, seed: int, protection: str = "none") -> dict:
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
            # Protected receiver rejects stale reordered packets; unprotected accepts all.
            for packet in queue.pop(control_tick, []):
                receiver, sender = packet["receiver"], packet["sender"]
                if protection == "protected" and packet["sequence"] <= latest_sequence[receiver, sender]:
                    rejected_stale += 1
                    continue
                knowledge[receiver][sender] = packet["data"]
                sent_tick[receiver, sender] = packet["sent_tick"]
                latest_sequence[receiver, sender] = packet["sequence"]
            rows = []
            for receiver in range(4):
                view_blocks = [item.copy() for item in knowledge[receiver]]
                view_blocks[receiver] = true_blocks[receiver]
                remote_aoi = control_tick - sent_tick[receiver]
                remote_aoi[receiver] = 0
                maximum_aoi = int(np.max(remote_aoi))
                quality = float(np.exp(-maximum_aoi / 10.0))
                config = AllocationConfig()
                if protection == "protected":
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
                    else:
                        config = AllocationConfig(
                            speed_gain=0.8 * quality,
                            max_zero_sum_accel_mps2=0.8 * max(quality, 0.5),
                        )
                view = assemble(view_blocks)
                candidate, _ = allocate_controls(view, accel, front, rear, params, config=config)
                command = candidate[receiver].copy()
                if protection == "protected" and (quality < 0.999 or previous_quality[receiver] < 0.999):
                    accel_step = 0.20
                    steer_step = np.deg2rad(2.0)
                    command[0] = np.clip(command[0], controls[receiver, 0] - accel_step, controls[receiver, 0] + accel_step)
                    command[1] = np.clip(command[1], controls[receiver, 1] - steer_step, controls[receiver, 1] + steer_step)
                rows.append(command)
                previous_quality[receiver] = quality
            controls = np.asarray(rows)
            aoi = control_tick - sent_tick
            aoi[np.arange(4), np.arange(4)] = 0
            max_aoi = max(max_aoi, int(np.max(aoi)))
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
            records.append(
                {
                    "t_s": t,
                    "distance_m": distance,
                    "stage": stage,
                    "payload": payload.copy(),
                    "vehicles": vehicles.copy(),
                    "peak_force_n": float(np.max(current_force)),
                    "q_abs_n": float(max(abs(diag["q_front_rear_n"]), abs(diag["q_left_right_n"]))),
                }
            )
        next_state = rk4_step(state, controls, DT_S, params)
        _, next_payload = split_state(next_state)
        next_speed = float(np.linalg.norm(next_payload[3:5]))
        distance += 0.5 * (speed + next_speed) * DT_S
        state = next_state
        t += DT_S

    _, payload = split_state(state)
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
        "max_formation_displacement_m": max_formation,
        "max_internal_force_residual_n": max_internal,
        "max_aoi_ticks": max_aoi,
        "packet_delivery_ratio": trace["packet_delivery_ratio"],
        "mean_delay_ticks_delivered": trace["mean_delay_ticks_delivered"],
        "rejected_stale_packets": rejected_stale,
        "fallback_receiver_ticks": fallback_receiver_ticks,
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


def plot(summary: dict, output: Path) -> None:
    conditions = list(CONDITIONS)
    force = [summary[c]["peak_force_mean_n"] / 1000.0 for c in conditions]
    force99 = [summary[c]["p99_force_mean_n"] / 1000.0 for c in conditions]
    error = [summary[c]["payload_position_rmse_mean_m"] for c in conditions]
    formation = [summary[c]["max_formation_mean_m"] for c in conditions]
    x = np.arange(len(conditions))
    fig, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    axes[0].bar(x - 0.18, force, 0.36, label="peak"); axes[0].bar(x + 0.18, force99, 0.36, label="P99")
    axes[0].axhline(12.0, color="red", linestyle="--", label="reference rated")
    axes[0].set_ylabel("Connector force [kN]"); axes[0].legend(); axes[0].grid(True, axis="y", alpha=0.3)
    axes[1].bar(x, error); axes[1].set_ylabel("Payload deviation RMSE [m]"); axes[1].grid(True, axis="y", alpha=0.3)
    axes[2].bar(x, formation); axes[2].set_ylabel("Max connector displacement [m]")
    axes[2].set_xticks(x, conditions); axes[2].grid(True, axis="y", alpha=0.3)
    fig.suptitle("C0: unprotected communication degradation on the 100 m maneuver")
    fig.tight_layout(); fig.savefig(output / "need.png", dpi=180); plt.close(fig)


def main() -> None:
    output = Path(__file__).resolve().parent / "comm"
    output.mkdir(parents=True, exist_ok=True)
    seeds = [3101, 3102, 3103, 3104, 3105]
    all_results = []
    for seed in seeds:
        clean = simulate("clean", seed)
        clean.update(clean_reference_error(clean, clean))
        all_results.append(strip_records(clean))
        print("clean", seed, clean["completed"], clean["peak_connector_force_n"])
        for condition in ("light", "medium", "heavy"):
            result = simulate(condition, seed)
            result.update(clean_reference_error(result, clean))
            all_results.append(strip_records(result))
            print(condition, seed, result["completed"], result["peak_connector_force_n"], result["payload_position_rmse_m"])

    summary = {}
    for condition in CONDITIONS:
        rows = [row for row in all_results if row["condition"] == condition]
        summary[condition] = {
            "n": len(rows),
            "completion_rate": float(np.mean([row["completed"] for row in rows])),
            "peak_force_mean_n": float(np.mean([row["peak_connector_force_n"] for row in rows])),
            "p99_force_mean_n": float(np.mean([row["p99_connector_force_n"] for row in rows])),
            "opening_p99_mean_n": float(np.mean([row["p99_abs_opening_proxy_n"] for row in rows])),
            "max_formation_mean_m": float(np.mean([row["max_formation_displacement_m"] for row in rows])),
            "payload_position_rmse_mean_m": float(np.mean([row["payload_position_rmse_m"] for row in rows])),
            "payload_yaw_rmse_mean_rad": float(np.mean([row["payload_yaw_rmse_rad"] for row in rows])),
            "vehicle_position_rmse_mean_m": float(np.mean([row["vehicle_position_rmse_m"] for row in rows])),
            "packet_delivery_ratio_mean": float(np.mean([row["packet_delivery_ratio"] for row in rows])),
            "max_aoi_ticks_mean": float(np.mean([row["max_aoi_ticks"] for row in rows])),
        }
    clean_force = summary["clean"]["p99_force_mean_n"]
    clean_opening = summary["clean"]["opening_p99_mean_n"]
    degraded = summary["medium"]["p99_force_mean_n"] > 1.15 * clean_force or summary["heavy"]["p99_force_mean_n"] > 1.15 * clean_force
    opening_trigger = (
        summary["medium"]["opening_p99_mean_n"] > 1.15 * clean_opening
        or summary["heavy"]["opening_p99_mean_n"] > 1.15 * clean_opening
    )
    error_trigger = summary["medium"]["payload_position_rmse_mean_m"] > 0.10 or summary["heavy"]["payload_position_rmse_mean_m"] > 0.10
    completion_trigger = summary["medium"]["completion_rate"] < 1.0 or summary["heavy"]["completion_rate"] < 1.0
    need = bool(degraded or opening_trigger or error_trigger or completion_trigger)
    report = {
        "evidence_level": "E1/E2 diagnostic, five paired network seeds",
        "need_protection": need,
        "triggers": {
            "p99_force_increase_over_15pct": degraded,
            "p99_opening_increase_over_15pct": opening_trigger,
            "payload_deviation_over_0p10m": error_trigger,
            "completion_loss": completion_trigger,
        },
        "summary": summary,
        "runs": all_results,
    }
    (output / "need.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    plot(summary, output)
    print(json.dumps({"need_protection": need, "triggers": report["triggers"], "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
