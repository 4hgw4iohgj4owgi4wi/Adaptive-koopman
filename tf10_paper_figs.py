"""Generate paper-style figures (Fig.1~Fig.8) using TF10 experiment data.

This module is designed for interactive notebook use. It expects the caller
(notebook) to provide runtime variables and callbacks from tf10_pre.ipynb.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np


def _solver_success_rate(res: Dict[str, Any]) -> float:
    hist = res.get("solver_status_hist", [])
    vals: List[float] = []
    for lst in hist:
        if len(lst) == 0:
            vals.append(np.nan)
            continue
        ok = 0
        for st in lst:
            s = str(st).strip().lower()
            if s in ("fallback", "nonfinite_recover", "", "none"):
                continue
            if "fail" in s or "error" in s:
                continue
            ok += 1
        vals.append(ok / len(lst))
    return float(np.nanmean(vals)) if len(vals) > 0 else np.nan


def _full_path_rate(res: Dict[str, Any]) -> float:
    flags = np.array(res.get("full_path_flags", []), dtype=float)
    return float(np.mean(flags)) if flags.size > 0 else np.nan


def _case_metric(res: Dict[str, Any], key: str, num_vehicles: int) -> float:
    m = res.get("metrics", {})
    if isinstance(m, dict) and key in m:
        return float(m[key])
    if key == "solver_success_rate":
        return _solver_success_rate(res)
    if key == "full_path_rate":
        return _full_path_rate(res)
    if key == "fail_total":
        return float(np.sum(res.get("fail_counts", [])))
    if key == "progress_guard_total":
        return float(np.sum(res.get("progress_guard_counts", [0] * num_vehicles)))
    return float(res.get(key, np.nan))


def _main_case_name(compare_results: Dict[str, Dict[str, Any]]) -> str:
    if "tf10_main" in compare_results:
        return "tf10_main"
    return list(compare_results.keys())[0]


def _get_errors(
    res: Dict[str, Any],
    dt: float,
    num_vehicles: int,
    x_ref_raw: np.ndarray,
    x0_vehicles: List[np.ndarray],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    xts = res["xt_actual_vehicles"]
    sim_steps = int(res.get("sim_steps", xts[0].shape[0] - 1))
    eval_len = sim_steps + 1
    t = np.arange(eval_len) * dt

    e_lat_vs: List[np.ndarray] = []
    e_long_vs: List[np.ndarray] = []
    for v in range(num_vehicles):
        x_hist = xts[v][:eval_len, :]

        s_ref_base = x_ref_raw[0, :] + x0_vehicles[v][0]
        if eval_len <= s_ref_base.shape[0]:
            s_ref_v = s_ref_base[:eval_len]
        else:
            s_ref_v = np.concatenate(
                [s_ref_base, np.full(eval_len - s_ref_base.shape[0], s_ref_base[-1])]
            )
        ey_ref_v = np.full(eval_len, x0_vehicles[v][1])

        e_long_vs.append(x_hist[:, 0] - s_ref_v)
        e_lat_vs.append(x_hist[:, 1] - ey_ref_v)

    e_lat_mean = np.mean(np.vstack(e_lat_vs), axis=0)
    e_long_mean = np.mean(np.vstack(e_long_vs), axis=0)
    return t, e_lat_mean, e_long_mean


def _plot_case_path(
    ax: Any,
    res: Dict[str, Any],
    num_vehicles: int,
    x_path: np.ndarray,
    y_ref_path: np.ndarray,
    s_ref_path: np.ndarray,
    psi_ref_path: np.ndarray,
    frenet_to_global: Any,
    title: str,
) -> None:
    ax.plot(x_path, y_ref_path, color="black", linewidth=2.0, label="Reference")
    colors = ["tab:blue", "tab:purple", "tab:green", "tab:red"]
    for v in range(num_vehicles):
        sim_steps = int(res.get("sim_steps", res["xt_actual_vehicles"][v].shape[0] - 1))
        s_v = res["xt_actual_vehicles"][v][: sim_steps + 1, 0]
        ey_v = res["xt_actual_vehicles"][v][: sim_steps + 1, 1]
        s_v = np.clip(s_v, s_ref_path[0], s_ref_path[-1])
        xv, yv = frenet_to_global(s_v, ey_v, s_ref_path, x_path, y_ref_path, psi_ref_path)
        ax.plot(xv, yv, color=colors[v % len(colors)], linewidth=1.5, label=f"car{v + 1}")
    ax.set_title(title)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.grid(True, alpha=0.3)


def _finalize(fig: Any, fig_dir: str, stem: str, dpi: int, save_pdf: bool, show: bool) -> List[str]:
    saved = []
    png_path = os.path.join(fig_dir, f"{stem}.png")
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight")
    saved.append(png_path)
    if save_pdf:
        pdf_path = os.path.join(fig_dir, f"{stem}.pdf")
        fig.savefig(pdf_path, bbox_inches="tight")
        saved.append(pdf_path)
    if show:
        plt.show()
    else:
        plt.close(fig)
    return saved


def generate_tf10_paper_figures(
    *,
    compare_results: Dict[str, Dict[str, Any]],
    tf10_modules_default: Dict[str, Any],
    tf10_ablation_cases: List[Dict[str, Any]],
    run_tf10_case: Any,
    dt: float,
    num_vehicles: int,
    x_ref_raw: np.ndarray,
    x0_vehicles: List[np.ndarray],
    x_path: np.ndarray,
    y_ref_path: np.ndarray,
    s_ref_path: np.ndarray,
    psi_ref_path: np.ndarray,
    frenet_to_global: Any,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate paper-style figures from TF10 data.

    Parameters are intentionally explicit to keep this function reusable from
    notebooks without hidden global dependencies.
    """
    if not isinstance(compare_results, dict) or len(compare_results) == 0:
        raise RuntimeError("compare_results is empty. Run TF10 experiments first.")

    cfg_local = {
        "output_dir": "paper_figs_tf10",
        "dpi": 220,
        "save_pdf": True,
        "show": True,
        # Default: only use existing compare_results, do not launch new runs.
        "run_extra_cases_for_fig3": False,
    }
    if cfg:
        cfg_local.update(cfg)

    fig_dir = str(cfg_local["output_dir"])
    dpi = int(cfg_local["dpi"])
    save_pdf = bool(cfg_local["save_pdf"])
    show = bool(cfg_local["show"])
    run_extra = bool(cfg_local["run_extra_cases_for_fig3"])

    os.makedirs(fig_dir, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["axes.unicode_minus"] = False

    saved_files: List[str] = []

    main_name = _main_case_name(compare_results)
    main_res = compare_results[main_name]

    # Fig.1: module contribution (relative to main method)
    fig1_cases = [c["name"] for c in tf10_ablation_cases if c.get("name") in compare_results]
    base_full = _case_metric(main_res, "full_path_rate", num_vehicles)
    base_rmse = _case_metric(main_res, "rmse_lat_mean", num_vehicles)

    labels, d_full, d_rmse = [], [], []
    for cname in fig1_cases:
        r = compare_results[cname]
        labels.append(cname.replace("abl_", ""))
        d_full.append((_case_metric(r, "full_path_rate", num_vehicles) - base_full) * 100.0)
        d_rmse.append(
            (base_rmse - _case_metric(r, "rmse_lat_mean", num_vehicles))
            / max(abs(base_rmse), 1e-9)
            * 100.0
        )

    if len(labels) > 0:
        x = np.arange(len(labels))
        w = 0.38
        fig = plt.figure(figsize=(12, 4.8))
        plt.bar(x - w / 2, d_full, width=w, label="Completion rate delta (pp)", color="tab:blue")
        plt.bar(x + w / 2, d_rmse, width=w, label="Lateral RMSE improvement (%)", color="tab:orange")
        plt.axhline(0.0, color="black", linewidth=0.8, linestyle=":")
        plt.xticks(x, labels, rotation=20, ha="right")
        plt.ylabel("Relative change vs main")
        plt.title("Fig.1 (TF10): Module contribution")
        plt.legend()
        saved_files += _finalize(fig, fig_dir, "fig1_module_contribution", dpi, save_pdf, show)

    # Fig.2: module on/off matrix
    module_names = list(tf10_modules_default.keys())
    case_names = list(compare_results.keys())
    M = np.zeros((len(case_names), len(module_names)), dtype=float)
    for i, cname in enumerate(case_names):
        mods = compare_results[cname].get("modules", tf10_modules_default)
        for j, mn in enumerate(module_names):
            M[i, j] = 1.0 if bool(mods.get(mn, False)) else 0.0

    fig = plt.figure(figsize=(1.25 * len(module_names) + 2, 0.55 * len(case_names) + 2.2))
    plt.imshow(M, aspect="auto", cmap="YlGn", vmin=0, vmax=1)
    plt.xticks(np.arange(len(module_names)), module_names, rotation=26, ha="right")
    plt.yticks(np.arange(len(case_names)), case_names)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            plt.text(j, i, int(M[i, j]), ha="center", va="center", fontsize=8)
    plt.title("Fig.2 (TF10): Module activation map")
    plt.colorbar(fraction=0.02, pad=0.02, label="Off/On")
    saved_files += _finalize(fig, fig_dir, "fig2_module_matrix", dpi, save_pdf, show)

    # Fig.3: linear/bilinear + adaptive/non-adaptive comparison
    def _ensure_case(name: str, module_overrides: Dict[str, Any], extra_method_cfg: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if name in compare_results:
            return compare_results[name]
        if not run_extra:
            return None
        res = run_tf10_case(name, module_overrides=module_overrides, extra_method_cfg=extra_method_cfg)
        compare_results[name] = res
        return res

    c_lin_no = _ensure_case("paper_lin_noadapt", {"koopman_structure": "linear", "online_adaptation": False})
    c_lin_ad = _ensure_case("paper_lin_adapt", {"koopman_structure": "linear", "online_adaptation": True})
    c_bil_no = _ensure_case("paper_bil_noadapt", {"koopman_structure": "bilinear", "online_adaptation": False})
    c_bil_ad = _ensure_case(
        "paper_bil_adapt",
        {"koopman_structure": "bilinear", "online_adaptation": True},
        extra_method_cfg={"online_adaptation_mode": "bilinear_ridge"},
    )

    if all(c is not None for c in [c_lin_no, c_lin_ad, c_bil_no, c_bil_ad]):
        fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex="col")

        t0, ey0, es0 = _get_errors(c_lin_no, dt, num_vehicles, x_ref_raw, x0_vehicles)
        t1, ey1, es1 = _get_errors(c_lin_ad, dt, num_vehicles, x_ref_raw, x0_vehicles)
        axes[0, 0].plot(t0, ey0, linewidth=1.8, label="Linear-noadapt")
        axes[0, 0].plot(t1, ey1, linewidth=1.8, label="Linear-adapt")
        axes[1, 0].plot(t0, es0, linewidth=1.8)
        axes[1, 0].plot(t1, es1, linewidth=1.8)
        axes[0, 0].set_title("Linear Koopman")

        t0, ey0, es0 = _get_errors(c_bil_no, dt, num_vehicles, x_ref_raw, x0_vehicles)
        t1, ey1, es1 = _get_errors(c_bil_ad, dt, num_vehicles, x_ref_raw, x0_vehicles)
        axes[0, 1].plot(t0, ey0, linewidth=1.8, label="Bilinear-noadapt")
        axes[0, 1].plot(t1, ey1, linewidth=1.8, label="Bilinear-adapt")
        axes[1, 1].plot(t0, es0, linewidth=1.8)
        axes[1, 1].plot(t1, es1, linewidth=1.8)
        axes[0, 1].set_title("Bilinear Koopman")

        for ax in axes[0, :]:
            ax.set_ylabel("Mean lateral error e_y [m]")
            ax.legend(fontsize=8)
        for ax in axes[1, :]:
            ax.set_ylabel("Mean longitudinal error e_s [m]")
            ax.set_xlabel("Time [s]")

        fig.suptitle("Fig.3 (TF10): Linear/Bilinear adaptive comparison", fontsize=13, fontweight="bold")
        saved_files += _finalize(fig, fig_dir, "fig3_linear_bilinear_adapt_compare", dpi, save_pdf, show)
    else:
        print("[TF10] Fig.3 skipped: required paper_* cases are missing and run_extra_cases_for_fig3=False.")

    # Fig.4: ablation heatmap
    main_full = _case_metric(main_res, "full_path_rate", num_vehicles)
    main_solver = _case_metric(main_res, "solver_success_rate", num_vehicles)
    main_ey = _case_metric(main_res, "rmse_lat_mean", num_vehicles)
    main_es = _case_metric(main_res, "rmse_long_mean", num_vehicles)

    heat_cases = list(compare_results.keys())
    heat_metrics = ["full_path_rate", "solver_success_rate", "rmse_lat_mean", "rmse_long_mean"]
    H = np.zeros((len(heat_cases), len(heat_metrics)), dtype=float)

    for i, cname in enumerate(heat_cases):
        r = compare_results[cname]
        fpr = _case_metric(r, "full_path_rate", num_vehicles)
        ssr = _case_metric(r, "solver_success_rate", num_vehicles)
        rmse_y = _case_metric(r, "rmse_lat_mean", num_vehicles)
        rmse_s = _case_metric(r, "rmse_long_mean", num_vehicles)

        H[i, 0] = (fpr - main_full) * 100.0
        H[i, 1] = (ssr - main_solver) * 100.0
        H[i, 2] = (main_ey - rmse_y) / max(abs(main_ey), 1e-9) * 100.0
        H[i, 3] = (main_es - rmse_s) / max(abs(main_es), 1e-9) * 100.0

    fig = plt.figure(figsize=(9.4, 0.55 * len(heat_cases) + 2.4))
    vmax = max(5.0, float(np.max(np.abs(H))))
    plt.imshow(H, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    plt.xticks(np.arange(4), ["Completion delta (pp)", "Solver delta (pp)", "RMSE_y gain (%)", "RMSE_s gain (%)"])
    plt.yticks(np.arange(len(heat_cases)), heat_cases)
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            plt.text(j, i, f"{H[i, j]:.1f}", ha="center", va="center", fontsize=8)
    plt.title("Fig.4 (TF10): Ablation robustness heatmap")
    plt.colorbar(fraction=0.03, pad=0.02)
    saved_files += _finalize(fig, fig_dir, "fig4_ablation_heatmap", dpi, save_pdf, show)

    # Fig.5: average compute time
    names = list(compare_results.keys())
    step_times = [_case_metric(compare_results[n], "avg_step_time", num_vehicles) for n in names]
    fig = plt.figure(figsize=(10, 4.6))
    plt.bar(np.arange(len(names)), step_times, color="tab:cyan")
    plt.xticks(np.arange(len(names)), names, rotation=18, ha="right")
    plt.ylabel("Average step time [s]")
    plt.title("Fig.5 (TF10): Computation time comparison")
    plt.grid(True, axis="y", alpha=0.3)
    saved_files += _finalize(fig, fig_dir, "fig5_computation_time", dpi, save_pdf, show)

    # Fig.6: robustness comparison
    solver_rates = [_case_metric(compare_results[n], "solver_success_rate", num_vehicles) * 100.0 for n in names]
    full_rates = [_case_metric(compare_results[n], "full_path_rate", num_vehicles) * 100.0 for n in names]
    fig = plt.figure(figsize=(10, 4.8))
    x = np.arange(len(names))
    w = 0.38
    plt.bar(x - w / 2, solver_rates, width=w, label="Solver success rate", color="tab:blue")
    plt.bar(x + w / 2, full_rates, width=w, label="Full-path success rate", color="tab:orange")
    plt.xticks(x, names, rotation=18, ha="right")
    plt.ylim(0, 105)
    plt.ylabel("Rate (%)")
    plt.title("Fig.6 (TF10): Stability and completion robustness")
    plt.grid(True, axis="y", alpha=0.3)
    plt.legend()
    saved_files += _finalize(fig, fig_dir, "fig6_robustness_compare", dpi, save_pdf, show)

    # Fig.7: best vs worst path
    rows = []
    for n in names:
        r = compare_results[n]
        rows.append(
            (
                n,
                _case_metric(r, "full_path_rate", num_vehicles),
                _case_metric(r, "rmse_lat_mean", num_vehicles),
                _case_metric(r, "solver_success_rate", num_vehicles),
            )
        )

    rows_best = sorted(rows, key=lambda x: (x[1], -x[2], x[3]), reverse=True)
    best_name, worst_name = rows_best[0][0], rows_best[-1][0]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    _plot_case_path(
        axes[0],
        compare_results[best_name],
        num_vehicles,
        x_path,
        y_ref_path,
        s_ref_path,
        psi_ref_path,
        frenet_to_global,
        f"Best: {best_name}",
    )
    _plot_case_path(
        axes[1],
        compare_results[worst_name],
        num_vehicles,
        x_path,
        y_ref_path,
        s_ref_path,
        psi_ref_path,
        frenet_to_global,
        f"Worst: {worst_name}",
    )
    axes[1].legend(loc="best", fontsize=8)
    fig.suptitle("Fig.7 (TF10): Best vs worst path tracking", fontsize=13, fontweight="bold")
    saved_files += _finalize(fig, fig_dir, "fig7_best_vs_worst_path", dpi, save_pdf, show)

    # Fig.8a/Fig.8b: split error evolution into two appendix figures
    t_b, ey_b, es_b = _get_errors(compare_results[best_name], dt, num_vehicles, x_ref_raw, x0_vehicles)
    t_w, ey_w, es_w = _get_errors(compare_results[worst_name], dt, num_vehicles, x_ref_raw, x0_vehicles)

    # Appendix Fig.A: lateral error only
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 4.6), sharey=True)
    axes[0].plot(t_b, ey_b, color="tab:green", linewidth=1.8)
    axes[1].plot(t_w, ey_w, color="tab:red", linewidth=1.8)
    axes[0].set_title(f"Best: {best_name}")
    axes[1].set_title(f"Worst: {worst_name}")
    for ax in axes:
        ax.set_xlabel("Time [s]")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("Mean lateral error e_y [m]")
    fig.suptitle("Appendix Fig.A (TF10): Lateral error comparison", fontsize=13, fontweight="bold")
    saved_files += _finalize(fig, fig_dir, "fig8a_lateral_error_compare", dpi, save_pdf, show)

    # Appendix Fig.B: longitudinal error only
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 4.6), sharey=True)
    axes[0].plot(t_b, es_b, color="tab:green", linewidth=1.8)
    axes[1].plot(t_w, es_w, color="tab:red", linewidth=1.8)
    axes[0].set_title(f"Best: {best_name}")
    axes[1].set_title(f"Worst: {worst_name}")
    for ax in axes:
        ax.set_xlabel("Time [s]")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("Mean longitudinal error e_s [m]")
    fig.suptitle("Appendix Fig.B (TF10): Longitudinal error comparison", fontsize=13, fontweight="bold")
    saved_files += _finalize(fig, fig_dir, "fig8b_longitudinal_error_compare", dpi, save_pdf, show)

    summary = {
        "output_dir": os.path.abspath(fig_dir),
        "main_case": main_name,
        "n_cases": len(compare_results),
        "saved_files": sorted(saved_files),
    }

    print("[TF10] Paper-style figures generated in:", summary["output_dir"])
    for fn in summary["saved_files"]:
        print(" -", os.path.basename(fn))

    return summary
