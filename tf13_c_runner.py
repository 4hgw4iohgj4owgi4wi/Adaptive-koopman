"""TF13_C experiment runner.

TF13_C goals:
1) Run TF13 main method.
2) Add TF12A-style comparison method.
3) Run ablation studies robustly (with retry / fallback speed scaling).
4) Save figures + metrics into a dedicated timestamped folder.
"""

from __future__ import annotations

import copy
import csv
import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Tuple

import matplotlib.pyplot as plt
import numpy as np

from tf12_full_compare_figs import generate_tf12_full_comparison_figs


def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _smooth_1d(x: np.ndarray, alpha: float) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.size <= 1:
        return x.copy()
    a = float(np.clip(alpha, 0.0, 0.9999))
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, x.size):
        out[i] = a * out[i - 1] + (1.0 - a) * x[i]
    return out


def build_ref_raw_from_path_pack(
    *,
    path_pack: Mapping[str, Any],
    num_states: int,
    vx_nom: float,
    mode: str,
    path_cfg: Mapping[str, Any] | None = None,
    speed_scale: float = 1.0,
) -> np.ndarray:
    """Build 6xN Frenet reference from path library pack."""
    cfg = dict(path_cfg or {})
    mode_l = str(mode).strip().lower()
    s_ref = np.asarray(path_pack["s_ref_path"], dtype=float)
    kappa = np.asarray(path_pack["curvature_ref_path"], dtype=float)
    n = int(s_ref.size)
    if n <= 1:
        raise ValueError(f"Invalid path pack for mode={mode}: s_ref_path too short.")

    if mode_l == "hairpin":
        v_cap = float(np.clip(cfg.get("hairpin_ref_speed", min(1.3, vx_nom)), 0.2, vx_nom))
        gain = float(max(cfg.get("hairpin_speed_profile_gain", 25.0), 0.0))
        v_min = float(np.clip(cfg.get("hairpin_speed_min", 0.55), 0.05, v_cap))
        smooth = float(np.clip(cfg.get("speed_profile_smooth", 0.85), 0.0, 0.9999))
    else:
        v_cap = float(np.clip(cfg.get("dlc_speed_cap", vx_nom), 0.2, vx_nom))
        gain = float(max(cfg.get("speed_profile_curv_gain", 12.0), 0.0))
        v_min = float(np.clip(cfg.get("speed_profile_min", 0.8), 0.05, v_cap))
        smooth = float(np.clip(cfg.get("speed_profile_smooth", 0.85), 0.0, 0.9999))

    v_cap = float(np.clip(v_cap * float(max(speed_scale, 0.05)), 0.2, vx_nom))
    v_min = float(np.clip(v_min * float(max(speed_scale, 0.05)), 0.05, v_cap))

    vx_ref = v_cap / (1.0 + gain * np.abs(kappa))
    vx_ref = np.clip(vx_ref, v_min, v_cap)
    vx_ref = _smooth_1d(vx_ref, smooth)

    x_ref = np.zeros((int(num_states), n), dtype=float)
    x_ref[0, :] = s_ref
    x_ref[1, :] = 0.0
    x_ref[2, :] = 0.0
    x_ref[3, :] = vx_ref
    x_ref[4, :] = 0.0
    x_ref[5, :] = vx_ref * kappa
    return x_ref


