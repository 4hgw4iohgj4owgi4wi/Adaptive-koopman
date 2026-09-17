"""EXP-R4 U3 deterministic process-parallel finite-difference equivalence test."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import time
from pathlib import Path

import numpy as np

from ..controllers import physical_tracking_pilot as controller
from ..controllers.physical_tracking_pilot import PilotConfig
from ..e01_100m import params
from .qp_fd_trials import array_digest, load_saved_problem
from .qp_sensitivity import load_raw, reference_state, row_at, solve_fixed, state_and_previous


def _rollout_job(job):
    z, u, model = job
    return controller.rollout_step(z, u, model)


def parallel_linearize(z, u, model, executor, finite_difference_scale=1.0):
    z = np.asarray(z, float); u = np.asarray(u, float)
    f0 = controller.rollout_step(z, u, model)
    state_steps = controller._steps(34, scale=finite_difference_scale)
    input_steps = np.asarray([1e-4 if j % 2 == 0 else 1e-6 for j in range(8)]) * finite_difference_scale
    jobs = []
    for j, step in enumerate(state_steps):
        plus = z.copy(); minus = z.copy(); plus[j] += step; minus[j] -= step
        jobs.extend(((plus, u, model), (minus, u, model)))
    for j, step in enumerate(input_steps):
        plus = u.copy(); minus = u.copy(); plus[j] += step; minus[j] -= step
        jobs.extend(((z, plus, model), (z, minus, model)))
    values = list(executor.map(_rollout_job, jobs, chunksize=1))
    A = np.empty((34, 34)); B = np.empty((34, 8)); offset = 0
    for j, step in enumerate(state_steps):
        A[:, j] = (values[offset] - values[offset + 1]) / (2 * step); offset += 2
    for j, step in enumerate(input_steps):
        B[:, j] = (values[offset] - values[offset + 1]) / (2 * step); offset += 2
    return f0, A, B


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--saved-problem", required=True)
    parser.add_argument("--time-s", type=float, default=42.58)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16: raise ValueError("WORKERS_OUT_OF_RANGE")
    out = Path(args.out).resolve()
    if out.exists(): raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    out.mkdir(parents=True)
    values, columns = load_raw(Path(args.source).resolve())
    sample = row_at(values, columns, args.time_s)
    z0, previous = state_and_previous(sample, columns)
    model = params("P0")
    _, _, u_nom, refs = reference_state(args.time_s, model, previous)
    config = PilotConfig(horizon=20, lambda_internal=2.0, finite_difference_scale=1.0, frozen_dynamics_jacobian=False)
    saved = load_saved_problem(Path(args.saved_problem).resolve())
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Pool creation is a one-time controller initialization cost, recorded separately.
        started = time.perf_counter(); list(executor.map(_rollout_job, [(z0, u_nom[0], model)] * args.workers, chunksize=1)); warm_s = time.perf_counter() - started
        original = controller.linearize_step
        controller.linearize_step = lambda z, u, m, finite_difference_scale=1.0: parallel_linearize(z, u, m, executor, finite_difference_scale)
        try:
            started = time.perf_counter(); problem = controller.build_problem(z0, u_nom, refs, model, config); build_s = time.perf_counter() - started
        finally:
            controller.linearize_step = original
    exact = {key: bool(np.array_equal(np.asarray(problem[key]), np.asarray(saved[key]), equal_nan=True)) for key in ("P", "q", "A", "l", "u", "u_nom")}
    started = time.perf_counter(); solution = solve_fixed(problem, z0, model, config); solve_validate_s = time.perf_counter() - started
    total_s = build_s + solve_validate_s
    report = {
        "schema_version": "EXP-R4-U3-parallel-equivalence-v1", "candidate_id": "EXP-R4-unfrozen-parallel-fd-v1",
        "status": "PASS_EQUIVALENT_BUDGET" if all(exact.values()) and solution["validation"]["status"] == "PASS" and total_s <= 5.0 else "FAIL",
        "scope": "One pre-registered saved-QP point; no closed-loop propagation.", "workers": args.workers,
        "pool_warmup_s": warm_s, "build_s": build_s, "solve_and_validate_s": solve_validate_s, "total_per_step_s": total_s, "budget_target_s": 5.0,
        "matrix_exact_saved": exact, "first_control_sha256": array_digest(solution["control"][0]),
        "solver_status": solution["status"], "nonlinear_validation": solution["validation"]["status"],
        "implementation_note": "Only independent central-difference rollout evaluations are dispatched to persistent worker processes; reconstruction order and all formulas are unchanged."
    }
    (out / "parallel_equivalence.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "workers", "pool_warmup_s", "build_s", "solve_and_validate_s", "total_per_step_s")}))
    if report["status"] != "PASS_EQUIVALENT_BUDGET": raise SystemExit(20)


if __name__ == "__main__":
    main()
