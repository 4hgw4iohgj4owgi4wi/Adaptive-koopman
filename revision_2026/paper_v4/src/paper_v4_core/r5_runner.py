"""EXP-R2 R5 legal-information physical-MPC development runner."""
from __future__ import annotations

import argparse
import json
import osqp
import sys
import time
from pathlib import Path

import numpy as np

import contextlib

from .cli import save, sha
from .controllers.physical_tracking_pilot import PilotConfig
from .diagnostics.relative_motion import extract
from .e01_100m import DT, LIMIT, RATE, TAU, params
from .failure_boundary import consume_audit
from .information.legal_information import SensorNoise, sample_packets, solve_from_information
from .pilot_runner import ROUTE_LENGTH, SPEED, _path_sample, make_preview
from .plant.event_substep import EventSubstepConfig, advance_outer_step
from .plant.four_vehicle_common import connector_diagnostics, initialize_state, system_derivative
from .reference_geometry import transition_targets


ESTIMATE_COLUMNS = [f"estimate_x{i}" for i in range(30)] + [f"estimate_delta{i}" for i in range(4)]
ERROR_COLUMNS = [f"error_x{i}" for i in range(30)] + [f"error_delta{i}" for i in range(4)]


def _checkpoint(out, rows, columns, subrows, subcolumns, estimates, status):
    np.savez_compressed(out / "raw.npz", values=np.asarray(rows, float), columns=np.asarray(columns))
    sub = np.asarray(subrows, float) if subrows else np.empty((0, len(subcolumns)))
    np.savez_compressed(out / "substeps.npz", values=sub, columns=np.asarray(subcolumns))
    estimate_values = np.asarray(estimates, float) if estimates else np.empty((0, 2 + 68))
    np.savez_compressed(
        out / "estimates.npz",
        values=estimate_values,
        columns=np.asarray(["tick", "time_s", *ESTIMATE_COLUMNS, *ERROR_COLUMNS]),
    )
    save(out, "status.json", status)


