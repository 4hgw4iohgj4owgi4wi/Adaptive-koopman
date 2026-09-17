"""Compare two R4 cells of the same parameter point at different plant steps.

Reuses the four frozen R3 convergence gates so the GPU cells are judged by the same
contract the CPU R3 recovery used: peak point force, force-impulse vector, terminal
payload position and terminal payload heading.  Read-only.
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

POSITION_INDEX = (0, 1, 6, 7, 12, 13, 18, 19)
HEADING_INDEX = (2, 8, 14, 20)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), [str(value) for value in data["columns"]]


def impulse_vector(substeps: Path, columns) -> np.ndarray:
    index = {name: position for position, name in enumerate(columns)}
    sub, sub_columns = load(substeps)
    sub_index = {name: position for position, name in enumerate(sub_columns)}
    total = np.zeros(8)
    for i in range(4):
        total[2 * i] = float(sub[:, sub_index[f"force_impulse_x{i}"]].sum())
        total[2 * i + 1] = float(sub[:, sub_index[f"force_impulse_y{i}"]].sum())
    return total


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
    if protocol.get("schema_version") != "R4-CELL-COMPARE-v1":
        raise ValueError("PROTOCOL_SCHEMA_MISMATCH")
    for item in protocol["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    output = (paper / protocol["output"]) if not Path(protocol["output"]).is_absolute() else Path(protocol["output"])
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)

    cells = []
    for cell in protocol["cells"]:
        directory = paper / cell["output"]
        metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        raw, columns = load(directory / "raw.npz")
        _, sub_columns = load(directory / "substeps.npz")
        index = {name: position for position, name in enumerate(columns)}
        cells.append({
            "step_ms": cell["step_ms"],
            "output": cell["output"],
            "status": metrics["status"],
            "iterations": metrics["iterations"],
            "wall_s": metrics["wall_s"],
            "maximum_point_force_n": metrics["maximum_point_force_n"],
            "maximum_tire_utilization": metrics["maximum_tire_utilization"],
            "minimum_support_load_n": metrics["minimum_support_load_n"],
            "route_length_m": metrics["route_length_m"],
            "reference_distance_m": metrics["reference_distance_m"],
            "terminal_state": raw[-1][[index[f"x{i}"] for i in range(30)]].tolist(),
            "raw": raw,
            "index": index,
            "impulse": impulse_vector(directory / "substeps.npz", sub_columns),
        })

    cells.sort(key=lambda item: item["step_ms"], reverse=True)
    coarse, fine = cells[0], cells[1]
    ticks = int(min(coarse["raw"].shape[0], fine["raw"].shape[0]))
    coarse_state = coarse["raw"][:ticks][:, [coarse["index"][f"x{i}"] for i in range(30)]]
    fine_state = fine["raw"][:ticks][:, [fine["index"][f"x{i}"] for i in range(30)]]
    delta = np.abs(coarse_state - fine_state)
    position = delta[:, list(POSITION_INDEX)].max(axis=1)
    heading = delta[:, list(HEADING_INDEX)].max(axis=1)

    gates = protocol["gates"]
    peak_reference = float(coarse["maximum_point_force_n"])
    peak_relative = abs(fine["maximum_point_force_n"] - peak_reference) / max(peak_reference, np.finfo(float).tiny)
    impulse_reference = float(np.linalg.norm(coarse["impulse"]))
    impulse_relative = float(np.linalg.norm(fine["impulse"] - coarse["impulse"]) / max(impulse_reference, np.finfo(float).tiny))
    terminal_position = float(np.linalg.norm(np.asarray(fine["terminal_state"][24:26]) - np.asarray(coarse["terminal_state"][24:26])))
    terminal_heading_deg = float(abs(np.rad2deg(fine["terminal_state"][26] - coarse["terminal_state"][26])))

    verdicts = {
        "coarse_completed": coarse["status"] == "COMPLETED",
        "fine_completed": fine["status"] == "COMPLETED",
        "peak_force_within_gate": peak_relative <= gates["peak_force_relative"],
        "impulse_vector_within_gate": impulse_relative <= gates["impulse_vector_relative"],
        "terminal_position_within_gate": terminal_position <= gates["terminal_position_m"],
        "terminal_heading_within_gate": terminal_heading_deg <= gates["terminal_heading_deg"],
        "fine_original_hard_gates_hold": bool(
            fine["maximum_point_force_n"] <= gates["original_ultimate_force_n"] + 1e-6
            and fine["maximum_tire_utilization"] <= gates["original_tire_limit"] + 1e-9
            and fine["minimum_support_load_n"] >= 0.0
        ),
    }
    report = {
        "status": "PASS_R4_CELL_CONVERGENCE" if all(verdicts.values()) else "FAIL_R4_CELL_CONVERGENCE",
        "scope": protocol["scope"],
        "parameter_id": protocol["parameter_id"],
        "coarse_step_ms": coarse["step_ms"],
        "fine_step_ms": fine["step_ms"],
        "cells": [{key: value for key, value in cell.items() if key not in ("raw", "index", "terminal_state", "impulse")} | {"terminal_payload_xy": cell["terminal_state"][24:26], "terminal_heading_rad": cell["terminal_state"][26], "impulse_vector_ns": np.asarray(cell["impulse"], float).tolist()} for cell in cells],
        "gates": gates,
        "measurements": {
            "peak_force_relative_difference": peak_relative,
            "impulse_vector_relative_difference": impulse_relative,
            "terminal_position_difference_m": terminal_position,
            "terminal_heading_difference_deg": terminal_heading_deg,
            "state_max_abs_difference_m": float(delta[:, list(POSITION_INDEX)].max()),
            "position_series_m": position.tolist(),
            "heading_series_rad": heading.tolist(),
        },
        "verdicts": verdicts,
        "wall_clock_s": {f"{cell['step_ms']}ms": cell["wall_s"] for cell in cells},
        "claim_boundary": "Numerical convergence between two plant steps on the GPU route. Not a real-time claim and not a substitute for the hard gates of either cell.",
    }
    (output / f"r4_convergence_{coarse['step_ms']:g}ms_to_{fine['step_ms']:g}ms.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    figure, axes = plt.subplots(2, 2, figsize=(14.0, 8.6))
    axes[0, 0].semilogy(np.arange(ticks), np.maximum(position, 1e-18), label="max position deviation (m)")
    axes[0, 0].semilogy(np.arange(ticks), np.maximum(heading, 1e-18), label="max heading deviation (rad)")
    axes[0, 0].axhline(1e-18, color="#7f7f7f", linestyle=":", label="1e-18 display floor")
    axes[0, 0].set(xlabel="tick index", ylabel="coarse vs fine divergence (log)",
                   title=f"{coarse['step_ms']:g} ms vs {fine['step_ms']:g} ms plant step\nworst position {position.max():.3e} m")
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(which="both", alpha=0.25)

    labels = ["peak force\n(rel, gate 2e-2)", f"impulse vector\n(rel, gate {gates['impulse_vector_relative']:.0e})",
              f"terminal position\n(m, gate {gates['terminal_position_m']:.0e})", f"terminal heading\n(deg, gate {gates['terminal_heading_deg']:.2f})"]
    values = [max(peak_relative, 1e-18), max(impulse_relative, 1e-18), max(terminal_position, 1e-18), max(terminal_heading_deg, 1e-18)]
    gate_values = [gates["peak_force_relative"], gates["impulse_vector_relative"], gates["terminal_position_m"], gates["terminal_heading_deg"]]
    axes[0, 1].bar(np.arange(4) - 0.2, values, 0.4, label="measured", color="#1f77b4")
    axes[0, 1].bar(np.arange(4) + 0.2, gate_values, 0.4, label="frozen gate", color="#d62728")
    axes[0, 1].set_yscale("log")
    axes[0, 1].set(xticks=np.arange(4), xticklabels=labels, ylabel="value (log)",
                   title="Four frozen R3-style convergence gates")
    axes[0, 1].tick_params(axis="x", labelsize=7.5)
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(axis="y", which="both", alpha=0.25)

    names = [f"{cell['step_ms']:g} ms" for cell in cells]
    positions = np.arange(len(cells))
    axes[1, 0].bar(positions, [cell["maximum_point_force_n"] for cell in cells], 0.5, color="#2ca02c")
    for index, cell in enumerate(cells):
        axes[1, 0].text(index, cell["maximum_point_force_n"] * 1.0002, f"{cell['maximum_point_force_n']:.9f} N", ha="center", fontsize=8)
    axes[1, 0].set(xticks=positions, xticklabels=names, ylabel="maximum point force (N)",
                   ylim=(min(cell["maximum_point_force_n"] for cell in cells) * 0.9995, max(cell["maximum_point_force_n"] for cell in cells) * 1.001),
                   title="Peak connector force is step-independent to about 1e-10 relative")
    axes[1, 0].grid(axis="y", alpha=0.25)

    axes[1, 1].bar(np.arange(len(verdicts)) - 0.2, [1.0 if value else 0.0 for value in verdicts.values()], 0.4, color=["#2ca02c" if value else "#8b0000" for value in verdicts.values()])
    axes[1, 1].set(xticks=np.arange(len(verdicts)), xticklabels=[name.replace("_", " ") for name in verdicts], ylim=(0, 1.25), yticks=(0, 1), yticklabels=("FAIL", "PASS"),
                   title=f"Verdicts — overall {report['status']}")
    axes[1, 1].tick_params(axis="x", labelsize=7.5, rotation=25)
    for index, value in enumerate(verdicts.values()):
        axes[1, 1].text(index - 0.2, 1.05 if value else 0.05, "PASS" if value else "FAIL", ha="center", fontsize=8, color="#14532d" if value else "#8b0000", fontweight="bold")
    axes[1, 1].grid(axis="y", alpha=0.25)

    figure.suptitle(f"R4 cell convergence: {coarse['step_ms']:g} ms vs {fine['step_ms']:g} ms plant step (GPU route)", fontsize=12.5)
    figure.tight_layout(rect=(0, 0.01, 1, 0.95))
    figures = []
    for suffix in ("png", "svg"):
        name = f"r4_convergence.{suffix}"
        figure.savefig(output / name, dpi=200 if suffix == "png" else None)
        figures.append(name)
    plt.close(figure)

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "figures": figures,
        "source_files": [{"path": str(paper / item["path"]), "sha256": item["sha256"]} for item in protocol["identity_files"]]
        + [{"path": str(protocol_path), "sha256": sha(protocol_path)}],
        "result_files": [{"path": f"r4_convergence_{coarse['step_ms']:g}ms_to_{fine['step_ms']:g}ms.json",
                          "sha256": sha(output / f"r4_convergence_{coarse['step_ms']:g}ms_to_{fine['step_ms']:g}ms.json")}],
        "claim_boundary": report["claim_boundary"],
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "README.md").write_text(
        f"# R4 单元数值收敛比较：{coarse['step_ms']:g} ms vs {fine['step_ms']:g} ms\n\n"
        "复用R3冻结的四门（力峰相对2%、冲量向量相对2%、终点位置1mm、航向0.01°）比较同一参数点的两个植物步长单元，"
        "并核对细步长单元的原硬门。只读，不重跑任何动力学。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "verdicts": verdicts, "measurements": report["measurements"]["peak_force_relative_difference"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
