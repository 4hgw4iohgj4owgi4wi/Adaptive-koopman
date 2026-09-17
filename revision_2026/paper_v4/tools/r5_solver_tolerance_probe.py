"""Replay the 15 materially violating R5-N1 QPs under legacy and strict settings."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER / "src"))

from paper_v4_core.controllers import physical_tracking_pilot as controller
from paper_v4_core.controllers.physical_tracking_pilot import PilotConfig
from paper_v4_core.e01_100m import LIMIT, params
from paper_v4_core.gpu_port.ipc_backend import CudaIpcFiniteDifferenceBackend, install_cuda_linearization
from paper_v4_core.pilot_runner import make_preview


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_npz(path: Path) -> tuple[np.ndarray, dict[str, int]]:
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), {str(name): pos for pos, name in enumerate(data["columns"])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    protocol_path = args.protocol.resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("scope") != "R5_STRICT_SOLVER_PROBE":
        raise ValueError("SCOPE_MISMATCH")
    for item in [*protocol["source_files"], *protocol["identity_files"]]:
        path = PAPER / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    output = args.out.resolve()
    if output != (PAPER / protocol["output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")

    source = PAPER / protocol["source_run"]
    raw, raw_index = load_npz(source / "raw.npz")
    estimates, estimate_index = load_npz(source / "estimates.npz")
    solver_records = {
        int(item["tick"]): item
        for item in (json.loads(line) for line in (source / "solver.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())
    }
    model = params("P0")
    legacy_config = PilotConfig(horizon=20, lambda_internal=2.0, frozen_dynamics_jacobian=False,
                                finite_difference_scale=1.0, **protocol["legacy_solver_settings"])
    strict_config = PilotConfig(horizon=20, lambda_internal=2.0, frozen_dynamics_jacobian=False,
                                finite_difference_scale=1.0, **protocol["candidate_solver_settings"])
    acceptance = float(protocol["acceptance_tolerances"]["requested_steering_acceptance_tolerance_rad"])
    records = []
    started = time.perf_counter()

    with CudaIpcFiniteDifferenceBackend(model) as backend:
        environment = backend.environment()
        first_tick = int(protocol["ticks"][0])
        z_first = estimates[first_tick, [estimate_index[f"estimate_x{i}"] for i in range(30)]
                                      + [estimate_index[f"estimate_delta{i}"] for i in range(4)]]
        warmup_s = backend.warm(z_first, np.zeros(8))
        with install_cuda_linearization(backend):
            for tick_value in protocol["ticks"]:
                tick = int(tick_value)
                estimate = estimates[tick, [estimate_index[f"estimate_x{i}"] for i in range(30)]
                                              + [estimate_index[f"estimate_delta{i}"] for i in range(4)]]
                if tick == 0:
                    distance, beta, previous_u = 0.0, np.zeros(4), np.zeros(8)
                else:
                    distance = float(raw[tick, raw_index["interval_reference_distance_start_m"]])
                    beta = raw[tick - 1, [raw_index[f"reference_beta{i}"] for i in range(4)]]
                    previous_u = raw[tick - 1, [raw_index[f"previous_u{i}"] for i in range(8)]]
                u_nom, refs, _ = make_preview(distance, beta, model, previous_u, 20)
                legacy = controller.solve(estimate, u_nom, refs, model, legacy_config)
                strict = controller.solve(estimate, u_nom, refs, model, strict_config)
                stored = np.asarray(solver_records[tick]["first_control"], float)
                legacy_first = np.asarray(legacy["control"][0], float)
                strict_first = np.asarray(strict["control"][0], float)
                strict_request = strict_first.reshape(4, 2)[:, 1]
                records.append({
                    "tick": tick,
                    "time_s": float(solver_records[tick]["time_s"]),
                    "reference_distance_m": distance,
                    "legacy_status": legacy["status"],
                    "legacy_solver_status": legacy["solver_status"],
                    "legacy_validation_status": legacy["validation"]["status"],
                    "legacy_iterations": legacy["iterations"],
                    "legacy_wall_s": legacy["wall_s"],
                    "legacy_first_control_max_abs_difference": float(np.max(np.abs(legacy_first - stored))),
                    "strict_status": strict["status"],
                    "strict_solver_status": strict["solver_status"],
                    "strict_validation_status": strict["validation"]["status"],
                    "strict_iterations": strict["iterations"],
                    "strict_wall_s": strict["wall_s"],
                    "strict_requested_steering_max_rad": float(np.max(np.abs(strict_request))),
                    "strict_requested_steering_overshoot_rad": float(np.max(np.abs(strict_request)) - LIMIT),
                })

    gates = protocol["gates"]
    checks = [
        {"check": "legacy_first_control_reproduced", "pass": all(r["legacy_first_control_max_abs_difference"] <= float(gates["legacy_first_control_max_abs_difference"]) for r in records)},
        {"check": "legacy_solver_and_validation_pass", "pass": all(r["legacy_status"] == "PASS" and r["legacy_solver_status"] == "solved" and r["legacy_validation_status"] == "PASS" for r in records)},
        {"check": "strict_solver_and_validation_pass", "pass": all(r["strict_status"] == "PASS" and r["strict_solver_status"] == gates["strict_solver_status"] and r["strict_validation_status"] == gates["strict_validation_status"] for r in records)},
        {"check": "strict_request_overshoot_within_registered_tolerance", "pass": all(r["strict_requested_steering_overshoot_rad"] <= acceptance for r in records)},
    ]
    status = "PASS_R5_STRICT_SOLVER_PROBE" if all(item["pass"] for item in checks) else "FAIL_R5_STRICT_SOLVER_PROBE"
    output.mkdir(parents=True)
    figures = output / "figures"
    figures.mkdir()

    ticks = np.asarray([r["tick"] for r in records])
    overshoot = np.asarray([r["strict_requested_steering_overshoot_rad"] for r in records])
    legacy_diff = np.asarray([r["legacy_first_control_max_abs_difference"] for r in records])
    strict_iterations = np.asarray([r["strict_iterations"] for r in records])
    strict_wall = np.asarray([r["strict_wall_s"] for r in records])
    fig, axes = plt.subplots(2, 2, figsize=(14.2, 8.5))
    axes[0, 0].plot(ticks, overshoot, "o-")
    axes[0, 0].axhline(acceptance, color="red", linestyle=":", label=f"acceptance {acceptance:.1e} rad")
    axes[0, 0].axhline(0.0, color="black", linewidth=0.8)
    axes[0, 0].set(title="Strict requested-steering overshoot", xlabel="historical tick", ylabel="overshoot (rad)")
    axes[0, 0].legend(fontsize=8); axes[0, 0].grid(alpha=0.25)
    axes[0, 1].semilogy(ticks, np.maximum(legacy_diff, 1e-18), "o-")
    axes[0, 1].axhline(float(gates["legacy_first_control_max_abs_difference"]), color="red", linestyle=":")
    axes[0, 1].set(title="Legacy first-control reproduction", xlabel="historical tick", ylabel="max abs difference")
    axes[0, 1].grid(alpha=0.25)
    axes[1, 0].bar(ticks.astype(str), strict_iterations)
    axes[1, 0].tick_params(axis="x", rotation=60)
    axes[1, 0].set(title="Strict OSQP iterations", xlabel="historical tick", ylabel="iterations")
    axes[1, 0].grid(axis="y", alpha=0.25)
    axes[1, 1].bar(ticks.astype(str), strict_wall)
    axes[1, 1].tick_params(axis="x", rotation=60)
    axes[1, 1].set(title="Strict solve wall clock", xlabel="historical tick", ylabel="seconds")
    axes[1, 1].grid(axis="y", alpha=0.25)
    fig.suptitle(f"R5 strict solver fixed-QP probe — {status}")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    names = []
    for suffix in ("png", "svg"):
        name = f"r5_strict_solver_probe.{suffix}"
        fig.savefig(figures / name, dpi=300 if suffix == "png" else None)
        names.append(name)
    plt.close(fig)

    report = {
        "status": status,
        "protocol": rel(protocol_path),
        "protocol_sha256": args.protocol_sha.lower(),
        "source_run": protocol["source_run"],
        "ticks": protocol["ticks"],
        "legacy_solver_settings": protocol["legacy_solver_settings"],
        "candidate_solver_settings": protocol["candidate_solver_settings"],
        "acceptance_tolerances": protocol["acceptance_tolerances"],
        "environment": environment,
        "warmup_s": warmup_s,
        "wall_s": time.perf_counter() - started,
        "checks": checks,
        "records": records,
        "claim_boundary": "Fixed-QP numerical probe on 15 historical N1 violation ticks; no plant trajectory is advanced and no full-route result is claimed.",
    }
    (output / "probe.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "science_status": status,
        "figure_status": "PENDING_VISUAL_QA",
        "figures": [f"figures/{name}" for name in names],
        "generating_script": "tools/r5_solver_tolerance_probe.py",
        "generating_script_sha256": sha(Path(__file__)),
        "analysis_question": "Does the strict OSQP candidate remove the observed request-box violations while reproducing the legacy fixed QPs?",
        "caption": report["claim_boundary"],
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (figures / "README.md").write_text(
        f"# R5严格求解器固定QP探针\n\n科学状态：`{status}`。图表视觉状态待人工复核。\n\n{report['claim_boundary']}\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "output": str(output), "checks": checks}, ensure_ascii=False))
    if status != "PASS_R5_STRICT_SOLVER_PROBE":
        raise SystemExit(20)


def rel(path: Path) -> str:
    return str(path.relative_to(PAPER)).replace("\\", "/")


if __name__ == "__main__":
    main()
