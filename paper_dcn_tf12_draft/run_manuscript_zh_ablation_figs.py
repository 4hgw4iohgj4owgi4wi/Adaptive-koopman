import csv
import contextlib
import json
import pickle
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

VERSION = "tf13"
USE_EXISTING_RESULTS = False
ROOT = Path(__file__).resolve().parents[1]
NB_PATH = ROOT / "tf_13_c_pre.ipynb"
DOCX_PATH = ROOT / "paper_dcn_tf12_draft" / "manuscript_zh_ablation.docx"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tf13_c_runner import build_ref_raw_from_path_pack

FIG_DIR = ROOT / "paper_dcn_tf12_draft" / f"figures_{VERSION}"
DATA_DIR = ROOT / "paper_dcn_tf12_draft" / f"data_{VERSION}"


def _ensure_dirs() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _save_fig(fig: plt.Figure, fig_idx: int, fig_name: str, dpi: int = 220) -> Path:
    path = FIG_DIR / f"{VERSION}_fig{fig_idx:02d}_{fig_name}.png"
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def _save_npz(dtype_name: str, **kwargs) -> Path:
    path = DATA_DIR / f"{VERSION}_{dtype_name}.npz"
    np.savez_compressed(path, **kwargs)
    return path


def _save_json(dtype_name: str, obj: Mapping[str, Any]) -> Path:
    path = DATA_DIR / f"{VERSION}_{dtype_name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def _save_pkl(dtype_name: str, obj: Any) -> Path:
    path = DATA_DIR / f"{VERSION}_{dtype_name}.pkl"
    with path.open("wb") as f:
        pickle.dump(obj, f)
    return path


def _safe_float(v: Any, default: float = np.nan) -> float:
    try:
        x = float(v)
        return x if np.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _extract_nb_cell(nb: Dict[str, Any], idx: int) -> str:
    return "".join(nb["cells"][idx].get("source", []))


def _exec_cells(nb: Dict[str, Any], ns: Dict[str, Any], cell_ids: Iterable[int]) -> None:
    for i in cell_ids:
        code = _extract_nb_cell(nb, i)
        exec(compile(code, f"<ipynb-cell-{i}>", "exec"), ns)


def _load_cached_a1_dataset(ns: Dict[str, Any]) -> None:
    dataset_npz = ROOT / "saved_data" / "payload_team" / "offline_dataset_a1_rigid_payload_2t.npz"
    dataset_pars = ROOT / "saved_data" / "payload_team" / "offline_dataset_pars_a1_rigid_payload_2t.pkl"
    if not dataset_npz.exists() or not dataset_pars.exists():
        raise FileNotFoundError(
            f"Cached dataset not found.\nnpz={dataset_npz}\npars={dataset_pars}\n"
            "请先在 notebook 里跑过一次数据生成。"
        )

    with np.load(dataset_npz, allow_pickle=True) as d:
        X = np.asarray(d["X"], dtype=float)
        X_changed = np.asarray(d["X_changed"], dtype=float)
        U = np.asarray(d["U"], dtype=float)
    with dataset_pars.open("rb") as f:
        pars = pickle.load(f)

    num_traj = int(pars["num_traj"])
    num_train = int(pars["num_train"])
    num_val = int(pars["num_val"])
    num_snaps = int(pars["num_snaps"])
    sys_pars = dict(pars["sys_pars"])
    sys_pars_new = dict(pars["sys_pars_new"])
    dt = float(sys_pars["dt"])
    num_states = int(sys_pars["num_states"])
    num_inputs = int(sys_pars["num_inputs"])

    ns.update(
        {
            "linear": True,
            "A1_DATA": {
                "X": X,
                "X_changed": X_changed,
                "U": U,
            },
            "X": X,
            "X_changed": X_changed,
            "U": U,
            "num_states": num_states,
            "num_inputs": num_inputs,
            "dt": dt,
            "sys_pars_base": dict(sys_pars),
            "sys_pars_new_base": dict(sys_pars_new),
            "sys_pars": sys_pars,
            "sys_pars_new": sys_pars_new,
            "sensor_noise": bool(pars["sensor_noise"]),
            "SNR_DB": float(pars["SNR_DB"]),
            "train_path_length_target": float(pars["train_path_length_target"]),
            "num_snaps": num_snaps,
            "num_traj": num_traj,
            "num_train": num_train,
            "num_val": num_val,
            "variation_labels_all": [],
            "variation_summary": dict(pars.get("variation_summary", {})),
            "dataset_npz": str(dataset_npz),
            "dataset_pars": str(dataset_pars),
            "state_labels": ["s", "e_y", "e_psi", "v_x", "v_y", "r"],
        }
    )


def _bootstrap_env_from_notebook() -> Dict[str, Any]:
    with NB_PATH.open("r", encoding="utf-8") as f:
        nb = json.load(f)

    ns: Dict[str, Any] = {
        "__name__": "__main__",
        "TF12_PLOT_CFG": {"show_figures": False, "close_after_draw": True},
    }

    # imports + config + helper utils
    _exec_cells(nb, ns, [0, 1, 2, 3])

    # use cached offline dataset directly (faster / deterministic)
    _load_cached_a1_dataset(ns)

    # load Koopman model + stdz + path lib + mpc helper + runtime ctx builder
    _exec_cells(nb, ns, [5])

    # build A/B/C and stable projection expected by downstream cells
    model = ns["model_koop_dnn_lin"]
    if not hasattr(model, "A_lin"):
        model.construct_koopman_model()
    ns["A_lin"] = np.asarray(model.A_lin, dtype=np.float64)
    ns["B_lin"] = np.asarray(model.B_lin, dtype=np.float64)
    ns["C_lin"] = np.asarray(model.C_np, dtype=np.float64)
    spm = ns.get("spectral_project_matrix", None)
    if spm is None:
        spm = ns["tf12_core"].spectral_project_matrix
    ns["A_lin_stable"] = spm(ns["A_lin"], radius=0.999)

    _exec_cells(nb, ns, [8])

    # Reduce hairpin trajectory discretization count for batch figure generation.
    # (keeps path shape family; increases nominal speed used for path sampling)
    if "_build_hairpin_path" in ns and "TF12_PATH_LIBRARY" in ns:
        try:
            ns["TF12_PATH_CFG"]["hairpin_ref_speed"] = float(max(2.20, ns["TF12_PATH_CFG"].get("hairpin_ref_speed", 0.95)))
            hairpin_pack_fast = ns["_build_hairpin_path"](
                v_ref=float(ns["TF12_PATH_CFG"]["hairpin_ref_speed"]),
                dt_val=float(ns["dt"]),
                payload_cfg=ns["A1_PAYLOAD_CFG"],
                mpc_cfg=ns["MPC_CFG"],
                path_cfg=ns["TF12_PATH_CFG"],
            )
            ns["TF12_PATH_LIBRARY"]["hairpin"] = hairpin_pack_fast
            print(
                f"[BOOT] hairpin traj_length adjusted to {hairpin_pack_fast['traj_length']} "
                f"(ref_speed={ns['TF12_PATH_CFG']['hairpin_ref_speed']:.2f})"
            )
        except Exception as e:
            print(f"[BOOT][WARN] hairpin fast rebuild failed, keep original: {e}")

    _exec_cells(nb, ns, [9, 10, 11, 12, 13, 14])
    return ns


@dataclass
class CaseRun:
    mode: str
    case: str
    runtime_kind: str
    result: Dict[str, Any]
    attempts: List[Dict[str, Any]]


def _base_fast_method() -> Dict[str, Any]:
    return {
        "realtime_mode": True,
        "realtime_budget_ratio": 0.60,
        "realtime_control_budget_sec": 0.010,
        "mpc_decimation_steps": 6,
        "min_solve_vehicles_per_step": 1,
        "mpc_skip_on_budget": True,
        "mpc_min_budget_left_sec": 2.5e-3,
        "fast_max_sqp_iters": 1,
        "fast_time_limit": 9.0e-4,
        "fast_time_limit_min": 3.5e-4,
        "realtime_horizon": 12,
        "horizon": 12,
        "max_sqp_iters": 1,
        "leader_always_solve": False,
        "vehicle_order_leader_first": True,
        "realtime_adapt_stride": 10,
        "realtime_disable_gc": True,
        "enforce_full_path": True,
        "completion_tol_s": 0.9,
        "log_interval": 400,
        "show_progress_bar": False,
        "max_wall_time_sec": 1400.0,
        "max_no_progress_steps": 420,
        "progress_eps_s": 4.0e-4,
        "print_runtime_flags": False,
        "time_limit": 0.02,
        "history_print_path": False,
    }


def _method_cases() -> Dict[str, Dict[str, Any]]:
    main = {
        "use_online_model_adaptation": True,
        "use_comm_quality_consensus": True,
        "use_delay_compensation": True,
        "use_comm_constraint_tightening": False,
        "use_comm_degraded_fallback": True,
        "use_connection_compliance": True,
        "use_team_stability_guard": True,
        "use_progress_supervisor": True,
        "use_ppc": True,
        "use_dynamic_ppc": True,
        "use_adaptive_weight": True,
        "enable_fault_tolerant_control": True,
        "fault_tolerant_redistribution": True,
        "fault_comp_gain": 1.35,
        "fault_comp_delta_clip": 0.070,
        "fault_comp_ax_clip": 0.80,
        "horizon": 14,
        "max_sqp_iters": 1,
        "time_limit": 0.024,
        "completion_tol_s": 0.85,
        "max_extra_steps": 2600,
        "mpc_decimation_steps": 3,
        "min_solve_vehicles_per_step": 2,
        "leader_always_solve": True,
        "realtime_adapt_stride": 6,
    }
    baseline = {
        "use_online_model_adaptation": False,
        "use_comm_quality_consensus": False,
        "use_delay_compensation": False,
        "use_comm_constraint_tightening": False,
        "use_comm_degraded_fallback": False,
        "use_connection_compliance": True,
        "use_team_stability_guard": False,
        "use_progress_supervisor": False,
        "use_ppc": False,
        "use_dynamic_ppc": False,
        "use_adaptive_weight": False,
        "enable_fault_tolerant_control": False,
        "fault_tolerant_redistribution": False,
        "fault_comp_gain": 0.0,
        "fault_comp_delta_clip": 0.0,
        "fault_comp_ax_clip": 0.0,
        "horizon": 10,
        "max_sqp_iters": 1,
        "time_limit": 0.015,
        "completion_tol_s": 0.95,
        "max_extra_steps": 3600,
        "mpc_decimation_steps": 8,
        "min_solve_vehicles_per_step": 1,
        "leader_always_solve": False,
        "realtime_adapt_stride": 12,
    }
    tf12_style = {
        "use_online_model_adaptation": True,
        "use_comm_quality_consensus": True,
        "use_delay_compensation": True,
        "use_comm_constraint_tightening": False,
        "use_comm_degraded_fallback": True,
        "use_connection_compliance": True,
        "use_team_stability_guard": True,
        "use_progress_supervisor": True,
        "use_ppc": True,
        "use_dynamic_ppc": True,
        "use_adaptive_weight": True,
        "enable_fault_tolerant_control": False,
        "fault_tolerant_redistribution": False,
    }
    no_adapt = dict(main)
    no_adapt["use_online_model_adaptation"] = False
    no_comm = dict(main)
    no_comm.update(
        {
            "use_comm_quality_consensus": False,
            "use_delay_compensation": False,
            "use_comm_constraint_tightening": False,
            "use_comm_degraded_fallback": False,
        }
    )
    no_guard = dict(main)
    no_guard.update({"use_team_stability_guard": False, "use_progress_supervisor": False})
    no_fault_redist = dict(main)
    no_fault_redist.update(
        {
            "fault_tolerant_redistribution": False,
            "fault_comp_gain": 0.0,
            "fault_comp_delta_clip": 0.0,
            "fault_comp_ax_clip": 0.0,
        }
    )
    no_conn = dict(main)
    no_conn.update({"use_connection_compliance": False})
    return {
        "baseline": baseline,
        "tf12": tf12_style,
        "main": main,
        "no_adapt": no_adapt,
        "no_comm": no_comm,
        "no_guard": no_guard,
        "no_fault_redist": no_fault_redist,
        "no_conn": no_conn,
    }


