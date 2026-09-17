"""Bounded closed-loop window runner with a selectable CPU or CUDA linearisation backend.

Purpose (G3): resume the frozen closed loop from a checkpoint rebuilt out of saved
artifacts, over a short pre-registered window, and do so twice - once on the CPU
parallel backend and once on the RTX 5080 backend - so that two questions are
answered separately:

  * does the rebuilt checkpoint reproduce the original trajectory (CPU replay vs
    the persisted rows)?
  * does the CUDA backend drive the same closed loop with bounded divergence?

The control law, plant, horizon, weights, differential step, hard gates and
logging semantics follow ``post_r3_r4_runner.py`` exactly; that frozen module is
not modified.  This runner only adds (a) checkpoint resumption, (b) a backend
switch, and (c) the memory columns the frozen runner never persisted
(``tick_index``, ``reference_beta*``, ``previous_u*``, interval start distance).
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

import numpy as np

from ..cli import save, sha
from ..controllers import physical_tracking_pilot as controller
from ..controllers.parallel_fd_backend import ParallelFiniteDifferenceBackend, install_parallel_linearization
from ..controllers.physical_tracking_pilot import PilotConfig
from ..e01_100m import DT, params
from ..failure_boundary import consume_audit
from ..pilot_runner import ROUTE_LENGTH, SPEED, make_preview
from ..plant.event_substep import EventSubstepConfig, advance_outer_step
from ..plant.four_vehicle_common import connector_diagnostics, system_derivative
from .reference_memory import recover_interval_duration, replay_reference_chain, verify_replay

SCHEMA = "G3-CLOSED-LOOP-WINDOW-v1"
SCOPE = "G3_BOUNDED_CLOSED_LOOP_WINDOW"

MEMORY_COLUMNS = (
    ["tick_index", "interval_reference_distance_start_m"]
    + [f"reference_beta{i}" for i in range(4)]
    + [f"previous_u{i}" for i in range(8)]
)


def expanded_parameters(model) -> dict:
    value = asdict(model)
    value["vehicle_anchor_body_m"] = [list(item) for item in model.vehicle_anchor_body_m]
    value["payload"]["yaw_inertia_kgm2"] = model.payload.yaw_inertia_kgm2
    value["payload_anchor_body_m"] = model.payload_anchor_body_m.tolist()
    return value


def load_archive(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), [str(value) for value in data["columns"]]


def checkpoint(out: Path, rows, columns, subrows, subcolumns, status: dict) -> None:
    np.savez_compressed(out / "raw.npz", values=np.asarray(rows, float), columns=np.asarray(columns))
    sub = np.asarray(subrows, float) if subrows else np.empty((0, len(subcolumns)))
    np.savez_compressed(out / "substeps.npz", values=sub, columns=np.asarray(subcolumns))
    save(out, "status.json", status)


def assert_previous_control_layout(run: Path, raw, index: dict, start_tick: int) -> dict:
    """Guard the grouped-versus-interleaved trap that has now caused three defects.

    ``raw.npz`` stores the solved first control grouped as
    ``[a1..a4, delta1..delta4]``, while ``solver.jsonl`` stores the same vector
    interleaved as ``[a1, delta1, a2, delta2, ...]`` and so does the controller's
    decision vector.  Feeding the grouped order back in as ``previous_u`` changes the
    rate cost and the first control by order 1e-1, which silently invalidates a
    checkpoint.  This check fails loudly if the two layouts stop corresponding.
    """
    solver_path = run / "solver.jsonl"
    if not solver_path.is_file():
        return {"checked": False, "reason": "solver.jsonl_missing"}
    target = start_tick - 1
    line = None
    for candidate in solver_path.read_text(encoding="utf-8").splitlines():
        if candidate.strip() and int(json.loads(candidate)["tick"]) == target:
            line = candidate
            break
    if line is None:
        return {"checked": False, "reason": f"tick_{target}_not_found"}
    control = np.asarray(json.loads(line)["first_control"], float)
    grouped_in_raw = np.r_[
        raw[target][[index[f"request_accel{i}"] for i in range(4)]],
        raw[target][[index[f"request_delta{i}"] for i in range(4)]],
    ].astype(float)
    de_interleaved = np.r_[control[0::2], control[1::2]]
    if not np.array_equal(grouped_in_raw, de_interleaved):
        raise ValueError("PREVIOUS_CONTROL_LAYOUT_MISMATCH")
    return {"checked": True, "tick": target, "bitwise_identical": True, "layout": "solver.jsonl interleaved, raw grouped"}


def rebuild_checkpoint(paper: Path, source_run: str, parameter: str, start_tick: int) -> dict:
    """Rebuild the full state and memory needed to resume at loop index start_tick.

    The frozen runner stores, in row k, the state at the END of interval k, which is
    the state used at the START of loop index k+1.  So resuming at index K takes its
    state, steering, previous control and reference distance from row K-1, and its
    beta from the replayed reference chain.
    """
    run = paper / source_run
    raw, columns = load_archive(run / "raw.npz")
    index = {name: position for position, name in enumerate(columns)}
    if start_tick < 1 or start_tick >= raw.shape[0]:
        raise ValueError("START_TICK_OUT_OF_RANGE")
    model = params(parameter)
    closure = verify_replay(model, raw[:, index["time_s"]], raw[:, index["reference_distance_m"]])
    if closure["distance_max_relative_error"] > 1e-12:
        raise ValueError("REFERENCE_REPLAY_DOES_NOT_CLOSE")
    layout = assert_previous_control_layout(run, raw, index, start_tick)
    source = raw[start_tick - 1]
    state = source[[index[f"x{i}"] for i in range(30)]].astype(float)
    delta = source[[index[f"actual_delta{i}"] for i in range(4)]].astype(float)
    previous_u = np.empty(8, dtype=float)
    previous_u[0::2] = source[[index[f"request_accel{i}"] for i in range(4)]]
    previous_u[1::2] = source[[index[f"request_delta{i}"] for i in range(4)]]
    return {
        "state": state,
        "delta": delta,
        "previous_u": previous_u,
        "distance": float(source[index["reference_distance_m"]]),
        "beta": np.asarray(closure["betas"][start_tick - 1], dtype=float),
        "source_row": int(start_tick - 1),
        "replay_closure": {key: value for key, value in closure.items() if key not in ("distances", "betas")},
        "previous_control_layout": layout,
        "source_time_s": float(source[index["time_s"]]),
    }


def validate_protocol(path: Path, expected_sha: str, paper: Path, window_name: str, backend: str) -> dict:
    if sha(path) != expected_sha.lower():
        raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("schema_version") != SCHEMA:
        raise ValueError("PROTOCOL_SCHEMA_MISMATCH")
    if protocol.get("scope") != SCOPE:
        raise ValueError("PROTOCOL_SCOPE_MISMATCH")
    for item in protocol["identity_files"]:
        source = paper / item["path"]
        if not source.is_file() or sha(source) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    if backend not in ("cpu", "gpu"):
        raise ValueError("UNREGISTERED_BACKEND")
    matches = [run for run in protocol["runs"] if run["window"] == window_name and run["backend"] == backend]
    if len(matches) != 1:
        raise ValueError("UNREGISTERED_RUN_CELL")
    run = matches[0]
    window = next(item for item in protocol["windows"] if item["name"] == window_name)
    model = params(protocol["parameter_id"])
    if expanded_parameters(model) != protocol["absolute_parameters"]:
        raise ValueError("ABSOLUTE_PARAMETER_IDENTITY_MISMATCH")
    return {"protocol": protocol, "run": run, "window": window}


def execute(out: Path, model, parameter: str, backend_kind: str, window: dict, checkpoint_state: dict, max_step_s: float, deadline: float, protocol_sha: str) -> None:
    # ``model`` is the caller's instance, i.e. the very object the linearisation
    # backend was constructed with.  Re-deriving it here with params(parameter)
    # would produce a *different* object and trip the backend's model-identity
    # guard, which controller.solve() would swallow into a MODEL_DOMAIN_ERROR with
    # infinite residuals instead of a diagnosable failure.
    first_tick = int(window["start_tick"])
    count = int(window["ticks"])
    state = np.asarray(checkpoint_state["state"], float).copy()
    delta = np.asarray(checkpoint_state["delta"], float).copy()
    previous_u = np.asarray(checkpoint_state["previous_u"], float).copy()
    distance = float(checkpoint_state["distance"])
    beta = np.asarray(checkpoint_state["beta"], float).copy()

    actual_path = 0.0
    last_payload = state[24:26].copy()
    rows, subrows = [], []
    max_force = max_internal = max_tire = max_eg = 0.0
    min_support = float("inf")
    status, reason = "RUNNING", None
    started = time.perf_counter()
    columns = (
        ["time_s", "reference_distance_m", "actual_payload_path_m", "lambda_internal"]
        + [f"x{i}" for i in range(30)]
        + [f"request_accel{i}" for i in range(4)]
        + [f"request_delta{i}" for i in range(4)]
        + [f"actual_delta{i}" for i in range(4)]
        + [f"point_force_norm{i}" for i in range(4)]
        + [f"point_force_body_x{i}" for i in range(4)]
        + [f"point_force_body_y{i}" for i in range(4)]
        + [f"tire_utilization{i}" for i in range(4)]
        + [f"support_load{i}" for i in range(4)]
        + ["internal_force_norm_n", "tension_x_n", "tension_y_n", "max_e_g_m", "solver_wall_s"]
        + MEMORY_COLUMNS
    )
    subcolumns = (
        ["time_s", "dt_s"]
        + [f"force_peak{i}" for i in range(4)]
        + [f"force_body_x{i}" for i in range(4)]
        + [f"force_body_y{i}" for i in range(4)]
        + [f"force_impulse_x{i}" for i in range(4)]
        + [f"force_impulse_y{i}" for i in range(4)]
        + [f"tire_utilization{i}" for i in range(4)]
        + [f"support_load{i}" for i in range(4)]
    )
    with (out / "solver.jsonl").open("w", encoding="utf-8") as handle:
        for k in range(first_tick, first_tick + count):
            if time.time() > deadline:
                status, reason = "TIMEOUT_INCOMPLETE", "WINDOW_DEADLINE"
                break
            t = k * DT
            distance_before = distance
            u_nom, refs, _ = make_preview(distance, beta, model, previous_u, 20)
            config = PilotConfig(horizon=20, lambda_internal=2.0, frozen_dynamics_jacobian=False, finite_difference_scale=1.0)
            result = controller.solve(np.r_[state, delta], u_nom, refs, model, config)
            record = {key: result[key] for key in ("status", "solver_status", "iterations", "primal_residual", "dual_residual", "objective", "wall_s")}
            record.update({"tick": k, "time_s": t, "validation": result["validation"], "first_control": result["control"][0].tolist(), "last_control": result["control"][-1].tolist(), "problem_hashes": None})
            try:
                handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                handle.flush()
            except ValueError:
                # A non-finite solver record must stop the window loudly instead of
                # writing JSON that no reader can parse; the reason is preserved.
                non_finite = [key for key in ("primal_residual", "dual_residual", "objective") if not np.isfinite(float(record[key]))]
                save(out, "solver_failure.json", {
                    "tick": k, "time_s": t, "solver_status": record["solver_status"],
                    "non_finite_fields": non_finite,
                    "validation": {key: value for key, value in record["validation"].items() if key != "terminal_state"},
                    "reason": "NON_FINITE_SOLVER_RECORD",
                })
                status, reason = "FAILED", "NON_FINITE_SOLVER_RECORD:" + str(record["solver_status"])
                break
            if result["status"] != "PASS":
                status, reason = "FAILED", "MPC_" + str(result["solver_status"]) + ":" + str(result["validation"].get("reason", ""))
                break
            command = np.asarray(result["control"][0]).reshape(4, 2)
            previous_u = result["control"][0].copy()
            interval_duration = 0.0
            for _ in range(10):
                delta_before = delta.copy()
                free = command[:, 1] + np.exp(-0.002 / 0.12) * (delta - command[:, 1])
                delta = np.clip(delta + np.clip(free - delta, -1.2 * 0.002, 1.2 * 0.002), -np.deg2rad(15.0), np.deg2rad(15.0))
                try:
                    state, audit = advance_outer_step(state, np.c_[command[:, 0], delta], "R3", model, 0.002, "ES", EventSubstepConfig(), max_step_s=max_step_s, load_transfer_enabled=True)
                except Exception as error:  # noqa: BLE001 - mirrored from the frozen runner
                    status, reason = "FAILED", f"PLANT_{type(error).__name__}"
                    break
                boundary = consume_audit(audit, t + interval_duration, state, delta_before, delta)
                local = 0.0
                for segment in boundary["segments"]:
                    local += float(segment["dt_s"])
                    peak = np.asarray(segment["force_peak_n"])
                    body = np.asarray(segment["force_payload_body_n"])
                    impulse = np.asarray(segment["force_interval_impulse_world_ns"])
                    tire = np.asarray(segment["tire_raw_utilization"])
                    support = np.asarray(segment["payload_support_load_n"])
                    subrows.append(np.r_[t + interval_duration + local, segment["dt_s"], peak, body[:, 0], body[:, 1], impulse[:, 0], impulse[:, 1], tire, support])
                    max_force = max(max_force, float(np.max(peak)))
                    max_tire = max(max_tire, float(np.max(tire)))
                    min_support = min(min_support, float(np.min(support)))
                interval_duration += boundary["accepted_duration_s"]
                if audit["status"] != "PASS":
                    status, reason = "FAILED", audit["status"]
                    break
            if status != "RUNNING":
                break
            distance = min(distance + SPEED * interval_duration, ROUTE_LENGTH)
            beta += (interval_duration / DT) * (np.asarray(refs[0]["beta_star"]) - beta)
            diag = connector_diagnostics(state, model, "R3")
            _, system = system_derivative(state, np.c_[command[:, 0], delta], model, "R3", load_transfer_enabled=True)
            force = np.asarray(diag["force_norm_n"])
            body = np.asarray(diag["force_payload_body_n"])
            tire = np.asarray([item["raw_utilization"] for item in system["tire"]])
            support = np.asarray(system["payload_support_load_n"])
            payload = state[24:26]
            actual_path += float(np.linalg.norm(payload - last_payload))
            last_payload = payload.copy()
            max_force = max(max_force, float(np.max(force)))
            max_internal = max(max_internal, float(diag["internal_force_norm_n"]))
            max_tire, min_support = max(max_tire, float(np.max(tire))), min(min_support, float(np.min(support)))
            rows.append(np.r_[
                t + interval_duration, distance, actual_path, 2.0, state,
                command[:, 0], command[:, 1], delta, force, body[:, 0], body[:, 1], tire, support,
                diag["internal_force_norm_n"], diag["tension_x_n"], diag["tension_y_n"], 0.0, result["wall_s"],
                float(k), float(distance_before), beta.copy(), previous_u.copy(),
            ])
            if max_force > 15000.0 + 1e-6:
                status, reason = "FAILED", "STOP_ULTIMATE_FORCE_ENDPOINT"
            elif max_tire > 1.0 + 1e-9:
                status, reason = "FAILED", "TIRE_CAPABILITY_VIOLATION"
            elif min_support < 0.0:
                status, reason = "FAILED", "SUPPORT_LIFT"
            if status != "RUNNING":
                break
            if len(rows) % 10 == 0:
                checkpoint(out, rows, columns, subrows, subcolumns, {
                    "status": "RUNNING", "completed_ticks": len(rows), "total_ticks": count,
                    "tick_index": k, "time_s": t + interval_duration, "reference_distance_m": distance,
                    "updated_unix": time.time(), "deadline_unix": deadline,
                })
                print(json.dumps({"window": window["name"], "completed": len(rows), "total": count, "last_solver_s": result["wall_s"]}), flush=True)
        if status == "RUNNING":
            status = "COMPLETED" if len(rows) == count else "PAUSED"
    metrics = {
        "status": status, "reason": reason, "role": "G3_BOUNDED_CLOSED_LOOP_WINDOW",
        "identity": "Windowed closed-loop equivalence diagnostic on a rebuilt checkpoint",
        "candidate_id": "EXP-R3-unfrozen-v1", "implementation_id": f"G3-window-{backend_kind}-v1",
        "parameter_id": parameter, "parameter_values": expanded_parameters(model),
        "window_name": window["name"], "backend": backend_kind, "start_tick": first_tick, "ticks": count,
        "source_run": window["source_run"], "checkpoint_source_row": checkpoint_state["source_row"],
        "checkpoint_source_time_s": checkpoint_state["source_time_s"],
        "replay_closure": checkpoint_state["replay_closure"],
        "lambda_internal": 2.0, "horizon": 20, "controller_step_s": DT, "plant_step_s": 0.002,
        "maximum_plant_step_s": max_step_s, "iterations": len(rows), "expected_iterations": count,
        "duration_s": float(rows[-1][0]) if rows else 0.0, "reference_distance_m": distance,
        "route_length_m": ROUTE_LENGTH, "actual_payload_path_m": actual_path,
        "maximum_point_force_n": max_force, "maximum_internal_force_norm_n": max_internal,
        "maximum_tire_utilization": max_tire, "minimum_support_load_n": min_support,
        "maximum_configuration_error_m": max_eg, "frozen_dynamics_jacobian": False,
        "finite_difference_scale": 1.0, "wall_s": time.perf_counter() - started,
        "deadline_unix": deadline, "protocol_sha256": protocol_sha, "source_sha256": sha(__file__),
    }
    checkpoint(out, rows, columns, subrows, subcolumns, metrics)
    save(out, "metrics.json", metrics)
    print(json.dumps(metrics, ensure_ascii=False), flush=True)
    if status != "COMPLETED":
        raise SystemExit(20)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--window", required=True)
    parser.add_argument("--backend", choices=("cpu", "gpu"), required=True)
    parser.add_argument("--deadline-unix", type=float, required=True)
    args = parser.parse_args()
    paper = Path(__file__).resolve().parents[3]
    protocol_path = Path(args.protocol).resolve()
    resolved = validate_protocol(protocol_path, args.protocol_sha, paper, args.window, args.backend)
    protocol, run, window = resolved["protocol"], resolved["run"], resolved["window"]
    out = Path(run["output"]).resolve() if Path(run["output"]).is_absolute() else (paper / run["output"]).resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")

    parameter = protocol["parameter_id"]
    model = params(parameter)
    # Pre-flight before creating any output: the rebuilt checkpoint must close
    # against the persisted reference distance, otherwise the window is not
    # resumable and no directory should be left behind.
    checkpoint_state = rebuild_checkpoint(paper, window["source_run"], parameter, int(window["start_tick"]))
    out.mkdir(parents=True)
    save(out, "checkpoint_source.json", {
        "window": window["name"], "backend": args.backend, "start_tick": int(window["start_tick"]),
        "ticks": int(window["ticks"]), "source_run": window["source_run"],
        "checkpoint_source_row": checkpoint_state["source_row"],
        "checkpoint_source_time_s": checkpoint_state["source_time_s"],
        "replay_closure": checkpoint_state["replay_closure"],
        "state": checkpoint_state["state"].tolist(), "delta": checkpoint_state["delta"].tolist(),
        "previous_u": checkpoint_state["previous_u"].tolist(), "distance": checkpoint_state["distance"],
        "beta": checkpoint_state["beta"].tolist(),
    })
    max_step_s = float(window["plant_max_step_ms"]) / 1000.0
    workers = int(run["workers"])
    if args.backend == "cpu":
        with ParallelFiniteDifferenceBackend(workers) as backend:
            warmup = backend.warm(np.r_[checkpoint_state["state"], checkpoint_state["delta"]], np.zeros(8), model)
            save(out, "pool.json", {"workers": workers, "warmup_s": warmup})
            with install_parallel_linearization(backend):
                execute(out, model, parameter, "cpu", window, checkpoint_state, max_step_s, args.deadline_unix, args.protocol_sha.lower())
    else:
        from ..gpu_port.ipc_backend import CudaIpcFiniteDifferenceBackend, install_cuda_linearization

        with CudaIpcFiniteDifferenceBackend(model) as backend:
            environment = backend.environment()
            warmup = backend.warm(np.r_[checkpoint_state["state"], checkpoint_state["delta"]], np.zeros(8))
            save(out, "pool.json", {
                "backend": "cuda", "device": environment.get("device_name"),
                "warmup_s": warmup, "worker_module_audit": environment.get("worker_module_audit"),
            })
            with install_cuda_linearization(backend):
                execute(out, model, parameter, "gpu", window, checkpoint_state, max_step_s, args.deadline_unix, args.protocol_sha.lower())


if __name__ == "__main__":
    main()
