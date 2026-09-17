from __future__ import annotations

import argparse
import json
import pickle
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_ROOT = Path(
    r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main"
    r"\paper_dcn_tf12_draft\hairpin_stress_suite_2026-05-06_030045"
)

VERSION = "tf13"
COLORS = {
    "baseline": "#7f7f7f",
    "main": "#d62728",
    "no_adapt": "#1f77b4",
    "no_comm": "#2ca02c",
    "no_fault_redist": "#ff7f0e",
    "no_guard": "#9467bd",
    "no_conn": "#8c564b",
}
DISPLAY = {
    "baseline": "AKE-baseline",
    "main": "TF13",
    "no_adapt": "No AdaptNet",
    "no_comm": "No Comm.",
    "no_fault_redist": "No Fault Redist.",
    "no_guard": "No Guard",
    "no_conn": "No Compliance",
}


REQUIRED_FIGS: Sequence[Tuple[str, str]] = [
    ("S01", "tf13_stress_suite_global_summary.png"),
    ("S02", "tf13_nominal_clean_pair_system_lat_long_error_compare.png"),
    ("S03", "tf13_comm_noise_medium_system_lat_long_error_compare.png"),
    ("S04", "tf13_comm_noise_heavy_system_lat_long_error_compare.png"),
    ("S05", "tf13_rand_fault_deg_v2_system_lat_long_error_compare.png"),
    ("S06", "tf13_rand_fault_zero_v2_system_lat_long_error_compare.png"),
    ("S07", "tf13_mixed_fault_and_noise_system_lat_long_error_compare.png"),
    ("S08", "tf13_comm_noise_heavy_team_center_traj_compare.png"),
    ("S09", "tf13_mixed_fault_and_noise_team_center_traj_compare.png"),
    ("S10", "tf13_comm_protection_ablation_system_lat_long_error_compare.png"),
    ("S11", "tf13_comm_protection_ablation_connection_error_compare.png"),
    ("S12", "tf13_fault_redist_ablation_system_lat_long_error_compare.png"),
    ("S13", "tf13_fault_redist_ablation_connection_error_compare.png"),
    ("S14", "tf13_comm_protection_ablation_fault_window_zoom.png"),
    ("S15", "tf13_fault_redist_ablation_fault_window_zoom.png"),
]


OPTIONAL_FIGS: Sequence[Tuple[str, str]] = [
    ("O01", "tf13_comm_protection_ablation_payload_force_moment_compare.png"),
    ("O02", "tf13_fault_redist_ablation_payload_force_moment_compare.png"),
    ("O03", "tf13_mixed_fault_and_noise_fault_window_zoom.png"),
    ("O04", "tf13_mixed_fault_and_noise_comm_delay_fault_timeline.png"),
    ("O05", "tf13_comm_noise_heavy_comm_delay_fault_timeline.png"),
    ("O06", "tf13_rand_fault_deg_v2_fault_window_zoom.png"),
    ("O07", "tf13_rand_fault_zero_v2_fault_window_zoom.png"),
    ("O08", "targeted_ablations_overview_composite.png"),
]


def _set_style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 160,
            "savefig.dpi": 300,
            "font.sans-serif": [
                "Microsoft YaHei",
                "SimHei",
                "Noto Sans CJK SC",
                "Arial Unicode MS",
                "DejaVu Sans",
            ],
            "axes.unicode_minus": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "legend.framealpha": 0.88,
        }
    )


def _safe_float(x: Any, default: float = np.nan) -> float:
    try:
        y = float(x)
        return y if np.isfinite(y) else default
    except Exception:
        return default


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _find_by_name(root: Path, name: str) -> Optional[Path]:
    for base in [root / "figures", root / "figures_composite", root / "figures_composite_hd", root / "figures_composite_uhd"]:
        if not base.exists():
            continue
        hits = sorted(base.rglob(name))
        if hits:
            return hits[0]
    return None


