"""Read-only fixed-QP replay probe for the R5 strict solver chain (stage S2).

Task book R5_STRICT_CHAIN_EXECUTION_20260917.md section S2 requires, before any of the three
full-route runs may start, a probe at the ticks where the old R5-N1 actually violated the
15 degree requested-steering bound.  A three-tick smoke test from the initial condition cannot
observe the first violation (tick 834) and is explicitly not a substitute.

The probe replays, for each registered tick:

  * the controller estimate that the old run assembled (estimates.npz),
  * the reference distance, beta and previous control that the old run actually passed to
    make_preview, and
  * the preview inputs they imply,

then solves the same QP twice: once with the historical 2e-4 settings, which must reproduce the
saved first control, and once with the strict candidate, whose requested-steering overshoot must
fall inside the separately registered acceptance tolerance.

Time-base alignment is the subtle part.  r5_runner appends its row after it has already updated
previous_u and beta, while distance_before is captured before the update.  Therefore tick k's
inputs are: distance from row k, but beta and previous_u from row k-1.  The reproduction check is
what proves the alignment: if it were wrong, the old-settings solve could not match the saved
control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

PAPER = Path(__file__).resolve().parents[1]
SOURCE_RUN = "results/20260916_R5_N1_GPU01"
STEERING_LIMIT_RAD = np.deg2rad(15.0)
# Registered in the task book: 15 material ticks plus tick 1652 which exceeds the limit only by
# 5.55e-17 rad and is float-equality dust rather than a material violation.
VIOLATING_TICKS = [834, 839, 853, 930, 963, 1112, 1180, 1194, 1298, 1301, 1370, 1384, 1524, 1538, 1549]
DUST_TICKS = [1652]
OLD_SETTINGS = {"eps_abs": 2e-4, "eps_rel": 2e-4, "scaled_termination": False, "max_iter": 4000, "polishing": True}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), {str(name): pos for pos, name in enumerate(data["columns"])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if sha(args.protocol.resolve()) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("scope") != "R5_STRICT_QP_PROBE":
        raise ValueError("SCOPE_MISMATCH")
    for item in protocol["identity_files"]:
        path = PAPER / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    output = args.out.resolve()
    if output != (PAPER / protocol["output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")

    strict_settings = dict(protocol["strict_candidate_solver_settings"])
    acceptance = float(protocol["acceptance_tolerances"]["requested_steering_acceptance_tolerance_rad"])
    reproduce_tolerance = float(protocol["probe_conditions"]["old_settings_reproduction_max_abs_rad"])

    sys.path.insert(0, str(PAPER / "src"))
    from paper_v4_core.controllers.physical_tracking_pilot import PilotConfig, solve
    from paper_v4_core.e01_100m import params
    from paper_v4_core.gpu_port.ipc_backend import CudaIpcFiniteDifferenceBackend, install_cuda_linearization
    from paper_v4_core.pilot_runner import make_preview

    run = PAPER / SOURCE_RUN
    raw, raw_index = load(run / "raw.npz")
    estimates, estimate_index = load(run / "estimates.npz")
    solver_records = {}
    for line in (run / "solver.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            solver_records[int(record["tick"])] = record
    model = params("P0")

    def reconstructed_inputs(tick: int):
        """Rebuild exactly what the old run passed to make_preview at this tick."""
        estimate = estimates[tick, [estimate_index[f"estimate_x{i}"] for i in range(30)]
                             + [estimate_index[f"estimate_delta{i}"] for i in range(4)]]
        distance = float(raw[tick, raw_index["interval_reference_distance_start_m"]])
        if tick == 0:
            beta = np.zeros(4)
            previous_u = np.zeros(8)
        else:
            beta = raw[tick - 1, [raw_index[f"reference_beta{i}"] for i in range(4)]].copy()
            previous_u = raw[tick - 1, [raw_index[f"previous_u{i}"] for i in range(8)]].copy()
        u_nom, refs, _ = make_preview(distance, beta, model, previous_u, 20)
        return estimate, distance, beta, previous_u, u_nom, refs

    cases = []
    output.mkdir(parents=True)
    with CudaIpcFiniteDifferenceBackend(model) as backend:
        environment = backend.environment()
        backend.warm(np.r_[np.zeros(30), np.zeros(4)], np.zeros(8))
        with install_cuda_linearization(backend):
            for tick in VIOLATING_TICKS + DUST_TICKS:
                estimate, distance, beta, previous_u, u_nom, refs = reconstructed_inputs(tick)
                saved = np.asarray(solver_records[tick]["first_control"], float)

                started = time.perf_counter()
                old = solve(estimate, u_nom, refs, model, PilotConfig(horizon=20, lambda_internal=2.0,
                                                                      frozen_dynamics_jacobian=False,
                                                                      finite_difference_scale=1.0, **OLD_SETTINGS))
                old_wall = time.perf_counter() - started
                old_first = np.asarray(old["control"][0], float)
                reproduction = float(np.abs(old_first - saved).max())

                started = time.perf_counter()
                strict = solve(estimate, u_nom, refs, model, PilotConfig(horizon=20, lambda_internal=2.0,
                                                                         frozen_dynamics_jacobian=False,
                                                                         finite_difference_scale=1.0, **strict_settings))
                strict_wall = time.perf_counter() - started
                strict_first = np.asarray(strict["control"][0], float)

                # first_control is interleaved [a1,d1,a2,d2,...]: only the odd indices are
                # steering.  The first version took max over the whole vector, which compared
                # accelerations (bounded by 2.0) against the 15 degree steering bound and
                # reported a fictitious 1.03 rad overshoot.
                saved_steering = saved[1::2]
                strict_steering = strict_first[1::2]
                saved_overshoot = float(np.abs(saved_steering).max() - STEERING_LIMIT_RAD)
                strict_overshoot = float(np.abs(strict_steering).max() - STEERING_LIMIT_RAD)
                cases.append({
                    "tick": int(tick),
                    "reference_distance_m": distance,
                    "is_float_dust_case": tick in DUST_TICKS,
                    "saved_max_request_rad": float(np.abs(saved_steering).max()),
                    "saved_max_accel": float(np.abs(saved[0::2]).max()),
                    "saved_overshoot_rad": saved_overshoot,
                    "old_settings": {
                        "status": old["status"], "solver_status": old["solver_status"],
                        "iterations": int(old["iterations"]),
                        "primal_residual": float(old["primal_residual"]),
                        "dual_residual": float(old["dual_residual"]),
                        "wall_s": old_wall,
                        "reproduction_max_abs_rad": reproduction,
                        "reproduces_saved_first_control": reproduction <= reproduce_tolerance,
                        "validation": old["validation"].get("status"),
                    },
                    "strict_candidate": {
                        "settings": strict_settings,
                        "status": strict["status"], "solver_status": strict["solver_status"],
                        "iterations": int(strict["iterations"]),
                        "primal_residual": float(strict["primal_residual"]),
                        "dual_residual": float(strict["dual_residual"]),
                        "wall_s": strict_wall,
                        "max_request_rad": float(np.abs(strict_steering).max()),
                        "max_accel": float(np.abs(strict_first[0::2]).max()),
                        "overshoot_rad": strict_overshoot,
                        "within_registered_acceptance": strict_overshoot <= acceptance,
                        "validation": strict["validation"].get("status"),
                        "effective_settings": strict.get("solver_settings_effective"),
                    },
                })
        worker_environment = environment

    material = [case for case in cases if not case["is_float_dust_case"]]
    checks = []
    checks.append({"item": len(checks) + 1, "check": "old_settings_reproduce_the_saved_first_control",
                   "pass": all(case["old_settings"]["reproduces_saved_first_control"] for case in cases),
                   "detail": {"max_reproduction_error_rad": max(case["old_settings"]["reproduction_max_abs_rad"] for case in cases),
                              "tolerance_rad": reproduce_tolerance,
                              "bitwise_cases": sum(1 for case in cases if case["old_settings"]["reproduction_max_abs_rad"] == 0.0),
                              "cases": len(cases)}})
    checks.append({"item": len(checks) + 1, "check": "strict_candidate_solves_every_case",
                   "pass": all(case["strict_candidate"]["status"] == "PASS" for case in cases),
                   "detail": {str(c["tick"]): c["strict_candidate"]["status"] for c in cases if c["strict_candidate"]["status"] != "PASS"}})
    checks.append({"item": len(checks) + 1, "check": "strict_candidate_passes_nonlinear_validation",
                   "pass": all(case["strict_candidate"]["validation"] == "PASS" for case in cases),
                   "detail": {str(c["tick"]): c["strict_candidate"]["validation"] for c in cases if c["strict_candidate"]["validation"] != "PASS"}})
    checks.append({"item": len(checks) + 1, "check": "no_solved_inaccurate_or_iteration_exhaustion",
                   "pass": all(case["strict_candidate"]["solver_status"] == "solved" and case["strict_candidate"]["iterations"] < 4000 for case in cases),
                   "detail": {str(c["tick"]): {"status": c["strict_candidate"]["solver_status"], "iterations": c["strict_candidate"]["iterations"]}
                              for c in cases if c["strict_candidate"]["solver_status"] != "solved" or c["strict_candidate"]["iterations"] >= 4000}})
    checks.append({"item": len(checks) + 1, "check": "no_non_finite_residuals",
                   "pass": all(np.isfinite([case["strict_candidate"]["primal_residual"], case["strict_candidate"]["dual_residual"]]).all() for case in cases),
                   "detail": "all strict-candidate residuals finite"})
    checks.append({"item": len(checks) + 1, "check": "material_violating_ticks_within_registered_acceptance",
                   "pass": all(case["strict_candidate"]["within_registered_acceptance"] for case in material),
                   "detail": {"acceptance_rad": acceptance,
                              "worst_overshoot_rad": max(case["strict_candidate"]["overshoot_rad"] for case in material),
                              "cases": len(material)}})
    worst_wall = max(case["strict_candidate"]["wall_s"] for case in cases)
    checks.append({"item": len(checks) + 1, "check": "solve_wall_time_not_anomalous",
                   "pass": worst_wall < 60.0, "detail": {"max_wall_s": worst_wall}})
    passed = all(check["pass"] for check in checks)

    report = {
        "status": "PASS_STRICT_QP_PROBE" if passed else "FAIL_STRICT_QP_PROBE",
        "scope": protocol["scope"],
        "source_run": SOURCE_RUN,
        "why_this_probe": protocol["why_this_probe"],
        "time_base_alignment": protocol["time_base_alignment"],
        "old_settings": OLD_SETTINGS,
        "strict_candidate_solver_settings": strict_settings,
        "acceptance_tolerances": protocol["acceptance_tolerances"],
        "environment": {k: worker_environment.get(k) for k in ("device_name",)},
        "checks": checks,
        "cases": cases,
        "what_this_releases": ("A PASS releases the three strict full-route runs (S3/S4/S5). The strict candidate is validated only at the "
                               "registered violating ticks; it is not a proof for the whole route, which is what the three runs then establish."),
        "claim_boundary": "Read-only replay at 16 registered ticks. It changes no run, no gate and no threshold.",
    }
    (output / "qp_probe.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- figure: overshoot, iterations, wall time -------------------------------------
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_dir = output / "figures"
    figure_dir.mkdir()
    ticks = [case["tick"] for case in cases]
    positions = np.arange(len(ticks))
    figure, axes = plt.subplots(1, 3, figsize=(18.0, 6.4))
    axes[0].bar(positions - 0.2, [np.rad2deg(case["saved_overshoot_rad"]) for case in cases], 0.4,
                label="old 2e-4 settings (as run)", color="#d62728")
    axes[0].bar(positions + 0.2, [np.rad2deg(case["strict_candidate"]["overshoot_rad"]) for case in cases], 0.4,
                label="strict candidate", color="#1f77b4")
    axes[0].axhline(np.rad2deg(acceptance), color="black", linestyle="--", label=f"registered acceptance {acceptance:g} rad")
    axes[0].set_xticks(positions)
    axes[0].set_xticklabels([str(t) + ("*" if t in DUST_TICKS else "") for t in ticks], rotation=90, fontsize=7.5)
    axes[0].set(xlabel="tick", ylabel="requested-steering overshoot (deg)",
                title="Requested-steering overshoot above 15 deg\n(* float-dust case, not a material violation)")
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.25)

    axes[1].bar(positions - 0.2, [case["old_settings"]["iterations"] for case in cases], 0.4, label="old settings", color="#d62728")
    axes[1].bar(positions + 0.2, [case["strict_candidate"]["iterations"] for case in cases], 0.4, label="strict candidate", color="#1f77b4")
    axes[1].axhline(4000, color="black", linestyle="--", label="max_iter")
    axes[1].set_xticks(positions)
    axes[1].set_xticklabels(ticks, rotation=90, fontsize=7.5)
    axes[1].set(xlabel="tick", ylabel="QP iterations", title="Iterations — no exhaustion")
    axes[1].legend(fontsize=8)
    axes[1].grid(axis="y", alpha=0.25)

    axes[2].bar(positions - 0.2, [case["old_settings"]["wall_s"] for case in cases], 0.4, label="old settings", color="#d62728")
    axes[2].bar(positions + 0.2, [case["strict_candidate"]["wall_s"] for case in cases], 0.4, label="strict candidate", color="#1f77b4")
    axes[2].set_xticks(positions)
    axes[2].set_xticklabels(ticks, rotation=90, fontsize=7.5)
    axes[2].set(xlabel="tick", ylabel="solve wall clock (s)", title="Solve cost — strict settings are not slower by construction")
    axes[2].legend(fontsize=8)
    axes[2].grid(axis="y", alpha=0.25)

    figure.suptitle(f"R5 strict fixed-QP probe — {report['status']}", fontsize=13)
    figure.tight_layout(rect=(0, 0.01, 1, 0.93))
    names = []
    for suffix in ("png", "svg"):
        name = f"r5_strict_qp_probe.{suffix}"
        figure.savefig(figure_dir / name, dpi=300 if suffix == "png" else None)
        names.append(name)
    plt.close(figure)

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": protocol["scope"],
        "analysis_question": "Do the historical settings reproduce the saved first control at the registered violating ticks, and does the strict candidate bring the requested-steering overshoot inside the registered acceptance tolerance?",
        "figures": [f"figures/{name}" for name in names],
        "fields": {"overshoot": "requested steering above the 15 degree bound, old versus strict",
                   "iterations": "QP iterations per solve", "cost": "solve wall clock"},
        "units": "deg, count, s",
        "statistics_convention": "deterministic replay of 16 registered ticks; no sampling",
        "generating_script": "tools/r5_strict_qp_probe.py",
        "generating_script_sha256": sha(Path(__file__)),
        "caption": (f"Fixed-QP probe at {len(VIOLATING_TICKS)} material violating ticks plus one float-dust tick: "
                    f"worst strict-candidate overshoot {max(case['strict_candidate']['overshoot_rad'] for case in cases):.3e} rad "
                    f"against a registered acceptance of {acceptance:g} rad."),
        "claim_boundary": report["claim_boundary"],
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (figure_dir / "README.md").write_text(
        "# R5 严格固定QP探针图\n\n"
        "三面板：①**请求转角越界**（旧 `2e-4` vs 严格候选，并标登记验收容差）；②**QP迭代数**（未耗尽）；③**求解耗时**。\n\n"
        "带 `*` 的 tick 1652 只以 `5.55e-17 rad` 超限，属**浮点等值尘埃**，不计入 15 个实质越界 tick。\n\n"
        "**对齐口径**：`distance` 取第 k 行，`beta` 与 `previous_u` 取第 **k−1** 行——因为 `r5_runner` 追加行时这两者已更新为下一 tick 的值。"
        "该对齐由\"旧设置必须复现已保存首控制\"这一检查自证。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"],
                      "max_reproduction_error_rad": max(case["old_settings"]["reproduction_max_abs_rad"] for case in cases),
                      "worst_strict_overshoot_rad": max(case["strict_candidate"]["overshoot_rad"] for case in cases),
                      "acceptance_rad": acceptance,
                      "checks_passed": sum(1 for c in checks if c["pass"]), "checks_total": len(checks),
                      "output": str(output)}, ensure_ascii=False))
    if not passed:
        raise SystemExit(20)


if __name__ == "__main__":
    main()
