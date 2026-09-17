"""Definitive A/B figure: defective versus corrected control-rate penalty sign.

Same candidate, same P0 nominal parameter point, same 2 ms plant step, same route.  The
only controlled variable is the sign of the rate-penalty linear term; the backend differs
(GPU versus the historical CPU run) and contributes about 2.4e-05 m over 2200 ticks, which
is three orders of magnitude below the effect shown here.

Section 25.4 requires trajectory, error, force/constraint, input and cost information; each
is present either as a curve or in the status board.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER / "src"))

BUGGY = {"run": "results/20260911_R3_UNFROZEN_FULL01/2ms", "label": "P0 nominal 2 ms, CPU — DEFECTIVE sign", "color": "#d62728"}
FIXED = {"run": "results/20260916_R5_BASELINE_P0_2MS_GPU02", "label": "P0 nominal 2 ms, GPU — CORRECTED sign", "color": "#1f77b4"}
OTHERS = [
    ("results/20260915_R4_P1_2MS_GPU01", "P1 GPU 2 ms, defective", "#ff7f0e"),
    ("results/20260915_R4_P2_2MS_GPU01", "P2 GPU 2 ms, defective", "#2ca02c"),
]
FORCE_LIMIT_N = 15000.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def track(run_rel: str, route: dict) -> dict:
    run = PAPER / run_rel
    with np.load(run / "raw.npz", allow_pickle=False) as data:
        raw = data["values"].copy()
        columns = [str(name) for name in data["columns"]]
    index = {name: position for position, name in enumerate(columns)}
    distance = raw[:, index["reference_distance_m"]]
    reference_x = np.interp(distance, route["s_m"], route["x_m"])
    reference_y = np.interp(distance, route["s_m"], route["y_m"])
    reference_psi = np.interp(distance, route["s_m"], route["heading_rad"])
    dx = raw[:, index["x24"]] - reference_x
    dy = raw[:, index["x25"]] - reference_y
    lateral = -np.sin(reference_psi) * dx + np.cos(reference_psi) * dy
    longitudinal = np.cos(reference_psi) * dx + np.sin(reference_psi) * dy
    position = np.hypot(dx, dy)
    time = raw[:, index["time_s"]]
    force = raw[:, [index[f"point_force_norm{i}"] for i in range(4)]]
    wall = raw[:, index["solver_wall_s"]]
    tail = time >= 44.0
    return {
        "run": run_rel, "distance": distance, "time": time,
        "lateral": lateral, "longitudinal": longitudinal, "position": position,
        "force": force, "wall": wall,
        "lateral_end": float(lateral[-1]), "lateral_max_abs": float(np.abs(lateral).max()),
        "longitudinal_end": float(longitudinal[-1]),
        "position_end": float(position[-1]), "position_rmse": float(np.sqrt(np.mean(position ** 2))),
        "lateral_growth_after_44s": float(np.polyfit(time[tail], lateral[tail], 1)[0]) if tail.sum() > 20 else None,
        "peak_force": float(force.max()), "mean_wall": float(wall.mean()), "max_wall": float(wall.max()),
        "within_5s": int(np.count_nonzero(wall <= 5.0)), "ticks": int(raw.shape[0]),
    }


def main() -> None:
    from paper_v4_core.references import build_hairpin

    route = build_hairpin()
    buggy = track(BUGGY["run"], route)
    fixed = track(FIXED["run"], route)
    others = [dict(zip(("run", "label", "color"), item), **track(item[0], route)) for item in OTHERS]

    target = PAPER / "analysis/20260917_RATE_PENALTY_FIXED_EFFECT_02"
    figure_dir = target / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(2, 3, figsize=(19.5, 10.0))

    axes[0, 0].plot(buggy["distance"], buggy["lateral"], color=BUGGY["color"], label=BUGGY["label"])
    axes[0, 0].plot(fixed["distance"], fixed["lateral"], color=FIXED["color"], label=FIXED["label"])
    axes[0, 0].axhline(0.0, color="black", linewidth=0.8)
    axes[0, 0].set(xlabel="reference distance (m)", ylabel="payload lateral error (m)",
                   title=f"Lateral error — endpoint {buggy['lateral_end']:.4f} m to {fixed['lateral_end']:.4f} m "
                         f"({(fixed['lateral_end'] / buggy['lateral_end'] - 1) * 100:+.1f}%)")
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(alpha=0.25)

    axes[0, 1].plot(buggy["distance"], buggy["longitudinal"], color=BUGGY["color"], label="defective")
    axes[0, 1].plot(fixed["distance"], fixed["longitudinal"], color=FIXED["color"], label="corrected")
    axes[0, 1].axhline(0.0, color="black", linewidth=0.8)
    axes[0, 1].set(xlabel="reference distance (m)", ylabel="payload longitudinal error (m)",
                   title=f"Longitudinal error — endpoint {buggy['longitudinal_end']:.4f} m to {fixed['longitudinal_end']:.4f} m")
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(alpha=0.25)

    axes[0, 2].plot(buggy["distance"], buggy["position"], color=BUGGY["color"], label="defective")
    axes[0, 2].plot(fixed["distance"], fixed["position"], color=FIXED["color"], label="corrected")
    axes[0, 2].set(xlabel="reference distance (m)", ylabel="payload position error (m)",
                   title=f"Position error — RMSE {buggy['position_rmse']:.4f} m to {fixed['position_rmse']:.4f} m "
                         f"({(fixed['position_rmse'] / buggy['position_rmse'] - 1) * 100:+.1f}%)")
    axes[0, 2].legend(fontsize=8)
    axes[0, 2].grid(alpha=0.25)

    for index in range(4):
        axes[1, 0].plot(buggy["distance"], buggy["force"][:, index], color=BUGGY["color"], linewidth=0.9,
                        label="defective, points 1-4" if index == 0 else None)
        axes[1, 0].plot(fixed["distance"], fixed["force"][:, index], color=FIXED["color"], linewidth=0.9,
                        label="corrected, points 1-4" if index == 0 else None)
    readable = 1.25 * max(buggy["peak_force"], fixed["peak_force"])
    axes[1, 0].set_ylim(0.0, readable)
    axes[1, 0].annotate(f"15000 N ultimate gate is off-scale above this panel "
                        f"({FORCE_LIMIT_N / max(buggy['peak_force'], fixed['peak_force']):.0f}x the highest peak)",
                        xy=(0.02, 0.94), xycoords="axes fraction", fontsize=8.5, color="#8b0000")
    axes[1, 0].axhline(buggy["peak_force"], color=BUGGY["color"], linestyle=":", linewidth=1.0)
    axes[1, 0].axhline(fixed["peak_force"], color=FIXED["color"], linestyle=":", linewidth=1.0)
    axes[1, 0].set(xlabel="reference distance (m)", ylabel="point force norm (N)",
                   title=f"Force on a readable scale — peak {buggy['peak_force']:.1f} N to {fixed['peak_force']:.1f} N "
                         f"({(fixed['peak_force'] / buggy['peak_force'] - 1) * 100:+.1f}%)")
    axes[1, 0].legend(fontsize=8)
    axes[1, 0].grid(alpha=0.25)

    for item in others:
        axes[1, 1].plot(item["distance"], item["lateral"], color=item["color"], linewidth=1.0, label=item["label"])
    axes[1, 1].plot(buggy["distance"], buggy["lateral"], color=BUGGY["color"], linewidth=1.4, label="P0 CPU 2 ms, defective")
    axes[1, 1].plot(fixed["distance"], fixed["lateral"], color=FIXED["color"], linewidth=1.6, label="P0 GPU 2 ms, corrected")
    axes[1, 1].axhline(0.0, color="black", linewidth=0.8)
    axes[1, 1].set(xlabel="reference distance (m)", ylabel="payload lateral error (m)",
                   title="All defective runs cluster together; the corrected run is far below")
    axes[1, 1].legend(fontsize=7.5)
    axes[1, 1].grid(alpha=0.25)

    axes[1, 2].axis("off")
    lines = [
        "Rate-penalty sign: defective versus corrected",
        "",
        "controlled variable: the sign of the rate penalty only",
        "candidate, parameter point (P0 nominal), plant step (2 ms),",
        "route and gates are identical",
        "",
        f"{'':26s} {'defective':>11s} {'corrected':>11s} {'change':>9s}",
        f"{'lateral endpoint (m)':26s} {buggy['lateral_end']:11.6f} {fixed['lateral_end']:11.6f} "
        f"{(fixed['lateral_end'] / buggy['lateral_end'] - 1) * 100:+8.2f}%",
        f"{'lateral max (m)':26s} {buggy['lateral_max_abs']:11.6f} {fixed['lateral_max_abs']:11.6f} "
        f"{(fixed['lateral_max_abs'] / buggy['lateral_max_abs'] - 1) * 100:+8.2f}%",
        f"{'position RMSE (m)':26s} {buggy['position_rmse']:11.6f} {fixed['position_rmse']:11.6f} "
        f"{(fixed['position_rmse'] / buggy['position_rmse'] - 1) * 100:+8.2f}%",
        f"{'drift after 44 s (m/s)':26s} {buggy['lateral_growth_after_44s']:11.6f} {fixed['lateral_growth_after_44s']:11.6f} "
        f"{(fixed['lateral_growth_after_44s'] / buggy['lateral_growth_after_44s'] - 1) * 100:+8.2f}%",
        f"{'peak point force (N)':26s} {buggy['peak_force']:11.2f} {fixed['peak_force']:11.2f} "
        f"{(fixed['peak_force'] / buggy['peak_force'] - 1) * 100:+8.2f}%",
        f"{'longitudinal endpoint (m)':26s} {buggy['longitudinal_end']:11.6f} {fixed['longitudinal_end']:11.6f} "
        f"{(fixed['longitudinal_end'] / buggy['longitudinal_end'] - 1) * 100:+8.2f}%",
        f"{'terminal position (m)':26s} {buggy['position_end']:11.6f} {fixed['position_end']:11.6f} "
        f"{(fixed['position_end'] / buggy['position_end'] - 1) * 100:+8.2f}%",
        "",
        f"force gate margin: {FORCE_LIMIT_N / fixed['peak_force']:.1f}x (corrected run)",
        f"mean solve wall: {buggy['mean_wall']:.3f} s to {fixed['mean_wall']:.3f} s",
        f"within 5 s budget: {buggy['within_5s']}/{buggy['ticks']} to {fixed['within_5s']}/{fixed['ticks']}",
        "",
        "Reading: the sign defect caused about 72 percent of the late",
        "lateral deviation, and correcting it also cuts the position RMSE",
        "by half. But it is NOT a free improvement: the peak connector",
        "force rises 38 percent and the error moves into the longitudinal",
        "channel (endpoint -0.093 m to -0.416 m, 4.5x worse), so the net",
        "terminal position only improves from 0.675 m to 0.455 m (-33%).",
        "The backend difference contributes only about 24 um over 2200 ticks.",
    ]
    axes[1, 2].text(0.0, 1.0, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9.0,
                    transform=axes[1, 2].transAxes)

    figure.suptitle("Control-rate penalty sign: defective versus corrected, same candidate and parameter point", fontsize=13)
    figure.tight_layout(rect=(0, 0.01, 1, 0.95))
    names = []
    for suffix in ("png", "svg"):
        name = f"rate_penalty_defective_vs_corrected.{suffix}"
        figure.savefig(figure_dir / name, dpi=300 if suffix == "png" else None)
        names.append(name)
    plt.close(figure)

    payload = {
        "status": "PASS_READ_ONLY_DEFECT_IMPACT_MEASURED",
        "scope": "rate-penalty sign impact at P0 nominal 2 ms",
        "controlled_variable": "sign of the control-rate penalty linear term",
        "unchanged": ["candidate EXP-R3-unfrozen-v1", "parameter point P0 nominal", "plant step 2 ms",
                      "route", "gates", "weights", "scales"],
        "backend_caveat": "defective reference is CPU, corrected run is GPU; measured cross-backend agreement is 2.398450764928839e-05 m over 2200 ticks, about three orders below the effect reported here",
        "defective": {k: buggy[k] for k in ("lateral_end","lateral_max_abs","longitudinal_end","position_end","position_rmse","lateral_growth_after_44s","peak_force","mean_wall","max_wall","within_5s","ticks")},
        "corrected": {k: fixed[k] for k in ("lateral_end","lateral_max_abs","longitudinal_end","position_end","position_rmse","lateral_growth_after_44s","peak_force","mean_wall","max_wall","within_5s","ticks")},
        "reading": "About 72 percent of the late lateral deviation is attributable to the sign defect. The correction also raises the peak connector force by 38 percent, so it trades tracking for force rather than improving everything.",
        "claim_boundary": "This measures the impact of one sign error. It does not make the P1 tracking deviation acceptable, does not restore the retired C1 total PASS, and is not a method-level result.",
    }
    (target / "fixed_vs_buggy_tracking.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "science_status": payload["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": payload["scope"],
        "analysis_question": "How much of the late lateral deviation was caused by the rate-penalty sign defect?",
        "figures": [f"figures/{name}" for name in names],
        "fields": {"error": "payload error projected on the reference heading (D1 convention)",
                   "force": "four point-force norms against the 15000 N gate",
                   "cost": "per-solve wall clock against the 5 s budget"},
        "units": "m, N, s",
        "window": "whole route, 2379 ticks",
        "statistics_convention": "deterministic single runs; one controlled variable",
        "generating_script": "tools/rate_penalty_fixed_effect_figure.py",
        "generating_script_sha256": sha(Path(__file__)),
        "source_files": [{"path": BUGGY["run"] + "/raw.npz", "sha256": sha(PAPER / BUGGY["run"] / "raw.npz")},
                         {"path": FIXED["run"] + "/raw.npz", "sha256": sha(PAPER / FIXED["run"] / "raw.npz")},
                         {"path": FIXED["run"] + "/metrics.json", "sha256": sha(PAPER / FIXED["run"] / "metrics.json")}],
        "caption": payload["reading"],
        "claim_boundary": payload["claim_boundary"],
    }
    (target / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (figure_dir / "README.md").write_text(
        "# 速率惩罚符号：缺陷版 vs 修复版（决定性 A/B）\n\n"
        "**受控变量只有速率惩罚的符号**：候选（`EXP-R3-unfrozen-v1`）、参数点（P0 名义）、植物步长（2 ms）、"
        "路线、门、权重、尺度**全部相同**。后端不同（缺陷参考为 CPU、修复版为 GPU），"
        "而跨后端实测一致度为 2200 tick 约 `2.4e-05 m`，比本图效应低约三个数量级。\n\n"
        "六面板：①横向误差；②纵向误差；③位置误差；④四点力（含 15000 N 硬界）；"
        "⑤**全部缺陷运行聚在一起、修复版远在其下**；⑥数字状态板与解读。\n\n"
        "**结论**：符号缺陷解释了**约 72%** 的晚段横向偏离；修复后横向 0.184 m、位置RMSE 0.125 m，"
        "但**力峰上升 38%**（288→399 N，仍留约 37 倍余量）——是**跟踪与受力的取舍**，不是全面改善。\n\n"
        "**边界**：本图只量化一处符号错误的影响；**不**使 P1 的跟踪偏离变得可接受、**不**恢复已退役的 C1 总PASS、"
        "**不**构成方法级结论。\n",
        encoding="utf-8",
    )
    print(json.dumps({"figures": names, "defective_lateral_end": buggy["lateral_end"],
                      "corrected_lateral_end": fixed["lateral_end"],
                      "defective_peak_force": buggy["peak_force"], "corrected_peak_force": fixed["peak_force"],
                      "output": str(target)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
