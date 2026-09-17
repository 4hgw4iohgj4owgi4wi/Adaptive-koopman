"""EXP-R3 branch-A pre-registered finite-difference/Jacobian single-point trials."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from ..controllers.physical_tracking_pilot import PilotConfig, build_problem
from ..diagnostics.qp_sensitivity import (
    load_raw,
    matrix_summary,
    problem_difference,
    reference_state,
    row_at,
    save_problem,
    serializable_solution,
    sha256,
    solve_fixed,
    state_and_previous,
)
from ..e01_100m import params


PROTOCOL_SHA256 = "eb5d176e444dd5008c9d527fa0c44cef134c9a2d285833ce5c4e5ba7cb8e0b87"
TRIALS = (
    ("t42p58_fd0p5_frozen", 42.58, 0.5, True),
    ("t42p58_fd2_frozen", 42.58, 2.0, True),
    ("t42p58_fd1_unfrozen", 42.58, 1.0, False),
    ("t43p06_fd1_unfrozen", 43.06, 1.0, False),
)


def array_digest(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest().upper()


def load_saved_problem(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as archive:
        return {name: np.asarray(archive[name], float) for name in ("P", "q", "A", "l", "u", "u_nom")}


def exact_problem_equal(a: dict, b: dict) -> tuple[bool, dict]:
    checks = {}
    for name in ("P", "q", "A", "l", "u", "u_nom"):
        av, bv = np.asarray(a[name]), np.asarray(b[name])
        checks[name] = bool(av.shape == bv.shape and np.array_equal(av, bv, equal_nan=True))
    return all(checks.values()), checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-coarse", required=True)
    parser.add_argument("--source-fine", required=True)
    parser.add_argument("--baseline-matrix-dir", required=True)
    parser.add_argument("--baseline-report", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    protocol = Path(args.protocol).resolve()
    if sha256(protocol).lower() != PROTOCOL_SHA256:
        raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    out = Path(args.out).resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    out.mkdir(parents=True)
    matrix_out = out / "matrices"
    matrix_out.mkdir()
    paths = {"coarse": Path(args.source_coarse).resolve(), "fine": Path(args.source_fine).resolve()}
    loaded = {name: load_raw(path) for name, path in paths.items()}
    baseline_report = json.loads(Path(args.baseline_report).read_text(encoding="utf-8-sig"))
    baseline_differences = {
        float(point["time_s"]): float(point["common_fine_memory"]["first_control_difference_norm"])
        for point in baseline_report["points"]
    }
    model = params("P0")

    # Hard default-behaviour gate before any registered variant trial.
    fine_values, fine_columns = loaded["fine"]
    regression_row = row_at(fine_values, fine_columns, 42.58)
    regression_z0, regression_previous = state_and_previous(regression_row, fine_columns)
    _, _, regression_u_nom, regression_refs = reference_state(42.58, model, regression_previous)
    regression_config = PilotConfig(horizon=20, lambda_internal=2.0)
    rebuilt = build_problem(regression_z0, regression_u_nom, regression_refs, model, regression_config)
    saved = load_saved_problem(Path(args.baseline_matrix_dir) / "t42p58_common_fine_previous_fine.npz")
    exact, exact_fields = exact_problem_equal(rebuilt, saved)
    regression = {
        "status": "PASS" if exact else "FAIL",
        "saved_matrix": str(Path(args.baseline_matrix_dir) / "t42p58_common_fine_previous_fine.npz"),
        "exact_fields": exact_fields,
        "rebuilt_hashes": {name: array_digest(np.asarray(rebuilt[name])) for name in exact_fields},
        "saved_hashes": {name: array_digest(np.asarray(saved[name])) for name in exact_fields},
    }
    (out / "default_regression.json").write_text(json.dumps(regression, indent=2), encoding="utf-8")
    if not exact:
        raise SystemExit(21)

    report = {
        "status": "RUNNING",
        "scope": "Exactly four pre-registered single-point QP builds; no closed-loop propagation",
        "protocol_sha256": sha256(protocol),
        "sources": {name: {"path": str(path), "sha256": sha256(path)} for name, path in paths.items()},
        "default_regression": regression,
        "trials_registered": [
            {"name": name, "time_s": time_s, "finite_difference_scale": scale, "frozen_dynamics_jacobian": frozen}
            for name, time_s, scale, frozen in TRIALS
        ],
        "trials": [],
    }
    for trial_name, time_s, scale, frozen in TRIALS:
        config = PilotConfig(
            horizon=20,
            lambda_internal=2.0,
            finite_difference_scale=scale,
            frozen_dynamics_jacobian=frozen,
        )
        pair = {}
        problems = {}
        solutions = {}
        fine_row = row_at(fine_values, fine_columns, time_s)
        _, common_previous = state_and_previous(fine_row, fine_columns)
        for source in ("coarse", "fine"):
            values, columns = loaded[source]
            row = row_at(values, columns, time_s)
            z0, _ = state_and_previous(row, columns)
            _, _, u_nom, refs = reference_state(time_s, model, common_previous)
            started = time.perf_counter()
            problem = build_problem(z0, u_nom, refs, model, config)
            build_wall_s = time.perf_counter() - started
            solution = solve_fixed(problem, z0, model, config)
            save_problem(matrix_out / f"{trial_name}_{source}.npz", z0, common_previous, problem)
            problems[source] = problem
            solutions[source] = solution
            pair[source] = {
                "build_wall_s": build_wall_s,
                "matrix": matrix_summary(problem),
                "solution": serializable_solution(solution),
            }
        difference = float(np.linalg.norm(solutions["coarse"]["control"][0] - solutions["fine"]["control"][0]))
        baseline_difference = baseline_differences[time_s]
        trial = {
            "name": trial_name,
            "time_s": time_s,
            "finite_difference_scale": scale,
            "frozen_dynamics_jacobian": frozen,
            "coarse": pair["coarse"],
            "fine": pair["fine"],
            "problem_difference": problem_difference(problems["coarse"], problems["fine"]),
            "first_control_difference_norm": difference,
            "baseline_first_control_difference_norm": baseline_difference,
            "difference_ratio_to_baseline": difference / max(baseline_difference, 1e-15),
            "both_nonlinear_valid": bool(
                solutions["coarse"]["validation"]["status"] == "PASS"
                and solutions["fine"]["validation"]["status"] == "PASS"
            ),
        }
        report["trials"].append(trial)
        (out / "progress.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    report["checks"] = {
        "default_problem_bit_exact": True,
        "exactly_four_registered_trials": len(report["trials"]) == len(TRIALS) == 4,
        "all_qps_solved": all(t[s]["solution"]["status"] == "solved" for t in report["trials"] for s in ("coarse", "fine")),
        "all_nonlinear_validations_pass": all(t["both_nonlinear_valid"] for t in report["trials"]),
    }
    report["status"] = "PASS_DIAGNOSTIC" if all(report["checks"].values()) else "FAIL"
    report["source_sha256"] = sha256(Path(__file__))
    (out / "qp_fd_trials.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "ratios": [{"name": t["name"], "ratio": t["difference_ratio_to_baseline"]} for t in report["trials"]],
    }))
    if report["status"] != "PASS_DIAGNOSTIC":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
