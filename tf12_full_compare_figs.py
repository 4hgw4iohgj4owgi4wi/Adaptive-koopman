import os
from pathlib import Path
from typing import Callable, Dict, Any, Tuple

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath

try:
    from scipy.spatial import ConvexHull
except Exception:
    ConvexHull = None

try:
    from control_files.tf12.history_store import load_tf12_history_records
except Exception:
    load_tf12_history_records = None


def _ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _frenet_to_global_default(s, ey, s_ref, x_ref, y_ref, psi_ref):
    s = np.asarray(s, dtype=float)
    ey = np.asarray(ey, dtype=float)
    s_ref = np.asarray(s_ref, dtype=float)
    x_ref = np.asarray(x_ref, dtype=float)
    y_ref = np.asarray(y_ref, dtype=float)
    psi_ref = np.asarray(psi_ref, dtype=float)

    s_clip = np.clip(s, s_ref[0], s_ref[-1])
    x_c = np.interp(s_clip, s_ref, x_ref)
    y_c = np.interp(s_clip, s_ref, y_ref)
    psi_c = np.interp(s_clip, s_ref, psi_ref)

    xg = x_c - ey * np.sin(psi_c)
    yg = y_c + ey * np.cos(psi_c)
    return xg, yg


def _safe_grad(x: np.ndarray, dt: float) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.size <= 1:
        return np.zeros_like(x)
    return np.gradient(x, float(dt))


