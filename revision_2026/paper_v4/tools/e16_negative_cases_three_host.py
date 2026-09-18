"""Run registered E16 negative examples and draw their diagnostic figures."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PAPER = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(PAPER.resolve())).replace("\\", "/")


def formula_verdict(norm_a: float, r_u: float, c_u: float) -> dict:
    if norm_a > r_u:
        return {"status": "NOT_CERTIFIABLE", "gamma_interval": None}
    if c_u == 0.0:
        return {"status": "BASE_BLOCK_CERTIFIABLE", "gamma_interval": [0.0, 1.0]}
    gamma_max = min(1.0, (r_u - norm_a) / c_u)
    return {"status": "CERTIFIABLE_INTERVAL", "gamma_interval": [0.0, gamma_max]}


def trajectory(matrix: np.ndarray, initial: np.ndarray, steps: int) -> np.ndarray:
    rows = [initial.astype(float)]
    for _ in range(steps):
        rows.append(matrix @ rows[-1])
    return np.asarray(rows)


def save(fig: plt.Figure, directory: Path, stem: str) -> list[str]:
    png = directory / f"{stem}.png"
    svg = directory / f"{stem}.svg"
    fig.savefig(png, dpi=220, bbox_inches="tight")
    fig.savefig(svg, bbox_inches="tight")
    plt.close(fig)
    return [relative(png), relative(svg)]


def compute(spec: dict) -> tuple[dict, dict[str, np.ndarray]]:
    formula_rows = []
    formula_pass = True
    for case in spec["formula_13_cases"]:
        verdict = formula_verdict(case["norm_a_plus"], case["r_u"], case["c_u"])
        passed = verdict["status"] == case["expected_status"]
        if "expected_gamma_max" in case:
            actual = verdict["gamma_interval"][1] if verdict["gamma_interval"] else None
            passed = passed and np.isclose(actual, case["expected_gamma_max"], atol=1e-15)
        formula_pass = formula_pass and bool(passed)
        formula_rows.append({**case, "actual": verdict, "pass": bool(passed)})

    scalar = spec["scalar_clip_counterexample"]
    bad_gamma = float(np.clip((scalar["r_u"] - scalar["norm_a_plus"]) / scalar["c_u"], 0.0, 1.0))
    true_verdict = formula_verdict(scalar["norm_a_plus"], scalar["r_u"], scalar["c_u"])
    scalar_pass = (
        np.isclose(bad_gamma, scalar["expected_bad_gamma"], atol=1e-15)
        and true_verdict["status"] == scalar["expected_true_status"]
    )

    nonnormal = spec["nonnormal_case"]
    n_matrix = np.asarray(nonnormal["matrix"], dtype=float)
    n_traj = trajectory(n_matrix, np.asarray(nonnormal["initial_state"], dtype=float), int(nonnormal["steps"]))
    n_norms = np.linalg.norm(n_traj, axis=1)
    n_radius = float(np.max(np.abs(np.linalg.eigvals(n_matrix))))
    n_operator = float(np.linalg.norm(n_matrix, 2))
    n_growth = float(np.max(n_norms) / n_norms[0])
    nonnormal_pass = n_radius < 1.0 and n_growth > 1.0

    switched = spec["switched_case"]
    a = np.asarray(switched["matrix_a"], dtype=float)
    b = np.asarray(switched["matrix_b"], dtype=float)
    x0 = np.asarray(switched["initial_state"], dtype=float)
    steps = int(switched["steps"])
    fixed_a = trajectory(a, x0, steps)
    fixed_b = trajectory(b, x0, steps)
    alternating = [x0]
    for index in range(steps):
        matrix = a if index % 2 == 0 else b
        alternating.append(matrix @ alternating[-1])
    alternating = np.asarray(alternating)
    radius_a = float(np.max(np.abs(np.linalg.eigvals(a))))
    radius_b = float(np.max(np.abs(np.linalg.eigvals(b))))
    alt_growth = float(np.linalg.norm(alternating[-1]) / np.linalg.norm(alternating[0]))
    switched_pass = radius_a < 1.0 and radius_b < 1.0 and alt_growth > 1.0

    status = "PASS_E16_NEGATIVE_TESTS" if all(
        (formula_pass, scalar_pass, nonnormal_pass, switched_pass)
    ) else "FAIL_E16_NEGATIVE_TESTS"
    report = {
        "status": status,
        "contract_id": spec["contract_id"],
        "formula_13": {"cases": formula_rows, "pass": formula_pass},
        "scalar_clip_counterexample": {
            "bad_rule_gamma": bad_gamma,
            "true_verdict": true_verdict,
            "pass": bool(scalar_pass),
        },
        "nonnormal_counterexample": {
            "spectral_radius": n_radius,
            "operator_2_norm": n_operator,
            "maximum_state_norm_growth": n_growth,
            "pass": bool(nonnormal_pass),
        },
        "switched_counterexample": {
            "spectral_radius_a": radius_a,
            "spectral_radius_b": radius_b,
            "alternating_final_norm_growth": alt_growth,
            "pass": bool(switched_pass),
        },
        "claim_boundary": spec["claim_boundary"],
    }
    arrays = {
        "nonnormal": n_traj,
        "fixed_a": fixed_a,
        "fixed_b": fixed_b,
        "alternating": alternating,
    }
    return report, arrays


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    spec_path = args.spec.resolve()
    output = args.out.resolve()
    if not spec_path.is_file():
        raise FileNotFoundError("SPEC_MISSING")
    if output.exists():
        raise FileExistsError("REFUSING_TO_OVERWRITE_OUTPUT")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    report, arrays = compute(spec)
    if args.dry_run:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if report["status"] != "PASS_E16_NEGATIVE_TESTS":
            raise SystemExit(20)
        return

    figures = output / "figures"
    figures.mkdir(parents=True)
    output.joinpath("counterexamples.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with output.joinpath("trajectories.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case", "step", "x0", "x1", "state_norm"])
        for name, values in arrays.items():
            for step, state in enumerate(values):
                writer.writerow([name, step, state[0], state[1], np.linalg.norm(state)])

    made: list[str] = []
    gamma = np.linspace(0.0, 1.0, 201)
    fig, axis = plt.subplots(figsize=(8.2, 5.0))
    for case in spec["formula_13_cases"]:
        lhs = case["norm_a_plus"] + gamma * case["c_u"]
        axis.plot(gamma, lhs, label=case["id"])
    axis.axhline(1.0, color="red", linestyle="--", label="r_u=1")
    axis.set(xlabel="gamma", ylabel="registered bound expression", title="Equation (13) branch and scalar counterexample")
    axis.grid(alpha=0.25); axis.legend()
    made.extend(save(fig, figures, "e16_formula13_branches"))

    fig, axis = plt.subplots(figsize=(8.2, 5.0))
    norms = np.linalg.norm(arrays["nonnormal"], axis=1)
    axis.semilogy(np.arange(len(norms)), norms, marker="o", markersize=3)
    axis.axhline(norms[0], color="red", linestyle="--", label="initial norm")
    axis.set(xlabel="step", ylabel="state 2-norm", title="Stable spectral radius does not prevent nonnormal transient growth")
    axis.grid(alpha=0.25); axis.legend()
    made.extend(save(fig, figures, "e16_nonnormal_transient"))

    fig, axis = plt.subplots(figsize=(8.2, 5.0))
    for name, label in (("fixed_a", "fixed A"), ("fixed_b", "fixed B"), ("alternating", "alternating A/B")):
        norms = np.linalg.norm(arrays[name], axis=1)
        axis.semilogy(np.arange(len(norms)), norms, label=label)
    axis.set(xlabel="step", ylabel="state 2-norm", title="Individually stable modes do not imply arbitrary-switching stability")
    axis.grid(alpha=0.25); axis.legend()
    made.extend(save(fig, figures, "e16_switched_counterexample"))

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "figures": made,
        "generating_script": relative(Path(__file__)),
        "generating_script_sha256": sha(Path(__file__)),
        "source_files": [{"path": relative(spec_path), "sha256": sha(spec_path)}],
        "claim_boundary": spec["claim_boundary"],
    }
    output.joinpath("figure_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    output.joinpath("README.md").write_text(
        "# E16负向测试\n\n这些反例只排除无效推论，不构成闭环稳定性或递归可行性证明。图需人工视觉QA后才可标PASS。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "output": relative(output), "figures": made}, ensure_ascii=False))
    if report["status"] != "PASS_E16_NEGATIVE_TESTS":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
