"""Figures for the rate-penalty sign defect and for the defective-version tracking reference.

Two figure sets:
  analysis/20260916_RATE_PENALTY_SIGN_PROBE_02/figures/       defect evidence
  analysis/20260916_RATE_PENALTY_EFFECT_BUGGY_REFERENCE/figures/  defective-version tracking

The corrected-controller run is still in flight, so its curve is deliberately NOT drawn;
the panels reserve the slot and state PENDING, per task-book section 25.3 (no fabricated
curves, state what is missing).
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

CHANNELS = ["accel 1", "steer 1", "accel 2", "steer 2", "accel 3", "steer 3", "accel 4", "steer 4"]
BUGGY_RUNS = [
    ("results/20260911_R3_UNFROZEN_FULL01/2ms", "P0 nominal, CPU, 2 ms", "#1f77b4"),
    ("results/20260915_R4_P1_2MS_GPU01", "P1, GPU, 2 ms", "#ff7f0e"),
    ("results/20260915_R4_P2_2MS_GPU01", "P2, GPU, 2 ms", "#2ca02c"),
]
FIXED_RUN = "results/20260916_R5_BASELINE_P0_2MS_GPU02"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def track(run: Path, route: dict) -> dict | None:
    if not (run / "raw.npz").is_file():
        return None
    with np.load(run / "raw.npz", allow_pickle=False) as data:
        raw = data["values"].copy()
        columns = [str(name) for name in data["columns"]]
    index = {name: position for position, name in enumerate(columns)}
    if "reference_distance_m" not in index or "x24" not in index:
        return None
    distance = raw[:, index["reference_distance_m"]]
    reference_x = np.interp(distance, route["s_m"], route["x_m"])
    reference_y = np.interp(distance, route["s_m"], route["y_m"])
    reference_psi = np.interp(distance, route["s_m"], route["heading_rad"])
    dx = raw[:, index["x24"]] - reference_x
    dy = raw[:, index["x25"]] - reference_y
    lateral = -np.sin(reference_psi) * dx + np.cos(reference_psi) * dy
    longitudinal = np.cos(reference_psi) * dx + np.sin(reference_psi) * dy
    return {
        "distance": distance,
        "time": raw[:, index["time_s"]],
        "lateral": lateral,
        "longitudinal": longitudinal,
        "position": np.hypot(dx, dy),
        "force": raw[:, [index[f"point_force_norm{i}"] for i in range(4)]].max(axis=1),
    }


def defect_figures() -> None:
    source = PAPER / "analysis/20260916_RATE_PENALTY_SIGN_PROBE_02/rate_penalty_sign.json"
    report = json.loads(source.read_text(encoding="utf-8"))
    coded = np.asarray(report["coded"]["first_control"], float)
    corrected = np.asarray(report["corrected"]["first_control"], float)
    previous = np.asarray(report["previous_u"], float)
    nominal = np.asarray(report["nominal_first_control"], float)
    r_nom = np.asarray(report["r_nom_first_block"], float) if "r_nom_first_block" in report else (nominal - previous)

    # recompute the two gradients exactly as the probe did
    scale = np.tile(np.asarray([0.2, np.deg2rad(2)] * 4), 1)[:8]
    n = 20
    full_scale = np.tile(np.asarray([0.2, np.deg2rad(2)] * 4), n)
    # first block only: (D^T r_nom) restricted to block 0 equals r_nom block 0 minus the
    # block-1 contribution, which the probe evaluated in full; reuse the probe numbers.
    coded_gradient = np.asarray(report["rate_gradient_first_block_coded"], float) if "rate_gradient_first_block_coded" in report else None
    correct_gradient = np.asarray(report["rate_gradient_first_block_correct"], float) if "rate_gradient_first_block_correct" in report else None

    figure_dir = source.parent / "figures"
    figure_dir.mkdir(exist_ok=True)
    figure, axes = plt.subplots(2, 2, figsize=(15.0, 9.6))

    if coded_gradient is not None:
        positions = np.arange(8)
        axes[0, 0].bar(positions - 0.2, coded_gradient, 0.4, label="as coded (target = -r_nom)", color="#d62728")
        axes[0, 0].bar(positions + 0.2, correct_gradient, 0.4, label="corrected (target = +r_nom)", color="#1f77b4")
        axes[0, 0].axhline(0.0, color="black", linewidth=0.8)
        axes[0, 0].set(xticks=positions, xticklabels=CHANNELS, ylabel="rate-term gradient, first horizon step",
                       title="The two signs give exactly opposite gradients")
        axes[0, 0].tick_params(axis="x", labelsize=7.5, rotation=30)
        axes[0, 0].legend(fontsize=8)
        axes[0, 0].grid(axis="y", alpha=0.25)

    # what the implemented quadratic actually minimises
    rate = np.linspace(-1.5, 2.5, 400)
    representative = float(r_nom[1]) if abs(r_nom[1]) > 1e-9 else 0.1
    intended = 0.05 * (rate / 0.2) ** 2
    implemented = 0.05 * ((rate - 2 * representative) / 0.2) ** 2
    axes[0, 1].plot(rate, intended, label="intended: 0.05*||rho/scale||^2", color="#1f77b4")
    axes[0, 1].plot(rate, implemented, label="as coded: 0.05*||(rho - 2*r_nom)/scale||^2", color="#d62728")
    axes[0, 1].axvline(0.0, color="#1f77b4", linestyle=":", linewidth=1.0)
    axes[0, 1].axvline(2 * representative, color="#d62728", linestyle=":", linewidth=1.0)
    axes[0, 1].annotate("minimum at rate = 0", (0.0, 0.2), fontsize=8, color="#1f77b4", rotation=90, va="bottom")
    axes[0, 1].annotate("minimum at rate = 2*r_nom", (2 * representative, 0.2), fontsize=8, color="#d62728", rotation=90, va="bottom")
    axes[0, 1].set(xlabel="realised control rate rho (channel 2, scaled units)", ylabel="rate cost (scaled)",
                   title=f"The coded term drives the rate to 2*r_nom = {2 * representative:.4f}, not to zero")
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(alpha=0.25)

    positions = np.arange(8)
    axes[1, 0].bar(positions - 0.2, coded, 0.4, label="as coded", color="#d62728")
    axes[1, 0].bar(positions + 0.2, corrected, 0.4, label="corrected", color="#1f77b4")
    axes[1, 0].set(xticks=positions, xticklabels=CHANNELS, ylabel="first control (absolute)",
                   title="First control from the same state, same QP, only the sign differs")
    axes[1, 0].tick_params(axis="x", labelsize=7.5, rotation=30)
    axes[1, 0].legend(fontsize=8)
    axes[1, 0].grid(axis="y", alpha=0.25)

    axes[1, 1].axis("off")
    lines = [
        "Rate-penalty sign defect — measured effect",
        "",
        f"probe tick                 : {report.get('probe_tick')}",
        f"reference distance         : {report.get('probe_reference_distance_m'):.3f} m",
        "",
        f"gradients exactly opposite : {report.get('gradients_exactly_opposite')}",
        f"coded gradient . r_nom     : {report.get('coded_rate_gradient_dot_r_nom'):+.6f}   (negative = REWARD)",
        f"correct gradient . r_nom   : {report.get('correct_rate_gradient_dot_r_nom'):+.6f}   (positive = penalty)",
        "",
        f"first-step change, coded   : {report.get('first_step_change_norm_coded'):.8f}",
        f"first-step change, correct : {report.get('first_step_change_norm_corrected'):.8f}",
        "",
        "channel 6 (steer 3) step   :",
        f"  coded   {coded[6]:+.8f}",
        f"  correct {corrected[6]:+.8f}",
        "",
        "Impact: this controller is pinned by 26 protocols and",
        "produced every R3, R4, G3, G0-G2 and R5-baseline run.",
        "The defect does NOT make the QP fail: it still solves,",
        "still passes all 21 audit items and every hard gate.",
        "",
        "Record: qp_rate_penalty_sign_defect_20260916.md",
    ]
    axes[1, 1].text(0.0, 1.0, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9.2,
                    transform=axes[1, 1].transAxes)

    figure.suptitle("QP control-rate penalty sign defect — evidence and measured effect", fontsize=13)
    figure.tight_layout(rect=(0, 0.01, 1, 0.95))
    names = []
    for suffix in ("png", "svg"):
        name = f"rate_penalty_sign_defect.{suffix}"
        figure.savefig(figure_dir / name, dpi=300 if suffix == "png" else None)
        names.append(name)
    plt.close(figure)

    manifest = {
        "science_status": "PASS_READ_ONLY_DEFECT_EVIDENCE",
        "figure_status": "PENDING_VISUAL_QA",
        "scope": "rate-penalty sign defect",
        "analysis_question": "Is the control-rate penalty sign wrong, and what does the wrong sign do?",
        "figures": [f"figures/{name}" for name in names],
        "fields": {"gradients": "rate-term gradient of the QP linear cost at the first horizon step",
                   "cost_shape": "intended versus coded rate cost as a function of the realised rate",
                   "first_control": "optimal first control from one fixed mid-route state"},
        "units": "control units; accel channels in m/s^2 scale, steering in rad scale",
        "statistics_convention": "deterministic single-state comparison, no sampling",
        "generating_script": "tools/rate_penalty_evidence_figures.py",
        "generating_script_sha256": sha(Path(__file__)),
        "source_files": [{"path": str(source.relative_to(PAPER)).replace("\\", "/"), "sha256": sha(source)}],
        "caption": "Evidence for the control-rate penalty sign defect. The coded linear term is a reward proportional to the nominal rate, so the quadratic drives the realised rate toward twice the nominal rate instead of toward zero.",
    }
    (source.parent / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (figure_dir / "README.md").write_text(
        "# 控制变化率惩罚符号缺陷——证据图\n\n"
        "四面板：①编码与修正两种符号的速率项梯度，**精确互为相反数**；"
        "②**编码版本实际最小化的代价**——最小点从`rate=0`移到`rate=2*r_nom`；"
        "③同一状态求解的首控制逐通道对比；④实测数字状态板。\n\n"
        "**必须与图同时引用**：该缺陷**不会让QP失败**——仍解得出、仍PASS、仍满足全部硬门与21项审计，"
        "只是把控制器推向相反方向。记录见`qp_rate_penalty_sign_defect_20260916.md`。\n",
        encoding="utf-8",
    )
    print("defect figures:", names)


def tracking_figures() -> None:
    from paper_v4_core.references import build_hairpin

    route = build_hairpin()
    series = []
    for run_rel, label, color in BUGGY_RUNS:
        record = track(PAPER / run_rel, route)
        if record is not None:
            series.append({"label": label, "color": color, "run": run_rel, **record})
    fixed = track(PAPER / FIXED_RUN, route)

    target = PAPER / "analysis/20260916_RATE_PENALTY_EFFECT_BUGGY_REFERENCE"
    figure_dir = target / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(2, 2, figsize=(15.0, 9.4))

    for item in series:
        axes[0, 0].plot(item["distance"], item["lateral"], color=item["color"], label=f"{item['label']} (defective controller)")
    axes[0, 0].axhline(0.0, color="black", linewidth=0.8)
    axes[0, 0].set(xlabel="reference distance (m)", ylabel="payload lateral error (m)",
                   title="Lateral error under the DEFECTIVE controller — three parameter points nearly coincide")
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(alpha=0.25)

    for item in series:
        axes[0, 1].plot(item["distance"], item["longitudinal"], color=item["color"], label=item["label"])
    axes[0, 1].axhline(0.0, color="black", linewidth=0.8)
    axes[0, 1].set(xlabel="reference distance (m)", ylabel="payload longitudinal error (m)",
                   title="Longitudinal error under the DEFECTIVE controller")
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(alpha=0.25)

    for item in series:
        axes[1, 0].plot(item["distance"], item["position"], color=item["color"], label=item["label"])
    axes[1, 0].set(xlabel="reference distance (m)", ylabel="payload position error (m)",
                   title="Position error norm under the DEFECTIVE controller")
    axes[1, 0].legend(fontsize=8)
    axes[1, 0].grid(alpha=0.25)

    axes[1, 1].axis("off")
    lines = ["Defective-version tracking reference (rate-penalty sign wrong)", ""]
    lines.append(f"{'run':28s} {'lat_end':>9s} {'pos_rmse':>9s} {'growth>44s':>11s}")
    for item in series:
        slope = np.polyfit(item["time"][item["time"] >= 44.0], item["lateral"][item["time"] >= 44.0], 1)[0]
        lines.append(f"{item['label']:28s} {item['lateral'][-1]:9.6f} {np.sqrt(np.mean(item['position']**2)):9.6f} {slope:11.6f}")
    lines += [
        "",
        "Three parameter points give nearly identical lateral drift",
        "(0.6683 / 0.6682 / 0.6735 m), which points at the controller",
        "defect rather than at parameter sensitivity.",
        "",
        "Corrected-controller run:",
        f"  {FIXED_RUN}",
        "  status: " + ("COMPLETED" if fixed is not None else "PENDING — still in flight, curve deliberately NOT drawn"),
        "",
        "No curve is extrapolated for the pending run (section 25.3).",
        "Old and new results must never be mixed into one claim.",
    ]
    axes[1, 1].text(0.0, 1.0, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=9.2,
                    transform=axes[1, 1].transAxes)

    figure.suptitle("Defective-version tracking reference and the pending corrected run", fontsize=13)
    figure.tight_layout(rect=(0, 0.01, 1, 0.95))
    names = []
    for suffix in ("png", "svg"):
        name = f"rate_penalty_effect_buggy_reference.{suffix}"
        figure.savefig(figure_dir / name, dpi=300 if suffix == "png" else None)
        names.append(name)
    plt.close(figure)

    manifest = {
        "science_status": "PASS_READ_ONLY_DEFECTIVE_VERSION_REFERENCE",
        "figure_status": "PENDING_VISUAL_QA",
        "scope": "defective-version tracking reference",
        "analysis_question": "How large is the late lateral deviation under the defective controller, and does it vary with the parameter point?",
        "figures": [f"figures/{name}" for name in names],
        "fields": {"lateral": "payload error projected on the reference heading (D1 convention)",
                   "longitudinal": "payload error along the reference heading",
                   "position": "payload position error norm"},
        "units": "m",
        "window": "whole route, 2379 ticks, 95.12831551628261 m of reference",
        "statistics_convention": "deterministic single runs; the three parameter points are coverage points, not statistical samples",
        "generating_script": "tools/rate_penalty_evidence_figures.py",
        "generating_script_sha256": sha(Path(__file__)),
        "source_files": [{"path": item["run"] + "/raw.npz", "sha256": sha(PAPER / item["run"] / "raw.npz")} for item in series],
        "caption": "Defective-version lateral drift. The three parameter points give nearly identical endpoint lateral errors, which supports the controller defect as the cause rather than parameter sensitivity. The corrected-controller run is in flight and its curve is deliberately not drawn.",
        "not_authorized": "This figure must not be read as a property of the candidate method: every curve here was produced with the defective rate-penalty sign.",
    }
    (target / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (figure_dir / "README.md").write_text(
        "# 缺陷版跟踪参考图\n\n"
        "三面板曲线：**缺陷控制器**（速率惩罚符号错误）下的货物横向误差、纵向误差、位置误差范数，"
        "覆盖 P0 名义(CPU)、P1(GPU)、P2(GPU) 三个参数点；第四面板为数字状态板。\n\n"
        "**核心观察**：三个参数点的横向漂移几乎相同（0.6683 / 0.6682 / 0.6735 m），"
        "指向**控制器缺陷**而非参数敏感性。\n\n"
        "**修复版运行仍在飞行中，按§25.3 其曲线不绘制、不外推**，仅标 `PENDING`。\n\n"
        "**不可误读**：本图全部曲线都由缺陷版本产生，**不得**当作候选方法的固有性质；"
        "旧新结果永不混算。\n",
        encoding="utf-8",
    )
    print("tracking figures:", names, "| fixed run available:", fixed is not None)


if __name__ == "__main__":
    defect_figures()
    tracking_figures()
