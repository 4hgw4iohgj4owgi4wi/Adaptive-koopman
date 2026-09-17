"""EXP-R2 section 18.7 frozen-command actuator-discretization diagnostic."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np

from .cli import save, sha
from .e01_100m import DT, LIMIT, RATE, TAU, params
from .failure_boundary import consume_audit
from .plant.event_substep import EventSubstepConfig, advance_outer_step
from .plant.four_vehicle_common import connector_diagnostics, initialize_state, system_derivative


SOURCE_RAW_SHA256 = "C68CCAF51CACBA8FEFD17E135C5CDA1808417E67B76209F6F04D5A697EB4CC92"
WINDOWS = {
    "straight_acceleration": (0.0, 2.0),
    "steering_onset": (11.5, 2.0),
    "reverse_switch": (16.5, 2.0),
}
UPDATE_INTERVALS = (0.002, 0.001, 0.0005)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _source_data(path: Path, start_s: float, duration_s: float):
    if _file_sha256(path) != SOURCE_RAW_SHA256:
        raise ValueError("100m source raw identity mismatch")
    with np.load(path, allow_pickle=False) as data:
        values = data["values"]
        columns = {str(name): index for index, name in enumerate(data["columns"])}
    starts = values[:, columns["interval_start_time_s"]]
    selected = np.where((starts >= start_s - 1e-12) & (starts < start_s + duration_s - 1e-12))[0]
    expected = int(round(duration_s / DT))
    if len(selected) != expected or not np.allclose(starts[selected], start_s + DT * np.arange(expected), rtol=0.0, atol=1e-12):
        raise ValueError("source command window is incomplete or shifted")
    if start_s == 0.0:
        state = initialize_state(params("P0"), 1.0)
        steering = np.zeros(4)
    else:
        previous = np.where(np.isclose(values[:, columns["time_s"]], start_s, rtol=0.0, atol=1e-12))[0]
        if len(previous) != 1:
            raise ValueError("unique source initial endpoint not found")
        row = values[int(previous[0])]
        state = row[[columns[f"x{i}"] for i in range(30)]].copy()
        steering = row[[columns[f"actual_delta{i}"] for i in range(4)]].copy()
    commands = np.empty((expected, 8))
    commands[:, 0::2] = values[selected][:, [columns[f"accel{i}"] for i in range(4)]]
    commands[:, 1::2] = values[selected][:, [columns[f"request_delta{i}"] for i in range(4)]]
    source_end = values[selected][:, [columns[f"x{i}"] for i in range(30)] + [columns[f"actual_delta{i}"] for i in range(4)]]
    digest = hashlib.sha256(np.ascontiguousarray(commands).tobytes()).hexdigest().upper()
    return state, steering, commands, source_end, digest


def run(out, source_raw, window, actuator_update_s):
    if window not in WINDOWS or actuator_update_s not in UPDATE_INTERVALS:
        raise ValueError("unregistered window or actuator update interval")
    if abs(round(DT / actuator_update_s) * actuator_update_s - DT) > 1e-15:
        raise ValueError("actuator update interval must divide 20 ms")
    start_s, duration_s = WINDOWS[window]
    # The source identity and window completeness are validated BEFORE the output directory is
    # created.  The first version created the directory first, so a rejected source still left an
    # empty run directory behind, which the task book forbids ("rejection must happen before any
    # formal run output is created").
    state, steering, commands, source_end, command_digest = _source_data(Path(source_raw), start_s, duration_s)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    model = params("P0")
    update_rows, control_rows, subrows = [], [], []
    point_peak = np.zeros(4)
    impulse = np.zeros((4, 2))
    max_tire = 0.0
    min_support = float("inf")
    status, reason = "RUNNING", None
    relative_time = 0.0
    updates_per_control = int(round(DT / actuator_update_s))
    for tick, command_flat in enumerate(commands):
        command = command_flat.reshape(4, 2)
        for _ in range(updates_per_control):
            previous_steering = steering.copy()
            free = command[:, 1] + np.exp(-actuator_update_s / TAU) * (steering - command[:, 1])
            steering = np.clip(steering + np.clip(free - steering, -RATE * actuator_update_s, RATE * actuator_update_s), -LIMIT, LIMIT)
            state, audit = advance_outer_step(state, np.c_[command[:, 0], steering], "R3", model, actuator_update_s, "ES", EventSubstepConfig(), max_step_s=0.0005, load_transfer_enabled=True)
            boundary = consume_audit(audit, start_s + relative_time, state, previous_steering, steering)
            local = 0.0
            for segment in boundary["segments"]:
                dt = float(segment["dt_s"])
                local += dt
                force = np.asarray(segment["force_peak_n"])
                force_impulse = np.asarray(segment["force_interval_impulse_world_ns"])
                tire = np.asarray(segment["tire_raw_utilization"])
                support = np.asarray(segment["payload_support_load_n"])
                subrows.append(np.r_[relative_time + local, dt, force, force_impulse.ravel(), tire, support])
                point_peak = np.maximum(point_peak, force)
                impulse += force_impulse
                max_tire = max(max_tire, float(np.max(tire)))
                min_support = min(min_support, float(np.min(support)))
            relative_time += boundary["accepted_duration_s"]
            diagnostics = connector_diagnostics(state, model, "R3")
            _, system = system_derivative(state, np.c_[command[:, 0], steering], model, "R3", load_transfer_enabled=True)
            tire = np.asarray([item["raw_utilization"] for item in system["tire"]])
            support = np.asarray(system["payload_support_load_n"])
            point_force = np.asarray(diagnostics["force_norm_n"])
            point_peak = np.maximum(point_peak, point_force)
            max_tire = max(max_tire, float(np.max(tire)))
            min_support = min(min_support, float(np.min(support)))
            update_rows.append(np.r_[relative_time, state, steering, point_force, tire, support])
            if audit["status"] != "PASS":
                status, reason = "FAILED", audit["status"]
                break
        control_rows.append(np.r_[tick, relative_time, state, steering, source_end[tick], command_flat])
        if status == "FAILED":
            break
    if status == "RUNNING":
        status = "COMPLETED" if len(control_rows) == len(commands) else "PAUSED"
    update_columns = ["time_s", *[f"x{i}" for i in range(30)], *[f"actual_delta{i}" for i in range(4)], *[f"point_force{i}" for i in range(4)], *[f"tire_utilization{i}" for i in range(4)], *[f"support_load{i}" for i in range(4)]]
    control_columns = ["tick", "time_s", *[f"x{i}" for i in range(30)], *[f"actual_delta{i}" for i in range(4)], *[f"source_x{i}" for i in range(30)], *[f"source_actual_delta{i}" for i in range(4)], *[f"command{i}" for i in range(8)]]
    subcolumns = ["time_s", "dt_s", *[f"force_peak{i}" for i in range(4)], *[f"force_impulse{i}_{axis}" for i in range(4) for axis in ("x", "y")], *[f"tire_utilization{i}" for i in range(4)], *[f"support_load{i}" for i in range(4)]]
    np.savez_compressed(out / "updates.npz", values=np.asarray(update_rows, float), columns=np.asarray(update_columns))
    np.savez_compressed(out / "control_end.npz", values=np.asarray(control_rows, float), columns=np.asarray(control_columns))
    np.savez_compressed(out / "substeps.npz", values=np.asarray(subrows, float), columns=np.asarray(subcolumns))
    replay_difference = float(np.max(np.abs(np.asarray(control_rows)[:, 2:36] - source_end[: len(control_rows)]))) if control_rows else float("inf")
    metrics = {
        "status": status,
        "reason": reason,
        "window": window,
        "source_start_s": start_s,
        "requested_duration_s": duration_s,
        "accepted_duration_s": relative_time,
        "actuator_update_s": actuator_update_s,
        "plant_max_step_s": 0.0005,
        "control_step_s": DT,
        "control_ticks": len(control_rows),
        "actuator_updates": len(update_rows),
        "source_raw_path": str(Path(source_raw)),
        "source_raw_sha256": SOURCE_RAW_SHA256,
        "command_content_sha256": command_digest,
        "point_force_peak4_n": point_peak.tolist(),
        "force_impulse4x2_ns": impulse.tolist(),
        "maximum_tire_utilization": max_tire,
        "minimum_support_load_n": min_support,
        "source_replay_max_abs_difference": replay_difference if actuator_update_s == 0.002 else None,
        "trajectory_completed": status == "COMPLETED" and abs(relative_time - duration_s) <= 1e-12,
        "source_sha256": sha(__file__),
    }
    save(out, "metrics.json", metrics)
    save(out, "status.json", metrics)
    if status != "COMPLETED":
        raise SystemExit(20)
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--source-raw", required=True)
    parser.add_argument("--window", choices=WINDOWS, required=True)
    parser.add_argument("--actuator-update-ms", choices=[2.0, 1.0, 0.5], type=float, required=True)
    args = parser.parse_args()
    run(args.out, args.source_raw, args.window, args.actuator_update_ms / 1000.0)


if __name__ == "__main__":
    main()