def _chunk5_mean_abs(err: np.ndarray) -> np.ndarray:
    arr = np.abs(np.asarray(err, dtype=float))
    if arr.size == 0:
        return np.array([], dtype=float)
    n = (arr.size // 5) * 5
    if n <= 0:
        return np.array([float(np.mean(arr))], dtype=float)
    return arr[:n].reshape(-1, 5).mean(axis=1)


def _fit_linear_residual(z: np.ndarray, u: np.ndarray, ridge: float = 1e-5) -> np.ndarray:
    if z.shape[0] < 3:
        return np.array([], dtype=float)
    zk = z[:-1, :]
    zk1 = z[1:, :]
    uk = u[: zk.shape[0], :]
    x = np.hstack([zk, uk])
    y = zk1
    xtx = x.T @ x
    reg = ridge * np.eye(xtx.shape[0], dtype=float)
    theta = np.linalg.solve(xtx + reg, x.T @ y)
    pred = x @ theta
    err = np.linalg.norm(y - pred, axis=1)
    return err


def _entity_names(num_vehicles: int) -> list[str]:
    return ["system"] + [f"vehicle_{i+1}" for i in range(num_vehicles)]


def _infer_hist_method(method_name: str) -> str:
    txt = str(method_name or "").lower()
    if "baseline" in txt:
        return "baseline"
    return "main"


def _infer_hist_mode(metadata: Dict[str, Any]) -> str:
    mode = str(metadata.get("scenario_mode", "")).strip().lower()
    if mode:
        return mode
    name = str(metadata.get("method_name", "")).strip().lower()
    if "hairpin" in name or "u_turn" in name or "uturn" in name:
        return "hairpin"
    if "dlc" in name or "double_lane" in name:
        return "dlc"
    return "unknown"


def _extract_mode_data(
    result: Dict[str, Any],
    mode_pack: Dict[str, Any],
    dt: float,
    frenet_to_global_fn: Callable,
) -> Dict[str, Dict[str, np.ndarray]]:
    team = np.asarray(result["team_state_hist"], dtype=float)
    team_ref = np.asarray(result["ref_team_hist"], dtype=float)
    xh = result["xt_actual_vehicles"]
    rh = result["ref_vehicle_histories"]

    n_steps = int(result.get("sim_steps", team.shape[0] - 1)) + 1
    n_steps = min(n_steps, team.shape[0], team_ref.shape[0])

    s_ref_path = np.asarray(mode_pack["s_ref_path"], dtype=float)
    x_path = np.asarray(mode_pack["x_path"], dtype=float)
    y_ref_path = np.asarray(mode_pack["y_ref_path"], dtype=float)
    psi_ref_path = np.asarray(mode_pack["psi_ref_path"], dtype=float)

    out: Dict[str, Dict[str, np.ndarray]] = {}

    # system entity
    es_sys = team[:n_steps, 0] - team_ref[:n_steps, 0]
    ey_sys = team[:n_steps, 1] - team_ref[:n_steps, 1]
    xg_sys, yg_sys = frenet_to_global_fn(
        team[:n_steps, 0],
        team[:n_steps, 1],
        s_ref_path,
        x_path,
        y_ref_path,
        psi_ref_path,
    )
    xg_ref_sys, yg_ref_sys = frenet_to_global_fn(
        team_ref[:n_steps, 0],
        team_ref[:n_steps, 1],
        s_ref_path,
        x_path,
        y_ref_path,
        psi_ref_path,
    )
    epos_sys = np.hypot(xg_sys - xg_ref_sys, yg_sys - yg_ref_sys)
    r_sys = team[:n_steps, 5]
    rdot_sys = _safe_grad(r_sys, dt)
    out["system"] = {
        "t": np.arange(n_steps, dtype=float) * float(dt),
        "e_s": es_sys,
        "e_y": ey_sys,
        "e_pos": epos_sys,
        "r": r_sys,
        "rdot": rdot_sys,
        "xg": np.asarray(xg_sys, dtype=float),
        "yg": np.asarray(yg_sys, dtype=float),
        "xg_ref": np.asarray(xg_ref_sys, dtype=float),
        "yg_ref": np.asarray(yg_ref_sys, dtype=float),
    }

    num_vehicles = min(len(xh), len(rh))
    for v in range(num_vehicles):
        xv = np.asarray(xh[v], dtype=float)
        rv = np.asarray(rh[v], dtype=float)
        nv = min(n_steps, xv.shape[0], rv.shape[0])
        es = xv[:nv, 0] - rv[:nv, 0]
        ey = xv[:nv, 1] - rv[:nv, 1]
        xg, yg = frenet_to_global_fn(
            xv[:nv, 0],
            xv[:nv, 1],
            s_ref_path,
            x_path,
            y_ref_path,
            psi_ref_path,
        )
        xg_ref, yg_ref = frenet_to_global_fn(
            rv[:nv, 0],
            rv[:nv, 1],
            s_ref_path,
            x_path,
            y_ref_path,
            psi_ref_path,
        )
        epos = np.hypot(xg - xg_ref, yg - yg_ref)
        r = xv[:nv, 5]
        rdot = _safe_grad(r, dt)
        out[f"vehicle_{v+1}"] = {
            "t": np.arange(nv, dtype=float) * float(dt),
            "e_s": es,
            "e_y": ey,
            "e_pos": epos,
            "r": r,
            "rdot": rdot,
            "xg": np.asarray(xg, dtype=float),
            "yg": np.asarray(yg, dtype=float),
            "xg_ref": np.asarray(xg_ref, dtype=float),
            "yg_ref": np.asarray(yg_ref, dtype=float),
        }

    return out


def _common_fig_style():
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def _save_show(fig, path: Path, show: bool):
    fig.savefig(path, dpi=220, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)


def _phase_hull(points: np.ndarray):
    pts = np.asarray(points, dtype=float)
    pts = pts[np.all(np.isfinite(pts), axis=1)]
    if pts.shape[0] < 8:
        return None
    if ConvexHull is None:
        return None
    try:
        hull = ConvexHull(pts)
        poly = pts[hull.vertices]
        return poly
    except Exception:
        return None


def generate_tf12_full_comparison_figs(
    *,
    compare_results_b1_dual: Dict[str, Dict[str, Any]],
    dt: float,
    tf12_path_library: Dict[str, Dict[str, Any]],
    output_dir: str = "results/tf12_full_compare_figs",
    frenet_to_global_fn: Callable | None = None,
    include_traj_tracking_figs: bool = True,
    include_history_block: bool = True,
    history_root_dir: str = "results/history/tf12",
    history_limit: int = 240,
    show: bool = False,
) -> Dict[str, Any]:
    """Generate full comparison figure pack for TF12 main vs baseline.

    Expected compare_results_b1_dual format:
    {
      "dlc": {"baseline_bilinear_adaptnet": res_b, "main_tf12_full": res_m, ...},
      "hairpin": {...}
    }
    """
    _common_fig_style()
    out_dir = _ensure_dir(output_dir)
    fg = frenet_to_global_fn or _frenet_to_global_default

    modes = [m for m in ["dlc", "hairpin"] if m in compare_results_b1_dual and m in tf12_path_library]
    if len(modes) == 0:
        raise ValueError("No overlapping modes between compare_results_b1_dual and tf12_path_library")

    summary: Dict[str, Any] = {"output_dir": str(out_dir), "figures": [], "metrics": {}}

    labels_v = ["车1", "车2", "车3", "车4"]
    colors_v = ["tab:blue", "tab:purple", "tab:green", "tab:red"]

    extracted: Dict[str, Dict[str, Dict[str, Dict[str, np.ndarray]]]] = {}

    # ---------------------------
    # Extract all mode data first
    # ---------------------------
    for mode in modes:
        res_b = compare_results_b1_dual[mode]["baseline_bilinear_adaptnet"]
        res_m = compare_results_b1_dual[mode]["main_tf12_full"]
        pack = tf12_path_library[mode]
        ext_b = _extract_mode_data(res_b, pack, dt, fg)
        ext_m = _extract_mode_data(res_m, pack, dt, fg)
        extracted[mode] = {"baseline": ext_b, "main": ext_m}

    # ----------------------------------------------------------
    # Figure T: trajectory tracking (reference + four vehicles)
    # ----------------------------------------------------------
    if include_traj_tracking_figs:
        ls_ref = [":", ":", ":", ":"]
        ls_act = ["--", "-.", (0, (5, 2, 1, 2)), (0, (1, 1))]
        labels_full = ["车1 (前左)", "车2 (前右)", "车3 (后左)", "车4 (后右)"]

        for mode in modes:
            mode_pack = tf12_path_library[mode]

            fig, axes = plt.subplots(1, 2, figsize=(18, 6), sharex=False, sharey=False)
            fig.suptitle(f"{mode.upper()} 路径跟踪图（Baseline vs 主方法）", fontsize=15, fontweight="bold")
            method_names = [("baseline", "Baseline"), ("main", "主方法")]

            for ax, (method_key, title_name) in zip(axes, method_names):
                ax.plot(
                    mode_pack["x_path"],
                    mode_pack["y_ref_path"],
                    color="black",
                    linewidth=2.4,
                    label="货物中心参考路径",
                )
                for v in range(4):
                    d = extracted[mode][method_key][f"vehicle_{v+1}"]
                    ax.plot(
                        d["xg_ref"],
                        d["yg_ref"],
                        color=colors_v[v],
                        linestyle=ls_ref[v],
                        linewidth=1.0,
                        alpha=0.60,
                        label=f"{labels_full[v]} 参考",
                    )
                    ax.plot(
                        d["xg"],
                        d["yg"],
                        color=colors_v[v],
                        linestyle=ls_act[v],
                        linewidth=2.0,
                        label=labels_full[v],
                    )
                ax.set_title(title_name)
                ax.set_xlabel("x [m]")
                ax.set_ylabel("y [m]")
                ax.grid(True, alpha=0.30)
                ax.legend(fontsize=8, loc="upper right", ncol=2)

            fpath = out_dir / f"fig_traj_tracking_{mode}_baseline_vs_main.png"
            _save_show(fig, fpath, show)
            summary["figures"].append(str(fpath))

            fig, ax = plt.subplots(1, 1, figsize=(12, 8))
            ax.plot(
                mode_pack["x_path"],
                mode_pack["y_ref_path"],
                color="black",
                linewidth=2.5,
                label="货物中心参考路径",
            )
            for v in range(4):
                d = extracted[mode]["main"][f"vehicle_{v+1}"]
                ax.plot(
                    d["xg_ref"],
                    d["yg_ref"],
                    color=colors_v[v],
                    linestyle=ls_ref[v],
                    linewidth=1.0,
                    alpha=0.60,
                    label=f"{labels_full[v]} 参考",
                )
                ax.plot(
                    d["xg"],
                    d["yg"],
                    color=colors_v[v],
                    linestyle=ls_act[v],
                    linewidth=2.2,
                    label=labels_full[v],
                )
            ax.set_title(f"TF12 {mode.upper()} 四车刚性搬运路径跟踪")
            ax.set_xlabel("x [m]")
            ax.set_ylabel("y [m]")
            ax.grid(True, alpha=0.30)
            ax.legend(fontsize=8, loc="upper right", ncol=2)
            fpath = out_dir / f"fig_traj_tracking_{mode}_main.png"
            _save_show(fig, fpath, show)
            summary["figures"].append(str(fpath))

    # -----------------------------------------
    # Figure A: Position error (system + 4 cars)
    # -----------------------------------------
    for mode in modes:
        fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=False)
        fig.suptitle(f"{mode.upper()} 位置误差对比（Baseline vs 主方法）", fontsize=15, fontweight="bold")

        entity_order = ["system", "vehicle_1", "vehicle_2", "vehicle_3", "vehicle_4"]
        titles = ["系统整体", "车1", "车2", "车3", "车4"]

        for i, ent in enumerate(entity_order):
            r = i // 3
            c = i % 3
            ax = axes[r, c]
            db = extracted[mode]["baseline"][ent]
            dm = extracted[mode]["main"][ent]
            ax.plot(db["t"], db["e_pos"], "--", color="tab:gray", linewidth=1.6, label="Baseline")
            ax.plot(dm["t"], dm["e_pos"], "-", color="black", linewidth=2.0, label="主方法")
            ax.axhline(0.01, color="tab:orange", linestyle=":", linewidth=1.0, alpha=0.9, label="0.01 m")
            ax.set_title(titles[i])
            ax.set_xlabel("时间 [s]")
            ax.set_ylabel("e_pos [m]")
            ax.grid(True, alpha=0.30)
            ax.legend(fontsize=8, loc="upper right")

        # fleet mean in last panel
        ax = axes[1, 2]
        e_b = []
        e_m = []
        tmax = 0
        for k in ["vehicle_1", "vehicle_2", "vehicle_3", "vehicle_4"]:
            tmax = max(tmax, extracted[mode]["baseline"][k]["e_pos"].size, extracted[mode]["main"][k]["e_pos"].size)
        E_b = np.full((4, tmax), np.nan)
        E_m = np.full((4, tmax), np.nan)
        for i, k in enumerate(["vehicle_1", "vehicle_2", "vehicle_3", "vehicle_4"]):
            vb = extracted[mode]["baseline"][k]["e_pos"]
            vm = extracted[mode]["main"][k]["e_pos"]
            E_b[i, : vb.size] = vb
            E_m[i, : vm.size] = vm
        t = np.arange(tmax) * float(dt)
        ax.plot(t, np.nanmean(E_b, axis=0), "--", color="tab:gray", linewidth=1.8, label="Baseline 均值")
        ax.plot(t, np.nanmean(E_m, axis=0), "-", color="black", linewidth=2.2, label="主方法 均值")
        ax.plot(t, np.nanmax(E_b, axis=0), "--", color="tab:red", linewidth=1.2, alpha=0.8, label="Baseline 最大")
        ax.plot(t, np.nanmax(E_m, axis=0), "-", color="tab:green", linewidth=1.5, alpha=0.9, label="主方法 最大")
        ax.axhline(0.01, color="tab:orange", linestyle=":", linewidth=1.0, alpha=0.9)
        ax.set_title("车队统计")
        ax.set_xlabel("时间 [s]")
        ax.set_ylabel("e_pos [m]")
        ax.grid(True, alpha=0.30)
        ax.legend(fontsize=8, loc="upper right")

        fpath = out_dir / f"fig_pos_error_{mode}.png"
        _save_show(fig, fpath, show)
        summary["figures"].append(str(fpath))

    # --------------------------------------------------
    # Figure B: lateral/longitudinal errors per vehicle
    # --------------------------------------------------
    for mode in modes:
        fig, axes = plt.subplots(4, 2, figsize=(14, 12), sharex=False)
        fig.suptitle(f"{mode.upper()} 四车横向/纵向误差（Baseline vs 主方法）", fontsize=15, fontweight="bold")

        for v in range(4):
            ent = f"vehicle_{v+1}"
            db = extracted[mode]["baseline"][ent]
            dm = extracted[mode]["main"][ent]

            axl = axes[v, 0]
            axl.plot(db["t"], db["e_y"], "--", color=colors_v[v], linewidth=1.5, label=f"{labels_v[v]} Baseline")
            axl.plot(dm["t"], dm["e_y"], "-", color=colors_v[v], linewidth=1.9, label=f"{labels_v[v]} 主方法")
            axl.axhline(0.0, color="gray", linestyle=":", linewidth=1.0)
            axl.set_ylabel("e_y [m]")
            axl.grid(True, alpha=0.30)
            axl.legend(fontsize=8, loc="upper right")
            if v == 0:
                axl.set_title("横向误差")

            axs = axes[v, 1]
            axs.plot(db["t"], db["e_s"], "--", color=colors_v[v], linewidth=1.5, label=f"{labels_v[v]} Baseline")
            axs.plot(dm["t"], dm["e_s"], "-", color=colors_v[v], linewidth=1.9, label=f"{labels_v[v]} 主方法")
            axs.axhline(0.0, color="gray", linestyle=":", linewidth=1.0)
            axs.set_ylabel("e_s [m]")
            axs.grid(True, alpha=0.30)
            axs.legend(fontsize=8, loc="upper right")
            if v == 0:
                axs.set_title("纵向误差")

        axes[3, 0].set_xlabel("时间 [s]")
        axes[3, 1].set_xlabel("时间 [s]")

        fpath = out_dir / f"fig_lat_long_each_vehicle_{mode}.png"
        _save_show(fig, fpath, show)
        summary["figures"].append(str(fpath))

    # ----------------------------------
    # Figure C: phase portrait clusters
    # ----------------------------------
    for mode in modes:
        fig, axes = plt.subplots(2, 3, figsize=(16, 10))
        fig.suptitle(f"{mode.upper()} 相图簇：r vs r_dot（系统+四车）", fontsize=15, fontweight="bold")
        ents = ["system", "vehicle_1", "vehicle_2", "vehicle_3", "vehicle_4"]
        titles = ["系统", "车1", "车2", "车3", "车4"]

        for i, ent in enumerate(ents):
            ax = axes[i // 3, i % 3]
            for method, color, alpha_main in [("baseline", "tab:gray", 0.22), ("main", "tab:blue", 0.26)]:
                d = extracted[mode][method][ent]
                r = d["r"]
                rdot = d["rdot"]
                n = r.size
                seg = max(20, n // 18)
                step = max(8, seg // 3)
                for st in range(0, max(1, n - seg), step):
                    ax.plot(r[st:st+seg], rdot[st:st+seg], color=color, alpha=alpha_main, linewidth=1.0)
                ax.plot(r, rdot, color=("tab:red" if method == "main" else "tab:green"), linewidth=1.6, alpha=0.9,
                        label=("主方法主轨迹" if method == "main" else "Baseline主轨迹"))
            ax.scatter([r[0]], [rdot[0]], c="yellow", s=18, edgecolors="k", linewidths=0.4, zorder=4)
            ax.scatter([r[-1]], [rdot[-1]], c="red", s=18, edgecolors="k", linewidths=0.4, zorder=4)
            ax.set_title(titles[i])
            ax.set_xlabel("r [rad/s]")
            ax.set_ylabel("r_dot [rad/s^2]")
            ax.grid(True, alpha=0.30)
            ax.legend(fontsize=8, loc="upper right")

        axes[1, 2].axis("off")
        fpath = out_dir / f"fig_phase_cluster_{mode}.png"
        _save_show(fig, fpath, show)
        summary["figures"].append(str(fpath))

    # ------------------------------------------------------
    # Figure D: stability-region phase map (inside/outside)
    # ------------------------------------------------------
    for mode in modes:
        fig, axes = plt.subplots(2, 3, figsize=(16, 10))
        fig.suptitle(f"{mode.upper()} 稳定区域判定相图（系统+四车）", fontsize=15, fontweight="bold")

        ents = ["system", "vehicle_1", "vehicle_2", "vehicle_3", "vehicle_4"]
        titles = ["系统", "车1", "车2", "车3", "车4"]
        stable_stats = {}

        for i, ent in enumerate(ents):
            ax = axes[i // 3, i % 3]
            dm = extracted[mode]["main"][ent]
            db = extracted[mode]["baseline"][ent]

            p_main = np.column_stack([dm["r"], dm["rdot"]])
            p_base = np.column_stack([db["r"], db["rdot"]])

            n_tail = max(20, int(0.45 * p_main.shape[0]))
            ref_pts = p_main[-n_tail:, :]
            poly = _phase_hull(ref_pts)

            if poly is not None:
                poly_path = MplPath(poly)
                in_main = poly_path.contains_points(p_main)
                in_base = poly_path.contains_points(p_base)
                ax.fill(poly[:, 0], poly[:, 1], color="tab:green", alpha=0.20, label="稳定区域")
            else:
                r0 = np.quantile(np.abs(ref_pts[:, 0]), 0.80)
                rd0 = np.quantile(np.abs(ref_pts[:, 1]), 0.80)
                in_main = (np.abs(p_main[:, 0]) <= r0) & (np.abs(p_main[:, 1]) <= rd0)
                in_base = (np.abs(p_base[:, 0]) <= r0) & (np.abs(p_base[:, 1]) <= rd0)
                xx = np.array([-r0, r0, r0, -r0, -r0])
                yy = np.array([-rd0, -rd0, rd0, rd0, -rd0])
                ax.fill(xx, yy, color="tab:green", alpha=0.20, label="稳定区域(箱体)")

            ax.scatter(p_base[~in_base, 0], p_base[~in_base, 1], s=6, c="tab:gray", alpha=0.55, label="Baseline 区外")
            ax.scatter(p_base[in_base, 0], p_base[in_base, 1], s=6, c="tab:blue", alpha=0.55, label="Baseline 区内")
            ax.scatter(p_main[~in_main, 0], p_main[~in_main, 1], s=6, c="tab:orange", alpha=0.65, label="主方法 区外")
            ax.scatter(p_main[in_main, 0], p_main[in_main, 1], s=6, c="tab:red", alpha=0.65, label="主方法 区内")

            ratio_main = float(np.mean(in_main)) if in_main.size else np.nan
            ratio_base = float(np.mean(in_base)) if in_base.size else np.nan
            stable_stats[ent] = {"main": ratio_main, "baseline": ratio_base}

            ax.set_title(f"{titles[i]} | 区内比 Main={ratio_main:.1%}, Base={ratio_base:.1%}")
            ax.set_xlabel("r [rad/s]")
            ax.set_ylabel("r_dot [rad/s^2]")
            ax.grid(True, alpha=0.30)
            ax.legend(fontsize=7, loc="upper right")

        axes[1, 2].axis("off")
        ax_txt = axes[1, 2]
        ax_txt.text(
            0.02,
            0.98,
            "稳定判定：\n1) 以主方法尾段相轨迹构建区域\n2) 统计轨迹落入比例\n3) 对比 Baseline / Main",
            va="top",
            fontsize=11,
        )

        fpath = out_dir / f"fig_stability_region_{mode}.png"
        _save_show(fig, fpath, show)
        summary["figures"].append(str(fpath))
        summary["metrics"][f"stability_{mode}"] = stable_stats

    # -----------------------------------------------
    # Figure E: construction of an example zonotope
    # -----------------------------------------------
    z_mode = "hairpin" if "hairpin" in modes else modes[0]
    dm_sys = extracted[z_mode]["main"]["system"]
    err2 = np.column_stack([dm_sys["e_y"], dm_sys["e_s"]])
    err2 = err2[np.all(np.isfinite(err2), axis=1)]
    c = np.mean(err2, axis=0)
    cov = np.cov(err2.T)
    eigval, eigvec = np.linalg.eigh(cov + 1e-9 * np.eye(2))
    order = np.argsort(eigval)[::-1]
    eigval = eigval[order]
    eigvec = eigvec[:, order]
    g1 = eigvec[:, 0] * np.sqrt(max(eigval[0], 1e-9)) * 2.0
    g2 = eigvec[:, 1] * np.sqrt(max(eigval[1], 1e-9)) * 2.0
    g3 = 0.35 * np.array([g1[0], -g2[1]])
    G = np.column_stack([g1, g2, g3])

    # sample zonotope points
    m = 2000
    xi = np.random.uniform(-1.0, 1.0, size=(G.shape[1], m))
    pts = (c.reshape(-1, 1) + G @ xi).T
    poly = _phase_hull(pts)

    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111)
    ax.scatter(err2[:, 0], err2[:, 1], s=6, c="tab:gray", alpha=0.25, label="误差样本")
    ax.scatter(pts[:, 0], pts[:, 1], s=5, c="tab:cyan", alpha=0.12, label="zonotope采样")
    if poly is not None:
        ax.fill(poly[:, 0], poly[:, 1], color="tab:blue", alpha=0.18, label="示例Zonotope")
    ax.scatter([c[0]], [c[1]], c="red", s=40, label="中心")
    for j in range(G.shape[1]):
        ax.arrow(c[0], c[1], G[0, j], G[1, j], width=0.0005, head_width=0.005, color="tab:red", alpha=0.85)
    ax.set_title("Construction of an Example Zonotope")
    ax.set_xlabel("e_y [m]")
    ax.set_ylabel("e_s [m]")
    ax.grid(True, alpha=0.30)
    ax.legend(loc="upper right")
    fpath = out_dir / "fig_example_zonotope.png"
    _save_show(fig, fpath, show)
    summary["figures"].append(str(fpath))

    # ------------------------------------------------
    # Figure F: Koopman modeling error constraint plot
    # ------------------------------------------------
    fig, axes = plt.subplots(len(modes), 1, figsize=(13, 4.2 * len(modes)), sharex=False)
    if len(modes) == 1:
        axes = [axes]
    koop_metrics = {}
    for ax, mode in zip(axes, modes):
        rb = compare_results_b1_dual[mode]["baseline_bilinear_adaptnet"]
        rm = compare_results_b1_dual[mode]["main_tf12_full"]
        zb = np.asarray(rb["z_vehicles"][0], dtype=float)
        zm = np.asarray(rm["z_vehicles"][0], dtype=float)
        ub = np.asarray(rb["team_input_hist"], dtype=float)
        um = np.asarray(rm["team_input_hist"], dtype=float)

        eb = _fit_linear_residual(zb, ub, ridge=1e-4)
        em = _fit_linear_residual(zm, um, ridge=1e-4)
        tb = np.arange(eb.size) * float(dt)
        tm = np.arange(em.size) * float(dt)
        bb = float(np.quantile(eb, 0.95) * 1.05) if eb.size else np.nan
        bm = float(np.quantile(em, 0.95) * 1.05) if em.size else np.nan

        ax.plot(tb, eb, "--", color="tab:gray", linewidth=1.4, label="Baseline modeling error")
        ax.plot(tm, em, "-", color="tab:red", linewidth=1.8, label="Main modeling error")
        if np.isfinite(bb):
            ax.axhline(bb, color="tab:blue", linestyle=":", linewidth=1.1, label=f"Baseline constraint={bb:.4f}")
        if np.isfinite(bm):
            ax.axhline(bm, color="tab:green", linestyle=":", linewidth=1.1, label=f"Main constraint={bm:.4f}")
        ax.set_title(f"Koopman Modeling Error Constraint ({mode.upper()})")
        ax.set_xlabel("时间 [s]")
        ax.set_ylabel("||e_k|| [-]")
        ax.grid(True, alpha=0.30)
        ax.legend(fontsize=8, ncol=2, loc="upper right")
        koop_metrics[mode] = {
            "baseline_mean": float(np.mean(eb)) if eb.size else np.nan,
            "main_mean": float(np.mean(em)) if em.size else np.nan,
            "baseline_constraint": bb,
            "main_constraint": bm,
        }

    fpath = out_dir / "fig_koopman_error_constraint.png"
    _save_show(fig, fpath, show)
    summary["figures"].append(str(fpath))
    summary["metrics"]["koopman_constraint"] = koop_metrics

    # -------------------------------------------
    # Figure G: visualization of convergence
    # -------------------------------------------
    fig, axes = plt.subplots(1, len(modes), figsize=(7 * len(modes), 5), sharey=True)
    if len(modes) == 1:
        axes = [axes]
    conv_metrics = {}
    for ax, mode in zip(axes, modes):
        db = extracted[mode]["baseline"]["system"]
        dm = extracted[mode]["main"]["system"]
        eb = np.asarray(db["e_pos"], dtype=float)
        em = np.asarray(dm["e_pos"], dtype=float)
        rb = np.sqrt(np.maximum(1e-12, np.cumsum(eb ** 2) / np.arange(1, eb.size + 1)))
        rm = np.sqrt(np.maximum(1e-12, np.cumsum(em ** 2) / np.arange(1, em.size + 1)))
        tb = np.arange(eb.size) * float(dt)
        tm = np.arange(em.size) * float(dt)
        ax.semilogy(tb, rb, "--", color="tab:gray", linewidth=1.7, label="Baseline RMS running")
        ax.semilogy(tm, rm, "-", color="tab:red", linewidth=2.0, label="Main RMS running")
        ax.axhline(0.01, color="tab:orange", linestyle=":", linewidth=1.0, label="0.01")
        ax.set_title(f"Visualization of Convergence ({mode.upper()})")
        ax.set_xlabel("时间 [s]")
        ax.grid(True, alpha=0.30, which="both")
        ax.legend(fontsize=8, loc="upper right")
        conv_metrics[mode] = {
            "baseline_final_running_rms": float(rb[-1]) if rb.size else np.nan,
            "main_final_running_rms": float(rm[-1]) if rm.size else np.nan,
        }
    axes[0].set_ylabel("Running RMS of position error [m]")

    fpath = out_dir / "fig_convergence_process.png"
    _save_show(fig, fpath, show)
    summary["figures"].append(str(fpath))
    summary["metrics"]["convergence"] = conv_metrics

    # -------------------------------------------------
    # Figure H: 3D stacked error lines (image-like style)
    # -------------------------------------------------
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    mode = "hairpin" if "hairpin" in modes else modes[0]
    fig = plt.figure(figsize=(14, 6))
    for j, method in enumerate(["baseline", "main"], start=1):
        ax = fig.add_subplot(1, 2, j, projection="3d")
        ax.set_title(f"{mode.upper()} 3D Error Stack - {method}")
        traces = [("LLD", extracted[mode][method]["system"]["e_pos"])]
        for v in range(4):
            traces.append((f"FLD {v+1}", extracted[mode][method][f"vehicle_{v+1}"]["e_pos"]))

        for yi, (name, arr) in enumerate(traces):
            arr = np.asarray(arr, dtype=float)
            n = arr.size
            t = np.arange(n)
            y = np.full(n, yi, dtype=float)
            z = arr - np.mean(arr)
            ax.plot(t, y, z, linewidth=1.6, label=name)

        ax.set_xlabel("Time-Samples [-]")
        ax.set_ylabel("Trace [-]")
        ax.set_zlabel("Error [m]")
        ax.set_yticks(np.arange(len(traces)))
        ax.set_yticklabels([x[0] for x in traces])
        ax.legend(fontsize=7, loc="upper right")

    fpath = out_dir / "fig_3d_error_stack.png"
    _save_show(fig, fpath, show)
    summary["figures"].append(str(fpath))

    # ---------------------------------
    # summary metrics for each 5-steps
    # ---------------------------------
    metric_pack = {}
    for mode in modes:
        metric_pack[mode] = {}
        for method in ["baseline", "main"]:
            vals_max = []
            vals_mean = []
            vals_group5 = []
            for ent in ["vehicle_1", "vehicle_2", "vehicle_3", "vehicle_4"]:
                epos = extracted[mode][method][ent]["e_pos"]
                vals_max.append(float(np.max(np.abs(epos))) if epos.size else np.nan)
                vals_mean.append(float(np.mean(np.abs(epos))) if epos.size else np.nan)
                g5 = _chunk5_mean_abs(epos)
                vals_group5.append(float(np.mean(g5)) if g5.size else np.nan)

            result_raw = compare_results_b1_dual[mode]["main_tf12_full"] if method == "main" else compare_results_b1_dual[mode]["baseline_bilinear_adaptnet"]
            metric_pack[mode][method] = {
                "fleet_max_abs_pos_err": float(np.nanmax(vals_max)),
                "fleet_mean_abs_pos_err": float(np.nanmean(vals_mean)),
                "fleet_mean_abs_pos_err_every5": float(np.nanmean(vals_group5)),
                "step_time_mean": float(result_raw.get("step_time_mean", np.nan)),
                "step_time_max": float(result_raw.get("step_time_max", np.nan)),
                "rmse_lat_mean": float(result_raw.get("rmse_lat_mean", np.nan)),
                "rmse_long_mean": float(result_raw.get("rmse_long_mean", np.nan)),
                "max_lat_global": float(result_raw.get("max_lat_global", np.nan)),
                "max_long_global": float(result_raw.get("max_long_global", np.nan)),
            }

    summary["metrics"]["comparison_core"] = metric_pack

    # ---------------------------------
    # Figure I: core metric bar compare
    # ---------------------------------
    fig, axes = plt.subplots(1, len(modes), figsize=(7 * len(modes), 5), sharey=False)
    if len(modes) == 1:
        axes = [axes]
    for ax, mode in zip(axes, modes):
        mb = metric_pack[mode]["baseline"]
        mm = metric_pack[mode]["main"]
        metric_names = [
            "fleet_max_abs_pos_err",
            "fleet_mean_abs_pos_err",
            "fleet_mean_abs_pos_err_every5",
            "step_time_mean",
        ]
        vals_b = [mb[k] for k in metric_names]
        vals_m = [mm[k] for k in metric_names]
        x = np.arange(len(metric_names))
        w = 0.34
        ax.bar(x - w/2, vals_b, width=w, color="tab:gray", alpha=0.85, label="Baseline")
        ax.bar(x + w/2, vals_m, width=w, color="tab:red", alpha=0.85, label="Main")
        ax.set_xticks(x)
        ax.set_xticklabels(["max", "mean", "mean/5", "time"], rotation=0)
        ax.set_title(f"{mode.upper()} Core Metrics")
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend(fontsize=8)

    fpath = out_dir / "fig_core_metric_bar_compare.png"
    _save_show(fig, fpath, show)
    summary["figures"].append(str(fpath))

    # ----------------------------------------------------
    # Figure J: mean absolute position error every 5 steps
    # ----------------------------------------------------
    fig, axes = plt.subplots(1, len(modes), figsize=(7 * len(modes), 5), sharey=False)
    if len(modes) == 1:
        axes = [axes]
    for ax, mode in zip(axes, modes):
        # fleet averaged every-5-step absolute error
        g5_b = []
        g5_m = []
        max_len = 0
        for ent in ["vehicle_1", "vehicle_2", "vehicle_3", "vehicle_4"]:
            eb = _chunk5_mean_abs(extracted[mode]["baseline"][ent]["e_pos"])
            em = _chunk5_mean_abs(extracted[mode]["main"][ent]["e_pos"])
            g5_b.append(eb)
            g5_m.append(em)
            max_len = max(max_len, eb.size, em.size)

        B = np.full((4, max_len), np.nan)
        M = np.full((4, max_len), np.nan)
        for i in range(4):
            B[i, : g5_b[i].size] = g5_b[i]
            M[i, : g5_m[i].size] = g5_m[i]

        bb = np.nanmean(B, axis=0)
        mm = np.nanmean(M, axis=0)
        x = np.arange(max_len) * 5
        ax.plot(x, bb, "--", color="tab:gray", linewidth=1.8, label="Baseline 每5步均值")
        ax.plot(x, mm, "-", color="tab:red", linewidth=2.0, label="主方法 每5步均值")
        ax.axhline(0.01, color="tab:orange", linestyle=":", linewidth=1.0, alpha=0.9, label="0.01 m")
        ax.set_title(f"{mode.upper()} 每5步位置误差均值")
        ax.set_xlabel("样本步 [-]")
        ax.set_ylabel("mean |e_pos| [m]")
        ax.grid(True, alpha=0.30)
        ax.legend(fontsize=8, loc="upper right")

    fpath = out_dir / "fig_every5_pos_error_compare.png"
    _save_show(fig, fpath, show)
    summary["figures"].append(str(fpath))

    # ----------------------------------------------------------
    # Figure K: historical records trend (loaded from disk files)
    # ----------------------------------------------------------
    history_metrics = {
        "enabled": bool(include_history_block),
        "history_root_dir": str(history_root_dir),
        "history_limit": int(history_limit),
        "records_total": 0,
        "records_used": 0,
        "figure": None,
    }
    if include_history_block and load_tf12_history_records is not None:
        records = load_tf12_history_records(
            root_dir=history_root_dir,
            limit=int(max(1, history_limit)),
            load_series=False,
        )
        history_metrics["records_total"] = int(len(records))

        rows = []
        for rec in records:
            md = rec.get("metadata", {})
            mode = _infer_hist_mode(md)
            if mode not in modes:
                continue
            method = _infer_hist_method(md.get("method_name", ""))
            if method not in ("baseline", "main"):
                continue
            rows.append({
                "timestamp_local": str(md.get("timestamp_local", "")),
                "mode": mode,
                "method": method,
                "fleet_max_abs_pos_err": float(
                    max(
                        abs(float(md.get("max_lat_global", np.nan))),
                        abs(float(md.get("max_long_global", np.nan))),
                    )
                ),
                "step_time_mean": float(md.get("step_time_mean", np.nan)),
            })

        rows.sort(key=lambda x: x["timestamp_local"])
        history_metrics["records_used"] = int(len(rows))

        if len(rows) > 0:
            hist_modes = [m for m in modes if any(r["mode"] == m for r in rows)]
            fig, axes = plt.subplots(2, len(hist_modes), figsize=(7 * len(hist_modes), 8), sharex=False)
            if len(hist_modes) == 1:
                axes = np.array(axes).reshape(2, 1)

            for col, mode in enumerate(hist_modes):
                mode_rows = [r for r in rows if r["mode"] == mode]
                for method, color, marker in [("baseline", "tab:gray", "o"), ("main", "tab:red", "s")]:
                    mr = [r for r in mode_rows if r["method"] == method]
                    if len(mr) == 0:
                        continue
                    x = np.arange(len(mr), dtype=int)
                    y_err = np.array([r["fleet_max_abs_pos_err"] for r in mr], dtype=float)
                    y_time = np.array([r["step_time_mean"] for r in mr], dtype=float)
                    axes[0, col].plot(
                        x, y_err, marker=marker, markersize=4, linewidth=1.4, color=color,
                        label=f"{method}"
                    )
                    axes[1, col].plot(
                        x, y_time, marker=marker, markersize=4, linewidth=1.4, color=color,
                        label=f"{method}"
                    )

                axes[0, col].set_title(f"{mode.upper()} 历史最大位置误差")
                axes[0, col].set_ylabel("max(|e|) [m]")
                axes[0, col].grid(True, alpha=0.30)
                axes[0, col].legend(fontsize=8, loc="upper right")

                axes[1, col].set_title(f"{mode.upper()} 历史平均步耗时")
                axes[1, col].set_xlabel("历史记录序号（同方法内）[-]")
                axes[1, col].set_ylabel("step_time_mean [s]")
                axes[1, col].grid(True, alpha=0.30)
                axes[1, col].legend(fontsize=8, loc="upper right")

            fig.suptitle("TF12 历史记录趋势（来自 results/history/tf12）", fontsize=14, fontweight="bold")
            fpath = out_dir / "fig_history_trend_from_records.png"
            _save_show(fig, fpath, show)
            summary["figures"].append(str(fpath))
            history_metrics["figure"] = str(fpath)
    elif include_history_block and load_tf12_history_records is None:
        history_metrics["enabled"] = False
        history_metrics["reason"] = "history_loader_unavailable"

    summary["metrics"]["history_records"] = history_metrics

    # save summary as npy/json-like text
    summary_path = out_dir / "tf12_full_compare_summary.npy"
    np.save(summary_path, summary, allow_pickle=True)
    summary["summary_file"] = str(summary_path)

    return summary

