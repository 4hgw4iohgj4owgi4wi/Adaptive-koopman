"""EXP-R3 branch-A fixed-QP and state sensitivity diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import osqp
from scipy import sparse

from ..controllers.physical_tracking_pilot import (
    PilotConfig,
    build_problem,
    validate,
)
from ..e01_100m import params
from ..pilot_runner import DT, ROUTE_LENGTH, SPEED, make_preview


PROTOCOL_SHA256 = "eb5d176e444dd5008c9d527fa0c44cef134c9a2d285833ce5c4e5ba7cb8e0b87"
REGISTERED_TIMES = (42.40, 42.58, 43.06, 43.12)
TIME_ATOL = 1e-10


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def digest_array(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest().upper()


def load_raw(path: Path) -> tuple[np.ndarray, dict[str, int]]:
    with np.load(path, allow_pickle=False) as archive:
        values = np.asarray(archive["values"], float)
        names = np.asarray(archive["columns"]).astype(str)
    if len(names) != len(set(names.tolist())):
        raise ValueError("DUPLICATE_RAW_COLUMN")
    columns = {name: index for index, name in enumerate(names)}
    required = (
        ["time_s", "reference_distance_m"]
        + [f"x{i}" for i in range(30)]
        + [f"actual_delta{i}" for i in range(4)]
        + [f"request_accel{i}" for i in range(4)]
        + [f"request_delta{i}" for i in range(4)]
    )
    missing = [name for name in required if name not in columns]
    if missing:
        raise ValueError("MISSING_RAW_COLUMNS:" + ",".join(missing))
    if not np.all(np.isfinite(values[:, [columns[x] for x in required]])):
        raise ValueError("NONFINITE_RAW")
    return values, columns


def row_at(values: np.ndarray, columns: dict[str, int], time_s: float) -> np.ndarray:
    rows = np.flatnonzero(
        np.isclose(values[:, columns["time_s"]], time_s, rtol=0.0, atol=TIME_ATOL)
    )
    if len(rows) != 1:
        raise ValueError(f"TIME_ROW_COUNT:{time_s}:{len(rows)}")
    return values[int(rows[0])]


def state_and_previous(row: np.ndarray, c: dict[str, int]) -> tuple[np.ndarray, np.ndarray]:
    state = row[[c[f"x{i}"] for i in range(30)]]
    actual = row[[c[f"actual_delta{i}"] for i in range(4)]]
    previous = np.empty(8, dtype=float)
    previous[0::2] = row[[c[f"request_accel{i}"] for i in range(4)]]
    previous[1::2] = row[[c[f"request_delta{i}"] for i in range(4)]]
    return np.r_[state, actual], previous


def reference_state(time_s: float, model, previous_u: np.ndarray):
    tick = int(round(time_s / DT))
    if abs(time_s - tick * DT) > TIME_ATOL:
        raise ValueError("TIME_NOT_ON_CONTROL_GRID")
    beta = np.zeros(4)
    distance = 0.0
    zeros = np.zeros(8)
    for _ in range(tick):
        _, refs, _ = make_preview(distance, beta, model, zeros, 20)
        beta = np.asarray(refs[0]["beta_star"], float)
        distance = min(distance + SPEED * DT, ROUTE_LENGTH)
    u_nom, refs, _ = make_preview(distance, beta, model, previous_u, 20)
    return distance, beta, u_nom, refs


def solve_fixed(problem: dict, z0: np.ndarray, model, config: PilotConfig) -> dict:
    solver = osqp.OSQP()
    solver.setup(
        P=sparse.csc_matrix(problem["P"]),
        q=problem["q"],
        A=sparse.csc_matrix(problem["A"]),
        l=problem["l"],
        u=problem["u"],
        verbose=False,
        eps_abs=config.eps_abs,
        eps_rel=config.eps_rel,
        max_iter=config.max_iter,
        polishing=True,
    )
    result = solver.solve()
    ok = result.info.status in ("solved", "solved inaccurate") and result.x is not None
    if not ok:
        candidate = problem["u_nom"].ravel()
        validation = {"status": "NOT_RUN"}
        x = np.full_like(candidate, np.nan)
    else:
        x = np.asarray(result.x, float)
        candidate = problem["u_nom"].ravel() + x
        validation = validate(z0, candidate.reshape(config.horizon, 8), model)
    activity_tol = 5.0 * max(config.eps_abs, config.eps_rel)
    ax = problem["A"] @ x if ok else np.full_like(problem["l"], np.nan)
    lower_slack = ax - problem["l"]
    upper_slack = problem["u"] - ax
    finite_lower = np.isfinite(problem["l"])
    finite_upper = np.isfinite(problem["u"])
    active_lower = np.flatnonzero(finite_lower & (lower_slack <= activity_tol)).tolist()
    active_upper = np.flatnonzero(finite_upper & (upper_slack <= activity_tol)).tolist()
    return {
        "status": str(result.info.status),
        "iterations": int(result.info.iter),
        "primal_residual": float(result.info.prim_res),
        "dual_residual": float(result.info.dual_res),
        "objective": float(result.info.obj_val),
        "x": x,
        "control": candidate.reshape(config.horizon, 8),
        "validation": validation,
        "activity_tolerance": activity_tol,
        "active_lower": active_lower,
        "active_upper": active_upper,
        "minimum_finite_lower_slack": float(np.min(lower_slack[finite_lower])),
        "minimum_finite_upper_slack": float(np.min(upper_slack[finite_upper])),
    }


def matrix_summary(problem: dict) -> dict:
    p = np.asarray(problem["P"], float)
    eigenvalues = np.linalg.eigvalsh(p)
    positive = eigenvalues[eigenvalues > max(np.max(eigenvalues) * 1e-14, 1e-16)]
    return {
        "P_sha256": digest_array(p),
        "q_sha256": digest_array(problem["q"]),
        "A_sha256": digest_array(problem["A"]),
        "l_sha256": digest_array(problem["l"]),
        "u_sha256": digest_array(problem["u"]),
        "P_norm2": float(np.linalg.norm(p, 2)),
        "q_norm2": float(np.linalg.norm(problem["q"])),
        "A_norm2": float(np.linalg.norm(problem["A"], 2)),
        "P_min_eigenvalue": float(np.min(eigenvalues)),
        "P_max_eigenvalue": float(np.max(eigenvalues)),
        "P_effective_condition": float(np.max(eigenvalues) / np.min(positive)),
    }


def save_problem(path: Path, z0: np.ndarray, previous: np.ndarray, problem: dict) -> None:
    np.savez_compressed(
        path,
        z0=np.asarray(z0, float),
        previous_u=np.asarray(previous, float),
        u_nom=np.asarray(problem["u_nom"], float),
        P=np.asarray(problem["P"], float),
        q=np.asarray(problem["q"], float),
        A=np.asarray(problem["A"], float),
        l=np.asarray(problem["l"], float),
        u=np.asarray(problem["u"], float),
    )


def problem_difference(a: dict, b: dict) -> dict:
    result = {}
    for name in ("P", "q", "A", "l", "u"):
        av = np.asarray(a[name], float)
        bv = np.asarray(b[name], float)
        finite = np.isfinite(av) & np.isfinite(bv)
        absolute = float(np.linalg.norm((av - bv)[finite]))
        denominator = max(float(np.linalg.norm(bv[finite])), 1e-15)
        result[name + "_absolute_norm"] = absolute
        result[name + "_relative_norm"] = absolute / denominator
    return result


def serializable_solution(solution: dict) -> dict:
    return {
        key: value
        for key, value in solution.items()
        if key not in ("x", "control")
    } | {
        "x_sha256": digest_array(solution["x"]),
        "first_control": solution["control"][0].tolist(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-coarse", required=True)
    parser.add_argument("--source-fine", required=True)
    parser.add_argument("--times", nargs="+", type=float, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--protocol", required=True)
    args = parser.parse_args()
    if tuple(args.times) != REGISTERED_TIMES:
        raise ValueError("TIMES_NOT_REGISTERED")
    protocol = Path(args.protocol).resolve()
    if sha256(protocol).lower() != PROTOCOL_SHA256:
        raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    out = Path(args.out).resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    out.mkdir(parents=True)
    matrix_dir = out / "matrices"
    matrix_dir.mkdir()
    paths = {"coarse": Path(args.source_coarse).resolve(), "fine": Path(args.source_fine).resolve()}
    loaded = {name: load_raw(path) for name, path in paths.items()}
    model = params("P0")
    config = PilotConfig(horizon=20, lambda_internal=2.0)
    report = {
        "status": "RUNNING",
        "scope": "Saved-QP repeatability and state/previous-input sensitivity; no closed-loop plant run",
        "protocol_sha256": sha256(protocol),
        "sources": {name: {"path": str(path), "sha256": sha256(path)} for name, path in paths.items()},
        "times_s": list(REGISTERED_TIMES),
        "solver": {"eps_abs": config.eps_abs, "eps_rel": config.eps_rel, "max_iter": config.max_iter, "polishing": True},
        "points": [],
    }
    all_repeats_exact = True
    all_repeats_valid = True
    for time_s in REGISTERED_TIMES:
        point = {"time_s": time_s, "own_memory": {}, "common_fine_memory": {}}
        own = {}
        raw_rows = {}
        for name in ("coarse", "fine"):
            values, columns = loaded[name]
            row = row_at(values, columns, time_s)
            z0, previous = state_and_previous(row, columns)
            distance, beta, u_nom, refs = reference_state(time_s, model, previous)
            raw_distance = float(row[columns["reference_distance_m"]])
            if abs(distance - raw_distance) > 1e-10:
                raise ValueError("REFERENCE_DISTANCE_RECONSTRUCTION_MISMATCH")
            problem = build_problem(z0, u_nom, refs, model, config)
            tag = f"t{time_s:.2f}".replace(".", "p")
            save_problem(matrix_dir / f"{tag}_own_{name}.npz", z0, previous, problem)
            solutions = [solve_fixed(problem, z0, model, config) for _ in range(3)]
            repeat_exact = len({sol["x"].tobytes() for sol in solutions}) == 1
            repeat_valid = all(sol["validation"]["status"] == "PASS" for sol in solutions)
            all_repeats_exact &= repeat_exact
            all_repeats_valid &= repeat_valid
            point["own_memory"][name] = {
                "state_sha256": digest_array(z0),
                "previous_u_sha256": digest_array(previous),
                "reference_distance_m": distance,
                "beta_rad": beta.tolist(),
                "matrix": matrix_summary(problem),
                "repeats": [serializable_solution(sol) for sol in solutions],
                "repeat_solution_exact": repeat_exact,
                "repeat_validation_pass": repeat_valid,
            }
            own[name] = {"z0": z0, "previous": previous, "solution": solutions[0], "problem": problem}
            raw_rows[name] = (z0, previous)
        point["own_memory"]["first_control_difference_norm"] = float(
            np.linalg.norm(own["coarse"]["solution"]["control"][0] - own["fine"]["solution"]["control"][0])
        )
        point["own_memory"]["state_difference_norm"] = float(
            np.linalg.norm(own["coarse"]["z0"] - own["fine"]["z0"])
        )
        point["own_memory"]["previous_u_difference_norm"] = float(
            np.linalg.norm(own["coarse"]["previous"] - own["fine"]["previous"])
        )
        point["own_memory"]["problem_difference"] = problem_difference(
            own["coarse"]["problem"], own["fine"]["problem"]
        )

        common_previous = own["fine"]["previous"]
        common_solutions = {}
        common_problems = {}
        for name in ("coarse", "fine"):
            z0 = own[name]["z0"]
            _, _, u_nom, refs = reference_state(time_s, model, common_previous)
            problem = build_problem(z0, u_nom, refs, model, config)
            save_problem(
                matrix_dir / f"{tag}_common_fine_previous_{name}.npz",
                z0,
                common_previous,
                problem,
            )
            solution = solve_fixed(problem, z0, model, config)
            common_solutions[name] = solution
            common_problems[name] = problem
            point["common_fine_memory"][name] = {
                "matrix": matrix_summary(problem),
                "solution": serializable_solution(solution),
            }
        point["common_fine_memory"]["first_control_difference_norm"] = float(
            np.linalg.norm(common_solutions["coarse"]["control"][0] - common_solutions["fine"]["control"][0])
        )
        point["common_fine_memory"]["problem_difference"] = problem_difference(
            common_problems["coarse"], common_problems["fine"]
        )
        report["points"].append(point)
        save_json = lambda name, obj: (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        save_json("progress.json", report)
    report["checks"] = {
        "same_qp_three_repeats_bit_exact": bool(all_repeats_exact),
        "all_nonlinear_validations_pass": bool(all_repeats_valid),
    }
    report["status"] = "PASS_DIAGNOSTIC" if all(report["checks"].values()) else "FAIL"
    report["source_sha256"] = sha256(Path(__file__))
    (out / "qp_sensitivity.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": report["checks"], "control_differences": [{"time_s": p["time_s"], "own": p["own_memory"]["first_control_difference_norm"], "common": p["common_fine_memory"]["first_control_difference_norm"]} for p in report["points"]]}, ensure_ascii=False))
    if report["status"] != "PASS_DIAGNOSTIC":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