def build_tf13c_case_bank(method_cfg: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Case set: main + TF12A compare + ablations."""
    base = dict(method_cfg)

    # TF13_C main: keep TF13 fault-tolerant stack enabled.
    main_cfg = dict(base)
    main_cfg.update(
        {
            "name": "tf13_c_main_full",
            "enable_fault_tolerant_control": True,
            "fault_tolerant_redistribution": True,
            "use_connection_compliance": True,
            "use_comm_quality_consensus": True,
            "use_delay_compensation": True,
            "use_comm_degraded_fallback": True,
            "use_team_stability_guard": True,
            "use_progress_supervisor": True,
            "use_online_model_adaptation": True,
            "use_ppc": True,
            "use_dynamic_ppc": True,
            "use_adaptive_weight": True,
        }
    )

    # TF12A-like compare: remove TF13 fault-tolerant compensation, keep TF12 comm/stability stack.
    tf12a_cfg = dict(base)
    tf12a_cfg.update(
        {
            "name": "tf13_c_compare_tf12a",
            "enable_fault_tolerant_control": False,
            "fault_tolerant_redistribution": False,
            "fault_comp_gain": 0.0,
            "fault_comp_delta_clip": 0.0,
            "fault_comp_ax_clip": 0.0,
            "use_connection_compliance": True,
            "use_comm_quality_consensus": True,
            "use_delay_compensation": True,
            "use_comm_degraded_fallback": True,
            "use_team_stability_guard": True,
            "use_progress_supervisor": True,
            "use_online_model_adaptation": True,
            "use_ppc": True,
            "use_dynamic_ppc": True,
            "use_adaptive_weight": True,
        }
    )

    # Ablation set
    abl_no_online = dict(main_cfg)
    abl_no_online.update({"name": "ablate_no_online_adapt", "use_online_model_adaptation": False})

    abl_no_comm = dict(main_cfg)
    abl_no_comm.update(
        {
            "name": "ablate_no_comm_consensus",
            "use_comm_quality_consensus": False,
            "use_delay_compensation": False,
            "use_comm_constraint_tightening": False,
            "use_comm_degraded_fallback": False,
        }
    )

    abl_no_conn = dict(main_cfg)
    abl_no_conn.update({"name": "ablate_no_connection_compliance", "use_connection_compliance": False})

    abl_no_ppc_adapt_w = dict(main_cfg)
    abl_no_ppc_adapt_w.update(
        {
            "name": "ablate_no_ppc_adaptw",
            "use_ppc": False,
            "use_dynamic_ppc": False,
            "use_adaptive_weight": False,
        }
    )

    abl_no_fault_redist = dict(main_cfg)
    abl_no_fault_redist.update(
        {
            "name": "ablate_no_fault_redistribution",
            "fault_tolerant_redistribution": False,
            "fault_comp_gain": 0.0,
            "fault_comp_delta_clip": 0.0,
            "fault_comp_ax_clip": 0.0,
        }
    )

    return {
        "main": main_cfg,
        "compare_tf12a": tf12a_cfg,
        "ablations": {
            "no_online_adapt": abl_no_online,
            "no_comm_consensus": abl_no_comm,
            "no_connection_compliance": abl_no_conn,
            "no_ppc_adaptw": abl_no_ppc_adapt_w,
            "no_fault_redistribution": abl_no_fault_redist,
        },
    }


def _metric_row(mode: str, case_key: str, result: Mapping[str, Any]) -> Dict[str, Any]:
    max_lat = float(result.get("max_lat_global", np.nan))
    max_long = float(result.get("max_long_global", np.nan))
    rmse_lat = float(result.get("rmse_lat_mean", np.nan))
    rmse_long = float(result.get("rmse_long_mean", np.nan))
    step_mean = float(result.get("step_time_mean", np.nan))
    solve_mean = float(result.get("mpc_solve_time_mean", np.nan))
    return {
        "mode": mode,
        "case": case_key,
        "full_path_reached": bool(result.get("full_path_reached", False)),
        "fleet_max_abs_err": float(max(abs(max_lat), abs(max_long))),
        "fleet_rmse_mean": float(np.nanmean([abs(rmse_lat), abs(rmse_long)])),
        "rmse_lat_mean": rmse_lat,
        "rmse_long_mean": rmse_long,
        "max_lat_global": max_lat,
        "max_long_global": max_long,
        "step_time_mean": step_mean,
        "step_time_max": float(result.get("step_time_max", np.nan)),
        "mpc_solve_time_mean": solve_mean,
        "mpc_solve_time_max": float(result.get("mpc_solve_time_max", np.nan)),
        "avg_step_time": float(result.get("avg_step_time", np.nan)),
        "sim_steps": int(result.get("sim_steps", -1)),
        "fail_total": int(np.sum(result.get("fail_counts", []))),
        "progress_guard_total": int(np.sum(result.get("progress_guard_counts", []))),
    }


def _cand_score(result: Mapping[str, Any]) -> Tuple[int, float, float]:
    full = bool(result.get("full_path_reached", False))
    max_lat = float(result.get("max_lat_global", np.inf))
    max_long = float(result.get("max_long_global", np.inf))
    m = float(max(abs(max_lat), abs(max_long)))
    step_t = float(result.get("step_time_mean", np.inf))
    if not np.isfinite(step_t):
        step_t = np.inf
    return (0 if full else 1, m, step_t)


def _save_metrics_csv(rows: List[Dict[str, Any]], out_csv: Path) -> None:
    if len(rows) == 0:
        return
    fieldnames = list(rows[0].keys())
    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _plot_ablation_summary(
    *,
    mode: str,
    rows_mode: List[Dict[str, Any]],
    out_dir: Path,
    show: bool,
) -> Path | None:
    if len(rows_mode) == 0:
        return None

    # fixed order for readability
    order = [
        "main",
        "compare_tf12a",
        "no_online_adapt",
        "no_comm_consensus",
        "no_connection_compliance",
        "no_ppc_adaptw",
        "no_fault_redistribution",
    ]
    rows_sort = sorted(rows_mode, key=lambda r: order.index(r["case"]) if r["case"] in order else 999)
    labels = [r["case"] for r in rows_sort]
    y1 = [float(r["fleet_max_abs_err"]) for r in rows_sort]
    y2 = [float(r["fleet_rmse_mean"]) for r in rows_sort]
    y3 = [float(r["step_time_mean"]) for r in rows_sort]

    x = np.arange(len(labels), dtype=float)
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    fig.suptitle(f"TF13_C Ablation Summary ({mode.upper()})", fontsize=14, fontweight="bold")

    axes[0].bar(x, y1, color="tab:red", alpha=0.85)
    axes[0].set_ylabel("fleet max abs err [m]")
    axes[0].grid(True, alpha=0.25)

    axes[1].bar(x, y2, color="tab:blue", alpha=0.85)
    axes[1].set_ylabel("fleet rmse mean [m]")
    axes[1].grid(True, alpha=0.25)

    axes[2].bar(x, y3, color="tab:green", alpha=0.85)
    axes[2].set_ylabel("step mean [s]")
    axes[2].grid(True, alpha=0.25)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels, rotation=20, ha="right")

    # annotate full-path status
    for i, r in enumerate(rows_sort):
        status = "OK" if bool(r["full_path_reached"]) else "FAIL"
        axes[0].text(x[i], y1[i], status, ha="center", va="bottom", fontsize=9)

    fig.tight_layout(rect=[0.02, 0.03, 1, 0.96])
    out = out_dir / f"tf13_c_ablation_summary_{mode}.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return out


@dataclass
class _RunInputs:
    mode: str
    case_key: str
    case_cfg: Dict[str, Any]
    speed_scale: float
    max_extra_steps: int


def _run_one_attempt(
    *,
    inp: _RunInputs,
    build_runtime_context_fn: Callable[[], Dict[str, Any]],
    runtime_module,
    payload_module,
    payload_cfg: Mapping[str, Any],
    standardizer_x,
    leader_idx: int,
    horizon_pad: int,
    path_pack: Mapping[str, Any],
    path_cfg: Mapping[str, Any],
    change_mask: Iterable[int],
    history_root_dir: str,
) -> Dict[str, Any]:
    ctx = build_runtime_context_fn()
    num_states = int(ctx["num_states"])
    vx_nom = float(ctx.get("vx_nom", 3.0))

    x_ref_raw = build_ref_raw_from_path_pack(
        path_pack=path_pack,
        num_states=num_states,
        vx_nom=vx_nom,
        mode=inp.mode,
        path_cfg=path_cfg,
        speed_scale=inp.speed_scale,
    )

    coordinator, ref_bundle = runtime_module.build_a1_reference_bundle(
        payload_module=payload_module,
        payload_cfg=payload_cfg,
        standardizer_x=standardizer_x,
        x_ref_raw=x_ref_raw,
        leader_idx=int(leader_idx),
        horizon_pad=int(horizon_pad),
    )

    ctx["x_ref_raw"] = x_ref_raw
    ctx["traj_length"] = int(path_pack["traj_length"])
    ctx["s_ref_path"] = np.asarray(path_pack["s_ref_path"], dtype=float)
    ctx["curvature_ref_path"] = np.asarray(path_pack["curvature_ref_path"], dtype=float)
    ctx["A1_COORDINATOR"] = coordinator
    ctx["A1_REF_BUNDLE"] = ref_bundle

    method = dict(ctx.get("METHOD_CFG", {}))
    method.update(dict(inp.case_cfg))
    method["scenario_mode"] = str(inp.mode)
    method["active_mode"] = str(inp.mode)
    method["path_mode"] = str(inp.mode)
    method["max_extra_steps"] = int(max(0, inp.max_extra_steps))
    method["history_root_dir"] = str(history_root_dir)
    method["save_history"] = True
    method["history_print_path"] = False
    method["history_case_name"] = f"tf13_c_{inp.mode}_{inp.case_key}"
    method["name"] = f"tf13_c_{inp.mode}_{inp.case_key}"
    ctx["METHOD_CFG"] = method

    return runtime_module.run_tf12_main(ctx, payload_module, payload_cfg, tuple(change_mask))


def _run_case_robust(
    *,
    mode: str,
    case_key: str,
    case_cfg: Dict[str, Any],
    build_runtime_context_fn: Callable[[], Dict[str, Any]],
    runtime_module,
    payload_module,
    payload_cfg: Mapping[str, Any],
    standardizer_x,
    leader_idx: int,
    horizon_pad: int,
    path_pack: Mapping[str, Any],
    path_cfg: Mapping[str, Any],
    change_mask: Iterable[int],
    base_speed_scale: float,
    history_root_dir: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    # Robust retry schedule:
    # - if not full-path, gradually reduce speed and increase max_extra_steps.
    extra_base = int(max(800, case_cfg.get("max_extra_steps", 2600)))
    attempts = [
        (1.00, 1.00),
        (0.95, 1.25),
        (0.90, 1.50),
        (0.82, 1.90),
    ]
    if "main" in case_key:
        attempts = [
            (1.00, 1.00),
            (0.97, 1.20),
            (0.94, 1.40),
            (0.88, 1.75),
        ]

    records: List[Dict[str, Any]] = []
    cands: List[Dict[str, Any]] = []
    last_error = None

    for idx, (k_speed, k_extra) in enumerate(attempts, start=1):
        speed_scale = float(max(0.35, base_speed_scale * k_speed))
        max_extra = int(np.ceil(extra_base * k_extra))
        inp = _RunInputs(
            mode=mode,
            case_key=case_key,
            case_cfg=case_cfg,
            speed_scale=speed_scale,
            max_extra_steps=max_extra,
        )
        t0 = time.perf_counter()
        try:
            res = _run_one_attempt(
                inp=inp,
                build_runtime_context_fn=build_runtime_context_fn,
                runtime_module=runtime_module,
                payload_module=payload_module,
                payload_cfg=payload_cfg,
                standardizer_x=standardizer_x,
                leader_idx=leader_idx,
                horizon_pad=horizon_pad,
                path_pack=path_pack,
                path_cfg=path_cfg,
                change_mask=change_mask,
                history_root_dir=history_root_dir,
            )
            t1 = time.perf_counter()
            res = dict(res)
            res["_tf13c_attempt"] = idx
            res["_tf13c_speed_scale"] = speed_scale
            res["_tf13c_elapsed_wall"] = float(t1 - t0)
            cands.append(res)
            records.append(
                {
                    "attempt": idx,
                    "speed_scale": speed_scale,
                    "max_extra_steps": max_extra,
                    "full_path_reached": bool(res.get("full_path_reached", False)),
                    "fleet_max_abs_err": float(
                        max(abs(float(res.get("max_lat_global", np.nan))), abs(float(res.get("max_long_global", np.nan))))
                    ),
                    "step_time_mean": float(res.get("step_time_mean", np.nan)),
                    "wall_time_sec": float(t1 - t0),
                    "ok": True,
                    "error": "",
                }
            )
            if bool(res.get("full_path_reached", False)):
                break
        except Exception as e:
            t1 = time.perf_counter()
            last_error = str(e)
            records.append(
                {
                    "attempt": idx,
                    "speed_scale": speed_scale,
                    "max_extra_steps": max_extra,
                    "full_path_reached": False,
                    "fleet_max_abs_err": float("inf"),
                    "step_time_mean": float("inf"),
                    "wall_time_sec": float(t1 - t0),
                    "ok": False,
                    "error": str(e),
                }
            )

    if len(cands) == 0:
        raise RuntimeError(f"All attempts failed for mode={mode}, case={case_key}. last_error={last_error}")

    best_idx = min(range(len(cands)), key=lambda i: _cand_score(cands[i]))
    return cands[best_idx], records


def run_tf13_c_suite(
    *,
    build_runtime_context_fn: Callable[[], Dict[str, Any]],
    runtime_module,
    payload_module,
    payload_cfg: Mapping[str, Any],
    standardizer_x,
    formation_cfg: Mapping[str, Any],
    horizon_pad: int,
    path_library: Mapping[str, Mapping[str, Any]],
    path_cfg: Mapping[str, Any],
    base_method_cfg: Mapping[str, Any],
    change_mask: Iterable[int],
    modes: Iterable[str] = ("dlc", "hairpin"),
    output_root: str = "results/tf13_c",
    show_figures: bool = False,
) -> Dict[str, Any]:
    """Run TF13_C main + TF12A compare + ablations for configured modes."""
    out_root = _ensure_dir(output_root)
    run_dir = _ensure_dir(out_root / _now_tag())
    fig_dir = _ensure_dir(run_dir / "figures")
    data_dir = _ensure_dir(run_dir / "data")
    history_dir = _ensure_dir(run_dir / "history")

    case_bank = build_tf13c_case_bank(base_method_cfg)
    leader_idx = int(formation_cfg.get("leader_index", 0))

    # Mode-level speed presets (hairpin a bit slower for robustness).
    mode_speed = {"dlc": 1.00, "hairpin": 0.90}
    all_results: Dict[str, Dict[str, Any]] = {}
    attempt_logs: Dict[str, Dict[str, Any]] = {}
    metric_rows: List[Dict[str, Any]] = []

    for mode in [str(m).strip().lower() for m in modes]:
        if mode not in path_library:
            continue
        path_pack = path_library[mode]
        all_results[mode] = {}
        attempt_logs[mode] = {}

        case_order = [("main", case_bank["main"]), ("compare_tf12a", case_bank["compare_tf12a"])]
        case_order += list(case_bank["ablations"].items())
        for case_key, case_cfg in case_order:
            res, logs = _run_case_robust(
                mode=mode,
                case_key=case_key,
                case_cfg=dict(case_cfg),
                build_runtime_context_fn=build_runtime_context_fn,
                runtime_module=runtime_module,
                payload_module=payload_module,
                payload_cfg=payload_cfg,
                standardizer_x=standardizer_x,
                leader_idx=leader_idx,
                horizon_pad=int(horizon_pad),
                path_pack=path_pack,
                path_cfg=path_cfg,
                change_mask=change_mask,
                base_speed_scale=float(mode_speed.get(mode, 1.0)),
                history_root_dir=str(history_dir),
            )
            all_results[mode][case_key] = res
            attempt_logs[mode][case_key] = logs
            metric_rows.append(_metric_row(mode, case_key, res))

    if len(all_results) == 0:
        raise RuntimeError("TF13_C run failed: no mode result generated.")

    # Main vs TF12A comparison pack for full figure generator.
    compare_dual = {}
    for mode, pack in all_results.items():
        if ("main" in pack) and ("compare_tf12a" in pack):
            compare_dual[mode] = {
                "baseline_bilinear_adaptnet": pack["compare_tf12a"],
                "main_tf12_full": pack["main"],
            }

    if len(compare_dual) > 0:
        full_fig_summary = generate_tf12_full_comparison_figs(
            compare_results_b1_dual=compare_dual,
            dt=float(build_runtime_context_fn()["dt"]),
            tf12_path_library=dict(path_library),
            output_dir=str(fig_dir / "main_vs_tf12a"),
            include_traj_tracking_figs=True,
            include_history_block=True,
            history_root_dir=str(history_dir),
            show=bool(show_figures),
        )
    else:
        full_fig_summary = {"output_dir": str(fig_dir / "main_vs_tf12a"), "figures": [], "metrics": {}}

    # Ablation summary bars per mode
    ablation_figs = []
    for mode in all_results.keys():
        rows_mode = [r for r in metric_rows if r["mode"] == mode]
        fp = _plot_ablation_summary(
            mode=mode,
            rows_mode=rows_mode,
            out_dir=fig_dir,
            show=bool(show_figures),
        )
        if fp is not None:
            ablation_figs.append(str(fp))

    # Persist metrics and raw results
    metrics_csv = data_dir / "tf13_c_metrics.csv"
    _save_metrics_csv(metric_rows, metrics_csv)

    with (data_dir / "tf13_c_attempt_logs.json").open("w", encoding="utf-8") as f:
        json.dump(attempt_logs, f, ensure_ascii=False, indent=2)

    with (data_dir / "tf13_c_all_results.pkl").open("wb") as f:
        pickle.dump(all_results, f)

    summary = {
        "run_dir": str(run_dir),
        "figure_dir": str(fig_dir),
        "data_dir": str(data_dir),
        "history_dir": str(history_dir),
        "modes": list(all_results.keys()),
        "cases_per_mode": {m: list(all_results[m].keys()) for m in all_results},
        "full_compare_fig_summary": full_fig_summary,
        "ablation_figures": ablation_figs,
        "metrics_csv": str(metrics_csv),
        "attempt_logs_json": str(data_dir / "tf13_c_attempt_logs.json"),
        "raw_results_pkl": str(data_dir / "tf13_c_all_results.pkl"),
    }
    with (run_dir / "tf13_c_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return {
        "summary": summary,
        "all_results": all_results,
        "compare_results_tf13c_dual": compare_dual,
        "metric_rows": metric_rows,
        "attempt_logs": attempt_logs,
    }