def run(
    out,
    noise_name="none",
    seed=5105,
    segment_s=None,
    backend_name="gpu",
    output_ready=False,
    model=None,
    solver_settings=None,
    acceptance_tolerances=None,
    deadline_unix=None,
    protocol_sha256=None,
):
    out = Path(out)
    # output_ready is set by main() for the GPU and CPU-parallel branches, which must
    # create the directory early in order to record pool.json before the loop starts.
    # Without it the second mkdir raised FileExistsError and every accelerated launch died
    # immediately (observed on the first R5-N0 attempt, 0 ticks, no data).
    out.mkdir(parents=True, exist_ok=output_ready)
    if noise_name not in {"none", "basic"}:
        raise ValueError("noise_name must be none or basic")
    if backend_name not in {"gpu", "cpu", "serial"}:
        raise ValueError("backend_name must be gpu, cpu or serial")
    noise = SensorNoise.none() if noise_name == "none" else SensorNoise.basic()
    # The CUDA backend validates the model by identity (`model is not self.source_model`),
    # and params() returns a fresh object on every call.  Deriving the model here while the
    # backend was built from a different instance raised CUDA_BACKEND_MODEL_IDENTITY_MISMATCH,
    # which solve()'s catch-all swallowed into infinite residuals and then crashed the JSON
    # writer.  The caller's instance is therefore used when provided.
    model = params("P0") if model is None else model
    state = initialize_state(model, SPEED)
    delta = np.zeros(4)
    beta = np.zeros(4)
    previous_u = np.zeros(8)
    distance = 0.0
    rows, subrows, estimates = [], [], []
    solver_path = out / "solver.jsonl"
    information_path = out / "information.jsonl"
    started = time.perf_counter()
    status, reason = "RUNNING", None
    actual_path = 0.0
    last_payload = state[24:26].copy()
    max_force = max_internal = max_tire = max_eg = 0.0
    min_support = float("inf")
    iterations = 0
    lambda_internal = 2.0
    pilot_config = PilotConfig(
        horizon=20,
        lambda_internal=lambda_internal,
        frozen_dynamics_jacobian=False,
        finite_difference_scale=1.0,
        **(solver_settings or {}),
    )
    effective_settings = None
    requested_segment_s = float(segment_s) if segment_s is not None else ROUTE_LENGTH / SPEED
    count = int(np.ceil(requested_segment_s / DT))
    columns = (
        ["time_s", "reference_distance_m", "actual_payload_path_m", "lambda_internal"]
        + [f"x{i}" for i in range(30)]
        + [f"request_accel{i}" for i in range(4)]
        + [f"request_delta{i}" for i in range(4)]
        + [f"actual_delta{i}" for i in range(4)]
        + [f"point_force_norm{i}" for i in range(4)]
        + [f"tire_utilization{i}" for i in range(4)]
        + [f"support_load{i}" for i in range(4)]
        + ["internal_force_norm_n", "tension_x_n", "tension_y_n", "max_e_g_m", "solver_wall_s"]
        + ["tick_index", "interval_reference_distance_start_m"]
        + [f"reference_beta{i}" for i in range(4)]
        + [f"previous_u{i}" for i in range(8)]
    )
    subcolumns = ["time_s", "dt_s"] + [f"force_peak{i}" for i in range(4)] + [f"force_impulse_x{i}" for i in range(4)] + [f"force_impulse_y{i}" for i in range(4)] + [f"tire_utilization{i}" for i in range(4)] + [f"support_load{i}" for i in range(4)]

    with solver_path.open("w", encoding="utf-8") as solver_handle, information_path.open("w", encoding="utf-8") as information_handle:
        for k in range(count):
            if deadline_unix is not None and time.time() > float(deadline_unix):
                status, reason = "TIMEOUT_INCOMPLETE", "RUN_DEADLINE"
                break
            t = k * DT
            u_nom, refs, _ = make_preview(distance, beta, model, previous_u, 20)
            packet_bundle = sample_packets(state, delta, k, noise, int(seed))
            result = solve_from_information(
                packet_bundle,
                k,
                u_nom,
                refs,
                model,
                pilot_config,
            )
            effective = result.get("solver_settings_effective")
            effective_settings = effective
            if effective is not None and solver_settings and dict(effective) != dict(solver_settings):
                save(out, "solver_mismatch.json", {
                    "tick": k, "declared": dict(solver_settings), "effective": dict(effective),
                    "rule": "protocol-declared and runtime-effective solver settings must agree item by item",
                })
                status, reason = "FAILED", "SOLVER_SETTINGS_RUNTIME_MISMATCH"
                break
            estimate = np.asarray(result.pop("initial_estimate"), float)
            information_audit = result.pop("information_audit")
            estimate_error = estimate - np.r_[state, delta]
            estimate_error[[2, 8, 14, 20, 26]] = (
                estimate_error[[2, 8, 14, 20, 26]] + np.pi
            ) % (2.0 * np.pi) - np.pi
            estimates.append(np.r_[k, t, estimate, estimate_error])
            information_handle.write(json.dumps({
                "tick": k,
                "time_s": t,
                "noise_name": noise_name,
                "noise": noise.metadata(),
                "measurements_34": estimate.tolist(),
                "audit": information_audit,
            }, ensure_ascii=False, allow_nan=False) + "\n")
            information_handle.flush()
            solver_record = {key: result[key] for key in ("status", "solver_status", "iterations", "primal_residual", "dual_residual", "objective", "wall_s")}
            solver_record.update({"tick": k, "time_s": t, "validation": result["validation"], "first_control": result["control"][0].tolist(), "last_control": result["control"][-1].tolist(), "information_audit": information_audit})
            non_finite = [name for name in ("primal_residual", "dual_residual", "objective", "wall_s")
                          if not np.isfinite(float(solver_record[name]))]
            if non_finite:
                # A failed solve must be recorded, not crash the writer.  This mirrors the
                # fix applied to the G3 window runner after the same class of failure.
                save(out, "solver_failure.json", {
                    "tick": k, "time_s": t, "non_finite_fields": non_finite,
                    "solver_status": solver_record["solver_status"],
                    "validation_reason": result["validation"].get("reason"),
                    "record": json.loads(json.dumps(solver_record, ensure_ascii=False, default=str)),
                })
                status, reason = "FAILED", "NON_FINITE_SOLVER_RECORD:" + ",".join(non_finite)
                break
            solver_handle.write(json.dumps(solver_record, ensure_ascii=False, allow_nan=False) + "\n")
            solver_handle.flush()
            if result["status"] != "PASS":
                status, reason = "FAILED", "MPC_" + str(result["solver_status"])
                break

            command = np.asarray(result["control"][0]).reshape(4, 2)
            previous_u = result["control"][0].copy()
            interval_duration = 0.0
            for _ in range(10):
                delta_before = delta.copy()
                free = command[:, 1] + np.exp(-0.002 / TAU) * (delta - command[:, 1])
                delta = np.clip(delta + np.clip(free - delta, -RATE * 0.002, RATE * 0.002), -LIMIT, LIMIT)
                try:
                    state, audit = advance_outer_step(state, np.c_[command[:, 0], delta], "R3", model, 0.002, "ES", EventSubstepConfig(), max_step_s=0.002, load_transfer_enabled=True)
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

            if status != "RUNNING":
                break

            distance_before = float(distance)
            distance = min(distance + SPEED * interval_duration, ROUTE_LENGTH)
            beta = beta + (interval_duration / DT) * (np.asarray(refs[0]["beta_star"]) - beta)
            diagnostics = connector_diagnostics(state, model, "R3")
            _, system = system_derivative(state, np.c_[command[:, 0], delta], model, "R3", load_transfer_enabled=True)
            point_force = np.asarray(diagnostics["force_norm_n"])
            tire = np.asarray([item["raw_utilization"] for item in system["tire"]])
            support = np.asarray(system["payload_support_load_n"])
            q_star = transition_targets(np.asarray([SPEED, 0.0]), SPEED * _path_sample(distance)[3], beta, model)["centers"]
            relative = extract(state, model, q_star, beta)
            e_g = float(np.max(np.linalg.norm(relative["e_g_m"], axis=1)))
            payload = state[24:26]
            actual_path += float(np.linalg.norm(payload - last_payload))
            last_payload = payload.copy()
            max_force = max(max_force, float(np.max(point_force)))
            max_internal = max(max_internal, float(diagnostics["internal_force_norm_n"]))
            max_tire = max(max_tire, float(np.max(tire)))
            min_support = min(min_support, float(np.min(support)))
            max_eg = max(max_eg, e_g)
            rows.append(np.r_[t + interval_duration, distance, actual_path, lambda_internal, state, command[:, 0], command[:, 1], delta, point_force, tire, support, diagnostics["internal_force_norm_n"], diagnostics["tension_x_n"], diagnostics["tension_y_n"], e_g, result["wall_s"], float(k), distance_before, beta.copy(), previous_u.copy()])
            iterations = k + 1
            if max_force > 15000.0 + 1e-6:
                status, reason = "FAILED", "STOP_ULTIMATE_FORCE_ENDPOINT"
            elif max_tire > 1.0 + 1e-9:
                status, reason = "FAILED", "TIRE_CAPABILITY_VIOLATION"
            elif min_support < 0.0:
                status, reason = "FAILED", "SUPPORT_LIFT"
            if status == "FAILED":
                break
            if (k + 1) % 25 == 0:
                _checkpoint(out, rows, columns, subrows, subcolumns, estimates, {"status": "RUNNING", "tick": k + 1, "time_s": t + interval_duration, "reference_distance_m": distance, "updated_unix": time.time()})
        if status == "RUNNING":
            status = "COMPLETED" if iterations == count else "PAUSED"

    errors = np.asarray(estimates, float)[:, 36:] if estimates else np.empty((0, 34))
    metrics = {
        "status": status,
        "reason": reason,
        "role": "DEV",
        "execution_backend": backend_name,
        "solver_settings": pilot_config.solver_settings(),
        "solver_settings_effective": effective_settings,
        "solver_settings_source": "protocol" if solver_settings else "runner_default_historical",
        "acceptance_tolerances": dict(acceptance_tolerances) if acceptance_tolerances else None,
        "environment": {"python": sys.executable, "version": sys.version.split()[0],
                        "osqp": osqp.__version__, "numpy": np.__version__},
        "deadline_unix": float(deadline_unix) if deadline_unix is not None else None,
        "frozen_dynamics_jacobian": False,
        "finite_difference_scale": 1.0,
        "noise_indexing": "per absolute tick, node and field via SeedSequence",
        "information_schema": "EXP-R2-R5-legal-information-v2-absolute-tick-noise",
        "identity": "Centralized physical MPC supplied only by same-tick legal sensor packets; R5 interface diagnostic",
        "information_architecture": "centralized same-tick fusion; no network impairment",
        "noise_name": noise_name,
        "noise": noise.metadata(),
        "noise_seed": int(seed),
        "parameter_id": "P0",
        "lambda_internal": lambda_internal,
        "horizon": 20,
        "controller_step_s": DT,
        "plant_step_s": 0.002,
        "maximum_plant_step_s": 0.002,
        "requested_segment_s": requested_segment_s,
        "iterations": iterations,
        "duration_s": float(rows[-1][0]) if rows else 0.0,
        "reference_distance_m": distance,
        "route_length_m": ROUTE_LENGTH,
        "actual_payload_path_m": actual_path,
        "maximum_point_force_n": max_force,
        "maximum_internal_force_norm_n": max_internal,
        "maximum_tire_utilization": max_tire,
        "minimum_support_load_n": min_support,
        "maximum_configuration_error_m": max_eg,
        "trajectory_completed": bool(status == "COMPLETED" and distance >= ROUTE_LENGTH - 1e-9),
        "predicted_force_budget_n": 12000.0,
        "ultimate_stop_n": 15000.0,
        "solver_calls": iterations + (1 if status == "FAILED" and reason and reason.startswith("MPC_") else 0),
        "state_estimate_rmse": float(np.sqrt(np.mean(errors[:, :30] ** 2))) if len(errors) else None,
        "steering_estimate_rmse_rad": float(np.sqrt(np.mean(errors[:, 30:] ** 2))) if len(errors) else None,
        "wall_s": time.perf_counter() - started,
        "source_sha256": sha(__file__),
        "protocol_sha256": protocol_sha256,
    }
    _checkpoint(out, rows, columns, subrows, subcolumns, estimates, metrics)
    save(out, "metrics.json", metrics)
    if status != "COMPLETED":
        raise SystemExit(20)
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--noise", choices=["none", "basic"], required=True)
    parser.add_argument("--seed", type=int, default=5105)
    parser.add_argument("--segment-s", type=float)
    parser.add_argument("--backend", choices=["gpu", "cpu", "serial"], default="gpu")
    parser.add_argument("--protocol")
    parser.add_argument("--protocol-sha")
    parser.add_argument("--deadline-unix", type=float)
    args = parser.parse_args()
    out = Path(args.out)
    # Initialised before the protocol block so that the protocol-derived value is not
    # clobbered; with a protocol the settings are mandatory, without one the runner records
    # that it fell back to the historical configuration.
    solver_settings = None
    acceptance = None
    protocol_sha256 = None
    if args.protocol:
        protocol_path = Path(args.protocol)
        if sha(protocol_path) != str(args.protocol_sha).lower():
            raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
        protocol_sha256 = str(args.protocol_sha).lower()
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        if protocol.get("scope") != "R5_LEGAL_INFORMATION":
            raise ValueError("SCOPE_MISMATCH")
        declared = protocol["run"]
        if declared["output"] != args.out.replace("\\", "/"):
            raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
        if declared["noise"] != args.noise or int(declared["seed"]) != int(args.seed) or declared["backend"] != args.backend:
            raise ValueError("RUN_CONFIGURATION_MISMATCH")
        required_run = {
            "parameter_id": "P0",
            "plant_max_step_ms": 2.0,
            "controller_step_ms": 20.0,
            "horizon": 20,
            "lambda_internal": 2.0,
            "frozen_dynamics_jacobian": False,
            "finite_difference_scale": 1.0,
            "total_ticks": 2379,
        }
        for key, expected in required_run.items():
            if declared.get(key) != expected:
                raise ValueError("RUN_CONFIGURATION_MISMATCH:" + key)
        from .diagnostics.full_route_gpu_runner import resolve_acceptance_tolerances, resolve_solver_settings

        resolved = resolve_solver_settings(protocol)
        if resolved["source"] != "protocol":
            raise ValueError("SOLVER_SETTINGS_NOT_DECLARED_IN_PROTOCOL")
        solver_settings = resolved["settings"]
        acceptance = resolve_acceptance_tolerances(protocol)
        if acceptance is None:
            raise ValueError("ACCEPTANCE_TOLERANCES_NOT_DECLARED_IN_PROTOCOL")
        if args.deadline_unix is None:
            raise ValueError("DEADLINE_REQUIRED_FOR_PROTOCOL_RUN")
        paper = Path(__file__).resolve().parents[2]
        for item in protocol["identity_files"]:
            path = paper / item["path"]
            if not path.is_file() or sha(path) != item["sha256"]:
                raise ValueError("IDENTITY_FILE_MISMATCH:" + item["path"])
        if out.exists():
            raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    model = params("P0")
    if args.backend == "gpu":
        from .gpu_port.ipc_backend import CudaIpcFiniteDifferenceBackend, install_cuda_linearization

        with CudaIpcFiniteDifferenceBackend(model) as backend:
            environment = backend.environment()
            warmup_s = backend.warm(np.r_[initialize_state(model, SPEED), np.zeros(4)], np.zeros(8))
            out.mkdir(parents=True, exist_ok=False)
            save(out, "pool.json", {
                "backend": "cuda",
                "device": environment.get("device_name"),
                "warmup_s": warmup_s,
                "worker_module_audit": environment.get("worker_module_audit"),
                "note": "R5 runs on the GPU path per gpu_platform_decision_20260916.md; the noiseless no-op gate is compared against a same-backend baseline.",
            })
            with install_cuda_linearization(backend):
                run(
                    out, args.noise, args.seed, args.segment_s, args.backend,
                    output_ready=True, model=model, solver_settings=solver_settings,
                    acceptance_tolerances=acceptance, deadline_unix=args.deadline_unix,
                    protocol_sha256=protocol_sha256,
                )
    elif args.backend == "cpu":
        from .controllers.parallel_fd_backend import ParallelFiniteDifferenceBackend, install_parallel_linearization

        with ParallelFiniteDifferenceBackend(8) as backend:
            warmup_s = backend.warm(np.r_[initialize_state(model, SPEED), np.zeros(4)], np.zeros(8), model)
            out.mkdir(parents=True, exist_ok=False)
            save(out, "pool.json", {"backend": "cpu_parallel8", "workers": 8, "warmup_s": warmup_s})
            with install_parallel_linearization(backend):
                run(
                    out, args.noise, args.seed, args.segment_s, args.backend,
                    output_ready=True, model=model, solver_settings=solver_settings,
                    acceptance_tolerances=acceptance, deadline_unix=args.deadline_unix,
                    protocol_sha256=protocol_sha256,
                )
    else:
        run(
            out, args.noise, args.seed, args.segment_s, args.backend,
            solver_settings=solver_settings, acceptance_tolerances=acceptance,
            deadline_unix=args.deadline_unix, protocol_sha256=protocol_sha256,
        )


if __name__ == "__main__":
    main()
