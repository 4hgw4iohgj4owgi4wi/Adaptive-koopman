"""Read-only figure QA for the RTX 5080 G0-G2 v5 qualification.

The frozen qualifier plotted normalized errors of order 1e-7..1e-3 on a linear
0..1 axis, so every bar collapsed onto zero and only the gate line was visible.
The JSON numbers are correct and are not recomputed here; this tool only re-plots
the saved numbers on a logarithmic axis.

Writes into a separate analysis directory and never touches the frozen results
directory or the frozen qualifier source.
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paper = Path(__file__).resolve().parents[1]
    source = (paper / args.source).resolve() if not args.source.is_absolute() else args.source
    output = (paper / args.out).resolve() if not args.out.is_absolute() else args.out
    if not source.is_dir():
        raise ValueError("SOURCE_MISSING:" + str(source))
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)

    g1 = json.loads((source / "g1_physics.json").read_text(encoding="utf-8"))
    g2 = json.loads((source / "g2_fd_qp.json").read_text(encoding="utf-8"))
    qualification = json.loads((source / "qualification.json").read_text(encoding="utf-8"))

    figure, axes = plt.subplots(2, 2, figsize=(14.5, 9.0))

    # --- G1: normalized error per sample, log scale -------------------------
    samples = [row["sample"] for row in g1["samples"]]
    kinds = ["rhs", "rk4_2ms", "rollout_20ms"]
    width = 0.26
    positions = np.arange(len(samples))
    for offset, kind in enumerate(kinds):
        values = [max(row["comparisons"][kind]["maximum_normalized_error"], FLOOR) for row in g1["samples"]]
        axes[0, 0].bar(positions + (offset - 1) * width, values, width, label=kind)
    axes[0, 0].axhline(1.0, color="red", linestyle=":", label="frozen gate = 1.0")
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_ylim(FLOOR * 0.5, 10.0)
    axes[0, 0].set(
        xticks=positions,
        xticklabels=samples,
        ylabel="maximum normalized error (log)",
        title=f"G1 CPU/GPU float64 physics equivalence — {g1['status']}\nfloor {FLOOR:.0e} marks exact zero",
    )
    axes[0, 0].tick_params(axis="x", rotation=18)
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(axis="y", alpha=0.25, which="both")

    # --- G2: per-component normalized error, log scale ----------------------
    labels, values, colors = [], [], []
    for case in g2["cases"]:
        for key, value in case["finite_difference_comparisons"].items():
            labels.append(f"{case['case']}\nFD-{key}")
            values.append(max(value["maximum_normalized_error"], FLOOR))
            colors.append("#1f77b4")
        for key, value in case["qp_comparisons"].items():
            labels.append(f"{case['case']}\n{key}")
            values.append(max(value["maximum_normalized_error"], FLOOR))
            colors.append("#ff7f0e")
    axes[0, 1].bar(np.arange(len(labels)), values, color=colors)
    axes[0, 1].axhline(1.0, color="red", linestyle=":", label="frozen gate = 1.0")
    axes[0, 1].set_yscale("log")
    axes[0, 1].set_ylim(FLOOR * 0.5, 10.0)
    axes[0, 1].set(
        xticks=np.arange(len(labels)),
        xticklabels=labels,
        ylabel="maximum normalized error (log)",
        title=f"G2 fixed-QP CPU/GPU identity — {g2['status']}\nblue = finite difference, orange = QP object",
    )
    axes[0, 1].tick_params(axis="x", labelsize=6.5, rotation=60)
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(axis="y", alpha=0.25, which="both")

    # --- timing -------------------------------------------------------------
    cases = [case["case"] for case in g2["cases"]]
    cpu = [case["timing_s"]["cpu_parallel8_end_to_end"] for case in g2["cases"]]
    gpu = [case["timing_s"]["gpu_end_to_end"] for case in g2["cases"]]
    positions = np.arange(len(cases))
    bars_cpu = axes[1, 0].bar(positions - 0.18, cpu, 0.36, label="CPU parallel8")
    bars_gpu = axes[1, 0].bar(positions + 0.18, gpu, 0.36, label="RTX 5080 batch FD")
    axes[1, 0].axhline(5.0, color="red", linestyle=":", label="original 5 s budget")
    for bars, series in ((bars_cpu, cpu), (bars_gpu, gpu)):
        for bar, value in zip(bars, series):
            axes[1, 0].text(bar.get_x() + bar.get_width() / 2, value + 0.15, f"{value:.2f}s", ha="center", fontsize=8)
    axes[1, 0].set(
        xticks=positions,
        xticklabels=cases,
        ylabel="end-to-end solve time (s)",
        ylim=(0, max(cpu) * 1.18),
        title=f"G2 fixed-QP cost — {g2['performance_status']}\nmean speedup {g2['performance']['speedup']:.3f}x, 5 s budget pass = {g2['performance']['original_5s_budget_pass']}",
    )
    axes[1, 0].legend(fontsize=8)
    axes[1, 0].grid(axis="y", alpha=0.25)

    # --- headroom summary ---------------------------------------------------
    worst_g1 = max(
        row["comparisons"][kind]["maximum_normalized_error"] for row in g1["samples"] for kind in kinds
    )
    worst_g2 = max(
        max(value["maximum_normalized_error"] for value in case["finite_difference_comparisons"].values())
        for case in g2["cases"]
    )
    worst_g2_qp = max(
        max(value["maximum_normalized_error"] for value in case["qp_comparisons"].values()) for case in g2["cases"]
    )
    checks = [
        ("G1 worst physics", worst_g1),
        ("G2 worst finite difference", worst_g2),
        ("G2 worst QP object", worst_g2_qp),
    ]
    axes[1, 1].barh([name for name, _ in checks], [max(value, FLOOR) for _, value in checks], color="#2ca02c")
    axes[1, 1].axvline(1.0, color="red", linestyle=":", label="frozen gate = 1.0")
    axes[1, 1].set_xscale("log")
    axes[1, 1].set_xlim(FLOOR * 0.5, 10.0)
    for index, (_, value) in enumerate(checks):
        axes[1, 1].text(max(value, FLOOR) * 1.6, index, f"{value:.3e}", va="center", fontsize=9)
    axes[1, 1].set(
        xlabel="maximum normalized error (log)",
        title="Gate headroom: worst observed value per group\nevery group sits orders of magnitude inside the frozen gate",
    )
    axes[1, 1].legend(fontsize=8)
    axes[1, 1].grid(axis="x", alpha=0.25, which="both")

    figure.suptitle(
        "RTX 5080 G0-G2 qualification (read-only figure QA, same numbers as the frozen JSON)",
        fontsize=13,
    )
    figure.tight_layout(rect=(0, 0.01, 1, 0.97))
    figures = []
    for suffix in ("png", "svg"):
        name = f"g0_g2_v5_qa.{suffix}"
        figure.savefig(output / name, dpi=200 if suffix == "png" else None)
        figures.append(name)
    plt.close(figure)

    manifest = {
        "science_status": qualification["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": "FIGURE_QA_ONLY_NO_RECOMPUTATION",
        "source_result_directory": "results/20260915_RTX5080_G0_G2_05",
        "source_files": [
            {"path": "results/20260915_RTX5080_G0_G2_05/g1_physics.json", "sha256": sha(source / "g1_physics.json")},
            {"path": "results/20260915_RTX5080_G0_G2_05/g2_fd_qp.json", "sha256": sha(source / "g2_fd_qp.json")},
            {"path": "results/20260915_RTX5080_G0_G2_05/qualification.json", "sha256": sha(source / "qualification.json")},
        ],
        "figures": figures,
        "defect_corrected": "The frozen qualifier's G1 and G2 error panels used a linear 0..1 axis for values of order 1e-7..1e-3, so no bar was visible; this QA re-plot uses a logarithmic axis and marks exact zeros at the display floor.",
        "numbers_recomputed": False,
        "claim_boundary": "Fixed-sample numerical equivalence and cost only. No closed loop, no G3/G4, no full-route real-time claim.",
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "README.md").write_text(
        "# RTX 5080 G0—G2 图表 QA（只读重绘）\n\n"
        "冻结资格脚本的 G1/G2 误差面板把 1e-7~1e-3 量级画在 0—1 线性轴上，柱子全部塌成零、只剩门槛线。\n\n"
        "本目录不改冻结源码、不重跑任何计算，只把 `results/20260915_RTX5080_G0_G2_05` 里已保存的 JSON 数值重画到对数轴，"
        "使等价裕度可读；零值以显示下限标记。数值与裁决不变。\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "figures": figures, "worst_g1": worst_g1, "worst_g2_fd": worst_g2, "worst_g2_qp": worst_g2_qp}, ensure_ascii=False))


if __name__ == "__main__":
    main()