def copy_selected(root: Path, out_root: Path) -> Dict[str, Any]:
    copied: List[Dict[str, str]] = []
    missing: List[Dict[str, str]] = []
    for subdir, specs in [("selected_required", REQUIRED_FIGS), ("selected_optional", OPTIONAL_FIGS)]:
        out_dir = _ensure(out_root / subdir)
        for tag, filename in specs:
            src = _find_by_name(root, filename)
            dst = out_dir / f"{tag}_{filename}"
            if src is None:
                missing.append({"tag": tag, "filename": filename, "group": subdir})
                continue
            shutil.copy2(src, dst)
            copied.append({"tag": tag, "src": str(src), "dst": str(dst), "group": subdir})
    return {"copied": copied, "missing": missing}


def load_metrics(root: Path) -> pd.DataFrame:
    csv_path = root / "data" / "tf13_stress_suite_metrics.csv"
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    df = pd.read_csv(csv_path)
    for col in [
        "attempt_idx",
        "speed_scale",
        "max_extra_steps",
        "progress_ratio",
        "final_s",
        "traj_length",
        "rmse_lat_mean",
        "rmse_long_mean",
        "max_lat_global",
        "max_long_global",
        "step_time_mean",
        "mpc_solve_time_mean",
        "comm_quality_mean",
        "comm_delay_mean",
        "comm_loss_mean",
        "fault_active_ratio",
        "fault_deficit_norm_peak",
        "conn_rms_mean",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _result_pkl(root: Path, category: str, experiment: str) -> Optional[Path]:
    p = root / "data" / category / f"{VERSION}_{experiment}_results.pkl"
    return p if p.exists() else None


def load_result(root: Path, category: str, experiment: str) -> Optional[Mapping[str, Mapping[str, Any]]]:
    p = _result_pkl(root, category, experiment)
    if p is None:
        return None
    with p.open("rb") as f:
        return pickle.load(f)


def _metric_rows_from_pkl(root: Path, df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for (category, experiment), g in df.groupby(["category", "experiment"], sort=False):
        pack = load_result(root, str(category), str(experiment))
        if not pack:
            continue
        for method, res in pack.items():
            step_hist = np.asarray(res.get("step_runtime_hist", []), dtype=float)
            solve_hist = np.asarray(res.get("mpc_solve_time_hist", []), dtype=float)
            rows.append(
                {
                    "category": category,
                    "experiment": experiment,
                    "method": method,
                    "step_time_mean": _safe_float(res.get("step_time_mean")),
                    "step_time_p95": float(np.nanpercentile(step_hist, 95)) if step_hist.size else np.nan,
                    "step_time_max": _safe_float(res.get("step_time_max")),
                    "mpc_solve_time_mean": _safe_float(res.get("mpc_solve_time_mean")),
                    "mpc_solve_time_p95": float(np.nanpercentile(solve_hist, 95)) if solve_hist.size else np.nan,
                    "mpc_solve_time_max": _safe_float(res.get("mpc_solve_time_max")),
                    "full_path_reached": bool(res.get("full_path_reached", False)),
                }
            )
    return pd.DataFrame(rows)


def _bar_by_method(
    ax: plt.Axes,
    data: pd.DataFrame,
    metric: str,
    title: str,
    ylabel: str,
    methods: Sequence[str] = ("baseline", "main"),
) -> None:
    sub = data[data["method"].isin(methods)].copy()
    labels = list(dict.fromkeys(sub["experiment"].astype(str).tolist()))
    x = np.arange(len(labels))
    width = min(0.34, 0.78 / max(1, len(methods)))
    for i, m in enumerate(methods):
        vals = []
        for lab in labels:
            hit = sub[(sub["experiment"] == lab) & (sub["method"] == m)]
            vals.append(_safe_float(hit[metric].iloc[0]) if len(hit) else np.nan)
        ax.bar(x + (i - (len(methods) - 1) / 2.0) * width, vals, width, label=DISPLAY.get(m, m), color=COLORS.get(m))
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.legend(fontsize=8)


def fig_n1_solve_time(root: Path, df: pd.DataFrame, out_dir: Path) -> Path:
    rt = _metric_rows_from_pkl(root, df)
    if rt.empty:
        rt = df.copy()
        rt["step_time_p95"] = np.nan
        rt["mpc_solve_time_p95"] = np.nan
    rt.to_csv(out_dir / "N01_solve_time_summary_data.csv", index=False, encoding="utf-8-sig")
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    _bar_by_method(axes[0, 0], rt, "step_time_mean", "平均单步耗时", "time [s]")
    _bar_by_method(axes[0, 1], rt, "mpc_solve_time_mean", "平均 MPC 求解耗时", "time [s]")
    _bar_by_method(axes[1, 0], rt, "step_time_p95", "单步耗时 95 分位", "time [s]")
    _bar_by_method(axes[1, 1], rt, "mpc_solve_time_p95", "MPC 求解耗时 95 分位", "time [s]")
    fig.suptitle("N1 全场景求解时长统计（用于如实说明时间开销）", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    p = out_dir / "N01_solve_time_summary.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_n2_attempt_audit(root: Path, df: pd.DataFrame, out_dir: Path) -> Path:
    audit = df[df["method"].isin(["baseline", "main"])].copy()
    audit.to_csv(out_dir / "N02_fixed_attempt_audit_data.csv", index=False, encoding="utf-8-sig")
    labels = list(dict.fromkeys(audit["experiment"].astype(str).tolist()))
    x = np.arange(len(labels))
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
    for ax, metric, title, ylabel in [
        (axes[0], "attempt_idx", "尝试编号审计", "attempt [-]"),
        (axes[1], "speed_scale", "路径速度缩放", "speed scale [-]"),
        (axes[2], "max_extra_steps", "额外步数上限", "steps [-]"),
    ]:
        for m in ["baseline", "main"]:
            vals = []
            for lab in labels:
                hit = audit[(audit["experiment"] == lab) & (audit["method"] == m)]
                vals.append(_safe_float(hit[metric].iloc[0]) if len(hit) else np.nan)
            axes_idx = ax
            axes_idx.plot(x, vals, marker="o", linewidth=1.8, label=DISPLAY.get(m, m), color=COLORS.get(m))
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=8, ncol=2)
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    axes[-1].set_xlabel("experiment [-]")
    fig.suptitle("N2 固定尝试口径审计图", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    p = out_dir / "N02_fixed_attempt_audit.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def _diag_series(res: Mapping[str, Any], key: str, field: str) -> np.ndarray:
    vals = []
    for item in res.get(key, []) or []:
        if isinstance(item, Mapping):
            vals.append(_safe_float(item.get(field), np.nan))
    return np.asarray(vals, dtype=float)


def _payload_stats(res: Mapping[str, Any]) -> Dict[str, float]:
    fx: List[float] = []
    fy: List[float] = []
    mz: List[float] = []
    load_spread: List[float] = []
    for item in res.get("payload_force_hist", []) or []:
        if not isinstance(item, Mapping):
            continue
        fx.append(_safe_float(item.get("fx_payload")))
        fy.append(_safe_float(item.get("fy_payload")))
        mz.append(_safe_float(item.get("mz_payload")))
        cn = item.get("corner_normal_loads")
        try:
            arr = np.asarray(cn, dtype=float).reshape(-1)
            load_spread.append(float(np.nanmax(arr) - np.nanmin(arr)))
        except Exception:
            pass
    fx_arr = np.asarray(fx, dtype=float)
    fy_arr = np.asarray(fy, dtype=float)
    mz_arr = np.asarray(mz, dtype=float)
    force = np.sqrt(fx_arr**2 + fy_arr**2)
    return {
        "force_rms_N": float(np.sqrt(np.nanmean(force**2))) if force.size else np.nan,
        "force_p95_N": float(np.nanpercentile(np.abs(force), 95)) if force.size else np.nan,
        "yaw_moment_p95_Nm": float(np.nanpercentile(np.abs(mz_arr), 95)) if mz_arr.size else np.nan,
        "normal_load_spread_p95_N": float(np.nanpercentile(np.abs(load_spread), 95)) if load_spread else np.nan,
    }


def collect_pkl_stats(root: Path, df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for (category, experiment), _ in df.groupby(["category", "experiment"], sort=False):
        pack = load_result(root, str(category), str(experiment))
        if not pack:
            continue
        for method, res in pack.items():
            conn_rms = _diag_series(res, "connection_diag_hist", "rms_rel")
            max_dey = _diag_series(res, "connection_diag_hist", "max_abs_dey")
            max_dpsi = _diag_series(res, "connection_diag_hist", "max_abs_dpsi")
            base = {
                "category": category,
                "experiment": experiment,
                "method": method,
                "conn_rms_mean": float(np.nanmean(conn_rms)) if conn_rms.size else np.nan,
                "conn_rms_p95": float(np.nanpercentile(conn_rms, 95)) if conn_rms.size else np.nan,
                "conn_dey_p95_m": float(np.nanpercentile(np.abs(max_dey), 95)) if max_dey.size else np.nan,
                "conn_dpsi_p95_rad": float(np.nanpercentile(np.abs(max_dpsi), 95)) if max_dpsi.size else np.nan,
            }
            base.update(_payload_stats(res))
            rows.append(base)
    out = pd.DataFrame(rows)
    return out


def fig_n3_connection_summary(root: Path, df: pd.DataFrame, out_dir: Path) -> Path:
    stats = collect_pkl_stats(root, df)
    stats.to_csv(out_dir / "N03_connection_safety_summary_data.csv", index=False, encoding="utf-8-sig")
    methods = ["baseline", "main"]
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    _bar_by_method(axes[0, 0], stats, "conn_rms_p95", "连接相对误差 95 分位", "relative error [-]", methods)
    _bar_by_method(axes[0, 1], stats, "conn_dey_p95_m", "连接横向误差 95 分位", "error [m]", methods)
    _bar_by_method(axes[1, 0], stats, "conn_dpsi_p95_rad", "连接航向误差 95 分位", "error [rad]", methods)
    _bar_by_method(axes[1, 1], stats, "conn_rms_mean", "连接相对误差均值", "relative error [-]", methods)
    fig.suptitle("N3 连接安全裕度跨场景汇总", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    p = out_dir / "N03_connection_safety_summary.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_n4_force_summary(root: Path, df: pd.DataFrame, out_dir: Path) -> Path:
    stats_path = out_dir / "N03_connection_safety_summary_data.csv"
    stats = pd.read_csv(stats_path) if stats_path.exists() else collect_pkl_stats(root, df)
    stats.to_csv(out_dir / "N04_force_demand_summary_data.csv", index=False, encoding="utf-8-sig")
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    _bar_by_method(axes[0, 0], stats, "force_rms_N", "载荷合力 RMS", "force [N]")
    _bar_by_method(axes[0, 1], stats, "force_p95_N", "载荷合力 95 分位", "force [N]")
    _bar_by_method(axes[1, 0], stats, "yaw_moment_p95_Nm", "偏航力矩 95 分位", "moment [N·m]")
    _bar_by_method(axes[1, 1], stats, "normal_load_spread_p95_N", "四角法向载荷差 95 分位", "load spread [N]")
    fig.suptitle("N4 载荷受力需求稳健统计汇总", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    p = out_dir / "N04_force_demand_summary.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def _vehicle_from_exp(name: str) -> str:
    for v in range(1, 5):
        if f"_v{v}" in name:
            return f"车{v}"
    return name


def fig_fault_symmetry(df: pd.DataFrame, category: str, out_dir: Path, tag: str, title: str) -> Path:
    sub = df[(df["category"] == category) & (df["method"].isin(["baseline", "main"]))].copy()
    sub["vehicle"] = sub["experiment"].astype(str).map(_vehicle_from_exp)
    sub.to_csv(out_dir / f"{tag}_fault_symmetry_data.csv", index=False, encoding="utf-8-sig")
    vehicles = [f"车{i}" for i in range(1, 5)]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, metric, ylabel in [
        (axes[0], "rmse_lat_mean", "lateral RMSE [m]"),
        (axes[1], "rmse_long_mean", "longitudinal RMSE [m]"),
        (axes[2], "progress_ratio", "progress ratio [-]"),
    ]:
        x = np.arange(len(vehicles))
        width = 0.34
        for i, method in enumerate(["baseline", "main"]):
            vals = []
            for v in vehicles:
                hit = sub[(sub["vehicle"] == v) & (sub["method"] == method)]
                vals.append(_safe_float(hit[metric].iloc[0]) if len(hit) else np.nan)
            ax.bar(x + (i - 0.5) * width, vals, width, label=DISPLAY.get(method, method), color=COLORS.get(method))
        ax.set_title(metric)
        ax.set_ylabel(ylabel)
        ax.set_xticks(x)
        ax.set_xticklabels(vehicles)
        ax.legend(fontsize=8)
    fig.suptitle(title, fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    p = out_dir / f"{tag}_fault_symmetry.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_n7_comm_dose(df: pd.DataFrame, out_dir: Path) -> Path:
    rows = []
    for exp, level in [
        ("nominal_clean_pair", "none"),
        ("comm_noise_medium", "medium"),
        ("comm_noise_heavy", "heavy"),
    ]:
        hit = df[(df["experiment"] == exp) & (df["method"].isin(["baseline", "main"]))].copy()
        hit["noise_level"] = level
        rows.append(hit)
    sub = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    sub.to_csv(out_dir / "N07_comm_noise_dose_response_data.csv", index=False, encoding="utf-8-sig")
    levels = ["none", "medium", "heavy"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    for ax, metric, ylabel in [
        (axes[0, 0], "rmse_lat_mean", "lateral RMSE [m]"),
        (axes[0, 1], "rmse_long_mean", "longitudinal RMSE [m]"),
        (axes[1, 0], "progress_ratio", "progress ratio [-]"),
        (axes[1, 1], "comm_loss_mean", "packet loss ratio [-]"),
    ]:
        for m in ["baseline", "main"]:
            vals = []
            for lv in levels:
                hit = sub[(sub["noise_level"] == lv) & (sub["method"] == m)]
                vals.append(_safe_float(hit[metric].iloc[0]) if len(hit) else np.nan)
            ax.plot(levels, vals, marker="o", linewidth=2.0, label=DISPLAY.get(m, m), color=COLORS.get(m))
        ax.set_ylabel(ylabel)
        ax.set_title(metric)
        ax.legend(fontsize=8)
    fig.suptitle("N7 通信噪声剂量-响应图", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p = out_dir / "N07_comm_noise_dose_response.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_n8_mixed_heatmap(df: pd.DataFrame, out_dir: Path) -> Path:
    methods = ["baseline", "no_comm", "no_fault_redist", "main"]
    metrics = [
        ("rmse_lat_mean", "Lat RMSE"),
        ("rmse_long_mean", "Long RMSE"),
        ("max_lat_global", "Max Lat"),
        ("max_long_global", "Max Long"),
        ("progress_ratio", "Progress"),
        ("fault_deficit_norm_peak", "Fault Deficit"),
        ("comm_loss_mean", "Comm Loss"),
        ("conn_rms_mean", "Conn RMS"),
    ]
    sub = df[(df["experiment"] == "mixed_fault_and_noise") & (df["method"].isin(methods))].copy()
    raw = np.zeros((len(methods), len(metrics)), dtype=float)
    for i, method in enumerate(methods):
        row = sub[sub["method"] == method]
        for j, (metric, _) in enumerate(metrics):
            val = _safe_float(row[metric].iloc[0]) if len(row) else np.nan
            raw[i, j] = val
    norm = raw.copy()
    for j, (metric, _) in enumerate(metrics):
        col = raw[:, j].astype(float)
        finite = np.isfinite(col)
        if not np.any(finite):
            continue
        cmin, cmax = float(np.nanmin(col)), float(np.nanmax(col))
        if abs(cmax - cmin) < 1e-12:
            norm[:, j] = 0.5
        else:
            if metric == "progress_ratio":
                norm[:, j] = (cmax - col) / (cmax - cmin)
            else:
                norm[:, j] = (col - cmin) / (cmax - cmin)
    out = pd.DataFrame(raw, index=methods, columns=[m[0] for m in metrics])
    out.to_csv(out_dir / "N08_mixed_disturbance_ablation_heatmap_data.csv", encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(11, 5))
    im = ax.imshow(norm, cmap="YlOrRd", vmin=0.0, vmax=1.0, aspect="auto")
    ax.set_xticks(np.arange(len(metrics)))
    ax.set_xticklabels([m[1] for m in metrics], rotation=35, ha="right")
    ax.set_yticks(np.arange(len(methods)))
    ax.set_yticklabels([DISPLAY.get(m, m) for m in methods])
    for i in range(len(methods)):
        for j in range(len(metrics)):
            ax.text(j, i, f"{raw[i, j]:.3g}", ha="center", va="center", fontsize=8)
    cb = fig.colorbar(im, ax=ax)
    cb.set_label("normalized badness [-]")
    ax.set_title("N8 混合扰动消融热力图（颜色越浅越好）")
    fig.tight_layout()
    p = out_dir / "N08_mixed_disturbance_ablation_heatmap.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def _system_series_npz(root: Path, category: str, experiment: str) -> Optional[Path]:
    p = root / "data" / category / f"{VERSION}_{experiment}_series.npz"
    return p if p.exists() else None


def fig_n9_adaptation_window(root: Path, out_dir: Path) -> Path:
    series_p = _system_series_npz(root, "targeted_ablations", "nominal_adapt_ablation")
    pack = load_result(root, "targeted_ablations", "nominal_adapt_ablation")
    if series_p is None or pack is None:
        raise FileNotFoundError("nominal_adapt_ablation data not found")
    z = np.load(series_p, allow_pickle=True)
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=False)
    for method in ["no_adapt", "main"]:
        if f"{method}_system_t" not in z.files:
            continue
        t = z[f"{method}_system_t"]
        ey = z[f"{method}_system_e_y"]
        es = z[f"{method}_system_e_s"]
        axes[0].plot(t, ey, label=DISPLAY.get(method, method), color=COLORS.get(method), linewidth=1.8)
        axes[1].plot(t, es, label=DISPLAY.get(method, method), color=COLORS.get(method), linewidth=1.8)
    main = pack.get("main", {})
    a = np.asarray(main.get("adapt_A_norm_hist", []), dtype=float)
    b = np.asarray(main.get("adapt_B_norm_hist", []), dtype=float)
    if a.size:
        axes[2].plot(np.arange(a.size), a, label=r"$||\Delta A||$", color="tab:blue", linewidth=1.5)
    if b.size:
        axes[2].plot(np.arange(b.size), b, label=r"$||\Delta B||$", color="tab:orange", linewidth=1.5)
    if not a.size and not b.size:
        axes[2].text(
            0.5,
            0.5,
            "当前 stress suite 采用实时快速口径，未记录在线矩阵更新序列；\n"
            "本图保留 main / no-adapt 的跟踪误差对比作为自适应收益审计入口。",
            ha="center",
            va="center",
            transform=axes[2].transAxes,
            fontsize=10,
            bbox={"facecolor": "white", "edgecolor": "0.7", "alpha": 0.9},
        )
    axes[0].axhline(0, color="k", linestyle=":", linewidth=1.0)
    axes[1].axhline(0, color="k", linestyle=":", linewidth=1.0)
    axes[0].set_ylabel("e_y [m]")
    axes[1].set_ylabel("e_s [m]")
    axes[2].set_ylabel("adapt norm [-]")
    axes[2].set_xlabel("update index [-]")
    axes[0].set_title("局部横向误差")
    axes[1].set_title("局部纵向误差")
    axes[2].set_title("在线自适应矩阵更新幅值")
    for ax in axes:
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(fontsize=8)
    fig.suptitle("N9 在线自适应收益触发图（现有 nominal adapt 数据口径）", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p = out_dir / "N09_online_adaptation_trigger.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_n10_random_ensemble_proxy(df: pd.DataFrame, out_dir: Path) -> Path:
    # The current suite stores one communication seed per comm case, but it does
    # contain repeated random fault locations. This figure is intentionally named
    # as an ensemble/proxy plot instead of claiming strict multi-seed simulation.
    sub = df[
        (
            df["category"].isin(["fault_degraded", "fault_zero", "comm_noise"])
            | df["experiment"].isin(["mixed_fault_and_noise"])
        )
        & df["method"].isin(["baseline", "main"])
    ].copy()
    sub.to_csv(out_dir / "N10_stochastic_ensemble_proxy_data.csv", index=False, encoding="utf-8-sig")
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    for ax, metric, ylabel in [
        (axes[0], "rmse_lat_mean", "lateral RMSE [m]"),
        (axes[1], "rmse_long_mean", "longitudinal RMSE [m]"),
        (axes[2], "progress_ratio", "progress ratio [-]"),
    ]:
        data = []
        labels = []
        colors = []
        for method in ["baseline", "main"]:
            vals = sub[sub["method"] == method][metric].dropna().to_numpy(dtype=float)
            data.append(vals)
            labels.append(DISPLAY.get(method, method))
            colors.append(COLORS.get(method))
        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, showmeans=True)
        for patch, c in zip(bp["boxes"], colors):
            patch.set_facecolor(c)
            patch.set_alpha(0.35)
        ax.set_title(metric)
        ax.set_ylabel(ylabel)
    fig.suptitle("N10 随机扰动集合统计图（当前 suite 可用代理口径）", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    p = out_dir / "N10_stochastic_ensemble_proxy.png"
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return p


def build(root: Path, out_root: Optional[Path] = None) -> Dict[str, Any]:
    _set_style()
    root = root.resolve()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    if out_root is None:
        out_root = root / f"safe_supplement_pack_{stamp}"
    out_root = out_root.resolve()
    figs_new = _ensure(out_root / "new_figures")
    _ensure(out_root / "selected_required")
    _ensure(out_root / "selected_optional")
    _ensure(out_root / "data")

    copy_info = copy_selected(root, out_root)
    df = load_metrics(root)
    df.to_csv(out_root / "data" / "source_metrics_copy.csv", index=False, encoding="utf-8-sig")

    generated: List[str] = []
    generated.append(str(fig_n1_solve_time(root, df, figs_new)))
    generated.append(str(fig_n2_attempt_audit(root, df, figs_new)))
    generated.append(str(fig_n3_connection_summary(root, df, figs_new)))
    generated.append(str(fig_n4_force_summary(root, df, figs_new)))
    generated.append(str(fig_fault_symmetry(df, "fault_degraded", figs_new, "N05_degraded_fault_vehicle_symmetry", "N5 四个降额故障位置的对称性汇总")))
    generated.append(str(fig_fault_symmetry(df, "fault_zero", figs_new, "N06_zero_fault_vehicle_symmetry", "N6 四个失效故障位置的对称性汇总")))
    generated.append(str(fig_n7_comm_dose(df, figs_new)))
    generated.append(str(fig_n8_mixed_heatmap(df, figs_new)))
    generated.append(str(fig_n9_adaptation_window(root, figs_new)))
    generated.append(str(fig_n10_random_ensemble_proxy(df, figs_new)))

    # Copy generated data CSVs into the data folder as well, keeping figures
    # self-contained while making numerical checks easy.
    for csv in figs_new.glob("*.csv"):
        shutil.copy2(csv, out_root / "data" / csv.name)

    manifest = {
        "source_root": str(root),
        "out_root": str(out_root),
        "required_copied": len([x for x in copy_info["copied"] if x["group"] == "selected_required"]),
        "optional_copied": len([x for x in copy_info["copied"] if x["group"] == "selected_optional"]),
        "missing_selected": copy_info["missing"],
        "generated_new_figures": generated,
        "note": (
            "N10 uses the stochastic/fault ensemble already present in the suite. "
            "Strict multi-seed communication simulation would require additional heavy reruns."
        ),
    }
    with (out_root / "supplement_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Build selected + missing safe supplement figures.")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--out-root", type=Path, default=None)
    args = ap.parse_args()
    manifest = build(args.root, args.out_root)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
