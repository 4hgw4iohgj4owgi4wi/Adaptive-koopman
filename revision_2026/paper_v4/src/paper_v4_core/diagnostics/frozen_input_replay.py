"""EXP-R3 R3A frozen-input replay: isolate plant propagation from MPC feedback."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from ..e01_100m import LIMIT, RATE, TAU, params
from ..failure_boundary import consume_audit
from ..plant.event_substep import EventSubstepConfig, advance_outer_step


PROTOCOL_SHA256 = "eb5d176e444dd5008c9d527fa0c44cef134c9a2d285833ce5c4e5ba7cb8e0b87"
CONTROL_DT = 0.02
ACTUATOR_DT = 0.002
TIME_ATOL = 1e-10


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def save_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def _columns(npz) -> tuple[np.ndarray, dict[str, int]]:
    names = np.asarray(npz["columns"]).astype(str)
    if len(names) != len(set(names.tolist())):
        raise ValueError("DUPLICATE_SOURCE_COLUMN")
    return names, {name: index for index, name in enumerate(names)}


def extract_window(source: Path, start_s: float, end_s: float) -> dict:
    if not (np.isfinite(start_s) and np.isfinite(end_s) and end_s > start_s):
        raise ValueError("INVALID_WINDOW")
    ticks = (end_s - start_s) / CONTROL_DT
    count = int(round(ticks))
    if count <= 0 or abs(ticks - count) > 1e-9:
        raise ValueError("WINDOW_NOT_ON_CONTROL_GRID")
    with np.load(source, allow_pickle=False) as archive:
        values = np.asarray(archive["values"], dtype=float)
        names, c = _columns(archive)
    required = (
        ["time_s"]
        + [f"x{i}" for i in range(30)]
        + [f"request_accel{i}" for i in range(4)]
        + [f"request_delta{i}" for i in range(4)]
        + [f"actual_delta{i}" for i in range(4)]
    )
    missing = [name for name in required if name not in c]
    if missing:
        raise ValueError("MISSING_SOURCE_COLUMNS:" + ",".join(missing))
    if not np.all(np.isfinite(values[:, [c[name] for name in required]])):
        raise ValueError("NONFINITE_SOURCE_VALUE")
    times = values[:, c["time_s"]]

    def unique_row(target: float) -> int:
        found = np.flatnonzero(np.isclose(times, target, rtol=0.0, atol=TIME_ATOL))
        if len(found) != 1:
            raise ValueError(f"SOURCE_TIME_ROW_COUNT:{target}:{len(found)}")
        return int(found[0])

    start_row = unique_row(start_s)
    end_times = start_s + CONTROL_DT * np.arange(1, count + 1)
    end_rows = np.asarray([unique_row(float(t)) for t in end_times], dtype=int)
    if not np.all(np.diff(end_rows) == 1):
        raise ValueError("NONCONTIGUOUS_SOURCE_ROWS")
    state_cols = [c[f"x{i}"] for i in range(30)]
    accel_cols = [c[f"request_accel{i}"] for i in range(4)]
    delta_cols = [c[f"request_delta{i}"] for i in range(4)]
    actual_cols = [c[f"actual_delta{i}"] for i in range(4)]
    commands = np.empty((count, 4, 2), dtype=float)
    commands[:, :, 0] = values[end_rows][:, accel_cols]
    commands[:, :, 1] = values[end_rows][:, delta_cols]
    return {
        "source_columns": names,
        "source_values": values,
        "start_row": start_row,
        "end_rows": end_rows,
        "end_times": end_times,
        "initial_state": values[start_row, state_cols].copy(),
        "initial_actual_delta": values[start_row, actual_cols].copy(),
        "commands": commands,
        "source_states": values[end_rows][:, state_cols].copy(),
        "source_actual_delta": values[end_rows][:, actual_cols].copy(),
    }


def run(
    source: Path,
    start_s: float,
    end_s: float,
    max_step_s: float,
    out: Path,
    protocol: Path,
) -> dict:
    source = source.resolve()
    protocol = protocol.resolve()
    out = out.resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    if sha256(protocol).lower() != PROTOCOL_SHA256:
        raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    if max_step_s not in (0.001, 0.0005):
        raise ValueError("R3A_MAX_STEP_NOT_ALLOWED")
    source_metrics_path = source.parent / "metrics.json"
    source_metrics = json.loads(source_metrics_path.read_text(encoding="utf-8-sig"))
    if source_metrics.get("parameter_id") != "P0":
        raise ValueError("SOURCE_PARAMETER_NOT_P0")
    if float(source_metrics.get("lambda_internal")) != 2.0:
        raise ValueError("SOURCE_LAMBDA_NOT_2")
    if abs(float(source_metrics.get("maximum_plant_step_s")) - 0.0005) > 1e-15:
        raise ValueError("SOURCE_IS_NOT_REGISTERED_FINE_RUN")

    window = extract_window(source, start_s, end_s)
    state = window["initial_state"].copy()
    actual_delta = window["initial_actual_delta"].copy()
    initial_state_bytes = state.tobytes()
    initial_delta_bytes = actual_delta.tobytes()
    commands = window["commands"]
    command_bytes = commands.tobytes()
    model = params("P0")
    config = EventSubstepConfig()
    rows: list[np.ndarray] = []
    subrows: list[np.ndarray] = []
    events: list[dict] = []
    status = "RUNNING"
    reason = None
    begun = time.perf_counter()

    raw_columns = (
        ["time_s"]
        + [f"x{i}" for i in range(30)]
        + [f"actual_delta{i}" for i in range(4)]
        + [f"request_accel{i}" for i in range(4)]
        + [f"request_delta{i}" for i in range(4)]
        + [f"source_x{i}" for i in range(30)]
        + [f"source_actual_delta{i}" for i in range(4)]
    )
    subcolumns = (
        ["time_s", "dt_s"]
        + [f"force_peak{i}" for i in range(4)]
        + [f"force_impulse_x{i}" for i in range(4)]
        + [f"force_impulse_y{i}" for i in range(4)]
        + [f"tire_utilization{i}" for i in range(4)]
        + [f"support_load{i}" for i in range(4)]
    )

    for tick, (end_time, command) in enumerate(zip(window["end_times"], commands)):
        accepted = 0.0
        for actuator_subtick in range(10):
            before = actual_delta.copy()
            free = command[:, 1] + np.exp(-ACTUATOR_DT / TAU) * (
                actual_delta - command[:, 1]
            )
            actual_delta = np.clip(
                actual_delta
                + np.clip(free - actual_delta, -RATE * ACTUATOR_DT, RATE * ACTUATOR_DT),
                -LIMIT,
                LIMIT,
            )
            state, audit = advance_outer_step(
                state,
                np.c_[command[:, 0], actual_delta],
                "R3",
                model,
                ACTUATOR_DT,
                "ES",
                config,
                max_step_s=max_step_s,
                load_transfer_enabled=True,
            )
            boundary = consume_audit(
                audit,
                float(end_time - CONTROL_DT + accepted),
                state,
                before,
                actual_delta,
            )
            local = 0.0
            for segment in boundary["segments"]:
                local += float(segment["dt_s"])
                subrows.append(
                    np.r_[
                        end_time - CONTROL_DT + accepted + local,
                        segment["dt_s"],
                        segment["force_peak_n"],
                        np.asarray(segment["force_interval_impulse_world_ns"])[:, 0],
                        np.asarray(segment["force_interval_impulse_world_ns"])[:, 1],
                        segment["tire_raw_utilization"],
                        segment["payload_support_load_n"],
                    ]
                )
            for event in audit.get("events", []):
                events.append(
                    {
                        "control_tick": tick,
                        "actuator_subtick": actuator_subtick,
                        **event,
                    }
                )
            accepted += float(boundary["accepted_duration_s"])
            if audit["status"] != "PASS":
                status = "FAILED"
                reason = str(audit["status"])
                break
        rows.append(
            np.r_[
                end_time - CONTROL_DT + accepted,
                state,
                actual_delta,
                command[:, 0],
                command[:, 1],
                window["source_states"][tick],
                window["source_actual_delta"][tick],
            ]
        )
        if status == "FAILED":
            break
    if status == "RUNNING":
        status = "COMPLETED"

    out.mkdir(parents=True, exist_ok=False)
    raw_values = np.asarray(rows, dtype=float)
    sub_values = (
        np.asarray(subrows, dtype=float)
        if subrows
        else np.empty((0, len(subcolumns)), dtype=float)
    )
    np.savez_compressed(out / "raw.npz", values=raw_values, columns=np.asarray(raw_columns))
    np.savez_compressed(
        out / "substeps.npz", values=sub_values, columns=np.asarray(subcolumns)
    )
    save_json(out / "events.json", {"events": events})
    complete_ticks = len(rows)
    state_error = raw_values[:, 1:31] - window["source_states"][:complete_ticks]
    delta_error = raw_values[:, 31:35] - window["source_actual_delta"][:complete_ticks]
    metrics = {
        "status": status,
        "reason": reason,
        "role": "DEV_NUMERICAL_DIAGNOSTIC",
        "scope": "Frozen requested input; no MPC solve",
        "source_raw": str(source),
        "source_raw_sha256": sha256(source),
        "source_metrics_sha256": sha256(source_metrics_path),
        "protocol": str(protocol),
        "protocol_sha256": sha256(protocol),
        "start_s": start_s,
        "end_s": end_s,
        "requested_control_ticks": len(commands),
        "completed_control_ticks": complete_ticks,
        "maximum_plant_step_s": max_step_s,
        "actuator_update_s": ACTUATOR_DT,
        "control_step_s": CONTROL_DT,
        "initial_state_sha256": hashlib.sha256(initial_state_bytes).hexdigest().upper(),
        "initial_actual_delta_sha256": hashlib.sha256(initial_delta_bytes).hexdigest().upper(),
        "requested_command_sha256": hashlib.sha256(command_bytes).hexdigest().upper(),
        "source_start_row": int(window["start_row"]),
        "source_end_rows": [int(x) for x in window["end_rows"]],
        "source_self_reproduction_max_state_abs": float(np.max(np.abs(state_error))),
        "source_self_reproduction_max_actual_delta_abs_rad": float(
            np.max(np.abs(delta_error))
        ),
        "wall_s": time.perf_counter() - begun,
    }
    save_json(out / "metrics.json", metrics)
    print(json.dumps(metrics, ensure_ascii=False, allow_nan=False))
    if status != "COMPLETED":
        raise SystemExit(20)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--start-s", type=float, required=True)
    parser.add_argument("--end-s", type=float, required=True)
    parser.add_argument("--max-step-ms", type=float, choices=(1.0, 0.5), required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--protocol", required=True)
    args = parser.parse_args()
    run(
        Path(args.source),
        args.start_s,
        args.end_s,
        args.max_step_ms / 1000.0,
        Path(args.out),
        Path(args.protocol),
    )


if __name__ == "__main__":
    main()
