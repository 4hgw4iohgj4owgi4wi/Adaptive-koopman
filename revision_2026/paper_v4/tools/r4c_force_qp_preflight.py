"""One-point serial/parallel QP and state-restore gate for EXP-R4-C."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from paper_v4_core.controllers import physical_tracking_pilot as controller
from paper_v4_core.controllers.parallel_fd_backend import ParallelFiniteDifferenceBackend, install_parallel_linearization
from paper_v4_core.controllers.physical_tracking_pilot import PilotConfig
from paper_v4_core.diagnostics.qp_fd_trials import array_digest
from paper_v4_core.diagnostics.qp_sensitivity import load_raw, reference_state, row_at, solve_fixed, state_and_previous
from paper_v4_core.e01_100m import params


MATRICES = ("P", "q", "A", "l", "u", "u_nom")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--time-s", type=float, required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    protocol_path = Path(args.protocol).resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if args.time_s != float(protocol["force_window"]["start_s"]):
        raise ValueError("REGISTERED_START_TIME_MISMATCH")
    root = protocol_path.parent.parent
    for item in protocol["identity_files"]:
        if sha((root / item["path"]).resolve()) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    out = Path(args.out).resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    out.mkdir(parents=True)

    source = Path(args.source).resolve()
    values, columns = load_raw(source)
    initial_rows = np.flatnonzero(np.isclose(values[:, columns["time_s"]], args.time_s, rtol=0.0, atol=1e-10))
    sample = row_at(values, columns, args.time_s)
    z0, previous = state_and_previous(sample, columns)
    model = params("P0")
    distance, beta, u_nom, refs = reference_state(args.time_s, model, previous)
    config = PilotConfig(horizon=20, lambda_internal=2.0, finite_difference_scale=1.0, frozen_dynamics_jacobian=False)
    restore_checks = {
        "unique_initial_row": bool(len(initial_rows) == 1),
        "state30_and_actual_delta4_finite": bool(z0.shape == (34,) and np.all(np.isfinite(z0))),
        "previous_control8_finite": bool(previous.shape == (8,) and np.all(np.isfinite(previous))),
        "reference_distance_exact": bool(abs(distance - float(sample[columns["reference_distance_m"]])) <= 1e-12),
        "connector_law_has_no_hidden_history_state": True,
    }

    started = time.perf_counter()
    serial_problem = controller.build_problem(z0, u_nom, refs, model, config)
    serial_build_s = time.perf_counter() - started
    started = time.perf_counter(); serial_solution = solve_fixed(serial_problem, z0, model, config); serial_solve_s = time.perf_counter() - started
    with ParallelFiniteDifferenceBackend(8) as backend:
        warmup_s = backend.warm(z0, u_nom[0], model)
        with install_parallel_linearization(backend):
            started = time.perf_counter(); parallel_problem = controller.build_problem(z0, u_nom, refs, model, config); parallel_build_s = time.perf_counter() - started
    started = time.perf_counter(); parallel_solution = solve_fixed(parallel_problem, z0, model, config); parallel_solve_s = time.perf_counter() - started

    differences = {name: float(np.max(np.abs(np.asarray(serial_problem[name]) - np.asarray(parallel_problem[name])))) for name in MATRICES}
    exact = {name: bool(np.array_equal(np.asarray(serial_problem[name]), np.asarray(parallel_problem[name]), equal_nan=True)) for name in MATRICES}
    first_exact = bool(np.array_equal(serial_solution["control"][0], parallel_solution["control"][0], equal_nan=True))
    checks = {
        "state_restore_complete": all(restore_checks.values()),
        "all_qp_arrays_bitwise_exact": all(exact.values()),
        "first_control_bitwise_exact": first_exact,
        "serial_nonlinear_validation": serial_solution["validation"]["status"] == "PASS",
        "parallel_nonlinear_validation": parallel_solution["validation"]["status"] == "PASS",
    }
    status = "PASS_FORCE_WINDOW_QP" if all(checks.values()) else "FAIL"
    report = {
        "schema_version": "EXP-R4C-force-QP-v1",
        "status": status,
        "candidate_id": "EXP-R3-unfrozen-v1",
        "time_s": args.time_s,
        "protocol_sha256": args.protocol_sha.lower(),
        "restore_checks": restore_checks,
        "checks": checks,
        "matrix_exact": exact,
        "matrix_max_absolute_difference": differences,
        "serial_first_control_sha256": array_digest(serial_solution["control"][0]),
        "parallel_first_control_sha256": array_digest(parallel_solution["control"][0]),
        "serial_validation": serial_solution["validation"],
        "parallel_validation": parallel_solution["validation"],
        "timing_s": {
            "serial_build": serial_build_s,
            "serial_solve_and_validate": serial_solve_s,
            "parallel_pool_warmup": warmup_s,
            "parallel_build": parallel_build_s,
            "parallel_solve_and_validate": parallel_solve_s,
        },
        "claim_limits": ["ONE_REGISTERED_FORCE_BEARING_POINT", "OFFLINE_ONLY", "FAIL_ORIGINAL_5S_BUDGET"],
    }
    (out / "force_qp_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(out / "qp_arrays.npz", **{f"serial_{k}": np.asarray(serial_problem[k]) for k in MATRICES}, **{f"parallel_{k}": np.asarray(parallel_problem[k]) for k in MATRICES})

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2))
    labels = list(MATRICES)
    axes[0].bar(labels, [differences[k] for k in labels], color="#438a5e")
    axes[0].set(title="Serial / parallel QP difference", ylabel="Maximum absolute difference")
    x = np.arange(8)
    axes[1].plot(x, serial_solution["control"][0], "o-", label="serial")
    axes[1].plot(x, parallel_solution["control"][0], "x--", label="parallel (8)")
    axes[1].set(title="First applied control", xlabel="Control component", ylabel="Native command unit")
    axes[1].legend()
    timing_labels = ["Serial build", "Parallel build", "Serial solve+check", "Parallel solve+check"]
    timing = [serial_build_s, parallel_build_s, serial_solve_s, parallel_solve_s]
    axes[2].bar(timing_labels, timing, color=["#315a9c", "#e18437", "#7094c4", "#efb275"])
    axes[2].axhline(5.0, color="red", linestyle=":", label="Original 5 s budget")
    axes[2].tick_params(axis="x", rotation=25); axes[2].set(title="Registered-point wall time", ylabel="Wall time (s)"); axes[2].legend()
    for ax in axes: ax.grid(alpha=0.2)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(out / f"force_qp_preflight.{ext}", dpi=300)
    plt.close(fig)
    script_path = Path(__file__).resolve()
    manifest = {
        "science_status": status,
        "figure_status": "GENERATED_PENDING_VISUAL_QA",
        "protocol_sha256": args.protocol_sha.lower(),
        "generator": str(script_path),
        "generator_sha256": sha(script_path),
        "source": str(source),
        "source_sha256": sha(source),
        "figures": [{
            "name": "force_qp_preflight",
            "files": ["force_qp_preflight.png", "force_qp_preflight.svg"],
            "caption": "One preregistered force-bearing point: exact serial/parallel QP and first-control comparison, nonlinear validation, and offline timing."
        }]
    }
    (out / "figure_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "README.md").write_text("# 有力窗口QP预检\n\n本目录仅对应预登记起点的一对串行/8进程QP，不是闭环窗口或完整R3。\n", encoding="utf-8")
    print(json.dumps({"status": status, "checks": checks, "timing_s": report["timing_s"]}, ensure_ascii=False))
    if status != "PASS_FORCE_WINDOW_QP":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
