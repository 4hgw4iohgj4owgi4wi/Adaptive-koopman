"""EXP-R4 U2 bounded cost attribution on the four saved QP diagnostic points."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import osqp
from scipy import sparse

from ..controllers import physical_tracking_pilot as controller
from ..controllers.physical_tracking_pilot import PilotConfig
from ..e01_100m import params
from .qp_fd_trials import TRIALS, array_digest, load_saved_problem
from .qp_sensitivity import load_raw, reference_state, row_at, state_and_previous


def profile_build(z0, u_nom, refs, model, config):
    totals = {"dynamics_linearization_s": 0.0, "tracking_feature_jacobian_s": 0.0, "internal_force_jacobian_s": 0.0, "constraint_jacobian_s": 0.0}
    originals = (controller.linearize_step, controller._jacobian, controller._constraint_jacobian)

    def linearize(*args, **kwargs):
        started = time.perf_counter(); result = originals[0](*args, **kwargs)
        totals["dynamics_linearization_s"] += time.perf_counter() - started
        return result

    def jacobian(*args, **kwargs):
        started = time.perf_counter(); result = originals[1](*args, **kwargs)
        key = "tracking_feature_jacobian_s" if len(result[0]) > 12 else "internal_force_jacobian_s"
        totals[key] += time.perf_counter() - started
        return result

    def constraint(*args, **kwargs):
        started = time.perf_counter(); result = originals[2](*args, **kwargs)
        totals["constraint_jacobian_s"] += time.perf_counter() - started
        return result

    controller.linearize_step, controller._jacobian, controller._constraint_jacobian = linearize, jacobian, constraint
    try:
        started = time.perf_counter()
        problem = controller.build_problem(z0, u_nom, refs, model, config)
        total = time.perf_counter() - started
    finally:
        controller.linearize_step, controller._jacobian, controller._constraint_jacobian = originals
    totals["assembly_other_s"] = max(0.0, total - sum(totals.values()))
    totals["build_total_s"] = total
    return problem, totals


def solve_and_validate(problem, z0, model, config):
    started = time.perf_counter()
    solver = osqp.OSQP()
    solver.setup(P=sparse.csc_matrix(problem["P"]), q=problem["q"], A=sparse.csc_matrix(problem["A"]), l=problem["l"], u=problem["u"], verbose=False, eps_abs=config.eps_abs, eps_rel=config.eps_rel, max_iter=config.max_iter, polishing=True)
    result = solver.solve()
    solve_s = time.perf_counter() - started
    if result.info.status not in ("solved", "solved inaccurate") or result.x is None:
        raise RuntimeError("QP_NOT_SOLVED:" + str(result.info.status))
    controls = problem["u_nom"].ravel() + result.x
    started = time.perf_counter()
    validation = controller.validate(z0, controls.reshape(config.horizon, 8), model)
    validation_s = time.perf_counter() - started
    return result, controls, validation, solve_s, validation_s


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fd-report", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    out.mkdir(parents=True)
    fd_report_path = Path(args.fd_report).resolve()
    fd_report = json.loads(fd_report_path.read_text(encoding="utf-8-sig"))
    fine_path = Path(fd_report["sources"]["fine"]["path"])
    values, columns = load_raw(fine_path)
    model = params("P0")
    rows = []
    for name, time_s, scale, frozen in TRIALS:
        row = row_at(values, columns, time_s)
        z0, previous = state_and_previous(row, columns)
        _, _, u_nom, refs = reference_state(time_s, model, previous)
        config = PilotConfig(horizon=20, lambda_internal=2.0, finite_difference_scale=scale, frozen_dynamics_jacobian=frozen)
        problem, timing = profile_build(z0, u_nom, refs, model, config)
        result, controls, validation, solve_s, validation_s = solve_and_validate(problem, z0, model, config)
        saved = load_saved_problem(fd_report_path.parent / "matrices" / f"{name}_fine.npz")
        exact = {key: bool(np.array_equal(np.asarray(problem[key]), np.asarray(saved[key]), equal_nan=True)) for key in ("P", "q", "A", "l", "u", "u_nom")}
        timing.update({"qp_setup_and_solve_s": solve_s, "nonlinear_validation_s": validation_s})
        total = timing["build_total_s"] + solve_s + validation_s
        rows.append({
            "name": name, "time_s": time_s, "frozen_dynamics_jacobian": frozen, "finite_difference_scale": scale,
            "timing": timing, "total_s": total,
            "build_fraction": timing["build_total_s"] / total,
            "dynamics_fraction_of_build": timing["dynamics_linearization_s"] / timing["build_total_s"],
            "matrix_exact_saved": exact,
            "first_control_sha256": array_digest(controls[:8]),
            "solver_status": str(result.info.status), "solver_iterations": int(result.info.iter),
            "nonlinear_validation": validation["status"],
        })
    unfrozen = [r for r in rows if not r["frozen_dynamics_jacobian"]]
    mean_total = float(np.mean([r["total_s"] for r in unfrozen]))
    mean_build = float(np.mean([r["timing"]["build_total_s"] for r in unfrozen]))
    report = {
        "schema_version": "EXP-R4-U2-QP-cost-profile-v1", "status": "PASS_DIAGNOSTIC",
        "scope": "Four registered saved QP points, fine-state side only; no closed-loop propagation.",
        "source_report": str(fd_report_path), "rows": rows,
        "summary": {
            "unfrozen_mean_total_s": mean_total, "unfrozen_mean_build_s": mean_build,
            "budget_target_s": 5.0, "budget_pass": mean_total <= 5.0,
            "dominant_component": "dynamics_linearization" if all(r["timing"]["dynamics_linearization_s"] > 0.5 * r["timing"]["build_total_s"] for r in unfrozen) else "mixed",
            "next_design": "Accelerate the repeated finite-difference dynamics linearizations without changing P/q/A/bounds; require exact matrix, first-control and nonlinear-validation regression before any short window."
        },
        "checks": {
            "exactly_four_points": len(rows) == 4,
            "all_matrices_exact_saved": all(all(r["matrix_exact_saved"].values()) for r in rows),
            "all_qps_solved": all(r["solver_status"] in ("solved", "solved inaccurate") for r in rows),
            "all_nonlinear_valid": all(r["nonlinear_validation"] == "PASS" for r in rows),
        }
    }
    if not all(report["checks"].values()): report["status"] = "FAIL"
    (out / "qp_cost_profile.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], **report["summary"]}))
    if report["status"] == "FAIL": raise SystemExit(20)


if __name__ == "__main__":
    main()