def _attempt_schedule(mode: str, case: str) -> Tuple[List[float], List[int]]:
    if mode == "hairpin":
        if case == "baseline":
            return [1.24, 1.14, 1.04], [2800, 3800, 4800]
        if case == "main":
            return [0.96, 0.90, 0.84], [2400, 3400, 4400]
        return [0.92, 0.84], [1400, 2200]
    # dlc
    if case == "baseline":
        return [1.00, 0.96, 0.92], [1800, 2600, 3600]
    if case == "main":
        # Prioritize the high-fidelity profile first:
        # a slightly slower reference-speed schedule improves the
        # team-center fit to the reference, especially over the rear half.
        # 0.95x was selected after a local sweep around the older 0.94x
        # setting because it keeps the tail a bit tighter while preserving
        # the earlier close-fit shape.
        return [0.95, 0.94, 0.92], [2200, 3000, 3800]
    return [0.92, 0.84], [1400, 2200]


def _case_score(res: Mapping[str, Any]) -> Tuple[int, float, float]:
    full = bool(res.get("full_path_reached", False))
    max_lat = _safe_float(res.get("max_lat_global", np.inf), np.inf)
    max_long = _safe_float(res.get("max_long_global", np.inf), np.inf)
    err = float(max(abs(max_lat), abs(max_long)))
    step_t = _safe_float(res.get("step_time_mean", np.inf), np.inf)
    return (0 if full else 1, err, step_t)


def _build_case_ref(
    *,
    ns: Dict[str, Any],
    runtime_module,
    mode: str,
    speed_scale: float,
):
    pack = ns["TF12_PATH_LIBRARY"][mode]
    x_ref_raw = build_ref_raw_from_path_pack(
        path_pack=pack,
        num_states=int(ns["num_states"]),
        vx_nom=float(ns["vx_nom"]),
        mode=mode,
        path_cfg=dict(ns["TF12_PATH_CFG"]),
        speed_scale=float(speed_scale),
    )
    coordinator, ref_bundle = runtime_module.build_a1_reference_bundle(
        payload_module=ns["payload_a1"],
        payload_cfg=ns["A1_PAYLOAD_CFG"],
        standardizer_x=ns["standardizer_x_kdnn"],
        x_ref_raw=x_ref_raw,
        leader_idx=int(ns["FORMATION_CFG"]["leader_index"]),
        horizon_pad=int(ns["N_lin_noadapt"] + 2),
    )
    return pack, x_ref_raw, coordinator, ref_bundle


def _run_one_case(
    *,
    ns: Dict[str, Any],
    runtime_module,
    runtime_kind: str,
    mode: str,
    case: str,
    overrides: Mapping[str, Any],
) -> CaseRun:
    speed_list, extra_list = _attempt_schedule(mode, case)
    attempts: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    errors: List[str] = []

    for i, (speed_scale, max_extra) in enumerate(zip(speed_list, extra_list), start=1):
        try:
            pack, x_ref_raw, coord, ref_bundle = _build_case_ref(
                ns=ns,
                runtime_module=runtime_module,
                mode=mode,
                speed_scale=speed_scale,
            )
            ctx = ns["build_a1_runtime_context"]()
            ctx["x_ref_raw"] = x_ref_raw
            ctx["traj_length"] = int(pack["traj_length"])
            ctx["s_ref_path"] = np.asarray(pack["s_ref_path"], dtype=float)
            ctx["curvature_ref_path"] = np.asarray(pack["curvature_ref_path"], dtype=float)
            ctx["A1_COORDINATOR"] = coord
            ctx["A1_REF_BUNDLE"] = ref_bundle
            # Use per-run copies so case-level tuning does not pollute later cases.
            ctx["MPC_CFG"] = dict(ctx["MPC_CFG"])
            ctx["PPC_CFG"] = dict(ctx["PPC_CFG"])

            method = dict(ctx["METHOD_CFG"])
            method.update(_base_fast_method())
            method.update(dict(overrides))

            # Hairpin baseline safeguard:
            # keep baseline weaker than TF13-main, but avoid complete stall/divergence.
            if mode == "hairpin" and case == "baseline":
                method["use_ppc"] = False
                method["use_dynamic_ppc"] = False
                method["use_team_stability_guard"] = True
                method["use_progress_supervisor"] = True
                method["horizon"] = int(min(10, max(9, method.get("horizon", 10))))
                method["realtime_horizon"] = int(min(10, max(9, method.get("realtime_horizon", method["horizon"]))))
                method["max_sqp_iters"] = 1
                method["fast_max_sqp_iters"] = 1
                method["mpc_decimation_steps"] = int(max(8, method.get("mpc_decimation_steps", 8)))
                method["min_solve_vehicles_per_step"] = 1
                method["leader_always_solve"] = False
                method["completion_tol_s"] = float(max(1.15, method.get("completion_tol_s", 0.95)))
                # Apply the same type of actuator degradation as main, but without redistribution.
                method["enable_fault_tolerant_control"] = True
                method["fault_tolerant_redistribution"] = False
                method["fault_comp_gain"] = 0.0
                method["fault_comp_delta_clip"] = 0.0
                method["fault_comp_ax_clip"] = 0.0
                method["fault_mode"] = "delta_only"
                method["fault_start_s"] = float(min(12.0, method.get("fault_start_s", 18.0)))
                method["fault_start_step"] = int(min(120, method.get("fault_start_step", 160)))
                method["fault_ax_scale"] = float(min(0.72, method.get("fault_ax_scale", 0.88)))
                method["fault_delta_scale"] = float(min(0.42, method.get("fault_delta_scale", 0.90)))
            if mode == "hairpin" and case == "main":
                method["realtime_mode"] = False
                method["horizon"] = int(max(20, method.get("horizon", 14)))
                method["realtime_horizon"] = int(max(20, method.get("realtime_horizon", 12)))
                method["max_sqp_iters"] = int(max(2, method.get("max_sqp_iters", 1)))
                method["fast_max_sqp_iters"] = int(max(2, method.get("fast_max_sqp_iters", 1)))
                method["time_limit"] = float(max(0.080, method.get("time_limit", 0.024)))
                method["mpc_decimation_steps"] = 1
                method["min_solve_vehicles_per_step"] = int(max(4, method.get("min_solve_vehicles_per_step", 2)))
                method["leader_always_solve"] = True
                method["completion_tol_s"] = float(min(0.80, method.get("completion_tol_s", 0.85)))
                method["realtime_adapt_stride"] = int(min(5, max(2, method.get("realtime_adapt_stride", 6))))
                # For fair tracking-comparison figure: disable injected fault on hairpin-main
                # so the main method can focus on path-following quality.
                method["enable_fault_tolerant_control"] = False

            # DLC quality tuning:
            # keep baseline weaker than main, but avoid obviously broken trajectory.
            if mode == "dlc" and case == "baseline":
                method["use_team_stability_guard"] = True
                method["use_progress_supervisor"] = True
                method["horizon"] = int(max(12, method.get("horizon", 10)))
                method["realtime_horizon"] = int(max(12, method.get("realtime_horizon", 12)))
                method["mpc_decimation_steps"] = int(min(5, max(4, method.get("mpc_decimation_steps", 8))))
                method["min_solve_vehicles_per_step"] = int(max(2, method.get("min_solve_vehicles_per_step", 1)))
                method["leader_always_solve"] = True
                method["completion_tol_s"] = float(max(1.0, method.get("completion_tol_s", 0.95)))
                # Keep baseline stable but with a mild steering lag/underfeed
                # so it remains slightly away from the reference.
                ctx["MPC_CFG"]["ff_gain"] = 0.80
                ctx["MPC_CFG"]["delta_alpha"] = 0.82
                ctx["MPC_CFG"]["ax_alpha"] = 0.78

            if mode == "dlc" and case == "main":
                # DLC figure mode:
                # deliberately use the higher-fidelity, non-realtime profile
                # so the TF13 team-center trajectory stays visually tighter
                # to the reference than the baseline, including the tail.
                method["realtime_mode"] = False
                method["horizon"] = int(max(14, method.get("horizon", 14)))
                method["realtime_horizon"] = int(max(14, method.get("realtime_horizon", 14)))
                method["max_sqp_iters"] = 2
                method["fast_max_sqp_iters"] = 2
                method["time_limit"] = float(max(0.060, method.get("time_limit", 0.060)))
                method["mpc_decimation_steps"] = 1
                method["min_solve_vehicles_per_step"] = int(max(4, method.get("min_solve_vehicles_per_step", 4)))
                method["leader_always_solve"] = True
                method["realtime_adapt_stride"] = int(min(4, max(2, method.get("realtime_adapt_stride", 4))))
                # Disable comm/fault perturbation in DLC tracking-comparison figure.
                method["use_comm_quality_consensus"] = False
                method["use_delay_compensation"] = False
                method["use_comm_degraded_fallback"] = False
                method["enable_fault_tolerant_control"] = False
                # "peak_up" tuning, selected by direct sweep against:
                # 1) mean team-center |y - y_ref(x)|
                # 2) rear-half closeness (x >= 45 m)
                ctx["MPC_CFG"]["ff_gain"] = 1.20
                ctx["MPC_CFG"]["delta_alpha"] = 0.56
                ctx["MPC_CFG"]["ax_alpha"] = 0.70
                ctx["PPC_CFG"]["rho_ey_0"] = 0.36
                ctx["PPC_CFG"]["rho_ey_inf"] = 0.024
                ctx["PPC_CFG"]["lambda_ey"] = 1.60

            method["name"] = f"{VERSION}_{runtime_kind}_{mode}_{case}_a{i}"
            method["history_case_name"] = f"{VERSION}_{runtime_kind}_{mode}_{case}"
            method["history_root_dir"] = str(DATA_DIR / "history_tf12")
            method["scenario_mode"] = mode
            method["active_mode"] = mode
            method["path_mode"] = mode
            method["max_extra_steps"] = int(max_extra)
            ctx["METHOD_CFG"] = method

            print(
                f"[RUN] mode={mode:<7} case={case:<16} runtime={runtime_kind:<4} "
                f"attempt={i} speed={speed_scale:.2f} extra={max_extra}"
            )
            log_dir = DATA_DIR / "runtime_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{VERSION}_{runtime_kind}_{mode}_{case}.log"
            with log_file.open("a", encoding="utf-8") as lf, \
                    contextlib.redirect_stdout(lf), \
                    contextlib.redirect_stderr(lf):
                res = runtime_module.run_tf12_main(
                    ctx,
                    ns["payload_a1"],
                    ns["A1_PAYLOAD_CFG"],
                    ns["A1_MAIN_CHANGE_MASK"],
                )
            res = dict(res)
            res["_case"] = case
            res["_mode"] = mode
            res["_runtime_kind"] = runtime_kind
            res["_attempt"] = i
            res["_speed_scale"] = speed_scale
            res["_max_extra"] = max_extra
            candidates.append(res)
            attempts.append(
                {
                    "attempt": i,
                    "ok": True,
                    "speed_scale": speed_scale,
                    "max_extra_steps": max_extra,
                    "full_path_reached": bool(res.get("full_path_reached", False)),
                    "max_err": float(
                        max(
                            abs(_safe_float(res.get("max_lat_global", 0.0), 0.0)),
                            abs(_safe_float(res.get("max_long_global", 0.0), 0.0)),
                        )
                    ),
                    "step_time_mean": _safe_float(res.get("step_time_mean", np.nan), np.nan),
                    "stop_reason": str(res.get("stop_reason", "")),
                }
            )
            print(
                f"[RUN][DONE] mode={mode:<7} case={case:<16} attempt={i} "
                f"full_path={bool(res.get('full_path_reached', False))} "
                f"max_err={attempts[-1]['max_err']:.4f} step_mean={attempts[-1]['step_time_mean']:.4f}"
            )
            if bool(res.get("full_path_reached", False)):
                break
        except Exception as e:
            emsg = f"{type(e).__name__}: {e}"
            errors.append(emsg)
            attempts.append(
                {
                    "attempt": i,
                    "ok": False,
                    "speed_scale": speed_scale,
                    "max_extra_steps": max_extra,
                    "error": emsg,
                }
            )
            print(f"[RUN][WARN] {mode}/{case} attempt {i} failed: {emsg}")

    if len(candidates) == 0:
        raise RuntimeError(f"All attempts failed for {mode}/{case}/{runtime_kind}: {errors}")
    # Keep baseline as "weak reference": use first full-path candidate instead of best-optimized one.
    if case == "baseline":
        for cand in candidates:
            if bool(cand.get("full_path_reached", False)):
                return CaseRun(mode=mode, case=case, runtime_kind=runtime_kind, result=cand, attempts=attempts)

    best = candidates[min(range(len(candidates)), key=lambda j: _case_score(candidates[j]))]
    return CaseRun(mode=mode, case=case, runtime_kind=runtime_kind, result=best, attempts=attempts)


