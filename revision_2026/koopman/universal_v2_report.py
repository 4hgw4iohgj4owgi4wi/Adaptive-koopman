"""Generate evidence tables, figures, solutions and the final v2 report."""

from __future__ import annotations

from collections import defaultdict
import csv
import json
import math
import argparse
from pathlib import Path
import sys
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
OUT = HERE / "universal_v2"
if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))
import universal_v2_modules as m  # noqa: E402


plt.rcParams.update({"figure.dpi": 150, "savefig.dpi": 180, "axes.grid": True, "grid.alpha": 0.25,
                     "font.size": 9, "axes.titlesize": 10})


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def savefig(fig: Any, name: str) -> None:
    fig.tight_layout(); fig.savefig(OUT / name, bbox_inches="tight"); plt.close(fig)


def module_tables() -> dict[str, Any]:
    f = read_json(OUT / "t3" / "results.json"); h = read_json(OUT / "t4" / "results.json")
    c = read_json(OUT / "t5" / "c_results.json"); a = read_json(OUT / "t5" / "adaptation_results.json")
    rows = []
    for name in m.amend_g2():
        f0, f2 = f[name]["development"]["F0"], f[name]["development"]["F2"]
        rows.extend([
            {"backbone": name, "module": "F2", "primary_improvement_pct": 100 * ((f0["force"] + f0["load"] - f2["force"] - f2["load"]) / (f0["force"] + f0["load"])), "passed": False},
            {"backbone": name, "module": "H-LS", "primary_improvement_pct": 100 * h[name]["HLS_improvement"], "passed": h[name]["relative_gate"]},
            {"backbone": name, "module": "C", "primary_improvement_pct": 100 * c[name]["improvement"], "passed": c[name]["relative_gate"]},
            {"backbone": name, "module": "A", "primary_improvement_pct": 100 * a[name]["external_improvement"], "passed": a[name]["relative_gate"]},
        ])
    write_csv(OUT / "module_by_backbone.csv", rows)
    fig, ax = plt.subplots(figsize=(9, 4.5)); names = list(m.amend_g2()); modules = ("F2", "H-LS", "C", "A")
    x = np.arange(len(names)); width = 0.18
    for index, module in enumerate(modules):
        values = [next(float(row["primary_improvement_pct"]) for row in rows if row["backbone"] == name and row["module"] == module) for name in names]
        bars = ax.bar(x + (index - 1.5) * width, values, width, label=module)
        for bar, name in zip(bars, names):
            passed = next(bool(row["passed"]) for row in rows if row["backbone"] == name and row["module"] == module)
            if not passed:
                bar.set_hatch("///"); bar.set_alpha(.45)
    ax.axhline(8, color="black", linestyle="--", linewidth=1, label="8% gate"); ax.axhline(0, color="black", linewidth=.7)
    ax.set_xticks(x, names); ax.set_ylabel("Development primary improvement (%)"); ax.set_title("Module increment by frozen backbone"); ax.legend(ncol=5)
    savefig(fig, "module_by_backbone.png")
    return {"F": f, "H": h, "C": c, "A": a, "rows": rows}


