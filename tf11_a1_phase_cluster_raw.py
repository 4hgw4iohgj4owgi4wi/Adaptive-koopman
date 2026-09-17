import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree


DEFAULT_PHASE_CLUSTER_CFG = {
    "k_neigh": 14,
    "dt_sim": 0.02,
    "r_bound_scale": 1.9,
    "rdot_bound_scale": 1.9,
    "smooth_win": 7,
    "seed": 2026,
    # Increased sample count to expand initial-value diversity.
    "traj_only_samples": 520,
    "traj_only_len": 120,
    # Mixed sampling: a portion starts directly from historical phase points.
    "hist_seed_ratio": 0.38,
    # Relative jitter (w.r.t. axis limits) around each initial state.
    "seed_jitter_r": 0.05,
    "seed_jitter_rdot": 0.05,
    # Disable overlay of current run trajectory by default.
    "show_current_trajectory": False,
    "show_current_points": False,
    "show_attractor_marker": False,
    # Optional upper bound for model count in one figure.
    "max_items": 5,
    "figsize": (18, 10),
}


def _moving_average(arr, win):
    arr = np.asarray(arr, dtype=float).reshape(-1)
    if win <= 1 or arr.size < 3:
        return arr
    win = int(max(1, min(win, max(3, arr.size // 4))))
    if win % 2 == 0:
        win += 1
    ker = np.ones(win, dtype=float) / float(win)
    return np.convolve(arr, ker, mode="same")


def _phase_from_hist(r_hist, dt_val, smooth_win):
    r_hist = np.asarray(r_hist, dtype=float).reshape(-1)
    valid = np.isfinite(r_hist)
    r = r_hist[valid]
    if r.size < 8:
        return None
    r = _moving_average(r, smooth_win)
    rdot = np.gradient(r, float(dt_val))
    rdot = _moving_average(rdot, max(3, smooth_win - 2))
    rddot = np.gradient(rdot, float(dt_val))
    phase = np.column_stack([r, rdot])
    return phase, rddot


def _build_phase_model(phase_pts, rddot_targets):
    tree = cKDTree(phase_pts)
    y = np.asarray(rddot_targets, dtype=float).reshape(-1)

    def pred_rddot(x_query, k_neigh=12):
        xq = np.asarray(x_query, dtype=float)
        if xq.ndim == 1:
            xq = xq.reshape(1, 2)
        k_eff = int(max(1, min(k_neigh, phase_pts.shape[0])))
        d, idx = tree.query(xq, k=k_eff)
        if k_eff == 1:
            d = d.reshape(-1, 1)
            idx = idx.reshape(-1, 1)
        w = 1.0 / np.maximum(d, 1e-6)
        return np.sum(w * y[idx], axis=1) / np.sum(w, axis=1)

    return pred_rddot


def _simulate_traj(x0, pred_fn, cfg, r_lim, rd_lim, n_steps=60):
    x = np.asarray(x0, dtype=float).reshape(2)
    out = [x.copy()]
    for _ in range(int(n_steps)):
        if (not np.all(np.isfinite(x))) or (abs(x[0]) > r_lim) or (abs(x[1]) > rd_lim):
            break
        rdd = float(pred_fn(x, k_neigh=cfg["k_neigh"])[0])
        x = np.array(
            [
                x[0] + cfg["dt_sim"] * x[1],
                x[1] + cfg["dt_sim"] * rdd,
            ],
            dtype=float,
        )
        out.append(x.copy())
    return np.array(out, dtype=float)


def _sample_initial_states(phase_pts, rr, rrd, n_traj, cfg, rng, r_lim, rd_lim):
    n_traj = int(max(1, n_traj))
    rr_flat = rr.reshape(-1)
    rrd_flat = rrd.reshape(-1)

    # Uniform grid seeds.
    idx_uniform = rng.integers(0, rr_flat.size, size=n_traj)
    starts = np.column_stack([rr_flat[idx_uniform], rrd_flat[idx_uniform]])

    # Replace part with historical seeds for richer realistic initialization.
    hist_ratio = float(np.clip(cfg.get("hist_seed_ratio", 0.3), 0.0, 1.0))
    n_hist = int(hist_ratio * n_traj)
    if phase_pts is not None and phase_pts.shape[0] > 0 and n_hist > 0:
        idx_hist = rng.integers(0, phase_pts.shape[0], size=n_hist)
        starts[:n_hist, :] = phase_pts[idx_hist, :]

    # Local jitter to expand data cloud.
    jit_r = float(cfg.get("seed_jitter_r", 0.0)) * float(r_lim)
    jit_rd = float(cfg.get("seed_jitter_rdot", 0.0)) * float(rd_lim)
    if jit_r > 0.0 or jit_rd > 0.0:
        starts[:, 0] += rng.normal(0.0, jit_r, size=n_traj)
        starts[:, 1] += rng.normal(0.0, jit_rd, size=n_traj)

    starts[:, 0] = np.clip(starts[:, 0], -r_lim, r_lim)
    starts[:, 1] = np.clip(starts[:, 1], -rd_lim, rd_lim)
    return starts


def build_phase_items(main_result, team_state_hist, xt_actual_vehicles, dt, num_vehicles):
    sim_steps_phase = int(main_result.get("sim_steps", team_state_hist.shape[0] - 1))
    sim_steps_phase = max(10, sim_steps_phase)

    phase_items = []
    labels_v = ["车1 (前左)", "车2 (前右)", "车3 (后左)", "车4 (后右)"]
    colors_v = ["tab:blue", "tab:purple", "tab:green", "tab:red"]

    if isinstance(team_state_hist, np.ndarray) and team_state_hist.ndim == 2 and team_state_hist.shape[1] >= 6:
        n_team = min(sim_steps_phase + 1, team_state_hist.shape[0])
        phase_items.append(
            {
                "name": "系统整体",
                "color": "tab:blue",
                "r_hist": team_state_hist[:n_team, 5],
            }
        )

    for v in range(int(num_vehicles)):
        x_hist = np.asarray(xt_actual_vehicles[v], dtype=float)
        if x_hist.ndim != 2 or x_hist.shape[1] < 6:
            continue
        n_hist = min(sim_steps_phase + 1, x_hist.shape[0])
        phase_items.append(
            {
                "name": labels_v[v] if v < len(labels_v) else f"车{v+1}",
                "color": colors_v[v % len(colors_v)],
                "r_hist": x_hist[:n_hist, 5],
            }
        )
    return phase_items


def plot_raw_phase_clusters(
    *,
    main_result,
    team_state_hist,
    xt_actual_vehicles,
    dt,
    num_vehicles=4,
    cfg=None,
    save_path=None,
    show=True,
):
    """
    Draw raw phase trajectory clusters in a standalone file workflow.

    Inputs:
    - main_result, team_state_hist, xt_actual_vehicles, dt:
      Same runtime variables from tf11_A1 main notebook.
    - cfg:
      Optional dict to override DEFAULT_PHASE_CLUSTER_CFG.
    """
    if main_result is None:
        raise RuntimeError("main_result is None. Run TF11-A1 main method first.")
    if team_state_hist is None or xt_actual_vehicles is None:
        raise RuntimeError("team_state_hist / xt_actual_vehicles is missing.")

    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    run_cfg = dict(DEFAULT_PHASE_CLUSTER_CFG)
    if cfg:
        run_cfg.update(cfg)
    run_cfg["dt_sim"] = float(run_cfg.get("dt_sim", dt))

    base_items = build_phase_items(main_result, team_state_hist, xt_actual_vehicles, dt, num_vehicles)
    if len(base_items) == 0:
        raise RuntimeError("No valid phase data for plotting.")

    model_items = []
    for item in base_items[: int(run_cfg.get("max_items", 5))]:
        pack = _phase_from_hist(item["r_hist"], dt, run_cfg["smooth_win"])
        if pack is None:
            continue
        phase_pts, rddot_t = pack
        model_items.append(
            {
                "name": item["name"],
                "color": item["color"],
                "phase": phase_pts,
                "rddot": rddot_t,
                "pred_fn": _build_phase_model(phase_pts, rddot_t),
            }
        )
    if len(model_items) == 0:
        raise RuntimeError("No usable phase model items after preprocessing.")

    r_all = np.concatenate([it["phase"][:, 0] for it in model_items], axis=0)
    rd_all = np.concatenate([it["phase"][:, 1] for it in model_items], axis=0)
    r_span = np.percentile(np.abs(r_all), 99)
    rd_span = np.percentile(np.abs(rd_all), 99)
    r_lim = max(0.20, float(run_cfg["r_bound_scale"]) * float(r_span))
    rd_lim = max(0.40, float(run_cfg["rdot_bound_scale"]) * float(rd_span))

    # Seed lattice for initial state sampling.
    grid_n = int(max(30, np.sqrt(run_cfg["traj_only_samples"]) * 2))
    r_grid = np.linspace(-r_lim, r_lim, grid_n)
    rd_grid = np.linspace(-rd_lim, rd_lim, grid_n)
    rr, rrd = np.meshgrid(r_grid, rd_grid)

    rng = np.random.default_rng(int(run_cfg["seed"]))

    fig, axes = plt.subplots(2, 3, figsize=tuple(run_cfg["figsize"]), constrained_layout=True)
    axes = axes.flatten()
    fig.suptitle("TF11-A1 原始相轨迹簇图（系统整体 + 四车）\n相平面: r - r_dot", fontsize=15, fontweight="bold")

    summary_rows = []
    for idx, model in enumerate(model_items):
        ax = axes[idx]
        phase_pts = model["phase"]
        starts = _sample_initial_states(
            phase_pts=phase_pts,
            rr=rr,
            rrd=rrd,
            n_traj=run_cfg["traj_only_samples"],
            cfg=run_cfg,
            rng=rng,
            r_lim=r_lim,
            rd_lim=rd_lim,
        )

        cmap = plt.cm.turbo
        valid_count = 0
        for j, s0 in enumerate(starts):
            tr = _simulate_traj(
                s0,
                model["pred_fn"],
                run_cfg,
                r_lim,
                rd_lim,
                n_steps=run_cfg["traj_only_len"],
            )
            if tr.shape[0] > 1:
                ax.plot(tr[:, 0], tr[:, 1], color=cmap(j / max(1, starts.shape[0] - 1)), alpha=0.70, linewidth=0.85)
                valid_count += 1

        tail_n = max(8, int(0.12 * phase_pts.shape[0]))
        attractor = np.mean(phase_pts[-tail_n:, :], axis=0)

        if bool(run_cfg.get("show_current_trajectory", False)):
            ax.plot(phase_pts[:, 0], phase_pts[:, 1], color="white", linewidth=2.0, alpha=0.95, label="历史轨迹")
        if bool(run_cfg.get("show_current_points", False)):
            ax.scatter(
                phase_pts[0, 0],
                phase_pts[0, 1],
                s=34,
                c="yellow",
                edgecolors="k",
                linewidths=0.6,
                marker="o",
                label="历史起点",
            )
            ax.scatter(
                phase_pts[-1, 0],
                phase_pts[-1, 1],
                s=34,
                c="red",
                edgecolors="k",
                linewidths=0.6,
                marker="X",
                label="历史终点",
            )
        if bool(run_cfg.get("show_attractor_marker", False)):
            ax.scatter(
                attractor[0],
                attractor[1],
                s=56,
                c="lime",
                edgecolors="k",
                linewidths=0.8,
                marker="*",
                label="吸引点",
            )
        ax.set_title(f"{model['name']} | 相轨迹簇", fontsize=11)
        ax.set_xlabel("r [rad/s]")
        ax.set_ylabel("r_dot [rad/s$^2$]")
        ax.set_xlim(-r_lim, r_lim)
        ax.set_ylim(-rd_lim, rd_lim)
        ax.axhline(0.0, color="gray", linestyle=":", linewidth=0.8)
        ax.axvline(0.0, color="gray", linestyle=":", linewidth=0.8)
        ax.grid(True, alpha=0.25)
        h, l = ax.get_legend_handles_labels()
        if len(h) > 0:
            ax.legend(fontsize=8, loc="upper right")

        summary_rows.append(
            {
                "name": model["name"],
                "phase_points": int(phase_pts.shape[0]),
                "seed_count": int(starts.shape[0]),
                "valid_traj_count": int(valid_count),
            }
        )

    if len(axes) > 5:
        ax_info = axes[5]
        ax_info.axis("off")
        txt = (
            "原始相轨迹簇图说明:\n"
            "1) 彩线=不同初值相轨迹\n"
            "2) 默认不叠加当前实验历史轨迹\n"
            "3) 可通过开关恢复历史轨迹/起终点/吸引点\n\n"
            f"traj_only_samples={run_cfg['traj_only_samples']}\n"
            f"traj_only_len={run_cfg['traj_only_len']}\n"
            f"hist_seed_ratio={run_cfg['hist_seed_ratio']}\n"
            f"seed_jitter_r={run_cfg['seed_jitter_r']}\n"
            f"seed_jitter_rdot={run_cfg['seed_jitter_rdot']}\n"
            f"show_current_trajectory={run_cfg['show_current_trajectory']}"
        )
        ax_info.text(0.05, 0.95, txt, va="top", ha="left", fontsize=11)

    if save_path is not None and str(save_path).strip():
        fig.savefig(str(save_path), dpi=220, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close(fig)

    return {
        "fig": fig,
        "cfg": run_cfg,
        "r_lim": float(r_lim),
        "rd_lim": float(rd_lim),
        "items": summary_rows,
    }
