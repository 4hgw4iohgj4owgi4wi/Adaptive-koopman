"""Figure QA for the G3 verdict panel: a FAIL must be visible.

The frozen comparator drew verdicts as bars of height 1 or 0, so every FAIL became a
zero-length bar and the panel appeared entirely green.  This read-only tool re-plots
the same saved verdicts as a categorical matrix and does not touch the frozen
comparator, the runs or any other pinned file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paper = Path(__file__).resolve().parents[1]
    source = (paper / args.source) if not args.source.is_absolute() else args.source
    output = (paper / args.out) if not args.out.is_absolute() else args.out
    report_path = source / "g3_restart_equivalence.json"
    if not report_path.is_file():
        raise ValueError("SOURCE_REPORT_MISSING")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)
    report = json.loads(report_path.read_text(encoding="utf-8"))

    windows = [item["window"] for item in report["windows"]]
    verdict_names = list(report["windows"][0]["verdicts"].keys())
    matrix = np.zeros((len(verdict_names), len(windows)))
    for column, item in enumerate(report["windows"]):
        for row, name in enumerate(verdict_names):
            matrix[row, column] = 1.0 if item["verdicts"][name] else 0.0

    figure, axes = plt.subplots(1, 2, figsize=(15.0, 6.2), gridspec_kw={"width_ratios": [1.25, 1.0]})

    axes[0].imshow(matrix, cmap="RdYlGn", vmin=0.0, vmax=1.0, aspect="auto")
    axes[0].set(
        xticks=np.arange(len(windows)),
        xticklabels=[f"{name}\npass={item['pass']}" for name, item in zip(windows, report["windows"])],
        yticks=np.arange(len(verdict_names)),
        yticklabels=[name.replace("_", " ") for name in verdict_names],
        title=f"G3 frozen verdicts — overall {report['status']}\nevery cell labelled; red cells are genuine failures",
    )
    for row in range(len(verdict_names)):
        for column in range(len(windows)):
            value = matrix[row, column]
            axes[0].text(column, row, "PASS" if value else "FAIL", ha="center", va="center",
                         color="white" if value == 0 else "black", fontweight="bold", fontsize=9)
    axes[0].legend(handles=[Patch(color="#a6d96a", label="PASS"), Patch(color="#d73027", label="FAIL")],
                   loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=9)

    positions = np.arange(len(windows))
    width = 0.38
    cpu = []
    gpu = []
    floor = 1e-17
    for item in report["windows"]:
        cpu.append(max(item["backends"]["cpu"]["comparison"]["position_max_abs_m"], floor))
        gpu.append(max(item["backends"]["gpu"]["comparison"]["position_max_abs_m"], floor))
    axes[1].bar(positions - width / 2, cpu, width, label="CPU replay vs saved (restart test)", color="#1f77b4")
    axes[1].bar(positions + width / 2, gpu, width, label="GPU vs saved", color="#ff7f0e")
    axes[1].axhline(report["gates"]["restart_position_atol_m"], color="#1f77b4", linestyle=":", label="restart gate 1e-06 m")
    axes[1].axhline(report["gates"]["window_position_atol_m"], color="#ff7f0e", linestyle="--", label="window gate 1e-02 m")
    axes[1].set_yscale("log")
    axes[1].set(xticks=positions, xticklabels=windows, ylabel="worst position deviation (m, log)",
                title="Checkpoint fidelity versus backend equivalence\nCPU replay tests the first; GPU tests the second")
    for index, (cpu_value, gpu_value) in enumerate(zip(cpu, gpu)):
        axes[1].text(index - width / 2, cpu_value * 1.6, f"{cpu_value:.1e}", ha="center", fontsize=7.5)
        axes[1].text(index + width / 2, gpu_value * 1.6, f"{gpu_value:.1e}", ha="center", fontsize=7.5)
    axes[1].legend(fontsize=8)
    axes[1].grid(which="both", alpha=0.25)

    figure.suptitle("G3 figure QA (read-only re-plot of the saved verdicts and deviations)", fontsize=12.5)
    figure.tight_layout(rect=(0, 0.02, 1, 0.94))
    figures = []
    for suffix in ("png", "svg"):
        name = f"g3_verdicts_qa.{suffix}"
        figure.savefig(output / name, dpi=200 if suffix == "png" else None)
        figures.append(name)
    plt.close(figure)

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": "FIGURE_QA_ONLY_NO_RECOMPUTATION",
        "source_report": str(source.relative_to(paper)).replace("\\", "/"),
        "source_sha256": sha(report_path),
        "figures": figures,
        "defect_corrected": "the frozen comparator encoded verdicts as bar heights, so every FAIL collapsed to a zero-length bar and the panel looked entirely green; this re-plot labels every cell explicitly",
        "numbers_recomputed": False,
        "claim_boundary": "Presentation only. No run, gate, tolerance or verdict changed.",
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "README.md").write_text(
        "# G3 图表 QA（只读重绘裁决面板）\n\n"
        "冻结比较器把裁决画成高度为1/0的柱，导致每个FAIL都变成零高度柱、面板看起来全绿。\n\n"
        "本目录只读同一份已保存JSON，把24个裁决单元逐格标注PASS/FAIL，并并排给出"
        "“CPU重放（检查点保真）”与“GPU（后端等价）”两组偏差，说明两者是不同问题。\n\n"
        "数值与裁决未变。\n",
        encoding="utf-8",
    )
    failed = [(name, item["window"]) for name in verdict_names for item in report["windows"] if not item["verdicts"][name]]
    print(json.dumps({"output": str(output), "overall": report["status"], "failed_cells": failed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