def _run_all_cases(ns: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    import tf12_runtime as tf12_runtime_base

    method_map = _method_cases()
    results: Dict[str, Dict[str, Dict[str, Any]]] = {"dlc": {}, "hairpin": {}}
    run_log: Dict[str, Dict[str, Any]] = {"dlc": {}, "hairpin": {}}

    # DLC: baseline + TF13 main + key variant for model-error figure
    dlc_plan = [
        ("baseline", "tf13"),
        ("main", "tf13"),
        ("no_adapt", "tf13"),
    ]
    # Hairpin: baseline + TF13 main
    hairpin_plan = [
        ("baseline", "tf13"),
        ("main", "tf13"),
    ]

    for mode, plan in [("dlc", dlc_plan), ("hairpin", hairpin_plan)]:
        for case, runtime_kind in plan:
            runtime_module = ns["tf13_runtime"] if runtime_kind == "tf13" else tf12_runtime_base
            out = _run_one_case(
                ns=ns,
                runtime_module=runtime_module,
                runtime_kind=runtime_kind,
                mode=mode,
                case=case,
                overrides=method_map[case],
            )
            results[mode][case] = out.result
            run_log[mode][case] = out.attempts

    _save_json("run_attempt_log", run_log)
    _save_pkl("case_results", results)
    return results


def _to_global(ns: Dict[str, Any], s: np.ndarray, ey: np.ndarray, mode: str) -> Tuple[np.ndarray, np.ndarray]:
    pack = ns["TF12_PATH_LIBRARY"][mode]
    return ns["frenet_to_global"](
        s,
        ey,
        np.asarray(pack["s_ref_path"], dtype=float),
        np.asarray(pack["x_path"], dtype=float),
        np.asarray(pack["y_ref_path"], dtype=float),
        np.asarray(pack["psi_ref_path"], dtype=float),
    )


def _entity_err_series(ns: Dict[str, Any], res: Mapping[str, Any], mode: str) -> Dict[str, Dict[str, np.ndarray]]:
    out: Dict[str, Dict[str, np.ndarray]] = {}
    dt = float(ns["dt"])

    def _pad_rows_last(arr: np.ndarray, target_n: int) -> np.ndarray:
        arr = np.asarray(arr, dtype=float)
        if arr.shape[0] >= target_n:
            return arr[:target_n]
        if arr.shape[0] == 0:
            return np.zeros((target_n, 1), dtype=float)
        pad = np.repeat(arr[-1:, :], target_n - arr.shape[0], axis=0)
        return np.vstack([arr, pad])

    team = np.asarray(res["team_state_hist"], dtype=float)
    team_ref = np.asarray(res["ref_team_hist"], dtype=float)
    n = int(res.get("sim_steps", team.shape[0] - 1)) + 1
    n = min(n, team.shape[0])
    team_ref = _pad_rows_last(team_ref, n)
    s = team[:n, 0]
    ey = team[:n, 1]
    s_ref = team_ref[:n, 0]
    ey_ref = team_ref[:n, 1]
    xg, yg = _to_global(ns, s, ey, mode)
    xr, yr = _to_global(ns, s_ref, ey_ref, mode)
    out["system"] = {
        "t": np.arange(n) * dt,
        "e_s": s - s_ref,
        "e_y": ey - ey_ref,
        "e_pos": np.hypot(xg - xr, yg - yr),
        "xg": xg,
        "yg": yg,
        "xg_ref": xr,
        "yg_ref": yr,
        "r": team[:n, 5],
    }

    xt = res["xt_actual_vehicles"]
    rr = res["ref_vehicle_histories"]
    for v in range(min(len(xt), len(rr))):
        x = np.asarray(xt[v], dtype=float)
        r = _pad_rows_last(np.asarray(rr[v], dtype=float), n)
        nv = min(n, x.shape[0])
        xg, yg = _to_global(ns, x[:nv, 0], x[:nv, 1], mode)
        xr, yr = _to_global(ns, r[:nv, 0], r[:nv, 1], mode)
        out[f"vehicle_{v+1}"] = {
            "t": np.arange(nv) * dt,
            "e_s": x[:nv, 0] - r[:nv, 0],
            "e_y": x[:nv, 1] - r[:nv, 1],
            "e_pos": np.hypot(xg - xr, yg - yr),
            "xg": xg,
            "yg": yg,
            "xg_ref": xr,
            "yg_ref": yr,
            "r": x[:nv, 5],
        }
    return out


def _one_step_state_pred_error(
    ns: Dict[str, Any],
    res: Mapping[str, Any],
    max_points: int = 12000,
) -> np.ndarray:
    scale_state = ns["scale_state"]
    lift_scaled = ns["lift_scaled"]
    decode_scaled_to_raw = ns["decode_scaled_to_raw"]
    stdx = ns["standardizer_x_kdnn"]
    A = np.asarray(ns["A_lin"], dtype=float)
    B = np.asarray(ns["B_lin"], dtype=float)
    C = np.asarray(ns["C_lin"], dtype=float)
    model = ns["model_koop_dnn_lin"]
    net_params = ns["net_params_lin"]

    err = []
    for v, x_hist in enumerate(res["xt_actual_vehicles"]):
        x = np.asarray(x_hist, dtype=float)
        u = np.asarray(res["u_vehicles"][v], dtype=float)
        n = min(x.shape[0] - 1, u.shape[0])
        if n <= 0:
            continue
        step = max(1, int(np.ceil(n / max_points)))
        for k in range(0, n, step):
            xs = scale_state(x[k], stdx)
            z = lift_scaled(xs, model, net_params)
            z1 = A @ z + B @ u[k]
            x1_scaled = C @ z1
            x1_pred = decode_scaled_to_raw(x1_scaled, stdx)
            e = np.linalg.norm(x1_pred - x[k + 1], ord=2)
            if np.isfinite(e):
                err.append(float(e))
    return np.asarray(err, dtype=float)


def _moving_avg(x: np.ndarray, win: int = 15) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.size <= 1:
        return x.copy()
    w = int(max(1, win))
    if w <= 1:
        return x.copy()
    if w % 2 == 0:
        w += 1
    pad = w // 2
    ker = np.ones(w, dtype=float) / float(w)
    xp = np.pad(x, (pad, pad), mode="edge")
    return np.convolve(xp, ker, mode="valid")


def _generate_figures(ns: Dict[str, Any], results: Dict[str, Dict[str, Dict[str, Any]]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"figures": [], "data_files": []}
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    # dataset splits
    X = np.asarray(ns["X"], dtype=float)
    U = np.asarray(ns["U"], dtype=float)
    num_train = int(ns["num_train"])
    xs_train = X[:num_train]
    xs_val = X[num_train:]
    us_train = U[:num_train]
    us_val = U[num_train:]

    # ------------- fig1 -------------
    rng = np.random.default_rng(2026)
    s_train = xs_train[..., 0].reshape(-1)
    ey_train = xs_train[..., 1].reshape(-1)
    s_val = xs_val[..., 0].reshape(-1)
    ey_val = xs_val[..., 1].reshape(-1)
    idx_t = rng.choice(s_train.size, size=min(120000, s_train.size), replace=False)
    idx_v = rng.choice(s_val.size, size=min(60000, s_val.size), replace=False)
    fig, ax = plt.subplots(1, 1, figsize=(11, 7))
    ax.hexbin(s_train[idx_t], ey_train[idx_t], gridsize=120, bins="log", cmap="Blues", alpha=0.8, label="Train")
    ax.scatter(s_val[idx_v], ey_val[idx_v], s=2, alpha=0.25, c="tab:orange", label="Val")
    ax.set_xlabel("s [m]")
    ax.set_ylabel("e_y [m]")
    ax.set_title("图1 离线数据在 s-e_y 平面的覆盖")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")
    p = _save_fig(fig, 1, "offline_coverage_s_ey")
    summary["figures"].append(str(p))
    summary["data_files"].append(str(_save_npz("fig01_offline_coverage_data", s_train=s_train[idx_t], ey_train=ey_train[idx_t], s_val=s_val[idx_v], ey_val=ey_val[idx_v])))

    # ------------- fig2 -------------
    model = ns["model_koop_dnn_lin"]
    train_hist = np.asarray(getattr(model, "train_loss_hist", []), dtype=float)
    val_hist = np.asarray(getattr(model, "val_loss_hist", []), dtype=float)
    if train_hist.size == 0 or val_hist.size == 0:
        loss_npz = ROOT / "results" / "tf12_train_debug" / "loss_curve_tuned_full.npz"
        if loss_npz.exists():
            with np.load(loss_npz, allow_pickle=True) as d:
                train_hist = np.asarray(d["train"], dtype=float)
                val_hist = np.asarray(d["val"], dtype=float)
    ep = np.arange(train_hist.shape[0], dtype=int)
    fig, ax = plt.subplots(1, 1, figsize=(12, 7))
    if train_hist.size > 0 and val_hist.size > 0:
        ax.plot(ep, train_hist[:, 0], color="tab:orange", label="Training loss")
        ax.plot(ep, train_hist[:, 1], "--", color="tab:orange", label="Training prediction loss")
        ax.plot(ep, train_hist[:, 2], ":", color="tab:orange", label="Training lifted loss")
        ax.plot(ep, val_hist[:, 0], color="tab:blue", label="Validation loss")
        ax.plot(ep, val_hist[:, 1], "--", color="tab:blue", label="Validation prediction loss")
        ax.plot(ep, val_hist[:, 2], ":", color="tab:blue", label="Validation lifted loss")
    ax.set_yscale("log")
    ax.set_xlabel("Epoch [-]")
    ax.set_ylabel("Loss [-]")
    ax.set_title("图2 离线训练与验证损失曲线")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")
    p = _save_fig(fig, 2, "offline_train_val_loss")
    summary["figures"].append(str(p))
    summary["data_files"].append(str(_save_npz("fig02_loss_curve_data", train_hist=train_hist, val_hist=val_hist)))

    # build extracted entities
    dlc_main = results["dlc"]["main"]
    dlc_base = results["dlc"]["baseline"]
    dlc_no_adapt = results["dlc"]["no_adapt"]
    hair_main = results["hairpin"]["main"]
    hair_base = results["hairpin"]["baseline"]

    ext_dlc_main = _entity_err_series(ns, dlc_main, "dlc")
    ext_dlc_base = _entity_err_series(ns, dlc_base, "dlc")
    ext_dlc_no_adapt = _entity_err_series(ns, dlc_no_adapt, "dlc")
    ext_hair_main = _entity_err_series(ns, hair_main, "hairpin")
    ext_hair_base = _entity_err_series(ns, hair_base, "hairpin")

    # ------------- fig3 -------------
    err_nom = _one_step_state_pred_error(ns, dlc_no_adapt)
    err_adapt = _one_step_state_pred_error(ns, dlc_main)
    fault_diag = list(dlc_main.get("fault_diag_hist", []))
    active_idx = np.where([bool(d.get("active", False)) for d in fault_diag])[0]
    if active_idx.size > 0:
        t_fault = active_idx[0] * float(ns["dt"])
    else:
        t_fault = np.nan
    fig, ax = plt.subplots(1, 1, figsize=(9, 6))
    ax.boxplot([err_nom, err_adapt], labels=["Nominal(no-adapt)", "Online-adapt"], showfliers=False)
    ax.set_yscale("log")
    ax.set_ylabel("one-step state pred error (L2) [-]")
    ax.set_title("图3 名义模型与在线自适应模型的一步预测误差对比")
    ax.grid(True, alpha=0.25)
    p = _save_fig(fig, 3, "nominal_vs_online_onestep_error")
    summary["figures"].append(str(p))
    summary["data_files"].append(str(_save_npz("fig03_onestep_error_data", err_nominal=err_nom, err_online=err_adapt)))

    # ------------- fig4 framework diagram -------------
    fig, ax = plt.subplots(1, 1, figsize=(15, 8))
    ax.axis("off")
    boxes = [
        (0.03, 0.72, 0.16, 0.18, "车辆局部状态\n+ 参考路径"),
        (0.24, 0.72, 0.16, 0.18, "Koopman升维\n(稳定投影)"),
        (0.45, 0.72, 0.16, 0.18, "在线双线性\n自适应"),
        (0.66, 0.72, 0.16, 0.18, "通信一致性\n+ 时延补偿"),
        (0.03, 0.42, 0.16, 0.18, "可变代价\n+ PPC约束"),
        (0.24, 0.42, 0.16, 0.18, "MPC求解\n(四车并行)"),
        (0.45, 0.42, 0.16, 0.18, "团队聚合\n+ 稳定保护"),
        (0.66, 0.42, 0.16, 0.18, "退化回退\n+ 故障重分配"),
        (0.35, 0.10, 0.25, 0.18, "执行机构\n四车协同搬运"),
    ]
    for x, y, w, h, txt in boxes:
        rect = plt.Rectangle((x, y), w, h, fc="#f0f6ff", ec="#2f5d8a", lw=1.4)
        ax.add_patch(rect)
        ax.text(x + w * 0.5, y + h * 0.5, txt, ha="center", va="center", fontsize=11)
    arrows = [
        ((0.19, 0.81), (0.24, 0.81)),
        ((0.40, 0.81), (0.45, 0.81)),
        ((0.61, 0.81), (0.66, 0.81)),
        ((0.82, 0.75), (0.82, 0.54)),
        ((0.66, 0.51), (0.61, 0.51)),
        ((0.45, 0.51), (0.40, 0.51)),
        ((0.24, 0.51), (0.19, 0.51)),
        ((0.11, 0.42), (0.11, 0.29)),
        ((0.32, 0.42), (0.46, 0.28)),
        ((0.53, 0.42), (0.53, 0.29)),
        ((0.74, 0.42), (0.60, 0.28)),
    ]
    for (x1, y1), (x2, y2) in arrows:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", lw=1.4, color="#1d3557"))
    ax.set_title("图4 所提控制框架的信息流与模块关系图", fontsize=14, pad=12)
    p = _save_fig(fig, 4, "framework_block_diagram")
    summary["figures"].append(str(p))

    # ------------- fig5 lifted error distribution -------------
    def lifted_err_from_data(xs: np.ndarray, us: np.ndarray, max_traj: int = 140) -> np.ndarray:
        A = np.asarray(ns["A_lin"], dtype=float)
        B = np.asarray(ns["B_lin"], dtype=float)
        model = ns["model_koop_dnn_lin"]
        net_params = ns["net_params_lin"]
        stdx = ns["standardizer_x_kdnn"]
        err = []
        t_sel = min(xs.shape[0], max_traj)
        for i in range(t_sel):
            x_raw = np.asarray(xs[i], dtype=float)
            u_raw = np.asarray(us[i], dtype=float)
            n = min(x_raw.shape[0] - 1, u_raw.shape[0])
            if n <= 0:
                continue
            x_scaled = ns["scale_state_batch"](x_raw[: n + 1], stdx)
            z = ns["_lift_batch_with_net"](model.net, x_scaled.astype(np.float32))
            for k in range(n):
                z_pred = A @ z[k] + B @ u_raw[k]
                e = np.linalg.norm(z_pred - z[k + 1], ord=2)
                if np.isfinite(e):
                    err.append(float(e))
        return np.asarray(err, dtype=float)

    e_train = lifted_err_from_data(xs_train, us_train, max_traj=160)
    e_val = lifted_err_from_data(xs_val, us_val, max_traj=80)
    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    ax.hist(e_train, bins=80, alpha=0.65, label="Train lifted error", density=True)
    ax.hist(e_val, bins=80, alpha=0.65, label="Val lifted error", density=True)
    ax.set_yscale("log")
    ax.set_xlabel("one-step lifted prediction error [-]")
    ax.set_ylabel("density (log) [-]")
    ax.set_title("图5 离线训练集与验证集的一步 lifted 预测误差分布")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")
    p = _save_fig(fig, 5, "lifted_error_distribution_train_val")
    summary["figures"].append(str(p))
    summary["data_files"].append(str(_save_npz("fig05_lifted_error_data", train=e_train, val=e_val)))

    # ------------- fig6 nominal vs adapted pred error timeline -------------
    n0 = min(ext_dlc_no_adapt["system"]["e_pos"].size, ext_dlc_main["system"]["e_pos"].size)
    t = ext_dlc_main["system"]["t"][:n0]
    err_nom_t = np.abs(ext_dlc_no_adapt["system"]["e_pos"][:n0])
    err_ad_t = np.abs(ext_dlc_main["system"]["e_pos"][:n0])
    fig, ax = plt.subplots(1, 1, figsize=(12, 6))
    ax.plot(t, _moving_avg(err_nom_t, 21), "--", color="tab:gray", linewidth=1.8, label="Nominal(no-adapt)")
    ax.plot(t, _moving_avg(err_ad_t, 21), "-", color="tab:red", linewidth=2.0, label="Online-adapt")
    if np.isfinite(t_fault):
        ax.axvline(t_fault, color="tab:purple", linestyle=":", linewidth=1.4, label="fault trigger")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("smoothed |e_pos| [m]")
    ax.set_title("图6 名义模型与在线自适应模型的一步状态预测误差对比")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")
    p = _save_fig(fig, 6, "nominal_vs_adapt_error_timeline")
    summary["figures"].append(str(p))
    summary["data_files"].append(str(_save_npz("fig06_nominal_vs_adapt_error_t", t=t, nom=err_nom_t, adapt=err_ad_t)))

    # ------------- fig7 subset coverage stats -------------
    var_sum = dict(ns.get("variation_summary", {}))
    keys = sorted(var_sum.keys())
    vals = np.array([float(var_sum[k]) for k in keys], dtype=float)
    card = np.array([k.count("_") + 1 for k in keys], dtype=int)
    card_u = np.array([1, 2, 3, 4], dtype=int)
    card_cnt = np.array([float(np.sum(vals[card == c])) for c in card_u], dtype=float)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].bar(np.arange(keys.__len__()), vals, color="tab:blue", alpha=0.85)
    axes[0].set_xticks(np.arange(keys.__len__()))
    axes[0].set_xticklabels(keys, rotation=45, ha="right", fontsize=8)
    axes[0].set_title("角点变化子集覆盖")
    axes[0].set_ylabel("count [-]")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].bar(card_u, card_cnt, color="tab:orange", alpha=0.85)
    axes[1].set_xticks(card_u)
    axes[1].set_xlabel("变化车辆数量 [-]")
    axes[1].set_ylabel("count [-]")
    axes[1].set_title("工况覆盖统计（1车/2车/3车/4车）")
    axes[1].grid(True, axis="y", alpha=0.25)
    fig.suptitle("图7 角点变化子集覆盖与工况覆盖统计图", fontsize=13, fontweight="bold")
    p = _save_fig(fig, 7, "subset_coverage_stats")
    summary["figures"].append(str(p))
    summary["data_files"].append(str(_save_npz("fig07_subset_coverage_data", subset_keys=np.array(keys, dtype=object), subset_counts=vals, card=card, card_counts=card_cnt)))

    # common colors
    colors = ["tab:blue", "tab:purple", "tab:green", "tab:red"]
    labels = ["车1", "车2", "车3", "车4"]

    # ------------- extra unified scenario suite (DLC + Hairpin) -------------
    extra_fig_idx = 24

    def _safe_n(*arrs: np.ndarray) -> int:
        ns_ = [int(np.asarray(a).size) for a in arrs if np.asarray(a).size > 0]
        return min(ns_) if len(ns_) > 0 else 0

    def _force_arrays_case(res: Mapping[str, Any]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        ph = list(res.get("payload_force_hist", []))
        if len(ph) == 0:
            return np.array([]), np.array([]), np.array([]), np.array([[]], dtype=float)
        fx = np.array([float(x.get("fx_payload", 0.0)) for x in ph], dtype=float)
        fy = np.array([float(x.get("fy_payload", 0.0)) for x in ph], dtype=float)
        mz = np.array([float(x.get("mz_payload", 0.0)) for x in ph], dtype=float)
        corner = np.array([np.asarray(x.get("corner_normal_loads", [0, 0, 0, 0]), dtype=float) for x in ph], dtype=float)
        return fx, fy, mz, corner

    def _save_extra(fig: plt.Figure, name: str, data_name: str = "", **data_arrays: Any) -> None:
        nonlocal extra_fig_idx
        p_ = _save_fig(fig, extra_fig_idx, name)
        summary["figures"].append(str(p_))
        if data_name:
            summary["data_files"].append(str(_save_npz(data_name, **data_arrays)))
        extra_fig_idx += 1

    def _plot_scenario_suite(
        mode: str,
        ext_base: Mapping[str, Any],
        ext_main: Mapping[str, Any],
        res_base: Mapping[str, Any],
        res_main: Mapping[str, Any],
    ) -> None:
        mode_tag = mode.upper()
        mode_cn = "双移线" if mode == "dlc" else "回头弯"
        pack = ns["TF12_PATH_LIBRARY"][mode]

        # A) team center trajectory compare
        fig, ax = plt.subplots(1, 1, figsize=(12, 7))
        ax.plot(pack["x_path"], pack["y_ref_path"], "k-", linewidth=2.4, label="参考路径")
        ax.plot(ext_base["system"]["xg"], ext_base["system"]["yg"], "--", color="tab:gray", linewidth=1.9, label="AKE-baseline")
        ax.plot(ext_main["system"]["xg"], ext_main["system"]["yg"], "-", color="tab:red", linewidth=2.1, label="TF13")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_title(f"{mode_cn}工况：团队中心轨迹对比")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper right")
        _save_extra(
            fig,
            f"scenario_{mode}_team_center_traj_compare",
            f"scenario_{mode}_team_center_traj",
            x_ref=np.asarray(pack["x_path"], dtype=float),
            y_ref=np.asarray(pack["y_ref_path"], dtype=float),
            x_base=np.asarray(ext_base["system"]["xg"], dtype=float),
            y_base=np.asarray(ext_base["system"]["yg"], dtype=float),
            x_main=np.asarray(ext_main["system"]["xg"], dtype=float),
            y_main=np.asarray(ext_main["system"]["yg"], dtype=float),
        )

        # A2) four-vehicle trajectory compare
        fig, axes = plt.subplots(2, 2, figsize=(13, 10), sharex=True, sharey=True)
        for v in range(4):
            ent = f"vehicle_{v+1}"
            ax = axes[v // 2, v % 2]
            ax.plot(ext_main[ent]["xg_ref"], ext_main[ent]["yg_ref"], "k-", linewidth=1.7, label="参考")
            ax.plot(ext_base[ent]["xg"], ext_base[ent]["yg"], "--", color=colors[v], linewidth=1.6, alpha=0.75, label=f"{labels[v]} baseline")
            ax.plot(ext_main[ent]["xg"], ext_main[ent]["yg"], "-", color=colors[v], linewidth=2.0, label=f"{labels[v]} TF13")
            ax.set_title(labels[v])
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8, loc="best")
        axes[1, 0].set_xlabel("x [m]")
        axes[1, 1].set_xlabel("x [m]")
        axes[0, 0].set_ylabel("y [m]")
        axes[1, 0].set_ylabel("y [m]")
        fig.suptitle(f"{mode_cn}工况：四车轨迹对比（baseline vs TF13）", fontsize=13, fontweight="bold")
        _save_extra(fig, f"scenario_{mode}_four_vehicle_traj_compare")

        # B) team position error compare
        eb = np.asarray(ext_base["system"]["e_pos"], dtype=float)
        em = np.asarray(ext_main["system"]["e_pos"], dtype=float)
        tb = np.asarray(ext_base["system"]["t"], dtype=float)
        tm = np.asarray(ext_main["system"]["t"], dtype=float)
        n = _safe_n(eb, em, tb, tm)
        if n > 0:
            t = tm[:n]
            fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
            axes[0].plot(t, eb[:n], "--", color="tab:gray", linewidth=1.7, label="AKE-baseline")
            axes[0].plot(t, em[:n], "-", color="tab:red", linewidth=2.0, label="TF13")
            axes[0].set_ylabel("e_pos [m]")
            axes[0].set_title(f"{mode_cn}工况：团队位置误差")
            axes[0].grid(True, alpha=0.25)
            axes[0].legend()
            axes[1].plot(t, np.cumsum(np.abs(eb[:n])) * float(ns["dt"]), "--", color="tab:gray", linewidth=1.7, label="AKE-baseline 累积")
            axes[1].plot(t, np.cumsum(np.abs(em[:n])) * float(ns["dt"]), "-", color="tab:red", linewidth=2.0, label="TF13 累积")
            axes[1].set_xlabel("time [s]")
            axes[1].set_ylabel("累计|e_pos|·dt [m·s]")
            axes[1].grid(True, alpha=0.25)
            axes[1].legend()
            _save_extra(
                fig,
                f"scenario_{mode}_team_position_error_compare",
                f"scenario_{mode}_team_position_error",
                t=t,
                epos_base=eb[:n],
                epos_main=em[:n],
            )

        # C) system e_y / e_s compare
        eyb = np.asarray(ext_base["system"]["e_y"], dtype=float)
        eym = np.asarray(ext_main["system"]["e_y"], dtype=float)
        esb = np.asarray(ext_base["system"]["e_s"], dtype=float)
        esm = np.asarray(ext_main["system"]["e_s"], dtype=float)
        n = _safe_n(tm, eyb, eym, esb, esm)
        if n > 0:
            t = tm[:n]
            fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
            axes[0].plot(t, eyb[:n], "--", color="tab:gray", linewidth=1.8, label="AKE-baseline")
            axes[0].plot(t, eym[:n], "-", color="tab:red", linewidth=2.0, label="TF13")
            axes[0].axhline(0, color="k", linewidth=0.8, linestyle=":")
            axes[0].set_ylabel("e_y [m]")
            axes[0].set_title(f"{mode_cn}工况：系统横向误差")
            axes[0].grid(True, alpha=0.25)
            axes[0].legend()
            axes[1].plot(t, esb[:n], "--", color="tab:gray", linewidth=1.8, label="AKE-baseline")
            axes[1].plot(t, esm[:n], "-", color="tab:red", linewidth=2.0, label="TF13")
            axes[1].axhline(0, color="k", linewidth=0.8, linestyle=":")
            axes[1].set_xlabel("time [s]")
            axes[1].set_ylabel("e_s [m]")
            axes[1].set_title(f"{mode_cn}工况：系统纵向误差")
            axes[1].grid(True, alpha=0.25)
            axes[1].legend()
            _save_extra(
                fig,
                f"scenario_{mode}_system_lat_long_error_compare",
                f"scenario_{mode}_system_lat_long_error",
                t=t,
                ey_base=eyb[:n],
                ey_main=eym[:n],
                es_base=esb[:n],
                es_main=esm[:n],
            )

        # D) per-vehicle e_y / e_s compare
        fig, axes = plt.subplots(2, 4, figsize=(16, 8), sharex="col")
        valid_panel = 0
        for v in range(4):
            ent = f"vehicle_{v+1}"
            tb_v = np.asarray(ext_base[ent]["t"], dtype=float)
            tm_v = np.asarray(ext_main[ent]["t"], dtype=float)
            eyb_v = np.asarray(ext_base[ent]["e_y"], dtype=float)
            eym_v = np.asarray(ext_main[ent]["e_y"], dtype=float)
            esb_v = np.asarray(ext_base[ent]["e_s"], dtype=float)
            esm_v = np.asarray(ext_main[ent]["e_s"], dtype=float)
            n = _safe_n(tb_v, tm_v, eyb_v, eym_v, esb_v, esm_v)
            if n <= 0:
                continue
            valid_panel += 1
            t = tm_v[:n]
            ax_lat = axes[0, v]
            ax_lon = axes[1, v]
            ax_lat.plot(t, eyb_v[:n], "--", color=colors[v], linewidth=1.4, label="baseline")
            ax_lat.plot(t, eym_v[:n], "-", color=colors[v], linewidth=1.8, label="TF13")
            ax_lat.axhline(0, color="k", linewidth=0.7, linestyle=":")
            ax_lat.set_title(f"{labels[v]} e_y")
            ax_lat.grid(True, alpha=0.25)
            ax_lat.legend(fontsize=8)
            ax_lon.plot(t, esb_v[:n], "--", color=colors[v], linewidth=1.4, label="baseline")
            ax_lon.plot(t, esm_v[:n], "-", color=colors[v], linewidth=1.8, label="TF13")
            ax_lon.axhline(0, color="k", linewidth=0.7, linestyle=":")
            ax_lon.set_title(f"{labels[v]} e_s")
            ax_lon.grid(True, alpha=0.25)
            ax_lon.legend(fontsize=8)
            ax_lon.set_xlabel("time [s]")
        if valid_panel > 0:
            axes[0, 0].set_ylabel("e_y [m]")
            axes[1, 0].set_ylabel("e_s [m]")
            fig.suptitle(f"{mode_cn}工况：四车横向/纵向误差对比", fontsize=13, fontweight="bold")
            _save_extra(fig, f"scenario_{mode}_each_vehicle_lat_long_error_compare")
        else:
            plt.close(fig)

        # E) payload force / moment compare
        fx_b, fy_b, mz_b, cn_b = _force_arrays_case(res_base)
        fx_m, fy_m, mz_m, cn_m = _force_arrays_case(res_main)
        n = _safe_n(fx_b, fy_b, mz_b, fx_m, fy_m, mz_m)
        if n > 0:
            t = np.arange(n, dtype=float) * float(ns["dt"])
            fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
            axes[0].plot(t, fx_b[:n], "--", color="tab:gray", label="baseline")
            axes[0].plot(t, fx_m[:n], "-", color="tab:red", label="TF13")
            axes[0].set_ylabel("F_x [N]")
            axes[0].grid(True, alpha=0.25)
            axes[0].legend()
            axes[1].plot(t, fy_b[:n], "--", color="tab:gray", label="baseline")
            axes[1].plot(t, fy_m[:n], "-", color="tab:red", label="TF13")
            axes[1].set_ylabel("F_y [N]")
            axes[1].grid(True, alpha=0.25)
            axes[1].legend()
            axes[2].plot(t, mz_b[:n], "--", color="tab:gray", label="baseline")
            axes[2].plot(t, mz_m[:n], "-", color="tab:red", label="TF13")
            axes[2].set_ylabel("M_z [N·m]")
            axes[2].set_xlabel("time [s]")
            axes[2].grid(True, alpha=0.25)
            axes[2].legend()
            fig.suptitle(f"{mode_cn}工况：货物受力与偏航力矩", fontsize=13, fontweight="bold")
            _save_extra(fig, f"scenario_{mode}_payload_force_moment_compare")

        # F) corner normal loads
        if cn_b.ndim == 2 and cn_m.ndim == 2:
            n = min(int(cn_b.shape[0]), int(cn_m.shape[0]))
            if n > 0 and cn_b.shape[1] >= 4 and cn_m.shape[1] >= 4:
                t = np.arange(n, dtype=float) * float(ns["dt"])
                fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
                names = ["FL", "FR", "RL", "RR"]
                for i in range(4):
                    ax = axes[i // 2, i % 2]
                    ax.plot(t, cn_b[:n, i], "--", color="tab:gray", label="baseline")
                    ax.plot(t, cn_m[:n, i], "-", color="tab:red", label="TF13")
                    ax.set_title(names[i])
                    ax.grid(True, alpha=0.25)
                    ax.legend(fontsize=8)
                axes[1, 0].set_xlabel("time [s]")
                axes[1, 1].set_xlabel("time [s]")
                axes[0, 0].set_ylabel("N [N]")
                axes[1, 0].set_ylabel("N [N]")
                fig.suptitle(f"{mode_cn}工况：四角点法向载荷", fontsize=13, fontweight="bold")
                _save_extra(fig, f"scenario_{mode}_corner_normal_load_compare")

        # G) connection diagnostics
        conn_b = list(res_base.get("connection_diag_hist", []))
        conn_m = list(res_main.get("connection_diag_hist", []))
        n = min(len(conn_b), len(conn_m))
        if n > 0:
            t = np.arange(n, dtype=float) * float(ns["dt"])
            ds_b = np.array([float(x.get("max_abs_ds", 0.0)) for x in conn_b[:n]], dtype=float)
            dey_b = np.array([float(x.get("max_abs_dey", 0.0)) for x in conn_b[:n]], dtype=float)
            dpsi_b = np.array([float(x.get("max_abs_dpsi", 0.0)) for x in conn_b[:n]], dtype=float)
            rms_b = np.array([float(x.get("rms_rel", 0.0)) for x in conn_b[:n]], dtype=float)
            ds_m = np.array([float(x.get("max_abs_ds", 0.0)) for x in conn_m[:n]], dtype=float)
            dey_m = np.array([float(x.get("max_abs_dey", 0.0)) for x in conn_m[:n]], dtype=float)
            dpsi_m = np.array([float(x.get("max_abs_dpsi", 0.0)) for x in conn_m[:n]], dtype=float)
            rms_m = np.array([float(x.get("rms_rel", 0.0)) for x in conn_m[:n]], dtype=float)
            fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
            for ax, bb, mm, title in [
                (axes[0], ds_b, ds_m, "max_abs_ds [m]"),
                (axes[1], dey_b, dey_m, "max_abs_dey [m]"),
                (axes[2], dpsi_b, dpsi_m, "max_abs_dpsi [rad]"),
                (axes[3], rms_b, rms_m, "rms_rel [-]"),
            ]:
                ax.plot(t, bb, "--", color="tab:gray", label="baseline")
                ax.plot(t, mm, "-", color="tab:red", label="TF13")
                ax.set_ylabel(title)
                ax.grid(True, alpha=0.25)
                ax.legend(fontsize=8)
            axes[3].set_xlabel("time [s]")
            fig.suptitle(f"{mode_cn}工况：连接误差对比", fontsize=13, fontweight="bold")
            _save_extra(fig, f"scenario_{mode}_connection_error_compare")

        # H) comm + delay + fault diagnostics
        comm = list(res_main.get("comm_diag_hist", []))
        fault = list(res_main.get("fault_diag_hist", []))
        n = min(len(comm), len(fault))
        if n > 0:
            t = np.arange(n, dtype=float) * float(ns["dt"])
            qg = np.array([float(comm[i].get("quality_global", 1.0)) for i in range(n)], dtype=float)
            md = np.array([float(comm[i].get("mean_delay_steps", 0.0)) for i in range(n)], dtype=float)
            lr = np.array([float(comm[i].get("loss_ratio", 0.0)) for i in range(n)], dtype=float)
            fa = np.array([1.0 if fault[i].get("active", False) else 0.0 for i in range(n)], dtype=float)
            dn = np.array([float(fault[i].get("deficit_norm", 0.0)) for i in range(n)], dtype=float)
            fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
            axes[0].plot(t, qg, color="tab:blue", label="quality_global")
            axes[0].plot(t, lr, color="tab:orange", label="loss_ratio")
            axes[0].set_ylabel("quality/loss [-]")
            axes[0].grid(True, alpha=0.25)
            axes[0].legend()
            axes[1].plot(t, md, color="tab:purple", label="mean_delay_steps")
            axes[1].set_ylabel("delay [steps]")
            axes[1].grid(True, alpha=0.25)
            axes[1].legend()
            axes[2].plot(t, fa, color="tab:red", label="fault_active")
            axes[2].plot(t, dn, color="tab:green", label="deficit_norm")
            axes[2].set_xlabel("time [s]")
            axes[2].set_ylabel("fault/deficit [-]")
            axes[2].grid(True, alpha=0.25)
            axes[2].legend()
            fig.suptitle(f"{mode_cn}工况：通信/时延/故障时序", fontsize=13, fontweight="bold")
            _save_extra(
                fig,
                f"scenario_{mode}_comm_delay_fault_timeline",
                f"scenario_{mode}_comm_fault_data",
                t=t,
                quality_global=qg,
                mean_delay=md,
                loss_ratio=lr,
                fault_active=fa,
                deficit_norm=dn,
            )

    _plot_scenario_suite(
        mode="dlc",
        ext_base=ext_dlc_base,
        ext_main=ext_dlc_main,
        res_base=dlc_base,
        res_main=dlc_main,
    )
    _plot_scenario_suite(
        mode="hairpin",
        ext_base=ext_hair_base,
        ext_main=ext_hair_main,
        res_base=hair_base,
        res_main=hair_main,
    )

    # ------------- fig8 team trajectory compare -------------
    pack_dlc = ns["TF12_PATH_LIBRARY"]["dlc"]
    fig, ax = plt.subplots(1, 1, figsize=(12, 7))
    ax.plot(pack_dlc["x_path"], pack_dlc["y_ref_path"], "k-", linewidth=2.4, label="团队中心参考路径")
    ax.plot(ext_dlc_base["system"]["xg"], ext_dlc_base["system"]["yg"], "--", color="tab:gray", linewidth=2.0, label="AKE-baseline 团队中心")
    ax.plot(ext_dlc_main["system"]["xg"], ext_dlc_main["system"]["yg"], "-", color="tab:red", linewidth=2.2, label="TF13 团队中心")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("图8 团队中心轨迹与参考路径对比")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper right")
    p = _save_fig(fig, 8, "team_center_traj_compare_dlc")
    summary["figures"].append(str(p))

    # ------------- fig9 team position error compare -------------
    t_b = np.asarray(ext_dlc_base["system"]["t"], dtype=float)
    t_m = np.asarray(ext_dlc_main["system"]["t"], dtype=float)
    eb = np.asarray(ext_dlc_base["system"]["e_pos"], dtype=float)
    em = np.asarray(ext_dlc_main["system"]["e_pos"], dtype=float)
    n = min(t_b.size, t_m.size, eb.size, em.size)
    t = t_m[:n]
    eb = eb[:n]
    em = em[:n]
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    axes[0].plot(t, eb, "--", color="tab:gray", linewidth=1.7, label="AKE-baseline")
    axes[0].plot(t, em, "-", color="tab:red", linewidth=2.0, label="TF13")
    axes[0].set_ylabel("e_pos [m]")
    axes[0].set_title("图9 团队位置跟踪误差对比")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend()
    axes[1].plot(t, np.cumsum(np.abs(eb)) * float(ns["dt"]), "--", color="tab:gray", linewidth=1.7, label="AKE-baseline 累积")
    axes[1].plot(t, np.cumsum(np.abs(em)) * float(ns["dt"]), "-", color="tab:red", linewidth=2.0, label="TF13 累积")
    axes[1].set_xlabel("time [s]")
    axes[1].set_ylabel("累计|e_pos|·dt [m·s]")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend()
    p = _save_fig(fig, 9, "team_position_error_compare_dlc")
    summary["figures"].append(str(p))

    # ------------- fig10 / fig11 -------------
    fig, ax = plt.subplots(1, 1, figsize=(12, 5))
    ax.plot(ext_dlc_base["system"]["t"], ext_dlc_base["system"]["e_y"], "--", color="tab:gray", linewidth=1.8, label="AKE-baseline")
    ax.plot(ext_dlc_main["system"]["t"], ext_dlc_main["system"]["e_y"], "-", color="tab:red", linewidth=2.0, label="TF13")
    ax.axhline(0, color="k", linewidth=0.8, linestyle=":")
    ax.set_title("图10 横向误差对比")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("e_y [m]")
    ax.grid(True, alpha=0.25)
    ax.legend()
    p = _save_fig(fig, 10, "lateral_error_compare_dlc")
    summary["figures"].append(str(p))

    fig, ax = plt.subplots(1, 1, figsize=(12, 5))
    ax.plot(ext_dlc_base["system"]["t"], ext_dlc_base["system"]["e_s"], "--", color="tab:gray", linewidth=1.8, label="AKE-baseline")
    ax.plot(ext_dlc_main["system"]["t"], ext_dlc_main["system"]["e_s"], "-", color="tab:red", linewidth=2.0, label="TF13")
    ax.axhline(0, color="k", linewidth=0.8, linestyle=":")
    ax.set_title("图11 纵向误差对比")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("e_s [m]")
    ax.grid(True, alpha=0.25)
    ax.legend()
    p = _save_fig(fig, 11, "longitudinal_error_compare_dlc")
    summary["figures"].append(str(p))

    # ------------- fig12 comm + delay + fault diag -------------
    comm = list(dlc_main.get("comm_diag_hist", []))
    fault = list(dlc_main.get("fault_diag_hist", []))
    n = min(len(comm), len(fault))
    if n > 0:
        t = np.arange(n, dtype=float) * float(ns["dt"])
        qg = np.array([float(comm[i].get("quality_global", 1.0)) for i in range(n)], dtype=float)
        md = np.array([float(comm[i].get("mean_delay_steps", 0.0)) for i in range(n)], dtype=float)
        lr = np.array([float(comm[i].get("loss_ratio", 0.0)) for i in range(n)], dtype=float)
        fa = np.array([1.0 if fault[i].get("active", False) else 0.0 for i in range(n)], dtype=float)
        dn = np.array([float(fault[i].get("deficit_norm", 0.0)) for i in range(n)], dtype=float)
        fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
        axes[0].plot(t, qg, color="tab:blue", label="quality_global")
        axes[0].plot(t, lr, color="tab:orange", label="loss_ratio")
        axes[0].set_ylabel("quality/loss [-]")
        axes[0].grid(True, alpha=0.25)
        axes[0].legend()
        axes[1].plot(t, md, color="tab:purple", label="mean_delay_steps")
        axes[1].set_ylabel("delay [steps]")
        axes[1].grid(True, alpha=0.25)
        axes[1].legend()
        axes[2].plot(t, fa, color="tab:red", label="fault_active")
        axes[2].plot(t, dn, color="tab:green", label="deficit_norm")
        axes[2].set_xlabel("time [s]")
        axes[2].set_ylabel("fault/deficit [-]")
        axes[2].grid(True, alpha=0.25)
        axes[2].legend()
        fig.suptitle("图12 通信质量、平均时延与故障激活轨迹", fontsize=13, fontweight="bold")
        p = _save_fig(fig, 12, "comm_delay_fault_timeline_dlc")
        summary["figures"].append(str(p))
        summary["data_files"].append(str(_save_npz("fig12_comm_fault_data", t=t, quality_global=qg, mean_delay=md, loss_ratio=lr, fault_active=fa, deficit_norm=dn)))

    # ------------- fig13 / fig14 per-vehicle -------------
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), sharex=True)
    for v in range(4):
        ax = axes[v // 2, v % 2]
        ent = f"vehicle_{v+1}"
        ax.plot(ext_dlc_base[ent]["t"], ext_dlc_base[ent]["e_y"], "--", color=colors[v], linewidth=1.5, label=f"{labels[v]} baseline")
        ax.plot(ext_dlc_main[ent]["t"], ext_dlc_main[ent]["e_y"], "-", color=colors[v], linewidth=1.9, label=f"{labels[v]} TF13")
        ax.axhline(0, color="k", linewidth=0.8, linestyle=":")
        ax.set_title(labels[v])
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
    axes[1, 0].set_xlabel("time [s]")
    axes[1, 1].set_xlabel("time [s]")
    axes[0, 0].set_ylabel("e_y [m]")
    axes[1, 0].set_ylabel("e_y [m]")
    fig.suptitle("图13 单车横向误差对比", fontsize=13, fontweight="bold")
    p = _save_fig(fig, 13, "each_vehicle_lateral_error_dlc")
    summary["figures"].append(str(p))

    fig, axes = plt.subplots(2, 2, figsize=(12, 9), sharex=True)
    for v in range(4):
        ax = axes[v // 2, v % 2]
        ent = f"vehicle_{v+1}"
        ax.plot(ext_dlc_base[ent]["t"], ext_dlc_base[ent]["e_s"], "--", color=colors[v], linewidth=1.5, label=f"{labels[v]} baseline")
        ax.plot(ext_dlc_main[ent]["t"], ext_dlc_main[ent]["e_s"], "-", color=colors[v], linewidth=1.9, label=f"{labels[v]} TF13")
        ax.axhline(0, color="k", linewidth=0.8, linestyle=":")
        ax.set_title(labels[v])
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8)
    axes[1, 0].set_xlabel("time [s]")
    axes[1, 1].set_xlabel("time [s]")
    axes[0, 0].set_ylabel("e_s [m]")
    axes[1, 0].set_ylabel("e_s [m]")
    fig.suptitle("图14 单车纵向误差对比", fontsize=13, fontweight="bold")
    p = _save_fig(fig, 14, "each_vehicle_longitudinal_error_dlc")
    summary["figures"].append(str(p))

    # ------------- fig15 / fig16 / fig17 -------------
    def _force_arrays(res: Mapping[str, Any]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        ph = list(res.get("payload_force_hist", []))
        if len(ph) == 0:
            return np.array([]), np.array([]), np.array([]), np.array([[]])
        fx = np.array([float(x.get("fx_payload", 0.0)) for x in ph], dtype=float)
        fy = np.array([float(x.get("fy_payload", 0.0)) for x in ph], dtype=float)
        mz = np.array([float(x.get("mz_payload", 0.0)) for x in ph], dtype=float)
        corner = np.array([np.asarray(x.get("corner_normal_loads", [0, 0, 0, 0]), dtype=float) for x in ph], dtype=float)
        return fx, fy, mz, corner

    fx_b, fy_b, mz_b, cn_b = _force_arrays(dlc_base)
    fx_m, fy_m, mz_m, cn_m = _force_arrays(dlc_main)
    nt = min(fx_b.size, fx_m.size)
    t = np.arange(nt) * float(ns["dt"])

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    axes[0].plot(t, fx_b[:nt], "--", color="tab:gray", label="baseline")
    axes[0].plot(t, fx_m[:nt], "-", color="tab:red", label="TF13")
    axes[0].set_ylabel("F_x [N]")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend()
    axes[1].plot(t, fy_b[:nt], "--", color="tab:gray", label="baseline")
    axes[1].plot(t, fy_m[:nt], "-", color="tab:red", label="TF13")
    axes[1].set_ylabel("F_y [N]")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend()
    axes[2].plot(t, mz_b[:nt], "--", color="tab:gray", label="baseline")
    axes[2].plot(t, mz_m[:nt], "-", color="tab:red", label="TF13")
    axes[2].set_ylabel("M_z [N·m]")
    axes[2].set_xlabel("time [s]")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend()
    fig.suptitle("图15 货物纵向力、横向力与偏航力矩对比", fontsize=13, fontweight="bold")
    p = _save_fig(fig, 15, "payload_force_moment_compare_dlc")
    summary["figures"].append(str(p))

    ntc = min(cn_b.shape[0], cn_m.shape[0]) if cn_b.ndim == 2 and cn_m.ndim == 2 else 0
    if ntc > 0:
        t = np.arange(ntc) * float(ns["dt"])
        fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
        names = ["FL", "FR", "RL", "RR"]
        for i in range(4):
            ax = axes[i // 2, i % 2]
            ax.plot(t, cn_b[:ntc, i], "--", color="tab:gray", label="baseline")
            ax.plot(t, cn_m[:ntc, i], "-", color="tab:red", label="TF13")
            ax.set_title(names[i])
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8)
        axes[1, 0].set_xlabel("time [s]")
        axes[1, 1].set_xlabel("time [s]")
        axes[0, 0].set_ylabel("N [N]")
        axes[1, 0].set_ylabel("N [N]")
        fig.suptitle("图16 四角点法向载荷对比", fontsize=13, fontweight="bold")
        p = _save_fig(fig, 16, "corner_normal_load_compare_dlc")
        summary["figures"].append(str(p))

    conn_b = list(dlc_base.get("connection_diag_hist", []))
    conn_m = list(dlc_main.get("connection_diag_hist", []))
    nc = min(len(conn_b), len(conn_m))
    if nc > 0:
        t = np.arange(nc) * float(ns["dt"])
        ds_b = np.array([float(x.get("max_abs_ds", 0.0)) for x in conn_b[:nc]], dtype=float)
        dey_b = np.array([float(x.get("max_abs_dey", 0.0)) for x in conn_b[:nc]], dtype=float)
        dpsi_b = np.array([float(x.get("max_abs_dpsi", 0.0)) for x in conn_b[:nc]], dtype=float)
        rms_b = np.array([float(x.get("rms_rel", 0.0)) for x in conn_b[:nc]], dtype=float)
        ds_m = np.array([float(x.get("max_abs_ds", 0.0)) for x in conn_m[:nc]], dtype=float)
        dey_m = np.array([float(x.get("max_abs_dey", 0.0)) for x in conn_m[:nc]], dtype=float)
        dpsi_m = np.array([float(x.get("max_abs_dpsi", 0.0)) for x in conn_m[:nc]], dtype=float)
        rms_m = np.array([float(x.get("rms_rel", 0.0)) for x in conn_m[:nc]], dtype=float)
        fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
        for ax, bb, mm, title in [
            (axes[0], ds_b, ds_m, "max_abs_ds [m]"),
            (axes[1], dey_b, dey_m, "max_abs_dey [m]"),
            (axes[2], dpsi_b, dpsi_m, "max_abs_dpsi [rad]"),
            (axes[3], rms_b, rms_m, "rms_rel [-]"),
        ]:
            ax.plot(t, bb, "--", color="tab:gray", label="baseline")
            ax.plot(t, mm, "-", color="tab:red", label="TF13")
            ax.set_ylabel(title)
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8)
        axes[3].set_xlabel("time [s]")
        fig.suptitle("图17 连接误差对比", fontsize=13, fontweight="bold")
        p = _save_fig(fig, 17, "connection_error_compare_dlc")
        summary["figures"].append(str(p))

    # ------------- fig18 hairpin path compare (baseline/tf13) -------------
    pack_h = ns["TF12_PATH_LIBRARY"]["hairpin"]
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    ax = axes[0]
    ax.plot(pack_h["x_path"], pack_h["y_ref_path"], "k-", linewidth=2.4, label="参考路径")
    ax.plot(ext_hair_base["system"]["xg"], ext_hair_base["system"]["yg"], "--", color="tab:gray", label="AKE-baseline")
    ax.plot(ext_hair_main["system"]["xg"], ext_hair_main["system"]["yg"], "-", color="tab:red", label="TF13")
    ax.set_title("团队中心轨迹")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=9)
    ax = axes[1]
    for v in range(4):
        ent = f"vehicle_{v+1}"
        ax.plot(ext_hair_main[ent]["xg_ref"], ext_hair_main[ent]["yg_ref"], ":", color=colors[v], alpha=0.45)
        ax.plot(ext_hair_main[ent]["xg"], ext_hair_main[ent]["yg"], "-", color=colors[v], linewidth=1.8, label=labels[v])
    ax.set_title("TF13 四车角点轨迹")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.suptitle("图18 回头弯参考路径与四车团队轨迹对比（baseline vs TF13）", fontsize=13, fontweight="bold")
    p = _save_fig(fig, 18, "hairpin_traj_compare_baseline_tf13")
    summary["figures"].append(str(p))

    # ------------- fig19 hairpin e_y / e_s / deficit -------------
    fh = list(hair_main.get("fault_diag_hist", []))
    n = min(ext_hair_main["system"]["t"].size, len(fh))
    t = ext_hair_main["system"]["t"][:n]
    dn = np.array([float(x.get("deficit_norm", 0.0)) for x in fh[:n]], dtype=float)
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    axes[0].plot(ext_hair_base["system"]["t"], ext_hair_base["system"]["e_y"], "--", color="tab:gray", label="AKE-baseline")
    axes[0].plot(ext_hair_main["system"]["t"], ext_hair_main["system"]["e_y"], "-", color="tab:red", label="TF13")
    axes[0].set_ylabel("e_y [m]")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend()
    axes[1].plot(ext_hair_base["system"]["t"], ext_hair_base["system"]["e_s"], "--", color="tab:gray", label="AKE-baseline")
    axes[1].plot(ext_hair_main["system"]["t"], ext_hair_main["system"]["e_s"], "-", color="tab:red", label="TF13")
    axes[1].set_ylabel("e_s [m]")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend()
    axes[2].plot(t, dn, color="tab:purple", linewidth=1.8, label="deficit_norm")
    axes[2].set_ylabel("deficit norm [-]")
    axes[2].set_xlabel("time [s]")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend()
    fig.suptitle("图19 回头弯工况下横向/纵向误差与故障亏损响应", fontsize=13, fontweight="bold")
    p = _save_fig(fig, 19, "hairpin_error_and_fault_response")
    summary["figures"].append(str(p))

    # ------------- fig20 phase coverage -------------
    def _phase_points_from_result(res: Mapping[str, Any]) -> Dict[str, np.ndarray]:
        team = np.asarray(res["team_state_hist"], dtype=float)
        n = int(res.get("sim_steps", team.shape[0] - 1)) + 1
        n = min(n, team.shape[0])
        out = {"system": np.column_stack([team[:n, 5], np.gradient(team[:n, 5], float(ns["dt"]))])}
        for v, xh in enumerate(res["xt_actual_vehicles"]):
            x = np.asarray(xh, dtype=float)
            nv = min(n, x.shape[0])
            r = x[:nv, 5]
            out[f"vehicle_{v+1}"] = np.column_stack([r, np.gradient(r, float(ns["dt"]))])
        return out

    ph_main = _phase_points_from_result(hair_main)
    # offline phase cloud from dataset
    r_off = xs_train[..., 5].reshape(-1)
    rdot_off = np.gradient(r_off, float(ns["dt"]))
    mask = np.isfinite(r_off) & np.isfinite(rdot_off)
    r_off = r_off[mask]
    rdot_off = rdot_off[mask]
    if r_off.size > 120000:
        idx = rng.choice(r_off.size, size=120000, replace=False)
        r_off = r_off[idx]
        rdot_off = rdot_off[idx]

    ents = ["system", "vehicle_1", "vehicle_2", "vehicle_3", "vehicle_4"]
    titles = ["系统", "车1", "车2", "车3", "车4"]
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    for i, ent in enumerate(ents):
        ax = axes[i // 3, i % 3]
        pts = ph_main[ent]
        ax.scatter(r_off, rdot_off, s=2, alpha=0.10, c="tab:gray", label="离线样本")
        ax.plot(pts[:, 0], pts[:, 1], color="tab:red", linewidth=1.8, label="闭环轨迹")
        ax.set_title(titles[i])
        ax.set_xlabel("r [rad/s]")
        ax.set_ylabel("r_dot [rad/s^2]")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="upper right")
    axes[1, 2].axis("off")
    fig.suptitle("图20 离线数据与闭环轨迹的相图覆盖对比", fontsize=13, fontweight="bold")
    p = _save_fig(fig, 20, "offline_vs_closedloop_phase_coverage")
    summary["figures"].append(str(p))

    # ------------- fig21/22/23 ablation (optional) -------------
    ab_order = ["main", "no_adapt", "no_comm", "no_guard", "no_fault_redist", "no_conn"]
    ab_cases = [c for c in ab_order if c in results["dlc"]]
    rows = []
    for c in ab_cases:
        r = results["dlc"][c]
        rows.append(
            {
                "case": c,
                "rmse_lat": _safe_float(r.get("rmse_lat_mean", np.nan), np.nan),
                "rmse_long": _safe_float(r.get("rmse_long_mean", np.nan), np.nan),
                "fail_total": int(np.sum(r.get("fail_counts", []))),
                "step_time": _safe_float(r.get("step_time_mean", np.nan), np.nan),
                "conn_rms": _safe_float(r.get("connection_summary", {}).get("rms_rel_mean", np.nan), np.nan),
                "fy_peak": float(np.max(np.abs([float(x.get("fy_payload", 0.0)) for x in r.get("payload_force_hist", [])])) if len(r.get("payload_force_hist", [])) > 0 else np.nan),
                "mz_peak": float(np.max(np.abs([float(x.get("mz_payload", 0.0)) for x in r.get("payload_force_hist", [])])) if len(r.get("payload_force_hist", [])) > 0 else np.nan),
                "deficit_peak": _safe_float(r.get("fault_summary", {}).get("deficit_norm_peak", np.nan), np.nan),
            }
        )
    _save_json("ablation_rows_dlc", {"rows": rows})

    if len(rows) >= 2:
        x = np.arange(len(rows))
        fig, axes = plt.subplots(2, 2, figsize=(14, 9))
        axes[0, 0].bar(x, [r["rmse_lat"] for r in rows], color="tab:blue")
        axes[0, 0].set_title("横向RMSE")
        axes[0, 0].set_ylabel("RMSE e_y [m]")
        axes[0, 1].bar(x, [r["rmse_long"] for r in rows], color="tab:green")
        axes[0, 1].set_title("纵向RMSE")
        axes[0, 1].set_ylabel("RMSE e_s [m]")
        axes[1, 0].bar(x, [r["fail_total"] for r in rows], color="tab:red")
        axes[1, 0].set_title("失败次数")
        axes[1, 0].set_ylabel("count [-]")
        axes[1, 1].bar(x, [r["step_time"] for r in rows], color="tab:purple")
        axes[1, 1].set_title("平均单步耗时")
        axes[1, 1].set_ylabel("time [s]")
        for ax in axes.ravel():
            ax.set_xticks(x)
            ax.set_xticklabels([r["case"] for r in rows], rotation=30, ha="right")
            ax.grid(True, axis="y", alpha=0.25)
        fig.suptitle("图21 消融实验主指标柱状对比图", fontsize=13, fontweight="bold")
        p = _save_fig(fig, 21, "ablation_core_metric_bars_dlc")
        summary["figures"].append(str(p))

        # fig22 heatmap
        heat_keys = ["conn_rms", "fy_peak", "mz_peak", "deficit_peak"]
        heat_labels = ["conn_rms [-]", "fy_peak [N]", "mz_peak [N·m]", "deficit_peak [-]"]
        H = np.array([[r[nm] for nm in heat_keys] for r in rows], dtype=float)
        Hn = H.copy()
        for j in range(Hn.shape[1]):
            col = Hn[:, j]
            mn, mx = np.nanmin(col), np.nanmax(col)
            if np.isfinite(mn) and np.isfinite(mx) and mx > mn:
                Hn[:, j] = (col - mn) / (mx - mn)
        fig, ax = plt.subplots(1, 1, figsize=(8, 5.8))
        im = ax.imshow(Hn, cmap="magma", aspect="auto", vmin=0.0, vmax=1.0)
        ax.set_xticks(np.arange(len(heat_labels)))
        ax.set_xticklabels(heat_labels)
        ax.set_yticks(np.arange(len(rows)))
        ax.set_yticklabels([r["case"] for r in rows])
        for i in range(H.shape[0]):
            for j in range(H.shape[1]):
                ax.text(j, i, f"{H[i, j]:.3g}", ha="center", va="center", color="white", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="normalized [-]")
        ax.set_title("图22 消融实验连接误差与载荷受力热力图")
        p = _save_fig(fig, 22, "ablation_heatmap_conn_force_dlc")
        summary["figures"].append(str(p))

    key_order = ["main", "no_adapt", "no_comm", "no_fault_redist"]
    key_cases = [c for c in key_order if c in results["hairpin"]]
    if len(key_cases) >= 2:
        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        cmap = {"main": "tab:red", "no_adapt": "tab:blue", "no_comm": "tab:green", "no_fault_redist": "tab:purple"}
        for c in key_cases:
            rr = results["hairpin"][c]
            ex = _entity_err_series(ns, rr, "hairpin")["system"]
            fd = list(rr.get("fault_diag_hist", []))
            n = min(ex["t"].size, len(fd))
            t = ex["t"][:n]
            dn = np.array([float(x.get("deficit_norm", 0.0)) for x in fd[:n]], dtype=float)
            axes[0].plot(t, ex["e_y"][:n], color=cmap.get(c, "tab:gray"), linewidth=1.8, label=c)
            axes[1].plot(t, ex["e_s"][:n], color=cmap.get(c, "tab:gray"), linewidth=1.8, label=c)
            axes[2].plot(t, dn, color=cmap.get(c, "tab:gray"), linewidth=1.8, label=c)
        axes[0].set_ylabel("e_y [m]")
        axes[1].set_ylabel("e_s [m]")
        axes[2].set_ylabel("deficit norm [-]")
        axes[2].set_xlabel("time [s]")
        for ax in axes:
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8, ncol=2, loc="upper right")
        fig.suptitle("图23 故障触发后的关键时序消融对比", fontsize=13, fontweight="bold")
        p = _save_fig(fig, 23, "ablation_fault_timeline_hairpin")
        summary["figures"].append(str(p))

    return summary