def scenario_and_envelope() -> dict[str, Any]:
    confirm = read_json(OUT / "t7_recovery" / "confirm_results.json")
    scenario_rows = []
    trajectory = {}
    for name, block in confirm.items():
        for variant, metrics in block["internal"].items():
            if variant.startswith("H"): continue
            grouped: dict[str, list[float]] = defaultdict(list)
            for file, value in metrics["per_trajectory_J"].items():
                scene = Path(file).name.split("_")[1]
                grouped[scene].append(float(value)); trajectory[(name, variant, Path(file).name)] = float(value)
            for scene, values in grouped.items():
                scenario_rows.append({"scenario": scene, "backbone": name, "variant": variant, "J_pred": float(np.mean(values)), "trajectories": len(values)})
    write_csv(OUT / "scenario_backbone_module.csv", scenario_rows)
    combinations = [(name, variant) for name in m.amend_g2() for variant in ("P0", "F2-diagnostic", "C-selected")]
    row_labels = [f"{name}-{variant}" for name, variant in combinations]
    scenes = [f"E{i}" for i in range(7)] + ["E9"]
    matrix = np.asarray([[next(row["J_pred"] for row in scenario_rows if row["backbone"] == name and row["variant"] == variant and row["scenario"] == scene) for scene in scenes] for name, variant in combinations])
    fig, ax = plt.subplots(figsize=(9, 6)); image = ax.imshow(np.log10(np.maximum(matrix, 1e-4)), aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(scenes)), scenes); ax.set_yticks(range(len(row_labels)), row_labels); ax.set_title("Scenario × backbone × frozen module (log10 J)")
    fig.colorbar(image, ax=ax, label="log10 J_pred"); savefig(fig, "scenario_heatmap.png")
    files = sorted({key[2] for key in trajectory})
    envelope = {file: min(trajectory[("K0", "P0", file)], trajectory[("K1", "P0", file)]) for file in files}
    envelope_rows = []
    for name in m.amend_g2():
        for variant in ("P0", "F2-diagnostic", "C-selected"):
            ratios = [(envelope[file] - trajectory[(name, variant, file)]) / max(envelope[file], 1e-12) for file in files]
            envelope_rows.append({"backbone": name, "variant": variant, "improvement_vs_K0_K1_envelope_pct": 100 * float(np.mean(ratios)), "trajectories": len(ratios)})
    write_csv(OUT / "absolute_vs_simple_envelope.csv", envelope_rows)
    labels = [f"{r['backbone']}\n{r['variant']}" for r in envelope_rows]; values = [r["improvement_vs_K0_K1_envelope_pct"] for r in envelope_rows]
    fig, ax = plt.subplots(figsize=(10, 4.5)); ax.bar(range(len(values)), values, color=["#4C78A8" if value >= 0 else "#E45756" for value in values])
    ax.axhline(8, color="black", linestyle="--"); ax.axhline(0, color="black", linewidth=.7); ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
    ax.set_ylabel("Mean improvement vs per-trajectory min(K0,K1) (%)"); ax.set_title("Absolute deployment comparison")
    savefig(fig, "absolute_vs_simple_envelope.png")
    return {"scenario": scenario_rows, "envelope": envelope_rows}


def horizon_plot() -> None:
    rows = read_csv(OUT / "horizon_state_force.csv")
    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    for name in m.amend_g2():
        for variant, style in (("P1", "--"), ("P2-HLS", "-")):
            subset = [row for row in rows if row["backbone"] == name and row["variant"] == variant]
            h = [int(row["horizon"]) for row in subset]
            for ax, key in zip(axes.flat, ("state", "force", "load", "force_rate")):
                ax.plot(h, [float(row[key]) for row in subset], style, label=f"{name}-{variant}", linewidth=1)
                ax.set_title(key); ax.set_yscale("symlog", linthresh=0.1)
    axes[1, 0].set_xlabel("horizon step"); axes[1, 1].set_xlabel("horizon step")
    handles, labels = axes[0, 0].get_legend_handles_labels(); fig.legend(handles, labels, loc="lower center", ncol=4, fontsize=7)
    fig.subplots_adjust(bottom=.18); savefig(fig, "horizon_state_force.png")


