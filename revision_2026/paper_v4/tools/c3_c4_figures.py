"""Read-only re-plots for C3 (data-fitted axes) and the C4 coverage figure.

C3's original figure scales every panel to the registered limit, so the measured values —
which sit three orders of magnitude below it — collapse into a narrow band at the bottom
and most of each panel is empty.  The registered limit is therefore moved out of the axis
range and drawn as an explicit off-scale annotation, exactly like the broken force axis
adopted on 2026-09-17 for the per-run figures.

C4's E01 evidence matrix is an audit class, so task-book section 25.4 requires a coverage
figure; no dynamics curve is invented for it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PAPER = Path(__file__).resolve().parents[1]
C3_REPORT = PAPER / "analysis/20260917_C3_ACTUATOR_DIAGNOSTIC_01/actuator_discretization.json"
C4_MATRIX = PAPER / "analysis/20260917_C4_E01_EVIDENCE_MATRIX_02/e01_evidence_matrix.json"
C4_GATE = PAPER / "analysis/20260917_C4_E01_EVIDENCE_MATRIX_02/plant_gate.json"
WINDOWS = ["straight_acceleration", "steering_onset", "reverse_switch"]
PAIR_ORDER = ["2ms_to_1ms", "1ms_to_0.5ms"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def c3_replot() -> None:
    report = json.loads(C3_REPORT.read_text(encoding="utf-8"))
    target = PAPER / "analysis/20260917_C3_ACTUATOR_DIAGNOSTIC_02"
    figure_dir = target / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)

    panels = [
        ("peak_max_relative", 100.0, "peak difference (%)", report["thresholds"]["peak_relative"] * 100.0, "%.3e"),
        ("impulse_vector_max_relative", 100.0, "impulse-vector difference (%)",
         report["thresholds"]["impulse_vector_relative"] * 100.0, "%.3e"),
        ("terminal_payload_position_m", 1000.0, "terminal position (mm)",
         report["thresholds"]["terminal_position_m"] * 1000.0, "%.3e"),
        ("terminal_payload_heading_deg", 1.0, "terminal heading (deg)",
         report["thresholds"]["terminal_heading_deg"], "%.3e"),
    ]
    figure, axes = plt.subplots(2, 2, figsize=(13.5, 9.0))
    colours = {"straight_acceleration": "#1f77b4", "steering_onset": "#ff7f0e", "reverse_switch": "#2ca02c"}
    for axis, (key, scale, ylabel, limit, fmt) in zip(axes.ravel(), panels):
        peak = 0.0
        for window in WINDOWS:
            rows = [row for row in report["pairs"] if row["window"] == window]
            rows = sorted(rows, key=lambda row: PAIR_ORDER.index(row["pair"]))
            values = [scale * row[key] for row in rows]
            peak = max(peak, max(values))
            axis.plot([row["pair"] for row in rows], values, marker="o", color=colours[window], label=window)
            for row, value in zip(rows, values):
                axis.annotate(fmt % value, (row["pair"], value), textcoords="offset points",
                              xytext=(0, 5), ha="center", fontsize=7.0)
        headroom = 1.45 * peak if peak > 0 else 1.0
        axis.set_ylim(0.0, headroom)
        axis.annotate(f"registered limit {limit:g} is {limit / peak if peak > 0 else float('inf'):.0f}x "
                      f"above this panel's scale",
                      xy=(0.02, 0.93), xycoords="axes fraction", fontsize=8.0, color="#8b0000")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
    for axis in axes.ravel():
        axis.set_xlabel("pair (2ms\u21921ms is diagnostic; 1ms\u21920.5ms is the decisive gate)")
    figure.suptitle("C3 actuator-update-interval diagnostic — axes fitted to the measured values, "
                    "registered limits off-scale", fontsize=12.0)
    figure.tight_layout(rect=(0, 0.01, 1, 0.94))
    names = []
    for suffix in ("png", "svg"):
        name = f"actuator_discretization_datafitted.{suffix}"
        figure.savefig(figure_dir / name, dpi=300 if suffix == "png" else None)
        names.append(name)
    plt.close(figure)

    decisive = [row for row in report["pairs"] if row["registered_gate_applies"]]
    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": "C3 actuator discretization, data-fitted re-plot",
        "analysis_question": "Do the three windows stay inside the registered convergence gates across actuator update intervals?",
        "figures": [f"figures/{name}" for name in names],
        "fields": {"pairs": "2ms->1ms diagnostic and 1ms->0.5ms decisive gate per window",
                   "metrics": "peak force, impulse vector, terminal payload position and heading"},
        "units": "%, mm, deg",
        "statistics_convention": "deterministic frozen-command replays; three windows are coverage points, not samples",
        "generating_script": "tools/c3_c4_figures.py",
        "generating_script_sha256": sha(Path(__file__)),
        "source_files": [{"path": "analysis/20260917_C3_ACTUATOR_DIAGNOSTIC_01/actuator_discretization.json",
                          "sha256": sha(C3_REPORT)}],
        "why_replotted": ("The original figure scaled every panel to the registered limit, which is three orders of "
                          "magnitude above the measured values, so the data collapsed into a narrow band and most of "
                          "each panel was empty. This is a presentation-only re-plot: no datum, threshold, window or "
                          "gate is changed, and the registered limits are stated explicitly in each panel."),
        "caption": (f"C3 frozen-command actuator diagnostic: all {len(decisive)} decisive 1 ms to 0.5 ms windows pass "
                    f"(peak {max(row['peak_max_relative'] for row in decisive) * 100:.3e} %, "
                    f"impulse {max(row['impulse_vector_max_relative'] for row in decisive) * 100:.3e} %, "
                    f"position {max(row['terminal_payload_position_m'] for row in decisive) * 1000:.3e} mm, "
                    f"heading {max(row['terminal_payload_heading_deg'] for row in decisive):.3e} deg)."),
        "claim_boundary": ("Numerical actuator-discretization diagnostic only. It does not establish tracking quality, "
                           "real-time behaviour, or any method-level advantage."),
    }
    (target / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (figure_dir / "README.md").write_text(
        "# C3 执行器离散诊断图（只读重绘）\n\n"
        "原图把四个面板的 y 轴都拉到登记阈值（2%／2%／1mm／0.01°），而实测值比它低**三个数量级**，"
        "导致数据挤成贴底一条、面板大部分是空白。本图**把轴拟合到实测值**，并把登记的限值降级为"
        "**离轴标注**（写明“registered limit X is N× above this panel’s scale”）。\n\n"
        "**纯呈现重绘**：不改任何数据、阈值、窗口或门；每个数值都标在点上。\n\n"
        "**结论**：三个窗的**决定性门（1ms→0.5ms）全部通过**；`steering_onset` 与 `reverse_switch` 的"
        "步长敏感度比直线段高约三个数量级（转向变化时执行器离散才起作用）。\n",
        encoding="utf-8",
    )
    print("C3 re-plot:", names)


def c4_coverage() -> None:
    matrix = json.loads(C4_MATRIX.read_text(encoding="utf-8"))
    gate = json.loads(C4_GATE.read_text(encoding="utf-8"))
    target = PAPER / "analysis/20260917_C4_E01_EVIDENCE_MATRIX_02"
    figure_dir = target / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)

    items = matrix["items"]
    labels, required, covered, failed = [], [], [], []
    for item in items:
        step = item["e01_step"]
        labels.append(f"step {step}")
        required.append(item["required_trajectories"])
        if step == "2a":
            covered.append(sum(1 for entry in item["evidence"] if entry.get("passing")))
        else:
            covered.append(0)
        failed.append(sum(1 for entry in item["evidence"] if entry.get("status") == "FAIL"))

    figure, axes = plt.subplots(1, 2, figsize=(15.0, 7.6))
    positions = np.arange(len(labels))
    axes[0].bar(positions - 0.2, required, 0.4, label="registered requirement", color="#c7c7c7")
    axes[0].bar(positions + 0.2, covered, 0.4, label="passing evidence", color="#2ca02c")
    for index, (req, cov) in enumerate(zip(required, covered)):
        if req:
            axes[0].annotate(f"{cov}/{req}", (index, max(req, cov) + 0.15), ha="center", fontsize=8.5)
    axes[0].set(xticks=positions, xticklabels=labels, ylabel="trajectories",
                title="E01 registered requirement versus passing evidence")
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.25)

    axes[1].axis("off")
    lines = [
        "C4 E01 evidence matrix — plant gate",
        "",
        f"registered requirement        : {matrix['required_trajectories_total']} trajectories (27 + 6)",
        f"passing evidence              : {matrix['trajectories_covered']}  (100 m step diagnostic only)",
        f"outstanding                   : {matrix['trajectories_outstanding']}",
        f"failed trajectories retained  : {matrix['failed_retained'] if 'failed_retained' in matrix else len(matrix['failed_trajectories_retained'])}",
        f"plant gate                    : {gate['status']}",
        f"independent review            : {gate['independent_review']}",
        "",
        "outstanding, frozen before execution:",
    ]
    for action in matrix["outstanding_actions"]:
        lines.append("  - " + action)
    lines += [
        "",
        "Rules applied (task book section 6):",
        "  the 33-item plan is not reduced by subtracting recent runs",
        "  old input generators are not mixed with the new controller",
        "  failed trajectories stay FAIL",
        "  100M05 covers only its own 100 m sub-gate",
        "  no overall E01-complete verdict is invented",
        "",
        "Coverage figure only: no dynamics curve is drawn for an",
        "audit class (section 25.4).",
    ]
    axes[1].text(0.0, 1.0, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9.0,
                 transform=axes[1].transAxes)

    figure.suptitle(f"E01 evidence coverage — plant gate {gate['status']}", fontsize=13)
    figure.tight_layout(rect=(0, 0.01, 1, 0.94))
    names = []
    for suffix in ("png", "svg"):
        name = f"e01_evidence_coverage.{suffix}"
        figure.savefig(figure_dir / name, dpi=300 if suffix == "png" else None)
        names.append(name)
    plt.close(figure)

    manifest = {
        "science_status": matrix["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": "C4 E01 evidence coverage",
        "analysis_question": "How much of the registered E01 requirement set has passing evidence, and what is outstanding?",
        "figures": [f"figures/{name}" for name in names],
        "fields": {"coverage": "registered trajectories per E01 step versus passing evidence",
                   "status": "plant gate status and outstanding actions"},
        "units": "trajectories (count)",
        "statistics_convention": "inventory of registered items; not a statistical sample",
        "generating_script": "tools/c3_c4_figures.py",
        "generating_script_sha256": sha(Path(__file__)),
        "source_files": [{"path": "analysis/20260917_C4_E01_EVIDENCE_MATRIX_02/e01_evidence_matrix.json", "sha256": sha(C4_MATRIX)},
                         {"path": "analysis/20260917_C4_E01_EVIDENCE_MATRIX_02/plant_gate.json", "sha256": sha(C4_GATE)}],
        "caption": (f"E01 evidence coverage: {matrix['trajectories_covered']} of {matrix['required_trajectories_total']} "
                    f"registered trajectories have passing evidence; the plant gate is {gate['status']}."),
        "claim_boundary": "A coverage figure for an audit class. It is not a plant gate PASS and releases nothing.",
    }
    (target / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (figure_dir / "README.md").write_text(
        "# C4 E01 证据覆盖图\n\n"
        "§25.4 对审计类的要求：**没有物理轨迹时用覆盖图，不硬造动力学曲线**。\n\n"
        "左：各 E01 步骤的**登记要求 vs 已通过证据**（仅 100m 阶跃诊断的 9 条有通过证据）；"
        "右：plant gate 状态、失败保留数、以及**执行前必须先冻结的缺口清单**。\n\n"
        f"**`plant_gate = {gate['status']}`**，独立审查 `{gate['independent_review']}`。\n\n"
        "**不发明“已完成 E01”总判定**；33 条不减最近运行数；失败轨迹保留 FAIL；100M05 只代表其 100m 子门。\n",
        encoding="utf-8",
    )
    print("C4 coverage:", names, "| covered", matrix["trajectories_covered"], "of", matrix["required_trajectories_total"])


if __name__ == "__main__":
    c3_replot()
    c4_coverage()