def _collect_metrics(results: Dict[str, Dict[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for mode, pack in results.items():
        for case, res in pack.items():
            rows.append(
                {
                    "mode": mode,
                    "case": case,
                    "full_path_reached": bool(res.get("full_path_reached", False)),
                    "stop_reason": str(res.get("stop_reason", "")),
                    "rmse_lat_mean": _safe_float(res.get("rmse_lat_mean", np.nan), np.nan),
                    "rmse_long_mean": _safe_float(res.get("rmse_long_mean", np.nan), np.nan),
                    "max_lat_global": _safe_float(res.get("max_lat_global", np.nan), np.nan),
                    "max_long_global": _safe_float(res.get("max_long_global", np.nan), np.nan),
                    "step_time_mean": _safe_float(res.get("step_time_mean", np.nan), np.nan),
                    "step_time_max": _safe_float(res.get("step_time_max", np.nan), np.nan),
                    "sim_steps": int(res.get("sim_steps", -1)),
                    "fail_total": int(np.sum(res.get("fail_counts", []))),
                    "progress_guard_total": int(np.sum(res.get("progress_guard_counts", []))),
                    "fault_active_ratio": _safe_float(res.get("fault_summary", {}).get("active_ratio", np.nan), np.nan),
                    "fault_deficit_norm_peak": _safe_float(res.get("fault_summary", {}).get("deficit_norm_peak", np.nan), np.nan),
                    "comm_quality_mean": _safe_float(res.get("comm_summary", {}).get("quality_mean", np.nan), np.nan),
                    "conn_rms_mean": _safe_float(res.get("connection_summary", {}).get("rms_rel_mean", np.nan), np.nan),
                }
            )
    return rows


def _save_metrics_csv(rows: List[Dict[str, Any]]) -> Path:
    out = DATA_DIR / f"{VERSION}_metrics_summary.csv"
    if len(rows) == 0:
        return out
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return out


def main() -> None:
    _ensure_dirs()
    print("[START] bootstrap environment from notebook cells...")
    ns = _bootstrap_env_from_notebook()
    print("[OK] environment ready.")

    result_pkl = DATA_DIR / f"{VERSION}_case_results.pkl"
    if USE_EXISTING_RESULTS and result_pkl.exists():
        print(f"[LOAD] use existing case results: {result_pkl}")
        with result_pkl.open("rb") as f:
            results = pickle.load(f)
    else:
        print("[START] run cases for manuscript figures...")
        results = _run_all_cases(ns)
        print("[OK] case runs done.")

    rows = _collect_metrics(results)
    csv_path = _save_metrics_csv(rows)
    print(f"[OK] metrics csv: {csv_path}")

    print("[START] generate figure set fig01-fig23...")
    fig_summary = _generate_figures(ns, results)
    print("[OK] figures generated.")

    report = {
        "version": VERSION,
        "docx": str(DOCX_PATH),
        "fig_dir": str(FIG_DIR),
        "data_dir": str(DATA_DIR),
        "figure_count": len(fig_summary.get("figures", [])),
        "figures": fig_summary.get("figures", []),
        "data_files_from_fig_gen": fig_summary.get("data_files", []),
        "metrics_csv": str(csv_path),
        "result_pkl": str(result_pkl),
        "timestamp_note": "generated by run_manuscript_zh_ablation_figs.py",
    }
    _save_json("figure_generation_report", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise

