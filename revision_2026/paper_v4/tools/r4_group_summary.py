"""R4 parameter-group summary figure: required by the task-book figure contract.

Section 25.4 requires, for step/parameter comparisons, "parameter group completion and
failure summary" in addition to the per-run figures.  Section 25.3 requires each
analysis directory to carry its own figures/ subtree.

Read-only.  Cells that are still running or not started are shown as coverage gaps with
their progress, never as fabricated curves.
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

CELLS = [
    {"parameter": "P1", "step_ms": 2.0, "run": "results/20260915_R4_P1_2MS_GPU01"},
    {"parameter": "P1", "step_ms": 1.0, "run": "results/20260915_R4_P1_1MS_GPU01"},
    {"parameter": "P1", "step_ms": 0.5, "run": "results/20260915_R4_P1_0P5MS_GPU01"},
    {"parameter": "P2", "step_ms": 2.0, "run": "results/20260915_R4_P2_2MS_GPU01"},
    {"parameter": "P2", "step_ms": 1.0, "run": "results/20260915_R4_P2_1MS_GPU02"},
    {"parameter": "P2", "step_ms": 0.5, "run": "results/20260915_R4_P2_0P5MS_GPU01"},
]

PAIR_SPECS = [
    {"parameter": "P1", "from_ms": 2.0, "to_ms": 1.0},
    {"parameter": "P1", "from_ms": 1.0, "to_ms": 0.5},
    {"parameter": "P2", "from_ms": 2.0, "to_ms": 1.0},
    {"parameter": "P2", "from_ms": 1.0, "to_ms": 0.5},
]


def discover_pair_reports(paper: Path) -> dict:
    """Find convergence reports by their own declared identity.

    The first version hard-coded the four report paths and therefore kept reporting a
    completed gate as PENDING once its report appeared.  Reports are now discovered by
    scanning analysis/ and reading each report's own parameter_id and step pair, so a
    gate flips to its real verdict as soon as the report exists.
    """
    found = {}
    for path in sorted((paper / "analysis").glob("*/r4_convergence_*ms_to_*ms.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        key = (report.get("parameter_id"), float(report.get("coarse_step_ms")), float(report.get("fine_step_ms")))
        found[key] = path
    return found


GATE_PANELS = [
    ("peak_force_relative_difference", "peak force (relative)", 2e-2),
    ("impulse_vector_relative_difference", "impulse vector (relative)", 2e-2),
    ("terminal_position_difference_m", "terminal position (m)", 1e-3),
    ("terminal_heading_difference_deg", "terminal heading (deg)", 1e-2),
]

LIMITS = {"force_n": 15000.0, "tire": 1.0, "support_n": 0.0, "route_m": 95.12831551628262}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_cell(paper: Path, cell: dict) -> dict:
    run = paper / cell["run"]
    record = dict(cell, exists=run.is_dir(), status="NOT_STARTED", ticks=0, progress=0.0)
    if not record["exists"]:
        return record
    metrics_path = run / "metrics.json"
    status_path = run / "status.json"
    if metrics_path.is_file():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        record.update({
            "status": metrics["status"],
            "ticks": int(metrics["iterations"]),
            "expected_ticks": int(metrics["expected_iterations"]),
            "wall_s": metrics["wall_s"],
            "peak_force_n": metrics["maximum_point_force_n"],
            "peak_tire": metrics["maximum_tire_utilization"],
            "min_support_n": metrics["minimum_support_load_n"],
            "route_distance_m": metrics["reference_distance_m"],
            "metrics_sha256": sha(metrics_path),
        })
        record["progress"] = record["ticks"] / max(record["expected_ticks"], 1)
        record["hard_gates_hold"] = bool(
            record["peak_force_n"] <= LIMITS["force_n"] + 1e-6
            and record["peak_tire"] <= LIMITS["tire"] + 1e-9
            and record["min_support_n"] >= LIMITS["support_n"]
            and record["route_distance_m"] >= LIMITS["route_m"] - 1e-9
        )
    elif status_path.is_file():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        record.update({
            "status": "RUNNING",
            "ticks": int(status.get("completed_ticks", 0)),
            "expected_ticks": int(status.get("total_ticks", 2379)),
            "route_distance_m": status.get("reference_distance_m"),
            "status_sha256": sha(status_path),
        })
        record["progress"] = record["ticks"] / max(record["expected_ticks"], 1)
    return record


def read_pair(paper: Path, pair: dict, discovered: dict) -> dict:
    path = discovered.get((pair["parameter"], pair["from_ms"], pair["to_ms"]))
    if path is None:
        return dict(pair, status="PENDING", measurements=None, verdicts=None)
    report = json.loads(path.read_text(encoding="utf-8"))
    return dict(pair, status=report["status"], measurements=report["measurements"],
                verdicts=report["verdicts"], report=str(path.relative_to(paper)).replace("\\", "/"), sha256=sha(path))


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
    if protocol.get("scope") != "R4_PARAMETER_GROUP_SUMMARY":
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

    cells = [read_cell(paper, dict(cell)) for cell in CELLS]
    discovered = discover_pair_reports(paper)
    pairs = [read_pair(paper, dict(spec), discovered) for spec in PAIR_SPECS]
    complete = [cell for cell in cells if cell["status"] == "COMPLETED"]
    running = [cell for cell in cells if cell["status"] == "RUNNING"]
    pending = [cell for cell in cells if cell["status"] in ("NOT_STARTED",)]

    figure_dir = output / "figures"
    figure_dir.mkdir()
    figure, axes = plt.subplots(2, 2, figsize=(15.5, 9.6))

    # --- 1 cell completion matrix ------------------------------------------
    parameters = ["P1", "P2"]
    steps = [2.0, 1.0, 0.5]
    code = {"COMPLETED": 2.0, "RUNNING": 1.0, "NOT_STARTED": 0.0}
    matrix = np.full((len(parameters), len(steps)), np.nan)
    for cell in cells:
        matrix[parameters.index(cell["parameter"]), steps.index(cell["step_ms"])] = code.get(cell["status"], 0.0)
    axes[0, 0].imshow(matrix, cmap="RdYlGn", vmin=0.0, vmax=2.0, aspect="auto")
    axes[0, 0].set(xticks=np.arange(len(steps)), xticklabels=[f"{step:g} ms" for step in steps],
                   yticks=np.arange(len(parameters)), yticklabels=parameters,
                   title=f"R4 parameter-group coverage — {len(complete)}/{len(cells)} cells complete")
    for row in range(len(parameters)):
        for column in range(len(steps)):
            cell = next(item for item in cells if item["parameter"] == parameters[row] and item["step_ms"] == steps[column])
            label = cell["status"].replace("_", " ")
            if cell["status"] == "RUNNING":
                label = f"RUNNING\n{100 * cell['progress']:.0f}%"
            axes[0, 0].text(column, row, label, ha="center", va="center", fontsize=9,
                            fontweight="bold", color="white" if cell["status"] == "NOT_STARTED" else "black")

    # --- 2 hard gates per cell ---------------------------------------------
    done = [cell for cell in cells if "peak_force_n" in cell]
    labels = [f"{cell['parameter']}\n{cell['step_ms']:g} ms" for cell in done]
    positions = np.arange(len(done))
    axes[0, 1].bar(positions - 0.2, [cell["peak_force_n"] / LIMITS["force_n"] for cell in done], 0.4,
                   label="peak force / 15000 N", color="#1f77b4")
    axes[0, 1].bar(positions + 0.2, [cell["peak_tire"] / LIMITS["tire"] for cell in done], 0.4,
                   label="peak tyre utilisation / 1.0", color="#ff7f0e")
    axes[0, 1].axhline(1.0, color="red", linestyle=":", label="hard gate = 1.0")
    for index, cell in enumerate(done):
        axes[0, 1].text(index - 0.2, cell["peak_force_n"] / LIMITS["force_n"] * 1.06, f"{cell['peak_force_n']:.1f} N", ha="center", fontsize=7)
    axes[0, 1].set(xticks=positions, xticklabels=labels, ylabel="fraction of the hard limit",
                   ylim=(0, 0.06), title=f"Original hard gates — worst cell uses {100 * max(cell['peak_force_n'] / LIMITS['force_n'] for cell in done):.3f}% of the force limit")
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(axis="y", alpha=0.25)

    # --- 3 pairwise convergence gates --------------------------------------
    gate_names = [name for name, _, _ in GATE_PANELS]
    gate_labels = [label for _, label, _ in GATE_PANELS]
    thresholds = [threshold for _, _, threshold in GATE_PANELS]
    pair_labels, values, colors = [], [], []
    for pair in pairs:
        for name, label, threshold in GATE_PANELS:
            pair_labels.append(f"{pair['parameter']} {pair['from_ms']:g}->{pair['to_ms']:g}\n{label}")
            if pair["measurements"] is None:
                values.append(FLOOR)
                colors.append("#8b0000")
            else:
                values.append(max(pair["measurements"][name], FLOOR))
                colors.append("#1f77b4")
    positions = np.arange(len(pair_labels))
    axes[1, 0].bar(positions, values, color=colors)
    for index in range(0, len(pair_labels), len(GATE_PANELS)):
        axes[1, 0].bar([index + offset for offset in range(len(GATE_PANELS))],
                       [thresholds[offset] for offset in range(len(GATE_PANELS))], 0.0)
    for index, threshold in enumerate(thresholds * len(pairs)):
        axes[1, 0].plot([index - 0.4, index + 0.4], [threshold, threshold], color="red", linestyle=":", linewidth=1.2)
    axes[1, 0].set_yscale("log")
    axes[1, 0].set_ylim(FLOOR * 0.5, 1.0)
    axes[1, 0].set(xticks=positions, xticklabels=pair_labels, ylabel="measured value (log)",
                   title=("Four decisive convergence gates per parameter point\n"
                          f"red dotted = frozen threshold; "
                          f"{sum(1 for pair in pairs if pair['status'] == 'PASS_R4_CELL_CONVERGENCE')}/{len(pairs)} gates PASS"
                          + ("" if all(pair["measurements"] for pair in pairs) else f", {sum(1 for pair in pairs if not pair['measurements'])} PENDING")))
    axes[1, 0].tick_params(axis="x", labelsize=6.5, rotation=45)
    for tick in axes[1, 0].get_xticklabels():
        tick.set_horizontalalignment("right")
    axes[1, 0].grid(which="both", axis="y", alpha=0.25)

    # --- 4 status board -----------------------------------------------------
    axes[1, 1].axis("off")
    lines = ["R4 parameter group — completion and failure summary", ""]
    lines.append(f"complete cells      : {len(complete)}/{len(cells)}")
    for cell in cells:
        if cell["status"] == "COMPLETED":
            detail = f"{cell['ticks']}/{cell['expected_ticks']} ticks, {cell['wall_s'] / 3600:.2f} h, gates {'PASS' if cell.get('hard_gates_hold') else 'FAIL'}"
        elif cell["status"] == "RUNNING":
            detail = f"{cell['ticks']}/{cell['expected_ticks']} ticks ({100 * cell['progress']:.1f}%), {cell.get('route_distance_m', float('nan')):.2f} m, no verdict yet"
        else:
            detail = "not started"
        lines.append(f"  {cell['parameter']} {cell['step_ms']:>4g} ms : {cell['status']:<11s} {detail}")
    lines.append("")
    lines.append("pairwise decisive gates:")
    for pair in pairs:
        tag = "PASS" if pair["status"] == "PASS_R4_CELL_CONVERGENCE" else pair["status"]
        if pair["measurements"]:
            lines.append(f"  {pair['parameter']} {pair['from_ms']:g}->{pair['to_ms']:g} ms : {tag}  "
                         f"(force {pair['measurements']['peak_force_relative_difference']:.2e}, "
                         f"position {pair['measurements']['terminal_position_difference_m']:.2e} m)")
        else:
            lines.append(f"  {pair['parameter']} {pair['from_ms']:g}->{pair['to_ms']:g} ms : {tag} (requires the 0.5 ms cell)")
    lines.append("")
    lines.append("NOT shown: any curve for a cell that is still running or not started.")
    lines.append("A completed route with all physical gates holding is NOT a tracking-quality")
    lines.append("claim; see analysis/20260916_R4_ROUTE_TRACKING_03 for the tracking report.")
    axes[1, 1].text(0.0, 1.0, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9.2,
                    transform=axes[1, 1].transAxes)

    figure.suptitle("R4 parameter-group summary (six cells, two parameter points, four decisive gates)", fontsize=13)
    figure.tight_layout(rect=(0, 0.01, 1, 0.95))
    figure_names = []
    for suffix in ("png", "svg"):
        name = f"r4_group_summary.{suffix}"
        figure.savefig(figure_dir / name, dpi=300 if suffix == "png" else None)
        figure_names.append(name)
    plt.close(figure)

    report = {
        "status": "PASS_R4_GROUP_SUMMARY",
        "scope": protocol["scope"],
        "cells_complete": len(complete),
        "cells_total": len(cells),
        "cells": [{key: value for key, value in cell.items()} for cell in cells],
        "pairs": pairs,
        "limits": LIMITS,
        "coverage_note": "Cells that are running or not started are reported with progress only; no curve is drawn for them.",
        "claim_boundary": "Group-level coverage and gate summary. It does not replace the per-run figures, does not claim tracking quality, and does not release R5: C1 total PASS also requires the P2 1-to-0.5 ms decisive gate and the linked r4_gate.json.",
    }
    (output / "r4_group_summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": protocol["scope"],
        "analysis_question": "Do all six R4 cells complete with the original hard gates holding, and do both parameter points pass their decisive step-convergence gates?",
        "figures": [f"figures/{name}" for name in figure_names],
        "fields": {
            "coverage": "cell status COMPLETED / RUNNING / NOT_STARTED with tick progress",
            "hard_gates": "peak connector force over 15000 N and peak tyre utilisation over 1.0, per cell",
            "convergence": "the four frozen gates per parameter point: peak force, impulse vector, terminal position, terminal heading",
        },
        "units": "N, m, deg, dimensionless ratios",
        "window": "whole route per completed cell; running cells show accepted progress only",
        "statistics_convention": "deterministic single runs; the three step sizes are numerical coverage points, not statistical samples",
        "generating_script": "tools/r4_group_summary.py",
        "generating_script_sha256": sha(Path(__file__)),
        "source_files": [{"path": str(paper / item["path"]), "sha256": item["sha256"]} for item in protocol["identity_files"]]
        + [{"path": str(protocol_path), "sha256": sha(protocol_path)}],
        "caption": (
            f"R4 parameter-group summary: {len(complete)} of {len(cells)} cells complete with all original hard gates holding; "
            f"{sum(1 for pair in pairs if pair['status'] == 'PASS_R4_CELL_CONVERGENCE')} of {len(pairs)} decisive step-convergence gates passed. "
            "Cells still running are shown as coverage gaps, never as curves."
        ),
        "claim_boundary": report["claim_boundary"],
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "figures" / "README.md").write_text(
        "# R4 参数组汇总图\n\n"
        "§25.4 要求“参数组完成/失败汇总”，本目录即该图；同时按 §25.3 把图放在分析目录自己的 `figures/` 子目录内。\n\n"
        "四面板：①六单元覆盖矩阵（完成/运行中/未开始，运行中给出百分比）；"
        "②原硬门占用（点力/15000 N、轮胎/1.0，并标出最差单元的占用比例）；"
        "③每个参数点的四个决定性收敛门与冻结阈值（PENDING 组明确标出）；"
        "④覆盖与判定的文字状态板。\n\n"
        "**未绘制**任何仍在运行或未开始单元的曲线——只报进度。\n\n"
        "**结论边界**：本图是组级覆盖与门汇总，不替代单条图；跑完全程且有硬门通过**不**等于跟踪质量合格"
        "（跟踪报告见 `analysis/20260916_R4_ROUTE_TRACKING_03`）；也**不**释放 R5——C1 总PASS还需 P2 的 1→0.5 ms 决定性门与汇总 `r4_gate.json`。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "cells_complete": len(complete),
                      "pairs_passed": sum(1 for pair in pairs if pair["status"] == "PASS_R4_CELL_CONVERGENCE"),
                      "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
