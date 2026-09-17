"""Route tracking-error report for completed R4 cells, using the D1 decomposition.

Reuses the exact convention registered in the D1 analysis so its published numbers
can be reproduced as a cross-check: the reference pose is interpolated from the
route at the *recorded* reference distance, and the payload position error is
projected onto the reference heading into longitudinal and lateral components.

Deliverable for task-book section 9.3, which requires reporting position, heading
and progress errors.  Unlike D1 this covers the *whole* route, including the
segment after 44 s that the interrupted CPU run never reached.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SPEED = 2.0
EXIT_STRAIGHT_START_M = 71.12831551628262
INTERRUPTION_TIME_S = 44.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values: np.ndarray) -> dict:
    values = np.asarray(values, dtype=float)
    return {
        "rmse": float(np.sqrt(np.mean(values ** 2))),
        "max_abs": float(np.max(np.abs(values))),
        "mean": float(np.mean(values)),
        "final": float(values[-1]),
        "count": int(values.size),
    }


def tracking_series(raw, columns, route) -> dict:
    index = {name: position for position, name in enumerate(columns)}
    distance = raw[:, index["reference_distance_m"]]
    reference = np.column_stack([
        np.interp(distance, route["s_m"], route[key]) for key in ("x_m", "y_m", "heading_rad", "curvature_1pm")
    ])
    dx = raw[:, index["x24"]] - reference[:, 0]
    dy = raw[:, index["x25"]] - reference[:, 1]
    cosine, sine = np.cos(reference[:, 2]), np.sin(reference[:, 2])
    longitudinal = cosine * dx + sine * dy
    lateral = -sine * dx + cosine * dy
    position = np.hypot(dx, dy)
    heading_deg = np.rad2deg(np.arctan2(np.sin(raw[:, index["x26"]] - reference[:, 2]), np.cos(raw[:, index["x26"]] - reference[:, 2])))
    forward_speed = raw[:, index["x27"]] - SPEED
    lateral_speed = raw[:, index["x28"]]
    yaw_rate = raw[:, index["x29"]] - SPEED * reference[:, 3]
    return {
        "time_s": raw[:, index["time_s"]],
        "reference_distance_m": distance,
        "longitudinal_m": longitudinal,
        "lateral_m": lateral,
        "position_m": position,
        "heading_deg": heading_deg,
        "forward_speed_mps": forward_speed,
        "lateral_speed_mps": lateral_speed,
        "yaw_rate_radps": yaw_rate,
    }


def cell_report(name: str, run: Path, route) -> dict:
    with np.load(run / "raw.npz", allow_pickle=False) as data:
        raw = data["values"].copy()
        columns = [str(value) for value in data["columns"]]
    series = tracking_series(raw, columns, route)
    distance = series["reference_distance_m"]
    late = distance >= EXIT_STRAIGHT_START_M
    after_interruption = series["time_s"] > INTERRUPTION_TIME_S
    growth = None
    if np.count_nonzero(after_interruption) > 5:
        times = series["time_s"][after_interruption]
        values = series["lateral_m"][after_interruption]
        growth = float(np.polyfit(times, values, 1)[0])
    return {
        "cell": name,
        "run": str(run.relative_to(run.parents[1])).replace("\\", "/"),
        "ticks": int(raw.shape[0]),
        "time_end_s": float(series["time_s"][-1]),
        "reference_distance_end_m": float(distance[-1]),
        "route_complete": bool(distance[-1] >= route["s_m"][-1] - 1e-9),
        "whole_route": {
            "position_m": stats(series["position_m"]),
            "longitudinal_m": stats(series["longitudinal_m"]),
            "lateral_m": stats(series["lateral_m"]),
            "heading_deg": stats(series["heading_deg"]),
            "forward_speed_mps": stats(series["forward_speed_mps"]),
            "yaw_rate_radps": stats(series["yaw_rate_radps"]),
        },
        "exit_straight_segment": {
            "ticks": int(np.count_nonzero(late)),
            "position_m": stats(series["position_m"][late]) if np.any(late) else None,
            "lateral_m": stats(series["lateral_m"][late]) if np.any(late) else None,
            "first_position_m": float(series["position_m"][late][0]) if np.any(late) else None,
            "final_position_m": float(series["position_m"][late][-1]) if np.any(late) else None,
            "fitted_position_growth_mps": float(np.polyfit(series["time_s"][late], series["position_m"][late], 1)[0]) if np.count_nonzero(late) > 5 else None,
        },
        "after_the_cpu_interruption": {
            "ticks": int(np.count_nonzero(after_interruption)),
            "lateral_m": stats(series["lateral_m"][after_interruption]) if np.any(after_interruption) else None,
            "position_m": stats(series["position_m"][after_interruption]) if np.any(after_interruption) else None,
            "fitted_lateral_growth_mps": growth,
        },
        "series": {key: value.tolist() for key, value in series.items()},
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
    if protocol.get("scope") != "R4_ROUTE_TRACKING_REPORT":
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

    sys.path.insert(0, str(paper / "src"))
    from paper_v4_core.references import build_hairpin

    route = build_hairpin()
    cells = [cell_report(cell["name"], paper / cell["run"], route) for cell in protocol["cells"]]

    # Cross-check against the numbers D1 published for the CPU prefix.
    validation = None
    if protocol.get("validation_reference"):
        reference = protocol["validation_reference"]
        target = next((cell for cell in cells if cell["cell"] == reference["cell"]), None)
        if target is not None:
            observed = {
                "final_position_m": target["whole_route"]["position_m"]["final"],
                "final_lateral_m": target["whole_route"]["lateral_m"]["final"],
                "final_longitudinal_m": target["whole_route"]["longitudinal_m"]["final"],
                "exit_straight_position_rmse_m": target["exit_straight_segment"]["position_m"]["rmse"],
                "exit_straight_first_position_m": target["exit_straight_segment"]["first_position_m"],
                "exit_straight_fitted_growth_mps": target["exit_straight_segment"]["fitted_position_growth_mps"],
            }
            comparisons = {
                key: {
                    "d1_published": reference["expected"][key],
                    "recomputed_here": observed[key],
                    "absolute_difference": abs(observed[key] - reference["expected"][key]),
                    "within_stated_tolerance": abs(observed[key] - reference["expected"][key]) <= reference["tolerance"],
                }
                for key in reference["expected"]
            }
            validation = {
                "cell": reference["cell"],
                "tolerance": reference["tolerance"],
                "comparisons": comparisons,
                "all_within_tolerance": all(item["within_stated_tolerance"] for item in comparisons.values()),
            }

    report = {
        "status": "PASS_ROUTE_TRACKING_REPORT",
        "scope": protocol["scope"],
        "convention": "reference pose interpolated from the route at the recorded reference distance; payload position error projected onto the reference heading into longitudinal and lateral components (identical to the registered D1 convention)",
        "exit_straight_start_m": EXIT_STRAIGHT_START_M,
        "interruption_time_s": INTERRUPTION_TIME_S,
        "d1_validation": validation,
        "cells": [{key: value for key, value in cell.items() if key != "series"} for cell in cells],
        "claim_boundary": "Tracking error is a quality metric, not a safety gate. Passing every physical hard gate does not make these numbers acceptable, and completing the route does not resolve a growing lateral deviation.",
    }
    (output / "route_tracking.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    # Cells have different lengths (the CPU prefix stops at 2200 ticks), so each
    # cell's series is stored under its own key prefix rather than stacked.
    archive = {}
    for series_cell in cells:
        for key in ("time_s", "reference_distance_m", "longitudinal_m", "lateral_m", "position_m", "heading_deg"):
            archive[f"{series_cell['cell']}__{key}"] = np.asarray(series_cell["series"][key], dtype=float)
    np.savez_compressed(output / "route_tracking_series.npz", **archive)

    figure, axes = plt.subplots(2, 2, figsize=(15.0, 9.0))
    colors = plt.cm.tab10(np.linspace(0, 1, max(len(cells), 3)))
    for color, series_cell in zip(colors, cells):
        axes[0, 0].plot(series_cell["series"]["time_s"], series_cell["series"]["lateral_m"], color=color, label=series_cell["cell"])
        axes[0, 1].plot(series_cell["series"]["time_s"], series_cell["series"]["position_m"], color=color, label=series_cell["cell"])
        axes[1, 0].plot(series_cell["series"]["time_s"], series_cell["series"]["heading_deg"], color=color, label=series_cell["cell"])
    axes[0, 0].axvline(INTERRUPTION_TIME_S, color="black", linestyle=":", label="CPU run interrupted here")
    axes[0, 0].axhline(0.0, color="#7f7f7f", linewidth=0.8)
    axes[0, 0].set(xlabel="time (s)", ylabel="lateral error (m)", title="Lateral deviation from the reference\npositive = left of the reference heading")
    axes[0, 0].legend(fontsize=7.5)
    axes[0, 0].grid(alpha=0.25)
    axes[0, 1].axvline(INTERRUPTION_TIME_S, color="black", linestyle=":")
    axes[0, 1].set(xlabel="time (s)", ylabel="payload position error (m)", title="Position error")
    axes[0, 1].legend(fontsize=7.5)
    axes[0, 1].grid(alpha=0.25)
    axes[1, 0].axvline(INTERRUPTION_TIME_S, color="black", linestyle=":")
    axes[1, 0].set(xlabel="time (s)", ylabel="heading error (deg)", title="Heading error")
    axes[1, 0].legend(fontsize=7.5)
    axes[1, 0].grid(alpha=0.25)

    names = [cell["cell"] for cell in cells]
    positions = np.arange(len(cells))
    width = 0.38
    final_lateral = [cell["whole_route"]["lateral_m"]["final"] for cell in cells]
    max_lateral = [cell["whole_route"]["lateral_m"]["max_abs"] for cell in cells]
    axes[1, 1].barh(positions - width / 2, final_lateral, width, label="final lateral error", color="#1f77b4")
    axes[1, 1].barh(positions + width / 2, max_lateral, width, label="max |lateral error|", color="#ff7f0e")
    for index, (final, maximum) in enumerate(zip(final_lateral, max_lateral)):
        axes[1, 1].text(max(final, maximum) + 0.005, index, f"final {final:+.3f} m, max {maximum:.3f} m", va="center", fontsize=8)
    axes[1, 1].set(yticks=positions, yticklabels=names, xlabel="lateral error (m)",
                   xlim=(min(0.0, min(final_lateral)) - 0.02, max(max_lateral) * 1.45),
                   title="Lateral deviation summary\ncompleting the route is not a tracking-quality claim")
    axes[1, 1].legend(fontsize=8)
    axes[1, 1].grid(axis="x", alpha=0.25)

    figure.suptitle("R4 route tracking quality (D1 convention, whole route including the segment past 44 s)", fontsize=12.5)
    figure.tight_layout(rect=(0, 0.01, 1, 0.95))
    figures = []
    for suffix in ("png", "svg"):
        name = f"route_tracking.{suffix}"
        figure.savefig(output / name, dpi=200 if suffix == "png" else None)
        figures.append(name)
    plt.close(figure)

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": protocol["scope"],
        "figures": figures,
        "source_files": [{"path": str(paper / item["path"]), "sha256": item["sha256"]} for item in protocol["identity_files"]]
        + [{"path": str(protocol_path), "sha256": sha(protocol_path)}],
        "result_files": [
            {"path": "route_tracking.json", "sha256": sha(output / "route_tracking.json")},
            {"path": "route_tracking_series.npz", "sha256": sha(output / "route_tracking_series.npz")},
        ],
        "claim_boundary": report["claim_boundary"],
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "README.md").write_text(
        "# R4 全路线跟踪质量报告\n\n"
        "按**登记的D1口径**计算：参考位姿由路线在**落盘参考距离**处插值得到，货物位置误差投影到参考航向，"
        "分解为纵向与横向分量。\n\n"
        "与D1不同之处：本报告覆盖**整条路线**，包含CPU运行从未到达的44 s之后那一段。\n\n"
        "**结论边界**：跟踪误差是质量指标、不是安全门。物理硬门全过**不**等于这些数字可接受；"
        "跑完全程也**不**等于横向偏离问题已解决。\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "validation_all_within_tolerance": None if validation is None else validation["all_within_tolerance"],
        "cells": [{cell["cell"]: None, "final_lateral_m": cell["whole_route"]["lateral_m"]["final"],
                   "max_lateral_m": cell["whole_route"]["lateral_m"]["max_abs"],
                   "late_lateral_final_m": (cell["after_the_cpu_interruption"]["lateral_m"] or {}).get("final")} for cell in cells],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
