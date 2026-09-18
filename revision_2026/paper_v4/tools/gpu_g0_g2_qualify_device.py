"""Registered G0-G2 qualification for one explicitly named CUDA device.

The protocol supplies the exact torch device name and a human-readable label.
The historical RTX 5080 qualification tool remains unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_archive(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), {str(value): index for index, value in enumerate(data["columns"])}


def error_stats(reference, candidate, gate: dict) -> dict:
    reference = np.asarray(reference, float)
    candidate = np.asarray(candidate, float)
    if reference.shape != candidate.shape:
        return {"shape_match": False, "pass": False}
    finite = np.isfinite(reference) & np.isfinite(candidate)
    same_infinite = np.array_equal(np.isposinf(reference), np.isposinf(candidate)) and np.array_equal(np.isneginf(reference), np.isneginf(candidate))
    if not finite.any():
        return {"shape_match": True, "same_infinite_mask": same_infinite, "pass": same_infinite}
    error = np.abs(candidate[finite] - reference[finite])
    scale = float(gate["atol"]) + float(gate["rtol"]) * np.abs(reference[finite])
    ratio = error / np.maximum(scale, np.finfo(float).tiny)
    result = {
        "shape_match": True,
        "same_infinite_mask": same_infinite,
        "maximum_absolute_error": float(np.max(error)),
        "rms_error": float(np.sqrt(np.mean(np.square(error)))),
        "maximum_normalized_error": float(np.max(ratio)),
        "worst_flat_index": int(np.flatnonzero(finite)[int(np.argmax(ratio))]),
    }
    result["pass"] = bool(same_infinite and result["maximum_normalized_error"] <= float(gate["maximum_normalized_error"]))
    return result


def validate_protocol(protocol_path: Path, expected_sha: str, paper: Path) -> dict:
    if sha(protocol_path) != expected_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("scope") != "GPU_DEVICE_G0_G2_ONLY_NO_CLOSED_LOOP":
        raise ValueError("SCOPE_MISMATCH")
    for item in protocol["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    return protocol


def select_samples(raw, columns, sub, subcolumns, model):
    from paper_v4_core.plant.four_vehicle_common import connector_kinematics

    request = raw[:, [columns[f"request_delta{i}"] for i in range(4)]]
    endpoint_force = raw[:, [columns[f"point_force_norm{i}"] for i in range(4)]]
    curve = np.flatnonzero(np.max(np.abs(np.rad2deg(request)), axis=1) >= 1.0)
    force_time = float(sub[int(np.argmax(np.max(np.column_stack([sub[:, subcolumns[f"force_peak{i}"]] for i in range(4)]), axis=1))), subcolumns["time_s"]])
    force_index = int(np.argmin(np.abs(raw[:, columns["time_s"]] - force_time)))
    gap_scores = []
    for row in raw:
        gaps = connector_kinematics(row[[columns[f"x{i}"] for i in range(30)]], model)["signed_gap_m"]
        gap_scores.append(float(np.min(np.minimum(np.abs(gaps), np.abs(gaps - model.connector.smoothing_width_m)))))
    indices = {
        "straight": 0,
        "curve_entry": int(curve[0]) if len(curve) else 0,
        "force_peak": force_index if np.max(endpoint_force) >= 0.0 else int(np.argmax(np.max(endpoint_force, axis=1))),
        "steering_limit": int(np.argmax(np.max(np.abs(request), axis=1))),
        "near_gap_boundary": int(np.argmin(gap_scores)),
        "late_prefix": len(raw) - 1,
    }
    return indices


def save_figure(fig, output: Path, stem: str) -> list[str]:
    fig.tight_layout()
    names = [f"{stem}.png", f"{stem}.svg"]
    fig.savefig(output / names[0], dpi=220)
    fig.savefig(output / names[1])
    plt.close(fig)
    return names


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    paper = Path(__file__).resolve().parents[1]
    protocol_path = args.protocol.resolve()
    protocol = validate_protocol(protocol_path, args.protocol_sha, paper)
    device_label = str(protocol.get("device_label", protocol["g0"]["required_device_name"]))
    output = args.out.resolve()
    if output != (paper / protocol["output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)

    sys.path.insert(0, str(paper / "src"))
    import osqp
    from paper_v4_core.controllers import physical_tracking_pilot as controller
    from paper_v4_core.controllers.parallel_fd_backend import ParallelFiniteDifferenceBackend, install_parallel_linearization
    from paper_v4_core.e01_100m import params
    from paper_v4_core.gpu_port.ipc_backend import CudaIpcFiniteDifferenceBackend, install_cuda_linearization
    from paper_v4_core.plant.four_vehicle_common import initialize_state, rk4_step, system_derivative
    from paper_v4_core.diagnostics.post_r3_r4_runner import make_preview

    model = params("P1")
    gpu_backend = CudaIpcFiniteDifferenceBackend(model)
    gpu_environment = gpu_backend.environment()
    if not gpu_environment["cuda_available"] or gpu_environment["device_name"] != protocol["g0"]["required_device_name"]:
        raise RuntimeError("G0_DEVICE_IDENTITY_FAIL")
    g0 = {
        "status": "PASS" if gpu_environment["float64_test_finite"] else "FAIL",
        "host": platform.node(),
        "python": platform.python_version(),
        "torch": gpu_environment["torch"],
        "torch_cuda_build": gpu_environment["torch_cuda_build"],
        "cuda_available": gpu_environment["cuda_available"],
        "device_name": gpu_environment["device_name"],
        "device_capability": gpu_environment["device_capability"],
        "device_total_memory_bytes": gpu_environment["device_total_memory_bytes"],
        "float64_test_result": gpu_environment["float64_test_result"],
        "float64_test_finite": gpu_environment["float64_test_finite"],
        "peak_allocated_bytes": gpu_environment["peak_allocated_bytes"],
        "process_isolation": "persistent single CUDA worker; CPU parent retains SciPy/OSQP",
        "worker_module_audit_at_environment": gpu_environment.get("worker_module_audit", {}),
        "versions": {"numpy": np.__version__, "scipy": scipy.__version__, "osqp": osqp.__version__},
    }
    (output / "g0_environment.json").write_text(json.dumps(g0, indent=2), encoding="utf-8")
    fig, axis = plt.subplots(figsize=(8.5, 4.8))
    axis.axis("off")
    axis.text(0.02, 0.95, f"G0 {device_label} environment qualification", fontsize=16, va="top")
    lines = [f"{key}: {value}" for key, value in g0.items() if key != "versions"] + [f"{key}: {value}" for key, value in g0["versions"].items()]
    axis.text(0.02, 0.84, "\n".join(lines), family="monospace", fontsize=10, va="top")
    g0_figures = save_figure(fig, output, "g0_environment")

    partial = paper / protocol["inputs"]["partial_run"]
    raw, c = load_archive(partial / "raw.npz")
    sub, s = load_archive(partial / "substeps.npz")
    sample_indices = select_samples(raw, c, sub, s, model)
    g1_rows = []
    for label, index in sample_indices.items():
        row = raw[index]
        state = row[[c[f"x{i}"] for i in range(30)]]
        actual_delta = row[[c[f"actual_delta{i}"] for i in range(4)]]
        request_delta = row[[c[f"request_delta{i}"] for i in range(4)]]
        acceleration = row[[c[f"request_accel{i}"] for i in range(4)]]
        applied = np.column_stack((acceleration, actual_delta))
        z = np.r_[state, actual_delta]
        request = np.column_stack((acceleration, request_delta)).reshape(8)
        cpu_rhs = system_derivative(state, applied, model, "R3", load_transfer_enabled=True)[0]
        gpu_rhs = gpu_backend.rhs(state[None, :], applied[None, :, :])[0]
        cpu_rk4 = rk4_step(state, applied, 0.002, model, "R3", load_transfer_enabled=True)
        gpu_rk4 = gpu_backend.rk4(state[None, :], applied[None, :, :], 0.002)[0]
        cpu_rollout = controller.rollout_step(z, request, model)
        gpu_rollout = gpu_backend.rollout(z[None, :], request[None, :])[0]
        comparisons = {
            "rhs": error_stats(cpu_rhs, gpu_rhs, protocol["gates"]["g1_rhs"]),
            "rk4_2ms": error_stats(cpu_rk4, gpu_rk4, protocol["gates"]["g1_rk4"]),
            "rollout_20ms": error_stats(cpu_rollout, gpu_rollout, protocol["gates"]["g1_rollout"]),
        }
        g1_rows.append({"sample": label, "raw_index": index, "time_s": float(row[c["time_s"]]), "comparisons": comparisons, "pass": all(value["pass"] for value in comparisons.values())})
    g1 = {"status": "PASS" if all(row["pass"] for row in g1_rows) else "FAIL", "samples": g1_rows}
    (output / "g1_physics.json").write_text(json.dumps(g1, indent=2), encoding="utf-8")
    labels, rhs_ratio, rk4_ratio, rollout_ratio = [], [], [], []
    for row in g1_rows:
        labels.append(row["sample"])
        rhs_ratio.append(row["comparisons"]["rhs"]["maximum_normalized_error"])
        rk4_ratio.append(row["comparisons"]["rk4_2ms"]["maximum_normalized_error"])
        rollout_ratio.append(row["comparisons"]["rollout_20ms"]["maximum_normalized_error"])
    x = np.arange(len(labels)); width = 0.25
    fig, axis = plt.subplots(figsize=(10.5, 5.2))
    axis.bar(x - width, rhs_ratio, width, label="RHS")
    axis.bar(x, rk4_ratio, width, label="2 ms RK4")
    axis.bar(x + width, rollout_ratio, width, label="20 ms rollout")
    axis.axhline(1.0, color="red", linestyle=":", label="Frozen normalized gate")
    axis.set(xticks=x, xticklabels=labels, ylabel="Maximum normalized error", title="G1 CPU/GPU float64 physics equivalence")
    axis.tick_params(axis="x", rotation=20); axis.grid(axis="y", alpha=0.2); axis.legend()
    g1_figures = save_figure(fig, output, "g1_physics_equivalence")

    initial_state = initialize_state(model, 2.0)
    cases = {
        "initial": initial_state.copy(),
        "force_bearing": initial_state.copy(),
    }
    cases["force_bearing"][0] += 0.03
    config = controller.PilotConfig(horizon=20, lambda_internal=2.0, frozen_dynamics_jacobian=False, finite_difference_scale=1.0)
    case_inputs = {}
    for name, state in cases.items():
        z = np.r_[state, np.zeros(4)]
        u_nom, refs, _ = make_preview(0.0, np.zeros(4), model, np.zeros(8), 20)
        case_inputs[name] = (z, u_nom, refs)

    cpu_results, cpu_fd = {}, {}
    with ParallelFiniteDifferenceBackend(8) as cpu_backend:
        cpu_warmup = cpu_backend.warm(case_inputs["initial"][0], case_inputs["initial"][1][0], model)
        for name, (z, u_nom, refs) in case_inputs.items():
            cpu_fd[name] = cpu_backend.linearize(z, u_nom[0], model, 1.0)
            with install_parallel_linearization(cpu_backend):
                cpu_results[name] = controller.solve(z, u_nom, refs, model, config)

    gpu_warmup = gpu_backend.warm(case_inputs["initial"][0], case_inputs["initial"][1][0])
    gpu_results, gpu_fd = {}, {}
    gpu_call_ranges = {}
    for name, (z, u_nom, refs) in case_inputs.items():
        gpu_fd[name] = gpu_backend.linearize(z, u_nom[0], model, 1.0)
        first_call = len(gpu_backend.calls)
        with install_cuda_linearization(gpu_backend):
            gpu_results[name] = controller.solve(z, u_nom, refs, model, config)
        gpu_call_ranges[name] = gpu_backend.calls[first_call:]
    gpu_backend.close()

    g2_cases = []
    qp_keys = ("P", "q", "A", "l", "u", "u_nom")
    for name in cases:
        cpu_result, gpu_result = cpu_results[name], gpu_results[name]
        fd = {
            "f0": error_stats(cpu_fd[name][0], gpu_fd[name][0], protocol["gates"]["g2_f0"]),
            "A": error_stats(cpu_fd[name][1], gpu_fd[name][1], protocol["gates"]["g2_jacobian"]),
            "B": error_stats(cpu_fd[name][2], gpu_fd[name][2], protocol["gates"]["g2_jacobian"]),
        }
        qp = {}
        for key in qp_keys:
            gate = protocol["gates"]["g2_qp_bounds"] if key in {"l", "u"} else protocol["gates"]["g2_qp_matrix"]
            qp[key] = error_stats(cpu_result["problem"][key], gpu_result["problem"][key], gate)
        control_error = gpu_result["control"][0] - cpu_result["control"][0]
        control_checks = {
            "maximum_acceleration_absolute_error_mps2": float(np.max(np.abs(control_error[0::2]))),
            "maximum_steering_absolute_error_rad": float(np.max(np.abs(control_error[1::2]))),
        }
        control_checks["pass"] = bool(
            control_checks["maximum_acceleration_absolute_error_mps2"] <= protocol["gates"]["first_control"]["acceleration_atol_mps2"]
            and control_checks["maximum_steering_absolute_error_rad"] <= protocol["gates"]["first_control"]["steering_atol_rad"]
        )
        call_timing = gpu_call_ranges[name]
        case_pass = bool(
            cpu_result["status"] == "PASS"
            and gpu_result["status"] == "PASS"
            and gpu_result["validation"]["status"] == "PASS"
            and all(item["pass"] for item in fd.values())
            and all(item["pass"] for item in qp.values())
            and control_checks["pass"]
        )
        g2_cases.append({
            "case": name,
            "cpu_status": cpu_result["status"],
            "gpu_status": gpu_result["status"],
            "gpu_cpu_nonlinear_validation": gpu_result["validation"],
            "finite_difference_comparisons": fd,
            "qp_comparisons": qp,
            "first_control": {"cpu": cpu_result["control"][0].tolist(), "gpu": gpu_result["control"][0].tolist(), **control_checks},
            "timing_s": {
                "cpu_parallel8_end_to_end": float(cpu_result["wall_s"]),
                "gpu_end_to_end": float(gpu_result["wall_s"]),
                "gpu_linearization_kernel_total": float(sum(item["kernel_s"] for item in call_timing)),
                "gpu_transfer_reconstruct_total": float(sum(item["device_to_host_and_reconstruct_s"] for item in call_timing)),
                "gpu_linearization_calls": len(call_timing),
            },
            "pass": case_pass,
        })
    gpu_times = [row["timing_s"]["gpu_end_to_end"] for row in g2_cases]
    cpu_times = [row["timing_s"]["cpu_parallel8_end_to_end"] for row in g2_cases]
    performance = {
        "cpu_parallel8_mean_s": float(np.mean(cpu_times)),
        "gpu_mean_s": float(np.mean(gpu_times)),
        "speedup": float(np.mean(cpu_times) / np.mean(gpu_times)),
        "original_5s_budget_pass": bool(max(gpu_times) <= 5.0),
        "faster_than_cpu_parallel8": bool(np.mean(gpu_times) < np.mean(cpu_times)),
    }
    g2 = {
        "status": "PASS" if all(row["pass"] for row in g2_cases) else "FAIL",
        "performance_status": "PASS_PERFORMANCE" if performance["faster_than_cpu_parallel8"] else "FAIL_NO_END_TO_END_BENEFIT",
        "cpu_pool_warmup_s": float(cpu_warmup),
        "gpu_batch_warmup_s": float(gpu_warmup),
        "cases": g2_cases,
        "performance": performance,
    }
    (output / "g2_fd_qp.json").write_text(json.dumps(g2, indent=2), encoding="utf-8")
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
    positions = np.arange(len(g2_cases))
    axes[0].bar(positions - 0.18, cpu_times, 0.36, label="CPU parallel8")
    axes[0].bar(positions + 0.18, gpu_times, 0.36, label=f"{device_label} batch FD")
    axes[0].axhline(5.0, color="red", linestyle=":", label="Original 5 s budget")
    axes[0].set(xticks=positions, xticklabels=[row["case"] for row in g2_cases], ylabel="End-to-end solve time (s)", title="G2 fixed-QP cost")
    axes[0].legend(); axes[0].grid(axis="y", alpha=0.2)
    qp_labels, qp_ratios = [], []
    for row in g2_cases:
        for key, value in row["finite_difference_comparisons"].items():
            qp_labels.append(f"{row['case']}:FD-{key}")
            qp_ratios.append(value.get("maximum_normalized_error", 0.0))
        for key, value in row["qp_comparisons"].items():
            qp_labels.append(f"{row['case']}:{key}")
            qp_ratios.append(value.get("maximum_normalized_error", 0.0))
    axes[1].bar(np.arange(len(qp_labels)), qp_ratios)
    axes[1].axhline(1.0, color="red", linestyle=":", label="Frozen normalized gate")
    axes[1].set(xticks=np.arange(len(qp_labels)), xticklabels=qp_labels, ylabel="Maximum normalized error", title="CPU/GPU QP identity")
    axes[1].tick_params(axis="x", rotation=60, labelsize=7); axes[1].legend(); axes[1].grid(axis="y", alpha=0.2)
    g2_figures = save_figure(fig, output, "g2_qp_performance")

    overall = {
        "status": "PASS_G0_G2_GPU_QUALIFIED" if g0["status"] == g1["status"] == g2["status"] == "PASS" else "FAIL_G0_G2_STOP",
        "scope": protocol["scope"],
        "g0_status": g0["status"],
        "g1_status": g1["status"],
        "g2_numerical_status": g2["status"],
        "g2_performance_status": g2["performance_status"],
        "worker_boundary": {
            "clean_at_environment": gpu_environment.get("worker_module_audit", {}).get("worker_boundary_clean"),
            "clean_after_linearize": gpu_backend.worker_purity.get("worker_boundary_clean"),
            "imported_after_startup_at_environment": gpu_environment.get("worker_module_audit", {}).get("imported_after_startup"),
            "imported_after_startup_after_linearize": gpu_backend.worker_purity.get("imported_after_startup"),
            "detail_after_linearize": gpu_backend.worker_purity,
            "interpretation": "clean=True supports the registered NumPy-in-pickle root cause and its fix; clean=False with PASS falsifies that candidate, and clean=False with failure keeps it open.",
        },
        "closed_loop_authorized": False,
        "p1_interrupted_run_reused_or_resumed": False,
        "next_action": "STOP_NO_G3_G4; separate authorization and protocol required",
        "protocol_sha256": sha(protocol_path),
    }
    (output / "qualification.json").write_text(json.dumps(overall, indent=2), encoding="utf-8")
    source_paths = [paper / item["path"] for item in protocol["identity_files"]] + [protocol_path]
    manifest = {
        "science_status": overall["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": protocol["scope"],
        "figures": g0_figures + g1_figures + g2_figures,
        "source_files": [{"path": str(path), "sha256": sha(path)} for path in source_paths],
        "result_files": [{"path": name, "sha256": sha(output / name)} for name in ("g0_environment.json", "g1_physics.json", "g2_fd_qp.json", "qualification.json")],
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "README.md").write_text(
        f"# {device_label} G0—G2资格\n\n仅验证GPU环境、六类固定物理样本、固定QP数值一致性与端到端成本。真实植物、OSQP和非线性复核仍为CPU；没有续跑P1，也没有启动G3/G4闭环。\n",
        encoding="utf-8",
    )
    print(json.dumps(overall, ensure_ascii=False))
    if overall["status"] != "PASS_G0_G2_GPU_QUALIFIED":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