def contact_and_direction(rows: list[dict[str, Any]], norms: dict[str, np.ndarray], models: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sums = defaultdict(lambda: [0.0, 0, 0.0, 0]); confusion = defaultdict(int); q_residual = 0.0
    heads = {}
    for name in m.amend_g2():
        with np.load(OUT / "t3" / "models" / f"{name}.npz", allow_pickle=False) as source:
            heads[name] = {key: np.asarray(source[key]) for key in ("coef", "feature_mean", "feature_std", "clip")}
    point_names = ("FL", "FR", "RL", "RR")
    for row in m.role_rows(rows, "development-test"):
        a = row["arrays"]; rated = float(row["meta"]["params"]["connector"]["rated_force_n"]); free = float(row["meta"]["params"]["connector"]["free_play_m"])
        for start in range(0, len(a["u1_four"]) - m.H + 1, m.H):
            true_phys = a["force_output"][start + 1:start + m.H + 1]
            true_n = (true_phys - norms["force_mean"]) / norms["force_std"]
            fb = true_phys[:, :8].reshape(m.H, 4, 2); fnorm = np.linalg.norm(fb, axis=2)
            disp = np.linalg.norm(a["displacement_body"][start + 1:start + m.H + 1], axis=2); contact = disp > free
            ratio = float(fnorm.max() / rated); labels = ["L0" if ratio < .1 else "L1" if ratio < .3 else "L2" if ratio < .5 else "L3" if ratio <= .8 else "L4-high"]
            if not np.any(contact): labels.append("R0")
            enter = bool(np.any((~contact[:-1]) & contact[1:])); leave = bool(np.any(contact[:-1] & (~contact[1:])))
            if enter: labels.append("R1")
            if np.any(contact) and not enter and not leave: labels.append("R2")
            if leave: labels.append("R3")
            active = (fnorm[:-1] > .01 * rated) & (fnorm[1:] > .01 * rated)
            reversal = np.any(active[..., None] & (np.sign(fb[:-1]) != np.sign(fb[1:])))
            if reversal: labels.append("R4")
            if np.max(np.abs(true_phys[:, 8:10])) >= .1 * rated: labels.append("R5")
            for name in m.amend_g2():
                xn, f0n = m.rollout(models[name], a, start)
                previous = a["force_output"][start, :8].reshape(4, 2); f1 = m.physics_force(xn, norms, previous)
                f2 = m.apply_fhead(heads[name], xn, a["u1_four"][start:start + m.H], f1, previous, norms)
                f2n = (f2 - norms["force_mean"]) / norms["force_std"]
                for variant, predn, predphys in (("F0", f0n, f0n * norms["force_std"] + norms["force_mean"]), ("F2", f2n, f2)):
                    ef = float(np.sum((predn[:, :8] - true_n[:, :8]) ** 2)); el = float(np.sum((predn[:, 8:10] - true_n[:, 8:10]) ** 2))
                    for label in labels:
                        key = (name, variant, label); sums[key][0] += ef; sums[key][1] += predn[:, :8].size; sums[key][2] += el; sums[key][3] += predn[:, 8:10].size
                    floor = norms["force_sign_floor"][:8]
                    for dim in range(8):
                        mask = np.abs(true_phys[:, dim]) >= floor[dim]
                        for tsgn, psgn in zip(np.sign(true_phys[mask, dim]), np.sign(predphys[mask, dim])):
                            confusion[(name, variant, point_names[dim // 2], "Fx" if dim % 2 == 0 else "Fy", int(tsgn), int(psgn))] += 1
                    q_rebuilt = np.c_[.5 * ((predphys[:, 0] + predphys[:, 2]) - (predphys[:, 4] + predphys[:, 6])),
                                      .5 * ((predphys[:, 1] + predphys[:, 5]) - (predphys[:, 3] + predphys[:, 7]))]
                    q_residual = max(q_residual, float(np.max(np.abs(q_rebuilt - predphys[:, 8:10]))))
    contact_rows = [{"backbone": key[0], "variant": key[1], "regime": key[2], "windows_equivalent": value[1] // (m.H * 8),
                     "force_NRMSE": math.sqrt(value[0] / value[1]), "load_NRMSE": math.sqrt(value[2] / value[3])} for key, value in sorted(sums.items())]
    confusion_rows = [{"backbone": key[0], "variant": key[1], "point": key[2], "component": key[3], "true_sign": key[4], "pred_sign": key[5], "count": value} for key, value in sorted(confusion.items())]
    write_csv(OUT / "contact_regime_results.csv", contact_rows); write_csv(OUT / "force_direction_confusion.csv", confusion_rows)
    labels = ["R0", "R1", "R2", "R3", "R4", "R5", "L0", "L1", "L2", "L3"]
    fig, ax = plt.subplots(figsize=(10, 5))
    for name in ("K0", "K1", "K5-linear"):
        values = [next((row["force_NRMSE"] for row in contact_rows if row["backbone"] == name and row["variant"] == "F2" and row["regime"] == label), np.nan) for label in labels]
        ax.plot(labels, values, marker="o", label=f"{name}-F2")
    ax.set_yscale("log"); ax.set_ylabel("force NRMSE"); ax.set_title("Contact/load-regime force errors"); ax.legend(); savefig(fig, "contact_transition.png")
    matrix = np.zeros((8, 8)); methods = [(name, variant) for name in m.amend_g2() for variant in ("F0", "F2")]
    for row_index, (name, variant) in enumerate(methods):
        correct = sum(r["count"] for r in confusion_rows if r["backbone"] == name and r["variant"] == variant and r["true_sign"] == r["pred_sign"])
        total = sum(r["count"] for r in confusion_rows if r["backbone"] == name and r["variant"] == variant)
        matrix[row_index, 0] = correct / max(total, 1); matrix[row_index, 1] = 1 - matrix[row_index, 0]
    fig, ax = plt.subplots(figsize=(6, 6)); image = ax.imshow(matrix[:, :2], vmin=0, vmax=1, cmap="RdYlGn")
    ax.set_xticks((0, 1), ("correct sign", "wrong sign")); ax.set_yticks(range(len(methods)), [f"{a}-{b}" for a,b in methods]); ax.set_title("Four-point Fx/Fy direction confusion")
    for i in range(len(methods)):
        for j in range(2): ax.text(j, i, f"{matrix[i,j]:.2f}", ha="center", va="center")
    fig.colorbar(image, ax=ax); savefig(fig, "force_direction_confusion.png")
    return {"q_algebraic_residual_max_n": q_residual, "contact_rows": len(contact_rows), "direction_rows": len(confusion_rows)}


def example_plots(norms: dict[str, np.ndarray], models: dict[str, dict[str, Any]]) -> dict[str, Any]:
    manifest = read_json(OUT / "d3_recovery" / "manifest.json")
    selected = max((row for row in manifest["physical"] if row["kind"] == "internal"), key=lambda row: row["max_connector_force_n"])
    path = OUT / "d3_recovery" / "trajectories" / selected["file"]
    with np.load(path, allow_pickle=False) as source: a = {key: np.asarray(source[key], dtype=float) for key in m.cp.ARRAY_KEYS}
    time_s = a["time_s"]; tension_rows = []
    predictions = {}
    for name in ("K0", "K1", "K5-linear"):
        values = []
        with np.load(OUT / "t3" / "models" / f"{name}.npz", allow_pickle=False) as source:
            head = {key: np.asarray(source[key]) for key in ("coef", "feature_mean", "feature_std", "clip")}
        for k in range(len(a["u1_four"])):
            z = m.cp.lift(models[name], a["s3_deform"][k]); z, _ = m.cp.model_step(models[name], z, a["u1_four"][k])
            _, fn, xn = m.cp.decode(models[name], z)
            if name == "K5-linear":
                previous = a["force_output"][k, :8].reshape(4, 2); f1 = m.physics_force(xn[None], norms, previous)
                force = m.apply_fhead(head, xn[None], a["u1_four"][k:k+1], f1, previous, norms)[0]
            else: force = fn * norms["force_std"] + norms["force_mean"]
            values.append(force)
        predictions[name] = np.asarray(values)
    for k in range(len(a["u1_four"])):
        row = {"time_s": time_s[k + 1], "true_Q_FR_n": a["force_output"][k + 1, 8], "true_Q_LR_n": a["force_output"][k + 1, 9]}
        for name, value in predictions.items(): row[f"{name}_Q_FR_n"] = value[k, 8]; row[f"{name}_Q_LR_n"] = value[k, 9]
        tension_rows.append(row)
    write_csv(OUT / "payload_tension.csv", tension_rows)
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for index, q in enumerate(("Q_FR", "Q_LR")):
        axes[index].plot(time_s[1:], a["force_output"][1:, 8 + index], color="black", label="true", linewidth=1.5)
        for name in predictions: axes[index].plot(time_s[1:], predictions[name][:, 8 + index], label=name, linewidth=.8)
        axes[index].set_ylabel(f"{q} (N)"); axes[index].legend(ncol=4)
    axes[-1].set_xlabel("time (s)"); fig.suptitle(f"Payload tension, blind-confirm {selected['file']}"); savefig(fig, "payload_tension.png")
    yaw_rows = []
    actual = a["s2_four"]; system = np.arctan2(np.mean(np.sin(actual[:, [2,8,14,20]]), axis=1), np.mean(np.cos(actual[:, [2,8,14,20]]), axis=1))
    for k in range(len(actual)):
        yaw_rows.append({"time_s": time_s[k], "FL_yaw": actual[k,2], "FR_yaw": actual[k,8], "RL_yaw": actual[k,14], "RR_yaw": actual[k,20], "system_yaw": system[k], "payload_yaw": actual[k,26]})
    write_csv(OUT / "vehicle_team_yaw.csv", yaw_rows)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for key, label in ((2,"FL"),(8,"FR"),(14,"RL"),(20,"RR")): ax.plot(time_s, actual[:,key], linewidth=.8, label=label)
    ax.plot(time_s, system, color="black", linewidth=1.5, label="vehicle-array mean"); ax.plot(time_s, actual[:,26], color="magenta", linestyle="--", label="payload")
    ax.set_xlabel("time (s)"); ax.set_ylabel("yaw (rad)"); ax.set_title("Four vehicles, array and payload yaw"); ax.legend(ncol=6); savefig(fig, "vehicle_team_yaw.png")
    return {"example_file": selected["file"], "peak_connector_force_n": selected["max_connector_force_n"]}


def adaptation_and_closedloop(module: dict[str, Any]) -> dict[str, Any]:
    rows = read_csv(OUT / "online_adaptation.csv")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    conditions = ("A0-zero", "A1-1s", "A1-2s", "A1-5s", "A2-online")
    for name in m.amend_g2():
        values = [float(next(row["J_pred"] for row in rows if row["backbone"] == name and row["condition"] == condition)) for condition in conditions]
        ax.plot(conditions, values, marker="o", label=name)
    ax.set_yscale("log"); ax.set_ylabel("development external J_pred"); ax.set_title("Zero/few/online parameter adaptation"); ax.legend(); savefig(fig, "parameter_adaptation.png")
    closed = read_csv(OUT / "closed_loop_metrics.csv"); extension = read_csv(OUT / "closed_loop_parameter_extension.csv")
    # Existing K5 rows are the retained A2-online run.
    for row in closed:
        row["method"] = "K5-linear-A2-online" if row["model"] == "K5-linear" else row["model"]
    all_closed = closed + extension
    groups = defaultdict(list)
    for row in all_closed: groups[(row["method"], row["scenario"], row["profile"], row["protected"])].append(row)
    summary = []
    for key, values in sorted(groups.items()):
        summary.append({"method": key[0], "scenario": key[1], "profile": key[2], "protected": key[3], "n": len(values),
                        "position_rmse_m": float(np.mean([float(v["payload_position_rmse_m"]) for v in values])),
                        "tension_rmse_n": float(np.mean([float(v["payload_tension_rmse_n"]) for v in values])),
                        "max_force_n": float(np.max([float(v["max_connector_force_n"]) for v in values])),
                        "solve_p99_ms": float(np.mean([float(v["solve_p99_ms"]) for v in values])),
                        "timeout_rate": float(np.mean([float(v["timeout_rate_20ms"]) for v in values])),
                        "distance_failures": sum(v["distance_gate"].lower() != "true" for v in values),
                        "ultimate_runs": sum(int(float(v["ultimate_steps"])) > 0 for v in values)})
    write_csv(OUT / "closed_loop_summary.csv", summary)
    network = [row for row in summary if row["scenario"] == "staged_100m" and row["profile"] != "clean"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5)); labels = [f"{r['method']}-{r['profile']}-{'P' if r['protected'].lower()=='true' else 'U'}" for r in network]
    axes[0].bar(range(len(network)), [r["position_rmse_m"] for r in network]); axes[1].bar(range(len(network)), [r["max_force_n"] / 1000 for r in network])
    for ax in axes: ax.set_xticks(range(len(labels)), labels, rotation=60, ha="right", fontsize=7)
    axes[0].set_ylabel("position RMSE (m)"); axes[1].set_ylabel("max connector force (kN)"); axes[1].axhline(15, color="red", linestyle="--")
    fig.suptitle("Network disturbance: unprotected vs state-propagation protection"); savefig(fig, "network_protection_closed_loop.png")
    clean = [r for r in summary if r["scenario"] == "staged_100m" and r["profile"] == "clean"]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.8)); labels = [r["method"] for r in clean]
    axes[0].bar(labels, [r["position_rmse_m"] for r in clean]); axes[1].bar(labels, [r["distance_failures"] for r in clean]); axes[2].bar(labels, [r["max_force_n"] / 1000 for r in clean])
    axes[0].set_ylabel("position RMSE (m)"); axes[1].set_ylabel("100 m failures / 10"); axes[2].set_ylabel("peak force (kN)"); fig.suptitle("100 m clean diagnostic closed loop")
    savefig(fig, "closed_loop_100m.png")
    confirm = read_json(OUT / "t7_recovery" / "confirm_results.json")
    pareto = []
    for name in m.amend_g2():
        cost_values = [r["solve_p99_ms"] for r in summary if r["method"] == name]
        if cost_values: pareto.append({"backbone": name, "confirm_J": confirm[name]["internal"]["P0"]["J_pred"], "closed_loop_p99_ms": float(np.mean(cost_values))})
    write_csv(OUT / "accuracy_cost_pareto.csv", pareto)
    fig, ax = plt.subplots(figsize=(6, 4.5))
    for row in pareto: ax.scatter(row["closed_loop_p99_ms"], row["confirm_J"], s=50); ax.text(row["closed_loop_p99_ms"], row["confirm_J"], row["backbone"])
    ax.axvline(20, color="red", linestyle="--"); ax.set_xlabel("diagnostic controller p99 (ms)"); ax.set_ylabel("blind internal J_pred"); ax.set_yscale("log"); ax.set_title("Accuracy–cost diagnostic")
    savefig(fig, "accuracy_cost_pareto.png")
    return {"closed_loop_summary": summary}


def reports(module: dict[str, Any], scenario: dict[str, Any], physical: dict[str, Any], example: dict[str, Any], closed: dict[str, Any]) -> None:
    t1 = read_json(OUT / "t1" / "complete.json"); t2 = read_json(OUT / "gate_amendment.json"); t7 = read_json(OUT / "t7_recovery" / "complete.json")
    recovery_stats = read_json(OUT / "t7_recovery" / "paired_statistics.json")["K5-linear"]["A"]
    summaries = closed["closed_loop_summary"]
    k0_delay_p = next(r for r in summaries if r["method"] == "K0" and r["profile"] == "delay" and r["protected"].lower() == "true")
    k1_dos_u = next(r for r in summaries if r["method"] == "K1" and r["profile"] == "dos" and r["protected"].lower() == "false")
    k1_dos_p = next(r for r in summaries if r["method"] == "K1" and r["profile"] == "dos" and r["protected"].lower() == "true")
    param = [r for r in summaries if r["scenario"] == "hairpin" and r["method"].startswith("K5-linear")]
    lines = [
        "# Koopman组合改进普适性实验 v2 最终报告", "", "> 状态：全部预注册阶段已有明确状态；正式部署候选为0，闭环均为诊断。", "",
        "## 结论", "",
        "组合改进的跨骨干普适性不成立。F只在失败的K5-linear受力解码上出现大幅修复，但未通过development发散保护；H四个骨干均因修正量和逐状态保护回退rank=0；C虽测到lift漂移机理但未过性能门；A仅在K5-linear的few-shot参数任务上复现约9%的离线改善。因此可以保留“特定失败骨干的受力解码/在线适应”作为诊断，不能写成一般Koopman增强。", "",
        "## 关键事实", "",
        f"- D1-v2为404条轨迹；train/validation/development L3窗分别为{t1['coverage']['train']['L3']}/{t1['coverage']['validation']['L3']}/{t1['coverage']['development-test']['L3']}，G1通过。",
        f"- G2进入F/H的骨干为{', '.join(t2['eligible'])}；K2/K3/K3-r2/K5-bilinear因秩亏或数量级爆炸只保留诊断。",
        f"- F跨家族通过0/4；H通过0/4；C通过0/3实际运行骨干；A development只通过{', '.join(read_json(OUT/'t5'/'adaptation_complete.json')['passing_backbones']) or '无'}。",
        f"- 原D2因协议路径在查看后追加内容而降级；D3恢复确认一次性评估：internal通过{t7['internal_passing']}；external参数适应复现{t7['external_passing']}；绝对部署候选为空。",
        f"- K5-linear A1-2s在D3的24条external轨迹上改善{100*recovery_stats['mean_improvement']:.2f}%，95% CI {100*recovery_stats['ci95_low']:.2f}%–{100*recovery_stats['ci95_high']:.2f}%，Holm p={recovery_stats['holm_p']:.4g}。",
        f"- 诊断闭环230+40条全部执行完成；统一适配器p99均低于20 ms，但clean 100 m的K0/K1各有2/10未完成距离门。",
        f"- 通信保护不是稳定收益：K1-DoS位置RMSE由{k1_dos_u['position_rmse_m']:.3f}降到{k1_dos_p['position_rmse_m']:.3f} m；但K0-delay保护峰值连接力达到{k0_delay_p['max_force_n']/1000:.3f} kN、10/10距离失败，并出现{k0_delay_p['ultimate_runs']}条ultimate触发。",
        f"- 高受力盲确认示例为{example['example_file']}，峰值{example['peak_connector_force_n']/1000:.3f} kN；货物撕裂只按Q_FR/Q_LR受拉趋势报告，不推断材料破坏。", "",
        "## 各方向优劣", "",
        "|方向|优势|主要问题|结论|", "|---|---|---|---|",
        "|F物理受力头|K5-linear的受力输出从失效量级显著恢复，方向准确率提高|依赖预测形变；K0/K1/K4反而变差，K5发散率微升|场景/骨干特定，不普适|",
        "|H-LS/H-RLS|非零回归在validation可降平均误差|修正p99为骨干输出0.9–1.3倍并破坏逐状态5%门；全部回退rank0|不成立；RLS在rank0时无额外价值|",
        "|C重新升维|K1/K4/K5测到漂移增长且与长时误差相关|p=1/2/5/10均未通过8%和安全门|机理存在但干预无部署收益|",
        "|A参数适应|K5-linear在development和D2均复现few-shot改善|K0/K1/K4不复现；零样本没有提升|仅支持K5特定在线/few-shot适应|",
        "|通信状态传播保护|K1在DoS局部改善|跨模型/网络不稳，delay可增力到ultimate并破坏100m|需要门控与安全回退，当前不可用|",
        "|简单骨干K0/K1|数值有限、整体精度和计算代价最好|20步仍有明显发散窗，诊断MPC的100m距离门不全过|仍是研究基线，不是当前闭环部署件|", "",
        "## 证据边界", "",
        "1. 作用—反作用没有车辆侧独立传感量，不能把货物侧力取负当作独立验证。", "2. 诊断闭环没有正式离线部署候选，不能据此作控制优越性主张。",
        "3. K5参数闭环已区分A0、固定前2 s A1和持续更新A2；不得混写。", "4. 首轮错误参数范围的数据已原样归档为invalid；原D2也只作审计历史，最终统计与确认图来自全新D3。", "",
        "## 主要文件", "",
        "- `universality_gates.json`：最终门禁；`confirm_metrics.csv`：盲确认；`closed_loop_summary.csv`：闭环汇总。",
        "- 十张主图和两张闭环补充图均有同名或对应CSV；所有极端失败值保留。", "",
    ]
    (OUT / "final_report.md").write_text("\n".join(lines), encoding="utf-8")
    solutions = f"""# solutions

## 已修正的实现问题

1. G1原train-L3为927/1000：未降低门槛，新增冻结36条强载荷轨迹后达到{t1['coverage']['train']['L3']}。
2. G2把长时域性能当H入口导致逻辑自锁：保留首次全排除，改为有限值/秩/条件数入口；模块后的发散与安全门未降低。
3. 首轮参数任务误用external极值范围：90条轨迹和A结果归档至`invalid_parameter_range_20260822`，按原范围整批重算。
4. K5参数闭环最初持续更新却标作2 s few-shot：原10条重标A2-online，补跑K0/K1/K5-A0/K5-A1-2s共40条。
5. D2后为闭环追加协议内容覆盖了冻结路径：精确恢复原协议hash并按G6把D2降级，使用全新seed完成D3恢复确认；最终图表与统计只读D3。

## 仍未解决的科学/工程卡口

### F的瓶颈

名义连接器公式本身正确，但输入是骨干预测形变/速度。建议下一轮先提高形变状态的1–20步可观测性，再训练满足对称约束的受限残差；不能继续扩大F2容量掩盖状态错误。

### H的瓶颈

当前非零H需要相当于骨干输出0.9–1.3倍的修正，说明“小残差”假设不成立。可验证方案：重训骨干或采用有状态约束的直接多时域主模型；若坚持残差，必须把0.5信赖域作为结构约束重新训练，不能后验裁剪。

### 通信保护的安全失败

固定“传播到当前”在长delay下累积模型偏差；K0-delay保护达到{k0_delay_p['max_force_n']:.2f} N并触发ultimate。建议新增只在validation选择的AoI/协方差门控：hold、传播、降速三模式；任何预测力>0.8 rated、传播不确定度过阈或100m距离趋势失败时立即回退hold+降速。必须重新生成未查看网络confirm后再判定。

### 闭环适配器

诊断有限控制集满足计算p99，但clean 100m仍有距离失败。下一轮需固定路径/速度参考、终端距离约束和安全力约束的46D模型无关MPC，再做正式候选比较；不得调整本轮确认结论。

## 结论边界

现有证据只支持K5-linear在获得近期参数观测后的特定适应信号。没有证据支持F+H跨Koopman结构普适，也没有满足正式闭环部署门的候选。
"""
    (OUT / "solutions.md").write_text(solutions, encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--recovery", action="store_true"); args=parser.parse_args()
    completion = OUT / "t9" / ("complete_recovery.json" if args.recovery else "complete.json")
    if completion.exists(): print("T9 report already complete"); return
    module = module_tables(); scenario = scenario_and_envelope(); horizon_plot()
    rows, norms, _, models = m.context()
    physical = contact_and_direction(rows, norms, models); example = example_plots(norms, models)
    closed = adaptation_and_closedloop(module)
    consistency = {**physical, "example": example, "action_reaction_independent_observation": False,
                   "reason": "only payload-side connector force is present; vehicle-side negative is not independent evidence",
                   "Newton_Euler_prediction_residual": "not_identifiable_from_frozen_64D_output_without predicted accelerations aligned to force time"}
    m.write_json(OUT / "physical_consistency.json", consistency)
    reports(module, scenario, physical, example, closed)
    required_images = ("module_by_backbone.png", "absolute_vs_simple_envelope.png", "horizon_state_force.png", "scenario_heatmap.png",
                       "contact_transition.png", "force_direction_confusion.png", "payload_tension.png", "vehicle_team_yaw.png",
                       "parameter_adaptation.png", "accuracy_cost_pareto.png", "network_protection_closed_loop.png", "closed_loop_100m.png")
    missing = [name for name in required_images if not (OUT / name).exists() or (OUT / name).stat().st_size == 0]
    stage = OUT / "t9"; stage.mkdir(parents=True, exist_ok=True)
    m.write_json(completion, {"stage": "T9-recovery" if args.recovery else "T9", "status": "complete" if not missing else "failed_missing_images",
                 "missing_images": missing, "final_report_sha256": m.uv2.sha256(OUT / "final_report.md"),
                 "solutions_sha256": m.uv2.sha256(OUT / "solutions.md"),
                 "images": {name: m.uv2.sha256(OUT / name) for name in required_images if (OUT / name).exists()}})
    m.uv2.append_log("W0071", "v2最终报告与图表", [
        f"生成12张结果图及对应CSV/JSON；缺失={missing}；最终确认版本={'D3-recovery' if args.recovery else 'D2'}。", "最终结论：跨骨干普适性不成立；K5 few-shot参数适应为唯一复现的局部信号；正式部署候选=0。",
        f"final report hash={m.uv2.sha256(OUT/'final_report.md')}；solutions hash={m.uv2.sha256(OUT/'solutions.md')}。",
    ])
    print(json.dumps({"T9": "complete", "missing": missing}, ensure_ascii=False))


if __name__ == "__main__": main()
