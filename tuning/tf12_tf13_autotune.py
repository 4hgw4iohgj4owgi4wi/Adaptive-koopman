import argparse
import json
import pathlib
import time
from copy import deepcopy
import sys

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_notebook(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _exec_cells(nb, cell_ids, env):
    for idx in cell_ids:
        cell = nb["cells"][idx]
        if cell.get("cell_type") != "code":
            continue
        src = "".join(cell.get("source", []))
        if not src.strip():
            continue
        exec(compile(src, f"<nb_cell_{idx}>", "exec"), env, env)


def bootstrap_tf12_env(disable_training=True):
    nb = _load_notebook(ROOT / "tf12_pre.ipynb")
    env = {"__name__": "__main__"}

    # 0-14 builds model + path + context helper.
    for idx in range(0, 15):
        cell = nb["cells"][idx]
        if cell.get("cell_type") != "code":
            continue
        src = "".join(cell.get("source", []))
        if not src.strip():
            continue
        exec(compile(src, f"<tf12_pre_cell_{idx}>", "exec"), env, env)
        if idx == 1 and disable_training:
            env["RUN_CFG"]["enable_koopman_training"] = False
            env["RUN_CFG"]["enable_koopman_linear_refit"] = True
            if "TF12_PLOT_CFG" in env and isinstance(env["TF12_PLOT_CFG"], dict):
                env["TF12_PLOT_CFG"]["show_figures"] = False
                env["TF12_PLOT_CFG"]["close_after_draw"] = True
    return env


def rebuild_path_library(env, mode, path_overrides=None):
    cfg = env["TF12_PATH_CFG"]
    if path_overrides:
        cfg.update(path_overrides)
    cfg["active_mode"] = str(mode).lower().strip()

    tf12_runtime = env["tf12_runtime"]
    payload_a1 = env["payload_a1"]
    A1_PAYLOAD_CFG = env["A1_PAYLOAD_CFG"]
    MPC_CFG = env["MPC_CFG"]
    RUN_CFG = env["RUN_CFG"]
    dt = float(env["dt"])
    vx_nom = float(env["vx_nom"])
    num_states = int(env["num_states"])

    TF12_PATH_LIBRARY = {}
    TF12_PATH_LIBRARY["dlc"] = env["_build_dlc_path"](
        path_length=float(MPC_CFG["path_length"]),
        vx_ref=vx_nom,
        dt_val=dt,
        enable_curved=bool(RUN_CFG["enable_curved_tracking"]),
    )
    if bool(cfg.get("build_hairpin", True)):
        v_h = float(np.clip(cfg.get("hairpin_ref_speed", 1.5), 0.8, vx_nom))
        TF12_PATH_LIBRARY["hairpin"] = env["_build_hairpin_path"](
            v_ref=v_h,
            dt_val=dt,
            payload_cfg=A1_PAYLOAD_CFG,
            mpc_cfg=MPC_CFG,
            path_cfg=cfg,
        )
    if cfg["active_mode"] not in TF12_PATH_LIBRARY:
        raise ValueError(f"mode={cfg['active_mode']} missing in path library")

    pack = TF12_PATH_LIBRARY[cfg["active_mode"]]
    env["TF12_PATH_LIBRARY"] = TF12_PATH_LIBRARY
    env["path_length"] = float(pack["path_length"])
    env["t_ref"] = pack["t_ref"]
    env["traj_length"] = int(pack["traj_length"])
    env["x_path"] = pack["x_path"]
    env["y_ref_path"] = pack["y_ref_path"]
    env["s_ref_path"] = pack["s_ref_path"]
    env["psi_ref_path"] = pack["psi_ref_path"]
    env["curvature_ref_path"] = pack["curvature_ref_path"]

    kappa_abs = np.abs(pack["curvature_ref_path"])
    if cfg["active_mode"] == "hairpin":
        v_cap = float(np.clip(cfg.get("hairpin_ref_speed", 1.5), 0.8, vx_nom))
        curv_gain = float(cfg.get("hairpin_speed_profile_gain", 12.0))
        v_min = float(cfg.get("hairpin_speed_min", 0.95))
    else:
        v_cap = float(np.clip(cfg.get("dlc_speed_cap", vx_nom), 0.8, vx_nom))
        curv_gain = float(MPC_CFG["speed_profile_curv_gain"])
        v_min = float(MPC_CFG["speed_profile_min"])
    vx_ref_profile = v_cap / (1.0 + curv_gain * kappa_abs)
    vx_ref_profile = np.clip(vx_ref_profile, max(0.65, v_min), v_cap)
    smooth_beta = float(np.clip(MPC_CFG["speed_profile_smooth"], 0.0, 0.98))
    for i in range(1, vx_ref_profile.size):
        vx_ref_profile[i] = smooth_beta * vx_ref_profile[i - 1] + (1.0 - smooth_beta) * vx_ref_profile[i]

    slow_start = float(MPC_CFG["terminal_slowdown_start_s"])
    slow_floor = float(np.clip(MPC_CFG["terminal_slowdown_floor"], 0.4, 1.0))
    if pack["s_ref_path"][-1] > slow_start:
        slow_ratio = np.clip(
            (pack["s_ref_path"] - slow_start) / max(pack["s_ref_path"][-1] - slow_start, 1e-6),
            0.0,
            1.0,
        )
        terminal_scale = 1.0 - (1.0 - slow_floor) * slow_ratio
        vx_ref_profile = np.clip(vx_ref_profile * terminal_scale, max(0.65, 0.85 * v_min), v_cap)

    x_ref_raw = np.zeros((num_states, int(pack["traj_length"])))
    x_ref_raw[0, :] = pack["s_ref_path"]
    x_ref_raw[1, :] = 0.0
    x_ref_raw[2, :] = 0.0
    x_ref_raw[3, :] = vx_ref_profile
    x_ref_raw[4, :] = 0.0
    x_ref_raw[5, :] = vx_ref_profile * pack["curvature_ref_path"]

    s_start_align_cfg = cfg.get("s_start_align", None)
    if s_start_align_cfg is None:
        s_start_align = float(env["x0_payload_center"][0])
    else:
        s_start_align = float(s_start_align_cfg)
    if abs(s_start_align) > 1e-12:
        x_ref_raw[0, :] = x_ref_raw[0, :] + s_start_align
        env["s_ref_path"] = env["s_ref_path"] + s_start_align

    env["x_ref_raw"] = x_ref_raw
    env["x_ref_scaled"] = env["standardizer_x_kdnn"].transform(x_ref_raw.T).T

    coord, ref_bundle = tf12_runtime.build_a1_reference_bundle(
        payload_module=payload_a1,
        payload_cfg=A1_PAYLOAD_CFG,
        standardizer_x=env["standardizer_x_kdnn"],
        x_ref_raw=x_ref_raw,
        leader_idx=env["FORMATION_CFG"]["leader_index"],
        horizon_pad=env["N_lin_noadapt"] + 2,
    )
    env["A1_COORDINATOR"] = coord
    env["A1_REF_BUNDLE"] = ref_bundle
    env["x_ref_raw_vehicles"] = ref_bundle["raw_vehicle_refs"]
    env["a1_ref_vehicle_histories"] = ref_bundle["corner_ref_histories"]
    env["x_ref_mpc_vehicles"] = ref_bundle["mpc_vehicle_refs"]
    return pack


def run_case(env, mode, method_overrides=None, path_overrides=None, tf13=False, name="case"):
    pack = rebuild_path_library(env, mode, path_overrides=path_overrides)

    ctx = env["build_a1_runtime_context"]()
    method_cfg = dict(ctx["METHOD_CFG"])
    if method_overrides:
        method_cfg.update(method_overrides)
    method_cfg["name"] = str(name)
    ctx["METHOD_CFG"] = method_cfg
    ctx["traj_length"] = int(pack["traj_length"])
    ctx["x_ref_raw"] = env["x_ref_raw"]
    ctx["s_ref_path"] = env["s_ref_path"]
    ctx["curvature_ref_path"] = env["curvature_ref_path"]
    ctx["A1_COORDINATOR"] = env["A1_COORDINATOR"]
    ctx["A1_REF_BUNDLE"] = env["A1_REF_BUNDLE"]

    t0 = time.perf_counter()
    if tf13:
        import tf13_runtime

        res = tf13_runtime.run_tf13_main(
            ctx,
            env["payload_a1"],
            env["A1_PAYLOAD_CFG"],
            env["A1_MAIN_CHANGE_MASK"],
        )
    else:
        res = env["tf12_runtime"].run_tf12_main(
            ctx,
            env["payload_a1"],
            env["A1_PAYLOAD_CFG"],
            env["A1_MAIN_CHANGE_MASK"],
        )
    elapsed = float(time.perf_counter() - t0)
    score = (
        (0.0 if bool(res.get("full_path_reached", False)) else 1e3)
        + max(float(res.get("max_lat_global", np.inf)), float(res.get("max_long_global", np.inf)))
        + 0.2 * (float(res.get("rmse_lat_mean", np.inf)) + float(res.get("rmse_long_mean", np.inf)))
        + 0.05 * float(res.get("step_time_mean", np.inf))
    )
    out = {
        "name": name,
        "mode": mode,
        "tf13": bool(tf13),
        "full_path": bool(res.get("full_path_reached", False)),
        "max_lat": float(res.get("max_lat_global", np.nan)),
        "max_long": float(res.get("max_long_global", np.nan)),
        "rmse_lat": float(res.get("rmse_lat_mean", np.nan)),
        "rmse_long": float(res.get("rmse_long_mean", np.nan)),
        "step_mean": float(res.get("step_time_mean", np.nan)),
        "sim_steps": int(res.get("sim_steps", -1)),
        "score": float(score),
        "elapsed": elapsed,
        "path_meta": pack.get("meta", {}),
        "result": res,
        "method_cfg": method_cfg,
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default="results/tuning/tf12_tf13_autotune_summary.json")
    args = ap.parse_args()

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    env = bootstrap_tf12_env(disable_training=True)

    # ---------- TF12 baseline ----------
    tf12_base_method = {
        "enforce_full_path": True,
        "completion_tol_s": 0.8,
        "max_extra_steps": 5000,
        "use_online_model_adaptation": True,
        "realtime_mode": True,
        "realtime_control_budget_sec": 0.014,
        "mpc_decimation_steps": 1,
        "min_solve_vehicles_per_step": 4,
        "mpc_skip_on_budget": False,
        "fast_time_limit": 6.0e-3,
        "fast_time_limit_min": 1.5e-3,
        "progress_lag_activate_s": 0.12,
        "progress_lag_full_s": 0.90,
        "progress_recover_ax_min": 0.20,
        "progress_recover_ax_max": 1.80,
    }

    tf12_candidates = [
        {
            "tag": "tf12_c0_current",
            "method": dict(tf12_base_method),
            "path_hairpin": {
                "hairpin_ref_speed": 1.50,
                "hairpin_speed_profile_gain": 12.0,
                "hairpin_speed_min": 0.95,
                "hairpin_ra_corner_r": 9.5,
            },
        },
        {
            "tag": "tf12_c1_slower",
            "method": {
                **tf12_base_method,
                "progress_recover_ax_min": 0.24,
                "progress_recover_ax_max": 1.55,
                "emergency_brake_ax": -0.55,
                "emergency_vx_cap": 2.8,
            },
            "path_hairpin": {
                "hairpin_ref_speed": 1.35,
                "hairpin_speed_profile_gain": 13.0,
                "hairpin_speed_min": 0.85,
                "hairpin_ra_corner_r": 10.5,
            },
        },
        {
            "tag": "tf12_c2_balance",
            "method": {
                **tf12_base_method,
                "progress_lag_activate_s": 0.18,
                "progress_lag_full_s": 1.10,
                "progress_recover_ax_min": 0.30,
                "progress_recover_ax_max": 1.45,
                "emergency_brake_ax": -0.48,
                "emergency_vx_cap": 3.0,
            },
            "path_hairpin": {
                "hairpin_ref_speed": 1.28,
                "hairpin_speed_profile_gain": 14.0,
                "hairpin_speed_min": 0.80,
                "hairpin_ra_corner_r": 11.5,
            },
        },
    ]

    tf12_runs = []
    for cand in tf12_candidates:
        for mode in ["dlc", "hairpin"]:
            path_over = cand["path_hairpin"] if mode == "hairpin" else {}
            run = run_case(
                env,
                mode=mode,
                method_overrides=cand["method"],
                path_overrides=path_over,
                tf13=False,
                name=f"{cand['tag']}_{mode}",
            )
            tf12_runs.append(run)
            print(
                f"[TF12] {run['name']}: full={run['full_path']} "
                f"max=({run['max_lat']:.4f},{run['max_long']:.4f}) "
                f"rmse=({run['rmse_lat']:.4f},{run['rmse_long']:.4f}) "
                f"step={run['step_mean']:.4f}s elapsed={run['elapsed']:.1f}s"
            )

    # select best candidate by sum score over both modes
    score_by_tag = {}
    for run in tf12_runs:
        tag = run["name"].rsplit("_", 1)[0]
        score_by_tag.setdefault(tag, 0.0)
        score_by_tag[tag] += run["score"]
    best_tf12_tag = min(score_by_tag, key=score_by_tag.get)
    best_tf12 = next(c for c in tf12_candidates if c["tag"] == best_tf12_tag)

    # ---------- TF13 tuning ----------
    tf13_base = {
        "enforce_full_path": True,
        "completion_tol_s": 1.0,
        "max_extra_steps": 5200,
        "realtime_mode": True,
        "realtime_control_budget_sec": 0.014,
        "min_solve_vehicles_per_step": 4,
        "mpc_skip_on_budget": False,
        "fast_time_limit": 6.0e-3,
        "fast_time_limit_min": 1.5e-3,
    }
    tf13_candidates = [
        {
            "tag": "tf13_c0_default_fault",
            "method": {
                **tf13_base,
                "enable_fault_tolerant_control": True,
                "fault_vehicle_index": 1,
                "fault_mode": "both",
                "fault_start_step": 80,
                "fault_start_s": 8.0,
                "fault_ax_scale": 0.45,
                "fault_delta_scale": 0.55,
                "fault_comp_gain": 0.90,
                "fault_comp_delta_clip": 0.035,
                "fault_comp_ax_clip": 0.38,
            },
        },
        {
            "tag": "tf13_c1_mid_fault",
            "method": {
                **tf13_base,
                "enable_fault_tolerant_control": True,
                "fault_vehicle_index": 1,
                "fault_mode": "both",
                "fault_start_step": 110,
                "fault_start_s": 10.0,
                "fault_ax_scale": 0.60,
                "fault_delta_scale": 0.70,
                "fault_comp_gain": 1.00,
                "fault_comp_delta_clip": 0.040,
                "fault_comp_ax_clip": 0.42,
            },
        },
        {
            "tag": "tf13_c2_mild_fault",
            "method": {
                **tf13_base,
                "enable_fault_tolerant_control": True,
                "fault_vehicle_index": 1,
                "fault_mode": "both",
                "fault_start_step": 140,
                "fault_start_s": 12.0,
                "fault_ax_scale": 0.72,
                "fault_delta_scale": 0.80,
                "fault_comp_gain": 1.05,
                "fault_comp_delta_clip": 0.045,
                "fault_comp_ax_clip": 0.45,
            },
        },
    ]

    tf13_runs = []
    for cand in tf13_candidates:
        for mode in ["dlc", "hairpin"]:
            # reuse tuned TF12 path profile for fairness and completion
            path_over = best_tf12["path_hairpin"] if mode == "hairpin" else {}
            run = run_case(
                env,
                mode=mode,
                method_overrides=cand["method"],
                path_overrides=path_over,
                tf13=True,
                name=f"{cand['tag']}_{mode}",
            )
            tf13_runs.append(run)
            fault_sum = run["result"].get("fault_summary", {})
            print(
                f"[TF13] {run['name']}: full={run['full_path']} "
                f"max=({run['max_lat']:.4f},{run['max_long']:.4f}) "
                f"rmse=({run['rmse_lat']:.4f},{run['rmse_long']:.4f}) "
                f"fault_active={fault_sum.get('active_steps', 0)} "
                f"elapsed={run['elapsed']:.1f}s"
            )

    score13 = {}
    for run in tf13_runs:
        tag = run["name"].rsplit("_", 1)[0]
        score13.setdefault(tag, 0.0)
        score13[tag] += run["score"]
    best_tf13_tag = min(score13, key=score13.get)
    best_tf13 = next(c for c in tf13_candidates if c["tag"] == best_tf13_tag)

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "best_tf12_tag": best_tf12_tag,
        "best_tf12_method": best_tf12["method"],
        "best_tf12_path_hairpin": best_tf12["path_hairpin"],
        "best_tf13_tag": best_tf13_tag,
        "best_tf13_method": best_tf13["method"],
        "tf12_runs": [
            {k: v for k, v in r.items() if k not in ("result", "method_cfg")}
            for r in tf12_runs
        ],
        "tf13_runs": [
            {k: v for k, v in r.items() if k not in ("result", "method_cfg")}
            for r in tf13_runs
        ],
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] summary -> {out_path}")


if __name__ == "__main__":
    main()
