"""Replay saved EXP-R3 QPs at the two registered tighter tolerances."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import osqp
from scipy import sparse

from ..controllers.physical_tracking_pilot import validate
from ..e01_100m import params


EPS = (2e-5, 2e-6)


def solve(path: Path, eps: float) -> dict:
    with np.load(path, allow_pickle=False) as z:
        data = {name: np.asarray(z[name], float) for name in z.files}
    solver = osqp.OSQP()
    solver.setup(
        P=sparse.csc_matrix(data["P"]), q=data["q"],
        A=sparse.csc_matrix(data["A"]), l=data["l"], u=data["u"],
        verbose=False, eps_abs=eps, eps_rel=eps, max_iter=4000, polishing=True,
    )
    result = solver.solve()
    ok = result.info.status in ("solved", "solved inaccurate") and result.x is not None
    candidate = data["u_nom"].ravel() + result.x if ok else data["u_nom"].ravel()
    validation = validate(data["z0"], candidate.reshape(20, 8), params("P0")) if ok else {"status": "NOT_RUN"}
    return {
        "status": str(result.info.status),
        "iterations": int(result.info.iter),
        "primal_residual": float(result.info.prim_res),
        "dual_residual": float(result.info.dual_res),
        "objective": float(result.info.obj_val),
        "first_control": candidate.reshape(20, 8)[0].tolist(),
        "validation": validation,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--matrix-dir", required=True)
    p.add_argument("--baseline-report", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    out = Path(a.out)
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    out.mkdir(parents=True)
    baseline = json.loads(Path(a.baseline_report).read_text(encoding="utf-8-sig"))
    baseline_first = {}
    for point in baseline["points"]:
        tag = f"t{point['time_s']:.2f}".replace(".", "p")
        for source in ("coarse", "fine"):
            baseline_first[(tag, source)] = np.asarray(
                point["own_memory"][source]["repeats"][0]["first_control"], float
            )
    rows = []
    for matrix in sorted(Path(a.matrix_dir).glob("t*_own_*.npz")):
        stem = matrix.stem
        source = "coarse" if stem.endswith("_coarse") else "fine"
        tag = stem.split("_own_")[0]
        for eps in EPS:
            result = solve(matrix, eps)
            result.update({
                "matrix": str(matrix), "tag": tag, "source": source, "eps_abs_rel": eps,
                "first_control_change_from_baseline_norm": float(
                    np.linalg.norm(np.asarray(result["first_control"]) - baseline_first[(tag, source)])
                ),
            })
            rows.append(result)
    checks = {
        "all_solved": all(row["status"] == "solved" for row in rows),
        "all_nonlinear_validation_pass": all(row["validation"]["status"] == "PASS" for row in rows),
        "two_registered_candidates_only": sorted({row["eps_abs_rel"] for row in rows}) == sorted(EPS),
    }
    report = {
        "status": "PASS_DIAGNOSTIC" if all(checks.values()) else "FAIL",
        "scope": "Saved QPs only; no rebuild and no closed-loop plant propagation",
        "checks": checks,
        "rows": rows,
        "maximum_first_control_change_from_baseline_norm": max(row["first_control_change_from_baseline_norm"] for row in rows),
    }
    (out / "qp_tolerance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "maximum_change": report["maximum_first_control_change_from_baseline_norm"]}, ensure_ascii=False))
    if report["status"] != "PASS_DIAGNOSTIC":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
