"""EXP-R4-C full-route 8-process runner with a hard deadline and checkpoints."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np

from ..cli import save, sha
from ..controllers import physical_tracking_pilot as controller
from ..controllers.parallel_fd_backend import ParallelFiniteDifferenceBackend, install_parallel_linearization
from ..controllers.physical_tracking_pilot import PilotConfig
from ..diagnostics.qp_fd_trials import array_digest
from ..diagnostics.relative_motion import extract
from ..e01_100m import DT, LIMIT, RATE, TAU, params
from ..failure_boundary import consume_audit
from ..pilot_runner import ROUTE_LENGTH, SPEED, _path_sample, make_preview
from ..plant.event_substep import EventSubstepConfig, advance_outer_step
from ..plant.four_vehicle_common import connector_diagnostics, initialize_state, system_derivative
from ..reference_geometry import transition_targets


def checkpoint(out: Path, rows, columns, subrows, subcolumns, status: dict) -> None:
    np.savez_compressed(out / "raw.npz", values=np.asarray(rows, float), columns=np.asarray(columns))
    sub = np.asarray(subrows, float) if subrows else np.empty((0, len(subcolumns)))
    np.savez_compressed(out / "substeps.npz", values=sub, columns=np.asarray(subcolumns))
    save(out, "status.json", status)


def validate_protocol(protocol_path: Path, expected_sha: str, paper: Path, step_ms: float, deadline_unix: float) -> dict:
    if sha(protocol_path) != expected_sha.lower():
        raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("schema_version") != "EXP-R4C-full-route-v1":
        raise ValueError("PROTOCOL_SCHEMA_MISMATCH")
    if float(protocol["run"]["plant_max_step_ms"]) != step_ms:
        raise ValueError("PLANT_STEP_PROTOCOL_MISMATCH")
    if protocol["run"]["implementation"] != "parallel8":
        raise ValueError("IMPLEMENTATION_PROTOCOL_MISMATCH")
    if float(protocol["run"]["deadline_unix"]) != float(deadline_unix):
        raise ValueError("DEADLINE_PROTOCOL_MISMATCH")
    mismatches = []
    for item in protocol["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            mismatches.append(item["path"])
    if mismatches:
        raise ValueError("IDENTITY_MISMATCH:" + ",".join(mismatches))
    parent = paper / protocol["force_pair_parent"]["report"]
    report = json.loads(parent.read_text(encoding="utf-8"))
    if sha(parent) != protocol["force_pair_parent"]["sha256"] or report.get("status") != "PASS_FORCE_WINDOW_EQUIVALENCE":
        raise ValueError("FORCE_PAIR_PARENT_NOT_PASS")
    return protocol


def execute(out: Path, max_step_s: float, deadline_unix: float) -> None:
    model = params("P0")
    state = initialize_state(model, SPEED)
    delta = np.zeros(4)
    beta = np.zeros(4)
    previous_u = np.zeros(8)
    distance = 0.0
    rows, subrows = [], []
    actual_path = 0.0
    last_payload = state[24:26].copy()
    max_force = max_internal = max_tire = max_eg = 0.0
    min_support = float("inf")
    reason = None
    status = "RUNNING"
    started = time.perf_counter()
    count = int(np.ceil((ROUTE_LENGTH / SPEED) / DT))
    columns = ["time_s", "reference_distance_m", "actual_payload_path_m", "lambda_internal"] + [f"x{i}" for i in range(30)] + [f"request_accel{i}" for i in range(4)] + [f"request_delta{i}" for i in range(4)] + [f"actual_delta{i}" for i in range(4)] + [f"point_force_norm{i}" for i in range(4)] + [f"tire_utilization{i}" for i in range(4)] + [f"support_load{i}" for i in range(4)] + ["internal_force_norm_n", "tension_x_n", "tension_y_n", "max_e_g_m", "solver_wall_s"]
    subcolumns = ["time_s", "dt_s"] + [f"force_peak{i}" for i in range(4)] + [f"force_impulse_x{i}" for i in range(4)] + [f"force_impulse_y{i}" for i in range(4)] + [f"tire_utilization{i}" for i in range(4)] + [f"support_load{i}" for i in range(4)]
    solver_path = out / "solver.jsonl"
    handle = solver_path.open("w", encoding="utf-8")
    try:
        for k in range(count):
            if time.time() > deadline_unix:
                status, reason = "TIMEOUT_INCOMPLETE", "FULL_ROUTE_12H_DEADLINE"
                break
            t = k * DT
            u_nom, refs, _ = make_preview(distance, beta, model, previous_u, 20)
            config = PilotConfig(horizon=20, lambda_internal=2.0, frozen_dynamics_jacobian=False, finite_difference_scale=1.0)
            result = controller.solve(np.r_[state, delta], u_nom, refs, model, config)
            problem = result["problem"]
            hashes = {name: array_digest(np.asarray(problem[name])) for name in ("P", "q", "A", "l", "u", "u_nom")} if problem is not None else None
            record = {key: result[key] for key in ("status", "solver_status", "iterations", "primal_residual", "dual_residual", "objective", "wall_s")}
            record.update({"tick": k, "time_s": t, "validation": result["validation"], "first_control": result["control"][0].tolist(), "last_control": result["control"][-1].tolist(), "problem_hashes": hashes})
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            handle.flush()
            if result["status"] != "PASS":
                status, reason = "FAILED", "MPC_" + str(result["solver_status"])
                break
            command = np.asarray(result["control"][0]).reshape(4, 2)
            previous_u = result["control"][0].copy()
            interval_duration = 0.0
            for _ in range(10):
                delta_before = delta.copy()
                free = command[:, 1] + np.exp(-.002 / TAU) * (delta - command[:, 1])
                delta = np.clip(delta + np.clip(free - delta, -RATE * .002, RATE * .002), -LIMIT, LIMIT)
                try:
                    state, audit = advance_outer_step(state, np.c_[command[:, 0], delta], "R3", model, .002, "ES", EventSubstepConfig(), max_step_s=max_step_s, load_transfer_enabled=True)
                except Exception as error:
                    status, reason = "FAILED", f"PLANT_{type(error).__name__}"
                    break
                boundary = consume_audit(audit, t + interval_duration, state, delta_before, delta)
                local = 0.0
                for segment in boundary["segments"]:
                    local += float(segment["dt_s"])
                    force_peak = np.asarray(segment["force_peak_n"])
                    impulse = np.asarray(segment["force_interval_impulse_world_ns"])
                    utilization = np.asarray(segment["tire_raw_utilization"])
                    support = np.asarray(segment["payload_support_load_n"])
                    subrows.append(np.r_[t + interval_duration + local, segment["dt_s"], force_peak, impulse[:, 0], impulse[:, 1], utilization, support])
                    max_force = max(max_force, float(np.max(force_peak)))
                    max_tire = max(max_tire, float(np.max(utilization)))
                    min_support = min(min_support, float(np.min(support)))
                interval_duration += boundary["accepted_duration_s"]
                if audit["status"] != "PASS":
                    status, reason = "FAILED", audit["status"]
                    break
            distance = min(distance + SPEED * interval_duration, ROUTE_LENGTH)
            beta = beta + (interval_duration / DT) * (np.asarray(refs[0]["beta_star"]) - beta)
            diag = connector_diagnostics(state, model, "R3")
            _, system = system_derivative(state, np.c_[command[:, 0], delta], model, "R3", load_transfer_enabled=True)
            force = np.asarray(diag["force_norm_n"])
            tire = np.asarray([item["raw_utilization"] for item in system["tire"]])
            support = np.asarray(system["payload_support_load_n"])
            qstar = transition_targets(np.asarray([SPEED, 0.0]), SPEED * _path_sample(distance)[3], beta, model)["centers"]
            eg = float(np.max(np.linalg.norm(extract(state, model, qstar, beta)["e_g_m"], axis=1)))
            payload = state[24:26]
            actual_path += float(np.linalg.norm(payload - last_payload))
            last_payload = payload.copy()
            max_force = max(max_force, float(np.max(force)))
            max_internal = max(max_internal, float(diag["internal_force_norm_n"]))
            max_tire = max(max_tire, float(np.max(tire)))
            min_support = min(min_support, float(np.min(support)))
            max_eg = max(max_eg, eg)
            rows.append(np.r_[t + interval_duration, distance, actual_path, 2.0, state, command[:, 0], command[:, 1], delta, force, tire, support, diag["internal_force_norm_n"], diag["tension_x_n"], diag["tension_y_n"], eg, result["wall_s"]])
            if max_force > 15000.0 + 1e-6:
                status, reason = "FAILED", "STOP_ULTIMATE_FORCE_ENDPOINT"
            elif max_tire > 1.0 + 1e-9:
                status, reason = "FAILED", "TIRE_CAPABILITY_VIOLATION"
            elif min_support < 0.0:
                status, reason = "FAILED", "SUPPORT_LIFT"
            if status != "RUNNING":
                break
            if (k + 1) % 25 == 0:
                checkpoint(out, rows, columns, subrows, subcolumns, {"status": "RUNNING", "completed_ticks": k + 1, "total_ticks": count, "time_s": t + interval_duration, "reference_distance_m": distance, "updated_unix": time.time(), "deadline_unix": deadline_unix})
                print(json.dumps({"implementation": "parallel8", "completed": k + 1, "total": count, "last_solver_s": result["wall_s"]}), flush=True)
        if status == "RUNNING":
            status = "COMPLETED" if len(rows) == count else "PAUSED"
    finally:
        handle.close()
    metrics = {"status": status, "reason": reason, "role": "DEV", "identity": "Centralized Full-State Physical Model Predictive Control diagnostic upper bound", "candidate_id": "EXP-R3-unfrozen-v1", "implementation_id": "EXP-R4C-parallel8-full-v1", "parameter_id": "P0", "lambda_internal": 2.0, "horizon": 20, "controller_step_s": DT, "plant_step_s": .002, "maximum_plant_step_s": max_step_s, "iterations": len(rows), "expected_iterations": count, "duration_s": float(rows[-1][0]) if rows else 0.0, "reference_distance_m": distance, "route_length_m": ROUTE_LENGTH, "actual_payload_path_m": actual_path, "maximum_point_force_n": max_force, "maximum_internal_force_norm_n": max_internal, "maximum_tire_utilization": max_tire, "minimum_support_load_n": min_support, "maximum_configuration_error_m": max_eg, "trajectory_completed": bool(status == "COMPLETED" and distance >= ROUTE_LENGTH - 1e-9), "frozen_dynamics_jacobian": False, "finite_difference_scale": 1.0, "wall_s": time.perf_counter() - started, "deadline_unix": deadline_unix, "source_sha256": sha(__file__), "controller_sha256": sha(Path(controller.__file__))}
    checkpoint(out, rows, columns, subrows, subcolumns, metrics)
    save(out, "metrics.json", metrics)
    print(json.dumps(metrics, ensure_ascii=False), flush=True)
    if status != "COMPLETED":
        raise SystemExit(20)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-step-ms", type=float, choices=(1.0, .5), required=True)
    parser.add_argument("--deadline-unix", type=float, required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha", required=True)
    args = parser.parse_args()
    paper = Path(__file__).resolve().parents[3]
    protocol_path = Path(args.protocol).resolve()
    protocol = validate_protocol(protocol_path, args.protocol_sha, paper, args.max_step_ms, args.deadline_unix)
    out = Path(args.out).resolve()
    if out != (paper / protocol["run"]["output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    out.mkdir(parents=True)
    model = params("P0")
    state = initialize_state(model, SPEED)
    u_nom, _, _ = make_preview(0.0, np.zeros(4), model, np.zeros(8), 20)
    with ParallelFiniteDifferenceBackend(8) as backend:
        warmup = backend.warm(np.r_[state, np.zeros(4)], u_nom[0], model)
        save(out, "pool.json", {"workers": 8, "warmup_s": warmup})
        with install_parallel_linearization(backend):
            execute(out, args.max_step_ms / 1000.0, args.deadline_unix)


if __name__ == "__main__":
    main()
