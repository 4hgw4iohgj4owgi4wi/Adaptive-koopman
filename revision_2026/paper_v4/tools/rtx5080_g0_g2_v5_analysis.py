"""Registered read-only analysis of the RTX 5080 G0-G2 v5 qualification.

Answers four questions from the saved JSON only (nothing is recomputed):

 1. how much gate margin does G1 actually have, sample by sample;
 2. which G2 object carries the largest CPU/GPU deviation, and how it propagates;
 3. where the remaining end-to-end time sits, i.e. the Amdahl decomposition of the
    3.26x speedup and the floor that survives even an infinitely fast GPU;
 4. what the measured per-solve times imply for the full 2379-cycle route, clearly
    labelled as an extrapolation rather than a result.

Writes to a new analysis directory; never modifies the frozen results or sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FLOOR = 1e-18


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def solver_mean_s(path: Path) -> dict:
    walls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            walls.append(float(json.loads(line)["wall_s"]))
    values = np.asarray(walls)
    return {
        "records": int(values.size),
        "mean_s": float(values.mean()),
        "median_s": float(np.median(values)),
        "p95_s": float(np.percentile(values, 95)),
        "max_s": float(values.max()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paper = Path(__file__).resolve().parents[1]
    protocol_path = args.protocol.resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("scope") != "RTX5080_G0_G2_V5_READ_ONLY_ANALYSIS":
        raise ValueError("SCOPE_MISMATCH")
    for item in protocol["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    output = args.out.resolve()
    if output != (paper / protocol["output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)

    result = paper / protocol["inputs"]["result_directory"]
    p1_solver = paper / protocol["inputs"]["p1_solver_jsonl"]
    g0 = json.loads((result / "g0_environment.json").read_text(encoding="utf-8"))
    g1 = json.loads((result / "g1_physics.json").read_text(encoding="utf-8"))
    g2 = json.loads((result / "g2_fd_qp.json").read_text(encoding="utf-8"))
    qualification = json.loads((result / "qualification.json").read_text(encoding="utf-8"))

    # ---- 1. G1 gate utilisation -------------------------------------------
    kinds = ["rhs", "rk4_2ms", "rollout_20ms"]
    g1_rows = []
    for row in g1["samples"]:
        for kind in kinds:
            value = row["comparisons"][kind]["maximum_normalized_error"]
            g1_rows.append({
                "sample": row["sample"],
                "quantity": kind,
                "maximum_normalized_error": value,
                "gate": 1.0,
                "gate_utilisation_percent": 100.0 * value,
                "exact_zero": value == 0.0,
                "headroom_orders_of_magnitude": float("inf") if value == 0.0 else -np.log10(value),
            })
    g1_worst = max(g1_rows, key=lambda item: item["maximum_normalized_error"])
    g1_zero_count = sum(1 for item in g1_rows if item["exact_zero"])

    # ---- 2. G2 per-field breakdown ----------------------------------------
    g2_fields = []
    for case in g2["cases"]:
        for group, label in (("finite_difference_comparisons", "finite_difference"), ("qp_comparisons", "qp_object")):
            for key, value in case[group].items():
                g2_fields.append({
                    "case": case["case"],
                    "group": label,
                    "field": key,
                    "maximum_absolute_error": value["maximum_absolute_error"],
                    "rms_error": value["rms_error"],
                    "maximum_normalized_error": value["maximum_normalized_error"],
                    "exact_zero": value["maximum_normalized_error"] == 0.0,
                })
    g2_worst = max(g2_fields, key=lambda item: item["maximum_normalized_error"])
    g2_zero_count = sum(1 for item in g2_fields if item["exact_zero"])

    # ---- 3. Amdahl decomposition ------------------------------------------
    amdahl = []
    for case in g2["cases"]:
        timing = case["timing_s"]
        gpu_total = timing["gpu_end_to_end"]
        kernel = timing["gpu_linearization_kernel_total"]
        transfer = timing["gpu_transfer_reconstruct_total"]
        cpu_total = timing["cpu_parallel8_end_to_end"]
        fixed = gpu_total - kernel - transfer
        cpu_linearization = cpu_total - fixed
        calls = timing["gpu_linearization_calls"]
        amdahl.append({
            "case": case["case"],
            "linearization_calls": calls,
            "cpu_total_s": cpu_total,
            "gpu_total_s": gpu_total,
            "gpu_kernel_s": kernel,
            "gpu_transfer_s": transfer,
            "gpu_fixed_cpu_side_s": fixed,
            "gpu_fixed_share_percent": 100.0 * fixed / gpu_total,
            "implied_cpu_linearization_s": cpu_linearization,
            "linearization_stage_speedup": cpu_linearization / kernel,
            "cpu_per_call_s": cpu_linearization / calls,
            "gpu_per_call_s": kernel / calls,
            "amdahl_floor_s": fixed,
            "further_gain_available": gpu_total / fixed,
            "end_to_end_speedup": cpu_total / gpu_total,
        })

    # ---- 4. full-route projection (EXTRAPOLATION) -------------------------
    p1_stats = solver_mean_s(p1_solver)
    speedup = qualification["g2_performance_status"] and float(g2["performance"]["speedup"])
    cycles = int(protocol["inputs"]["full_route_cycles"])
    projected = {
        "label": "EXTRAPOLATION_NOT_A_MEASUREMENT",
        "assumption": "per-cycle solve wall time scales by the measured fixed-sample end-to-end speedup and stays constant over the route",
        "measured_p1_cpu_mean_s_per_cycle": p1_stats["mean_s"],
        "measured_p1_cpu_median_s_per_cycle": p1_stats["median_s"],
        "measured_p1_cpu_p95_s_per_cycle": p1_stats["p95_s"],
        "measured_p1_solver_records": p1_stats["records"],
        "measured_speedup": speedup,
        "projected_gpu_s_per_cycle": p1_stats["mean_s"] / speedup,
        "cycles": cycles,
        "projected_cpu_hours": cycles * p1_stats["mean_s"] / 3600.0,
        "projected_gpu_hours": cycles * (p1_stats["mean_s"] / speedup) / 3600.0,
        "caveats": [
            "the fixed-sample solve does not include the true-plant event-substep integration, the per-cycle reference preview or the diagnostics writing of a closed-loop run",
            "G2 measured a cold single solve per case, not 2379 successive solves with warm starts and active-set history",
            "the projection must not be used to claim full-route real-time behaviour, and G3/G4 remain unauthorised",
        ],
    }

    report = {
        "status": "PASS_READ_ONLY_ANALYSIS_OF_G0_G2_V5",
        "scope": protocol["scope"],
        "source_result_directory": protocol["inputs"]["result_directory"],
        "science_status_analysed": qualification["status"],
        "g0": {
            "device": g0["device_name"],
            "capability": g0["device_capability"],
            "torch": g0["torch"],
            "torch_cuda_build": g0["torch_cuda_build"],
            "float64_test_finite": g0["float64_test_finite"],
            "versions": g0["versions"],
        },
        "g1_gate_utilisation": {
            "gate": 1.0,
            "worst": g1_worst,
            "exact_zero_pairs": g1_zero_count,
            "pairs": len(g1_rows),
            "rows": g1_rows,
        },
        "g2_field_breakdown": {
            "worst": g2_worst,
            "exact_zero_fields": g2_zero_count,
            "fields": len(g2_fields),
            "rows": g2_fields,
        },
        "amdahl": amdahl,
        "full_route_projection": projected,
        "conclusions_allowed": [
            "the GPU float64 batched predictor reproduces the CPU predictor at six fixed samples within a gate that is six orders of magnitude away from being binding",
            "the GPU-built fixed QP is numerically identical to the CPU-built one and yields a first control agreeing to 1e-10 or better",
            "on the two registered fixed samples the GPU path is 3.256x faster end to end and sits inside the original 5 s per-solve budget"
        ],
        "conclusions_forbidden": [
            "any closed-loop, full-route or real-time claim",
            "any claim that the GPU fixes the P1 late tracking divergence",
            "any distributed, communication or Koopman-superiority claim",
            "any claim that the remaining CPU-side cost has already been addressed"
        ],
    }
    (output / "v5_analysis.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- figure ------------------------------------------------------------
    figure, axes = plt.subplots(2, 2, figsize=(14.5, 9.2))

    labels = [f"{item['sample']}/{item['quantity']}" for item in g1_rows]
    values = [max(item["maximum_normalized_error"], FLOOR) for item in g1_rows]
    axes[0, 0].bar(np.arange(len(g1_rows)), values, color="#1f77b4")
    axes[0, 0].axhline(1.0, color="red", linestyle=":", label="frozen gate = 1.0")
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_ylim(FLOOR * 0.5, 100.0)
    axes[0, 0].set(
        xticks=np.arange(len(g1_rows)),
        xticklabels=labels,
        ylabel="maximum normalized error (log)",
        title=f"G1 gate utilisation — worst {g1_worst['sample']}/{g1_worst['quantity']} = {g1_worst['maximum_normalized_error']:.2e}\n"
              f"{g1_zero_count} of {len(g1_rows)} pairs are exactly zero (drawn at the {FLOOR:.0e} floor)",
    )
    axes[0, 0].tick_params(axis="x", labelsize=6.5, rotation=45)
    for tick in axes[0, 0].get_xticklabels():
        tick.set_horizontalalignment("right")
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(axis="y", which="both", alpha=0.25)

    non_zero = [item for item in g2_fields if not item["exact_zero"]]
    names = [f"{item['case']}\n{item['group'][:2]}-{item['field']}" for item in non_zero]
    magnitudes = [item["maximum_normalized_error"] for item in non_zero]
    colors = ["#1f77b4" if item["group"] == "finite_difference" else "#ff7f0e" for item in non_zero]
    axes[0, 1].bar(np.arange(len(non_zero)), magnitudes, color=colors)
    axes[0, 1].axhline(1.0, color="red", linestyle=":", label="frozen gate = 1.0")
    axes[0, 1].set_yscale("log")
    axes[0, 1].set_ylim(1e-13, 10.0)
    axes[0, 1].set(
        xticks=np.arange(len(non_zero)),
        xticklabels=names,
        ylabel="maximum normalized error (log)",
        title=f"G2 deviations that are not exactly zero — worst {g2_worst['case']}/{g2_worst['field']} = {g2_worst['maximum_normalized_error']:.2e}\n"
              f"{g2_zero_count} of {len(g2_fields)} fields are bitwise identical and are omitted",
    )
    axes[0, 1].tick_params(axis="x", labelsize=7, rotation=30)
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(axis="y", which="both", alpha=0.25)

    cases = [item["case"] for item in amdahl]
    positions = np.arange(len(amdahl))
    kernel = [item["gpu_kernel_s"] for item in amdahl]
    transfer = [item["gpu_transfer_s"] for item in amdahl]
    fixed = [item["gpu_fixed_cpu_side_s"] for item in amdahl]
    axes[1, 0].bar(positions - 0.19, [item["cpu_total_s"] for item in amdahl], 0.38, label="CPU parallel8 total", color="#1f77b4")
    axes[1, 0].bar(positions + 0.19, kernel, 0.38, label="GPU linearisation kernel", color="#ff7f0e")
    axes[1, 0].bar(positions + 0.19, transfer, 0.38, bottom=kernel, label="GPU transfer", color="#d62728")
    axes[1, 0].bar(positions + 0.19, fixed, 0.38, bottom=np.asarray(kernel) + np.asarray(transfer), label="CPU-side remainder (QP/OSQP/validation)", color="#7f7f7f")
    for index, item in enumerate(amdahl):
        axes[1, 0].text(index + 0.19, item["gpu_total_s"] + 0.45, f"{item['gpu_total_s']:.2f}s", ha="center", fontsize=8, va="bottom")
        axes[1, 0].text(index - 0.19, item["cpu_total_s"] + 0.45, f"{item['cpu_total_s']:.2f}s", ha="center", fontsize=8, va="bottom")
        axes[1, 0].hlines(item["amdahl_floor_s"], index - 0.42, index + 0.42, color="black", linestyle="--", linewidth=1.2)
        axes[1, 0].annotate(
            f"Amdahl floor {item['amdahl_floor_s']:.2f}s",
            xy=(index + 0.42, item["amdahl_floor_s"]),
            xytext=(index + 0.49, item["amdahl_floor_s"] + 1.1),
            fontsize=7.5,
            arrowprops={"arrowstyle": "-", "linewidth": 0.8, "color": "black"},
        )
    axes[1, 0].axhline(5.0, color="red", linestyle=":", label="original 5 s budget")
    axes[1, 0].set(
        xticks=positions,
        xticklabels=[f"{item['case']}\nstage speedup {item['linearization_stage_speedup']:.2f}x, end-to-end {item['end_to_end_speedup']:.2f}x" for item in amdahl],
        ylabel="end-to-end solve time (s)",
        ylim=(0, 18.5),
        title="Amdahl decomposition of the fixed-sample solve\nup to 2.06x more remains if the GPU kernel were free",
    )
    axes[1, 0].legend(fontsize=7.5, loc="upper center")
    axes[1, 0].grid(axis="y", alpha=0.25)

    bars = axes[1, 1].bar(
        ["CPU parallel8\n(measured, P1 prefix)", "GPU batch FD\n(EXTRAPOLATION)"],
        [projected["projected_cpu_hours"], projected["projected_gpu_hours"]],
        color=["#1f77b4", "#ff7f0e"],
    )
    for bar, value in zip(bars, [projected["projected_cpu_hours"], projected["projected_gpu_hours"]]):
        axes[1, 1].text(bar.get_x() + bar.get_width() / 2, value + 0.12, f"{value:.2f} h", ha="center", fontsize=10)
    axes[1, 1].set(
        ylabel="solve time for 2379 cycles (h)",
        ylim=(0, projected["projected_cpu_hours"] * 1.22),
        title="Full-route projection — NOT a measurement\n"
              f"{projected['measured_p1_cpu_mean_s_per_cycle']:.4f} s/cycle measured -> "
              f"{projected['projected_gpu_s_per_cycle']:.4f} s/cycle projected at {projected['measured_speedup']:.3f}x",
    )
    axes[1, 1].grid(axis="y", alpha=0.25)

    figure.text(
        0.78, 0.015,
        "Assumes a constant per-cycle cost and that the fixed-sample speedup transfers.\n"
        "Excludes true-plant substeps, reference preview and diagnostics overhead.",
        ha="center", fontsize=7.5, color="#8b0000",
    )

    figure.suptitle("RTX 5080 G0-G2 v5: read-only analysis of the saved qualification numbers", fontsize=13)
    figure.tight_layout(rect=(0, 0.055, 1, 0.97))
    figures = []
    for suffix in ("png", "svg"):
        name = f"v5_analysis.{suffix}"
        figure.savefig(output / name, dpi=200 if suffix == "png" else None)
        figures.append(name)
    plt.close(figure)

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": protocol["scope"],
        "figures": figures,
        "source_files": [
            {"path": str(paper / item["path"]), "sha256": item["sha256"]} for item in protocol["identity_files"]
        ] + [{"path": str(protocol_path), "sha256": sha(protocol_path)}],
        "result_files": [
            {"path": "v5_analysis.json", "sha256": sha(output / "v5_analysis.json")}
        ],
        "claim_boundary": "Read-only analysis. No recomputation, no closed loop, no G3/G4, no full-route measurement.",
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "README.md").write_text(
        "# RTX 5080 G0—G2 v5 只读分析\n\n"
        "本目录只读已保存的资格JSON与P1的solver记录，回答四个问题：G1的门裕度分布、G2哪个对象偏差最大、"
        "3.256×加速的Amdahl分解与剩余上限、以及全路线时间的**外推**（明确标为非测量）。\n\n"
        "不重算任何资格数值，不修改冻结结果或源码，不启动闭环。\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(output),
        "g1_worst": [g1_worst["sample"], g1_worst["quantity"], g1_worst["maximum_normalized_error"]],
        "g1_exact_zero_pairs": f"{g1_zero_count}/{len(g1_rows)}",
        "g2_worst": [g2_worst["case"], g2_worst["field"], g2_worst["maximum_normalized_error"]],
        "g2_exact_zero_fields": f"{g2_zero_count}/{len(g2_fields)}",
        "amdahl": [{item["case"]: None, "fixed_share_percent": item["gpu_fixed_share_percent"], "stage_speedup": item["linearization_stage_speedup"], "further_gain": item["further_gain_available"]} for item in amdahl],
        "projection": {"cpu_hours": projected["projected_cpu_hours"], "gpu_hours": projected["projected_gpu_hours"]},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
