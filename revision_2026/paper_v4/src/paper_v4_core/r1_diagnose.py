"""EXP-R2 R1: offline relative-motion and internal-load diagnosis only."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .cli import save, sha
from .diagnostics.internal_loading import decompose
from .diagnostics.relative_motion import extract
from .e01_100m import params
from .plant.four_vehicle_common import rotation
from .reference_geometry import transition_targets
from .references import build_hairpin


PATH = build_hairpin()


def _load(folder):
    with np.load(folder / "raw.npz", allow_pickle=False) as z:
        raw = z["values"]
        columns = [str(v) for v in z["columns"]]
    metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
    return raw, {name: i for i, name in enumerate(columns)}, metrics


def _phase(distance, curvature):
    b = PATH["boundaries_m"]
    if abs(curvature) < 1e-8:
        return "straight"
    if distance < b[2]:
        return "entry_transition"
    if distance < b[3]:
        return "constant_turn"
    return "exit_transition"


def _reference_at_endpoint(row, index, model):
    if "reference_beta0" not in index:
        beta = np.zeros(4)
        q = model.payload_anchor_body_m - np.asarray(model.vehicle_anchor_body_m)
        return q, beta
    beta_start = np.asarray([row[index[f"reference_beta{i}"]] for i in range(4)])
    dt = float(row[index["time_s"]] - row[index["interval_start_time_s"]])
    speed = float(row[index["reference_speed_start_mps"]])
    if "allocated_yaw_rate_radps" in index:
        yaw = float(row[index["allocated_yaw_rate_radps"]])
    elif "route_yaw_rate_radps" in index:
        yaw = float(row[index["route_yaw_rate_radps"]])
    else:
        yaw = speed * float(row[index["reference_curvature_1pm"]])
    target = transition_targets(np.asarray([speed, 0.0]), yaw, beta_start, model)
    beta = beta_start + dt * target["beta_dot"]
    target_end = transition_targets(np.asarray([speed, 0.0]), yaw, beta, model)
    return target_end["centers"], beta


def _first_sustained(time_s, signal, baseline_count=50, fraction=0.2, hold_s=1.0):
    signal = np.asarray(signal, dtype=float)
    baseline = float(np.median(signal[: min(len(signal), baseline_count)]))
    threshold = baseline + fraction * max(float(np.max(signal)) - baseline, 0.0)
    dt = float(np.median(np.diff(time_s))) if len(time_s) > 1 else hold_s
    count = max(1, int(np.ceil(hold_s / max(dt, 1e-12))))
    mask = signal >= threshold
    run = np.convolve(mask.astype(int), np.ones(count, dtype=int), mode="valid")
    hits = np.flatnonzero(run == count)
    return (None if len(hits) == 0 else float(time_s[hits[0]])), threshold


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def diagnose(sources, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    relative_rows, force_rows, summaries, series = [], [], [], []
    for label, folder in sources:
        raw, idx, metrics = _load(folder)
        model = params(str(metrics.get("parameter_id", "P0")))
        local_rel, local_force = [], []
        for row in raw:
            state = np.asarray([row[idx[f"x{i}"]] for i in range(30)])
            q_star, beta_star = _reference_at_endpoint(row, idx, model)
            rel = extract(state, model, q_star, beta_star)
            force_body = np.asarray([row[idx[f"payload_force_body_{i}"]] for i in range(8)]).reshape(4, 2)
            internal = decompose(force_body, model.payload_anchor_body_m, state[26], rel["connector_relative_velocity_world_mps"])
            t = float(row[idx["time_s"]]); distance = float(row[idx.get("reference_distance_m", idx["time_s"])]); curvature = float(row[idx["reference_curvature_1pm"]]) if "reference_curvature_1pm" in idx else 0.0
            rr = {"run": label, "time_s": t, "phase": _phase(distance, curvature), "reference_distance_m": distance}
            fr = {"run": label, "time_s": t, "phase": rr["phase"], "reference_distance_m": distance, "internal_force_norm_n": float(internal["internal_force_norm_n"]), "wrench_fx_n": float(internal["wrench_n_nm"][0]), "wrench_fy_n": float(internal["wrench_n_nm"][1]), "wrench_mz_nm": float(internal["wrench_n_nm"][2]), "tension_x_n": float(internal["tension_x_n"]), "tension_y_n": float(internal["tension_y_n"]), "tire_max_utilization": float(max(row[idx[f"tire_raw_utilization_{i}"]] for i in range(4)))}
            for i in range(4):
                rr.update({f"eg{i}_x_m": float(rel["e_g_m"][i, 0]), f"eg{i}_y_m": float(rel["e_g_m"][i, 1]), f"ebeta{i}_rad": float(rel["e_beta_rad"][i]), f"relv{i}_x_mps": float(rel["relative_velocity_body_mps"][i, 0]), f"relv{i}_y_mps": float(rel["relative_velocity_body_mps"][i, 1]), f"gap{i}_m": float(rel["connector_gap_m"][i]), f"normal_speed{i}_mps": float(rel["connector_normal_speed_mps"][i])})
                fr.update({f"force{i}_x_n": float(force_body[i, 0]), f"force{i}_y_n": float(force_body[i, 1]), f"internal{i}_x_n": float(internal["internal_force_vector_n"][2*i]), f"internal{i}_y_n": float(internal["internal_force_vector_n"][2*i+1]), f"pair_power{i}_w": float(internal["connector_pair_power_w"][i])})
            local_rel.append(rr); local_force.append(fr)
        relative_rows.extend(local_rel); force_rows.extend(local_force)
        t = np.asarray([r["time_s"] for r in local_rel]); eg = np.asarray([max(np.hypot(r[f"eg{i}_x_m"], r[f"eg{i}_y_m"]) for i in range(4)) for r in local_rel]); rv = np.asarray([max(np.hypot(r[f"relv{i}_x_mps"], r[f"relv{i}_y_mps"]) for i in range(4)) for r in local_rel]); fint = np.asarray([r["internal_force_norm_n"] for r in local_force]); tire = np.asarray([r["tire_max_utilization"] for r in local_force])
        onsets = {}
        for name, signal in (("configuration", eg), ("relative_velocity", rv), ("internal_force", fint), ("tire_utilization", tire)):
            onsets[name], threshold = _first_sustained(t, signal); onsets[name + "_threshold"] = threshold
        common = np.asarray([row[idx["common_accel_mps2"]] if "common_accel_mps2" in idx else 0.0 for row in raw]); actual_acc = np.asarray([[row[idx[f"accel{i}"]] for i in range(4)] for row in raw]); differential = actual_acc - common[:, None]
        final_diff_violation = float(max(0.0, np.max(np.abs(differential)) - 0.8))
        summaries.append({"run": label, "source": str(folder), "source_metrics_status": metrics.get("status"), "terminal_time_uncertain": label != "100m_nominal", "max_e_g_m": float(np.max(eg)), "max_relative_velocity_mps": float(np.max(rv)), "max_internal_force_n": float(np.max(fint)), "max_tire_utilization": float(np.max(tire)), "differential_acceleration_abs_max_mps2": float(np.max(np.abs(differential))), "declared_0p8_violation_mps2": final_diff_violation, "onsets": onsets})
        series.append((label, t, eg, rv, fint, tire))

    _write_csv(out / "relative_motion.csv", relative_rows)
    _write_csv(out / "force_decomposition.csv", force_rows)
    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=False, constrained_layout=True)
    for label, t, eg, rv, fint, tire in series:
        axes[0].plot(t, eg, label=label); axes[1].plot(t, rv, label=label); axes[2].plot(t, fint, label=label); axes[3].plot(t, tire, label=label)
    axes[0].set_ylabel("max |e_g| (m)"); axes[1].set_ylabel("max relative speed (m/s)"); axes[2].set_ylabel("|f_int| (N)"); axes[3].set_ylabel("max tire utilization"); axes[3].set_xlabel("recorded endpoint time (s)")
    for ax in axes: ax.grid(True, alpha=.25); ax.legend(fontsize=7, ncol=2)
    fig.suptitle("EXP-R2 R1 failure timeline (legacy terminal intervals shaded by uncertainty in report)")
    fig.savefig(out / "failure_timeline.png", dpi=180); plt.close(fig)

    order_lines=[]
    for item in summaries:
        ordered=sorted(((k,v) for k,v in item["onsets"].items() if not k.endswith("_threshold")),key=lambda kv: float("inf") if kv[1] is None else kv[1])
        order_lines.append(f"- {item['run']}: " + " → ".join(f"{k}={v:.3f}s" if v is not None else f"{k}=未检出" for k,v in ordered))
    violation=[s for s in summaries if s["declared_0p8_violation_mps2"]>1e-12]
    report = """# R1 离线构形与内力归因\n\n## 裁定\n\n本分析只重算既有三条失败轨迹和100m名义轨迹，没有运行新动力学。三条回头弯旧日志的最后已接受区间在旧记录器中可能缺失，因此末端区域统一视为 `FINAL_STATE_TIME_UNCERTAIN`；图表不能用于宣称15 kN附近的连续时间峰值已经收敛。\n\n现有证据支持：总体货物运动量不能代表四点内部载荷；几何参考残差小不等于实际构形误差小。阈值越过顺序只是定位线索，不构成因果证明。\n\n## 20%幅度、持续1秒的诊断阈值越过顺序\n\n""" + "\n".join(order_lines) + "\n\n## 额外审计\n\n" + ("差动加速度最终值越过声明的±0.8 m/s²，属于代码合同错误，必须先修。" if violation else "三条旧回头弯记录中，最终差动加速度未越过声明的±0.8 m/s²；仍不能以此证明控制充分。") + "\n\n`connector_pair_power_w` 定义为一对等大反向连接力对两端相对运动的总功率；负值表示该连接对相对运动耗散。`f_int` 是四点平面抓取矩阵零空间投影，和净合力/净力矩分开。\n\n## 数据身份\n\n- relative_motion.csv：真实记录端点状态重算的逐车构形、相对航向/速度和连接形变。\n- force_decomposition.csv：逐点力、净扳手、零空间内力、左右拉伸代理和连接功率。\n- failure_timeline.png：四组诊断量的时间线；旧失败末端时间不确定性须结合本报告解释。\n"
    (out / "diagnosis.md").write_text(report, encoding="utf-8")
    save(out, "summary.json", {"status": "PASS", "scope": "offline only", "sources": summaries, "terminal_state_caveat": "FINAL_STATE_TIME_UNCERTAIN for three legacy failures", "source_sha256": sha(__file__)})
    print(json.dumps({"status":"PASS","runs":[s["run"] for s in summaries],"violations":len(violation)}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--out",required=True);parser.add_argument("--source",action="append",nargs=2,metavar=("LABEL","FOLDER"),required=True);args=parser.parse_args()
    diagnose([(label,Path(folder)) for label,folder in args.source],args.out)


if __name__=="__main__":
    main()
