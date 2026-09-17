import os
import pickle
import random
import time
import gc
from typing import Any, Dict

import numpy as np
import scipy

from control_files.a1_progress_supervisor_v2 import A1ProgressSupervisorV2
from control_files.rigid_payload_connection_compliance_a1_v1 import (
    RigidPayloadConnectionComplianceA1V1,
)
from control_files.rigid_payload_coordinator_a1 import RigidPayloadCoordinatorA1
from control_files.rigid_payload_stability_guard_a1_v2 import RigidPayloadStabilityGuardA1V2
from control_files.tf12.comm_quality_consensus import CommAwareConsensusTF12
from control_files.tf14 import (
    OnlineFDIMonitorTF14,
    PhaseRoleSchedulerTF14,
    ReconfigurableFTCControllerTF14,
    SwitchedFTCCertificateTF14,
    summarize_tf14_interactions,
)
try:
    from control_files.tf12.history_store import save_tf12_history_record
except Exception:
    save_tf12_history_record = None
from dynamics.learned_models_control.bilinear_dynamics import bilinear_Dynamics
from dynamics.learned_models_control.linear_dynamics import linear_Dynamics


def _retune_rigid_team_parameters_a1(team_pars, payload_cfg):
    team_out = dict(team_pars)
    vehicle_pars = [dict(v) for v in team_out.get("vehicle_pars_list", [])]
    if len(vehicle_pars) >= 4:
        half_l = 0.5 * float(payload_cfg["payload_length"])
        team_out["lf"] = half_l
        team_out["lr"] = half_l
        team_out["Cf"] = float(vehicle_pars[0]["Cf"]) + float(vehicle_pars[1]["Cf"])
        team_out["Cr"] = float(vehicle_pars[2]["Cr"]) + float(vehicle_pars[3]["Cr"])
    return team_out


def _infer_scenario_mode(method_cfg, result):
    for key in ("scenario_mode", "path_mode", "active_mode", "mode"):
        val = str(method_cfg.get(key, "")).strip().lower()
        if val:
            return val

    name = str(method_cfg.get("name", "")).strip().lower()
    if "hairpin" in name or "u_turn" in name or "uturn" in name:
        return "hairpin"
    if "sine" in name:
        return "sine"

    team_ref = np.asarray(result.get("ref_team_hist", []), dtype=float)
    if team_ref.ndim == 2 and team_ref.shape[0] > 4 and team_ref.shape[1] > 1:
        yy = team_ref[:, 1]
        yy = yy[np.isfinite(yy)]
        if yy.size > 0:
            y_span = float(np.max(yy) - np.min(yy))
            if y_span > 10.0:
                return "hairpin"
            if y_span <= 6.0:
                return "sine"
    return "unknown"


def _save_history_if_enabled(method_cfg, result):
    if save_tf12_history_record is None:
        return {"enabled": False, "reason": "history_store_unavailable"}

    enabled = bool(method_cfg.get("save_history", True))
    if not enabled:
        return {"enabled": False, "reason": "disabled_by_cfg"}

    scenario_mode = _infer_scenario_mode(method_cfg, result)
    case_name = str(method_cfg.get("history_case_name", result.get("case_name", "tf14_main")))
    root_dir = str(method_cfg.get("history_root_dir", "results/history/tf14"))
    try:
        save_info = save_tf12_history_record(
            result=result,
            method_cfg=method_cfg,
            case_name=case_name,
            scenario_mode=scenario_mode,
            root_dir=root_dir,
        )
        out = {
            "enabled": True,
            "scenario_mode": scenario_mode,
            "case_name": case_name,
            "root_dir": root_dir,
            "npz_path": str(save_info.get("npz_path", "")),
            "json_path": str(save_info.get("json_path", "")),
        }
        if bool(method_cfg.get("history_print_path", True)):
            print(f"[TF14][history] saved npz: {out['npz_path']}")
            print(f"[TF14][history] saved json: {out['json_path']}")
        return out
    except Exception as e:
        print(f"[TF14][history][WARN] save failed: {e}")
        return {
            "enabled": False,
            "reason": "save_failed",
            "error": str(e),
            "root_dir": root_dir,
        }


def _cfg_vector(value, length, default):
    if value is None:
        return np.full(int(length), float(default), dtype=float)
    arr = np.asarray(value, dtype=float).reshape(-1)
    if arr.size == 0:
        return np.full(int(length), float(default), dtype=float)
    if arr.size == 1:
        return np.full(int(length), float(arr[0]), dtype=float)
    out = np.full(int(length), float(default), dtype=float)
    n = min(int(length), int(arr.size))
    out[:n] = arr[:n]
    return out


def _cfg_jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [_cfg_jsonable(v) for v in value]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def _prefixed_cfg(method_cfg, prefix, suffix, default=None, fallback_prefix="comm_fault"):
    key = f"{prefix}_{suffix}"
    if key in method_cfg:
        return method_cfg.get(key)
    if fallback_prefix:
        fb_key = f"{fallback_prefix}_{suffix}"
        if fb_key in method_cfg:
            return method_cfg.get(fb_key)
    return default


def _tf14_channel_active(method_cfg, prefix, step_value, s_value, fallback_prefix="comm_fault"):
    mode = str(
        _prefixed_cfg(method_cfg, prefix, "trigger_mode", "step_and_s", fallback_prefix)
    ).lower().strip()
    start_step = int(max(0, _prefixed_cfg(method_cfg, prefix, "start_step", 0, fallback_prefix)))
    start_s = float(_prefixed_cfg(method_cfg, prefix, "start_s", 0.0, fallback_prefix))
    end_step_raw = _prefixed_cfg(method_cfg, prefix, "end_step", None, fallback_prefix)
    end_s_raw = _prefixed_cfg(method_cfg, prefix, "end_s", None, fallback_prefix)

    step_active = int(step_value) >= start_step
    s_active = float(s_value) >= start_s
    if end_step_raw is not None:
        step_active = step_active and int(step_value) <= int(end_step_raw)
    if end_s_raw is not None:
        s_active = s_active and float(s_value) <= float(end_s_raw)

    if mode in ("s", "distance", "path", "route", "progress"):
        return bool(s_active)
    if mode in ("step", "time", "k"):
        return bool(step_active)
    if mode in ("step_or_s", "step|s", "or"):
        return bool(step_active or s_active)
    return bool(step_active and s_active)


def _sample_delay_steps(method_cfg, prefix, rng, fallback_prefix=None):
    base = int(max(0, _prefixed_cfg(method_cfg, prefix, "delay_steps", 0, fallback_prefix)))
    var_min = int(
        max(0, _prefixed_cfg(method_cfg, prefix, "variable_delay_min_steps", 0, fallback_prefix))
    )
    var_max = int(
        max(0, _prefixed_cfg(method_cfg, prefix, "variable_delay_max_steps", 0, fallback_prefix))
    )
    if var_max < var_min:
        var_max = var_min
    if var_max > 0:
        base += int(rng.integers(var_min, var_max + 1))
    return int(base)


def _delay_range_steps(method_cfg, prefix, fallback_prefix=None):
    base = int(max(0, _prefixed_cfg(method_cfg, prefix, "delay_steps", 0, fallback_prefix)))
    var_min = int(
        max(0, _prefixed_cfg(method_cfg, prefix, "variable_delay_min_steps", 0, fallback_prefix))
    )
    var_max = int(
        max(0, _prefixed_cfg(method_cfg, prefix, "variable_delay_max_steps", 0, fallback_prefix))
    )
    if var_max < var_min:
        var_max = var_min
    return [int(base + var_min), int(base + var_max)]


def _apply_vector_channel(value, method_cfg, prefix, rng, active, fallback_prefix=None):
    arr = np.asarray(value, dtype=float).copy()
    if not active:
        return arr
    scale = _cfg_vector(
        _prefixed_cfg(method_cfg, prefix, "scale", 1.0, fallback_prefix), arr.size, 1.0
    ).reshape(arr.shape)
    bias = _cfg_vector(
        _prefixed_cfg(method_cfg, prefix, "bias", 0.0, fallback_prefix), arr.size, 0.0
    ).reshape(arr.shape)
    noise_std = _cfg_vector(
        _prefixed_cfg(method_cfg, prefix, "noise_std", 0.0, fallback_prefix), arr.size, 0.0
    ).reshape(arr.shape)
    noise = rng.normal(0.0, noise_std, size=arr.shape) if np.any(noise_std > 0.0) else 0.0
    return scale * arr + bias + noise


def _adjacent_vehicle_pairs(num_vehicles):
    pairs = []
    for receiver in range(int(num_vehicles)):
        neigh = []
        if receiver - 1 >= 0:
            neigh.append(receiver - 1)
        if receiver + 1 < int(num_vehicles):
            neigh.append(receiver + 1)
        pairs.append(tuple(neigh))
    return pairs


def generate_a1_dataset(
    *,
    run_cfg,
    koopman_cfg,
    set_global_seed_fn,
    payload_module,
    single_vehicle_data_gen_multi_fn,
    payload_cfg,
    subset_weights,
    dataset_tag,
):
    set_global_seed_fn(run_cfg["seed"], deterministic=koopman_cfg["deterministic_training"])

    num_states = 6
    num_inputs = 2
    dt = 0.02

    sys_pars_base = {
        "num_states": num_states,
        "num_inputs": num_inputs,
        "dt": dt,
        "m": 1500.0,
        "Iz": 2250.0,
        "lf": 1.2,
        "lr": 1.6,
        "Cf": 80000.0,
        "Cr": 80000.0,
        "curvature_ref": 0.0,
        "uncertainty": "NA",
        "amp": 0.0,
        "road_modes": ["sine"],
        "road_mode_probs": [1.0],
        "u_modes": ["feedback_dominant", "sinusoidal", "mixed"],
        "u_mode_probs": [0.40, 0.30, 0.30],
        "alpha_u": 0.70,
        "s_margin": 18.0,
        "seed": run_cfg["seed"],
        "payload_cfg": dict(payload_cfg),
        "variation_subset_weights": dict(subset_weights),
    }

    sys_pars_new_base = dict(sys_pars_base)
    sys_pars_new_base["m"] = 1650.0
    sys_pars_new_base["Iz"] = 2400.0
    sys_pars_new_base["Cf"] = 70000.0
    sys_pars_new_base["Cr"] = 70000.0

    sensor_noise = False
    snr_db = 30
    train_path_length_target = 60.0
    num_snaps = 1400
    configs = [
        {"vx_ref": 2.2, "delta_max": 0.34, "ax_max": 1.10, "freq": 2.2},
        {"vx_ref": 2.8, "delta_max": 0.32, "ax_max": 1.20, "freq": 2.0},
        {"vx_ref": 3.2, "delta_max": 0.30, "ax_max": 1.20, "freq": 1.8},
        {"vx_ref": 3.6, "delta_max": 0.28, "ax_max": 1.10, "freq": 1.6},
        {"vx_ref": 4.0, "delta_max": 0.25, "ax_max": 1.00, "freq": 1.4},
    ]

    num_traj_per_batch = 36
    x_list, x_changed_list, u_list = [], [], []
    variation_labels_all = []

    for cfg in configs:
        sp = dict(sys_pars_base)
        sp.update(cfg)
        sp["payload_cfg"] = dict(payload_cfg)
        sp["variation_subset_weights"] = dict(subset_weights)

        sp_new = dict(sys_pars_new_base)
        sp_new.update(cfg)
        sp_new["payload_cfg"] = dict(payload_cfg)
        sp_new["variation_subset_weights"] = dict(subset_weights)

        xb, xcb, ub = single_vehicle_data_gen_multi_fn(
            num_traj_per_batch, num_snaps, sp, sp_new, sensor_noise, snr_db
        )
        x_list.append(xb)
        x_changed_list.append(xcb)
        u_list.append(ub)
        variation_labels_all.extend(list(payload_module.LAST_VARIATION_LABELS))

    x = np.concatenate(x_list, axis=0)
    x_changed = np.concatenate(x_changed_list, axis=0)
    u = np.concatenate(u_list, axis=0)
    num_traj = x.shape[0]

    np.random.seed(run_cfg["seed"])
    random.seed(run_cfg["seed"])
    for i in range(num_traj):
        s_shift = np.random.uniform(0.0, 80.0)
        ey_shift = np.random.uniform(-2.0, 2.0)
        x[i, :, 0] += s_shift
        x_changed[i, :, 0] += s_shift
        x[i, :, 1] += ey_shift
        x_changed[i, :, 1] += ey_shift

    indices = np.random.permutation(num_traj)
    x = x[indices]
    x_changed = x_changed[indices]
    u = u[indices]
    variation_labels_all = [variation_labels_all[idx] for idx in indices]

    num_train = int(0.8 * num_traj)
    num_val = num_traj - num_train

    sys_pars = dict(sys_pars_base)
    sys_pars.update({"vx_ref": 3.0, "delta_max": 0.22, "ax_max": 1.0, "freq": 1.8})
    sys_pars["payload_cfg"] = dict(payload_cfg)
    sys_pars["variation_subset_weights"] = dict(subset_weights)

    sys_pars_new = dict(sys_pars_new_base)
    sys_pars_new.update({"vx_ref": 3.0, "delta_max": 0.22, "ax_max": 1.0, "freq": 1.8})
    sys_pars_new["payload_cfg"] = dict(payload_cfg)
    sys_pars_new["variation_subset_weights"] = dict(subset_weights)

    os.makedirs("saved_data/payload_team", exist_ok=True)
    dataset_npz = f"saved_data/payload_team/offline_dataset_{dataset_tag}.npz"
    dataset_pars = f"saved_data/payload_team/offline_dataset_pars_{dataset_tag}.pkl"

    np.savez_compressed(dataset_npz, X=x, X_changed=x_changed, U=u)
    with open(dataset_pars, "wb") as f:
        pickle.dump({
            "sys_pars": sys_pars,
            "sys_pars_new": sys_pars_new,
            "num_traj": num_traj,
            "num_train": num_train,
            "num_val": num_val,
            "num_snaps": num_snaps,
            "sensor_noise": sensor_noise,
            "SNR_DB": snr_db,
            "dataset_tag": dataset_tag,
            "train_path_length_target": train_path_length_target,
            "variation_summary": payload_module.variation_summary(variation_labels_all),
            "payload_cfg": dict(payload_cfg),
        }, f)

    os.makedirs("saved_data/single_vehicle", exist_ok=True)
    np.savez_compressed("saved_data/single_vehicle/offline_dataset.npz", X=x, X_changed=x_changed, U=u)
    with open("saved_data/single_vehicle/offline_dataset_pars.pkl", "wb") as f:
        pickle.dump({
            "sys_pars": sys_pars,
            "sys_pars_new": sys_pars_new,
            "num_traj": num_traj,
            "num_train": num_train,
            "num_val": num_val,
            "num_snaps": num_snaps,
            "sensor_noise": sensor_noise,
            "SNR_DB": snr_db,
            "dataset_tag": dataset_tag,
            "train_path_length_target": train_path_length_target,
            "variation_summary": payload_module.variation_summary(variation_labels_all),
            "payload_cfg": dict(payload_cfg),
        }, f)

    return {
        "X": x,
        "X_changed": x_changed,
        "U": u,
        "num_states": num_states,
        "num_inputs": num_inputs,
        "dt": dt,
        "sys_pars_base": sys_pars_base,
        "sys_pars_new_base": sys_pars_new_base,
        "sys_pars": sys_pars,
        "sys_pars_new": sys_pars_new,
        "sensor_noise": sensor_noise,
        "SNR_DB": snr_db,
        "train_path_length_target": train_path_length_target,
        "num_snaps": num_snaps,
        "num_traj": num_traj,
        "num_train": num_train,
        "num_val": num_val,
        "variation_labels_all": variation_labels_all,
        "variation_summary": payload_module.variation_summary(variation_labels_all),
        "dataset_npz": dataset_npz,
        "dataset_pars": dataset_pars,
    }


def build_a1_initial_states(payload_module, payload_cfg, vx_nom):
    x0_payload_center = np.array([
        0.5 * payload_cfg["payload_length"],
        0.0,
        0.0,
        vx_nom,
        0.0,
        0.0,
    ], dtype=float)
    formation_offsets = list(payload_cfg["corner_offsets"])
    x0_vehicles = [
        np.array(xv, dtype=float)
        for xv in payload_module.team_to_corner_states(x0_payload_center, payload_cfg=payload_cfg)
    ]
    return x0_payload_center, formation_offsets, x0_vehicles


def build_a1_reference_bundle(
    *,
    payload_module,
    payload_cfg,
    standardizer_x,
    x_ref_raw,
    leader_idx=0,
    horizon_pad=0,
):
    coordinator = RigidPayloadCoordinatorA1(
        payload_module=payload_module,
        payload_cfg=payload_cfg,
        leader_idx=leader_idx,
    )
    ref_bundle = coordinator.build_mpc_reference_bundle(
        x_ref_raw=x_ref_raw,
        standardizer_x=standardizer_x,
        horizon_pad=horizon_pad,
    )
    return coordinator, ref_bundle


def run_tf12_main(ctx, payload_module, payload_cfg, change_mask):
    method_cfg = dict(ctx["METHOD_CFG"])
    if method_cfg.get("adapt_cfg_overrides"):
        # Keep the default runtime unchanged, but allow strict baseline runs to
        # mirror a published adaptation rule without mutating the notebook state.
        ctx = dict(ctx)
        adapt_cfg = dict(ctx["ADAPT_CFG"])
        adapt_cfg.update(dict(method_cfg.get("adapt_cfg_overrides", {})))
        ctx["ADAPT_CFG"] = adapt_cfg
    method_cfg.setdefault("name", "tf14_fdi_ftc_bilinear_adaptive")
    method_cfg.setdefault("koopman_structure", "bilinear")
    method_cfg.setdefault("use_online_model_adaptation", True)
    method_cfg.setdefault("online_adaptation_mode", "bilinear_ridge")
    method_cfg.setdefault("use_comm_quality_consensus", True)
    method_cfg.setdefault("use_delay_compensation", True)
    method_cfg.setdefault("use_comm_constraint_tightening", True)
    method_cfg.setdefault("use_comm_degraded_fallback", True)
    method_cfg.setdefault("use_online_fdi", True)
    method_cfg.setdefault("use_online_fault_identification", True)
    method_cfg.setdefault("use_online_ftc_switching", True)
    method_cfg.setdefault("use_phase_role_scheduler", False)
    method_cfg.setdefault("tf14_certificate_enabled", True)
    method_cfg.setdefault("tf14_detect_hold_steps", 5)
    method_cfg.setdefault("tf14_release_hold_steps", 10)
    method_cfg.setdefault("tf14_residual_threshold", 0.85)
    method_cfg.setdefault("tf14_residual_cusum_threshold", 8.0)
    method_cfg.setdefault("tf14_ax_eff_fault_threshold", 0.78)
    method_cfg.setdefault("tf14_delta_eff_fault_threshold", 0.80)
    method_cfg.setdefault("tf14_severe_eff_threshold", 0.35)
    method_cfg.setdefault("tf14_switch_dwell_steps", 4)
    method_cfg.setdefault("tf14_switch_activation_confidence", 0.12)
    method_cfg.setdefault("tf14_switch_safe_confidence", 0.80)
    method_cfg.setdefault("tf14_redistribution_gain", 0.80)
    # Real-time acceleration defaults (keep all functions, prioritize timely output)
    method_cfg.setdefault("realtime_mode", True)
    method_cfg.setdefault("realtime_budget_ratio", 0.75)
    method_cfg.setdefault("realtime_control_budget_sec", 0.018)
    method_cfg.setdefault("vehicle_order_leader_first", True)
    method_cfg.setdefault("leader_always_solve", True)
    method_cfg.setdefault("mpc_decimation_steps", 5)
    method_cfg.setdefault("min_solve_vehicles_per_step", 2)
    method_cfg.setdefault("mpc_skip_on_budget", True)
    method_cfg.setdefault("mpc_min_budget_left_sec", 1.5e-3)
    method_cfg.setdefault("fast_max_sqp_iters", 1)
    method_cfg.setdefault("fast_time_limit", 8.0e-3)
    method_cfg.setdefault("fast_time_limit_min", 2.0e-3)
    method_cfg.setdefault("realtime_adapt_stride", 6)
    method_cfg.setdefault("realtime_disable_online_adapt", True)
    method_cfg.setdefault("realtime_disable_gc", True)
    method_cfg.setdefault("realtime_horizon", 12)
    method_cfg.setdefault("save_history", True)
    method_cfg.setdefault("history_root_dir", "results/history/tf14")
    method_cfg.setdefault("history_case_name", "tf14_main")
    method_cfg.setdefault("history_print_path", True)
    # TF13-ready (default OFF in TF12): fault-tolerant cooperative transport
    method_cfg.setdefault("enable_fault_tolerant_control", False)
    method_cfg.setdefault("fault_vehicle_index", 0)
    method_cfg.setdefault("fault_mode", "ax_limit")   # ax_limit | delta_limit | both
    method_cfg.setdefault("fault_trigger_mode", "step_and_s")
    method_cfg.setdefault("fault_start_step", 0)
    method_cfg.setdefault("fault_start_s", 0.0)
    method_cfg.setdefault("fault_ax_scale", 0.60)
    method_cfg.setdefault("fault_delta_scale", 0.60)
    method_cfg.setdefault("fault_ax_abs_limit", None)
    method_cfg.setdefault("fault_delta_abs_limit", None)
    method_cfg.setdefault("fault_tolerant_redistribution", True)
    method_cfg.setdefault("fault_comp_gain", 0.85)
    method_cfg.setdefault("fault_comp_delta_clip", 0.040)
    method_cfg.setdefault("fault_comp_ax_clip", 0.45)
    # New TF14 communication restructuring defaults are identity/no-op unless
    # comm_restructure_enabled is explicitly enabled by the case config.
    method_cfg.setdefault("comm_restructure_enabled", False)
    method_cfg.setdefault("comm_fault_trigger_mode", "step_and_s")
    method_cfg.setdefault("comm_fault_start_step", 0)
    method_cfg.setdefault("comm_fault_start_s", 0.0)
    method_cfg.setdefault("comm_fault_end_step", None)
    method_cfg.setdefault("comm_fault_end_s", None)
    method_cfg.setdefault("comm_relative_state_delay_steps", 0)
    method_cfg.setdefault("comm_relative_state_variable_delay_min_steps", 0)
    method_cfg.setdefault("comm_relative_state_variable_delay_max_steps", 0)
    method_cfg.setdefault("comm_relative_state_dropout_prob", 0.0)
    method_cfg.setdefault("comm_relative_state_noise_std", 0.0)
    method_cfg.setdefault("comm_relative_state_bias", 0.0)
    method_cfg.setdefault("comm_relative_state_scale", 1.0)
    method_cfg.setdefault("comm_relative_distance_noise_std", 0.0)
    method_cfg.setdefault("comm_relative_distance_bias", 0.0)
    method_cfg.setdefault("comm_relative_distance_scale", 1.0)
    method_cfg.setdefault("comm_team_ey_delay_steps", 0)
    method_cfg.setdefault("comm_team_ey_variable_delay_min_steps", 0)
    method_cfg.setdefault("comm_team_ey_variable_delay_max_steps", 0)
    method_cfg.setdefault("comm_team_ey_dropout_prob", 0.0)
    method_cfg.setdefault("comm_team_ey_noise_std", 0.0)
    method_cfg.setdefault("comm_team_ey_bias", 0.0)
    method_cfg.setdefault("comm_team_ey_scale", 1.0)
    method_cfg.setdefault("upper_lower_comm_enabled", True)
    method_cfg.setdefault("upper_lower_comm_delay_steps", 0)
    method_cfg.setdefault("upper_lower_comm_variable_delay_min_steps", 0)
    method_cfg.setdefault("upper_lower_comm_variable_delay_max_steps", 0)
    method_cfg.setdefault("upper_lower_comm_dropout_prob", 0.0)
    method_cfg.setdefault("upper_lower_comm_noise_std", 0.0)
    method_cfg.setdefault("upper_lower_comm_bias", 0.0)
    method_cfg.setdefault("upper_lower_comm_scale", 1.0)
    method_cfg.setdefault("upper_lower_comm_ref_delay_steps", 0)
    method_cfg.setdefault("upper_lower_comm_ref_variable_delay_min_steps", 0)
    method_cfg.setdefault("upper_lower_comm_ref_variable_delay_max_steps", 0)
    method_cfg.setdefault("upper_lower_comm_ref_dropout_prob", 0.0)
    method_cfg.setdefault("upper_lower_comm_ref_noise_std", 0.0)
    method_cfg.setdefault("upper_lower_comm_ref_bias", 0.0)
    method_cfg.setdefault("upper_lower_comm_ref_scale", 1.0)
    method_cfg.setdefault("adjacent_distance_control_enabled", False)
    method_cfg.setdefault("adjacent_distance_target_mode", "reference_initial")
    method_cfg.setdefault("adjacent_distance_k_s", 0.10)
    method_cfg.setdefault("adjacent_distance_k_ey", 0.025)
    method_cfg.setdefault("adjacent_distance_k_v", 0.04)
    method_cfg.setdefault("adjacent_distance_deadband_m", 0.03)
    method_cfg.setdefault("adjacent_distance_error_clip_m", 0.30)
    method_cfg.setdefault("adjacent_distance_ax_clip", 0.12)
    method_cfg.setdefault("adjacent_distance_delta_clip", 0.015)
    method_cfg.setdefault("adjacent_distance_filter_beta", 0.50)
    method_cfg.setdefault("adjacent_distance_min_comm_quality", 0.0)
    method_cfg.setdefault("temporary_path_preview_enabled", False)
    method_cfg.setdefault("temporary_path_preview_mode", "shift")
    method_cfg.setdefault("temporary_path_preview_trigger_mode", "s")
    method_cfg.setdefault("temporary_path_preview_start_step", 0)
    method_cfg.setdefault("temporary_path_preview_start_s", 0.0)
    method_cfg.setdefault("temporary_path_preview_end_step", None)
    method_cfg.setdefault("temporary_path_preview_end_s", None)
    method_cfg.setdefault("temporary_path_preview_index_mode", "k")
    method_cfg.setdefault("temporary_path_preview_s_lookup", "nearest")
    method_cfg.setdefault("temporary_path_preview_use_ref_s", False)
    method_cfg.setdefault("temporary_path_preview_base_offset_steps", 1)
    method_cfg.setdefault("temporary_path_preview_shift_steps", 0)
    method_cfg.setdefault("temporary_path_preview_max_shift_steps", None)
    method_cfg.setdefault("temporary_path_preview_max_candidate_shift_steps", None)
    method_cfg.setdefault("temporary_path_preview_lookahead_m", 0.0)
    method_cfg.setdefault("temporary_path_preview_min_lookahead_m", None)
    method_cfg.setdefault("temporary_path_preview_max_lookahead_m", None)
    method_cfg.setdefault("temporary_path_preview_blend_weight", 1.0)
    method_cfg.setdefault("temporary_path_preview_smooth_enabled", True)
    method_cfg.setdefault("temporary_path_preview_ramp_s", 0.0)
    method_cfg.setdefault("temporary_path_preview_path_modes", None)
    method_cfg.setdefault("temporary_path_preview_fourws_heading_enabled", False)
    method_cfg.setdefault("temporary_path_preview_fourws_heading_blend", 1.0)
    method_cfg.setdefault("temporary_path_preview_heading_scale", None)
    method_cfg.setdefault("temporary_path_preview_rear_steer_ratio", 0.0)
    method_cfg.setdefault("temporary_path_preview_fourws_optimizer_enabled", True)
    method_cfg.setdefault("temporary_path_preview_fourws_steering_logic", "anti_phase_angle_ratio")
    method_cfg.setdefault("temporary_path_preview_fourws_grid_refine_enabled", False)
    method_cfg.setdefault("temporary_path_preview_fourws_grid_refine_span_rad", 0.03)
    method_cfg.setdefault("temporary_path_preview_fourws_grid_refine_points", 5)
    method_cfg.setdefault("temporary_path_preview_fourws_curvature_weight", 1.0)
    method_cfg.setdefault("temporary_path_preview_fourws_sideslip_weight", 0.0)
    method_cfg.setdefault("temporary_path_preview_fourws_ratio_weight", 0.0)
    method_cfg.setdefault("temporary_path_preview_fourws_steer_weight", 0.0)
    method_cfg.setdefault("temporary_path_preview_front_delta_est_clip_rad", None)
    method_cfg.setdefault("temporary_path_preview_wheelbase_m", None)
    method_cfg.setdefault("temporary_path_preview_lf_m", None)
    method_cfg.setdefault("temporary_path_preview_lr_m", None)
    method_cfg.setdefault("temporary_path_preview_vehicle_offset_scale", 1.0)
    method_cfg.setdefault("temporary_path_preview_fourws_local_path_enabled", False)
    method_cfg.setdefault("temporary_path_preview_fourws_local_path_blend", 1.0)
    method_cfg.setdefault("temporary_path_preview_local_path_lateral_scale", None)
    method_cfg.setdefault("temporary_path_preview_local_path_heading_clip_rad", 0.45)
    method_cfg.setdefault("temporary_path_preview_local_path_max_lateral_m", 0.35)
    # Supplemental high-curvature tri-objective mode. It is off by default and
    # is enabled only by the hairpin supplement experiment.
    method_cfg.setdefault("force_aware_hairpin_switch_enabled", False)
    method_cfg.setdefault("force_aware_switch_path_modes", "hairpin")
    method_cfg.setdefault("force_aware_switch_use_ref_s", True)
    method_cfg.setdefault("force_aware_switch_start_s", 24.0)
    method_cfg.setdefault("force_aware_switch_end_s", 72.0)
    method_cfg.setdefault("force_aware_switch_ramp_s", 2.0)
    method_cfg.setdefault("force_aware_switch_kappa_threshold", 0.018)
    method_cfg.setdefault("force_aware_switch_curvature_exit_enabled", False)
    method_cfg.setdefault("force_aware_switch_kappa_full_threshold", None)
    method_cfg.setdefault("force_aware_switch_stateful_exit_enabled", False)
    method_cfg.setdefault("force_aware_switch_kappa_on_threshold", None)
    method_cfg.setdefault("force_aware_switch_kappa_off_threshold", None)
    method_cfg.setdefault("force_aware_switch_min_active_s", 0.0)
    method_cfg.setdefault("force_aware_switch_exit_fade_s", 2.0)
    method_cfg.setdefault("force_aware_switch_min_case_speed_mps", 4.5)
    method_cfg.setdefault("force_aware_switch_max_case_speed_mps", 5.5)
    method_cfg.setdefault("force_aware_q_ey_scale", 1.28)
    method_cfg.setdefault("force_aware_q_epsi_scale", 1.16)
    method_cfg.setdefault("force_aware_q_r_scale", 1.10)
    method_cfg.setdefault("force_aware_qn_ey_scale", 1.34)
    method_cfg.setdefault("force_aware_qn_epsi_scale", 1.20)
    method_cfg.setdefault("force_aware_qn_r_scale", 1.12)
    method_cfg.setdefault("force_aware_r_delta_scale", 1.32)
    method_cfg.setdefault("force_aware_r_ax_scale", 1.42)
    method_cfg.setdefault("force_aware_delta_alpha", None)
    method_cfg.setdefault("force_aware_command_spread_suppression", 0.38)
    method_cfg.setdefault("force_aware_team_blend", 0.42)
    method_cfg.setdefault("force_aware_delta_abs_limit", None)
    method_cfg.setdefault("force_aware_ax_min", None)
    method_cfg.setdefault("force_aware_ax_max", None)
    method_cfg.setdefault("force_aware_delta_rate_limit", None)
    method_cfg.setdefault("force_aware_ax_rate_limit", None)
    method_cfg.setdefault("force_aware_speed_target_mps", None)
    method_cfg.setdefault("force_aware_speed_ax_gain", 0.0)
    method_cfg.setdefault("force_aware_speed_ax_clip", 0.0)

    structure_name = method_cfg.get("koopman_structure", "bilinear").lower().strip()
    traj_length = ctx["traj_length"]
    sim_steps_nominal = traj_length - 1
    enforce_full_path = bool(method_cfg.get("enforce_full_path", True))
    completion_tol_s = float(method_cfg.get("completion_tol_s", 0.8))
    max_extra_steps = int(method_cfg.get("max_extra_steps", 0))
    sim_steps_cap = sim_steps_nominal + (max_extra_steps if enforce_full_path else 0)

    realtime_mode = bool(method_cfg.get("realtime_mode", True))
    n_case = int(method_cfg.get("horizon", ctx["N_lin_noadapt"]))
    if realtime_mode:
        n_case = min(n_case, int(max(8, method_cfg.get("realtime_horizon", 14))))
    n_case = max(8, min(n_case, ctx["N_lin_noadapt"]))
    max_iter_case = int(method_cfg.get("max_sqp_iters", ctx["max_iter_lin"]))
    max_iter_case = max(1, max_iter_case)
    use_rigid_coord_correction = bool(method_cfg.get("use_rigid_coord_correction", False))

    use_ppc = bool(method_cfg.get("use_ppc", True))
    use_dynamic_ppc = bool(method_cfg.get("use_dynamic_ppc", True))
    use_adaptive_weight = bool(method_cfg.get("use_adaptive_weight", True))
    use_online_adapt = bool(method_cfg.get("use_online_model_adaptation", True))
    if realtime_mode and bool(method_cfg.get("realtime_disable_online_adapt", True)):
        use_online_adapt = False
    use_team_stability_guard = bool(method_cfg.get("use_team_stability_guard", True))
    use_progress_supervisor = bool(method_cfg.get("use_progress_supervisor", True))
    use_legacy_hard_brake = bool(method_cfg.get("use_legacy_hard_brake", False))
    use_connection_compliance = bool(method_cfg.get("use_connection_compliance", True))
    plant_mode = str(method_cfg.get("plant_mode", "equivalent_bicycle")).lower().strip()
    if plant_mode not in ("equivalent_bicycle", "four_vehicle_coupled"):
        raise ValueError(f"unsupported plant_mode={plant_mode!r}")
    use_coupled_plant = plant_mode == "four_vehicle_coupled"
    use_comm_quality_consensus = bool(method_cfg.get("use_comm_quality_consensus", True))
    use_delay_compensation = bool(method_cfg.get("use_delay_compensation", True))
    use_comm_constraint_tightening = bool(method_cfg.get("use_comm_constraint_tightening", True))
    use_comm_degraded_fallback = bool(method_cfg.get("use_comm_degraded_fallback", True))
    enable_emergency_progress_override = bool(
        method_cfg.get("enable_emergency_progress_override", True)
    )
    enable_fault_tolerant_control = bool(method_cfg.get("enable_fault_tolerant_control", False))
    fault_vehicle_index = int(method_cfg.get("fault_vehicle_index", 0))
    fault_mode = str(method_cfg.get("fault_mode", "ax_limit")).lower().strip()
    fault_trigger_mode = str(method_cfg.get("fault_trigger_mode", "step_and_s")).lower().strip()
    fault_start_step = int(max(0, method_cfg.get("fault_start_step", 0)))
    fault_start_s = float(method_cfg.get("fault_start_s", 0.0))
    fault_ax_scale = float(np.clip(method_cfg.get("fault_ax_scale", 0.55), 0.0, 1.0))
    fault_delta_scale = float(np.clip(method_cfg.get("fault_delta_scale", 0.60), 0.0, 1.0))
    fault_ax_abs_limit = method_cfg.get("fault_ax_abs_limit", None)
    fault_delta_abs_limit = method_cfg.get("fault_delta_abs_limit", None)
    fault_tolerant_redistribution = bool(method_cfg.get("fault_tolerant_redistribution", True))
    fault_comp_gain = float(max(0.0, method_cfg.get("fault_comp_gain", 0.85)))
    fault_comp_delta_clip = float(max(0.0, method_cfg.get("fault_comp_delta_clip", 0.040)))
    fault_comp_ax_clip = float(max(0.0, method_cfg.get("fault_comp_ax_clip", 0.45)))
    use_online_fdi = bool(method_cfg.get("use_online_fdi", True))
    use_online_fault_identification = bool(method_cfg.get("use_online_fault_identification", True))
    use_online_ftc_switching = bool(method_cfg.get("use_online_ftc_switching", True))
    use_phase_role_scheduler = bool(method_cfg.get("use_phase_role_scheduler", False))
    use_tf14_certificate = bool(method_cfg.get("tf14_certificate_enabled", True))
    use_comm_restructure = bool(method_cfg.get("comm_restructure_enabled", False))
    use_upper_lower_comm = use_comm_restructure and bool(method_cfg.get("upper_lower_comm_enabled", True))
    use_adjacent_distance_control = bool(
        method_cfg.get("adjacent_distance_control_enabled", False)
    )
    adjacent_distance_target_mode = str(
        method_cfg.get("adjacent_distance_target_mode", "reference_initial")
    ).lower().strip()
    use_temporary_path_preview = bool(method_cfg.get("temporary_path_preview_enabled", False))
    temporary_path_preview_mode = str(method_cfg.get("temporary_path_preview_mode", "shift")).lower().strip()
    temporary_path_preview_use_ref_s = bool(method_cfg.get("temporary_path_preview_use_ref_s", False))
    suite_path_mode = str(method_cfg.get("suite_path_mode", method_cfg.get("path_mode", ""))).lower().strip()
    if bool(method_cfg.get("print_runtime_flags", True)):
        print(
            "[TF14] runtime_flags: "
            f"team_guard={use_team_stability_guard}, "
            f"progress_supervisor={use_progress_supervisor}, "
            f"connection_compliance={use_connection_compliance}, "
            f"plant_mode={plant_mode}, "
            f"comm_quality_consensus={use_comm_quality_consensus}, "
            f"delay_comp={use_delay_compensation}, "
            f"tightening={use_comm_constraint_tightening}, "
            f"degraded_fb={use_comm_degraded_fallback}, "
            f"fault_tolerant={enable_fault_tolerant_control}, "
            f"online_fdi={use_online_fdi}, "
            f"online_ident={use_online_fault_identification}, "
            f"switching={use_online_ftc_switching}, "
            f"phase_role={use_phase_role_scheduler}, "
            f"comm_restructure={use_comm_restructure}, "
            f"upper_lower_comm={use_upper_lower_comm}, "
            f"adjacent_distance_control={use_adjacent_distance_control}, "
            f"legacy_hard_brake={use_legacy_hard_brake}, "
            f"emergency_progress_override={enable_emergency_progress_override}"
        )

    model_pack = ctx["get_tf9_model_pack"](method_cfg)
    if structure_name == "bilinear" and model_pack["bilinear_ready"]:
        a_case = model_pack["A_bilinear"]
        b_case = model_pack["B_bilinear"]
        c_case = model_pack["C_linear"]
        dynamics_obj = bilinear_Dynamics(
            scipy.sparse.csc_matrix(a_case),
            scipy.sparse.csc_matrix(b_case),
            c_case,
        )
        print("[TF12] Using bilinear Koopman dynamics")
        if model_pack["bilinear_info"] is not None:
            print("[TF12] Bilinear fit RMSE:", model_pack["bilinear_info"])
    else:
        structure_name = "linear"
        a_case = model_pack["A_linear"]
        b_case = model_pack["B_linear"]
        c_case = model_pack["C_linear"]
        dynamics_obj = linear_Dynamics(
            scipy.sparse.csc_matrix(a_case),
            scipy.sparse.csc_matrix(b_case),
            c_case,
        )
        print("[TF12][WARN] Bilinear model unavailable, fallback to linear.")

    def lift_fn(x_raw):
        x_scaled = ctx["scale_state"](x_raw, ctx["standardizer_x_kdnn"])
        return ctx["lift_scaled"](x_scaled, ctx["model_koop_dnn_lin"], ctx["net_params_lin"])

    num_vehicles = ctx["num_vehicles"]
    num_states = ctx["num_states"]
    num_inputs = ctx["num_inputs"]
    traj_alloc = sim_steps_cap + 1
    nz_case = int(a_case.shape[0])

    xt_case = [np.zeros((traj_alloc, num_states)) for _ in range(num_vehicles)]
    u_case = [np.zeros((sim_steps_cap, num_inputs)) for _ in range(num_vehicles)]
    z_case = [np.zeros((traj_alloc, nz_case)) for _ in range(num_vehicles)]

    team_state_hist = np.zeros((traj_alloc, num_states))
    team_input_hist = np.zeros((sim_steps_cap, num_inputs))
    payload_force_hist = []
    control_spread_hist = []
    connection_diag_hist = []
    comm_diag_hist = []
    comm_perception_diag_hist = []
    upper_lower_comm_diag_hist = []
    adjacent_distance_control_diag_hist = []
    temporary_path_preview_diag_hist = []
    fault_diag_hist = []
    tf14_fdi_diag_hist = []
    tf14_switch_diag_hist = []
    tf14_certificate_hist = []
    phase_role_diag_hist = []

    coupled_state_hist = np.zeros((traj_alloc, 30), dtype=float) if use_coupled_plant else None
    coupled_control_hist = np.zeros((sim_steps_cap, 4, 2), dtype=float) if use_coupled_plant else None
    coupled_alloc_diag_hist = []
    coupled_path = None
    coupled_params = None
    coupled_cfg = None
    coupled_state = None
    if use_coupled_plant:
        import sys

        coupled_model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "revision_2026", "model")
        if coupled_model_dir not in sys.path:
            sys.path.insert(0, coupled_model_dir)
        from adapter import (
            CoupledAdapterConfig,
            FrenetMap,
            advance_joint_state,
            frenet_states,
            initialize_joint_state,
            physical_history_row,
            summarize_physical_history,
        )
        from four_vehicle_coupled import ModelParams

        coupled_path = FrenetMap(ctx["s_ref_path"], ctx["curvature_ref_path"])
        coupled_params = ModelParams()
        coupled_cfg = CoupledAdapterConfig(
            substep_s=float(method_cfg.get("coupled_substep_s", 0.002)),
            virtual_front_scale=float(method_cfg.get("coupled_virtual_front_scale", 2.0 / 3.0)),
            virtual_rear_ratio=float(method_cfg.get("coupled_virtual_rear_ratio", -0.5)),
            heading_gain=float(method_cfg.get("coupled_heading_gain", 2.0)),
            speed_gain=float(method_cfg.get("coupled_speed_gain", 0.8)),
            max_vehicle_steering_deg=float(method_cfg.get("coupled_max_vehicle_steering_deg", 15.0)),
            max_zero_sum_accel_mps2=float(method_cfg.get("coupled_max_zero_sum_accel_mps2", 0.8)),
        )

    connection_model = RigidPayloadConnectionComplianceA1V1(
        dt=ctx["dt"],
        num_vehicles=num_vehicles,
        enabled=use_connection_compliance and (not use_coupled_plant),
        max_rel_s=method_cfg.get("conn_max_rel_s", 0.070),
        max_rel_ey=method_cfg.get("conn_max_rel_ey", 0.070),
        max_rel_psi=method_cfg.get("conn_max_rel_psi", 0.035),
        max_rel_vs=method_cfg.get("conn_max_rel_vs", 0.32),
        max_rel_vey=method_cfg.get("conn_max_rel_vey", 0.32),
        max_rel_r=method_cfg.get("conn_max_rel_r", 0.22),
        k_s=method_cfg.get("conn_k_s", 5.6),
        c_s=method_cfg.get("conn_c_s", 3.8),
        k_ey=method_cfg.get("conn_k_ey", 6.6),
        c_ey=method_cfg.get("conn_c_ey", 4.2),
        k_psi=method_cfg.get("conn_k_psi", 5.0),
        c_psi=method_cfg.get("conn_c_psi", 3.4),
        gain_ax=method_cfg.get("conn_gain_ax", 0.20),
        gain_delta_ey=method_cfg.get("conn_gain_delta_ey", 0.58),
        gain_delta_psi=method_cfg.get("conn_gain_delta_psi", 0.36),
        gain_r_psi=method_cfg.get("conn_gain_r_psi", 0.08),
    )
    connection_model.reset()

    x0_vehicles = ctx["x0_vehicles"]
    x0_team = payload_module.corner_states_to_team_state(np.vstack(x0_vehicles), payload_cfg=payload_cfg)
    if use_coupled_plant:
        coupled_state = initialize_joint_state(x0_team, coupled_path, coupled_params)
        coupled_state_hist[0, :] = coupled_state
        init_local_states, x0_team_physical = frenet_states(coupled_state, coupled_path)
        team_state_hist[0, :] = x0_team_physical
    else:
        team_state_hist[0, :] = x0_team
        init_local_states = connection_model.corner_states_from_team(
            x0_team, payload_module, payload_cfg
        )
    for v in range(num_vehicles):
        xt_case[v][0, :] = init_local_states[v]
        z_case[v][0, :] = lift_fn(init_local_states[v])

    ref_needed_cols = sim_steps_cap + n_case + 2
    ref_pad = max(0, ref_needed_cols - ctx["x_ref_raw"].shape[1])
    coordinator = ctx.get("A1_COORDINATOR")
    ref_bundle = ctx.get("A1_REF_BUNDLE")
    need_rebuild_ref = (
        coordinator is None
        or ref_bundle is None
        or "mpc_vehicle_refs" not in ref_bundle
        or any(ref_v.shape[1] < ref_needed_cols for ref_v in ref_bundle["mpc_vehicle_refs"])
    )
    if need_rebuild_ref:
        coordinator, ref_bundle = build_a1_reference_bundle(
            payload_module=payload_module,
            payload_cfg=payload_cfg,
            standardizer_x=ctx["standardizer_x_kdnn"],
            x_ref_raw=ctx["x_ref_raw"],
            leader_idx=ctx["leader_idx"],
            horizon_pad=ref_pad,
        )
    x_ref_case_vehicles = ref_bundle["mpc_vehicle_refs"]
    raw_ref_vehicle_hist = ref_bundle["corner_ref_histories"]

    solver_settings_case = dict(ctx["solver_settings"])
    if method_cfg.get("time_limit", None) is not None:
        solver_settings_case["time_limit"] = float(method_cfg["time_limit"])

    def _scaled_sparse_diagonal(base_mat, index_to_key):
        diag = np.asarray(base_mat.diagonal(), dtype=float).copy()
        for idx, key in index_to_key.items():
            if key in method_cfg and 0 <= int(idx) < diag.size:
                diag[int(idx)] *= float(method_cfg.get(key, 1.0))
        return scipy.sparse.diags(diag, offsets=0, format="dia")

    def _scaled_sparse_diagonal_runtime(base_mat, index_to_scale):
        diag = np.asarray(base_mat.diagonal(), dtype=float).copy()
        for idx, scale in index_to_scale.items():
            if 0 <= int(idx) < diag.size:
                diag[int(idx)] *= float(scale)
        return scipy.sparse.diags(diag, offsets=0, format="dia")

    def _windowed_mpc_active(s_value: float, curvature_value: float) -> bool:
        if not bool(method_cfg.get("windowed_mpc_weight_enabled", False)):
            return False
        start_s = float(method_cfg.get("windowed_mpc_start_s", -np.inf))
        end_s = float(method_cfg.get("windowed_mpc_end_s", np.inf))
        threshold = float(method_cfg.get("windowed_mpc_kappa_threshold", 0.0))
        return start_s <= float(s_value) <= end_s and abs(float(curvature_value)) >= threshold

    def _path_mode_allowed(allowed_modes) -> bool:
        if allowed_modes is None or allowed_modes == "":
            return True
        if isinstance(allowed_modes, str):
            modes = [item.strip().lower() for item in allowed_modes.split(",")]
        elif isinstance(allowed_modes, (list, tuple, set)):
            modes = [str(item).strip().lower() for item in allowed_modes]
        else:
            return True
        modes = [item for item in modes if item]
        if not modes:
            return True
        return suite_path_mode in modes

    def _fault_trigger_active(step_value: int, s_value: float) -> bool:
        step_active = int(step_value) >= fault_start_step
        s_active = float(s_value) >= fault_start_s
        if fault_trigger_mode in ("s", "distance", "path", "route", "progress"):
            return s_active
        if fault_trigger_mode in ("step", "time", "k"):
            return step_active
        return step_active and s_active

    def _critical_lateral_priority_active(step_value: int, s_value: float, curvature_value: float, ey_value: float, fault_active: bool) -> bool:
        if not bool(method_cfg.get("critical_lateral_priority_enabled", False)):
            return False
        if bool(method_cfg.get("critical_lateral_priority_fault_required", True)) and not bool(fault_active):
            return False
        start_s = float(method_cfg.get("critical_lateral_priority_start_s", -np.inf))
        end_s = float(method_cfg.get("critical_lateral_priority_end_s", np.inf))
        threshold = float(method_cfg.get("critical_lateral_priority_kappa_threshold", 0.0))
        ey_threshold = float(method_cfg.get("critical_lateral_priority_ey_threshold", 0.0))
        return (
            start_s <= float(s_value) <= end_s
            and abs(float(curvature_value)) >= threshold
            and abs(float(ey_value)) >= ey_threshold
            and _fault_trigger_active(step_value, s_value)
        )

    def _smooth_step01(value: float) -> float:
        x = float(np.clip(value, 0.0, 1.0))
        return x * x * (3.0 - 2.0 * x)

    def _smooth_box_gain(s_value: float, start_s: float, end_s: float, ramp_s: float) -> float:
        if float(s_value) < start_s or float(s_value) > end_s:
            return 0.0
        ramp = max(float(ramp_s), 1e-6)
        up = _smooth_step01((float(s_value) - start_s) / ramp)
        down = _smooth_step01((end_s - float(s_value)) / ramp)
        return float(min(up, down, 1.0))

    force_aware_switch_state = {
        "latched": False,
        "entry_s": np.nan,
        "exit_s": np.nan,
    }

    def _force_aware_switch_profile(s_value: float, curvature_value: float) -> Dict[str, Any]:
        if not bool(method_cfg.get("force_aware_hairpin_switch_enabled", False)):
            return {"active": False, "gain": 0.0, "s_ref": float(s_value), "curvature": float(curvature_value)}
        if not _path_mode_allowed(method_cfg.get("force_aware_switch_path_modes", "hairpin")):
            return {"active": False, "gain": 0.0, "s_ref": float(s_value), "curvature": float(curvature_value)}
        case_speed = float(method_cfg.get("speed_cap_mps", np.nan))
        min_case_speed = float(method_cfg.get("force_aware_switch_min_case_speed_mps", -np.inf))
        max_case_speed = float(method_cfg.get("force_aware_switch_max_case_speed_mps", np.inf))
        if np.isfinite(case_speed) and not (min_case_speed <= case_speed <= max_case_speed):
            return {"active": False, "gain": 0.0, "s_ref": float(s_value), "curvature": float(curvature_value)}
        start_s = float(method_cfg.get("force_aware_switch_start_s", -np.inf))
        end_s = float(method_cfg.get("force_aware_switch_end_s", np.inf))
        threshold = float(method_cfg.get("force_aware_switch_kappa_threshold", 0.0))
        if not (start_s <= float(s_value) <= end_s):
            return {"active": False, "gain": 0.0, "s_ref": float(s_value), "curvature": float(curvature_value)}
        abs_kappa = abs(float(curvature_value))
        if bool(method_cfg.get("force_aware_switch_stateful_exit_enabled", False)):
            on_cfg = method_cfg.get("force_aware_switch_kappa_on_threshold", None)
            off_cfg = method_cfg.get("force_aware_switch_kappa_off_threshold", None)
            on_threshold = threshold if on_cfg is None else float(on_cfg)
            off_threshold = threshold if off_cfg is None else min(float(off_cfg), on_threshold)
            min_active_s = max(float(method_cfg.get("force_aware_switch_min_active_s", 0.0)), 0.0)
            exit_fade_s = max(float(method_cfg.get("force_aware_switch_exit_fade_s", 2.0)), 1e-6)
            state_gain = 0.0
            if not bool(force_aware_switch_state["latched"]):
                if abs_kappa < on_threshold:
                    return {"active": False, "gain": 0.0, "s_ref": float(s_value), "curvature": float(curvature_value)}
                force_aware_switch_state["latched"] = True
                force_aware_switch_state["entry_s"] = float(s_value)
                force_aware_switch_state["exit_s"] = np.nan
            entry_s = float(force_aware_switch_state["entry_s"])
            exit_s = float(force_aware_switch_state["exit_s"])
            if not np.isfinite(exit_s):
                min_active_done = (float(s_value) - entry_s) >= min_active_s
                if min_active_done and abs_kappa <= off_threshold:
                    force_aware_switch_state["exit_s"] = float(s_value)
                    exit_s = float(s_value)
            if np.isfinite(exit_s):
                state_gain = 1.0 - _smooth_step01((float(s_value) - exit_s) / exit_fade_s)
            else:
                state_gain = 1.0
            gain = _smooth_box_gain(
                float(s_value),
                start_s,
                end_s,
                float(method_cfg.get("force_aware_switch_ramp_s", 2.0)),
            )
            gain *= float(np.clip(state_gain, 0.0, 1.0))
            return {
                "active": bool(gain > 1e-9),
                "gain": float(gain),
                "s_ref": float(s_value),
                "curvature": float(curvature_value),
            }
        if bool(method_cfg.get("force_aware_switch_curvature_exit_enabled", False)):
            full_threshold_cfg = method_cfg.get("force_aware_switch_kappa_full_threshold", None)
            if full_threshold_cfg is None:
                full_threshold = max(threshold * 1.75, threshold + 1e-6)
            else:
                full_threshold = max(float(full_threshold_cfg), threshold + 1e-6)
            if abs_kappa <= threshold:
                return {"active": False, "gain": 0.0, "s_ref": float(s_value), "curvature": float(curvature_value)}
            curvature_gain = _smooth_step01((abs_kappa - threshold) / (full_threshold - threshold))
        else:
            if abs_kappa < threshold:
                return {"active": False, "gain": 0.0, "s_ref": float(s_value), "curvature": float(curvature_value)}
            curvature_gain = 1.0
        gain = _smooth_box_gain(
            float(s_value),
            start_s,
            end_s,
            float(method_cfg.get("force_aware_switch_ramp_s", 2.0)),
        )
        gain *= float(curvature_gain)
        return {
            "active": bool(gain > 1e-9),
            "gain": float(gain),
            "s_ref": float(s_value),
            "curvature": float(curvature_value),
        }

    def _slice_ref_window_padded(ref_mat, start_col: int, width: int):
        ref_arr = np.asarray(ref_mat, dtype=float)
        width = int(max(0, width))
        if ref_arr.ndim != 2 or width <= 0:
            return ref_arr[:, :0].copy(), 0, 0, 0
        rows, total_cols = ref_arr.shape
        if total_cols <= 0:
            return np.zeros((rows, width), dtype=float), 0, width, 0

        start_col = int(start_col)
        end_col = start_col + width
        leading_pad = int(min(width, max(0, -start_col)))
        main_start = max(0, start_col)
        main_end = min(total_cols, end_col)
        main_width = int(max(0, main_end - main_start))
        main_width = int(min(main_width, max(0, width - leading_pad)))
        terminal_pad = int(max(0, width - leading_pad - main_width))
        raw_terminal_pad = int(max(0, end_col - total_cols))
        terminal_overshoot = int(max(0, raw_terminal_pad - terminal_pad))
        pieces = []
        if leading_pad > 0:
            pieces.append(np.repeat(ref_arr[:, 0:1], leading_pad, axis=1))
        if main_width > 0:
            pieces.append(ref_arr[:, main_start:main_start + main_width])
        if terminal_pad > 0:
            pieces.append(np.repeat(ref_arr[:, -1:], terminal_pad, axis=1))
        if pieces:
            out = np.concatenate(pieces, axis=1)
        else:
            out = np.repeat(ref_arr[:, -1:], width, axis=1)
        if out.shape[1] < width:
            pad_cols = width - out.shape[1]
            terminal_pad += pad_cols
            out = np.concatenate([out, np.repeat(ref_arr[:, -1:], pad_cols, axis=1)], axis=1)
        elif out.shape[1] > width:
            out = out[:, :width]
        terminal_pad = int(min(width, terminal_pad))
        return out.copy(), int(leading_pad), int(terminal_pad), int(terminal_overshoot)

    def _temporary_path_preview_explicit_s_grid(vehicle_index, n_cols):
        grid_keys = (
            "temporary_path_preview_s_grid",
            "temporary_path_preview_s_grids",
            "temporary_path_preview_ref_s_grid",
            "temporary_path_preview_ref_s_grids",
        )
        grid_cfg = None
        for key in grid_keys:
            if method_cfg.get(key, None) is not None:
                grid_cfg = method_cfg.get(key)
                break
        if grid_cfg is None:
            return None, False, "not_configured"
        try:
            grid_arr = np.asarray(grid_cfg, dtype=float)
        except (TypeError, ValueError):
            return None, True, "non_numeric"
        if grid_arr.ndim == 0:
            return None, True, "scalar"
        if grid_arr.ndim == 1:
            grid = grid_arr.reshape(-1)
        elif grid_arr.ndim == 2:
            vehicle_idx = int(np.clip(int(vehicle_index), 0, max(0, num_vehicles - 1)))
            if grid_arr.shape[0] == num_vehicles:
                grid = grid_arr[vehicle_idx, :].reshape(-1)
            elif grid_arr.shape[1] == num_vehicles:
                grid = grid_arr[:, vehicle_idx].reshape(-1)
            elif grid_arr.shape[0] == 1:
                grid = grid_arr[0, :].reshape(-1)
            else:
                return None, True, "shape_mismatch"
        else:
            return None, True, "rank_gt_2"
        if n_cols > 0:
            grid = grid[:int(n_cols)]
        finite_idx = np.flatnonzero(np.isfinite(grid))
        if finite_idx.size <= 0:
            return None, True, "no_finite_values"
        finite_s = grid[finite_idx]
        if finite_s.size > 1 and not np.all(np.diff(finite_s) >= -1e-9):
            return None, True, "not_monotone_increasing"
        return (grid, finite_idx), True, "ok"

    def _temporary_path_preview_prepare_physical_s_grid(grid_like, n_cols):
        try:
            grid = np.asarray(grid_like, dtype=float).reshape(-1)
        except (TypeError, ValueError):
            return None, "non_numeric"
        if grid.size <= 0:
            return None, "empty"
        if n_cols > 0:
            grid = grid[:int(n_cols)]
        finite_idx = np.flatnonzero(np.isfinite(grid))
        if finite_idx.size <= 0:
            return None, "no_finite_values"
        finite_s = grid[finite_idx]
        if finite_s.size > 1 and not np.all(np.diff(finite_s) >= -1e-9):
            return None, "not_monotone_increasing"
        return (grid, finite_idx), "ok"

    def _vehicle_ref_array_from_refs(refs_like, vehicle_index):
        if refs_like is None:
            return None, "missing"
        veh_idx = int(np.clip(int(vehicle_index), 0, max(0, num_vehicles - 1)))
        try:
            if isinstance(refs_like, (list, tuple)):
                if veh_idx >= len(refs_like):
                    return None, "vehicle_index_out_of_range"
                ref_arr = np.asarray(refs_like[veh_idx], dtype=float)
            else:
                ref_all = np.asarray(refs_like, dtype=float)
                if ref_all.ndim == 3:
                    if ref_all.shape[0] == num_vehicles:
                        ref_arr = ref_all[veh_idx]
                    elif ref_all.shape[1] == num_vehicles:
                        ref_arr = ref_all[:, veh_idx, :]
                    elif ref_all.shape[2] == num_vehicles:
                        ref_arr = ref_all[:, :, veh_idx]
                    else:
                        return None, "vehicle_axis_not_found"
                else:
                    ref_arr = ref_all
        except (TypeError, ValueError, IndexError):
            return None, "non_numeric"
        return ref_arr, "ok"

    def _temporary_path_preview_grid_from_vehicle_refs(refs_like, vehicle_index, n_cols):
        ref_arr, status = _vehicle_ref_array_from_refs(refs_like, vehicle_index)
        if ref_arr is None:
            return None, status

        if ref_arr.ndim == 1:
            return _temporary_path_preview_prepare_physical_s_grid(ref_arr, n_cols)
        if ref_arr.ndim != 2 or ref_arr.shape[0] <= 0 or ref_arr.shape[1] <= 0:
            return None, "shape_mismatch"

        if ref_arr.shape[1] <= 16 and ref_arr.shape[0] > ref_arr.shape[1]:
            grid = ref_arr[:, 0]
        elif ref_arr.shape[0] <= 16 and ref_arr.shape[1] >= ref_arr.shape[0]:
            grid = ref_arr[0, :]
        elif ref_arr.shape[0] >= ref_arr.shape[1]:
            grid = ref_arr[:, 0]
        else:
            grid = ref_arr[0, :]
        return _temporary_path_preview_prepare_physical_s_grid(grid, n_cols)

    def _temporary_path_preview_physical_s_grid(vehicle_index, n_cols):
        rejected = []
        candidates = (
            ("raw_ref_vehicle_hist_col0", raw_ref_vehicle_hist),
            ("ref_bundle_corner_ref_histories_col0", ref_bundle.get("corner_ref_histories", None)),
            ("ref_bundle_raw_vehicle_refs_row0", ref_bundle.get("raw_vehicle_refs", None)),
            ("ctx_raw_ref_vehicle_histories_col0", ctx.get("raw_ref_vehicle_histories", None)),
            ("ctx_ref_vehicle_histories_col0", ctx.get("ref_vehicle_histories", None)),
            ("ctx_a1_ref_vehicle_histories_col0", ctx.get("a1_ref_vehicle_histories", None)),
        )
        for source, refs_like in candidates:
            grid_pack, status = _temporary_path_preview_grid_from_vehicle_refs(
                refs_like, vehicle_index, n_cols
            )
            if grid_pack is not None:
                return grid_pack, {
                    "source": source,
                    "configured": False,
                    "status": str(status),
                    "fallback_reason": "none",
                }
            if status != "missing":
                rejected.append(f"{source}:{status}")

        grid_pack, configured, status = _temporary_path_preview_explicit_s_grid(
            vehicle_index, n_cols
        )
        if grid_pack is not None:
            return grid_pack, {
                "source": "explicit_s_grid",
                "configured": bool(configured),
                "status": str(status),
                "fallback_reason": "none",
            }
        if configured:
            rejected.append(f"explicit_s_grid:{status}")

        try:
            x_ref_raw_arr = np.asarray(ctx.get("x_ref_raw", None), dtype=float)
            x_ref_raw_s = x_ref_raw_arr[0, :] if x_ref_raw_arr.ndim == 2 else None
        except (TypeError, ValueError, IndexError):
            x_ref_raw_s = None
        for source, grid_like in (
            ("ctx_s_ref_path", ctx.get("s_ref_path", None)),
            ("ctx_x_ref_raw_row0", x_ref_raw_s),
        ):
            grid_pack, status = _temporary_path_preview_prepare_physical_s_grid(
                grid_like, n_cols
            )
            if grid_pack is not None:
                return grid_pack, {
                    "source": source,
                    "configured": False,
                    "status": str(status),
                    "fallback_reason": "none",
                }
            if status != "missing":
                rejected.append(f"{source}:{status}")

        reason = "physical_s_grid_unavailable"
        if rejected:
            reason = f"{reason}:" + ";".join(rejected[-4:])
        return None, {
            "source": "k_relative_fallback",
            "configured": bool(configured),
            "status": "unavailable",
            "fallback_reason": reason,
        }

    def _temporary_path_preview_base_index(ref_mat, k_value, s_value, vehicle_index=0):
        index_mode = str(method_cfg.get("temporary_path_preview_index_mode", "k")).lower().strip()
        nominal_start = int(k_value) + 1
        meta = {
            "base_index_mode_requested": index_mode,
            "base_index_mode_effective": "k_relative",
            "base_index_s_grid_configured": False,
            "base_index_s_grid_valid": False,
            "base_index_s_grid_status": "not_used",
        }
        if index_mode in ("s", "distance", "path", "progress"):
            ref_arr = np.asarray(ref_mat, dtype=float)
            n_cols = int(ref_arr.shape[1]) if ref_arr.ndim == 2 else 0
            grid_pack, configured, status = _temporary_path_preview_explicit_s_grid(
                vehicle_index, n_cols
            )
            meta["base_index_s_grid_configured"] = bool(configured)
            meta["base_index_s_grid_status"] = str(status)
            if grid_pack is not None:
                ref_s, finite_idx = grid_pack
                finite_s = ref_s[finite_idx]
                lookup = str(method_cfg.get("temporary_path_preview_s_lookup", "nearest")).lower().strip()
                if lookup in ("upper", "ceil", "ceiling", "next"):
                    rel_idx = int(np.searchsorted(finite_s, float(s_value), side="left"))
                    rel_idx = int(np.clip(rel_idx, 0, finite_idx.size - 1))
                    base_idx = int(finite_idx[rel_idx])
                elif lookup in ("lower", "floor", "prev", "previous"):
                    rel_idx = int(np.searchsorted(finite_s, float(s_value), side="right") - 1)
                    rel_idx = int(np.clip(rel_idx, 0, finite_idx.size - 1))
                    base_idx = int(finite_idx[rel_idx])
                else:
                    rel_idx = int(np.argmin(np.abs(finite_s - float(s_value))))
                    base_idx = int(finite_idx[rel_idx])
                base_idx += int(np.rint(method_cfg.get("temporary_path_preview_base_offset_steps", 1)))
                meta["base_index_mode_effective"] = "s_grid_explicit"
                meta["base_index_s_grid_valid"] = True
                return int(base_idx), meta
            meta["base_index_mode_effective"] = "s_relative_k"
            meta["base_index_s_grid_valid"] = False
            return nominal_start, meta
        return nominal_start, meta

    def _temporary_path_preview_blend_weight(active, s_value):
        if not active:
            return 0.0
        base_weight = float(
            np.clip(method_cfg.get("temporary_path_preview_blend_weight", 1.0), 0.0, 1.0)
        )
        if not bool(method_cfg.get("temporary_path_preview_smooth_enabled", True)):
            return base_weight
        ramp_s = float(max(0.0, method_cfg.get("temporary_path_preview_ramp_s", 0.0)))
        if ramp_s <= 1e-9:
            return base_weight
        start_s = float(method_cfg.get("temporary_path_preview_start_s", 0.0))
        end_s_raw = method_cfg.get("temporary_path_preview_end_s", None)
        if end_s_raw is None:
            ramp_weight = _smooth_step01((float(s_value) - start_s) / ramp_s)
        else:
            ramp_weight = _smooth_box_gain(float(s_value), start_s, float(end_s_raw), ramp_s)
        return float(base_weight * ramp_weight)

    def _temporary_path_preview_lookup_s_col(ref_mat, target_s, vehicle_index=0):
        ref_arr = np.asarray(ref_mat, dtype=float)
        n_cols = int(ref_arr.shape[1]) if ref_arr.ndim == 2 else 0
        meta = {
            "target_lookup_source": "unavailable",
            "target_lookup_valid": False,
            "target_lookup_s_grid_configured": False,
            "target_lookup_s_grid_valid": False,
            "target_lookup_s_grid_status": "not_used",
            "target_lookup_monotone": False,
            "target_lookup_clamped": False,
            "target_lookup_fallback_reason": "invalid_ref_mat",
        }
        if n_cols <= 0:
            return 0, meta

        grid_pack, grid_meta = _temporary_path_preview_physical_s_grid(
            vehicle_index, n_cols
        )
        meta["target_lookup_source"] = str(grid_meta.get("source", "unavailable"))
        meta["target_lookup_s_grid_configured"] = bool(grid_meta.get("configured", False))
        meta["target_lookup_s_grid_status"] = str(grid_meta.get("status", "unavailable"))
        if grid_pack is None:
            meta["target_lookup_fallback_reason"] = str(
                grid_meta.get("fallback_reason", "physical_s_grid_unavailable")
            )
            return 0, meta
        ref_s, finite_idx = grid_pack
        grid = np.asarray(ref_s, dtype=float).reshape(-1)[:n_cols]
        finite_idx = np.asarray(finite_idx, dtype=int)
        meta["target_lookup_s_grid_valid"] = True

        finite_idx = finite_idx[(finite_idx >= 0) & (finite_idx < n_cols)]
        finite_idx = finite_idx[np.isfinite(grid[finite_idx])]
        if finite_idx.size <= 0:
            meta["target_lookup_fallback_reason"] = "no_finite_s_values"
            return 0, meta

        finite_s = grid[finite_idx]
        monotone = bool(finite_s.size <= 1 or np.all(np.diff(finite_s) >= -1e-9))
        meta["target_lookup_monotone"] = monotone
        lookup = str(method_cfg.get("temporary_path_preview_s_lookup", "nearest")).lower().strip()
        target_s = float(target_s)
        if not np.isfinite(target_s):
            meta["target_lookup_fallback_reason"] = "nonfinite_target_s"
            return int(finite_idx[0]), meta

        if monotone and lookup in ("upper", "ceil", "ceiling", "next"):
            rel_idx = int(np.searchsorted(finite_s, target_s, side="left"))
            rel_idx = int(np.clip(rel_idx, 0, finite_idx.size - 1))
        elif monotone and lookup in ("lower", "floor", "prev", "previous"):
            rel_idx = int(np.searchsorted(finite_s, target_s, side="right") - 1)
            rel_idx = int(np.clip(rel_idx, 0, finite_idx.size - 1))
        else:
            rel_idx = int(np.argmin(np.abs(finite_s - target_s)))
            if not monotone and lookup not in ("nearest", "closest", ""):
                meta["target_lookup_fallback_reason"] = "nonmonotone_s_grid_nearest"

        if monotone:
            meta["target_lookup_clamped"] = bool(target_s < finite_s[0] or target_s > finite_s[-1])
            meta["target_lookup_fallback_reason"] = "none"
        else:
            finite_min = float(np.min(finite_s))
            finite_max = float(np.max(finite_s))
            meta["target_lookup_clamped"] = bool(target_s < finite_min or target_s > finite_max)
            if meta["target_lookup_fallback_reason"] == "invalid_ref_mat":
                meta["target_lookup_fallback_reason"] = "none"

        meta["target_lookup_valid"] = True
        return int(finite_idx[rel_idx]), meta

    def _temporary_path_preview_heading_curvature(ref_arr, target_start_col, fallback_reasons):
        if ref_arr.ndim != 2 or ref_arr.shape[0] <= 2 or ref_arr.shape[1] <= 1:
            fallback_reasons.append("heading_fallback_unavailable")
            return 0.0, "none", False

        n_cols = int(ref_arr.shape[1])
        center = int(np.clip(target_start_col, 0, n_cols - 1))
        half_span = int(
            max(1, method_cfg.get("temporary_path_preview_curvature_window_cols", 3))
        )
        start = max(0, center - half_span)
        end = min(n_cols - 1, center + half_span)
        if end <= start:
            fallback_reasons.append("heading_fallback_short_window")
            return 0.0, "none", False

        s_grid = ref_arr[0, :] if ref_arr.shape[0] > 0 else np.arange(n_cols, dtype=float)
        heading = ref_arr[2, :]
        finite = np.flatnonzero(
            np.isfinite(s_grid[start:end + 1]) & np.isfinite(heading[start:end + 1])
        )
        if finite.size < 2:
            fallback_reasons.append("heading_fallback_no_finite_pair")
            return 0.0, "none", False

        idx0 = start + int(finite[0])
        idx1 = start + int(finite[-1])
        ds = float(s_grid[idx1] - s_grid[idx0])
        if abs(ds) <= 1e-9:
            fallback_reasons.append("heading_fallback_zero_ds")
            return 0.0, "none", False

        heading_seg = np.unwrap(np.asarray(heading[idx0:idx1 + 1], dtype=float))
        dpsi = float(heading_seg[-1] - heading_seg[0])
        fallback_reasons.append("heading_fallback_scaled_ref_unreliable")
        return float(dpsi / ds), "scaled_xref_row2_heading_gradient", False

    def _wrap_angle_rad(value):
        try:
            val = float(value)
        except (TypeError, ValueError):
            return 0.0
        if not np.isfinite(val):
            return 0.0
        return float(np.arctan2(np.sin(val), np.cos(val)))

    def _raw_reference_row_from_matrix(arr_like, ref_index):
        try:
            arr = np.asarray(arr_like, dtype=float)
        except (TypeError, ValueError):
            return None
        if arr.ndim != 2 or arr.size == 0:
            return None
        idx = int(ref_index)
        if arr.shape[1] >= num_states and arr.shape[0] != num_states:
            idx = int(np.clip(idx, 0, arr.shape[0] - 1))
            row = arr[idx, :]
        elif arr.shape[0] >= num_states:
            idx = int(np.clip(idx, 0, arr.shape[1] - 1))
            row = arr[:, idx]
        elif arr.shape[1] >= 3:
            idx = int(np.clip(idx, 0, arr.shape[0] - 1))
            row = arr[idx, :]
        else:
            return None
        row = np.asarray(row, dtype=float).reshape(-1)
        if row.size < 3 or not np.all(np.isfinite(row[:3])):
            return None
        return row

    def _raw_team_ref_at(ref_index):
        for candidate in (
            ref_bundle.get("team_ref_hist", None),
            ctx.get("team_ref_hist", None),
            ctx.get("x_ref_raw", None),
        ):
            row = _raw_reference_row_from_matrix(candidate, ref_index)
            if row is not None:
                return row
        return None

    def _raw_vehicle_ref_at(vehicle_index, ref_index):
        veh_idx = int(np.clip(int(vehicle_index), 0, max(0, num_vehicles - 1)))
        candidates = (
            raw_ref_vehicle_hist,
            ref_bundle.get("corner_ref_histories", None),
            ref_bundle.get("raw_vehicle_refs", None),
            ctx.get("raw_ref_vehicle_histories", None),
            ctx.get("ref_vehicle_histories", None),
            ctx.get("a1_ref_vehicle_histories", None),
        )
        for refs_like in candidates:
            ref_arr, status = _vehicle_ref_array_from_refs(refs_like, veh_idx)
            if ref_arr is None:
                continue
            row = _raw_reference_row_from_matrix(ref_arr, ref_index)
            if row is not None:
                return row, status
        return None, "missing"

    def _temporary_path_preview_state_delta_scale(row_index, cfg_key=None):
        cfg_scale = method_cfg.get(cfg_key, None) if cfg_key else None
        if cfg_scale is not None:
            try:
                scale = float(cfg_scale)
                if np.isfinite(scale):
                    return scale, f"configured:{cfg_key}"
            except (TypeError, ValueError):
                pass
        try:
            std = ctx.get("standardizer_x_kdnn", None)
            std_scale = np.asarray(getattr(std, "scale_", []), dtype=float).reshape(-1)
            idx = int(row_index)
            if std_scale.size > idx and np.isfinite(std_scale[idx]) and abs(std_scale[idx]) > 1e-12:
                return float(1.0 / std_scale[idx]), "standardizer_x_kdnn_scale"
        except Exception:
            pass
        return 1.0, "unit_fallback"

    def _temporary_path_preview_heading_delta_scale():
        return _temporary_path_preview_state_delta_scale(
            2, "temporary_path_preview_heading_scale"
        )

    def _temporary_path_preview_lateral_delta_scale():
        return _temporary_path_preview_state_delta_scale(
            1, "temporary_path_preview_local_path_lateral_scale"
        )

    def _temporary_path_preview_geometry_params(fallback_reasons):
        sys_pars = ctx.get("sys_pars", {})

        def _finite_cfg_float(key, default):
            value = method_cfg.get(key, None)
            if value is None:
                return float(default)
            try:
                out = float(value)
            except (TypeError, ValueError):
                fallback_reasons.append(f"{key}_invalid")
                return float(default)
            if not np.isfinite(out) or out <= 0.0:
                fallback_reasons.append(f"{key}_invalid")
                return float(default)
            return float(out)

        lf_default = float(sys_pars.get("lf", 1.2))
        lr_default = float(sys_pars.get("lr", 1.6))
        lf = _finite_cfg_float("temporary_path_preview_lf_m", lf_default)
        lr = _finite_cfg_float("temporary_path_preview_lr_m", lr_default)
        wheelbase_default = max(1e-6, lf + lr)
        wheelbase = _finite_cfg_float("temporary_path_preview_wheelbase_m", wheelbase_default)
        if wheelbase <= 1e-9:
            wheelbase = wheelbase_default
            fallback_reasons.append("wheelbase_invalid_fallback")
        return lf, lr, wheelbase

    def _fourws_beta_curvature(delta_f, delta_r, lf, lr, wheelbase):
        tan_f = float(np.tan(delta_f))
        tan_r = float(np.tan(delta_r))
        beta = float(np.arctan((lr * tan_f + lf * tan_r) / max(wheelbase, 1e-6)))
        curvature = float(np.cos(beta) * (tan_f - tan_r) / max(wheelbase, 1e-6))
        return beta, curvature

    def _fourws_weight_cfg(key, default, fallback_reasons):
        try:
            value = float(method_cfg.get(key, default))
        except (TypeError, ValueError):
            fallback_reasons.append(f"{key}_invalid")
            return float(default)
        if not np.isfinite(value) or value < 0.0:
            fallback_reasons.append(f"{key}_invalid")
            return float(default)
        return float(value)

    def _solve_upper_layer_fourws_delta(
        curvature_ref,
        lf,
        lr,
        wheelbase,
        rear_ratio,
        delta_clip,
        fallback_reasons,
    ):
        steering_logic = str(
            method_cfg.get(
                "temporary_path_preview_fourws_steering_logic",
                "anti_phase_angle_ratio",
            )
        ).replace("-", "_").lower().strip()
        if steering_logic in ("", "default"):
            steering_logic = "anti_phase_angle_ratio"

        if steering_logic in ("zero_sideslip", "neutral_sideslip", "beta_zero"):
            front_delta_raw = float(np.arctan(float(curvature_ref) * float(lf)))
            rear_delta_raw = float(-np.arctan(float(curvature_ref) * float(lr)))
            steering_relation = "tan_rear_equals_minus_lr_over_lf_tan_front"
        else:
            if steering_logic in ("anti_phase_tan_ratio", "tan_ratio"):
                denom = max(1e-6, 1.0 + rear_ratio)
                tan_front = float(wheelbase * float(curvature_ref) / denom)
                front_delta_raw = float(np.arctan(tan_front))
                rear_delta_raw = float(-np.arctan(rear_ratio * tan_front))
                steering_relation = "tan_rear_equals_minus_ratio_tan_front"
            else:
                if steering_logic not in ("anti_phase_angle_ratio", "angle_ratio"):
                    fallback_reasons.append(f"unsupported_fourws_steering_logic:{steering_logic}")
                    steering_logic = "anti_phase_angle_ratio"
                denom = max(1e-6, 1.0 + rear_ratio)
                front_delta_raw = float(np.arctan(wheelbase * float(curvature_ref) / denom))
                rear_delta_raw = float(-rear_ratio * front_delta_raw)
                steering_relation = "rear_delta_equals_minus_ratio_front_delta"

        front_delta = float(np.clip(front_delta_raw, -delta_clip, delta_clip))
        rear_delta = float(np.clip(rear_delta_raw, -delta_clip, delta_clip))

        curvature_weight = _fourws_weight_cfg(
            "temporary_path_preview_fourws_curvature_weight", 1.0, fallback_reasons
        )
        sideslip_weight = _fourws_weight_cfg(
            "temporary_path_preview_fourws_sideslip_weight", 0.0, fallback_reasons
        )
        ratio_weight = _fourws_weight_cfg(
            "temporary_path_preview_fourws_ratio_weight", 0.0, fallback_reasons
        )
        steer_weight = _fourws_weight_cfg(
            "temporary_path_preview_fourws_steer_weight", 0.0, fallback_reasons
        )

        def _objective(delta_f, delta_r):
            beta, curvature_cmd = _fourws_beta_curvature(delta_f, delta_r, lf, lr, wheelbase)
            tan_f = float(np.tan(delta_f))
            tan_r = float(np.tan(delta_r))
            ratio_residual = float(tan_r + rear_ratio * tan_f)
            obj = (
                curvature_weight * float(curvature_cmd - curvature_ref) ** 2
                + sideslip_weight * float(beta) ** 2
                + ratio_weight * ratio_residual ** 2
                + steer_weight * (float(delta_f) ** 2 + float(delta_r) ** 2)
            )
            return float(obj), float(beta), float(curvature_cmd), float(ratio_residual)

        refined = False
        if bool(method_cfg.get("temporary_path_preview_fourws_grid_refine_enabled", False)):
            try:
                span = abs(
                    float(method_cfg.get("temporary_path_preview_fourws_grid_refine_span_rad", 0.03))
                )
            except (TypeError, ValueError):
                span = 0.03
                fallback_reasons.append("fourws_grid_refine_span_invalid")
            try:
                n_grid = int(method_cfg.get("temporary_path_preview_fourws_grid_refine_points", 5))
            except (TypeError, ValueError):
                n_grid = 5
                fallback_reasons.append("fourws_grid_refine_points_invalid")
            if not np.isfinite(span) or span <= 0.0:
                span = 0.03
                fallback_reasons.append("fourws_grid_refine_span_invalid")
            n_grid = int(np.clip(n_grid, 3, 15))
            grid = np.linspace(-span, span, n_grid)
            best = _objective(front_delta, rear_delta)
            best_pair = (front_delta, rear_delta)
            for df_off in grid:
                for dr_off in grid:
                    cand_f = float(np.clip(front_delta + float(df_off), -delta_clip, delta_clip))
                    cand_r = float(np.clip(rear_delta + float(dr_off), -delta_clip, delta_clip))
                    cand = _objective(cand_f, cand_r)
                    if cand[0] < best[0]:
                        best = cand
                        best_pair = (cand_f, cand_r)
                        refined = True
            front_delta, rear_delta = best_pair

        objective, beta_cmd, curvature_cmd, ratio_residual = _objective(front_delta, rear_delta)
        return {
            "front_delta_opt": float(front_delta),
            "front_delta_opt_raw": float(front_delta_raw),
            "rear_delta_opt": float(rear_delta),
            "rear_delta_opt_raw": float(rear_delta_raw),
            "fourws_optimizer_enabled": True,
            "fourws_optimizer_mode": "bounded_4ws_curvature_objective",
            "fourws_steering_logic": str(steering_logic),
            "fourws_steering_relation": str(steering_relation),
            "fourws_optimizer_refined": bool(refined),
            "fourws_optimizer_objective": float(objective),
            "fourws_optimizer_curvature_cmd": float(curvature_cmd),
            "fourws_optimizer_curvature_error": float(curvature_cmd - curvature_ref),
            "fourws_optimizer_sideslip_beta": float(beta_cmd),
            "fourws_optimizer_ratio_residual": float(ratio_residual),
        }

    def _fourws_vehicle_heading_adjustment(delta_diag, vehicle_index, ref_index):
        heading_diag = {
            "heading_reference_valid": False,
            "desired_heading_raw": 0.0,
            "nominal_heading_raw": 0.0,
            "heading_adjustment_raw": 0.0,
            "body_offset_longitudinal_m": 0.0,
            "body_offset_lateral_m": 0.0,
            "fourws_curvature_cmd": 0.0,
            "fourws_sideslip_beta": 0.0,
            "reference_s_m": np.nan,
            "fallback_reasons": [],
        }
        fallback_reasons = heading_diag["fallback_reasons"]
        team_ref = _raw_team_ref_at(ref_index)
        veh_ref, veh_ref_status = _raw_vehicle_ref_at(vehicle_index, ref_index)
        if team_ref is None:
            fallback_reasons.append("team_reference_unavailable")
            return heading_diag
        if veh_ref is None:
            fallback_reasons.append(f"vehicle_reference_unavailable:{veh_ref_status}")
            return heading_diag

        lf, lr, wheelbase = _temporary_path_preview_geometry_params(fallback_reasons)
        try:
            delta_f = float(delta_diag.get("front_delta_est", 0.0))
            delta_r = float(delta_diag.get("rear_delta_est", 0.0))
        except (TypeError, ValueError):
            delta_f = 0.0
            delta_r = 0.0
            fallback_reasons.append("delta_unavailable")
        if not np.isfinite(delta_f):
            delta_f = 0.0
            fallback_reasons.append("front_delta_nonfinite")
        if not np.isfinite(delta_r):
            delta_r = 0.0
            fallback_reasons.append("rear_delta_nonfinite")

        team_heading = _wrap_angle_rad(team_ref[2])
        nominal_heading = _wrap_angle_rad(veh_ref[2])
        dx_ref = float(veh_ref[0] - team_ref[0])
        dy_ref = float(veh_ref[1] - team_ref[1])
        if not np.isfinite(dx_ref) or not np.isfinite(dy_ref):
            fallback_reasons.append("vehicle_offset_nonfinite")
            return heading_diag

        cos_h = float(np.cos(team_heading))
        sin_h = float(np.sin(team_heading))
        offset_scale = float(method_cfg.get("temporary_path_preview_vehicle_offset_scale", 1.0))
        if not np.isfinite(offset_scale):
            offset_scale = 1.0
            fallback_reasons.append("vehicle_offset_scale_invalid")
        body_long = offset_scale * (cos_h * dx_ref + sin_h * dy_ref)
        body_lat = offset_scale * (-sin_h * dx_ref + cos_h * dy_ref)

        beta, curvature_cmd = _fourws_beta_curvature(delta_f, delta_r, lf, lr, wheelbase)
        vx_body = float(np.cos(beta) - curvature_cmd * body_lat)
        vy_body = float(np.sin(beta) + curvature_cmd * body_long)
        if abs(vx_body) <= 1e-12 and abs(vy_body) <= 1e-12:
            fallback_reasons.append("vehicle_heading_velocity_degenerate")
            return heading_diag

        local_heading = float(np.arctan2(vy_body, vx_body))
        desired_heading = _wrap_angle_rad(team_heading + local_heading)
        heading_adjustment = _wrap_angle_rad(desired_heading - nominal_heading)
        heading_diag.update(
            {
                "heading_reference_valid": True,
                "desired_heading_raw": float(desired_heading),
                "nominal_heading_raw": float(nominal_heading),
                "heading_adjustment_raw": float(heading_adjustment),
                "body_offset_longitudinal_m": float(body_long),
                "body_offset_lateral_m": float(body_lat),
                "fourws_curvature_cmd": float(curvature_cmd),
                "fourws_sideslip_beta": float(beta),
                "reference_s_m": float(veh_ref[0]),
            }
        )
        return heading_diag

    def _apply_fourws_heading_reference(
        xref_preview,
        delta_diag,
        vehicle_index,
        target_start_col,
        active,
        blend_weight,
        preview_mode_requested,
        fallback_reasons,
    ):
        ref_out = np.asarray(xref_preview, dtype=float).copy()
        diag = {
            "fourws_heading_enabled": False,
            "fourws_heading_applied": False,
            "fourws_heading_applied_cols": 0,
            "fourws_heading_blend": 0.0,
            "fourws_heading_delta_scale": 1.0,
            "fourws_heading_delta_scale_source": "not_used",
            "fourws_heading_adjustment_raw_mean": 0.0,
            "fourws_heading_adjustment_raw_max_abs": 0.0,
            "fourws_desired_heading_raw_mean": 0.0,
            "fourws_nominal_heading_raw_mean": 0.0,
            "fourws_body_offset_longitudinal_m": 0.0,
            "fourws_body_offset_lateral_m": 0.0,
            "fourws_curvature_cmd": 0.0,
            "fourws_sideslip_beta": 0.0,
            "fourws_heading_fallback_reason": "disabled",
            "fourws_local_path_enabled": False,
            "fourws_local_path_applied": False,
            "fourws_local_path_applied_cols": 0,
            "fourws_local_path_blend": 0.0,
            "fourws_local_path_lateral_scale": 1.0,
            "fourws_local_path_lateral_scale_source": "not_used",
            "fourws_local_path_lateral_delta_mean": 0.0,
            "fourws_local_path_lateral_delta_max_abs": 0.0,
            "fourws_local_path_heading_clip_rad": 0.0,
            "fourws_local_path_fallback_reason": "disabled",
        }
        mode_key = str(preview_mode_requested or "").replace("-", "_").lower().strip()
        requested_by_mode = mode_key in (
            "fourws_heading",
            "four_ws_heading",
            "4ws_heading",
            "fourws_local_path",
            "four_ws_local_path",
        )
        local_path_requested_by_mode = mode_key in ("fourws_local_path", "four_ws_local_path")
        local_path_enabled = local_path_requested_by_mode or bool(
            method_cfg.get("temporary_path_preview_fourws_local_path_enabled", False)
        )
        diag["fourws_local_path_enabled"] = bool(local_path_enabled)
        heading_enabled = requested_by_mode or bool(
            method_cfg.get("temporary_path_preview_fourws_heading_enabled", False)
        )
        diag["fourws_heading_enabled"] = bool(heading_enabled)
        if not heading_enabled:
            return ref_out, diag
        if not bool(active):
            diag["fourws_heading_fallback_reason"] = "inactive"
            return ref_out, diag
        if ref_out.ndim != 2 or ref_out.shape[0] <= 2 or ref_out.shape[1] <= 0:
            diag["fourws_heading_fallback_reason"] = "xref_shape_invalid"
            fallback_reasons.append("fourws_heading_xref_shape_invalid")
            return ref_out, diag

        try:
            heading_blend_cfg = float(
                method_cfg.get("temporary_path_preview_fourws_heading_blend", 1.0)
            )
        except (TypeError, ValueError):
            heading_blend_cfg = 1.0
            fallback_reasons.append("fourws_heading_blend_invalid")
        if not np.isfinite(heading_blend_cfg):
            heading_blend_cfg = 1.0
            fallback_reasons.append("fourws_heading_blend_invalid")
        heading_blend = float(np.clip(heading_blend_cfg, 0.0, 1.0) * np.clip(blend_weight, 0.0, 1.0))
        diag["fourws_heading_blend"] = float(heading_blend)
        if heading_blend <= 1e-12:
            diag["fourws_heading_fallback_reason"] = "zero_blend"
            return ref_out, diag

        heading_delta_scale, scale_source = _temporary_path_preview_heading_delta_scale()
        diag["fourws_heading_delta_scale"] = float(heading_delta_scale)
        diag["fourws_heading_delta_scale_source"] = str(scale_source)

        adjustments = []
        desired_headings = []
        nominal_headings = []
        body_longs = []
        body_lats = []
        curvature_cmds = []
        betas = []
        applied_cols = 0
        n_cols = int(ref_out.shape[1])
        raw_adjustments_by_col = np.full(n_cols, np.nan, dtype=float)
        ref_s_by_col = np.full(n_cols, np.nan, dtype=float)
        for j in range(n_cols):
            ref_index = int(target_start_col) + int(j)
            heading_diag = _fourws_vehicle_heading_adjustment(
                delta_diag, vehicle_index, ref_index
            )
            if not bool(heading_diag.get("heading_reference_valid", False)):
                fallback_reasons.extend(heading_diag.get("fallback_reasons", []))
                continue
            raw_adjustment = float(heading_diag.get("heading_adjustment_raw", 0.0))
            if not np.isfinite(raw_adjustment):
                fallback_reasons.append("fourws_heading_adjustment_nonfinite")
                continue
            ref_out[2, j] += heading_blend * heading_delta_scale * raw_adjustment
            raw_adjustments_by_col[j] = float(raw_adjustment)
            ref_s_by_col[j] = float(heading_diag.get("reference_s_m", np.nan))
            applied_cols += 1
            adjustments.append(raw_adjustment)
            desired_headings.append(float(heading_diag.get("desired_heading_raw", 0.0)))
            nominal_headings.append(float(heading_diag.get("nominal_heading_raw", 0.0)))
            body_longs.append(float(heading_diag.get("body_offset_longitudinal_m", 0.0)))
            body_lats.append(float(heading_diag.get("body_offset_lateral_m", 0.0)))
            curvature_cmds.append(float(heading_diag.get("fourws_curvature_cmd", 0.0)))
            betas.append(float(heading_diag.get("fourws_sideslip_beta", 0.0)))

        if applied_cols <= 0:
            diag["fourws_heading_fallback_reason"] = "no_valid_heading_reference"
            if local_path_enabled:
                diag["fourws_local_path_fallback_reason"] = "no_valid_heading_reference"
            fallback_reasons.append("fourws_heading_no_valid_reference")
            return ref_out, diag

        adj_arr = np.asarray(adjustments, dtype=float)
        if local_path_enabled:
            if ref_out.shape[0] <= 1:
                diag["fourws_local_path_fallback_reason"] = "xref_lateral_row_unavailable"
                fallback_reasons.append("fourws_local_path_lateral_row_unavailable")
            else:
                try:
                    local_blend_cfg = float(
                        method_cfg.get("temporary_path_preview_fourws_local_path_blend", 1.0)
                    )
                except (TypeError, ValueError):
                    local_blend_cfg = 1.0
                    fallback_reasons.append("fourws_local_path_blend_invalid")
                if not np.isfinite(local_blend_cfg):
                    local_blend_cfg = 1.0
                    fallback_reasons.append("fourws_local_path_blend_invalid")
                local_path_blend = float(
                    np.clip(local_blend_cfg, 0.0, 1.0) * np.clip(heading_blend, 0.0, 1.0)
                )
                diag["fourws_local_path_blend"] = float(local_path_blend)
                lateral_scale, lateral_scale_source = _temporary_path_preview_lateral_delta_scale()
                diag["fourws_local_path_lateral_scale"] = float(lateral_scale)
                diag["fourws_local_path_lateral_scale_source"] = str(lateral_scale_source)
                try:
                    heading_clip = abs(
                        float(method_cfg.get("temporary_path_preview_local_path_heading_clip_rad", 0.45))
                    )
                except (TypeError, ValueError):
                    heading_clip = 0.45
                    fallback_reasons.append("fourws_local_path_heading_clip_invalid")
                if not np.isfinite(heading_clip) or heading_clip <= 0.0:
                    heading_clip = 0.45
                    fallback_reasons.append("fourws_local_path_heading_clip_invalid")
                diag["fourws_local_path_heading_clip_rad"] = float(heading_clip)
                lateral_delta = np.full(n_cols, np.nan, dtype=float)
                valid_cols = np.flatnonzero(
                    np.isfinite(raw_adjustments_by_col) & np.isfinite(ref_s_by_col)
                )
                if local_path_blend <= 1e-12:
                    diag["fourws_local_path_fallback_reason"] = "zero_blend"
                elif valid_cols.size <= 0:
                    diag["fourws_local_path_fallback_reason"] = "no_valid_reference_s"
                    fallback_reasons.append("fourws_local_path_no_valid_reference_s")
                else:
                    acc = 0.0
                    prev_col = None
                    prev_s = None
                    prev_heading = None
                    for col in valid_cols:
                        col = int(col)
                        cur_s = float(ref_s_by_col[col])
                        cur_heading = float(raw_adjustments_by_col[col])
                        if prev_col is None:
                            lateral_delta[col] = 0.0
                        else:
                            ds = float(cur_s - prev_s)
                            if not np.isfinite(ds) or ds < 0.0:
                                ds = 0.0
                                fallback_reasons.append("fourws_local_path_nonmonotone_s")
                            heading_mid = float(0.5 * (prev_heading + cur_heading))
                            heading_mid = float(np.clip(heading_mid, -heading_clip, heading_clip))
                            acc += float(np.tan(heading_mid) * ds)
                            lateral_delta[col] = float(acc)
                        prev_col = col
                        prev_s = cur_s
                        prev_heading = cur_heading
                    try:
                        max_lat_cfg = float(
                            method_cfg.get("temporary_path_preview_local_path_max_lateral_m", 0.35)
                        )
                    except (TypeError, ValueError):
                        max_lat_cfg = 0.35
                        fallback_reasons.append("fourws_local_path_max_lateral_invalid")
                    if np.isfinite(max_lat_cfg) and max_lat_cfg > 0.0:
                        lateral_delta = np.clip(lateral_delta, -max_lat_cfg, max_lat_cfg)
                    apply_cols = np.flatnonzero(np.isfinite(lateral_delta))
                    for col in apply_cols:
                        ref_out[1, int(col)] += (
                            local_path_blend * lateral_scale * float(lateral_delta[int(col)])
                        )
                    if apply_cols.size > 0:
                        finite_delta = lateral_delta[apply_cols]
                        diag.update(
                            {
                                "fourws_local_path_applied": True,
                                "fourws_local_path_applied_cols": int(apply_cols.size),
                                "fourws_local_path_lateral_delta_mean": float(np.mean(finite_delta)),
                                "fourws_local_path_lateral_delta_max_abs": float(
                                    np.max(np.abs(finite_delta))
                                ),
                                "fourws_local_path_fallback_reason": "none",
                            }
                        )
                    else:
                        diag["fourws_local_path_fallback_reason"] = "no_finite_lateral_delta"
                        fallback_reasons.append("fourws_local_path_no_finite_lateral_delta")
        diag.update(
            {
                "fourws_heading_applied": True,
                "fourws_heading_applied_cols": int(applied_cols),
                "fourws_heading_adjustment_raw_mean": float(np.mean(adj_arr)),
                "fourws_heading_adjustment_raw_max_abs": float(np.max(np.abs(adj_arr))),
                "fourws_desired_heading_raw_mean": float(np.mean(desired_headings)),
                "fourws_nominal_heading_raw_mean": float(np.mean(nominal_headings)),
                "fourws_body_offset_longitudinal_m": float(np.mean(body_longs)),
                "fourws_body_offset_lateral_m": float(np.mean(body_lats)),
                "fourws_curvature_cmd": float(np.mean(curvature_cmds)),
                "fourws_sideslip_beta": float(np.mean(betas)),
                "fourws_heading_fallback_reason": "none",
            }
        )
        return ref_out, diag

    def _estimate_upper_layer_fourws_delta(ref_mat, target_start_col, target_s, vehicle_index):
        ref_arr = np.asarray(ref_mat, dtype=float)
        fallback_reasons = []
        curvature_est = np.nan
        curvature_source = "none"
        curvature_reliable = False

        try:
            curv_ref = np.asarray(ctx.get("curvature_ref_path", []), dtype=float).reshape(-1)
        except Exception:
            curv_ref = np.asarray([], dtype=float)
            fallback_reasons.append("curvature_ref_path_unreadable")
        if curv_ref.size > 0:
            curv_idx = int(np.clip(int(target_start_col), 0, curv_ref.size - 1))
            curv_val = float(curv_ref[curv_idx])
            if np.isfinite(curv_val):
                curvature_est = curv_val
                curvature_source = "curvature_ref_path"
                curvature_reliable = True
            else:
                fallback_reasons.append("curvature_ref_path_nonfinite")
        else:
            fallback_reasons.append("curvature_ref_path_missing")

        if not np.isfinite(curvature_est):
            curvature_est, curvature_source, curvature_reliable = (
                _temporary_path_preview_heading_curvature(
                    ref_arr, target_start_col, fallback_reasons
                )
            )

        if (
            (not np.isfinite(curvature_est))
            and ref_arr.ndim == 2
            and ref_arr.shape[0] > 5
            and ref_arr.shape[1] > 0
        ):
            speed = float(ref_arr[3, int(np.clip(target_start_col, 0, ref_arr.shape[1] - 1))])
            yaw_rate = float(ref_arr[5, int(np.clip(target_start_col, 0, ref_arr.shape[1] - 1))])
            if np.isfinite(speed) and abs(speed) > 1e-6 and np.isfinite(yaw_rate):
                curvature_est = float(yaw_rate / speed)
                curvature_source = "scaled_xref_r_over_vx"
                curvature_reliable = False
                fallback_reasons.append("yaw_rate_speed_scaled_ref_unreliable")
            else:
                fallback_reasons.append("yaw_rate_speed_fallback_unavailable")

        if not np.isfinite(curvature_est):
            curvature_est = 0.0
            curvature_source = "zero_fallback"
            curvature_reliable = False
            fallback_reasons.append("curvature_zero_fallback")

        lf, lr, wheelbase = _temporary_path_preview_geometry_params(fallback_reasons)

        try:
            rear_ratio = float(method_cfg.get("temporary_path_preview_rear_steer_ratio", 0.0))
        except (TypeError, ValueError):
            rear_ratio = 0.0
            fallback_reasons.append("rear_steer_ratio_invalid")
        if not np.isfinite(rear_ratio):
            rear_ratio = 0.0
            fallback_reasons.append("rear_steer_ratio_invalid")
        curvature_for_delta = float(curvature_est) if bool(curvature_reliable) else 0.0
        if not bool(curvature_reliable) and abs(float(curvature_est)) > 1e-12:
            fallback_reasons.append("unreliable_curvature_not_used_for_delta")

        delta_clip_cfg = method_cfg.get("temporary_path_preview_front_delta_est_clip_rad", None)
        if delta_clip_cfg is None:
            try:
                umin = np.asarray(ctx.get("umin_lin_noadapt", []), dtype=float).reshape(-1)
                umax = np.asarray(ctx.get("umax_lin_noadapt", []), dtype=float).reshape(-1)
                clip_candidates = []
                if umin.size > 0 and np.isfinite(umin[0]):
                    clip_candidates.append(abs(float(umin[0])))
                if umax.size > 0 and np.isfinite(umax[0]):
                    clip_candidates.append(abs(float(umax[0])))
                delta_clip = max(clip_candidates) if clip_candidates else 0.65
            except Exception:
                delta_clip = 0.65
                fallback_reasons.append("delta_clip_default_fallback")
        else:
            try:
                delta_clip = float(delta_clip_cfg)
            except (TypeError, ValueError):
                delta_clip = 0.65
                fallback_reasons.append("delta_clip_config_invalid")
        if not np.isfinite(delta_clip) or delta_clip <= 0.0:
            delta_clip = 0.65
            fallback_reasons.append("delta_clip_invalid_fallback")

        optimizer_enabled = bool(
            method_cfg.get("temporary_path_preview_fourws_optimizer_enabled", True)
        )
        if optimizer_enabled:
            opt_diag = _solve_upper_layer_fourws_delta(
                curvature_for_delta,
                lf,
                lr,
                wheelbase,
                rear_ratio,
                delta_clip,
                fallback_reasons,
            )
            front_delta_raw = float(opt_diag.get("front_delta_opt_raw", 0.0))
            rear_delta_raw = float(opt_diag.get("rear_delta_opt_raw", 0.0))
            front_delta_est = float(opt_diag.get("front_delta_opt", 0.0))
            rear_delta_est = float(opt_diag.get("rear_delta_opt", 0.0))
        else:
            steer_denom = max(1e-6, 1.0 + rear_ratio)
            front_delta_raw = float(np.arctan(wheelbase * curvature_for_delta / steer_denom))
            rear_delta_raw = float(-rear_ratio * front_delta_raw)
            front_delta_est = float(np.clip(front_delta_raw, -delta_clip, delta_clip))
            rear_delta_est = float(np.clip(rear_delta_raw, -delta_clip, delta_clip))
            beta_cmd, curvature_cmd = _fourws_beta_curvature(
                front_delta_est, rear_delta_est, lf, lr, wheelbase
            )
            opt_diag = {
                "front_delta_opt": float(front_delta_est),
                "front_delta_opt_raw": float(front_delta_raw),
                "rear_delta_opt": float(rear_delta_est),
                "rear_delta_opt_raw": float(rear_delta_raw),
                "fourws_optimizer_enabled": False,
                "fourws_optimizer_mode": "legacy_anti_phase_angle_ratio",
                "fourws_steering_logic": "anti_phase_angle_ratio",
                "fourws_steering_relation": "rear_delta_equals_minus_ratio_front_delta",
                "fourws_optimizer_refined": False,
                "fourws_optimizer_objective": float((curvature_cmd - curvature_for_delta) ** 2),
                "fourws_optimizer_curvature_cmd": float(curvature_cmd),
                "fourws_optimizer_curvature_error": float(curvature_cmd - curvature_for_delta),
                "fourws_optimizer_sideslip_beta": float(beta_cmd),
                "fourws_optimizer_ratio_residual": 0.0,
            }
        if abs(front_delta_est) <= 1e-9:
            fourws_intent = "straight"
        elif front_delta_est > 0.0:
            fourws_intent = "left_countersteer"
        else:
            fourws_intent = "right_countersteer"

        out = {
            "curvature_est": float(curvature_est),
            "curvature_source": str(curvature_source),
            "curvature_reliable": bool(curvature_reliable),
            "curvature_for_delta": float(curvature_for_delta),
            "curvature_used_for_delta": bool(curvature_reliable),
            "front_delta_est": float(front_delta_est),
            "front_delta_est_raw": float(front_delta_raw),
            "rear_delta_est": float(rear_delta_est),
            "rear_delta_est_raw": float(rear_delta_raw),
            "rear_steer_ratio": float(rear_ratio),
            "fourws_intent": str(fourws_intent),
            "lf_m": float(lf),
            "lr_m": float(lr),
            "wheelbase_m": float(wheelbase),
            "target_s_for_delta": float(target_s),
            "delta_fallback_reasons": list(fallback_reasons),
        }
        out.update(opt_diag)
        return out

    def _compute_upper_layer_fourws_preview(
        k_value,
        vehicle_index,
        xref_nominal,
        ref_mat,
        s_value,
        trigger_s,
        active=False,
        trigger_s_source="vehicle_actual_s",
        preview_mode_requested="fourws_geometric",
    ):
        xref_current = np.asarray(xref_nominal, dtype=float).copy()
        ref_arr = np.asarray(ref_mat, dtype=float)
        nominal_start = int(k_value) + 1
        window_width = int(xref_current.shape[1]) if xref_current.ndim == 2 else 0
        fallback_reasons = []

        veh_idx = int(np.clip(int(vehicle_index), 0, max(0, num_vehicles - 1)))
        try:
            lookahead_cfg = _cfg_vector(
                method_cfg.get("temporary_path_preview_lookahead_m", 0.0),
                num_vehicles,
                0.0,
            )
        except (TypeError, ValueError):
            lookahead_cfg = np.zeros(num_vehicles, dtype=float)
            fallback_reasons.append("lookahead_config_invalid")
        lookahead_requested = float(lookahead_cfg[veh_idx])
        if not np.isfinite(lookahead_requested):
            lookahead_requested = 0.0
            fallback_reasons.append("nonfinite_lookahead")

        min_cfg = method_cfg.get("temporary_path_preview_min_lookahead_m", None)
        max_cfg = method_cfg.get("temporary_path_preview_max_lookahead_m", None)
        lookahead_min = None
        lookahead_max = None
        if min_cfg is not None:
            try:
                lookahead_min = float(_cfg_vector(min_cfg, num_vehicles, -np.inf)[veh_idx])
            except (TypeError, ValueError):
                fallback_reasons.append("min_lookahead_config_invalid")
        if max_cfg is not None:
            try:
                lookahead_max = float(_cfg_vector(max_cfg, num_vehicles, np.inf)[veh_idx])
            except (TypeError, ValueError):
                fallback_reasons.append("max_lookahead_config_invalid")
        if lookahead_min is not None and not np.isfinite(lookahead_min):
            lookahead_min = None
        if lookahead_max is not None and not np.isfinite(lookahead_max):
            lookahead_max = None
        if lookahead_min is not None and lookahead_max is not None and lookahead_min > lookahead_max:
            lookahead_min, lookahead_max = lookahead_max, lookahead_min
            fallback_reasons.append("lookahead_bounds_swapped")

        lookahead_clipped = lookahead_requested
        if lookahead_min is not None:
            lookahead_clipped = max(lookahead_clipped, lookahead_min)
        if lookahead_max is not None:
            lookahead_clipped = min(lookahead_clipped, lookahead_max)

        try:
            vehicle_s = float(s_value)
        except Exception:
            vehicle_s = np.nan
        try:
            trigger_s_float = float(trigger_s)
        except Exception:
            trigger_s_float = np.nan
        trigger_s_input = float(trigger_s_float) if np.isfinite(trigger_s_float) else np.nan
        if not np.isfinite(trigger_s_float):
            trigger_s_float = vehicle_s
        if not np.isfinite(vehicle_s):
            if np.isfinite(trigger_s_float):
                vehicle_s = float(trigger_s_float)
                fallback_reasons.append("vehicle_s_fallback_trigger_s")
            else:
                grid_pack, grid_meta = _temporary_path_preview_physical_s_grid(
                    vehicle_index, int(ref_arr.shape[1]) if ref_arr.ndim == 2 else 0
                )
                if grid_pack is not None:
                    physical_s_grid, finite_idx = grid_pack
                    fallback_idx = int(np.clip(nominal_start, 0, physical_s_grid.size - 1))
                    if not np.isfinite(physical_s_grid[fallback_idx]):
                        finite_idx = np.asarray(finite_idx, dtype=int)
                        fallback_idx = int(finite_idx[np.argmin(np.abs(finite_idx - nominal_start))])
                    vehicle_s = float(physical_s_grid[fallback_idx])
                    fallback_reasons.append(
                        "vehicle_s_fallback_physical_s_grid:"
                        + str(grid_meta.get("source", "unavailable"))
                    )
                else:
                    vehicle_s = 0.0
                    fallback_reasons.append("vehicle_s_zero_fallback")
        if not np.isfinite(trigger_s_float):
            trigger_s_float = vehicle_s

        target_s_base = float(vehicle_s)
        target_s_source = "vehicle_actual_s_plus_lookahead"
        if bool(temporary_path_preview_use_ref_s):
            if np.isfinite(trigger_s_input):
                target_s_base = float(trigger_s_input)
                target_s_source = "trigger_s_plus_lookahead"
            elif np.isfinite(trigger_s_float):
                target_s_base = float(trigger_s_float)
                target_s_source = "trigger_s_fallback_plus_lookahead"
            else:
                fallback_reasons.append("target_s_ref_trigger_unavailable")
        target_s = float(target_s_base + lookahead_clipped)

        try:
            target_start_col, lookup_meta = _temporary_path_preview_lookup_s_col(
                ref_arr, target_s, vehicle_index=vehicle_index
            )
        except Exception as exc:
            target_start_col = nominal_start
            lookup_meta = {
                "target_lookup_source": "exception_fallback",
                "target_lookup_valid": False,
                "target_lookup_fallback_reason": type(exc).__name__,
                "target_lookup_clamped": False,
                "target_lookup_s_grid_configured": False,
                "target_lookup_s_grid_valid": False,
                "target_lookup_s_grid_status": "exception",
                "target_lookup_monotone": False,
            }
            fallback_reasons.append("target_lookup_exception")
        if not bool(lookup_meta.get("target_lookup_valid", False)):
            target_start_col = nominal_start
            fallback_reasons.append(str(lookup_meta.get("target_lookup_fallback_reason", "target_lookup_invalid")))

        target_start_col_raw = int(target_start_col)
        candidate_shift_before_clamp = int(target_start_col_raw - nominal_start)
        max_shift_cfg = method_cfg.get("temporary_path_preview_max_shift_steps", None)
        if max_shift_cfg is None:
            max_shift = float(abs(candidate_shift_before_clamp))
        else:
            max_shift_vec = _cfg_vector(
                max_shift_cfg, num_vehicles, abs(candidate_shift_before_clamp)
            )
            max_shift = max(0.0, float(max_shift_vec[veh_idx]))
        max_candidate_shift_cfg = method_cfg.get(
            "temporary_path_preview_max_candidate_shift_steps", None
        )
        if max_candidate_shift_cfg is None:
            max_candidate_shift = float(max_shift)
        else:
            max_candidate_shift_vec = _cfg_vector(
                max_candidate_shift_cfg, num_vehicles, max_shift
            )
            max_candidate_shift = max(0.0, float(max_candidate_shift_vec[veh_idx]))
        if np.isfinite(max_candidate_shift):
            candidate_shift = int(
                np.clip(
                    candidate_shift_before_clamp,
                    -float(max_candidate_shift),
                    float(max_candidate_shift),
                )
            )
        else:
            candidate_shift = int(candidate_shift_before_clamp)
        candidate_shift_clamped = bool(candidate_shift != candidate_shift_before_clamp)
        target_start_col = int(nominal_start + candidate_shift)
        blend_weight = _temporary_path_preview_blend_weight(active, trigger_s_float)
        preview_win, leading_pad, terminal_pad, terminal_overshoot = _slice_ref_window_padded(
            ref_arr, target_start_col, window_width
        )
        applied = bool(
            active
            and blend_weight > 1e-12
            and xref_current.shape == preview_win.shape
            and bool(lookup_meta.get("target_lookup_valid", False))
        )
        if applied:
            xref_preview = (1.0 - blend_weight) * xref_current + blend_weight * preview_win
        else:
            xref_preview = xref_current
            if active and blend_weight > 1e-12 and xref_current.shape != preview_win.shape:
                fallback_reasons.append("preview_window_shape_mismatch")

        delta_diag = _estimate_upper_layer_fourws_delta(
            ref_arr, target_start_col, target_s, vehicle_index
        )
        fallback_reasons.extend(delta_diag.get("delta_fallback_reasons", []))
        xref_preview, heading_diag = _apply_fourws_heading_reference(
            xref_preview,
            delta_diag,
            vehicle_index,
            target_start_col,
            active,
            blend_weight,
            preview_mode_requested,
            fallback_reasons,
        )
        preview_mode_key = str(preview_mode_requested or "").replace("-", "_").lower().strip()
        preview_mode_effective = (
            "fourws_local_path"
            if bool(heading_diag.get("fourws_local_path_applied", False))
            else "fourws_heading"
            if (
                bool(heading_diag.get("fourws_heading_enabled", False))
                or preview_mode_key in ("fourws_heading", "four_ws_heading", "4ws_heading")
                or preview_mode_key in ("fourws_local_path", "four_ws_local_path")
            )
            else "fourws_geometric"
        )
        fallback_reason = "none" if not fallback_reasons else "|".join(str(x) for x in fallback_reasons)
        applied_shift = int(candidate_shift) if applied else 0
        effective_shift = float(blend_weight * candidate_shift) if applied else 0.0
        diag = {
            "step": int(k_value),
            "vehicle_index": int(vehicle_index),
            "enabled": bool(use_temporary_path_preview),
            "active": bool(active),
            "applied": bool(applied),
            "s": float(vehicle_s),
            "vehicle_s": float(vehicle_s),
            "trigger_s": float(trigger_s_float),
            "trigger_s_source": str(trigger_s_source),
            "use_ref_s": bool(temporary_path_preview_use_ref_s),
            "trigger_mode": str(method_cfg.get("temporary_path_preview_trigger_mode", "s")),
            "preview_mode_requested": str(preview_mode_requested),
            "preview_mode": str(preview_mode_effective),
            "geometric_preview_applied": bool(applied),
            "lookahead_m_requested": float(lookahead_requested),
            "lookahead_m": float(lookahead_clipped),
            "lookahead_min_m": None if lookahead_min is None else float(lookahead_min),
            "lookahead_max_m": None if lookahead_max is None else float(lookahead_max),
            "lookahead_clipped": bool(abs(lookahead_clipped - lookahead_requested) > 1e-12),
            "target_s": float(target_s),
            "target_s_base": float(target_s_base),
            "target_s_source": str(target_s_source),
            "target_start_col": int(target_start_col),
            "target_start_col_raw": int(target_start_col_raw),
            "target_lookup_source": str(lookup_meta.get("target_lookup_source", "unavailable")),
            "target_lookup_valid": bool(lookup_meta.get("target_lookup_valid", False)),
            "target_lookup_clamped": bool(lookup_meta.get("target_lookup_clamped", False)),
            "target_lookup_s_grid_configured": bool(
                lookup_meta.get("target_lookup_s_grid_configured", False)
            ),
            "target_lookup_s_grid_valid": bool(
                lookup_meta.get("target_lookup_s_grid_valid", False)
            ),
            "target_lookup_s_grid_status": str(
                lookup_meta.get("target_lookup_s_grid_status", "not_used")
            ),
            "target_lookup_monotone": bool(lookup_meta.get("target_lookup_monotone", False)),
            "target_lookup_fallback_reason": str(
                lookup_meta.get("target_lookup_fallback_reason", "none")
            ),
            "fallback_reason": str(fallback_reason),
            "fallback_reasons": list(fallback_reasons),
            "index_mode": str(method_cfg.get("temporary_path_preview_index_mode", "k")),
            "base_index_mode_effective": "fourws_geometric_s_lookahead",
            "base_index_mode_requested": str(method_cfg.get("temporary_path_preview_index_mode", "k")),
            "base_index_s_grid_configured": bool(
                lookup_meta.get("target_lookup_s_grid_configured", False)
            ),
            "base_index_s_grid_valid": bool(lookup_meta.get("target_lookup_s_grid_valid", False)),
            "base_index_s_grid_status": str(
                lookup_meta.get("target_lookup_s_grid_status", "not_used")
            ),
            "s_lookup": str(method_cfg.get("temporary_path_preview_s_lookup", "nearest")),
            "nominal_start_col": int(nominal_start),
            "base_start_col": int(target_start_col_raw),
            "start_col": int(target_start_col),
            "start_col_before_clamp": int(target_start_col_raw),
            "window_width": int(window_width),
            "requested_preview_shift_steps": float(candidate_shift_before_clamp),
            "clipped_preview_shift_steps": float(candidate_shift),
            "configured_preview_shift_steps": int(candidate_shift),
            "candidate_preview_shift_steps_before_clamp": int(candidate_shift_before_clamp),
            "candidate_preview_shift_steps": int(candidate_shift),
            "candidate_shift_before_clamp": int(candidate_shift_before_clamp),
            "candidate_shift_clamped": bool(candidate_shift_clamped),
            "applied_preview_shift_steps": int(applied_shift),
            "requested_shift_steps": float(candidate_shift_before_clamp),
            "clipped_shift_steps": float(candidate_shift),
            "configured_shift_steps": int(candidate_shift),
            "candidate_shift_steps_before_clamp": int(candidate_shift_before_clamp),
            "candidate_shift_steps": int(candidate_shift),
            "actual_preview_shift_steps": int(applied_shift),
            "effective_preview_shift_steps": float(effective_shift),
            "blend_weight": float(blend_weight),
            "max_shift_steps": float(max_shift),
            "max_candidate_shift_steps": float(max_candidate_shift),
            "leading_pad_cols": int(leading_pad),
            "terminal_pad_cols": int(terminal_pad),
            "terminal_pad_overshoot_cols": int(terminal_overshoot),
        }
        diag.update(
            {
                "curvature_est": float(delta_diag.get("curvature_est", 0.0)),
                "curvature_source": str(delta_diag.get("curvature_source", "none")),
                "curvature_reliable": bool(delta_diag.get("curvature_reliable", False)),
                "curvature_for_delta": float(delta_diag.get("curvature_for_delta", 0.0)),
                "curvature_used_for_delta": bool(delta_diag.get("curvature_used_for_delta", False)),
                "front_delta_est": float(delta_diag.get("front_delta_est", 0.0)),
                "front_delta_est_raw": float(delta_diag.get("front_delta_est_raw", 0.0)),
                "rear_delta_est": float(delta_diag.get("rear_delta_est", 0.0)),
                "rear_delta_est_raw": float(delta_diag.get("rear_delta_est_raw", 0.0)),
                "rear_steer_ratio": float(delta_diag.get("rear_steer_ratio", 0.0)),
                "fourws_optimizer_enabled": bool(
                    delta_diag.get("fourws_optimizer_enabled", False)
                ),
                "fourws_optimizer_mode": str(
                    delta_diag.get("fourws_optimizer_mode", "not_used")
                ),
                "fourws_steering_logic": str(
                    delta_diag.get("fourws_steering_logic", "not_used")
                ),
                "fourws_steering_relation": str(
                    delta_diag.get("fourws_steering_relation", "not_used")
                ),
                "fourws_optimizer_refined": bool(
                    delta_diag.get("fourws_optimizer_refined", False)
                ),
                "fourws_optimizer_objective": float(
                    delta_diag.get("fourws_optimizer_objective", 0.0)
                ),
                "fourws_optimizer_curvature_cmd": float(
                    delta_diag.get("fourws_optimizer_curvature_cmd", 0.0)
                ),
                "fourws_optimizer_curvature_error": float(
                    delta_diag.get("fourws_optimizer_curvature_error", 0.0)
                ),
                "fourws_optimizer_sideslip_beta": float(
                    delta_diag.get("fourws_optimizer_sideslip_beta", 0.0)
                ),
                "fourws_optimizer_ratio_residual": float(
                    delta_diag.get("fourws_optimizer_ratio_residual", 0.0)
                ),
                "fourws_intent": str(delta_diag.get("fourws_intent", "straight")),
                "lf_m": float(delta_diag.get("lf_m", 0.0)),
                "lr_m": float(delta_diag.get("lr_m", 0.0)),
                "wheelbase_m": float(delta_diag.get("wheelbase_m", 0.0)),
                "fourws_heading_enabled": bool(heading_diag.get("fourws_heading_enabled", False)),
                "fourws_heading_applied": bool(heading_diag.get("fourws_heading_applied", False)),
                "fourws_heading_applied_cols": int(heading_diag.get("fourws_heading_applied_cols", 0)),
                "fourws_heading_blend": float(heading_diag.get("fourws_heading_blend", 0.0)),
                "fourws_heading_delta_scale": float(heading_diag.get("fourws_heading_delta_scale", 1.0)),
                "fourws_heading_delta_scale_source": str(
                    heading_diag.get("fourws_heading_delta_scale_source", "not_used")
                ),
                "fourws_heading_adjustment_raw_mean": float(
                    heading_diag.get("fourws_heading_adjustment_raw_mean", 0.0)
                ),
                "fourws_heading_adjustment_raw_max_abs": float(
                    heading_diag.get("fourws_heading_adjustment_raw_max_abs", 0.0)
                ),
                "fourws_desired_heading_raw_mean": float(
                    heading_diag.get("fourws_desired_heading_raw_mean", 0.0)
                ),
                "fourws_nominal_heading_raw_mean": float(
                    heading_diag.get("fourws_nominal_heading_raw_mean", 0.0)
                ),
                "fourws_body_offset_longitudinal_m": float(
                    heading_diag.get("fourws_body_offset_longitudinal_m", 0.0)
                ),
                "fourws_body_offset_lateral_m": float(
                    heading_diag.get("fourws_body_offset_lateral_m", 0.0)
                ),
                "fourws_curvature_cmd": float(heading_diag.get("fourws_curvature_cmd", 0.0)),
                "fourws_sideslip_beta": float(heading_diag.get("fourws_sideslip_beta", 0.0)),
                "fourws_heading_fallback_reason": str(
                    heading_diag.get("fourws_heading_fallback_reason", "none")
                ),
                "fourws_local_path_enabled": bool(
                    heading_diag.get("fourws_local_path_enabled", False)
                ),
                "fourws_local_path_applied": bool(
                    heading_diag.get("fourws_local_path_applied", False)
                ),
                "fourws_local_path_applied_cols": int(
                    heading_diag.get("fourws_local_path_applied_cols", 0)
                ),
                "fourws_local_path_blend": float(
                    heading_diag.get("fourws_local_path_blend", 0.0)
                ),
                "fourws_local_path_lateral_scale": float(
                    heading_diag.get("fourws_local_path_lateral_scale", 1.0)
                ),
                "fourws_local_path_lateral_delta_mean": float(
                    heading_diag.get("fourws_local_path_lateral_delta_mean", 0.0)
                ),
                "fourws_local_path_lateral_delta_max_abs": float(
                    heading_diag.get("fourws_local_path_lateral_delta_max_abs", 0.0)
                ),
                "fourws_local_path_heading_clip_rad": float(
                    heading_diag.get("fourws_local_path_heading_clip_rad", 0.0)
                ),
                "fourws_local_path_fallback_reason": str(
                    heading_diag.get("fourws_local_path_fallback_reason", "none")
                ),
            }
        )
        return xref_preview, diag

    def _apply_temporary_path_preview(
        k_value,
        vehicle_index,
        xref_nominal,
        ref_mat,
        s_value,
        trigger_s_value=None,
        trigger_s_source="vehicle_actual_s",
    ):
        xref_current = np.asarray(xref_nominal, dtype=float).copy()
        nominal_start = int(k_value) + 1
        vehicle_s = float(s_value)
        trigger_s = vehicle_s if trigger_s_value is None else float(trigger_s_value)
        active = bool(use_temporary_path_preview) and _tf14_channel_active(
            method_cfg, "temporary_path_preview", k_value, trigger_s, fallback_prefix=None
        )
        path_allowed = _path_mode_allowed(method_cfg.get("temporary_path_preview_path_modes", None))
        if not path_allowed:
            # A path-gated preview must be a true no-op outside its target path.
            # Returning before the 4WS/geometric branch avoids low-speed numerical drift
            # from disabled preview diagnostics.
            return xref_current, {
                "step": int(k_value),
                "vehicle_index": int(vehicle_index),
                "enabled": bool(use_temporary_path_preview),
                "active": False,
                "applied": False,
                "s": float(vehicle_s),
                "vehicle_s": float(vehicle_s),
                "trigger_s": float(trigger_s),
                "trigger_s_source": str(trigger_s_source),
                "use_ref_s": bool(temporary_path_preview_use_ref_s),
                "trigger_mode": str(method_cfg.get("temporary_path_preview_trigger_mode", "s")),
                "preview_mode_requested": str(temporary_path_preview_mode or "shift"),
                "preview_mode": "path_mode_disabled",
                "current_path_mode": str(suite_path_mode),
                "allowed_path_modes": method_cfg.get("temporary_path_preview_path_modes", None),
                "path_mode_allowed": False,
                "geometric_preview_applied": False,
                "lookahead_m_requested": 0.0,
                "lookahead_m": 0.0,
                "lookahead_min_m": None,
                "lookahead_max_m": None,
                "lookahead_clipped": False,
                "target_s": None,
                "target_start_col": int(nominal_start),
                "target_start_col_raw": int(nominal_start),
                "target_lookup_source": "path_mode_disabled",
                "target_lookup_valid": False,
                "target_lookup_clamped": False,
                "front_delta_est": 0.0,
                "front_delta_est_raw": 0.0,
                "rear_delta_est": 0.0,
                "rear_delta_est_raw": 0.0,
                "curvature_est": 0.0,
                "curvature_source": "path_mode_disabled",
                "curvature_reliable": False,
                "curvature_for_delta": 0.0,
                "curvature_used_for_delta": False,
                "fourws_optimizer_enabled": False,
                "fourws_optimizer_mode": "path_mode_disabled",
                "fourws_steering_logic": "path_mode_disabled",
                "fourws_steering_relation": "path_mode_disabled",
                "fourws_optimizer_refined": False,
                "fourws_optimizer_objective": 0.0,
                "fourws_optimizer_curvature_cmd": 0.0,
                "fourws_optimizer_curvature_error": 0.0,
                "fourws_optimizer_sideslip_beta": 0.0,
                "fourws_optimizer_ratio_residual": 0.0,
                "fourws_intent": "path_mode_disabled",
                "fourws_heading_enabled": False,
                "fourws_heading_applied": False,
                "fourws_heading_applied_cols": 0,
                "fourws_heading_blend": 0.0,
                "fourws_heading_adjustment_raw_mean": 0.0,
                "fourws_heading_adjustment_raw_max_abs": 0.0,
                "fourws_local_path_enabled": False,
                "fourws_local_path_applied": False,
                "fourws_local_path_applied_cols": 0,
                "fourws_local_path_blend": 0.0,
                "fourws_local_path_lateral_scale": 1.0,
                "fourws_local_path_lateral_delta_mean": 0.0,
                "fourws_local_path_lateral_delta_max_abs": 0.0,
                "fourws_local_path_heading_clip_rad": 0.0,
                "fourws_local_path_fallback_reason": "path_mode_disabled",
                "fallback_reason": "path_mode_disabled",
                "fallback_reasons": ["path_mode_disabled"],
                "index_mode": str(method_cfg.get("temporary_path_preview_index_mode", "k")),
                "base_index_mode_effective": "path_mode_disabled",
                "base_index_mode_requested": str(method_cfg.get("temporary_path_preview_index_mode", "k")),
                "base_index_s_grid_configured": False,
                "base_index_s_grid_valid": False,
                "base_index_s_grid_status": "path_mode_disabled",
                "s_lookup": str(method_cfg.get("temporary_path_preview_s_lookup", "nearest")),
                "nominal_start_col": int(nominal_start),
                "base_start_col": int(nominal_start),
                "start_col": int(nominal_start),
                "start_col_before_clamp": int(nominal_start),
                "window_width": int(xref_current.shape[1]) if xref_current.ndim == 2 else 0,
                "requested_preview_shift_steps": 0.0,
                "clipped_preview_shift_steps": 0.0,
                "configured_preview_shift_steps": 0,
                "candidate_preview_shift_steps_before_clamp": 0,
                "candidate_preview_shift_steps": 0,
                "candidate_shift_before_clamp": 0,
                "candidate_shift_clamped": False,
                "applied_preview_shift_steps": 0,
                "requested_shift_steps": 0.0,
                "clipped_shift_steps": 0.0,
                "configured_shift_steps": 0,
                "candidate_shift_steps_before_clamp": 0,
                "candidate_shift_steps": 0,
                "actual_preview_shift_steps": 0,
                "effective_preview_shift_steps": 0.0,
                "blend_weight": 0.0,
                "max_shift_steps": 0.0,
                "max_candidate_shift_steps": 0.0,
                "leading_pad_cols": 0,
                "terminal_pad_cols": 0,
                "terminal_pad_overshoot_cols": 0,
            }
        preview_mode_requested = temporary_path_preview_mode or "shift"
        preview_mode_key = preview_mode_requested.replace("-", "_").strip()
        mode_fallback_reason = "none"
        if preview_mode_key in (
            "fourws_geometric",
            "four_ws_geometric",
            "4ws_geometric",
            "geometric",
            "fourws_heading",
            "four_ws_heading",
            "4ws_heading",
            "fourws_local_path",
            "four_ws_local_path",
        ):
            return _compute_upper_layer_fourws_preview(
                k_value,
                vehicle_index,
                xref_nominal,
                ref_mat,
                s_value,
                trigger_s,
                active=active,
                trigger_s_source=trigger_s_source,
                preview_mode_requested=preview_mode_requested,
            )
        if preview_mode_key not in ("shift", "legacy_shift", "column_shift", ""):
            mode_fallback_reason = f"unsupported_preview_mode:{preview_mode_requested}"

        shift_cfg = _cfg_vector(
            method_cfg.get("temporary_path_preview_shift_steps", 0),
            num_vehicles,
            0.0,
        )
        requested_shift = float(shift_cfg[int(vehicle_index)])
        max_shift_cfg = method_cfg.get("temporary_path_preview_max_shift_steps", None)
        if max_shift_cfg is None:
            max_shift = abs(requested_shift)
        else:
            max_shift_vec = _cfg_vector(max_shift_cfg, num_vehicles, abs(requested_shift))
            max_shift = max(0.0, float(max_shift_vec[int(vehicle_index)]))
        clipped_shift = float(np.clip(requested_shift, -max_shift, max_shift))
        shift_steps = int(np.rint(clipped_shift))
        base_start, base_index_meta = _temporary_path_preview_base_index(
            ref_mat, k_value, trigger_s, vehicle_index=vehicle_index
        )
        start_col_raw = int(base_start + shift_steps)
        candidate_shift_before_clamp = int(start_col_raw - nominal_start)
        max_candidate_shift_cfg = method_cfg.get(
            "temporary_path_preview_max_candidate_shift_steps", None
        )
        if max_candidate_shift_cfg is None:
            max_candidate_shift = max(float(abs(shift_steps)), float(max_shift))
        else:
            max_candidate_shift_vec = _cfg_vector(
                max_candidate_shift_cfg, num_vehicles, max_shift
            )
            max_candidate_shift = max(0.0, float(max_candidate_shift_vec[int(vehicle_index)]))
        if np.isfinite(max_candidate_shift):
            candidate_shift = int(
                np.clip(
                    candidate_shift_before_clamp,
                    -float(max_candidate_shift),
                    float(max_candidate_shift),
                )
            )
        else:
            candidate_shift = int(candidate_shift_before_clamp)
        candidate_shift_clamped = bool(candidate_shift != candidate_shift_before_clamp)
        start_col = int(nominal_start + candidate_shift)
        blend_weight = _temporary_path_preview_blend_weight(active, trigger_s)
        shifted_win, leading_pad, terminal_pad, terminal_overshoot = _slice_ref_window_padded(
            ref_mat, start_col, xref_current.shape[1]
        )
        applied = bool(active and blend_weight > 1e-12 and xref_current.shape == shifted_win.shape)
        if applied:
            xref_preview = (1.0 - blend_weight) * xref_current + blend_weight * shifted_win
        else:
            xref_preview = xref_current
        applied_shift = int(candidate_shift) if applied else 0
        effective_shift = float(blend_weight * candidate_shift) if applied else 0.0
        diag = {
            "step": int(k_value),
            "vehicle_index": int(vehicle_index),
            "enabled": bool(use_temporary_path_preview),
            "active": bool(active),
            "applied": bool(applied),
            "s": float(vehicle_s),
            "vehicle_s": float(vehicle_s),
            "trigger_s": float(trigger_s),
            "trigger_s_source": str(trigger_s_source),
            "use_ref_s": bool(temporary_path_preview_use_ref_s),
            "trigger_mode": str(method_cfg.get("temporary_path_preview_trigger_mode", "s")),
            "preview_mode_requested": str(preview_mode_requested),
            "preview_mode": "shift",
            "geometric_preview_applied": False,
            "lookahead_m_requested": 0.0,
            "lookahead_m": 0.0,
            "lookahead_min_m": None,
            "lookahead_max_m": None,
            "lookahead_clipped": False,
            "target_s": None,
            "target_start_col": int(start_col),
            "target_start_col_raw": int(start_col_raw),
            "target_lookup_source": "shift_mode",
            "target_lookup_valid": True,
            "target_lookup_clamped": False,
            "front_delta_est": 0.0,
            "rear_delta_est": 0.0,
            "curvature_est": 0.0,
            "curvature_source": "not_used_shift_mode",
            "curvature_reliable": False,
            "fourws_intent": "not_used_shift_mode",
            "fallback_reason": str(mode_fallback_reason),
            "fallback_reasons": [] if mode_fallback_reason == "none" else [mode_fallback_reason],
            "index_mode": str(method_cfg.get("temporary_path_preview_index_mode", "k")),
            "base_index_mode_effective": str(
                base_index_meta.get("base_index_mode_effective", "k_relative")
            ),
            "base_index_mode_requested": str(
                base_index_meta.get("base_index_mode_requested", "k")
            ),
            "base_index_s_grid_configured": bool(
                base_index_meta.get("base_index_s_grid_configured", False)
            ),
            "base_index_s_grid_valid": bool(
                base_index_meta.get("base_index_s_grid_valid", False)
            ),
            "base_index_s_grid_status": str(
                base_index_meta.get("base_index_s_grid_status", "not_used")
            ),
            "s_lookup": str(method_cfg.get("temporary_path_preview_s_lookup", "nearest")),
            "nominal_start_col": int(nominal_start),
            "base_start_col": int(base_start),
            "start_col": int(start_col),
            "start_col_before_clamp": int(start_col_raw),
            "window_width": int(xref_current.shape[1]),
            "requested_preview_shift_steps": requested_shift,
            "clipped_preview_shift_steps": clipped_shift,
            "configured_preview_shift_steps": int(shift_steps),
            "candidate_preview_shift_steps_before_clamp": int(candidate_shift_before_clamp),
            "candidate_preview_shift_steps": int(candidate_shift),
            "candidate_shift_before_clamp": int(candidate_shift_before_clamp),
            "candidate_shift_clamped": bool(candidate_shift_clamped),
            "applied_preview_shift_steps": int(applied_shift),
            "requested_shift_steps": requested_shift,
            "clipped_shift_steps": clipped_shift,
            "configured_shift_steps": int(shift_steps),
            "candidate_shift_steps_before_clamp": int(candidate_shift_before_clamp),
            "candidate_shift_steps": int(candidate_shift),
            "actual_preview_shift_steps": int(applied_shift),
            "effective_preview_shift_steps": float(effective_shift),
            "blend_weight": float(blend_weight),
            "max_shift_steps": float(max_shift),
            "max_candidate_shift_steps": float(max_candidate_shift),
            "leading_pad_cols": int(leading_pad),
            "terminal_pad_cols": int(terminal_pad),
            "terminal_pad_overshoot_cols": int(terminal_overshoot),
        }
        return xref_preview, diag

    def _summarize_temporary_path_preview_step(k_value, diag_step):
        items = list(diag_step)
        def _safe_float(value, default=0.0):
            try:
                out = float(value)
            except (TypeError, ValueError):
                return float(default)
            return out if np.isfinite(out) else float(default)

        requested_shifts = [float(d.get("requested_preview_shift_steps", d.get("requested_shift_steps", 0.0))) for d in items]
        configured_shifts = [
            float(d.get("configured_preview_shift_steps", d.get("configured_shift_steps", 0.0)))
            for d in items
        ]
        candidate_shifts = [float(d.get("candidate_preview_shift_steps", 0.0)) for d in items]
        candidate_shifts_before_clamp = [
            float(d.get("candidate_preview_shift_steps_before_clamp", d.get("candidate_shift_before_clamp", 0.0)))
            for d in items
        ]
        applied_shifts = [
            float(d.get("applied_preview_shift_steps", d.get("actual_preview_shift_steps", 0.0)))
            for d in items
        ]
        eff_shifts = [float(d.get("effective_preview_shift_steps", 0.0)) for d in items]
        weights = [float(d.get("blend_weight", 0.0)) for d in items]
        active_flags = [bool(d.get("active", False)) for d in items]
        applied_flags = [bool(d.get("applied", False)) for d in items]
        candidate_clamped_flags = [bool(d.get("candidate_shift_clamped", False)) for d in items]
        base_index_modes = [str(d.get("base_index_mode_effective", "k_relative")) for d in items]
        terminal_pads = [int(d.get("terminal_pad_cols", 0)) for d in items]
        terminal_overshoots = [int(d.get("terminal_pad_overshoot_cols", 0)) for d in items]
        leading_pads = [int(d.get("leading_pad_cols", 0)) for d in items]
        trigger_s_values = [float(d.get("trigger_s", d.get("s", 0.0))) for d in items]
        vehicle_s_values = [float(d.get("vehicle_s", d.get("s", 0.0))) for d in items]
        preview_modes = [str(d.get("preview_mode", "shift")) for d in items]
        geometric_flags = [bool(d.get("geometric_preview_applied", False)) for d in items]
        lookahead_values = [_safe_float(d.get("lookahead_m", 0.0), 0.0) for d in items]
        target_s_values = [_safe_float(d.get("target_s", np.nan), np.nan) for d in items]
        target_s_sources = [str(d.get("target_s_source", "not_used_shift_mode")) for d in items]
        target_cols = [int(d.get("target_start_col", d.get("start_col", 0))) for d in items]
        front_delta_values = [_safe_float(d.get("front_delta_est", 0.0), 0.0) for d in items]
        rear_delta_values = [_safe_float(d.get("rear_delta_est", 0.0), 0.0) for d in items]
        optimizer_enabled_flags = [bool(d.get("fourws_optimizer_enabled", False)) for d in items]
        optimizer_modes = [str(d.get("fourws_optimizer_mode", "not_used")) for d in items]
        steering_logics = [str(d.get("fourws_steering_logic", "not_used")) for d in items]
        steering_relations = [str(d.get("fourws_steering_relation", "not_used")) for d in items]
        optimizer_objectives = [
            _safe_float(d.get("fourws_optimizer_objective", 0.0), 0.0) for d in items
        ]
        optimizer_curvature_errors = [
            _safe_float(d.get("fourws_optimizer_curvature_error", 0.0), 0.0) for d in items
        ]
        optimizer_sideslip_betas = [
            _safe_float(d.get("fourws_optimizer_sideslip_beta", 0.0), 0.0) for d in items
        ]
        optimizer_ratio_residuals = [
            _safe_float(d.get("fourws_optimizer_ratio_residual", 0.0), 0.0) for d in items
        ]
        heading_enabled_flags = [bool(d.get("fourws_heading_enabled", False)) for d in items]
        heading_applied_flags = [bool(d.get("fourws_heading_applied", False)) for d in items]
        heading_blends = [_safe_float(d.get("fourws_heading_blend", 0.0), 0.0) for d in items]
        heading_adjustments = [
            _safe_float(d.get("fourws_heading_adjustment_raw_mean", 0.0), 0.0)
            for d in items
        ]
        heading_adjustment_peaks = [
            _safe_float(d.get("fourws_heading_adjustment_raw_max_abs", 0.0), 0.0)
            for d in items
        ]
        heading_applied_cols = [int(d.get("fourws_heading_applied_cols", 0)) for d in items]
        local_path_enabled_flags = [bool(d.get("fourws_local_path_enabled", False)) for d in items]
        local_path_applied_flags = [bool(d.get("fourws_local_path_applied", False)) for d in items]
        local_path_blends = [_safe_float(d.get("fourws_local_path_blend", 0.0), 0.0) for d in items]
        local_path_deltas = [
            _safe_float(d.get("fourws_local_path_lateral_delta_mean", 0.0), 0.0)
            for d in items
        ]
        local_path_delta_peaks = [
            _safe_float(d.get("fourws_local_path_lateral_delta_max_abs", 0.0), 0.0)
            for d in items
        ]
        local_path_applied_cols = [int(d.get("fourws_local_path_applied_cols", 0)) for d in items]
        body_longs = [_safe_float(d.get("fourws_body_offset_longitudinal_m", 0.0), 0.0) for d in items]
        body_lats = [_safe_float(d.get("fourws_body_offset_lateral_m", 0.0), 0.0) for d in items]
        curvature_cmds = [_safe_float(d.get("fourws_curvature_cmd", 0.0), 0.0) for d in items]
        sideslip_betas = [_safe_float(d.get("fourws_sideslip_beta", 0.0), 0.0) for d in items]
        fallback_reasons = [str(d.get("fallback_reason", "none")) for d in items]
        fourws_intents = [str(d.get("fourws_intent", "not_used_shift_mode")) for d in items]
        curvature_sources = [str(d.get("curvature_source", "not_used_shift_mode")) for d in items]
        lookahead_finite = [x for x in lookahead_values if np.isfinite(x)]
        target_s_finite = [x for x in target_s_values if np.isfinite(x)]
        front_delta_finite = [x for x in front_delta_values if np.isfinite(x)]
        rear_delta_finite = [x for x in rear_delta_values if np.isfinite(x)]
        preview_mode_step = preview_modes[0] if preview_modes and len(set(preview_modes)) == 1 else "mixed"
        return {
            "step": int(k_value),
            "enabled": bool(use_temporary_path_preview),
            "use_ref_s": bool(temporary_path_preview_use_ref_s),
            "preview_mode": str(preview_mode_step),
            "preview_mode_by_vehicle": preview_modes,
            "active_per_vehicle": active_flags,
            "applied_per_vehicle": applied_flags,
            "geometric_preview_applied_by_vehicle": geometric_flags,
            "geometric_preview_applied_count": int(np.sum(geometric_flags)) if geometric_flags else 0,
            "geometric_preview_applied_ratio": float(np.mean(geometric_flags)) if geometric_flags else 0.0,
            "lookahead_m_by_vehicle": lookahead_values,
            "lookahead_m_mean": float(np.mean(lookahead_finite)) if lookahead_finite else 0.0,
            "target_s_by_vehicle": target_s_values,
            "target_s_source_by_vehicle": target_s_sources,
            "target_s_mean": float(np.mean(target_s_finite)) if target_s_finite else np.nan,
            "target_start_col_by_vehicle": target_cols,
            "front_delta_est_by_vehicle": front_delta_values,
            "front_delta_est_mean": float(np.mean(front_delta_finite)) if front_delta_finite else 0.0,
            "front_delta_est_max_abs": float(np.max(np.abs(front_delta_finite))) if front_delta_finite else 0.0,
            "rear_delta_est_by_vehicle": rear_delta_values,
            "rear_delta_est_mean": float(np.mean(rear_delta_finite)) if rear_delta_finite else 0.0,
            "rear_delta_est_max_abs": float(np.max(np.abs(rear_delta_finite))) if rear_delta_finite else 0.0,
            "fourws_optimizer_enabled_by_vehicle": optimizer_enabled_flags,
            "fourws_optimizer_enabled_ratio": (
                float(np.mean(optimizer_enabled_flags)) if optimizer_enabled_flags else 0.0
            ),
            "fourws_optimizer_mode_by_vehicle": optimizer_modes,
            "fourws_steering_logic_by_vehicle": steering_logics,
            "fourws_steering_relation_by_vehicle": steering_relations,
            "fourws_optimizer_objective_mean": (
                float(np.mean(optimizer_objectives)) if optimizer_objectives else 0.0
            ),
            "fourws_optimizer_curvature_error_mean": (
                float(np.mean(optimizer_curvature_errors)) if optimizer_curvature_errors else 0.0
            ),
            "fourws_optimizer_curvature_error_max_abs": (
                float(np.max(np.abs(optimizer_curvature_errors)))
                if optimizer_curvature_errors
                else 0.0
            ),
            "fourws_optimizer_sideslip_beta_max_abs": (
                float(np.max(np.abs(optimizer_sideslip_betas)))
                if optimizer_sideslip_betas
                else 0.0
            ),
            "fourws_optimizer_ratio_residual_max_abs": (
                float(np.max(np.abs(optimizer_ratio_residuals)))
                if optimizer_ratio_residuals
                else 0.0
            ),
            "fourws_heading_enabled_by_vehicle": heading_enabled_flags,
            "fourws_heading_enabled_ratio": float(np.mean(heading_enabled_flags)) if heading_enabled_flags else 0.0,
            "fourws_heading_applied_by_vehicle": heading_applied_flags,
            "fourws_heading_applied_count": int(np.sum(heading_applied_flags)) if heading_applied_flags else 0,
            "fourws_heading_applied_ratio": float(np.mean(heading_applied_flags)) if heading_applied_flags else 0.0,
            "fourws_heading_applied_cols_by_vehicle": heading_applied_cols,
            "fourws_heading_blend_mean": float(np.mean(heading_blends)) if heading_blends else 0.0,
            "fourws_heading_adjustment_raw_mean": float(np.mean(heading_adjustments)) if heading_adjustments else 0.0,
            "fourws_heading_adjustment_raw_max_abs": (
                float(np.max(heading_adjustment_peaks)) if heading_adjustment_peaks else 0.0
            ),
            "fourws_local_path_enabled_by_vehicle": local_path_enabled_flags,
            "fourws_local_path_enabled_ratio": (
                float(np.mean(local_path_enabled_flags)) if local_path_enabled_flags else 0.0
            ),
            "fourws_local_path_applied_by_vehicle": local_path_applied_flags,
            "fourws_local_path_applied_count": (
                int(np.sum(local_path_applied_flags)) if local_path_applied_flags else 0
            ),
            "fourws_local_path_applied_ratio": (
                float(np.mean(local_path_applied_flags)) if local_path_applied_flags else 0.0
            ),
            "fourws_local_path_applied_cols_by_vehicle": local_path_applied_cols,
            "fourws_local_path_blend_mean": float(np.mean(local_path_blends)) if local_path_blends else 0.0,
            "fourws_local_path_lateral_delta_mean": (
                float(np.mean(local_path_deltas)) if local_path_deltas else 0.0
            ),
            "fourws_local_path_lateral_delta_max_abs": (
                float(np.max(local_path_delta_peaks)) if local_path_delta_peaks else 0.0
            ),
            "fourws_body_offset_longitudinal_m_mean": float(np.mean(body_longs)) if body_longs else 0.0,
            "fourws_body_offset_lateral_m_mean": float(np.mean(body_lats)) if body_lats else 0.0,
            "fourws_curvature_cmd_mean": float(np.mean(curvature_cmds)) if curvature_cmds else 0.0,
            "fourws_sideslip_beta_mean": float(np.mean(sideslip_betas)) if sideslip_betas else 0.0,
            "fallback_reason_by_vehicle": fallback_reasons,
            "fourws_intent_by_vehicle": fourws_intents,
            "curvature_source_by_vehicle": curvature_sources,
            "active_count": int(np.sum(active_flags)) if active_flags else 0,
            "active_ratio": float(np.mean(active_flags)) if active_flags else 0.0,
            "applied_ratio": float(np.mean(applied_flags)) if applied_flags else 0.0,
            "requested_preview_shift_steps_by_vehicle": requested_shifts,
            "configured_preview_shift_steps_by_vehicle": [int(np.rint(x)) for x in configured_shifts],
            "candidate_preview_shift_steps_before_clamp_by_vehicle": [
                int(np.rint(x)) for x in candidate_shifts_before_clamp
            ],
            "candidate_preview_shift_steps_by_vehicle": [int(np.rint(x)) for x in candidate_shifts],
            "applied_preview_shift_steps_by_vehicle": [int(np.rint(x)) for x in applied_shifts],
            "actual_preview_shift_steps_by_vehicle": [int(np.rint(x)) for x in applied_shifts],
            "effective_preview_shift_steps_by_vehicle": eff_shifts,
            "candidate_shift_clamped_by_vehicle": candidate_clamped_flags,
            "candidate_shift_clamped_count": int(np.sum(candidate_clamped_flags)) if candidate_clamped_flags else 0,
            "candidate_shift_clamped_any": bool(np.any(candidate_clamped_flags)) if candidate_clamped_flags else False,
            "base_index_mode_effective_by_vehicle": base_index_modes,
            "requested_preview_shift_steps_mean": float(np.mean(requested_shifts)) if requested_shifts else 0.0,
            "requested_preview_shift_steps_max_abs": float(np.max(np.abs(requested_shifts))) if requested_shifts else 0.0,
            "configured_preview_shift_steps_mean": float(np.mean(configured_shifts)) if configured_shifts else 0.0,
            "configured_preview_shift_steps_max_abs": float(np.max(np.abs(configured_shifts))) if configured_shifts else 0.0,
            "candidate_preview_shift_steps_before_clamp_mean": float(
                np.mean(candidate_shifts_before_clamp)
            ) if candidate_shifts_before_clamp else 0.0,
            "candidate_preview_shift_steps_before_clamp_max_abs": float(
                np.max(np.abs(candidate_shifts_before_clamp))
            ) if candidate_shifts_before_clamp else 0.0,
            "candidate_preview_shift_steps_mean": float(np.mean(candidate_shifts)) if candidate_shifts else 0.0,
            "candidate_preview_shift_steps_max_abs": float(np.max(np.abs(candidate_shifts))) if candidate_shifts else 0.0,
            "applied_preview_shift_steps_mean": float(np.mean(applied_shifts)) if applied_shifts else 0.0,
            "applied_preview_shift_steps_max_abs": float(np.max(np.abs(applied_shifts))) if applied_shifts else 0.0,
            "actual_preview_shift_steps_mean": float(np.mean(applied_shifts)) if applied_shifts else 0.0,
            "actual_preview_shift_steps_max_abs": float(np.max(np.abs(applied_shifts))) if applied_shifts else 0.0,
            "effective_preview_shift_steps_mean": float(np.mean(eff_shifts)) if eff_shifts else 0.0,
            "effective_preview_shift_steps_max_abs": float(np.max(np.abs(eff_shifts))) if eff_shifts else 0.0,
            "blend_weight_mean": float(np.mean(weights)) if weights else 0.0,
            "blend_weight_max": float(np.max(weights)) if weights else 0.0,
            "vehicle_s_by_vehicle": vehicle_s_values,
            "trigger_s_by_vehicle": trigger_s_values,
            "leading_pad_cols_by_vehicle": leading_pads,
            "terminal_pad_cols_by_vehicle": terminal_pads,
            "terminal_pad_cols_max": int(np.max(terminal_pads)) if terminal_pads else 0,
            "terminal_pad_overshoot_cols_by_vehicle": terminal_overshoots,
            "terminal_pad_overshoot_cols_max": int(np.max(terminal_overshoots)) if terminal_overshoots else 0,
            "vehicle_diag": items,
        }

    def _spatial_lateral_switch_profile(s_value: float, curvature_value: float) -> Dict[str, Any]:
        if not bool(method_cfg.get("spatial_lateral_switch_enabled", False)):
            return {"enabled": False, "phase": "off", "pre_gain": 0.0, "lateral_gain": 0.0}
        s_val = float(s_value)
        kappa_abs = abs(float(curvature_value))
        ramp_s = float(method_cfg.get("spatial_switch_ramp_s", 0.65))
        pre_gain = _smooth_box_gain(
            s_val,
            float(method_cfg.get("spatial_pre_start_s", 30.0)),
            float(method_cfg.get("spatial_pre_end_s", 35.0)),
            ramp_s,
        )
        if kappa_abs < float(method_cfg.get("spatial_pre_kappa_threshold", 0.0)):
            pre_gain = 0.0
        lat_start = float(method_cfg.get("spatial_lateral_start_s", 35.0))
        lat_full_end = float(method_cfg.get("spatial_lateral_full_end_s", 42.0))
        lat_exit_end = float(method_cfg.get("spatial_lateral_exit_end_s", 50.0))
        lateral_gain = 0.0
        if lat_start <= s_val <= lat_full_end:
            lateral_gain = _smooth_step01((s_val - lat_start) / ramp_s)
        elif lat_full_end < s_val <= lat_exit_end:
            lateral_gain = 1.0 - _smooth_step01((s_val - lat_full_end) / max(lat_exit_end - lat_full_end, 1e-6))
        if kappa_abs < float(method_cfg.get("spatial_lateral_kappa_threshold", 0.0)):
            lateral_gain = 0.0
        phase = "off"
        if pre_gain > 1e-6:
            phase = "pre_decel"
        if lateral_gain > 1e-6:
            phase = "lateral_priority" if s_val <= lat_full_end else "exit_restore"
        return {
            "enabled": True,
            "phase": phase,
            "pre_gain": float(pre_gain),
            "lateral_gain": float(lateral_gain),
        }

    q_base_case = _scaled_sparse_diagonal(
        ctx["Q_base_lin"],
        {
            0: "mpc_q_s_scale",
            1: "mpc_q_ey_scale",
            2: "mpc_q_epsi_scale",
            3: "mpc_q_vx_scale",
            4: "mpc_q_vy_scale",
            5: "mpc_q_r_scale",
        },
    )
    qn_base_case = _scaled_sparse_diagonal(
        ctx["QN_base_lin"],
        {
            0: "mpc_qn_s_scale",
            1: "mpc_qn_ey_scale",
            2: "mpc_qn_epsi_scale",
            3: "mpc_qn_vx_scale",
            4: "mpc_qn_vy_scale",
            5: "mpc_qn_r_scale",
        },
    )
    r_base_case = _scaled_sparse_diagonal(
        ctx["R_mpc_lin_noadapt"],
        {
            0: "mpc_r_delta_scale",
            1: "mpc_r_ax_scale",
        },
    )

    controllers_case = []
    weight_memory = [{"ey": 1.0, "epsi": 1.0, "r": 1.0} for _ in range(num_vehicles)]
    stability_guard = RigidPayloadStabilityGuardA1V2(
        beta_limit=method_cfg.get("guard_beta_limit", 0.22),
        r_limit=method_cfg.get("guard_r_limit", 0.62),
    )
    progress_supervisor = A1ProgressSupervisorV2(
        lag_activate_s=method_cfg.get("progress_lag_activate_s", 1.2),
        lag_full_s=method_cfg.get("progress_lag_full_s", 4.5),
        stable_ey=method_cfg.get("progress_stable_ey", 0.55),
        stable_epsi=method_cfg.get("progress_stable_epsi", 0.24),
        stable_beta=method_cfg.get("progress_stable_beta", 0.18),
        stable_r=method_cfg.get("progress_stable_r", 0.75),
        recover_ax_min=method_cfg.get("progress_recover_ax_min", -0.12),
        recover_ax_max=method_cfg.get("progress_recover_ax_max", 0.65),
    )
    comm_consensus = CommAwareConsensusTF12(
        num_vehicles=num_vehicles,
        dt=ctx["dt"],
        seed=int(ctx["RUN_CFG"]["seed"]) + int(method_cfg.get("comm_seed_offset", 1200)),
        packet_loss_base=method_cfg.get("comm_packet_loss_base", 0.03),
        packet_loss_gain=method_cfg.get("comm_packet_loss_gain", 0.20),
        delay_steps_max=method_cfg.get("comm_delay_steps_max", 3),
        delay_bias=method_cfg.get("comm_delay_bias", 0.35),
        quality_smooth_beta=method_cfg.get("comm_quality_smooth_beta", 0.80),
        quality_tau_steps=method_cfg.get("comm_quality_tau_steps", 3.0),
        consensus_blend_min=method_cfg.get("comm_consensus_blend_min", 0.10),
        consensus_blend_max=method_cfg.get("comm_consensus_blend_max", 0.70),
        tighten_max_frac=method_cfg.get("comm_tighten_max_frac", 0.26),
        degrade_threshold=method_cfg.get("comm_degrade_threshold", 0.45),
        degrade_delta_scale=method_cfg.get("comm_degrade_delta_scale", 0.60),
    )
    tf14_fdi_monitor = OnlineFDIMonitorTF14(
        num_vehicles=num_vehicles,
        dt=ctx["dt"],
        mass=ctx["sys_pars"]["m"],
        Iz=ctx["sys_pars"]["Iz"],
        lf=ctx["sys_pars"]["lf"],
        lr=ctx["sys_pars"]["lr"],
        Cf=ctx["sys_pars"]["Cf"],
        Cr=ctx["sys_pars"]["Cr"],
        residual_ewma_beta=method_cfg.get("tf14_residual_ewma_beta", 0.82),
        residual_cusum_drift=method_cfg.get("tf14_residual_cusum_drift", 0.015),
        residual_cusum_leak=method_cfg.get("tf14_residual_cusum_leak", 0.92),
        residual_threshold=method_cfg.get("tf14_residual_threshold", 0.18),
        residual_cusum_threshold=method_cfg.get("tf14_residual_cusum_threshold", 0.30),
        detect_hold_steps=method_cfg.get("tf14_detect_hold_steps", 5),
        release_hold_steps=method_cfg.get("tf14_release_hold_steps", 10),
        ax_eff_fault_threshold=method_cfg.get("tf14_ax_eff_fault_threshold", 0.72),
        delta_eff_fault_threshold=method_cfg.get("tf14_delta_eff_fault_threshold", 0.74),
        severe_eff_threshold=method_cfg.get("tf14_severe_eff_threshold", 0.35),
        eff_smooth_beta=method_cfg.get("tf14_eff_smooth_beta", 0.88),
        cmd_deadzone_delta=method_cfg.get("tf14_cmd_deadzone_delta", 1.5e-3),
        cmd_deadzone_ax=method_cfg.get("tf14_cmd_deadzone_ax", 2.0e-2),
        min_valid_delta_cmd=method_cfg.get("tf14_min_valid_delta_cmd", 0.025),
        min_valid_ax_cmd=method_cfg.get("tf14_min_valid_ax_cmd", 0.10),
        warmup_steps=method_cfg.get("tf14_fdi_warmup_steps", 12),
    )
    tf14_switcher = ReconfigurableFTCControllerTF14(
        num_vehicles=num_vehicles,
        umin=ctx["umin_lin_noadapt"],
        umax=ctx["umax_lin_noadapt"],
        switch_dwell_steps=method_cfg.get("tf14_switch_dwell_steps", 6),
        activation_confidence=method_cfg.get("tf14_switch_activation_confidence", 0.28),
        safe_confidence=method_cfg.get("tf14_switch_safe_confidence", 0.70),
        redistribution_gain=method_cfg.get("tf14_redistribution_gain", 1.00),
        safe_global_delta_scale=method_cfg.get("tf14_safe_global_delta_scale", 0.80),
        safe_global_ax_scale=method_cfg.get("tf14_safe_global_ax_scale", 0.75),
    )
    phase_role_scheduler = PhaseRoleSchedulerTF14(
        num_vehicles=num_vehicles,
        dt=ctx["dt"],
        umin=ctx["umin_lin_noadapt"],
        umax=ctx["umax_lin_noadapt"],
        cfg=dict(method_cfg.get("phase_role_cfg", {})),
    )
    tf14_certificate = SwitchedFTCCertificateTF14(
        dt=ctx["dt"],
        lambda_nominal=method_cfg.get("tf14_lambda_nominal", 0.08),
        lambda_reconfigured=method_cfg.get("tf14_lambda_reconfigured", 0.06),
        lambda_safe=method_cfg.get("tf14_lambda_safe", 0.04),
        gamma_disturbance=method_cfg.get("tf14_gamma_disturbance", 0.85),
        gamma_identification=method_cfg.get("tf14_gamma_identification", 0.55),
    )
    for v in range(num_vehicles):
        x_init_raw_v = np.tile(init_local_states[v], (n_case + 1, 1))
        u_init_v = np.zeros((n_case, num_inputs))
        z_init_v = np.zeros((n_case + 1, nz_case))
        for ii in range(n_case + 1):
            z_init_v[ii, :] = lift_fn(x_init_raw_v[ii, :])

        ppc_params = {
            "rho_ey_0": ctx["PPC_CFG"]["rho_ey_0"],
            "rho_ey_inf": ctx["PPC_CFG"]["rho_ey_inf"],
            "lambda_ey": ctx["PPC_CFG"]["lambda_ey"],
            "rho_epsi_0": ctx["PPC_CFG"]["rho_epsi_0"],
            "rho_epsi_inf": ctx["PPC_CFG"]["rho_epsi_inf"],
            "lambda_epsi": ctx["PPC_CFG"]["lambda_epsi"],
        }
        for ppc_key in list(ppc_params.keys()):
            if ppc_key in method_cfg:
                ppc_params[ppc_key] = float(method_cfg[ppc_key])
            scale_key = f"{ppc_key}_scale"
            if scale_key in method_cfg:
                ppc_params[ppc_key] = float(ppc_params[ppc_key]) * float(method_cfg[scale_key])

        ctrl_v = ctx["NonlinearMPCController"](
            dynamics_obj,
            n_case,
            ctx["dt"],
            ctx["umin_lin_noadapt"],
            ctx["umax_lin_noadapt"],
            ctx["xmin_lin_noadapt"],
            ctx["xmax_lin_noadapt"],
            q_base_case,
            r_base_case,
            qn_base_case,
            solver_settings_case,
            add_ppc_soft=use_ppc,
            q_slack_ey=float(method_cfg.get("q_slack_ey", 4e4)),
            q_slack_epsi=float(method_cfg.get("q_slack_epsi", 3e4)),
            p_slack_ey=float(method_cfg.get("p_slack_ey", 4e3)),
            p_slack_epsi=float(method_cfg.get("p_slack_epsi", 3e3)),
            ppc_params=ppc_params,
        )
        ctrl_v.construct_controller(z_init_v, u_init_v, x_ref_case_vehicles[v][:, :n_case + 1])
        controllers_case.append(ctrl_v)

    fail_counts_case = [0] * num_vehicles
    progress_guard_counts = [0] * num_vehicles
    progress_boost_count = 0
    solver_status_case = [[] for _ in range(num_vehicles)]
    terminated_early_case = False
    target_s_vehicles = [float(raw_ref_vehicle_hist[v][-1, 0]) for v in range(num_vehicles)]
    prev_local_states_for_fdi = np.vstack([xt_case[v][0, :].copy() for v in range(num_vehicles)])
    prev_u_sent_stack_for_fdi = np.zeros((num_vehicles, num_inputs), dtype=float)
    prev_u_meas_stack_for_fdi = np.zeros((num_vehicles, num_inputs), dtype=float)

    z_buf = []
    u_buf = []
    dz_buf = []
    adapt_mode = ctx["resolve_adapt_mode"](method_cfg, structure_name)
    adapt_A_norm_hist = []
    adapt_B_norm_hist = []
    prev_dA = np.zeros((nz_case, nz_case), dtype=np.float64)
    prev_dB = np.zeros_like(dynamics_obj.B.toarray(), dtype=np.float64)

    team_rng = np.random.default_rng(ctx["RUN_CFG"]["seed"])
    _, team_actual_pars, payload_change_mask = payload_module.build_team_parameter_scenarios(
        ctx["sys_pars"],
        ctx["sys_pars_new"],
        payload_cfg=payload_cfg,
        rng=team_rng,
        change_mask=change_mask,
    )
    team_actual_pars = _retune_rigid_team_parameters_a1(team_actual_pars, payload_cfg)
    team_actual_pars["rng"] = team_rng
    team_actual_pars["vx_ref"] = ctx["vx_nom"]
    team_actual_pars["uncertainty"] = str(method_cfg.get("uncertainty_mode", "NA"))
    team_actual_pars["amp"] = float(
        method_cfg.get("plant_amp", method_cfg.get("uncertainty_amp", 0.0))
    )
    team_actual_pars["freq"] = float(method_cfg.get("plant_freq", 1.0))
    team_actual_pars["s_ref"] = ctx["s_ref_path"]
    team_actual_pars["curvature_ref"] = ctx["curvature_ref_path"]
    team_actual_pars["s_upper"] = float(
        ctx["s_ref_path"][-1] + 2.0 * payload_cfg["payload_length"] + 10.0
    )
    team_actual_pars["payload_cfg"] = dict(payload_cfg)

    delta_alpha = float(method_cfg.get("delta_alpha", ctx["MPC_CFG"]["delta_alpha"]))
    ax_alpha = float(method_cfg.get("ax_alpha", ctx["MPC_CFG"]["ax_alpha"]))
    eval_snr_db = float(method_cfg.get("eval_snr_db", ctx["SNR_DB"]))
    mpc_decimation_steps = int(max(1, method_cfg.get("mpc_decimation_steps", 8)))
    min_solve_vehicles_per_step = int(
        max(0, min(num_vehicles, method_cfg.get("min_solve_vehicles_per_step", 0)))
    )
    mpc_skip_on_budget = bool(method_cfg.get("mpc_skip_on_budget", True))
    mpc_min_budget_left_sec = float(max(1e-4, method_cfg.get("mpc_min_budget_left_sec", 4.0e-3)))
    fast_max_sqp_iters = int(max(1, method_cfg.get("fast_max_sqp_iters", 1)))
    fast_time_limit = float(max(5e-4, method_cfg.get("fast_time_limit", 8.0e-4)))
    fast_time_limit_min = float(max(2e-4, method_cfg.get("fast_time_limit_min", 3.0e-4)))
    realtime_adapt_stride = int(max(1, method_cfg.get("realtime_adapt_stride", 12)))
    if fast_time_limit_min > fast_time_limit:
        fast_time_limit_min = fast_time_limit
    control_budget_cfg = method_cfg.get("realtime_control_budget_sec", None)
    if control_budget_cfg is None:
        step_budget_sec = float(ctx["dt"]) * float(max(0.10, method_cfg.get("realtime_budget_ratio", 0.65)))
    else:
        step_budget_sec = float(control_budget_cfg)
    step_budget_sec = float(max(1e-4, step_budget_sec))
    max_wall_time_sec = float(max(0.0, method_cfg.get("max_wall_time_sec", 0.0)))
    max_no_progress_steps = int(max(0, method_cfg.get("max_no_progress_steps", 0)))
    progress_eps_s = float(max(0.0, method_cfg.get("progress_eps_s", 1e-4)))

    step_runtime_hist = []
    step_overrun_count = 0
    solve_runtime_hist = []
    solve_skip_count = 0
    solve_success_count = 0
    begin_t = time.time()
    actual_sim_steps = sim_steps_cap
    leader_idx = ctx["leader_idx"]
    gc_disabled = False
    if realtime_mode and bool(method_cfg.get("realtime_disable_gc", True)) and gc.isenabled():
        gc.disable()
        gc_disabled = True

    show_progress_bar = bool(method_cfg.get("show_progress_bar", True))
    progress_desc = str(method_cfg.get("progress_desc", method_cfg.get("name", "TF12"))).strip()
    if len(progress_desc) == 0:
        progress_desc = "TF12"
    progress_unit = str(method_cfg.get("progress_unit", "it")).strip() or "it"
    progress_leave = bool(method_cfg.get("progress_leave", True))
    progress_mininterval = float(max(0.0, method_cfg.get("progress_mininterval", 0.2)))
    progress_colour = method_cfg.get("progress_colour", "#ff4d6d")
    progress_postfix_every = int(max(1, method_cfg.get("progress_postfix_every", 50)))
    progress_print_time = bool(method_cfg.get("progress_print_time", True))
    progress_bar = None
    if show_progress_bar:
        try:
            from tqdm import tqdm

            pbar_kwargs = {
                "total": int(sim_steps_cap),
                "desc": progress_desc,
                "unit": progress_unit,
                "dynamic_ncols": True,
                "leave": progress_leave,
                "mininterval": progress_mininterval,
            }
            if progress_colour is not None:
                pbar_kwargs["colour"] = str(progress_colour)
            progress_bar = tqdm(**pbar_kwargs)
        except Exception:
            progress_bar = None
    best_team_s = float(team_state_hist[0, 0])
    no_progress_steps = 0
    stop_reason = "sim_steps_cap_reached"

    comm_rng = np.random.default_rng(
        int(ctx["RUN_CFG"]["seed"]) + int(method_cfg.get("comm_restructure_seed_offset", 2400))
    )
    adjacent_pairs = _adjacent_vehicle_pairs(num_vehicles)
    adjacent_distance_targets = np.full((num_vehicles, num_vehicles), np.nan, dtype=float)
    adjacent_distance_error_filter = np.zeros((num_vehicles, num_vehicles), dtype=float)
    adjacent_distance_quality_holder = {"quality_global": 1.0}
    comm_local_state_history = []
    comm_team_state_history = []
    last_rel_measure = np.zeros((num_vehicles, num_vehicles, num_states), dtype=float)
    last_team_ey_measure = np.full(num_vehicles, float(team_state_hist[0, 1]), dtype=float)
    upper_lower_ref_history = [[] for _ in range(num_vehicles)]
    upper_lower_last_ref = [None for _ in range(num_vehicles)]
    upper_lower_cmd_history = []
    upper_lower_last_cmd = np.zeros((num_vehicles, num_inputs), dtype=float)

    def _adjacent_distance_info(distance=np.nan, source="unavailable", fallback_reason="none"):
        return {
            "distance": float(distance) if np.isfinite(distance) else np.nan,
            "target_source": str(source),
            "target_fallback_reason": str(fallback_reason),
        }

    def _adjacent_distance_unique_text(values, default="none"):
        unique = []
        for value in values:
            if isinstance(value, (list, tuple, set)):
                iterable = value
            else:
                iterable = (value,)
            for item in iterable:
                text = str(item).strip()
                if not text or text == "nan":
                    continue
                if text not in unique:
                    unique.append(text)
        if not unique:
            return str(default), []
        return ("|".join(unique), unique)

    def _adjacent_distance_positions_from_refs(refs_like, vehicle_index):
        ref_arr, status = _vehicle_ref_array_from_refs(refs_like, vehicle_index)
        if ref_arr is None:
            return None, status
        if ref_arr.ndim != 2 or ref_arr.shape[0] <= 0 or ref_arr.shape[1] <= 0:
            return None, "shape_mismatch"

        if ref_arr.shape[1] == num_states:
            pos = ref_arr[:, :2]
        elif ref_arr.shape[0] == num_states:
            pos = ref_arr[:2, :].T
        elif ref_arr.shape[1] <= 16 and ref_arr.shape[0] > ref_arr.shape[1]:
            pos = ref_arr[:, :2]
        elif ref_arr.shape[0] <= 16 and ref_arr.shape[1] >= ref_arr.shape[0]:
            pos = ref_arr[:2, :].T
        elif ref_arr.shape[0] >= ref_arr.shape[1] and ref_arr.shape[1] >= 2:
            pos = ref_arr[:, :2]
        elif ref_arr.shape[0] >= 2:
            pos = ref_arr[:2, :].T
        else:
            return None, "missing_position_components"

        pos = np.asarray(pos, dtype=float)
        if pos.ndim != 2 or pos.shape[0] <= 0 or pos.shape[1] < 2:
            return None, "shape_mismatch"
        return pos[:, :2], "ok"

    def _reference_adjacent_distance_info(receiver, sender, ref_index):
        rejected = []
        candidates = (
            ("raw_ref_vehicle_hist", raw_ref_vehicle_hist),
            ("ref_bundle.corner_ref_histories", ref_bundle.get("corner_ref_histories", None)),
            ("ref_bundle.raw_vehicle_refs", ref_bundle.get("raw_vehicle_refs", None)),
            ("ctx.raw_ref_vehicle_histories", ctx.get("raw_ref_vehicle_histories", None)),
            ("ctx.ref_vehicle_histories", ctx.get("ref_vehicle_histories", None)),
            ("ctx.a1_ref_vehicle_histories", ctx.get("a1_ref_vehicle_histories", None)),
        )
        for source, refs_like in candidates:
            pos_receiver, status_receiver = _adjacent_distance_positions_from_refs(
                refs_like, receiver
            )
            pos_sender, status_sender = _adjacent_distance_positions_from_refs(
                refs_like, sender
            )
            if pos_receiver is None or pos_sender is None:
                if status_receiver != "missing" or status_sender != "missing":
                    rejected.append(
                        f"{source}:receiver_{status_receiver}|sender_{status_sender}"
                    )
                continue

            n_cols = min(pos_receiver.shape[0], pos_sender.shape[0])
            if n_cols <= 0:
                rejected.append(f"{source}:empty")
                continue
            idx = int(np.clip(int(ref_index), 0, n_cols - 1))
            rel_ref = pos_sender[idx, :2] - pos_receiver[idx, :2]
            target = float(np.linalg.norm(rel_ref))
            if np.isfinite(target):
                return _adjacent_distance_info(
                    max(target, 0.0),
                    source,
                    "none",
                )
            rejected.append(f"{source}:nonfinite_distance")

        reason = "physical_reference_unavailable"
        if rejected:
            reason = f"{reason}:" + ";".join(rejected[-4:])
        return _adjacent_distance_info(np.nan, "physical_reference_unavailable", reason)

    def _reference_adjacent_distance(receiver, sender, ref_index):
        return float(
            _reference_adjacent_distance_info(receiver, sender, ref_index).get(
                "distance", np.nan
            )
        )

    def _adjacent_state_from_initial_stack(states_like, vehicle_index):
        if states_like is None:
            return None, "missing"
        veh_idx = int(np.clip(int(vehicle_index), 0, max(0, num_vehicles - 1)))
        try:
            if isinstance(states_like, (list, tuple)):
                if veh_idx >= len(states_like):
                    return None, "vehicle_index_out_of_range"
                state = np.asarray(states_like[veh_idx], dtype=float).reshape(-1)
            else:
                arr = np.asarray(states_like, dtype=float)
                if arr.ndim != 2:
                    return None, "shape_mismatch"
                if arr.shape[0] == num_vehicles:
                    state = arr[veh_idx, :].reshape(-1)
                elif arr.shape[1] == num_vehicles:
                    state = arr[:, veh_idx].reshape(-1)
                else:
                    return None, "vehicle_axis_not_found"
        except (TypeError, ValueError, IndexError):
            return None, "non_numeric"
        if state.size < 2 or not np.all(np.isfinite(state[:2])):
            return None, "invalid_position"
        return state, "ok"

    def _initial_adjacent_distance_info(receiver, sender, fallback_reason):
        rejected = []
        candidates = (
            ("x0_vehicles_initial_true_formation", x0_vehicles),
            ("init_local_states_current_initial", init_local_states),
        )
        for source, states_like in candidates:
            state_receiver, status_receiver = _adjacent_state_from_initial_stack(
                states_like, receiver
            )
            state_sender, status_sender = _adjacent_state_from_initial_stack(
                states_like, sender
            )
            if state_receiver is None or state_sender is None:
                if status_receiver != "missing" or status_sender != "missing":
                    rejected.append(
                        f"{source}:receiver_{status_receiver}|sender_{status_sender}"
                    )
                continue
            target = float(np.linalg.norm(state_sender[:2] - state_receiver[:2]))
            if np.isfinite(target):
                return _adjacent_distance_info(max(target, 0.0), source, fallback_reason)
            rejected.append(f"{source}:nonfinite_distance")

        reason = f"{fallback_reason};initial_distance_unavailable"
        if rejected:
            reason = f"{reason}:" + ";".join(rejected[-4:])
        return _adjacent_distance_info(np.nan, "unavailable", reason)

    adjacent_distance_target_sources = [
        ["not_applicable" for _ in range(num_vehicles)] for _ in range(num_vehicles)
    ]
    adjacent_distance_target_fallback_reasons = [
        ["not_applicable" for _ in range(num_vehicles)] for _ in range(num_vehicles)
    ]
    for receiver in range(num_vehicles):
        for sender in adjacent_pairs[receiver]:
            target_info = _reference_adjacent_distance_info(receiver, sender, 0)
            if not np.isfinite(target_info.get("distance", np.nan)):
                target_info = _initial_adjacent_distance_info(
                    receiver,
                    sender,
                    target_info.get(
                        "target_fallback_reason", "physical_reference_unavailable"
                    ),
                )
            adjacent_distance_targets[receiver, sender] = float(
                target_info.get("distance", np.nan)
            )
            adjacent_distance_target_sources[receiver][sender] = str(
                target_info.get("target_source", "unavailable")
            )
            adjacent_distance_target_fallback_reasons[receiver][sender] = str(
                target_info.get("target_fallback_reason", "none")
            )

    def _adjacent_distance_target_info(receiver, sender, ref_index):
        mode = adjacent_distance_target_mode
        if mode in ("reference_step", "step", "current_reference", "reference_current"):
            target_step = _reference_adjacent_distance_info(receiver, sender, ref_index)
            if np.isfinite(target_step.get("distance", np.nan)):
                return target_step
            return _initial_adjacent_distance_info(
                receiver,
                sender,
                target_step.get(
                    "target_fallback_reason", "physical_reference_unavailable"
                ),
            )
        try:
            target_init = float(adjacent_distance_targets[int(receiver), int(sender)])
            if np.isfinite(target_init):
                return _adjacent_distance_info(
                    max(target_init, 0.0),
                    adjacent_distance_target_sources[int(receiver)][int(sender)],
                    adjacent_distance_target_fallback_reasons[int(receiver)][int(sender)],
                )
        except Exception:
            pass
        target_fallback = _reference_adjacent_distance_info(receiver, sender, 0)
        if np.isfinite(target_fallback.get("distance", np.nan)):
            return target_fallback
        return _initial_adjacent_distance_info(
            receiver,
            sender,
            target_fallback.get(
                "target_fallback_reason", "physical_reference_unavailable"
            ),
        )

    def _adjacent_distance_target(receiver, sender, ref_index):
        return float(
            _adjacent_distance_target_info(receiver, sender, ref_index).get(
                "distance", np.nan
            )
        )

    def _adjacent_distance_target_meta_for_vehicle(vehicle_index, ref_index):
        sources = []
        reasons = []
        for sender in adjacent_pairs[int(vehicle_index)] if 0 <= int(vehicle_index) < num_vehicles else ():
            target_info = _adjacent_distance_target_info(vehicle_index, sender, ref_index)
            sources.append(target_info.get("target_source", "unavailable"))
            reasons.append(target_info.get("target_fallback_reason", "none"))
        source_text, source_list = _adjacent_distance_unique_text(sources)
        reason_text, reason_list = _adjacent_distance_unique_text(reasons)
        return {
            "target_source": source_text,
            "target_sources": source_list,
            "target_fallback_reason": reason_text,
            "target_fallback_reasons": reason_list,
        }

    def _adjacent_distance_control_base_diag(vehicle_index, k_value):
        target_meta = _adjacent_distance_target_meta_for_vehicle(vehicle_index, k_value)
        return {
            "step": int(k_value),
            "vehicle_index": int(vehicle_index),
            "enabled": bool(use_adjacent_distance_control),
            "active": False,
            "reason": "disabled" if not use_adjacent_distance_control else "inactive",
            "target_mode": str(adjacent_distance_target_mode),
            "target_source": str(target_meta.get("target_source", "none")),
            "target_sources": list(target_meta.get("target_sources", [])),
            "target_fallback_reason": str(
                target_meta.get("target_fallback_reason", "none")
            ),
            "target_fallback_reasons": list(
                target_meta.get("target_fallback_reasons", [])
            ),
            "comm_quality_global": float(adjacent_distance_quality_holder.get("quality_global", 1.0)),
            "min_comm_quality": float(method_cfg.get("adjacent_distance_min_comm_quality", 0.0)),
            "delta_trim": 0.0,
            "ax_trim": 0.0,
            "delta_trim_raw": 0.0,
            "ax_trim_raw": 0.0,
            "error_mean": 0.0,
            "error_peak": 0.0,
            "controlled_error_mean": 0.0,
            "controlled_error_peak": 0.0,
            "pair_diag": [],
        }

    def _apply_adjacent_distance_control(
        vehicle_index, k_value, delta_cmd, ax_cmd, perceived_remote_states, x_self, ref_index
    ):
        delta_in = float(delta_cmd)
        ax_in = float(ax_cmd)
        diag = _adjacent_distance_control_base_diag(vehicle_index, k_value)
        if not use_adjacent_distance_control:
            return delta_in, ax_in, diag

        comm_quality = float(adjacent_distance_quality_holder.get("quality_global", 1.0))
        min_comm_quality = float(
            np.clip(method_cfg.get("adjacent_distance_min_comm_quality", 0.0), 0.0, 1.0)
        )
        diag["comm_quality_global"] = comm_quality
        diag["min_comm_quality"] = min_comm_quality
        if comm_quality < min_comm_quality:
            diag["reason"] = "comm_quality_below_min"
            return delta_in, ax_in, diag

        neighbors = adjacent_pairs[int(vehicle_index)] if 0 <= int(vehicle_index) < num_vehicles else ()
        if len(neighbors) == 0:
            diag["reason"] = "no_adjacent_neighbors"
            return delta_in, ax_in, diag

        k_s = float(method_cfg.get("adjacent_distance_k_s", 0.10))
        k_ey = float(method_cfg.get("adjacent_distance_k_ey", 0.025))
        k_v = float(method_cfg.get("adjacent_distance_k_v", 0.04))
        deadband = float(max(0.0, method_cfg.get("adjacent_distance_deadband_m", 0.03)))
        error_clip = float(max(0.0, method_cfg.get("adjacent_distance_error_clip_m", 0.30)))
        ax_clip = float(max(0.0, method_cfg.get("adjacent_distance_ax_clip", 0.12)))
        delta_clip = float(max(0.0, method_cfg.get("adjacent_distance_delta_clip", 0.015)))
        filter_beta = float(np.clip(method_cfg.get("adjacent_distance_filter_beta", 0.50), 0.0, 1.0))

        x_self_arr = np.asarray(x_self, dtype=float)
        perceived_arr = np.asarray(perceived_remote_states, dtype=float)
        delta_trim_raw = 0.0
        ax_trim_raw = 0.0
        target_errors = []
        controlled_errors = []
        pair_diag = []

        for sender in neighbors:
            target_info = _adjacent_distance_target_info(vehicle_index, sender, ref_index)
            target_distance = float(target_info.get("distance", np.nan))
            pair_info = {
                "receiver": int(vehicle_index),
                "sender": int(sender),
                "pair": f"{int(vehicle_index)}->{int(sender)}",
                "target_distance": float(target_distance) if np.isfinite(target_distance) else np.nan,
                "target_source": str(target_info.get("target_source", "unavailable")),
                "target_fallback_reason": str(
                    target_info.get("target_fallback_reason", "none")
                ),
                "active": False,
                "reason": "invalid_target",
                "delta_trim": 0.0,
                "ax_trim": 0.0,
            }
            if not np.isfinite(target_distance) or target_distance <= 1e-9:
                pair_diag.append(pair_info)
                continue

            measured_rel = perceived_arr[int(vehicle_index), int(sender), :] - x_self_arr
            measured_distance = float(np.linalg.norm(measured_rel[:2]))
            if not np.isfinite(measured_distance):
                pair_info["reason"] = "invalid_measured_distance"
                pair_diag.append(pair_info)
                continue

            raw_error = float(measured_distance - target_distance)
            if abs(raw_error) <= deadband:
                deadbanded_error = 0.0
            else:
                deadbanded_error = float(np.sign(raw_error) * (abs(raw_error) - deadband))
            clipped_error = (
                float(np.clip(deadbanded_error, -error_clip, error_clip))
                if error_clip > 0.0
                else deadbanded_error
            )
            prev_error = float(adjacent_distance_error_filter[int(vehicle_index), int(sender)])
            filtered_error = (
                filter_beta * prev_error + (1.0 - filter_beta) * clipped_error
                if filter_beta > 0.0
                else clipped_error
            )
            adjacent_distance_error_filter[int(vehicle_index), int(sender)] = filtered_error

            if measured_distance > 1e-9:
                unit_s = float(measured_rel[0] / measured_distance)
                unit_ey = float(measured_rel[1] / measured_distance)
            else:
                unit_s = 0.0
                unit_ey = 0.0

            relative_v_s = float(measured_rel[3]) if measured_rel.size > 3 else 0.0
            self_error_s = -filtered_error * unit_s
            self_error_ey = -filtered_error * unit_ey
            ax_pair_trim = float(-k_s * self_error_s + k_v * relative_v_s)
            delta_pair_trim = float(-k_ey * self_error_ey)
            ax_trim_raw += ax_pair_trim
            delta_trim_raw += delta_pair_trim
            target_errors.append(abs(raw_error))
            controlled_errors.append(abs(filtered_error))
            pair_info.update(
                {
                    "active": bool(
                        abs(filtered_error) > 1e-12
                        or abs(delta_pair_trim) > 1e-12
                        or abs(ax_pair_trim) > 1e-12
                    ),
                    "reason": "ok",
                    "measured_distance": measured_distance,
                    "measured_distance_error_to_target": raw_error,
                    "deadbanded_error": deadbanded_error,
                    "clipped_error": clipped_error,
                    "filtered_error": filtered_error,
                    "unit_s": unit_s,
                    "unit_ey": unit_ey,
                    "relative_v_s": relative_v_s,
                    "self_error_s": float(self_error_s),
                    "self_error_ey": float(self_error_ey),
                    "delta_trim": delta_pair_trim,
                    "ax_trim": ax_pair_trim,
                }
            )
            pair_diag.append(pair_info)

        delta_trim = (
            float(np.clip(delta_trim_raw, -delta_clip, delta_clip))
            if delta_clip > 0.0
            else float(delta_trim_raw)
        )
        ax_trim = (
            float(np.clip(ax_trim_raw, -ax_clip, ax_clip))
            if ax_clip > 0.0
            else float(ax_trim_raw)
        )
        pair_target_source_text, pair_target_source_list = _adjacent_distance_unique_text(
            [p.get("target_source", "unavailable") for p in pair_diag]
        )
        pair_fallback_text, pair_fallback_list = _adjacent_distance_unique_text(
            [p.get("target_fallback_reason", "none") for p in pair_diag]
        )
        diag.update(
            {
                "active": bool(abs(delta_trim) > 1e-12 or abs(ax_trim) > 1e-12),
                "reason": "ok" if target_errors else "no_valid_pairs",
                "target_source": pair_target_source_text,
                "target_sources": pair_target_source_list,
                "target_fallback_reason": pair_fallback_text,
                "target_fallback_reasons": pair_fallback_list,
                "delta_trim": delta_trim,
                "ax_trim": ax_trim,
                "delta_trim_raw": float(delta_trim_raw),
                "ax_trim_raw": float(ax_trim_raw),
                "delta_clip": delta_clip,
                "ax_clip": ax_clip,
                "error_mean": float(np.mean(target_errors)) if target_errors else 0.0,
                "error_peak": float(np.max(target_errors)) if target_errors else 0.0,
                "controlled_error_mean": float(np.mean(controlled_errors)) if controlled_errors else 0.0,
                "controlled_error_peak": float(np.max(controlled_errors)) if controlled_errors else 0.0,
                "pair_diag": pair_diag,
            }
        )
        return delta_in + delta_trim, ax_in + ax_trim, diag

    def _summarize_adjacent_distance_control_step(k_value, diag_step):
        diags = list(diag_step) if diag_step else []
        delta_trims = [float(d.get("delta_trim", 0.0)) for d in diags]
        ax_trims = [float(d.get("ax_trim", 0.0)) for d in diags]
        errors = [float(d.get("error_mean", 0.0)) for d in diags]
        peaks = [float(d.get("error_peak", 0.0)) for d in diags]
        active_flags = [bool(d.get("active", False)) for d in diags]
        target_sources = []
        target_fallback_reasons = []
        for d in diags:
            target_sources.extend(list(d.get("target_sources", [])))
            if not d.get("target_sources", []):
                target_sources.append(d.get("target_source", "unavailable"))
            target_fallback_reasons.extend(list(d.get("target_fallback_reasons", [])))
            if not d.get("target_fallback_reasons", []):
                target_fallback_reasons.append(d.get("target_fallback_reason", "none"))
        target_source_text, target_source_list = _adjacent_distance_unique_text(target_sources)
        fallback_reason_text, fallback_reason_list = _adjacent_distance_unique_text(
            target_fallback_reasons
        )
        return {
            "step": int(k_value),
            "enabled": bool(use_adjacent_distance_control),
            "active": bool(any(active_flags)),
            "active_count": int(np.sum(active_flags)) if active_flags else 0,
            "target_mode": str(adjacent_distance_target_mode),
            "target_source": target_source_text,
            "target_sources": target_source_list,
            "target_fallback_reason": fallback_reason_text,
            "target_fallback_reasons": fallback_reason_list,
            "delta_trim": float(np.sum(delta_trims)) if delta_trims else 0.0,
            "ax_trim": float(np.sum(ax_trims)) if ax_trims else 0.0,
            "delta_trim_max_abs": float(np.max(np.abs(delta_trims))) if delta_trims else 0.0,
            "ax_trim_max_abs": float(np.max(np.abs(ax_trims))) if ax_trims else 0.0,
            "error_mean": float(np.mean(errors)) if errors else 0.0,
            "error_peak": float(np.max(peaks)) if peaks else 0.0,
            "vehicle_diag": diags,
        }

    def _apply_ref_channel_matrix(ref_mat, active):
        ref_arr = np.asarray(ref_mat, dtype=float).copy()
        if not active:
            return ref_arr
        rows = ref_arr.shape[0]
        scale = _cfg_vector(method_cfg.get("upper_lower_comm_ref_scale", 1.0), rows, 1.0)[:, None]
        bias = _cfg_vector(method_cfg.get("upper_lower_comm_ref_bias", 0.0), rows, 0.0)[:, None]
        noise_std = _cfg_vector(method_cfg.get("upper_lower_comm_ref_noise_std", 0.0), rows, 0.0)[:, None]
        noise = (
            comm_rng.normal(0.0, noise_std, size=ref_arr.shape)
            if np.any(noise_std > 0.0)
            else 0.0
        )
        return scale * ref_arr + bias + noise

    def _build_comm_perception(k_value, local_states_stack, team_state, team_ref_step):
        active = bool(use_comm_restructure) and _tf14_channel_active(
            method_cfg, "comm_fault", k_value, float(team_state[0]), fallback_prefix=None
        )
        local_arr = np.asarray(local_states_stack, dtype=float)
        team_arr = np.asarray(team_state, dtype=float)
        perceived_remote_states = np.zeros((num_vehicles, num_vehicles, num_states), dtype=float)
        perceived_team_states = np.tile(team_arr.reshape(1, -1), (num_vehicles, 1))
        rel_errors = []
        rel_dist_errors = []
        rel_target_dist_errors = []
        rel_actual_target_dist_errors = []
        pair_delay_steps = []
        pair_dropouts = []
        pair_diag = []
        team_delay_steps = []
        team_dropouts = []
        team_ey_errors = []

        for receiver in range(num_vehicles):
            perceived_remote_states[receiver, :, :] = local_arr
            for sender in adjacent_pairs[receiver]:
                delay_steps = (
                    _sample_delay_steps(method_cfg, "comm_relative_state", comm_rng, None)
                    if active
                    else 0
                )
                source_idx = max(0, len(comm_local_state_history) - 1 - delay_steps)
                source_states = comm_local_state_history[source_idx]
                actual_rel = local_arr[sender, :] - local_arr[receiver, :]
                measured_rel = source_states[sender, :] - source_states[receiver, :]
                dropped = False
                if active:
                    dropped = bool(
                        comm_rng.random()
                        < float(np.clip(method_cfg.get("comm_relative_state_dropout_prob", 0.0), 0.0, 1.0))
                    )
                    if dropped:
                        measured_rel = last_rel_measure[receiver, sender, :].copy()
                    else:
                        measured_rel = _apply_vector_channel(
                            measured_rel, method_cfg, "comm_relative_state", comm_rng, True, None
                        )
                        source_dist = float(np.linalg.norm(measured_rel[:2]))
                        dist_scale = float(method_cfg.get("comm_relative_distance_scale", 1.0))
                        dist_bias = float(method_cfg.get("comm_relative_distance_bias", 0.0))
                        dist_std = float(max(0.0, method_cfg.get("comm_relative_distance_noise_std", 0.0)))
                        measured_dist = dist_scale * source_dist + dist_bias
                        if dist_std > 0.0:
                            measured_dist += float(comm_rng.normal(0.0, dist_std))
                        measured_dist = max(0.0, measured_dist)
                        if source_dist > 1e-9:
                            measured_rel[:2] *= measured_dist / source_dist
                        else:
                            measured_rel[0] = measured_dist
                        last_rel_measure[receiver, sender, :] = measured_rel.copy()
                else:
                    last_rel_measure[receiver, sender, :] = measured_rel.copy()
                perceived_remote_states[receiver, sender, :] = local_arr[receiver, :] + measured_rel
                actual_distance = float(np.linalg.norm(actual_rel[:2]))
                measured_distance = float(np.linalg.norm(measured_rel[:2]))
                target_info = _adjacent_distance_target_info(receiver, sender, k_value)
                target_distance = float(target_info.get("distance", np.nan))
                distance_error = float(measured_distance - actual_distance)
                measured_target_error = (
                    float(measured_distance - target_distance)
                    if np.isfinite(target_distance)
                    else 0.0
                )
                actual_target_error = (
                    float(actual_distance - target_distance)
                    if np.isfinite(target_distance)
                    else 0.0
                )
                rel_errors.append(float(np.linalg.norm(measured_rel - actual_rel)))
                rel_dist_errors.append(float(abs(distance_error)))
                if np.isfinite(target_distance):
                    rel_target_dist_errors.append(float(abs(measured_target_error)))
                    rel_actual_target_dist_errors.append(float(abs(actual_target_error)))
                pair_delay_steps.append(int(delay_steps))
                pair_dropouts.append(bool(dropped))
                pair_diag.append(
                    {
                        "receiver": int(receiver),
                        "sender": int(sender),
                        "pair": f"{receiver}->{sender}",
                        "actual_distance": actual_distance,
                        "measured_distance": measured_distance,
                        "target_distance": float(target_distance) if np.isfinite(target_distance) else np.nan,
                        "target_source": str(target_info.get("target_source", "unavailable")),
                        "target_fallback_reason": str(
                            target_info.get("target_fallback_reason", "none")
                        ),
                        "distance_error": distance_error,
                        "abs_distance_error": float(abs(distance_error)),
                        "measured_distance_error_to_target": measured_target_error,
                        "actual_distance_error_to_target": actual_target_error,
                        "abs_measured_distance_error_to_target": float(abs(measured_target_error)),
                        "abs_actual_distance_error_to_target": float(abs(actual_target_error)),
                        "delay_steps": int(delay_steps),
                        "dropped": bool(dropped),
                    }
                )

            team_delay = _sample_delay_steps(method_cfg, "comm_team_ey", comm_rng, None) if active else 0
            team_source_idx = max(0, len(comm_team_state_history) - 1 - team_delay)
            team_source = comm_team_state_history[team_source_idx]
            measured_ey = float(team_source[1])
            team_dropped = False
            if active:
                team_dropped = bool(
                    comm_rng.random()
                    < float(np.clip(method_cfg.get("comm_team_ey_dropout_prob", 0.0), 0.0, 1.0))
                )
                if team_dropped:
                    measured_ey = float(last_team_ey_measure[receiver])
                else:
                    measured_ey = float(
                        _apply_vector_channel(
                            np.array([measured_ey], dtype=float),
                            method_cfg,
                            "comm_team_ey",
                            comm_rng,
                            True,
                            None,
                        )[0]
                    )
                    last_team_ey_measure[receiver] = measured_ey
            else:
                last_team_ey_measure[receiver] = measured_ey
            perceived_team_states[receiver, 1] = measured_ey
            team_delay_steps.append(int(team_delay))
            team_dropouts.append(bool(team_dropped))
            team_ey_errors.append(float(measured_ey - team_arr[1]))

        team_state_mean = team_arr.copy()
        if num_vehicles > 0:
            team_state_mean[1] = float(np.mean(perceived_team_states[:, 1]))
        target_source_text, target_source_list = _adjacent_distance_unique_text(
            [p.get("target_source", "unavailable") for p in pair_diag]
        )
        target_fallback_text, target_fallback_list = _adjacent_distance_unique_text(
            [p.get("target_fallback_reason", "none") for p in pair_diag]
        )
        diag = {
            "step": int(k_value),
            "enabled": bool(use_comm_restructure),
            "active": bool(active),
            "trigger_mode": str(method_cfg.get("comm_fault_trigger_mode", "step_and_s")),
            "s": float(team_state[0]),
            "relative_distance_error_mean": float(np.mean(rel_dist_errors)) if rel_dist_errors else 0.0,
            "relative_distance_error_max": float(np.max(rel_dist_errors)) if rel_dist_errors else 0.0,
            "relative_target_distance_error_mean": float(np.mean(rel_target_dist_errors)) if rel_target_dist_errors else 0.0,
            "relative_target_distance_error_peak": float(np.max(rel_target_dist_errors)) if rel_target_dist_errors else 0.0,
            "relative_actual_target_distance_error_mean": float(np.mean(rel_actual_target_dist_errors)) if rel_actual_target_dist_errors else 0.0,
            "relative_actual_target_distance_error_peak": float(np.max(rel_actual_target_dist_errors)) if rel_actual_target_dist_errors else 0.0,
            "relative_state_error_mean": float(np.mean(rel_errors)) if rel_errors else 0.0,
            "relative_state_error_max": float(np.max(rel_errors)) if rel_errors else 0.0,
            "team_ey_error_mean": float(np.mean(team_ey_errors)) if team_ey_errors else 0.0,
            "team_ey_error_max_abs": float(np.max(np.abs(team_ey_errors))) if team_ey_errors else 0.0,
            "relative_state_delay_mean": float(np.mean(pair_delay_steps)) if pair_delay_steps else 0.0,
            "team_ey_delay_mean": float(np.mean(team_delay_steps)) if team_delay_steps else 0.0,
            "relative_state_delay_range_steps": _delay_range_steps(method_cfg, "comm_relative_state", None),
            "team_ey_delay_range_steps": _delay_range_steps(method_cfg, "comm_team_ey", None),
            "relative_state_dropout_ratio": float(np.mean(pair_dropouts)) if pair_dropouts else 0.0,
            "team_ey_dropout_ratio": float(np.mean(team_dropouts)) if team_dropouts else 0.0,
            "team_ey_error_by_vehicle": [float(x) for x in team_ey_errors],
            "adjacent_pairs": [list(x) for x in adjacent_pairs],
            "adjacent_distance_target_mode": str(adjacent_distance_target_mode),
            "adjacent_distance_targets": adjacent_distance_targets.tolist(),
            "adjacent_distance_target_source": target_source_text,
            "adjacent_distance_target_sources": target_source_list,
            "adjacent_distance_target_sources_matrix": adjacent_distance_target_sources,
            "adjacent_distance_target_fallback_reason": target_fallback_text,
            "adjacent_distance_target_fallback_reasons": target_fallback_list,
            "adjacent_distance_target_fallback_reasons_matrix": adjacent_distance_target_fallback_reasons,
            "relative_pair_diag": pair_diag,
        }
        return perceived_remote_states, perceived_team_states, team_state_mean, diag

    def _apply_upper_lower_ref_channel(k_value, vehicle_index, xref_win, s_value):
        xref_current = np.asarray(xref_win, dtype=float).copy()
        if not use_upper_lower_comm:
            return xref_current, {
                "vehicle_index": int(vehicle_index),
                "active": False,
                "delay_steps": 0,
                "delay_range_steps": _delay_range_steps(
                    method_cfg, "upper_lower_comm_ref", "upper_lower_comm"
                ),
                "dropped": False,
                "path_param_bias_norm": 0.0,
            }
        upper_lower_ref_history[vehicle_index].append(xref_current.copy())
        active = _tf14_channel_active(method_cfg, "upper_lower_comm", k_value, s_value)
        delay_steps = _sample_delay_steps(
            method_cfg, "upper_lower_comm_ref", comm_rng, "upper_lower_comm"
        ) if active else 0
        source_idx = max(0, len(upper_lower_ref_history[vehicle_index]) - 1 - delay_steps)
        delivered = upper_lower_ref_history[vehicle_index][source_idx].copy()
        dropped = False
        if active:
            dropped = bool(
                comm_rng.random()
                < float(np.clip(method_cfg.get("upper_lower_comm_ref_dropout_prob", 0.0), 0.0, 1.0))
            )
            if dropped and upper_lower_last_ref[vehicle_index] is not None:
                delivered = upper_lower_last_ref[vehicle_index].copy()
            elif not dropped:
                delivered = _apply_ref_channel_matrix(delivered, True)
        upper_lower_last_ref[vehicle_index] = delivered.copy()
        return delivered, {
            "vehicle_index": int(vehicle_index),
            "active": bool(active),
            "delay_steps": int(delay_steps),
            "delay_range_steps": _delay_range_steps(
                method_cfg, "upper_lower_comm_ref", "upper_lower_comm"
            ),
            "dropped": bool(dropped),
            "path_param_bias_norm": float(np.linalg.norm(delivered - xref_current)),
        }

    def _apply_upper_lower_command_channel(k_value, command_stack, s_value, ref_diag_step):
        nominal = np.asarray(command_stack, dtype=float).copy()
        if not use_upper_lower_comm:
            return nominal, {
                "step": int(k_value),
                "enabled": False,
                "active": False,
                "delay_steps_per_vehicle": [0] * num_vehicles,
                "upper_lower_delay_range_steps": _delay_range_steps(
                    method_cfg, "upper_lower_comm", None
                ),
                "upper_lower_ref_delay_range_steps": _delay_range_steps(
                    method_cfg, "upper_lower_comm_ref", "upper_lower_comm"
                ),
                "dropped_per_vehicle": [False] * num_vehicles,
                "command_bias_norm_mean": 0.0,
                "command_bias_norm_max": 0.0,
                "command_bias_stack": np.zeros_like(nominal).tolist(),
                "best_front_delta_bias": 0.0,
                "path_param_bias_norm_mean": 0.0,
                "path_param_bias_norm_max": 0.0,
            }
        upper_lower_cmd_history.append(nominal.copy())
        active = _tf14_channel_active(method_cfg, "upper_lower_comm", k_value, s_value)
        delivered = nominal.copy()
        delays = []
        dropped_flags = []
        for vehicle_index in range(num_vehicles):
            delay_steps = _sample_delay_steps(
                method_cfg, "upper_lower_comm", comm_rng, None
            ) if active else 0
            source_idx = max(0, len(upper_lower_cmd_history) - 1 - delay_steps)
            row = upper_lower_cmd_history[source_idx][vehicle_index, :].copy()
            dropped = False
            if active:
                dropped = bool(
                    comm_rng.random()
                    < float(np.clip(method_cfg.get("upper_lower_comm_dropout_prob", 0.0), 0.0, 1.0))
                )
                if dropped:
                    row = upper_lower_last_cmd[vehicle_index, :].copy()
                else:
                    row = _apply_vector_channel(
                        row, method_cfg, "upper_lower_comm", comm_rng, True, None
                    )
            row[0] = np.clip(row[0], ctx["umin_lin_noadapt"][0], ctx["umax_lin_noadapt"][0])
            row[1] = np.clip(row[1], ctx["umin_lin_noadapt"][1], ctx["umax_lin_noadapt"][1])
            delivered[vehicle_index, :] = row
            upper_lower_last_cmd[vehicle_index, :] = row
            delays.append(int(delay_steps))
            dropped_flags.append(bool(dropped))
        cmd_bias = delivered - nominal
        front_indices = list(range(min(2, num_vehicles))) or [0]
        best_front_nom = float(np.mean(nominal[front_indices, 0]))
        best_front_rx = float(np.mean(delivered[front_indices, 0]))
        path_bias_vals = [float(d.get("path_param_bias_norm", 0.0)) for d in ref_diag_step]
        return delivered, {
            "step": int(k_value),
            "enabled": bool(use_upper_lower_comm),
            "active": bool(active),
            "trigger_mode": str(method_cfg.get("upper_lower_comm_trigger_mode", method_cfg.get("comm_fault_trigger_mode", "step_and_s"))),
            "s": float(s_value),
            "delay_steps_per_vehicle": delays,
            "delay_steps_mean": float(np.mean(delays)) if delays else 0.0,
            "upper_lower_delay_range_steps": _delay_range_steps(
                method_cfg, "upper_lower_comm", None
            ),
            "upper_lower_ref_delay_range_steps": _delay_range_steps(
                method_cfg, "upper_lower_comm_ref", "upper_lower_comm"
            ),
            "dropped_per_vehicle": dropped_flags,
            "dropout_ratio": float(np.mean(dropped_flags)) if dropped_flags else 0.0,
            "command_bias_stack": cmd_bias.tolist(),
            "command_bias_norm_mean": float(np.mean(np.linalg.norm(cmd_bias, axis=1))) if cmd_bias.size else 0.0,
            "command_bias_norm_max": float(np.max(np.linalg.norm(cmd_bias, axis=1))) if cmd_bias.size else 0.0,
            "best_front_delta_nominal": best_front_nom,
            "best_front_delta_received": best_front_rx,
            "best_front_delta_bias": float(best_front_rx - best_front_nom),
            "path_param_bias_norm_mean": float(np.mean(path_bias_vals)) if path_bias_vals else 0.0,
            "path_param_bias_norm_max": float(np.max(path_bias_vals)) if path_bias_vals else 0.0,
            "ref_channel": list(ref_diag_step),
        }

    try:
        for k in range(sim_steps_cap):
            step_t0 = time.perf_counter()
            solved_this_step = 0
            if use_coupled_plant:
                local_states_k, team_state_from_plant = frenet_states(coupled_state, coupled_path)
                team_state_hist[k, :] = team_state_from_plant
            else:
                local_states_k = connection_model.corner_states_from_team(
                    team_state_hist[k, :], payload_module, payload_cfg
                )
            for v in range(num_vehicles):
                xt_case[v][k, :] = ctx["clip_closed_loop_state"](
                    local_states_k[v], s_upper=team_actual_pars["s_upper"]
                )
                z_case[v][k, :] = lift_fn(xt_case[v][k, :])

            local_states_now_stack = np.vstack([xt_case[v][k, :].copy() for v in range(num_vehicles)])
            team_ref_step_k = ref_bundle["team_ref_hist"][min(k, ref_bundle["team_ref_hist"].shape[0] - 1), :]
            comm_local_state_history.append(local_states_now_stack.copy())
            comm_team_state_history.append(team_state_hist[k, :].copy())
            (
                perceived_remote_states,
                perceived_team_states,
                perceived_team_state,
                comm_perception_diag,
            ) = _build_comm_perception(k, local_states_now_stack, team_state_hist[k, :], team_ref_step_k)

            consensus_state_stack = (
                np.mean(perceived_remote_states, axis=0)
                if use_comm_restructure
                else local_states_now_stack
            )
            comm_consensus.push_states(k, consensus_state_stack)
            prev_spread = control_spread_hist[-1] if len(control_spread_hist) > 0 else None
            if use_comm_quality_consensus:
                comm_step_diag = comm_consensus.update_channel(
                    k,
                    team_state=perceived_team_state if use_comm_restructure else team_state_hist[k, :],
                    control_spread=prev_spread,
                )
            else:
                comm_step_diag = {
                    "quality_global": 1.0,
                    "mean_delay_steps": 0.0,
                    "loss_ratio": 0.0,
                }
            adjacent_distance_quality_holder["quality_global"] = float(
                comm_step_diag.get("quality_global", 1.0)
            )

            if use_online_fdi and k > 0:
                diag_step = tf14_fdi_monitor.update(
                    k=k,
                    local_states_now=local_states_now_stack,
                    local_states_prev=prev_local_states_for_fdi,
                    u_sent_prev=prev_u_sent_stack_for_fdi,
                    u_meas_prev=prev_u_meas_stack_for_fdi,
                    comm_quality_global=float(comm_step_diag.get("quality_global", 1.0)),
                )
            else:
                diag_step = [
                    {
                        "step": int(k),
                        "vehicle_index": int(v),
                        "residual": [0.0] * num_states,
                        "residual_norm": 0.0,
                        "residual_ewma": 0.0,
                        "residual_cusum": 0.0,
                        "ax_eff_est": 1.0,
                        "delta_eff_est": 1.0,
                        "detect_counter": 0,
                        "release_counter": 0,
                        "detected": False,
                        "identified_mode": "nominal",
                        "confidence": 0.0,
                        "comm_quality_global": float(comm_step_diag.get("quality_global", 1.0)),
                    }
                    for v in range(num_vehicles)
                ]
            if not use_online_fault_identification:
                for d in diag_step:
                    d["identified_mode"] = "nominal"
                    d["confidence"] = 0.0
                    d["detected"] = False
            tf14_fdi_diag_hist.append(diag_step)

            leader_state_k = xt_case[leader_idx][k, :].copy()
            desired_u_stack = np.zeros((num_vehicles, num_inputs), dtype=float)
            phase_role_step = []
            upper_lower_ref_diag_step = []
            temporary_path_preview_diag_step = []
            adjacent_distance_control_diag_step = []

            if bool(method_cfg.get("vehicle_order_leader_first", True)):
                vehicle_order = [leader_idx] + [vv for vv in range(num_vehicles) if vv != leader_idx]
            else:
                vehicle_order = list(range(num_vehicles))

            for local_idx, v in enumerate(vehicle_order):
                xk_raw = xt_case[v][k, :].copy()
                xk_for_control = xk_raw.copy()
                if use_comm_restructure:
                    xk_for_control[1] = float(
                        xk_raw[1] + perceived_team_states[v, 1] - team_state_hist[k, 1]
                    )

                if use_adaptive_weight:
                    q_adapt, qn_adapt, r_adapt, mem_new = ctx["adaptive_mpc_weights"](
                        xk_for_control[1],
                        xk_for_control[2],
                        q_base_case,
                        qn_base_case,
                        r_base_case,
                        prev_mem=weight_memory[v],
                    )
                    weight_memory[v] = mem_new
                else:
                    q_adapt, qn_adapt, r_adapt = (
                        q_base_case,
                        qn_base_case,
                        r_base_case,
                    )

                curv_for_window = float(ctx["curvature_ref_path"][min(k, traj_length - 1)])
                if bool(method_cfg.get("spatial_switch_use_ref_s", True)):
                    ref_idx_for_window = min(k + 1, x_ref_case_vehicles[v].shape[1] - 1)
                    spatial_s_for_mpc = float(x_ref_case_vehicles[v][0, ref_idx_for_window])
                else:
                    spatial_s_for_mpc = float(xk_raw[0])
                spatial_mpc_profile = _spatial_lateral_switch_profile(spatial_s_for_mpc, curv_for_window)
                windowed_mpc_active = _windowed_mpc_active(float(xk_raw[0]), curv_for_window)
                if windowed_mpc_active:
                    q_adapt = _scaled_sparse_diagonal_runtime(
                        q_adapt,
                        {
                            1: method_cfg.get("windowed_mpc_q_ey_scale", 1.0),
                            2: method_cfg.get("windowed_mpc_q_epsi_scale", 1.0),
                            5: method_cfg.get("windowed_mpc_q_r_scale", 1.0),
                        },
                    )
                    qn_adapt = _scaled_sparse_diagonal_runtime(
                        qn_adapt,
                        {
                            1: method_cfg.get("windowed_mpc_qn_ey_scale", 1.0),
                            2: method_cfg.get("windowed_mpc_qn_epsi_scale", 1.0),
                            5: method_cfg.get("windowed_mpc_qn_r_scale", 1.0),
                        },
                    )
                    r_adapt = _scaled_sparse_diagonal_runtime(
                        r_adapt,
                        {
                            0: method_cfg.get("windowed_mpc_r_delta_scale", 1.0),
                            1: method_cfg.get("windowed_mpc_r_ax_scale", 1.0),
                        },
                    )
                force_aware_mpc_profile = _force_aware_switch_profile(spatial_s_for_mpc, curv_for_window)
                force_aware_mpc_gain = float(force_aware_mpc_profile.get("gain", 0.0))
                if force_aware_mpc_gain > 1e-9:
                    def _force_aware_blend_scale(key: str, default: float) -> float:
                        target = float(method_cfg.get(key, default))
                        return 1.0 + force_aware_mpc_gain * (target - 1.0)

                    q_adapt = _scaled_sparse_diagonal_runtime(
                        q_adapt,
                        {
                            1: _force_aware_blend_scale("force_aware_q_ey_scale", 1.28),
                            2: _force_aware_blend_scale("force_aware_q_epsi_scale", 1.16),
                            5: _force_aware_blend_scale("force_aware_q_r_scale", 1.10),
                        },
                    )
                    qn_adapt = _scaled_sparse_diagonal_runtime(
                        qn_adapt,
                        {
                            1: _force_aware_blend_scale("force_aware_qn_ey_scale", 1.34),
                            2: _force_aware_blend_scale("force_aware_qn_epsi_scale", 1.20),
                            5: _force_aware_blend_scale("force_aware_qn_r_scale", 1.12),
                        },
                    )
                    r_adapt = _scaled_sparse_diagonal_runtime(
                        r_adapt,
                        {
                            0: _force_aware_blend_scale("force_aware_r_delta_scale", 1.32),
                            1: _force_aware_blend_scale("force_aware_r_ax_scale", 1.42),
                        },
                    )
                spatial_lateral_gain_mpc = float(spatial_mpc_profile.get("lateral_gain", 0.0))
                if spatial_lateral_gain_mpc > 1e-9:
                    def _spatial_blend_scale(key: str, default: float) -> float:
                        target = float(method_cfg.get(key, default))
                        return 1.0 + spatial_lateral_gain_mpc * (target - 1.0)

                    q_adapt = _scaled_sparse_diagonal_runtime(
                        q_adapt,
                        {
                            0: _spatial_blend_scale("spatial_lateral_q_s_scale", 0.75),
                            1: _spatial_blend_scale("spatial_lateral_q_ey_scale", 1.55),
                            2: _spatial_blend_scale("spatial_lateral_q_epsi_scale", 1.25),
                            3: _spatial_blend_scale("spatial_lateral_q_vx_scale", 0.82),
                        },
                    )
                    qn_adapt = _scaled_sparse_diagonal_runtime(
                        qn_adapt,
                        {
                            0: _spatial_blend_scale("spatial_lateral_qn_s_scale", 0.70),
                            1: _spatial_blend_scale("spatial_lateral_qn_ey_scale", 1.70),
                            2: _spatial_blend_scale("spatial_lateral_qn_epsi_scale", 1.35),
                            3: _spatial_blend_scale("spatial_lateral_qn_vx_scale", 0.80),
                        },
                    )
                    r_adapt = _scaled_sparse_diagonal_runtime(
                        r_adapt,
                        {
                            0: _spatial_blend_scale("spatial_lateral_r_delta_scale", 0.78),
                        },
                    )

                controllers_case[v].Q = q_adapt
                controllers_case[v].QN = qn_adapt
                controllers_case[v].R = r_adapt

                if use_ppc:
                    ctx["maybe_update_ppc"](
                        controllers_case[v],
                        ctx["curvature_ref_path"][min(k, traj_length - 1)],
                        use_dynamic_ppc=use_dynamic_ppc,
                    )

                xref_win_nominal = x_ref_case_vehicles[v][:, k + 1:k + n_case + 2]
                preview_trigger_s = (
                    float(team_ref_step_k[0])
                    if temporary_path_preview_use_ref_s
                    else float(xk_raw[0])
                )
                preview_trigger_s_source = (
                    "team_ref_s" if temporary_path_preview_use_ref_s else "vehicle_actual_s"
                )
                if not np.isfinite(preview_trigger_s):
                    preview_trigger_s = float(xk_raw[0])
                    preview_trigger_s_source = f"{preview_trigger_s_source}_fallback_vehicle_actual_s"
                xref_win_preview, preview_diag = _apply_temporary_path_preview(
                    k,
                    v,
                    xref_win_nominal,
                    x_ref_case_vehicles[v],
                    float(xk_raw[0]),
                    trigger_s_value=preview_trigger_s,
                    trigger_s_source=preview_trigger_s_source,
                )
                xref_win, ref_channel_diag = _apply_upper_lower_ref_channel(
                    k, v, xref_win_preview, float(team_state_hist[k, 0])
                )
                ref_channel_diag["temporary_path_preview"] = dict(preview_diag)
                ref_channel_diag["temporary_path_preview_active"] = bool(preview_diag.get("active", False))
                ref_channel_diag["temporary_path_preview_blend_weight"] = float(
                    preview_diag.get("blend_weight", 0.0)
                )
                ref_channel_diag["temporary_path_preview_trigger_s"] = float(
                    preview_diag.get("trigger_s", preview_diag.get("s", 0.0))
                )
                ref_channel_diag["temporary_path_preview_trigger_s_source"] = str(
                    preview_diag.get("trigger_s_source", "vehicle_actual_s")
                )
                preview_target_s = preview_diag.get("target_s", np.nan)
                if preview_target_s is None:
                    preview_target_s = np.nan
                ref_channel_diag["temporary_path_preview_mode"] = str(
                    preview_diag.get("preview_mode", "shift")
                )
                ref_channel_diag["temporary_path_preview_lookahead_m"] = float(
                    preview_diag.get("lookahead_m", 0.0)
                )
                ref_channel_diag["temporary_path_preview_target_s"] = float(preview_target_s)
                ref_channel_diag["temporary_path_preview_target_s_source"] = str(
                    preview_diag.get("target_s_source", "not_used_shift_mode")
                )
                ref_channel_diag["temporary_path_preview_target_start_col"] = int(
                    preview_diag.get("target_start_col", preview_diag.get("start_col", 0))
                )
                ref_channel_diag["temporary_path_preview_front_delta_est"] = float(
                    preview_diag.get("front_delta_est", 0.0)
                )
                ref_channel_diag["temporary_path_preview_rear_delta_est"] = float(
                    preview_diag.get("rear_delta_est", 0.0)
                )
                ref_channel_diag["temporary_path_preview_fourws_heading_applied"] = bool(
                    preview_diag.get("fourws_heading_applied", False)
                )
                ref_channel_diag["temporary_path_preview_fourws_heading_blend"] = float(
                    preview_diag.get("fourws_heading_blend", 0.0)
                )
                ref_channel_diag["temporary_path_preview_fourws_heading_adjustment_raw_mean"] = float(
                    preview_diag.get("fourws_heading_adjustment_raw_mean", 0.0)
                )
                ref_channel_diag["temporary_path_preview_fourws_heading_adjustment_raw_max_abs"] = float(
                    preview_diag.get("fourws_heading_adjustment_raw_max_abs", 0.0)
                )
                ref_channel_diag["temporary_path_preview_fourws_curvature_cmd"] = float(
                    preview_diag.get("fourws_curvature_cmd", 0.0)
                )
                ref_channel_diag["temporary_path_preview_geometric_applied"] = bool(
                    preview_diag.get("geometric_preview_applied", False)
                )
                ref_channel_diag["temporary_path_preview_fallback_reason"] = str(
                    preview_diag.get("fallback_reason", "none")
                )
                ref_channel_diag["temporary_path_preview_requested_shift_steps"] = float(
                    preview_diag.get("requested_preview_shift_steps", preview_diag.get("requested_shift_steps", 0.0))
                )
                ref_channel_diag["temporary_path_preview_configured_shift_steps"] = int(
                    preview_diag.get("configured_preview_shift_steps", preview_diag.get("configured_shift_steps", 0))
                )
                ref_channel_diag["temporary_path_preview_base_index_mode_effective"] = str(
                    preview_diag.get("base_index_mode_effective", "k_relative")
                )
                ref_channel_diag["temporary_path_preview_candidate_shift_steps_before_clamp"] = int(
                    preview_diag.get("candidate_preview_shift_steps_before_clamp", 0)
                )
                ref_channel_diag["temporary_path_preview_candidate_shift_steps"] = int(
                    preview_diag.get("candidate_preview_shift_steps", 0)
                )
                ref_channel_diag["temporary_path_preview_candidate_shift_clamped"] = bool(
                    preview_diag.get("candidate_shift_clamped", False)
                )
                ref_channel_diag["temporary_path_preview_applied_shift_steps"] = int(
                    preview_diag.get("applied_preview_shift_steps", 0)
                )
                ref_channel_diag["temporary_path_preview_actual_shift_steps"] = int(
                    preview_diag.get("actual_preview_shift_steps", 0)
                )
                upper_lower_ref_diag_step.append(ref_channel_diag)
                temporary_path_preview_diag_step.append(preview_diag)
                should_attempt_solve = True
                if realtime_mode and mpc_decimation_steps > 1:
                    should_attempt_solve = (((k + v) % mpc_decimation_steps) == 0)
                    if bool(method_cfg.get("leader_always_solve", False)) and (v == leader_idx):
                        should_attempt_solve = True

                elapsed_now = time.perf_counter() - step_t0
                budget_left = step_budget_sec - elapsed_now
                if (
                    realtime_mode
                    and mpc_skip_on_budget
                    and (solved_this_step >= min_solve_vehicles_per_step)
                    and (budget_left <= mpc_min_budget_left_sec)
                ):
                    should_attempt_solve = False

                if should_attempt_solve:
                    max_iter_eff = max_iter_case
                    if realtime_mode:
                        vehicles_left = max(1, num_vehicles - local_idx)
                        dyn_tl = max(fast_time_limit_min, budget_left / float(vehicles_left))
                        dyn_tl = min(fast_time_limit, dyn_tl)
                        controllers_case[v].solver_settings["time_limit"] = float(dyn_tl)
                        max_iter_eff = max(1, min(max_iter_case, fast_max_sqp_iters))

                    solve_t0 = time.perf_counter()
                    try:
                        controllers_case[v].solve_to_convergence(
                            xref_win,
                            z_case[v][k, :],
                            controllers_case[v].z_init,
                            controllers_case[v].u_init,
                            max_iter=max_iter_eff,
                            eps=1e-3,
                        )
                        solve_runtime_hist.append(float(time.perf_counter() - solve_t0))
                        solve_success_count += 1
                        solved_this_step += 1
                        controllers_case[v].update_initial_guess_()
                        delta_fb_mpc = float(controllers_case[v].cur_u[0, 0])
                        ax_cmd = float(controllers_case[v].cur_u[0, 1])
                        solver_status_case[v].append(
                            controllers_case[v].last_solve_info.get("status", "solved")
                        )
                    except Exception as e:
                        solve_runtime_hist.append(float(time.perf_counter() - solve_t0))
                        fail_counts_case[v] += 1
                        solver_status_case[v].append("fallback")
                        if k % max(1, method_cfg.get("log_interval", 100)) == 0:
                            print(f"[WARN][TF14] vehicle {v + 1} MPC fallback at step {k}: {e}")
                        if k > 0:
                            delta_fb_mpc = float(u_case[v][k - 1, 0])
                            ax_cmd = float(u_case[v][k - 1, 1])
                        else:
                            delta_fb_mpc, ax_cmd = 0.0, 0.0
                else:
                    solve_skip_count += 1
                    solver_status_case[v].append("skip")
                    if k > 0:
                        delta_fb_mpc = float(u_case[v][k - 1, 0])
                        ax_cmd = float(u_case[v][k - 1, 1])
                    else:
                        delta_fb_mpc, ax_cmd = 0.0, 0.0

                ref_step_v = coordinator.get_vehicle_step_ref(ref_bundle, v, k)
                vx_ref_now = float(ref_step_v[3])
                ax_cmd += 0.45 * (vx_ref_now - xk_raw[3])

                coop_enable_now = (
                    abs(xk_for_control[1]) < float(ctx["MPC_CFG"].get("coop_disable_ey", 0.9))
                    and abs(xk_for_control[2]) < float(ctx["MPC_CFG"].get("coop_disable_epsi", 0.35))
                )
                if (
                    ctx["RUN_CFG"]["enable_cooperative_transport"]
                    and use_rigid_coord_correction
                    and coop_enable_now
                    and num_vehicles > 1
                    and v != leader_idx
                ):
                    rigid_target = coordinator.get_leader_relative_target(ref_bundle, v, k)
                    if use_delay_compensation:
                        leader_state_for_v = comm_consensus.get_predicted_remote_state(
                            receiver=v,
                            sender=leader_idx,
                            current_step=k,
                            fallback_state=leader_state_k,
                        )
                    else:
                        leader_state_for_v = leader_state_k
                    if use_comm_restructure:
                        leader_state_for_v = perceived_remote_states[v, leader_idx, :].copy()
                    delta_fb_mpc, ax_cmd = ctx["apply_coop_correction"](
                        delta_fb_mpc,
                        ax_cmd,
                        xk_for_control,
                        leader_state_for_v,
                        rigid_target,
                    )

                delta_fb_mpc, ax_cmd, adjacent_distance_diag = _apply_adjacent_distance_control(
                    v,
                    k,
                    delta_fb_mpc,
                    ax_cmd,
                    perceived_remote_states,
                    xk_for_control,
                    k,
                )
                adjacent_distance_control_diag_step.append(adjacent_distance_diag)

                ff_gain = ctx["MPC_CFG"]["ff_gain"] if ctx["RUN_CFG"]["enable_curved_tracking"] else 0.0
                delta_ff = ff_gain * (ctx["sys_pars"]["lf"] + ctx["sys_pars"]["lr"]) * ctx["curvature_ref_path"][min(k, traj_length - 1)]
                delta_cmd = delta_fb_mpc + delta_ff
                heading_bias_comp_cfg = method_cfg.get("heading_bias_comp_gains", 0.0)
                if isinstance(heading_bias_comp_cfg, (list, tuple, np.ndarray)):
                    if len(heading_bias_comp_cfg) > 0:
                        bias_comp_gain = float(
                            heading_bias_comp_cfg[min(v, len(heading_bias_comp_cfg) - 1)]
                        )
                    else:
                        bias_comp_gain = 0.0
                else:
                    bias_comp_gain = float(heading_bias_comp_cfg)
                if abs(bias_comp_gain) > 1e-12:
                    bias_comp_gate_ey = float(
                        max(1e-4, method_cfg.get("heading_bias_comp_ey_gate", 0.10))
                    )
                    bias_comp_start_s = float(
                        method_cfg.get("heading_bias_comp_start_s", -np.inf)
                    )
                    bias_comp_end_s = float(
                        method_cfg.get("heading_bias_comp_end_s", np.inf)
                    )
                    bias_comp_delta_clip = float(
                        max(0.0, method_cfg.get("heading_bias_comp_delta_clip", 0.10))
                    )
                    if bias_comp_start_s <= float(xk_raw[0]) <= bias_comp_end_s:
                        bias_gate = min(abs(float(xk_for_control[1])) / bias_comp_gate_ey, 1.0)
                        bias_delta = float(-bias_comp_gain * bias_gate * float(xk_for_control[2]))
                        if bias_comp_delta_clip > 0.0:
                            bias_delta = float(
                                np.clip(bias_delta, -bias_comp_delta_clip, bias_comp_delta_clip)
                            )
                        delta_cmd += bias_delta
                if use_phase_role_scheduler:
                    curv_idx = min(k, traj_length - 1)
                    curv_prev = ctx["curvature_ref_path"][max(0, curv_idx - 1)]
                    curv_now = ctx["curvature_ref_path"][curv_idx]
                    curv_next = ctx["curvature_ref_path"][min(traj_length - 1, curv_idx + 1)]
                    delta_cmd, ax_cmd, phase_diag = phase_role_scheduler.adjust(
                        k=k,
                        vehicle_index=v,
                        x_raw=xk_for_control,
                        ref_step=ref_step_v,
                        curvature=curv_now,
                        curvature_prev=curv_prev,
                        curvature_next=curv_next,
                        delta_cmd=delta_cmd,
                        ax_cmd=ax_cmd,
                        diagnoses=diag_step,
                        comm_quality_global=float(comm_step_diag.get("quality_global", 1.0)),
                    )
                    phase_role_step.append(phase_diag)
                curv_for_relief = float(ctx["curvature_ref_path"][min(k, traj_length - 1)])
                speed_cap_gain = float(method_cfg.get("high_curvature_speed_cap_gain", 0.0))
                if speed_cap_gain > 0.0:
                    speed_cap_threshold = float(method_cfg.get("high_curvature_speed_cap_threshold", 0.065))
                    speed_cap_start_s = float(method_cfg.get("high_curvature_speed_cap_start_s", -np.inf))
                    speed_cap_end_s = float(method_cfg.get("high_curvature_speed_cap_end_s", np.inf))
                    speed_cap_active = (
                        speed_cap_start_s <= float(xk_raw[0]) <= speed_cap_end_s
                        and abs(curv_for_relief) >= speed_cap_threshold
                    )
                    if speed_cap_active:
                        speed_cap_target = float(method_cfg.get("high_curvature_speed_cap_mps", 3.2))
                        speed_cap_clip = max(float(method_cfg.get("high_curvature_speed_cap_ax_clip", 0.8)), 0.0)
                        speed_excess = max(0.0, float(xk_raw[3]) - speed_cap_target)
                        if speed_excess > 0.0:
                            ax_relief = -speed_cap_gain * speed_excess
                            if speed_cap_clip > 0.0:
                                ax_relief = float(np.clip(ax_relief, -speed_cap_clip, speed_cap_clip))
                            ax_cmd += ax_relief
                relief_gain = float(method_cfg.get("high_curvature_ey_relief_gain", 0.0))
                if relief_gain > 0.0:
                    relief_threshold = float(method_cfg.get("high_curvature_ey_relief_threshold", 0.065))
                    relief_start_s = float(method_cfg.get("high_curvature_ey_relief_start_s", -np.inf))
                    relief_end_s = float(method_cfg.get("high_curvature_ey_relief_end_s", np.inf))
                    relief_s_active = relief_start_s <= float(xk_raw[0]) <= relief_end_s
                    if relief_s_active and abs(curv_for_relief) >= relief_threshold:
                        relief_deadband = float(method_cfg.get("high_curvature_ey_relief_deadband", 0.05))
                        relief_gate_width = max(
                            float(method_cfg.get("high_curvature_ey_relief_gate_width", 0.35)),
                            1e-6,
                        )
                        relief_gate = np.clip((abs(float(xk_for_control[1])) - relief_deadband) / relief_gate_width, 0.0, 1.0)
                        if relief_gate > 0.0:
                            relief_clip = max(float(method_cfg.get("high_curvature_ey_relief_clip", 0.035)), 0.0)
                            relief_delta = relief_gain * relief_gate * float(xk_for_control[1])
                            if relief_clip > 0.0:
                                relief_delta = float(np.clip(relief_delta, -relief_clip, relief_clip))
                            delta_cmd += relief_delta
                preapex_relief_gain = float(method_cfg.get("high_curvature_preapex_ey_relief_gain", 0.0))
                if abs(preapex_relief_gain) > 1e-12:
                    preapex_threshold = float(
                        method_cfg.get(
                            "high_curvature_preapex_ey_relief_threshold",
                            method_cfg.get("high_curvature_ey_relief_threshold", 0.065),
                        )
                    )
                    preapex_start_s = float(method_cfg.get("high_curvature_preapex_ey_relief_start_s", -np.inf))
                    preapex_end_s = float(method_cfg.get("high_curvature_preapex_ey_relief_end_s", np.inf))
                    preapex_s_active = preapex_start_s <= float(xk_raw[0]) <= preapex_end_s
                    if preapex_s_active and abs(curv_for_relief) >= preapex_threshold:
                        preapex_deadband = float(
                            method_cfg.get(
                                "high_curvature_preapex_ey_relief_deadband",
                                method_cfg.get("high_curvature_ey_relief_deadband", 0.05),
                            )
                        )
                        preapex_gate_width = max(
                            float(
                                method_cfg.get(
                                    "high_curvature_preapex_ey_relief_gate_width",
                                    method_cfg.get("high_curvature_ey_relief_gate_width", 0.35),
                                )
                            ),
                            1e-6,
                        )
                        preapex_gate = np.clip(
                            (abs(float(xk_for_control[1])) - preapex_deadband) / preapex_gate_width,
                            0.0,
                            1.0,
                        )
                        if preapex_gate > 0.0:
                            preapex_clip = max(
                                float(
                                    method_cfg.get(
                                        "high_curvature_preapex_ey_relief_clip",
                                        method_cfg.get("high_curvature_ey_relief_clip", 0.035),
                                    )
                                ),
                                0.0,
                            )
                            preapex_delta = preapex_relief_gain * preapex_gate * float(xk_for_control[1])
                            if preapex_clip > 0.0:
                                preapex_delta = float(np.clip(preapex_delta, -preapex_clip, preapex_clip))
                            delta_cmd += preapex_delta
                lag_s_v = float(ref_step_v[0] - xk_raw[0])
                lag_v_v = float(ref_step_v[3] - xk_raw[3])
                local_stable = (
                    abs(xk_for_control[1]) < float(method_cfg.get("local_stable_ey_th", 0.52))
                    and abs(xk_for_control[2]) < float(method_cfg.get("local_stable_epsi_th", 0.24))
                    and abs(xk_for_control[5]) < float(method_cfg.get("local_stable_r_th", 0.95))
                )
                delta_cmd, ax_cmd, emergency_active = ctx["apply_emergency_guard"](xk_for_control, delta_cmd, ax_cmd)
                if emergency_active:
                    emg_severity = max(
                        abs(xk_for_control[1]) / max(float(method_cfg.get("emergency_soft_ey_norm", 1.0)), 1e-6),
                        abs(xk_for_control[2]) / max(float(method_cfg.get("emergency_soft_epsi_norm", 0.40)), 1e-6),
                        abs(xk_for_control[5]) / max(float(method_cfg.get("emergency_soft_r_norm", 1.0)), 1e-6),
                    )
                    soft_floor_base = float(method_cfg.get("emergency_soft_ax_floor_base", -0.40))
                    soft_floor_span = float(method_cfg.get("emergency_soft_ax_floor_span", 0.35))
                    soft_floor = soft_floor_base - soft_floor_span * np.clip(emg_severity - 1.0, 0.0, 1.0)
                    ax_cmd = max(float(ax_cmd), float(soft_floor))
                if (
                    enable_emergency_progress_override
                    and emergency_active
                    and lag_s_v > float(method_cfg.get("emergency_override_lag_s", 1.5))
                    and local_stable
                ):
                    ax_floor = (
                        -0.08
                        + 0.10 * min(lag_s_v, 4.0)
                        + 0.25 * max(lag_v_v, 0.0)
                        - 0.06 * abs(xk_for_control[5])
                    )
                    ax_floor = float(
                        np.clip(
                            ax_floor,
                            method_cfg.get("emergency_override_ax_min", -0.10),
                            method_cfg.get("emergency_override_ax_max", 0.55),
                        )
                    )
                    ax_cmd = max(float(ax_cmd), ax_floor)
                delta_cmd = np.clip(delta_cmd, ctx["umin_lin_noadapt"][0], ctx["umax_lin_noadapt"][0])
                ax_cmd = np.clip(ax_cmd, ctx["umin_lin_noadapt"][1], ctx["umax_lin_noadapt"][1])

                if k == 0:
                    delta_applied = delta_cmd
                    ax_applied = ax_cmd
                else:
                    delta_alpha_eff = delta_alpha
                    if windowed_mpc_active and "windowed_mpc_delta_alpha" in method_cfg:
                        delta_alpha_eff = float(method_cfg.get("windowed_mpc_delta_alpha", delta_alpha))
                    if force_aware_mpc_gain > 1e-9 and method_cfg.get("force_aware_delta_alpha", None) is not None:
                        force_alpha = float(method_cfg.get("force_aware_delta_alpha", delta_alpha_eff))
                        delta_alpha_eff = (
                            (1.0 - force_aware_mpc_gain) * float(delta_alpha_eff)
                            + force_aware_mpc_gain * force_alpha
                        )
                    spatial_lateral_gain_alpha = float(spatial_mpc_profile.get("lateral_gain", 0.0))
                    if spatial_lateral_gain_alpha > 1e-9 and "spatial_lateral_delta_alpha" in method_cfg:
                        spatial_delta_alpha = float(method_cfg.get("spatial_lateral_delta_alpha", delta_alpha_eff))
                        delta_alpha_eff = (
                            (1.0 - spatial_lateral_gain_alpha) * float(delta_alpha_eff)
                            + spatial_lateral_gain_alpha * spatial_delta_alpha
                        )
                    delta_applied = delta_alpha_eff * u_case[v][k - 1, 0] + (1.0 - delta_alpha_eff) * delta_cmd
                    ax_applied = ax_alpha * u_case[v][k - 1, 1] + (1.0 - ax_alpha) * ax_cmd

                delta_applied = np.clip(delta_applied, ctx["umin_lin_noadapt"][0], ctx["umax_lin_noadapt"][0])
                ax_applied = np.clip(ax_applied, ctx["umin_lin_noadapt"][1], ctx["umax_lin_noadapt"][1])
                desired_u_stack[v, 0] = delta_applied
                desired_u_stack[v, 1] = ax_applied
                u_case[v][k, :] = desired_u_stack[v]

            if use_phase_role_scheduler:
                phase_role_diag_hist.append(phase_role_step)
            adjacent_distance_control_step_diag = _summarize_adjacent_distance_control_step(
                k, adjacent_distance_control_diag_step
            )

            planned_u_stack = desired_u_stack.copy()
            if use_online_ftc_switching:
                u_sent_stack, switch_diag_step = tf14_switcher.apply(
                    k=k,
                    planned_u_stack=planned_u_stack,
                    diagnoses=diag_step,
                    comm_quality_global=float(comm_step_diag.get("quality_global", 1.0)),
                )
            else:
                u_sent_stack = planned_u_stack.copy()
                switch_diag_step = {
                    "step": int(k),
                    "global_mode": "nominal_koopman_mpc",
                    "target_mode": "nominal_koopman_mpc",
                    "mode_hold_counter": 0,
                    "comm_quality_global": float(comm_step_diag.get("quality_global", 1.0)),
                    "redistributed_total_delta": 0.0,
                    "redistributed_total_ax": 0.0,
                    "active_vehicle_modes": {},
                }

            lower_received_stack, upper_lower_comm_diag = _apply_upper_lower_command_channel(
                k, u_sent_stack, float(team_state_hist[k, 0]), upper_lower_ref_diag_step
            )
            temporary_path_preview_step_diag = _summarize_temporary_path_preview_step(
                k, temporary_path_preview_diag_step
            )
            actual_u_stack = lower_received_stack.copy()
            fault_diag_step = {
                "step": int(k),
                "active": False,
                "vehicle_index": int(fault_vehicle_index),
                "mode": str(fault_mode),
                "deficit_delta": 0.0,
                "deficit_ax": 0.0,
                "deficit_norm": 0.0,
                "trigger_mode": str(fault_trigger_mode),
                "source": "none",
            }
            if (
                enable_fault_tolerant_control
                and (0 <= fault_vehicle_index < num_vehicles)
                and _fault_trigger_active(k, team_state_hist[k, 0])
            ):
                v_fault = int(fault_vehicle_index)
                u_sent_fault = lower_received_stack[v_fault, :].copy()
                u_fault = u_sent_fault.copy()

                use_delta_limit = fault_mode in ("delta_limit", "both", "steer_limit", "steering_limit")
                use_ax_limit = fault_mode in ("ax_limit", "both", "accel_limit", "acceleration_limit")

                if use_delta_limit:
                    u_fault[0] = fault_delta_scale * u_fault[0]
                    if fault_delta_abs_limit is not None:
                        try:
                            lim_d = abs(float(fault_delta_abs_limit))
                            if np.isfinite(lim_d) and lim_d > 1e-8:
                                u_fault[0] = np.clip(u_fault[0], -lim_d, lim_d)
                        except Exception:
                            pass

                if use_ax_limit:
                    u_fault[1] = fault_ax_scale * u_fault[1]
                    if fault_ax_abs_limit is not None:
                        try:
                            lim_a = abs(float(fault_ax_abs_limit))
                            if np.isfinite(lim_a) and lim_a > 1e-8:
                                u_fault[1] = np.clip(u_fault[1], -lim_a, lim_a)
                        except Exception:
                            pass

                deficit = u_sent_fault - u_fault
                actual_u_stack[v_fault, :] = u_fault

                if fault_tolerant_redistribution and (not use_online_ftc_switching) and num_vehicles > 1:
                    supporters = [vv for vv in range(num_vehicles) if vv != v_fault]
                    if len(supporters) > 0:
                        comp = (fault_comp_gain * deficit) / float(len(supporters))
                        comp[0] = np.clip(comp[0], -fault_comp_delta_clip, fault_comp_delta_clip)
                        comp[1] = np.clip(comp[1], -fault_comp_ax_clip, fault_comp_ax_clip)
                        for vv in supporters:
                            actual_u_stack[vv, 0] += comp[0]
                            actual_u_stack[vv, 1] += comp[1]

                actual_u_stack[:, 0] = np.clip(
                    actual_u_stack[:, 0], ctx["umin_lin_noadapt"][0], ctx["umax_lin_noadapt"][0]
                )
                actual_u_stack[:, 1] = np.clip(
                    actual_u_stack[:, 1], ctx["umin_lin_noadapt"][1], ctx["umax_lin_noadapt"][1]
                )
                fault_diag_step = {
                    "step": int(k),
                    "active": True,
                    "vehicle_index": int(v_fault),
                    "mode": str(fault_mode),
                    "u_sent_fault": u_sent_fault.tolist(),
                    "u_fault": u_fault.tolist(),
                    "deficit_delta": float(deficit[0]),
                    "deficit_ax": float(deficit[1]),
                    "deficit_norm": float(np.linalg.norm(deficit)),
                    "trigger_mode": str(fault_trigger_mode),
                    "redistribution_enabled": bool(fault_tolerant_redistribution and (not use_online_ftc_switching)),
                    "source": "simulated_injection",
                    "diagnosed_mode": str(diag_step[v_fault].get("identified_mode", "nominal")) if v_fault < len(diag_step) else "nominal",
                    "diagnosed_confidence": float(diag_step[v_fault].get("confidence", 0.0)) if v_fault < len(diag_step) else 0.0,
                }
                if k % max(1, int(method_cfg.get("log_interval", 100))) == 0:
                    print(
                        f"[TF14][fault] step={k} v={v_fault + 1} mode={fault_mode} "
                        f"def=({deficit[0]:+.3f},{deficit[1]:+.3f}) "
                        f"diag={fault_diag_step['diagnosed_mode']}@{fault_diag_step['diagnosed_confidence']:.2f}"
                    )
            tf14_switch_diag_hist.append(dict(switch_diag_step))
            fault_diag_hist.append(fault_diag_step)

            prev_team_u = team_input_hist[k - 1, :] if k > 0 else None
            if use_comm_quality_consensus:
                desired_u_for_agg, comm_proj_diag = comm_consensus.project_vehicle_commands(
                    actual_u_stack,
                    prev_team_u=prev_team_u,
                )
            else:
                desired_u_for_agg = actual_u_stack.copy()
                comm_proj_diag = {
                    "quality_in_min": 1.0,
                    "quality_in_mean": 1.0,
                    "quality_in_max": 1.0,
                    "blend_mean": 0.0,
                    "blend_max": 0.0,
                    "quality_global": 1.0,
                    "mean_delay_steps": 0.0,
                    "loss_ratio": 0.0,
                }
            force_aware_command_diag = {
                "active": False,
                "gain": 0.0,
                "s_ref": float(team_ref_step_k[0]),
                "curvature": float(ctx["curvature_ref_path"][min(k, traj_length - 1)]),
                "spread_delta_before": float(np.max(desired_u_for_agg[:, 0]) - np.min(desired_u_for_agg[:, 0])),
                "spread_delta_after": float(np.max(desired_u_for_agg[:, 0]) - np.min(desired_u_for_agg[:, 0])),
                "spread_ax_before": float(np.max(desired_u_for_agg[:, 1]) - np.min(desired_u_for_agg[:, 1])),
                "spread_ax_after": float(np.max(desired_u_for_agg[:, 1]) - np.min(desired_u_for_agg[:, 1])),
                "spread_suppression": 0.0,
            }
            if bool(method_cfg.get("force_aware_hairpin_switch_enabled", False)):
                force_s_cmd = (
                    float(team_ref_step_k[0])
                    if bool(method_cfg.get("force_aware_switch_use_ref_s", True))
                    else float(team_state_hist[k, 0])
                )
                force_profile_cmd = _force_aware_switch_profile(
                    force_s_cmd,
                    float(ctx["curvature_ref_path"][min(k, traj_length - 1)]),
                )
                force_cmd_gain = float(force_profile_cmd.get("gain", 0.0))
                spread_supp = float(
                    np.clip(method_cfg.get("force_aware_command_spread_suppression", 0.0), 0.0, 1.0)
                )
                if force_cmd_gain > 1e-9 and spread_supp > 1e-9 and desired_u_for_agg.size > 0:
                    before_delta_spread = float(np.max(desired_u_for_agg[:, 0]) - np.min(desired_u_for_agg[:, 0]))
                    before_ax_spread = float(np.max(desired_u_for_agg[:, 1]) - np.min(desired_u_for_agg[:, 1]))
                    command_center = np.mean(desired_u_for_agg, axis=0, keepdims=True)
                    shrink = 1.0 - force_cmd_gain * spread_supp
                    desired_u_for_agg = command_center + shrink * (desired_u_for_agg - command_center)
                    force_aware_command_diag.update(
                        {
                            "active": True,
                            "gain": float(force_cmd_gain),
                            "s_ref": float(force_profile_cmd.get("s_ref", force_s_cmd)),
                            "curvature": float(force_profile_cmd.get("curvature", 0.0)),
                            "spread_delta_before": before_delta_spread,
                            "spread_delta_after": float(
                                np.max(desired_u_for_agg[:, 0]) - np.min(desired_u_for_agg[:, 0])
                            ),
                            "spread_ax_before": before_ax_spread,
                            "spread_ax_after": float(
                                np.max(desired_u_for_agg[:, 1]) - np.min(desired_u_for_agg[:, 1])
                            ),
                            "spread_suppression": float(spread_supp),
                        }
                    )
            for v in range(num_vehicles):
                u_case[v][k, :] = desired_u_for_agg[v, :]

            u_team, spread_info = coordinator.aggregate_controls(
                desired_u_for_agg, prev_team_u=prev_team_u
            )
            team_ref_step = team_ref_step_k
            team_state_for_team_control = perceived_team_state if use_comm_restructure else team_state_hist[k, :]
            if use_team_stability_guard:
                u_guard, guard_diag = stability_guard.build_team_guard(
                    team_state_for_team_control, team_ref_step
                )
                u_team, guard_blend_diag = stability_guard.blend_controls(
                    u_team, u_guard, spread_info
                )
            else:
                guard_diag = {"w_guard": 0.0, "severity": 0.0, "beta": 0.0}
                guard_blend_diag = {"w_blend": 0.0, "w_spread": 0.0}

            if use_legacy_hard_brake and (
                abs(team_state_for_team_control[1]) > 0.90 or abs(team_state_for_team_control[2]) > 0.32
            ):
                u_team[1] = min(float(u_team[1]), -0.08 - 0.18 * abs(team_state_for_team_control[2]))

            u_team_before_progress = u_team.copy()
            critical_lateral_diag = {
                "active": False,
                "blend": 1.0,
                "ax_before": float(u_team[1]),
                "ax_after": float(u_team[1]),
                "ax_limit": np.nan,
            }
            if use_progress_supervisor:
                u_team, progress_diag = progress_supervisor.apply(
                    team_state=team_state_for_team_control,
                    team_ref=team_ref_step,
                    u_team=u_team,
                    umin=ctx["umin_lin_noadapt"],
                    umax=ctx["umax_lin_noadapt"],
                    guard_diag=guard_diag,
                    blend_diag=guard_blend_diag,
                )
                team_curv_for_critical = float(ctx["curvature_ref_path"][min(k, traj_length - 1)])
                critical_active = _critical_lateral_priority_active(
                    k,
                    team_state_for_team_control[0],
                    team_curv_for_critical,
                    team_state_for_team_control[1],
                    bool(fault_diag_step.get("active", False)),
                )
                if critical_active and progress_diag.get("boost_active", False):
                    progress_blend = float(
                        np.clip(method_cfg.get("critical_lateral_priority_progress_blend", 0.25), 0.0, 1.0)
                    )
                    ax_increase_clip = max(
                        float(method_cfg.get("critical_lateral_priority_ax_increase_clip", 0.12)),
                        0.0,
                    )
                    ax_before = float(u_team[1])
                    ax_limit = float(u_team_before_progress[1] + ax_increase_clip)
                    u_team[1] = (1.0 - progress_blend) * float(u_team_before_progress[1]) + progress_blend * float(u_team[1])
                    u_team[1] = min(float(u_team[1]), ax_limit)
                    progress_diag["critical_lateral_priority_active"] = True
                    progress_diag["critical_lateral_priority_progress_blend"] = progress_blend
                    critical_lateral_diag = {
                        "active": True,
                        "blend": progress_blend,
                        "ax_before": ax_before,
                        "ax_after": float(u_team[1]),
                        "ax_limit": ax_limit,
                    }
                if progress_diag.get("boost_active", False):
                    progress_boost_count += 1
            else:
                progress_diag = {
                    "boost_active": False,
                    "lag_s": float(max(team_ref_step[0] - team_state_for_team_control[0], 0.0)),
                    "lag_v": float(team_ref_step[3] - team_state_for_team_control[3]),
                    "stable": False,
                    "recover_ax": None,
                    "recover_mix": 0.0,
                }

            if use_comm_constraint_tightening:
                umin_eff, umax_eff, comm_tight_diag = comm_consensus.tightened_bounds(
                    ctx["umin_lin_noadapt"], ctx["umax_lin_noadapt"]
                )
            else:
                umin_eff = np.asarray(ctx["umin_lin_noadapt"], dtype=float).copy()
                umax_eff = np.asarray(ctx["umax_lin_noadapt"], dtype=float).copy()
                comm_tight_diag = {"tighten_frac": 0.0, "quality_global": 1.0}

            if use_comm_degraded_fallback:
                u_team, comm_fb_diag = comm_consensus.apply_degraded_fallback(
                    u_team,
                    team_state_for_team_control,
                    team_ref_step,
                    umin_eff,
                    umax_eff,
                )
            else:
                comm_fb_diag = {
                    "degrade_mix": 0.0,
                    "quality_global": float(comm_proj_diag.get("quality_global", 1.0)),
                    "loss_ratio": float(comm_proj_diag.get("loss_ratio", 0.0)),
                }

            spatial_switch_diag = {
                "enabled": False,
                "phase": "off",
                "pre_gain": 0.0,
                "lateral_gain": 0.0,
                "pre_ax_relief": 0.0,
                "lateral_ax_relief": 0.0,
                "lateral_delta_trim": 0.0,
                "progress_ax_reduction": 0.0,
                "ax_before": float(u_team[1]),
                "ax_after": float(u_team[1]),
                "delta_before": float(u_team[0]),
                "delta_after": float(u_team[0]),
                "s_ref": float(team_ref_step[0]),
            }
            if bool(method_cfg.get("spatial_lateral_switch_enabled", False)):
                team_curv_spatial = float(ctx["curvature_ref_path"][min(k, traj_length - 1)])
                spatial_s_team = float(team_ref_step[0]) if bool(method_cfg.get("spatial_switch_use_ref_s", True)) else float(team_state_for_team_control[0])
                spatial_profile_team = _spatial_lateral_switch_profile(spatial_s_team, team_curv_spatial)
                pre_gain_team = float(spatial_profile_team.get("pre_gain", 0.0))
                lateral_gain_team = float(spatial_profile_team.get("lateral_gain", 0.0))
                spatial_switch_diag.update(
                    {
                        "enabled": True,
                        "phase": str(spatial_profile_team.get("phase", "off")),
                        "pre_gain": pre_gain_team,
                        "lateral_gain": lateral_gain_team,
                        "s_ref": float(spatial_s_team),
                    }
                )
                ax_before_spatial = float(u_team[1])
                if pre_gain_team > 1e-9:
                    pre_target = float(method_cfg.get("spatial_pre_target_mps", 4.45))
                    pre_gain_ax = float(method_cfg.get("spatial_pre_ax_gain", 0.12))
                    pre_clip = max(float(method_cfg.get("spatial_pre_ax_clip", 0.18)), 0.0)
                    speed_excess = max(0.0, float(team_state_for_team_control[3]) - pre_target)
                    pre_ax_relief = -pre_gain_team * pre_gain_ax * speed_excess
                    if pre_clip > 0.0:
                        pre_ax_relief = float(np.clip(pre_ax_relief, -pre_clip, pre_clip))
                    u_team[1] += pre_ax_relief
                    spatial_switch_diag["pre_ax_relief"] = float(pre_ax_relief)
                if lateral_gain_team > 1e-9:
                    progress_keep = float(np.clip(method_cfg.get("spatial_lateral_progress_keep", 0.35), 0.0, 1.0))
                    ax_before_progress_reduction = float(u_team[1])
                    if u_team[1] > u_team_before_progress[1]:
                        progress_delta = float(u_team[1] - u_team_before_progress[1])
                        reduction = lateral_gain_team * (1.0 - progress_keep) * progress_delta
                        u_team[1] -= reduction
                        spatial_switch_diag["progress_ax_reduction"] = float(reduction)
                    ey_deadband = float(method_cfg.get("spatial_lateral_ey_deadband", 0.10))
                    ey_excess = max(0.0, abs(float(team_state_for_team_control[1])) - ey_deadband)
                    lateral_ax_gain = float(method_cfg.get("spatial_lateral_ax_gain", 0.16))
                    lateral_ax_clip = max(float(method_cfg.get("spatial_lateral_ax_clip", 0.16)), 0.0)
                    lateral_ax_relief = -lateral_gain_team * lateral_ax_gain * ey_excess
                    if lateral_ax_clip > 0.0:
                        lateral_ax_relief = float(np.clip(lateral_ax_relief, -lateral_ax_clip, lateral_ax_clip))
                    u_team[1] += lateral_ax_relief
                    ax_ceiling = method_cfg.get("spatial_lateral_ax_ceiling", None)
                    if ax_ceiling is not None:
                        u_team[1] = min(float(u_team[1]), float(ax_ceiling))
                    delta_gain = float(method_cfg.get("spatial_lateral_delta_gain", 0.0))
                    if abs(delta_gain) > 1e-12:
                        delta_deadband = float(method_cfg.get("spatial_lateral_delta_deadband", 0.04))
                        delta_clip = max(float(method_cfg.get("spatial_lateral_delta_clip", 0.04)), 0.0)
                        ey_for_delta = float(team_state_for_team_control[1])
                        ey_delta = np.sign(ey_for_delta) * max(0.0, abs(ey_for_delta) - delta_deadband)
                        lateral_delta_trim = lateral_gain_team * delta_gain * float(ey_delta)
                        if delta_clip > 0.0:
                            lateral_delta_trim = float(np.clip(lateral_delta_trim, -delta_clip, delta_clip))
                        u_team[0] += lateral_delta_trim
                        spatial_switch_diag["lateral_delta_trim"] = float(lateral_delta_trim)
                    spatial_switch_diag["lateral_ax_relief"] = float(lateral_ax_relief)
                    spatial_switch_diag["ax_before_lateral"] = ax_before_progress_reduction
                spatial_switch_diag["ax_before"] = ax_before_spatial
                spatial_switch_diag["ax_after"] = float(u_team[1])
                spatial_switch_diag["delta_after"] = float(u_team[0])

            guard_windows = method_cfg.get("spatial_error_guard_windows", [])
            if isinstance(guard_windows, dict):
                guard_windows = [guard_windows]
            if isinstance(guard_windows, (list, tuple)) and guard_windows:
                team_curv_guard = float(ctx["curvature_ref_path"][min(k, traj_length - 1)])
                guard_delta_total = 0.0
                guard_ax_total = 0.0
                guard_active_count = 0
                for guard in guard_windows:
                    if not isinstance(guard, dict):
                        continue
                    guard_start = float(guard.get("start_s", -np.inf))
                    guard_end = float(guard.get("end_s", np.inf))
                    if not _path_mode_allowed(guard.get("path_modes", None)):
                        continue
                    guard_case_speed = float(method_cfg.get("speed_cap_mps", team_ref_step[3] if len(team_ref_step) > 3 else team_state_for_team_control[3]))
                    guard_min_case_speed = float(guard.get("min_case_speed_mps", -np.inf))
                    guard_max_case_speed = float(guard.get("max_case_speed_mps", np.inf))
                    if not (guard_min_case_speed <= guard_case_speed <= guard_max_case_speed):
                        continue
                    guard_use_ref_s = bool(guard.get("use_ref_s", True))
                    guard_s = float(team_ref_step[0]) if guard_use_ref_s else float(team_state_for_team_control[0])
                    if not (guard_start <= guard_s <= guard_end):
                        continue
                    guard_kappa_threshold = float(guard.get("kappa_threshold", 0.0))
                    if abs(team_curv_guard) < guard_kappa_threshold:
                        continue
                    guard_ramp = max(float(guard.get("ramp_s", 0.25)), 1e-6)
                    guard_width = max(guard_end - guard_start, 1e-6)
                    if guard_width <= 2.0 * guard_ramp:
                        edge = min(guard_s - guard_start, guard_end - guard_s)
                        guard_profile = _smooth_step01(max(0.0, edge) / max(0.5 * guard_width, 1e-6))
                    elif guard_s < guard_start + guard_ramp:
                        guard_profile = _smooth_step01((guard_s - guard_start) / guard_ramp)
                    elif guard_s > guard_end - guard_ramp:
                        guard_profile = _smooth_step01((guard_end - guard_s) / guard_ramp)
                    else:
                        guard_profile = 1.0
                    if guard_profile <= 1e-9:
                        continue
                    guard_ey = float(team_state_for_team_control[1])
                    guard_epsi = float(team_state_for_team_control[2])
                    def _guard_sign_allowed(value, required):
                        if required is None:
                            return True
                        if isinstance(required, str):
                            req = required.lower().strip()
                            if req in ("", "any", "none", "both"):
                                return True
                            if req in ("positive", "pos", "+", "gt0"):
                                return value > 0.0
                            if req in ("negative", "neg", "-", "lt0"):
                                return value < 0.0
                            return True
                        try:
                            req_val = float(required)
                        except (TypeError, ValueError):
                            return True
                        if not np.isfinite(req_val) or abs(req_val) <= 1e-12:
                            return True
                        return value * req_val > 0.0

                    min_abs_ey = float(guard.get("min_abs_ey", 0.0))
                    max_abs_ey = float(guard.get("max_abs_ey", np.inf))
                    if abs(guard_ey) < max(0.0, min_abs_ey):
                        continue
                    if abs(guard_ey) > max_abs_ey:
                        continue
                    if not _guard_sign_allowed(guard_ey, guard.get("ey_sign", None)):
                        continue
                    if not _guard_sign_allowed(guard_epsi, guard.get("epsi_sign", None)):
                        continue
                    if not _guard_sign_allowed(team_curv_guard, guard.get("kappa_sign", None)):
                        continue
                    guard_active_count += 1
                    guard_deadband = float(guard.get("ey_deadband", 0.0))
                    guard_ey_delta = np.sign(guard_ey) * max(0.0, abs(guard_ey) - guard_deadband)
                    guard_delta_bias = float(guard.get("delta_bias", 0.0))
                    if abs(guard_delta_bias) > 1e-12:
                        guard_bias_clip = max(float(guard.get("delta_bias_clip", guard.get("delta_clip", 0.0))), 0.0)
                        guard_bias_trim = guard_profile * guard_delta_bias
                        if guard_bias_clip > 0.0:
                            guard_bias_trim = float(np.clip(guard_bias_trim, -guard_bias_clip, guard_bias_clip))
                        u_team[0] += guard_bias_trim
                        guard_delta_total += float(guard_bias_trim)
                    guard_delta_gain = float(guard.get("delta_gain", 0.0))
                    if abs(guard_delta_gain) > 1e-12:
                        guard_delta_clip = max(float(guard.get("delta_clip", 0.0)), 0.0)
                        guard_delta_trim = guard_profile * guard_delta_gain * float(guard_ey_delta)
                        if guard_delta_clip > 0.0:
                            guard_delta_trim = float(np.clip(guard_delta_trim, -guard_delta_clip, guard_delta_clip))
                        u_team[0] += guard_delta_trim
                        guard_delta_total += float(guard_delta_trim)
                    guard_heading_gain = float(guard.get("heading_delta_gain", 0.0))
                    if abs(guard_heading_gain) > 1e-12:
                        guard_heading_clip = max(float(guard.get("heading_delta_clip", guard.get("delta_clip", 0.0))), 0.0)
                        guard_heading_trim = guard_profile * guard_heading_gain * guard_epsi
                        if guard_heading_clip > 0.0:
                            guard_heading_trim = float(np.clip(guard_heading_trim, -guard_heading_clip, guard_heading_clip))
                        u_team[0] += guard_heading_trim
                        guard_delta_total += float(guard_heading_trim)
                    guard_ax_bias = float(guard.get("ax_bias", 0.0))
                    if abs(guard_ax_bias) > 1e-12:
                        guard_ax_bias_clip = max(float(guard.get("ax_bias_clip", guard.get("ax_clip", 0.0))), 0.0)
                        guard_ax_trim = guard_profile * guard_ax_bias
                        if guard_ax_bias_clip > 0.0:
                            guard_ax_trim = float(np.clip(guard_ax_trim, -guard_ax_bias_clip, guard_ax_bias_clip))
                        u_team[1] += guard_ax_trim
                        guard_ax_total += float(guard_ax_trim)
                    guard_speed_target = guard.get("speed_target_mps", None)
                    if guard_speed_target is not None:
                        guard_speed_excess = max(0.0, float(team_state_for_team_control[3]) - float(guard_speed_target))
                        if guard_speed_excess > 0.0:
                            guard_speed_gain = float(guard.get("speed_gain", 0.0))
                            guard_ax_clip = max(float(guard.get("ax_clip", 0.0)), 0.0)
                            guard_ax_relief = -guard_profile * guard_speed_gain * guard_speed_excess
                            if guard_ax_clip > 0.0:
                                guard_ax_relief = float(np.clip(guard_ax_relief, -guard_ax_clip, guard_ax_clip))
                            u_team[1] += guard_ax_relief
                            guard_ax_total += float(guard_ax_relief)
                if guard_active_count > 0:
                    spatial_switch_diag["enabled"] = True
                    spatial_switch_diag["guard_active_count"] = int(guard_active_count)
                    spatial_switch_diag["guard_delta_trim"] = float(guard_delta_total)
                    spatial_switch_diag["guard_ax_relief"] = float(guard_ax_total)
                    spatial_switch_diag["ax_after"] = float(u_team[1])
                    spatial_switch_diag["delta_after"] = float(u_team[0])

            team_speed_cap_diag = {
                "active": False,
                "speed_excess": 0.0,
                "ax_relief": 0.0,
                "target_mps": np.nan,
            }
            team_speed_cap_gain = float(method_cfg.get("high_curvature_team_speed_cap_gain", 0.0))
            if team_speed_cap_gain > 0.0:
                team_curv = float(ctx["curvature_ref_path"][min(k, traj_length - 1)])
                team_speed_cap_threshold = float(
                    method_cfg.get(
                        "high_curvature_team_speed_cap_threshold",
                        method_cfg.get("high_curvature_speed_cap_threshold", 0.065),
                    )
                )
                team_speed_cap_start_s = float(
                    method_cfg.get(
                        "high_curvature_team_speed_cap_start_s",
                        method_cfg.get("high_curvature_speed_cap_start_s", -np.inf),
                    )
                )
                team_speed_cap_end_s = float(
                    method_cfg.get(
                        "high_curvature_team_speed_cap_end_s",
                        method_cfg.get("high_curvature_speed_cap_end_s", np.inf),
                    )
                )
                team_speed_cap_active = (
                    team_speed_cap_start_s <= float(team_state_for_team_control[0]) <= team_speed_cap_end_s
                    and abs(team_curv) >= team_speed_cap_threshold
                )
                if team_speed_cap_active:
                    team_speed_cap_target = float(
                        method_cfg.get(
                            "high_curvature_team_speed_cap_mps",
                            method_cfg.get("high_curvature_speed_cap_mps", 3.2),
                        )
                    )
                    team_speed_cap_clip = max(
                        float(
                            method_cfg.get(
                                "high_curvature_team_speed_cap_ax_clip",
                                method_cfg.get("high_curvature_speed_cap_ax_clip", 0.8),
                            )
                        ),
                        0.0,
                    )
                    team_speed_excess = max(0.0, float(team_state_for_team_control[3]) - team_speed_cap_target)
                    if team_speed_excess > 0.0:
                        team_ax_relief = -team_speed_cap_gain * team_speed_excess
                        if team_speed_cap_clip > 0.0:
                            team_ax_relief = float(
                                np.clip(team_ax_relief, -team_speed_cap_clip, team_speed_cap_clip)
                            )
                        u_team[1] += team_ax_relief
                        team_speed_cap_diag.update(
                            {
                                "active": True,
                                "speed_excess": float(team_speed_excess),
                                "ax_relief": float(team_ax_relief),
                                "target_mps": float(team_speed_cap_target),
                            }
                        )

            critical_ax_ceiling_diag = {
                "active": False,
                "ax_before": float(u_team[1]),
                "ax_after": float(u_team[1]),
                "ax_ceiling": np.nan,
            }
            if bool(method_cfg.get("critical_lateral_ax_ceiling_enabled", False)):
                crit_s = float(team_state_for_team_control[0])
                crit_curv = float(ctx["curvature_ref_path"][min(k, traj_length - 1)])
                crit_start = float(method_cfg.get("critical_lateral_ax_ceiling_start_s", -np.inf))
                crit_end = float(method_cfg.get("critical_lateral_ax_ceiling_end_s", np.inf))
                crit_kappa = float(method_cfg.get("critical_lateral_ax_ceiling_kappa_threshold", 0.0))
                crit_ey = float(method_cfg.get("critical_lateral_ax_ceiling_ey_threshold", 0.0))
                crit_fault_required = bool(method_cfg.get("critical_lateral_ax_ceiling_fault_required", True))
                crit_fault_ok = (not crit_fault_required) or bool(fault_diag_step.get("active", False))
                if (
                    crit_fault_ok
                    and crit_start <= crit_s <= crit_end
                    and abs(crit_curv) >= crit_kappa
                    and abs(float(team_state_for_team_control[1])) >= crit_ey
                ):
                    ax_before_ceiling = float(u_team[1])
                    ax_ceiling = float(method_cfg.get("critical_lateral_ax_ceiling", ax_before_ceiling))
                    u_team[1] = min(float(u_team[1]), ax_ceiling)
                    critical_ax_ceiling_diag.update(
                        {
                            "active": bool(u_team[1] < ax_before_ceiling - 1e-12),
                            "ax_before": ax_before_ceiling,
                            "ax_after": float(u_team[1]),
                            "ax_ceiling": ax_ceiling,
                        }
                    )

            force_aware_team_diag = {
                "active": False,
                "gain": 0.0,
                "s_ref": float(team_ref_step[0]),
                "curvature": float(ctx["curvature_ref_path"][min(k, traj_length - 1)]),
                "delta_before": float(u_team[0]),
                "delta_after": float(u_team[0]),
                "ax_before": float(u_team[1]),
                "ax_after": float(u_team[1]),
                "speed_ax_relief": 0.0,
                "blend": 0.0,
            }
            if bool(method_cfg.get("force_aware_hairpin_switch_enabled", False)):
                force_s_team = (
                    float(team_ref_step[0])
                    if bool(method_cfg.get("force_aware_switch_use_ref_s", True))
                    else float(team_state_for_team_control[0])
                )
                force_profile_team = _force_aware_switch_profile(
                    force_s_team,
                    float(ctx["curvature_ref_path"][min(k, traj_length - 1)]),
                )
                force_team_gain = float(force_profile_team.get("gain", 0.0))
                if force_team_gain > 1e-9:
                    u_before_force = u_team.copy()
                    u_target_force = u_team.copy()
                    delta_abs_limit = method_cfg.get("force_aware_delta_abs_limit", None)
                    if delta_abs_limit is not None:
                        lim_delta = abs(float(delta_abs_limit))
                        if np.isfinite(lim_delta) and lim_delta > 1e-9:
                            u_target_force[0] = float(np.clip(u_target_force[0], -lim_delta, lim_delta))
                    ax_min_force = method_cfg.get("force_aware_ax_min", None)
                    if ax_min_force is not None:
                        u_target_force[1] = max(float(u_target_force[1]), float(ax_min_force))
                    ax_max_force = method_cfg.get("force_aware_ax_max", None)
                    if ax_max_force is not None:
                        u_target_force[1] = min(float(u_target_force[1]), float(ax_max_force))

                    speed_ax_relief = 0.0
                    speed_target_force = method_cfg.get("force_aware_speed_target_mps", None)
                    if speed_target_force is not None:
                        speed_excess_force = max(
                            0.0,
                            float(team_state_for_team_control[3]) - float(speed_target_force),
                        )
                        if speed_excess_force > 0.0:
                            speed_gain_force = float(method_cfg.get("force_aware_speed_ax_gain", 0.0))
                            speed_clip_force = max(float(method_cfg.get("force_aware_speed_ax_clip", 0.0)), 0.0)
                            speed_ax_relief = -force_team_gain * speed_gain_force * speed_excess_force
                            if speed_clip_force > 0.0:
                                speed_ax_relief = float(
                                    np.clip(speed_ax_relief, -speed_clip_force, speed_clip_force)
                                )
                            u_target_force[1] += speed_ax_relief

                    if prev_team_u is not None:
                        dt_force = float(ctx["dt"])
                        delta_rate_limit = method_cfg.get("force_aware_delta_rate_limit", None)
                        if delta_rate_limit is not None:
                            max_delta_step = abs(float(delta_rate_limit)) * dt_force
                            if np.isfinite(max_delta_step) and max_delta_step > 1e-12:
                                u_target_force[0] = float(
                                    np.clip(
                                        u_target_force[0],
                                        float(prev_team_u[0]) - max_delta_step,
                                        float(prev_team_u[0]) + max_delta_step,
                                    )
                                )
                        ax_rate_limit = method_cfg.get("force_aware_ax_rate_limit", None)
                        if ax_rate_limit is not None:
                            max_ax_step = abs(float(ax_rate_limit)) * dt_force
                            if np.isfinite(max_ax_step) and max_ax_step > 1e-12:
                                u_target_force[1] = float(
                                    np.clip(
                                        u_target_force[1],
                                        float(prev_team_u[1]) - max_ax_step,
                                        float(prev_team_u[1]) + max_ax_step,
                                    )
                                )

                    force_blend = float(np.clip(method_cfg.get("force_aware_team_blend", 0.0), 0.0, 1.0))
                    force_blend_eff = float(force_team_gain * force_blend)
                    u_team = (1.0 - force_blend_eff) * u_team + force_blend_eff * u_target_force
                    force_aware_team_diag.update(
                        {
                            "active": True,
                            "gain": float(force_team_gain),
                            "s_ref": float(force_profile_team.get("s_ref", force_s_team)),
                            "curvature": float(force_profile_team.get("curvature", 0.0)),
                            "delta_before": float(u_before_force[0]),
                            "delta_after": float(u_team[0]),
                            "ax_before": float(u_before_force[1]),
                            "ax_after": float(u_team[1]),
                            "speed_ax_relief": float(speed_ax_relief),
                            "blend": float(force_blend_eff),
                        }
                    )

            u_team[0] = np.clip(u_team[0], umin_eff[0], umax_eff[0])
            u_team[1] = np.clip(u_team[1], umin_eff[1], umax_eff[1])
            if use_coupled_plant:
                previous_physical_controls = (
                    coupled_control_hist[k - 1, :, :] if k > 0 else np.zeros((4, 2), dtype=float)
                )
                conn_diag = physical_history_row(
                    coupled_state,
                    previous_physical_controls,
                    coupled_params,
                    step=k,
                )
                conn_diag["enabled"] = True
                conn_diag["model"] = "four_vehicle_coupled"
            else:
                conn_diag = connection_model.update(
                    desired_u_stack=desired_u_for_agg,
                    u_team=u_team,
                    team_state=team_state_hist[k, :],
                    team_ref=team_ref_step,
                    dt=ctx["dt"],
                )
            spread_info["guard_weight"] = float(guard_diag["w_guard"])
            spread_info["guard_blend"] = float(guard_blend_diag["w_blend"])
            spread_info["progress_boost"] = bool(progress_diag["boost_active"])
            spread_info["progress_lag_s"] = float(progress_diag["lag_s"])
            spread_info["progress_lag_v"] = float(progress_diag["lag_v"])
            spread_info["progress_recover_mix"] = float(progress_diag["recover_mix"])
            spread_info["conn_enabled"] = bool(conn_diag.get("enabled", False))
            spread_info["conn_max_abs_ds"] = float(conn_diag.get("max_abs_ds", 0.0))
            spread_info["conn_max_abs_dey"] = float(conn_diag.get("max_abs_dey", 0.0))
            spread_info["conn_max_abs_dpsi"] = float(conn_diag.get("max_abs_dpsi", 0.0))
            spread_info["comm_quality_global"] = float(comm_step_diag.get("quality_global", 1.0))
            spread_info["comm_mean_delay_steps"] = float(comm_step_diag.get("mean_delay_steps", 0.0))
            spread_info["comm_loss_ratio"] = float(comm_step_diag.get("loss_ratio", 0.0))
            spread_info["comm_consensus_blend_mean"] = float(comm_proj_diag.get("blend_mean", 0.0))
            spread_info["comm_tighten_frac"] = float(comm_tight_diag.get("tighten_frac", 0.0))
            spread_info["comm_degrade_mix"] = float(comm_fb_diag.get("degrade_mix", 0.0))
            spread_info["comm_perception_active"] = bool(comm_perception_diag.get("active", False))
            spread_info["comm_relative_distance_error_mean"] = float(
                comm_perception_diag.get("relative_distance_error_mean", 0.0)
            )
            spread_info["comm_relative_target_distance_error_mean"] = float(
                comm_perception_diag.get("relative_target_distance_error_mean", 0.0)
            )
            spread_info["comm_relative_target_distance_error_peak"] = float(
                comm_perception_diag.get("relative_target_distance_error_peak", 0.0)
            )
            spread_info["comm_team_ey_error_mean"] = float(comm_perception_diag.get("team_ey_error_mean", 0.0))
            spread_info["adjacent_distance_control_active"] = bool(
                adjacent_distance_control_step_diag.get("active", False)
            )
            spread_info["adjacent_distance_control_delta_trim"] = float(
                adjacent_distance_control_step_diag.get("delta_trim", 0.0)
            )
            spread_info["adjacent_distance_control_ax_trim"] = float(
                adjacent_distance_control_step_diag.get("ax_trim", 0.0)
            )
            spread_info["adjacent_distance_control_error_mean"] = float(
                adjacent_distance_control_step_diag.get("error_mean", 0.0)
            )
            spread_info["adjacent_distance_control_error_peak"] = float(
                adjacent_distance_control_step_diag.get("error_peak", 0.0)
            )
            spread_info["adjacent_distance_control_target_mode"] = str(
                adjacent_distance_control_step_diag.get("target_mode", adjacent_distance_target_mode)
            )
            spread_info["adjacent_distance_control_target_source"] = str(
                adjacent_distance_control_step_diag.get("target_source", "none")
            )
            spread_info["adjacent_distance_control_target_fallback_reason"] = str(
                adjacent_distance_control_step_diag.get("target_fallback_reason", "none")
            )
            spread_info["upper_lower_comm_active"] = bool(upper_lower_comm_diag.get("active", False))
            spread_info["upper_lower_comm_delay_mean"] = float(
                upper_lower_comm_diag.get("delay_steps_mean", 0.0)
            )
            spread_info["upper_lower_comm_dropout_ratio"] = float(
                upper_lower_comm_diag.get("dropout_ratio", 0.0)
            )
            spread_info["upper_lower_comm_bias_norm_mean"] = float(
                upper_lower_comm_diag.get("command_bias_norm_mean", 0.0)
            )
            spread_info["temporary_path_preview_active_ratio"] = float(
                temporary_path_preview_step_diag.get("active_ratio", 0.0)
            )
            spread_info["temporary_path_preview_mode"] = str(
                temporary_path_preview_step_diag.get("preview_mode", "shift")
            )
            spread_info["temporary_path_preview_geometric_applied_ratio"] = float(
                temporary_path_preview_step_diag.get("geometric_preview_applied_ratio", 0.0)
            )
            spread_info["temporary_path_preview_lookahead_m_mean"] = float(
                temporary_path_preview_step_diag.get("lookahead_m_mean", 0.0)
            )
            spread_info["temporary_path_preview_front_delta_est_mean"] = float(
                temporary_path_preview_step_diag.get("front_delta_est_mean", 0.0)
            )
            spread_info["temporary_path_preview_front_delta_est_max_abs"] = float(
                temporary_path_preview_step_diag.get("front_delta_est_max_abs", 0.0)
            )
            spread_info["temporary_path_preview_rear_delta_est_mean"] = float(
                temporary_path_preview_step_diag.get("rear_delta_est_mean", 0.0)
            )
            spread_info["temporary_path_preview_rear_delta_est_max_abs"] = float(
                temporary_path_preview_step_diag.get("rear_delta_est_max_abs", 0.0)
            )
            spread_info["temporary_path_preview_fourws_heading_applied_ratio"] = float(
                temporary_path_preview_step_diag.get("fourws_heading_applied_ratio", 0.0)
            )
            spread_info["temporary_path_preview_fourws_heading_adjustment_raw_mean"] = float(
                temporary_path_preview_step_diag.get("fourws_heading_adjustment_raw_mean", 0.0)
            )
            spread_info["temporary_path_preview_fourws_heading_adjustment_raw_max_abs"] = float(
                temporary_path_preview_step_diag.get("fourws_heading_adjustment_raw_max_abs", 0.0)
            )
            spread_info["temporary_path_preview_fourws_curvature_cmd_mean"] = float(
                temporary_path_preview_step_diag.get("fourws_curvature_cmd_mean", 0.0)
            )
            spread_info["temporary_path_preview_fourws_local_path_enabled_ratio"] = float(
                temporary_path_preview_step_diag.get("fourws_local_path_enabled_ratio", 0.0)
            )
            spread_info["temporary_path_preview_fourws_local_path_applied_ratio"] = float(
                temporary_path_preview_step_diag.get("fourws_local_path_applied_ratio", 0.0)
            )
            spread_info["temporary_path_preview_fourws_local_path_lateral_delta_mean"] = float(
                temporary_path_preview_step_diag.get("fourws_local_path_lateral_delta_mean", 0.0)
            )
            spread_info["temporary_path_preview_fourws_local_path_lateral_delta_max_abs"] = float(
                temporary_path_preview_step_diag.get("fourws_local_path_lateral_delta_max_abs", 0.0)
            )
            spread_info["temporary_path_preview_requested_shift_steps_mean"] = float(
                temporary_path_preview_step_diag.get("requested_preview_shift_steps_mean", 0.0)
            )
            spread_info["temporary_path_preview_configured_shift_steps_mean"] = float(
                temporary_path_preview_step_diag.get("configured_preview_shift_steps_mean", 0.0)
            )
            spread_info["temporary_path_preview_candidate_shift_steps_before_clamp_mean"] = float(
                temporary_path_preview_step_diag.get("candidate_preview_shift_steps_before_clamp_mean", 0.0)
            )
            spread_info["temporary_path_preview_candidate_shift_steps_mean"] = float(
                temporary_path_preview_step_diag.get("candidate_preview_shift_steps_mean", 0.0)
            )
            spread_info["temporary_path_preview_candidate_shift_clamped_any"] = bool(
                temporary_path_preview_step_diag.get("candidate_shift_clamped_any", False)
            )
            spread_info["temporary_path_preview_shift_steps_mean"] = float(
                temporary_path_preview_step_diag.get("applied_preview_shift_steps_mean", 0.0)
            )
            spread_info["temporary_path_preview_shift_steps_max_abs"] = float(
                temporary_path_preview_step_diag.get("applied_preview_shift_steps_max_abs", 0.0)
            )
            spread_info["temporary_path_preview_applied_shift_steps_mean"] = float(
                temporary_path_preview_step_diag.get("applied_preview_shift_steps_mean", 0.0)
            )
            spread_info["temporary_path_preview_applied_shift_steps_max_abs"] = float(
                temporary_path_preview_step_diag.get("applied_preview_shift_steps_max_abs", 0.0)
            )
            spread_info["temporary_path_preview_effective_shift_steps_mean"] = float(
                temporary_path_preview_step_diag.get("effective_preview_shift_steps_mean", 0.0)
            )
            spread_info["temporary_path_preview_blend_weight_mean"] = float(
                temporary_path_preview_step_diag.get("blend_weight_mean", 0.0)
            )
            spread_info["temporary_path_preview_terminal_pad_cols_max"] = int(
                temporary_path_preview_step_diag.get("terminal_pad_cols_max", 0)
            )
            spread_info["temporary_path_preview_terminal_pad_overshoot_cols_max"] = int(
                temporary_path_preview_step_diag.get("terminal_pad_overshoot_cols_max", 0)
            )
            spread_info["high_curvature_team_speed_cap_active"] = bool(team_speed_cap_diag["active"])
            spread_info["high_curvature_team_speed_cap_excess"] = float(team_speed_cap_diag["speed_excess"])
            spread_info["high_curvature_team_speed_cap_ax_relief"] = float(team_speed_cap_diag["ax_relief"])
            spread_info["high_curvature_team_speed_cap_target"] = float(team_speed_cap_diag["target_mps"])
            spread_info["critical_lateral_priority_active"] = bool(critical_lateral_diag["active"])
            spread_info["critical_lateral_priority_blend"] = float(critical_lateral_diag["blend"])
            spread_info["critical_lateral_priority_ax_before"] = float(critical_lateral_diag["ax_before"])
            spread_info["critical_lateral_priority_ax_after"] = float(critical_lateral_diag["ax_after"])
            spread_info["critical_lateral_priority_ax_limit"] = float(critical_lateral_diag["ax_limit"])
            spread_info["critical_lateral_ax_ceiling_active"] = bool(critical_ax_ceiling_diag["active"])
            spread_info["critical_lateral_ax_ceiling_before"] = float(critical_ax_ceiling_diag["ax_before"])
            spread_info["critical_lateral_ax_ceiling_after"] = float(critical_ax_ceiling_diag["ax_after"])
            spread_info["critical_lateral_ax_ceiling"] = float(critical_ax_ceiling_diag["ax_ceiling"])
            spread_info["spatial_switch_enabled"] = bool(spatial_switch_diag["enabled"])
            spread_info["spatial_switch_phase"] = str(spatial_switch_diag["phase"])
            spread_info["spatial_switch_s_ref"] = float(spatial_switch_diag["s_ref"])
            spread_info["spatial_switch_pre_gain"] = float(spatial_switch_diag["pre_gain"])
            spread_info["spatial_switch_lateral_gain"] = float(spatial_switch_diag["lateral_gain"])
            spread_info["spatial_switch_pre_ax_relief"] = float(spatial_switch_diag["pre_ax_relief"])
            spread_info["spatial_switch_lateral_ax_relief"] = float(spatial_switch_diag["lateral_ax_relief"])
            spread_info["spatial_switch_lateral_delta_trim"] = float(spatial_switch_diag["lateral_delta_trim"])
            spread_info["spatial_switch_progress_ax_reduction"] = float(spatial_switch_diag["progress_ax_reduction"])
            spread_info["spatial_switch_ax_before"] = float(spatial_switch_diag["ax_before"])
            spread_info["spatial_switch_ax_after"] = float(spatial_switch_diag["ax_after"])
            spread_info["spatial_switch_delta_before"] = float(spatial_switch_diag["delta_before"])
            spread_info["spatial_switch_delta_after"] = float(spatial_switch_diag["delta_after"])
            spread_info["force_aware_switch_active"] = bool(
                force_aware_command_diag.get("active", False) or force_aware_team_diag.get("active", False)
            )
            spread_info["force_aware_switch_gain"] = float(
                max(force_aware_command_diag.get("gain", 0.0), force_aware_team_diag.get("gain", 0.0))
            )
            spread_info["force_aware_switch_s_ref"] = float(force_aware_team_diag.get("s_ref", np.nan))
            spread_info["force_aware_switch_curvature"] = float(force_aware_team_diag.get("curvature", np.nan))
            spread_info["force_aware_command_delta_spread_before"] = float(
                force_aware_command_diag.get("spread_delta_before", 0.0)
            )
            spread_info["force_aware_command_delta_spread_after"] = float(
                force_aware_command_diag.get("spread_delta_after", 0.0)
            )
            spread_info["force_aware_command_ax_spread_before"] = float(
                force_aware_command_diag.get("spread_ax_before", 0.0)
            )
            spread_info["force_aware_command_ax_spread_after"] = float(
                force_aware_command_diag.get("spread_ax_after", 0.0)
            )
            spread_info["force_aware_command_spread_suppression"] = float(
                force_aware_command_diag.get("spread_suppression", 0.0)
            )
            spread_info["force_aware_team_delta_before"] = float(force_aware_team_diag.get("delta_before", np.nan))
            spread_info["force_aware_team_delta_after"] = float(force_aware_team_diag.get("delta_after", np.nan))
            spread_info["force_aware_team_ax_before"] = float(force_aware_team_diag.get("ax_before", np.nan))
            spread_info["force_aware_team_ax_after"] = float(force_aware_team_diag.get("ax_after", np.nan))
            spread_info["force_aware_team_speed_ax_relief"] = float(
                force_aware_team_diag.get("speed_ax_relief", 0.0)
            )
            spread_info["force_aware_team_blend"] = float(force_aware_team_diag.get("blend", 0.0))
            spread_info["fault_active"] = bool(fault_diag_step.get("active", False))
            spread_info["fault_deficit_norm"] = float(fault_diag_step.get("deficit_norm", 0.0))
            spread_info["tf14_global_mode"] = str(switch_diag_step.get("global_mode", "nominal_koopman_mpc"))
            spread_info["redistributed_total_delta"] = float(
                switch_diag_step.get("redistributed_total_delta", 0.0)
            )
            spread_info["redistributed_total_ax"] = float(
                switch_diag_step.get("redistributed_total_ax", 0.0)
            )
            team_input_hist[k, :] = u_team
            control_spread_hist.append(spread_info)
            connection_diag_hist.append(dict(conn_diag))
            comm_perception_diag_hist.append(dict(comm_perception_diag))
            upper_lower_comm_diag_hist.append(dict(upper_lower_comm_diag))
            adjacent_distance_control_diag_hist.append(dict(adjacent_distance_control_step_diag))
            temporary_path_preview_diag_hist.append(dict(temporary_path_preview_step_diag))
            comm_diag_hist.append({
                "step": int(k),
                "quality_global": float(comm_step_diag.get("quality_global", 1.0)),
                "mean_delay_steps": float(comm_step_diag.get("mean_delay_steps", 0.0)),
                "loss_ratio": float(comm_step_diag.get("loss_ratio", 0.0)),
                "consensus_blend_mean": float(comm_proj_diag.get("blend_mean", 0.0)),
                "tighten_frac": float(comm_tight_diag.get("tighten_frac", 0.0)),
                "degrade_mix": float(comm_fb_diag.get("degrade_mix", 0.0)),
                "quality_in_mean": float(comm_proj_diag.get("quality_in_mean", 1.0)),
                "perception_active": bool(comm_perception_diag.get("active", False)),
                "relative_distance_error_mean": float(comm_perception_diag.get("relative_distance_error_mean", 0.0)),
                "relative_distance_error_max": float(comm_perception_diag.get("relative_distance_error_max", 0.0)),
                "relative_target_distance_error_mean": float(comm_perception_diag.get("relative_target_distance_error_mean", 0.0)),
                "relative_target_distance_error_peak": float(comm_perception_diag.get("relative_target_distance_error_peak", 0.0)),
                "relative_target_distance_source": str(
                    comm_perception_diag.get("adjacent_distance_target_source", "none")
                ),
                "relative_target_distance_fallback_reason": str(
                    comm_perception_diag.get(
                        "adjacent_distance_target_fallback_reason", "none"
                    )
                ),
                "relative_actual_target_distance_error_mean": float(comm_perception_diag.get("relative_actual_target_distance_error_mean", 0.0)),
                "relative_actual_target_distance_error_peak": float(comm_perception_diag.get("relative_actual_target_distance_error_peak", 0.0)),
                "team_ey_error_mean": float(comm_perception_diag.get("team_ey_error_mean", 0.0)),
                "team_ey_error_max_abs": float(comm_perception_diag.get("team_ey_error_max_abs", 0.0)),
                "relative_state_delay_range_steps": list(
                    comm_perception_diag.get("relative_state_delay_range_steps", [0, 0])
                ),
                "team_ey_delay_range_steps": list(
                    comm_perception_diag.get("team_ey_delay_range_steps", [0, 0])
                ),
                "upper_lower_active": bool(upper_lower_comm_diag.get("active", False)),
                "upper_lower_delay_steps_mean": float(upper_lower_comm_diag.get("delay_steps_mean", 0.0)),
                "upper_lower_delay_range_steps": list(
                    upper_lower_comm_diag.get("upper_lower_delay_range_steps", [0, 0])
                ),
                "upper_lower_ref_delay_range_steps": list(
                    upper_lower_comm_diag.get("upper_lower_ref_delay_range_steps", [0, 0])
                ),
                "upper_lower_dropout_ratio": float(upper_lower_comm_diag.get("dropout_ratio", 0.0)),
                "upper_lower_command_bias_norm_mean": float(upper_lower_comm_diag.get("command_bias_norm_mean", 0.0)),
                "upper_lower_best_front_delta_bias": float(upper_lower_comm_diag.get("best_front_delta_bias", 0.0)),
                "upper_lower_path_param_bias_norm_mean": float(upper_lower_comm_diag.get("path_param_bias_norm_mean", 0.0)),
                "temporary_path_preview_active_ratio": float(temporary_path_preview_step_diag.get("active_ratio", 0.0)),
                "temporary_path_preview_requested_shift_steps_mean": float(temporary_path_preview_step_diag.get("requested_preview_shift_steps_mean", 0.0)),
                "temporary_path_preview_configured_shift_steps_mean": float(temporary_path_preview_step_diag.get("configured_preview_shift_steps_mean", 0.0)),
                "temporary_path_preview_candidate_shift_steps_before_clamp_mean": float(temporary_path_preview_step_diag.get("candidate_preview_shift_steps_before_clamp_mean", 0.0)),
                "temporary_path_preview_candidate_shift_steps_mean": float(temporary_path_preview_step_diag.get("candidate_preview_shift_steps_mean", 0.0)),
                "temporary_path_preview_candidate_shift_clamped_any": bool(temporary_path_preview_step_diag.get("candidate_shift_clamped_any", False)),
                "temporary_path_preview_applied_shift_steps_mean": float(temporary_path_preview_step_diag.get("applied_preview_shift_steps_mean", 0.0)),
                "temporary_path_preview_applied_shift_steps_max_abs": float(temporary_path_preview_step_diag.get("applied_preview_shift_steps_max_abs", 0.0)),
                "temporary_path_preview_shift_steps_mean": float(temporary_path_preview_step_diag.get("applied_preview_shift_steps_mean", 0.0)),
                "temporary_path_preview_shift_steps_max_abs": float(temporary_path_preview_step_diag.get("applied_preview_shift_steps_max_abs", 0.0)),
                "temporary_path_preview_effective_shift_steps_mean": float(temporary_path_preview_step_diag.get("effective_preview_shift_steps_mean", 0.0)),
                "temporary_path_preview_blend_weight_mean": float(temporary_path_preview_step_diag.get("blend_weight_mean", 0.0)),
                "temporary_path_preview_terminal_pad_cols_max": int(temporary_path_preview_step_diag.get("terminal_pad_cols_max", 0)),
                "temporary_path_preview_terminal_pad_overshoot_cols_max": int(temporary_path_preview_step_diag.get("terminal_pad_overshoot_cols_max", 0)),
            })

            if use_coupled_plant:
                coupled_state, physical_controls, alloc_diag = advance_joint_state(
                    coupled_state,
                    u_team,
                    ctx["dt"],
                    coupled_params,
                    coupled_cfg,
                )
                coupled_state_hist[k + 1, :] = coupled_state
                coupled_control_hist[k, :, :] = physical_controls
                coupled_alloc_diag_hist.append(dict(alloc_diag))
                local_states_next, x_team_next = frenet_states(coupled_state, coupled_path)
                progress_corrected = False
            else:
                x_team_next = ctx["safe_FK_step"](
                    team_state_hist[k, :],
                    u_team,
                    team_actual_pars,
                    SNR_DB=eval_snr_db,
                    i=k,
                    fallback_state=team_state_hist[k, :].copy(),
                    verbose=False,
                )
                x_team_next, progress_corrected = ctx["enforce_progress_and_stability"](
                    team_state_hist[k, :], x_team_next
                )
                if progress_corrected:
                    progress_guard_counts = [pg + 1 for pg in progress_guard_counts]

            team_state_hist[k + 1, :] = x_team_next
            s_now = float(team_state_hist[k + 1, 0])
            if s_now > (best_team_s + progress_eps_s):
                best_team_s = s_now
                no_progress_steps = 0
            else:
                no_progress_steps += 1
            if use_coupled_plant:
                payload_force_hist.append(
                    physical_history_row(
                        coupled_state,
                        physical_controls,
                        coupled_params,
                        step=k,
                    )
                )
            else:
                payload_force_hist.append(
                    payload_module.compute_payload_force_metrics(
                        team_state_hist[k, :], team_input_hist[k, :], team_actual_pars, i_step=k
                    )
                )
                local_states_next = connection_model.corner_states_from_team(
                    x_team_next, payload_module, payload_cfg
                )
            for v in range(num_vehicles):
                xt_case[v][k + 1, :] = ctx["clip_closed_loop_state"](
                    local_states_next[v], s_upper=team_actual_pars["s_upper"]
                )
                z_case[v][k + 1, :] = lift_fn(xt_case[v][k + 1, :])

            team_ref_next = ref_bundle["team_ref_hist"][min(k + 1, ref_bundle["team_ref_hist"].shape[0] - 1), :]
            if use_tf14_certificate:
                cert_step = tf14_certificate.update(
                    k=k,
                    team_state=x_team_next,
                    team_ref=team_ref_next,
                    mode=str(switch_diag_step.get("global_mode", "nominal_koopman_mpc")),
                    diagnoses=diag_step,
                    comm_quality_global=float(comm_step_diag.get("quality_global", 1.0)),
                )
            else:
                cert_step = {
                    "step": int(k),
                    "mode": str(switch_diag_step.get("global_mode", "nominal_koopman_mpc")),
                    "V": np.nan,
                    "predicted_upper": np.nan,
                    "contraction_margin": np.nan,
                    "disturbance_level": np.nan,
                    "identification_error": np.nan,
                    "certificate_ok": True,
                }
            tf14_certificate_hist.append(cert_step)
            prev_local_states_for_fdi = local_states_now_stack.copy()
            prev_u_sent_stack_for_fdi = lower_received_stack.copy()
            prev_u_meas_stack_for_fdi = actual_u_stack.copy()

            z_now = z_case[leader_idx][k, :].copy()
            z_next_meas = z_case[leader_idx][k + 1, :].copy()
            z_pred = dynamics_obj.eval_dot(z_now, team_input_hist[k, :], None)
            if ctx["is_finite_vector"](z_pred) and ctx["is_finite_vector"](z_next_meas):
                dz_sample = z_next_meas - z_pred
                if np.all(np.isfinite(dz_sample)) and ctx["should_take_adapt_sample"](
                    leader_idx,
                    xt_case[leader_idx][k, :],
                    dz_sample,
                    leader_idx,
                    ctx["ADAPT_CFG"],
                ):
                    z_buf.append(z_now.copy())
                    u_buf.append(team_input_hist[k, :].copy())
                    dz_buf.append(dz_sample.copy())

            adapt_every = int(max(1, ctx["ADAPT_CFG"].get("update_every", 1)))
            if realtime_mode:
                adapt_every *= realtime_adapt_stride
            if use_online_adapt and (k + 1) % adapt_every == 0:
                window = int(max(2, ctx["ADAPT_CFG"].get("window", 10)))
                packed, w_arr = ctx["weighted_stack"](
                    z_buf, window, ctx["ADAPT_CFG"].get("forget_factor", 1.0)
                )
                if packed is not None and len(u_buf) >= window and len(dz_buf) >= window:
                    z_hist = np.array(z_buf[-window:], dtype=np.float64)
                    u_hist = np.array(u_buf[-window:], dtype=np.float64)
                    dz_hist = np.array(dz_buf[-window:], dtype=np.float64)
                    try:
                        if adapt_mode == "linear_net" and structure_name == "linear":
                            dA, dB = ctx["fit_delta_linear_net"](
                                z_hist,
                                u_hist,
                                dz_hist,
                                ctx["ADAPT_CFG"],
                                nz_case,
                                num_inputs,
                                ctx["net_params_lin"],
                                del_A_prev=prev_dA,
                                del_B_prev=prev_dB,
                            )
                        elif adapt_mode == "linear_ridge" and structure_name == "linear":
                            dA, dB = ctx["fit_delta_linear_ridge"](
                                z_hist,
                                u_hist,
                                dz_hist,
                                w_arr,
                                ridge_lambda=ctx["ADAPT_CFG"].get("ridge_lambda", 1e-4),
                            )
                        elif adapt_mode == "bilinear_ridge" and structure_name == "bilinear":
                            dA, dB = ctx["fit_delta_bilinear_ridge"](
                                z_hist,
                                u_hist,
                                dz_hist,
                                w_arr,
                                ridge_lambda=ctx["ADAPT_CFG"].get("ridge_lambda", 1e-4),
                            )
                        else:
                            dA = np.zeros((nz_case, nz_case), dtype=np.float64)
                            dB = np.zeros_like(dynamics_obj.B.toarray(), dtype=np.float64)

                        da_norm, db_norm = ctx["apply_online_delta"](
                            dynamics_obj, dA, dB, structure_name, ctx["ADAPT_CFG"]
                        )
                        adapt_A_norm_hist.append(da_norm)
                        adapt_B_norm_hist.append(db_norm)
                        prev_dA = np.asarray(dA, dtype=np.float64)
                        prev_dB = np.asarray(dB, dtype=np.float64)
                    except Exception as e:
                        if k % max(1, method_cfg.get("log_interval", 100)) == 0:
                            print(f"[WARN][TF12] online adaptation skipped at step {k}: {e}")

            step_elapsed = float(time.perf_counter() - step_t0)
            step_runtime_hist.append(step_elapsed)
            if step_elapsed > float(ctx["dt"]):
                step_overrun_count += 1

            if progress_bar is not None:
                progress_bar.update(1)
                if ((k + 1) % progress_postfix_every) == 0 or k == 0:
                    try:
                        progress_bar.set_postfix_str(
                            "fail={0} q={1:.2f}".format(
                                int(np.sum(fail_counts_case)),
                                float(comm_step_diag.get("quality_global", 1.0)),
                            )
                        )
                    except Exception:
                        pass

            if max_wall_time_sec > 0.0:
                elapsed_wall = float(time.time() - begin_t)
                if elapsed_wall >= max_wall_time_sec:
                    actual_sim_steps = k + 1
                    stop_reason = "wall_time_limit"
                    print(
                        f"[TF14][WARN] wall-time limit reached: elapsed={elapsed_wall:.2f}s >= "
                        f"max_wall_time_sec={max_wall_time_sec:.2f}s; stop at step {actual_sim_steps}."
                    )
                    if progress_bar is not None:
                        try:
                            progress_bar.total = int(actual_sim_steps)
                            progress_bar.n = int(actual_sim_steps)
                            progress_bar.refresh()
                        except Exception:
                            pass
                    break

            if max_no_progress_steps > 0 and no_progress_steps >= max_no_progress_steps:
                actual_sim_steps = k + 1
                stop_reason = "no_progress_limit"
                print(
                    f"[TF14][WARN] no-progress watchdog triggered: "
                    f"no_progress_steps={no_progress_steps} >= {max_no_progress_steps}; "
                    f"best_team_s={best_team_s:.3f}; stop at step {actual_sim_steps}."
                )
                if progress_bar is not None:
                    try:
                        progress_bar.total = int(actual_sim_steps)
                        progress_bar.n = int(actual_sim_steps)
                        progress_bar.refresh()
                    except Exception:
                        pass
                break

            if enforce_full_path and (k + 1) >= sim_steps_nominal:
                reached_step = [
                    xt_case[v][k + 1, 0] >= (target_s_vehicles[v] - completion_tol_s)
                    for v in range(num_vehicles)
                ]
                if all(reached_step):
                    actual_sim_steps = k + 1
                    terminated_early_case = True
                    stop_reason = "full_path_reached"
                    if progress_bar is not None:
                        try:
                            progress_bar.total = int(actual_sim_steps)
                            progress_bar.n = int(actual_sim_steps)
                            progress_bar.refresh()
                        except Exception:
                            pass
                    break

            if k % max(1, method_cfg.get("log_interval", 100)) == 0:
                msg = (
                    f"[TF14] step {k}/{sim_steps_cap} | fail_counts={fail_counts_case} | "
                    f"payload_mask={payload_change_mask} | team_u=({u_team[0]:+.3f}, {u_team[1]:+.3f}) | "
                    f"q={comm_step_diag.get('quality_global', 1.0):.3f} "
                    f"delay={comm_step_diag.get('mean_delay_steps', 0.0):.2f} "
                    f"loss={comm_step_diag.get('loss_ratio', 0.0):.2f}"
                )
                print(msg)
    finally:
        if progress_bar is not None:
            try:
                progress_bar.close()
            except Exception:
                pass
        if gc_disabled:
            gc.enable()

    end_t = time.time()
    if progress_bar is not None and progress_print_time:
        print(f"Time Taken {end_t - begin_t:.6f}")

    for v in range(num_vehicles):
        if actual_sim_steps < traj_alloc - 1:
            xt_case[v][actual_sim_steps + 1:, :] = xt_case[v][actual_sim_steps, :]
            z_case[v][actual_sim_steps + 1:, :] = z_case[v][actual_sim_steps, :]
        if actual_sim_steps > 0 and actual_sim_steps < sim_steps_cap:
            u_case[v][actual_sim_steps:, :] = u_case[v][actual_sim_steps - 1, :]

    if actual_sim_steps < traj_alloc - 1:
        team_state_hist[actual_sim_steps + 1:, :] = team_state_hist[actual_sim_steps, :]
    if actual_sim_steps > 0 and actual_sim_steps < sim_steps_cap:
        team_input_hist[actual_sim_steps:, :] = team_input_hist[actual_sim_steps - 1, :]

    vehicle_metrics = []
    eval_len = actual_sim_steps + 1
    for v in range(num_vehicles):
        ref_hist_v = raw_ref_vehicle_hist[v]
        ref_eval_v = ref_hist_v[:eval_len, :]
        e_long, e_lat = coordinator.compute_vehicle_errors(
            xt_case[v][:eval_len, :], ref_eval_v
        )
        valid = np.isfinite(e_long) & np.isfinite(e_lat)
        if np.any(valid):
            rmse_lat = float(np.sqrt(np.mean(e_lat[valid] ** 2)))
            rmse_long = float(np.sqrt(np.mean(e_long[valid] ** 2)))
            max_lat = float(np.max(np.abs(e_lat[valid])))
            max_long = float(np.max(np.abs(e_long[valid])))
        else:
            rmse_lat = rmse_long = max_lat = max_long = np.inf

        vehicle_metrics.append({
            "vehicle": v + 1,
            "rmse_lat": rmse_lat,
            "rmse_long": rmse_long,
            "max_lat": max_lat,
            "max_long": max_long,
        })

    rmse_lat_mean = float(np.mean([m["rmse_lat"] for m in vehicle_metrics]))
    rmse_long_mean = float(np.mean([m["rmse_long"] for m in vehicle_metrics]))
    max_lat_global = float(np.max([m["max_lat"] for m in vehicle_metrics]))
    max_long_global = float(np.max([m["max_long"] for m in vehicle_metrics]))
    final_s_team = float(team_state_hist[actual_sim_steps, 0])
    if "team_ref_hist" in ref_bundle and len(ref_bundle["team_ref_hist"]) > 0:
        target_s_team = float(ref_bundle["team_ref_hist"][-1, 0])
    else:
        target_s_team = float(np.max(target_s_vehicles)) if len(target_s_vehicles) > 0 else float(max(traj_length - 1, 1))
    progress_ratio = float(np.clip(final_s_team / max(target_s_team, 1e-6), 0.0, 1.0))
    final_s_vehicles = [float(xt_case[v][actual_sim_steps, 0]) for v in range(num_vehicles)]
    full_path_flags = [
        bool(final_s_vehicles[v] >= (target_s_vehicles[v] - completion_tol_s))
        for v in range(num_vehicles)
    ]
    if len(connection_diag_hist) > 0:
        conn_ds_peak = float(np.max([d.get("max_abs_ds", 0.0) for d in connection_diag_hist]))
        conn_dey_peak = float(np.max([d.get("max_abs_dey", 0.0) for d in connection_diag_hist]))
        conn_dpsi_peak = float(np.max([d.get("max_abs_dpsi", 0.0) for d in connection_diag_hist]))
        conn_rms_mean = float(np.mean([d.get("rms_rel", 0.0) for d in connection_diag_hist]))
    else:
        conn_ds_peak = conn_dey_peak = conn_dpsi_peak = conn_rms_mean = 0.0
    relative_state_delay_range_steps = _delay_range_steps(method_cfg, "comm_relative_state", None)
    team_ey_delay_range_steps = _delay_range_steps(method_cfg, "comm_team_ey", None)
    upper_lower_delay_range_steps = _delay_range_steps(method_cfg, "upper_lower_comm", None)
    upper_lower_ref_delay_range_steps = _delay_range_steps(
        method_cfg, "upper_lower_comm_ref", "upper_lower_comm"
    )
    if len(comm_diag_hist) > 0:
        comm_quality_mean = float(np.mean([d.get("quality_global", 1.0) for d in comm_diag_hist]))
        comm_quality_min = float(np.min([d.get("quality_global", 1.0) for d in comm_diag_hist]))
        comm_delay_mean = float(np.mean([d.get("mean_delay_steps", 0.0) for d in comm_diag_hist]))
        comm_loss_mean = float(np.mean([d.get("loss_ratio", 0.0) for d in comm_diag_hist]))
        comm_tighten_mean = float(np.mean([d.get("tighten_frac", 0.0) for d in comm_diag_hist]))
        comm_degrade_peak = float(np.max([d.get("degrade_mix", 0.0) for d in comm_diag_hist]))
        comm_rel_dist_err_mean = float(np.mean([d.get("relative_distance_error_mean", 0.0) for d in comm_diag_hist]))
        comm_rel_dist_err_peak = float(np.max([d.get("relative_distance_error_max", 0.0) for d in comm_diag_hist]))
        comm_rel_target_dist_err_mean = float(np.mean([d.get("relative_target_distance_error_mean", 0.0) for d in comm_diag_hist]))
        comm_rel_target_dist_err_peak = float(np.max([d.get("relative_target_distance_error_peak", 0.0) for d in comm_diag_hist]))
        comm_rel_actual_target_dist_err_mean = float(np.mean([d.get("relative_actual_target_distance_error_mean", 0.0) for d in comm_diag_hist]))
        comm_rel_actual_target_dist_err_peak = float(np.max([d.get("relative_actual_target_distance_error_peak", 0.0) for d in comm_diag_hist]))
        comm_team_ey_err_mean_abs = float(np.mean([abs(d.get("team_ey_error_mean", 0.0)) for d in comm_diag_hist]))
        comm_team_ey_err_peak = float(np.max([d.get("team_ey_error_max_abs", 0.0) for d in comm_diag_hist]))
        upper_lower_delay_mean = float(np.mean([d.get("upper_lower_delay_steps_mean", 0.0) for d in comm_diag_hist]))
        upper_lower_dropout_mean = float(np.mean([d.get("upper_lower_dropout_ratio", 0.0) for d in comm_diag_hist]))
        upper_lower_cmd_bias_mean = float(np.mean([d.get("upper_lower_command_bias_norm_mean", 0.0) for d in comm_diag_hist]))
        upper_lower_cmd_bias_peak = float(np.max([d.get("upper_lower_command_bias_norm_mean", 0.0) for d in comm_diag_hist]))
        upper_lower_path_bias_mean = float(np.mean([d.get("upper_lower_path_param_bias_norm_mean", 0.0) for d in comm_diag_hist]))
    else:
        comm_quality_mean = comm_quality_min = 1.0
        comm_delay_mean = comm_loss_mean = 0.0
        comm_tighten_mean = comm_degrade_peak = 0.0
        comm_rel_dist_err_mean = comm_rel_dist_err_peak = 0.0
        comm_rel_target_dist_err_mean = comm_rel_target_dist_err_peak = 0.0
        comm_rel_actual_target_dist_err_mean = comm_rel_actual_target_dist_err_peak = 0.0
        comm_team_ey_err_mean_abs = comm_team_ey_err_peak = 0.0
        upper_lower_delay_mean = upper_lower_dropout_mean = 0.0
        upper_lower_cmd_bias_mean = upper_lower_cmd_bias_peak = 0.0
        upper_lower_path_bias_mean = 0.0
    if len(temporary_path_preview_diag_hist) > 0:
        temp_preview_active_ratio_mean = float(
            np.mean([d.get("active_ratio", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_applied_ratio_mean = float(
            np.mean([d.get("applied_ratio", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_geometric_applied_ratio_mean = float(
            np.mean([d.get("geometric_preview_applied_ratio", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_lookahead_mean = float(
            np.mean([d.get("lookahead_m_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_front_delta_mean = float(
            np.mean([d.get("front_delta_est_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_front_delta_peak_abs = float(
            np.max([d.get("front_delta_est_max_abs", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_rear_delta_mean = float(
            np.mean([d.get("rear_delta_est_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_rear_delta_peak_abs = float(
            np.max([d.get("rear_delta_est_max_abs", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_fourws_optimizer_enabled_ratio = float(
            np.mean([bool(d.get("fourws_optimizer_enabled", False)) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_fourws_optimizer_curvature_error_mean_abs = float(
            np.mean([abs(d.get("fourws_optimizer_curvature_error_mean", 0.0)) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_fourws_optimizer_curvature_error_peak_abs = float(
            np.max([d.get("fourws_optimizer_curvature_error_max_abs", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_fourws_optimizer_sideslip_peak_abs = float(
            np.max([d.get("fourws_optimizer_sideslip_beta_max_abs", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_fourws_heading_applied_ratio_mean = float(
            np.mean([d.get("fourws_heading_applied_ratio", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_fourws_heading_adjustment_mean = float(
            np.mean([d.get("fourws_heading_adjustment_raw_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_fourws_heading_adjustment_peak_abs = float(
            np.max([d.get("fourws_heading_adjustment_raw_max_abs", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_fourws_curvature_cmd_mean = float(
            np.mean([d.get("fourws_curvature_cmd_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_requested_shift_mean = float(
            np.mean([d.get("requested_preview_shift_steps_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_requested_shift_peak_abs = float(
            np.max([d.get("requested_preview_shift_steps_max_abs", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_configured_shift_mean = float(
            np.mean([d.get("configured_preview_shift_steps_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_configured_shift_peak_abs = float(
            np.max([d.get("configured_preview_shift_steps_max_abs", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_candidate_shift_before_clamp_mean = float(
            np.mean([d.get("candidate_preview_shift_steps_before_clamp_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_candidate_shift_before_clamp_peak_abs = float(
            np.max([d.get("candidate_preview_shift_steps_before_clamp_max_abs", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_candidate_shift_clamped_steps = int(
            np.sum([d.get("candidate_shift_clamped_count", 0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_candidate_shift_mean = float(
            np.mean([d.get("candidate_preview_shift_steps_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_candidate_shift_peak_abs = float(
            np.max([d.get("candidate_preview_shift_steps_max_abs", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_shift_mean = float(
            np.mean([d.get("applied_preview_shift_steps_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_shift_peak_abs = float(
            np.max([d.get("applied_preview_shift_steps_max_abs", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_effective_shift_mean = float(
            np.mean([d.get("effective_preview_shift_steps_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_effective_shift_peak_abs = float(
            np.max([d.get("effective_preview_shift_steps_max_abs", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_blend_weight_mean = float(
            np.mean([d.get("blend_weight_mean", 0.0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_terminal_pad_peak = int(
            np.max([d.get("terminal_pad_cols_max", 0) for d in temporary_path_preview_diag_hist])
        )
        temp_preview_terminal_overshoot_peak = int(
            np.max([d.get("terminal_pad_overshoot_cols_max", 0) for d in temporary_path_preview_diag_hist])
        )
    else:
        temp_preview_active_ratio_mean = 0.0
        temp_preview_applied_ratio_mean = 0.0
        temp_preview_geometric_applied_ratio_mean = 0.0
        temp_preview_lookahead_mean = 0.0
        temp_preview_front_delta_mean = 0.0
        temp_preview_front_delta_peak_abs = 0.0
        temp_preview_rear_delta_mean = 0.0
        temp_preview_rear_delta_peak_abs = 0.0
        temp_preview_fourws_optimizer_enabled_ratio = 0.0
        temp_preview_fourws_optimizer_curvature_error_mean_abs = 0.0
        temp_preview_fourws_optimizer_curvature_error_peak_abs = 0.0
        temp_preview_fourws_optimizer_sideslip_peak_abs = 0.0
        temp_preview_fourws_heading_applied_ratio_mean = 0.0
        temp_preview_fourws_heading_adjustment_mean = 0.0
        temp_preview_fourws_heading_adjustment_peak_abs = 0.0
        temp_preview_fourws_curvature_cmd_mean = 0.0
        temp_preview_requested_shift_mean = 0.0
        temp_preview_requested_shift_peak_abs = 0.0
        temp_preview_configured_shift_mean = 0.0
        temp_preview_configured_shift_peak_abs = 0.0
        temp_preview_candidate_shift_before_clamp_mean = 0.0
        temp_preview_candidate_shift_before_clamp_peak_abs = 0.0
        temp_preview_candidate_shift_clamped_steps = 0
        temp_preview_candidate_shift_mean = 0.0
        temp_preview_candidate_shift_peak_abs = 0.0
        temp_preview_shift_mean = 0.0
        temp_preview_shift_peak_abs = 0.0
        temp_preview_effective_shift_mean = 0.0
        temp_preview_effective_shift_peak_abs = 0.0
        temp_preview_blend_weight_mean = 0.0
        temp_preview_terminal_pad_peak = 0
        temp_preview_terminal_overshoot_peak = 0
    pair_error_peak = 0.0
    pair_error_peak_pair = ""
    pair_target_error_peak = 0.0
    pair_target_error_peak_pair = ""
    for d in comm_perception_diag_hist:
        for pair_d in d.get("relative_pair_diag", []):
            err = float(pair_d.get("abs_distance_error", 0.0))
            if err >= pair_error_peak:
                pair_error_peak = err
                pair_error_peak_pair = str(pair_d.get("pair", ""))
            target_err = float(pair_d.get("abs_measured_distance_error_to_target", 0.0))
            if target_err >= pair_target_error_peak:
                pair_target_error_peak = target_err
                pair_target_error_peak_pair = str(pair_d.get("pair", ""))
    if len(adjacent_distance_control_diag_hist) > 0:
        adjacent_distance_control_active_steps = int(
            np.sum([bool(d.get("active", False)) for d in adjacent_distance_control_diag_hist])
        )
        adjacent_distance_control_delta_trim_mean = float(
            np.mean([abs(d.get("delta_trim", 0.0)) for d in adjacent_distance_control_diag_hist])
        )
        adjacent_distance_control_delta_trim_peak_abs = float(
            np.max([d.get("delta_trim_max_abs", 0.0) for d in adjacent_distance_control_diag_hist])
        )
        adjacent_distance_control_ax_trim_mean = float(
            np.mean([abs(d.get("ax_trim", 0.0)) for d in adjacent_distance_control_diag_hist])
        )
        adjacent_distance_control_ax_trim_peak_abs = float(
            np.max([d.get("ax_trim_max_abs", 0.0) for d in adjacent_distance_control_diag_hist])
        )
        adjacent_distance_control_error_mean = float(
            np.mean([d.get("error_mean", 0.0) for d in adjacent_distance_control_diag_hist])
        )
        adjacent_distance_control_error_peak = float(
            np.max([d.get("error_peak", 0.0) for d in adjacent_distance_control_diag_hist])
        )
    else:
        adjacent_distance_control_active_steps = 0
        adjacent_distance_control_delta_trim_mean = 0.0
        adjacent_distance_control_delta_trim_peak_abs = 0.0
        adjacent_distance_control_ax_trim_mean = 0.0
        adjacent_distance_control_ax_trim_peak_abs = 0.0
        adjacent_distance_control_error_mean = 0.0
        adjacent_distance_control_error_peak = 0.0
    adjacent_distance_target_source_text, adjacent_distance_target_source_list = (
        _adjacent_distance_unique_text(
            [
                adjacent_distance_target_sources[i][j]
                for i in range(num_vehicles)
                for j in range(num_vehicles)
                if adjacent_distance_target_sources[i][j] != "not_applicable"
            ]
        )
    )
    adjacent_distance_target_fallback_text, adjacent_distance_target_fallback_list = (
        _adjacent_distance_unique_text(
            [
                adjacent_distance_target_fallback_reasons[i][j]
                for i in range(num_vehicles)
                for j in range(num_vehicles)
                if adjacent_distance_target_fallback_reasons[i][j] != "not_applicable"
            ]
        )
    )
    if len(adjacent_distance_control_diag_hist) > 0:
        adjacent_distance_control_target_source_text, adjacent_distance_control_target_source_list = (
            _adjacent_distance_unique_text(
                [
                    source
                    for d in adjacent_distance_control_diag_hist
                    for source in list(d.get("target_sources", []))
                ]
                + [
                    d.get("target_source", "unavailable")
                    for d in adjacent_distance_control_diag_hist
                    if not d.get("target_sources", [])
                ]
            )
        )
        adjacent_distance_control_fallback_text, adjacent_distance_control_fallback_list = (
            _adjacent_distance_unique_text(
                [
                    reason
                    for d in adjacent_distance_control_diag_hist
                    for reason in list(d.get("target_fallback_reasons", []))
                ]
                + [
                    d.get("target_fallback_reason", "none")
                    for d in adjacent_distance_control_diag_hist
                    if not d.get("target_fallback_reasons", [])
                ]
            )
        )
    else:
        adjacent_distance_control_target_source_text = adjacent_distance_target_source_text
        adjacent_distance_control_target_source_list = adjacent_distance_target_source_list
        adjacent_distance_control_fallback_text = adjacent_distance_target_fallback_text
        adjacent_distance_control_fallback_list = adjacent_distance_target_fallback_list
    fault_active_steps = int(np.sum([1 for d in fault_diag_hist if d.get("active", False)]))
    fault_deficit_peak = float(
        np.max([d.get("deficit_norm", 0.0) for d in fault_diag_hist]) if len(fault_diag_hist) > 0 else 0.0
    )
    tf14_fdi_summary = tf14_fdi_monitor.summarize(tf14_fdi_diag_hist)
    tf14_switch_summary = tf14_switcher.summarize(tf14_switch_diag_hist)
    phase_role_summary = phase_role_scheduler.summarize(phase_role_diag_hist)
    tf14_certificate_summary = tf14_certificate.summarize(tf14_certificate_hist)
    tf14_interaction_summary = summarize_tf14_interactions(
        fdi_hist=tf14_fdi_diag_hist,
        switch_hist=tf14_switch_diag_hist,
        certificate_hist=tf14_certificate_hist,
        comm_diag_hist=comm_diag_hist,
        fault_diag_hist=fault_diag_hist,
        control_spread_hist=control_spread_hist,
        payload_force_hist=payload_force_hist,
        dt=ctx["dt"],
    )
    coupled_summary = (
        summarize_physical_history(payload_force_hist, coupled_params)
        if use_coupled_plant
        else {}
    )
    payload_force_summary = (
        coupled_summary
        if use_coupled_plant
        else payload_module.summarize_force_history(payload_force_hist)
    )

    result = {
        "case": method_cfg,
        "case_name": "tf14_main",
        "modules": dict(
            ctx.get(
                "TF14_MODULES_MAIN",
                ctx.get("TF13_MODULES_MAIN", ctx.get("TF12_MODULES_MAIN", ctx.get("TF11_MODULES_MAIN", {}))),
            )
        ),
        "xt_actual_vehicles": xt_case,
        "u_vehicles": u_case,
        "z_vehicles": z_case,
        "team_state_hist": team_state_hist,
        "team_input_hist": team_input_hist,
        "x0_team": x0_team.copy(),
        "ref_team_hist": ref_bundle["team_ref_hist"],
        "ref_vehicle_histories": raw_ref_vehicle_hist,
        "ref_leader_relative_targets": ref_bundle["leader_relative_targets"],
        "payload_force_hist": payload_force_hist,
        "payload_force_summary": payload_force_summary,
        "plant_mode": plant_mode,
        "payload_change_mask": tuple(payload_change_mask),
        "payload_actual_params": {
            "m": float(team_actual_pars["m"]),
            "Iz": float(team_actual_pars["Iz"]),
            "Cf": float(team_actual_pars["Cf"]),
            "Cr": float(team_actual_pars["Cr"]),
            "lf": float(team_actual_pars["lf"]),
            "lr": float(team_actual_pars["lr"]),
            "uncertainty_mode": str(team_actual_pars.get("uncertainty", "NA")),
            "uncertainty_amp": float(team_actual_pars.get("amp", 0.0)),
            "uncertainty_freq": float(team_actual_pars.get("freq", 1.0)),
        },
        "control_spread_hist": control_spread_hist,
        "connection_diag_hist": connection_diag_hist,
        "comm_diag_hist": comm_diag_hist,
        "comm_perception_diag_hist": comm_perception_diag_hist,
        "upper_lower_comm_diag_hist": upper_lower_comm_diag_hist,
        "adjacent_distance_control_diag_hist": adjacent_distance_control_diag_hist,
        "temporary_path_preview_diag_hist": temporary_path_preview_diag_hist,
        "fault_diag_hist": fault_diag_hist,
        "tf14_fdi_diag_hist": tf14_fdi_diag_hist,
        "tf14_switch_diag_hist": tf14_switch_diag_hist,
        "phase_role_diag_hist": phase_role_diag_hist,
        "tf14_certificate_hist": tf14_certificate_hist,
        "connection_compliance_enabled": bool(use_connection_compliance and (not use_coupled_plant)),
        "physical_connector_enabled": bool(use_coupled_plant),
        "comm_quality_consensus_enabled": bool(use_comm_quality_consensus),
        "comm_delay_compensation_enabled": bool(use_delay_compensation),
        "comm_constraint_tightening_enabled": bool(use_comm_constraint_tightening),
        "comm_degraded_fallback_enabled": bool(use_comm_degraded_fallback),
        "comm_restructure_enabled": bool(use_comm_restructure),
        "upper_lower_comm_enabled": bool(use_upper_lower_comm),
        "adjacent_distance_control_enabled": bool(use_adjacent_distance_control),
        "temporary_path_preview_enabled": bool(use_temporary_path_preview),
        "temporary_path_preview_mode": str(temporary_path_preview_mode),
        "temporary_path_preview_use_ref_s": bool(temporary_path_preview_use_ref_s),
        "fault_tolerant_enabled": bool(enable_fault_tolerant_control),
        "tf14_online_fdi_enabled": bool(use_online_fdi),
        "tf14_online_fault_identification_enabled": bool(use_online_fault_identification),
        "tf14_online_ftc_switching_enabled": bool(use_online_ftc_switching),
        "phase_role_scheduler_enabled": bool(use_phase_role_scheduler),
        "tf14_certificate_enabled": bool(use_tf14_certificate),
        "fault_settings": {
            "vehicle_index": int(fault_vehicle_index),
            "mode": str(fault_mode),
            "start_step": int(fault_start_step),
            "start_s": float(fault_start_s),
            "ax_scale": float(fault_ax_scale),
            "delta_scale": float(fault_delta_scale),
            "redistribution": bool(fault_tolerant_redistribution),
        },
        "connection_summary": {
            "max_abs_ds_peak": conn_ds_peak,
            "max_abs_dey_peak": conn_dey_peak,
            "max_abs_dpsi_peak": conn_dpsi_peak,
            "rms_rel_mean": conn_rms_mean,
        },
        "comm_summary": {
            "quality_mean": comm_quality_mean,
            "quality_min": comm_quality_min,
            "delay_mean": comm_delay_mean,
            "delay_steps_mean": comm_delay_mean,
            "loss_mean": comm_loss_mean,
            "loss_ratio_mean": comm_loss_mean,
            "tighten_frac_mean": comm_tighten_mean,
            "degrade_mix_peak": comm_degrade_peak,
            "relative_distance_error_mean": comm_rel_dist_err_mean,
            "relative_distance_error_peak": comm_rel_dist_err_peak,
            "relative_target_distance_error_mean": comm_rel_target_dist_err_mean,
            "relative_target_distance_error_peak": comm_rel_target_dist_err_peak,
            "relative_actual_target_distance_error_mean": comm_rel_actual_target_dist_err_mean,
            "relative_actual_target_distance_error_peak": comm_rel_actual_target_dist_err_peak,
            "relative_state_delay_range_steps": relative_state_delay_range_steps,
            "relative_pair_distance_error_peak": pair_error_peak,
            "relative_pair_distance_error_peak_pair": pair_error_peak_pair,
            "relative_pair_target_distance_error_peak": pair_target_error_peak,
            "relative_pair_target_distance_error_peak_pair": pair_target_error_peak_pair,
            "adjacent_distance_target_source": adjacent_distance_target_source_text,
            "adjacent_distance_target_sources": adjacent_distance_target_source_list,
            "adjacent_distance_target_fallback_reason": adjacent_distance_target_fallback_text,
            "adjacent_distance_target_fallback_reasons": adjacent_distance_target_fallback_list,
            "team_ey_error_mean_abs": comm_team_ey_err_mean_abs,
            "team_ey_error_peak_abs": comm_team_ey_err_peak,
            "team_ey_delay_range_steps": team_ey_delay_range_steps,
            "upper_lower_delay_range_steps": upper_lower_delay_range_steps,
            "upper_lower_delay_steps_mean": upper_lower_delay_mean,
            "upper_lower_dropout_ratio_mean": upper_lower_dropout_mean,
            "upper_lower_command_bias_norm_mean": upper_lower_cmd_bias_mean,
            "upper_lower_command_bias_norm_peak": upper_lower_cmd_bias_peak,
            "upper_lower_ref_delay_range_steps": upper_lower_ref_delay_range_steps,
            "upper_lower_path_param_bias_norm_mean": upper_lower_path_bias_mean,
            "temporary_path_preview_active_ratio_mean": temp_preview_active_ratio_mean,
            "temporary_path_preview_applied_ratio_mean": temp_preview_applied_ratio_mean,
            "temporary_path_preview_geometric_applied_ratio_mean": temp_preview_geometric_applied_ratio_mean,
            "temporary_path_preview_lookahead_m_mean": temp_preview_lookahead_mean,
            "temporary_path_preview_front_delta_est_mean": temp_preview_front_delta_mean,
            "temporary_path_preview_front_delta_est_peak_abs": temp_preview_front_delta_peak_abs,
            "temporary_path_preview_rear_delta_est_mean": temp_preview_rear_delta_mean,
            "temporary_path_preview_rear_delta_est_peak_abs": temp_preview_rear_delta_peak_abs,
            "temporary_path_preview_fourws_optimizer_enabled_ratio": temp_preview_fourws_optimizer_enabled_ratio,
            "temporary_path_preview_fourws_optimizer_curvature_error_mean_abs": (
                temp_preview_fourws_optimizer_curvature_error_mean_abs
            ),
            "temporary_path_preview_fourws_optimizer_curvature_error_peak_abs": (
                temp_preview_fourws_optimizer_curvature_error_peak_abs
            ),
            "temporary_path_preview_fourws_optimizer_sideslip_peak_abs": (
                temp_preview_fourws_optimizer_sideslip_peak_abs
            ),
            "temporary_path_preview_fourws_heading_applied_ratio_mean": temp_preview_fourws_heading_applied_ratio_mean,
            "temporary_path_preview_fourws_heading_adjustment_raw_mean": temp_preview_fourws_heading_adjustment_mean,
            "temporary_path_preview_fourws_heading_adjustment_raw_peak_abs": temp_preview_fourws_heading_adjustment_peak_abs,
            "temporary_path_preview_fourws_curvature_cmd_mean": temp_preview_fourws_curvature_cmd_mean,
            "temporary_path_preview_requested_shift_steps_mean": temp_preview_requested_shift_mean,
            "temporary_path_preview_requested_shift_steps_peak_abs": temp_preview_requested_shift_peak_abs,
            "temporary_path_preview_configured_shift_steps_mean": temp_preview_configured_shift_mean,
            "temporary_path_preview_configured_shift_steps_peak_abs": temp_preview_configured_shift_peak_abs,
            "temporary_path_preview_candidate_shift_steps_before_clamp_mean": temp_preview_candidate_shift_before_clamp_mean,
            "temporary_path_preview_candidate_shift_steps_before_clamp_peak_abs": temp_preview_candidate_shift_before_clamp_peak_abs,
            "temporary_path_preview_candidate_shift_clamped_steps": temp_preview_candidate_shift_clamped_steps,
            "temporary_path_preview_candidate_shift_steps_mean": temp_preview_candidate_shift_mean,
            "temporary_path_preview_candidate_shift_steps_peak_abs": temp_preview_candidate_shift_peak_abs,
            "temporary_path_preview_applied_shift_steps_mean": temp_preview_shift_mean,
            "temporary_path_preview_applied_shift_steps_peak_abs": temp_preview_shift_peak_abs,
            "temporary_path_preview_shift_steps_mean": temp_preview_shift_mean,
            "temporary_path_preview_shift_steps_peak_abs": temp_preview_shift_peak_abs,
            "temporary_path_preview_effective_shift_steps_mean": temp_preview_effective_shift_mean,
            "temporary_path_preview_effective_shift_steps_peak_abs": temp_preview_effective_shift_peak_abs,
            "temporary_path_preview_blend_weight_mean": temp_preview_blend_weight_mean,
            "temporary_path_preview_terminal_pad_cols_peak": temp_preview_terminal_pad_peak,
            "temporary_path_preview_terminal_pad_overshoot_cols_peak": temp_preview_terminal_overshoot_peak,
            "restructure_enabled": bool(use_comm_restructure),
            "upper_lower_enabled": bool(use_upper_lower_comm),
        },
        "adjacent_distance_control_settings": {
            "enabled": bool(use_adjacent_distance_control),
            "target_mode": str(adjacent_distance_target_mode),
            "targets": adjacent_distance_targets.tolist(),
            "target_source": adjacent_distance_target_source_text,
            "target_sources": adjacent_distance_target_source_list,
            "target_sources_matrix": adjacent_distance_target_sources,
            "target_fallback_reason": adjacent_distance_target_fallback_text,
            "target_fallback_reasons": adjacent_distance_target_fallback_list,
            "target_fallback_reasons_matrix": adjacent_distance_target_fallback_reasons,
            "k_s": float(method_cfg.get("adjacent_distance_k_s", 0.10)),
            "k_ey": float(method_cfg.get("adjacent_distance_k_ey", 0.025)),
            "k_v": float(method_cfg.get("adjacent_distance_k_v", 0.04)),
            "deadband_m": float(method_cfg.get("adjacent_distance_deadband_m", 0.03)),
            "error_clip_m": float(method_cfg.get("adjacent_distance_error_clip_m", 0.30)),
            "ax_clip": float(method_cfg.get("adjacent_distance_ax_clip", 0.12)),
            "delta_clip": float(method_cfg.get("adjacent_distance_delta_clip", 0.015)),
            "filter_beta": float(method_cfg.get("adjacent_distance_filter_beta", 0.50)),
            "min_comm_quality": float(method_cfg.get("adjacent_distance_min_comm_quality", 0.0)),
        },
        "adjacent_distance_control_summary": {
            "enabled": bool(use_adjacent_distance_control),
            "active_steps": int(adjacent_distance_control_active_steps),
            "active_ratio": float(adjacent_distance_control_active_steps / max(1, actual_sim_steps)),
            "target_mode": str(adjacent_distance_target_mode),
            "target_source": adjacent_distance_control_target_source_text,
            "target_sources": adjacent_distance_control_target_source_list,
            "target_fallback_reason": adjacent_distance_control_fallback_text,
            "target_fallback_reasons": adjacent_distance_control_fallback_list,
            "delta_trim_mean_abs": adjacent_distance_control_delta_trim_mean,
            "delta_trim_peak_abs": adjacent_distance_control_delta_trim_peak_abs,
            "ax_trim_mean_abs": adjacent_distance_control_ax_trim_mean,
            "ax_trim_peak_abs": adjacent_distance_control_ax_trim_peak_abs,
            "error_mean": adjacent_distance_control_error_mean,
            "error_peak": adjacent_distance_control_error_peak,
        },
        "comm_restructure_settings": {
            "enabled": bool(use_comm_restructure),
            "upper_lower_enabled": bool(use_upper_lower_comm),
            "trigger_mode": str(method_cfg.get("comm_fault_trigger_mode", "step_and_s")),
            "start_step": int(method_cfg.get("comm_fault_start_step", 0)),
            "start_s": float(method_cfg.get("comm_fault_start_s", 0.0)),
            "end_step": None if method_cfg.get("comm_fault_end_step", None) is None else int(method_cfg.get("comm_fault_end_step")),
            "end_s": None if method_cfg.get("comm_fault_end_s", None) is None else float(method_cfg.get("comm_fault_end_s")),
            "relative_state_delay_steps": int(method_cfg.get("comm_relative_state_delay_steps", 0)),
            "relative_state_variable_delay_min_steps": int(method_cfg.get("comm_relative_state_variable_delay_min_steps", 0)),
            "relative_state_variable_delay_max_steps": int(method_cfg.get("comm_relative_state_variable_delay_max_steps", 0)),
            "relative_state_delay_range_steps": relative_state_delay_range_steps,
            "relative_state_dropout_prob": float(method_cfg.get("comm_relative_state_dropout_prob", 0.0)),
            "relative_state_noise_std": _cfg_jsonable(method_cfg.get("comm_relative_state_noise_std", 0.0)),
            "relative_state_bias": _cfg_jsonable(method_cfg.get("comm_relative_state_bias", 0.0)),
            "relative_state_scale": _cfg_jsonable(method_cfg.get("comm_relative_state_scale", 1.0)),
            "relative_distance_noise_std": float(method_cfg.get("comm_relative_distance_noise_std", 0.0)),
            "relative_distance_bias": float(method_cfg.get("comm_relative_distance_bias", 0.0)),
            "relative_distance_scale": float(method_cfg.get("comm_relative_distance_scale", 1.0)),
            "team_ey_delay_steps": int(method_cfg.get("comm_team_ey_delay_steps", 0)),
            "team_ey_variable_delay_min_steps": int(method_cfg.get("comm_team_ey_variable_delay_min_steps", 0)),
            "team_ey_variable_delay_max_steps": int(method_cfg.get("comm_team_ey_variable_delay_max_steps", 0)),
            "team_ey_delay_range_steps": team_ey_delay_range_steps,
            "team_ey_dropout_prob": float(method_cfg.get("comm_team_ey_dropout_prob", 0.0)),
            "team_ey_noise_std": float(method_cfg.get("comm_team_ey_noise_std", 0.0)),
            "team_ey_bias": float(method_cfg.get("comm_team_ey_bias", 0.0)),
            "team_ey_scale": float(method_cfg.get("comm_team_ey_scale", 1.0)),
            "upper_lower_delay_steps": int(method_cfg.get("upper_lower_comm_delay_steps", 0)),
            "upper_lower_variable_delay_min_steps": int(method_cfg.get("upper_lower_comm_variable_delay_min_steps", 0)),
            "upper_lower_variable_delay_max_steps": int(method_cfg.get("upper_lower_comm_variable_delay_max_steps", 0)),
            "upper_lower_delay_range_steps": upper_lower_delay_range_steps,
            "upper_lower_dropout_prob": float(method_cfg.get("upper_lower_comm_dropout_prob", 0.0)),
            "upper_lower_noise_std": _cfg_jsonable(method_cfg.get("upper_lower_comm_noise_std", 0.0)),
            "upper_lower_bias": _cfg_jsonable(method_cfg.get("upper_lower_comm_bias", 0.0)),
            "upper_lower_scale": _cfg_jsonable(method_cfg.get("upper_lower_comm_scale", 1.0)),
            "upper_lower_ref_delay_steps": int(method_cfg.get("upper_lower_comm_ref_delay_steps", 0)),
            "upper_lower_ref_variable_delay_min_steps": int(method_cfg.get("upper_lower_comm_ref_variable_delay_min_steps", 0)),
            "upper_lower_ref_variable_delay_max_steps": int(method_cfg.get("upper_lower_comm_ref_variable_delay_max_steps", 0)),
            "upper_lower_ref_delay_range_steps": upper_lower_ref_delay_range_steps,
            "upper_lower_ref_dropout_prob": float(method_cfg.get("upper_lower_comm_ref_dropout_prob", 0.0)),
            "upper_lower_ref_noise_std": _cfg_jsonable(method_cfg.get("upper_lower_comm_ref_noise_std", 0.0)),
            "upper_lower_ref_bias": _cfg_jsonable(method_cfg.get("upper_lower_comm_ref_bias", 0.0)),
            "upper_lower_ref_scale": _cfg_jsonable(method_cfg.get("upper_lower_comm_ref_scale", 1.0)),
        },
        "temporary_path_preview_settings": {
            "enabled": bool(use_temporary_path_preview),
            "mode": str(temporary_path_preview_mode),
            "current_path_mode": str(suite_path_mode),
            "path_modes": _cfg_jsonable(method_cfg.get("temporary_path_preview_path_modes", None)),
            "path_mode_allowed": bool(
                _path_mode_allowed(method_cfg.get("temporary_path_preview_path_modes", None))
            ),
            "trigger_mode": str(method_cfg.get("temporary_path_preview_trigger_mode", "s")),
            "start_step": int(method_cfg.get("temporary_path_preview_start_step", 0)),
            "start_s": float(method_cfg.get("temporary_path_preview_start_s", 0.0)),
            "end_step": None if method_cfg.get("temporary_path_preview_end_step", None) is None else int(method_cfg.get("temporary_path_preview_end_step")),
            "end_s": None if method_cfg.get("temporary_path_preview_end_s", None) is None else float(method_cfg.get("temporary_path_preview_end_s")),
            "index_mode": str(method_cfg.get("temporary_path_preview_index_mode", "k")),
            "s_lookup": str(method_cfg.get("temporary_path_preview_s_lookup", "nearest")),
            "use_ref_s": bool(temporary_path_preview_use_ref_s),
            "base_offset_steps": int(method_cfg.get("temporary_path_preview_base_offset_steps", 1)),
            "shift_steps": _cfg_jsonable(method_cfg.get("temporary_path_preview_shift_steps", 0)),
            "max_shift_steps": _cfg_jsonable(method_cfg.get("temporary_path_preview_max_shift_steps", None)),
            "max_candidate_shift_steps": _cfg_jsonable(method_cfg.get("temporary_path_preview_max_candidate_shift_steps", None)),
            "lookahead_m": _cfg_jsonable(method_cfg.get("temporary_path_preview_lookahead_m", 0.0)),
            "min_lookahead_m": _cfg_jsonable(method_cfg.get("temporary_path_preview_min_lookahead_m", None)),
            "max_lookahead_m": _cfg_jsonable(method_cfg.get("temporary_path_preview_max_lookahead_m", None)),
            "blend_weight": float(method_cfg.get("temporary_path_preview_blend_weight", 1.0)),
            "smooth_enabled": bool(method_cfg.get("temporary_path_preview_smooth_enabled", True)),
            "ramp_s": float(method_cfg.get("temporary_path_preview_ramp_s", 0.0)),
            "fourws_heading_enabled": bool(method_cfg.get("temporary_path_preview_fourws_heading_enabled", False)),
            "fourws_heading_blend": float(method_cfg.get("temporary_path_preview_fourws_heading_blend", 1.0)),
            "heading_scale": _cfg_jsonable(method_cfg.get("temporary_path_preview_heading_scale", None)),
            "rear_steer_ratio": float(method_cfg.get("temporary_path_preview_rear_steer_ratio", 0.0)),
            "fourws_optimizer_enabled": bool(
                method_cfg.get("temporary_path_preview_fourws_optimizer_enabled", True)
            ),
            "fourws_steering_logic": str(
                method_cfg.get(
                    "temporary_path_preview_fourws_steering_logic",
                    "anti_phase_angle_ratio",
                )
            ),
            "fourws_grid_refine_enabled": bool(
                method_cfg.get("temporary_path_preview_fourws_grid_refine_enabled", False)
            ),
            "front_delta_est_clip_rad": _cfg_jsonable(method_cfg.get("temporary_path_preview_front_delta_est_clip_rad", None)),
            "wheelbase_m": _cfg_jsonable(method_cfg.get("temporary_path_preview_wheelbase_m", None)),
            "lf_m": _cfg_jsonable(method_cfg.get("temporary_path_preview_lf_m", None)),
            "lr_m": _cfg_jsonable(method_cfg.get("temporary_path_preview_lr_m", None)),
            "summary": {
                "active_ratio_mean": temp_preview_active_ratio_mean,
                "applied_ratio_mean": temp_preview_applied_ratio_mean,
                "geometric_applied_ratio_mean": temp_preview_geometric_applied_ratio_mean,
                "lookahead_m_mean": temp_preview_lookahead_mean,
                "front_delta_est_mean": temp_preview_front_delta_mean,
                "front_delta_est_peak_abs": temp_preview_front_delta_peak_abs,
                "rear_delta_est_mean": temp_preview_rear_delta_mean,
                "rear_delta_est_peak_abs": temp_preview_rear_delta_peak_abs,
                "fourws_optimizer_enabled_ratio": temp_preview_fourws_optimizer_enabled_ratio,
                "fourws_optimizer_curvature_error_mean_abs": (
                    temp_preview_fourws_optimizer_curvature_error_mean_abs
                ),
                "fourws_optimizer_curvature_error_peak_abs": (
                    temp_preview_fourws_optimizer_curvature_error_peak_abs
                ),
                "fourws_optimizer_sideslip_peak_abs": temp_preview_fourws_optimizer_sideslip_peak_abs,
                "fourws_heading_applied_ratio_mean": temp_preview_fourws_heading_applied_ratio_mean,
                "fourws_heading_adjustment_raw_mean": temp_preview_fourws_heading_adjustment_mean,
                "fourws_heading_adjustment_raw_peak_abs": temp_preview_fourws_heading_adjustment_peak_abs,
                "fourws_curvature_cmd_mean": temp_preview_fourws_curvature_cmd_mean,
                "requested_shift_steps_mean": temp_preview_requested_shift_mean,
                "requested_shift_steps_peak_abs": temp_preview_requested_shift_peak_abs,
                "configured_shift_steps_mean": temp_preview_configured_shift_mean,
                "configured_shift_steps_peak_abs": temp_preview_configured_shift_peak_abs,
                "candidate_shift_steps_before_clamp_mean": temp_preview_candidate_shift_before_clamp_mean,
                "candidate_shift_steps_before_clamp_peak_abs": temp_preview_candidate_shift_before_clamp_peak_abs,
                "candidate_shift_clamped_steps": temp_preview_candidate_shift_clamped_steps,
                "candidate_shift_steps_mean": temp_preview_candidate_shift_mean,
                "candidate_shift_steps_peak_abs": temp_preview_candidate_shift_peak_abs,
                "applied_shift_steps_mean": temp_preview_shift_mean,
                "applied_shift_steps_peak_abs": temp_preview_shift_peak_abs,
                "shift_steps_mean": temp_preview_shift_mean,
                "shift_steps_peak_abs": temp_preview_shift_peak_abs,
                "effective_shift_steps_mean": temp_preview_effective_shift_mean,
                "effective_shift_steps_peak_abs": temp_preview_effective_shift_peak_abs,
                "blend_weight_mean": temp_preview_blend_weight_mean,
                "terminal_pad_cols_peak": temp_preview_terminal_pad_peak,
                "terminal_pad_overshoot_cols_peak": temp_preview_terminal_overshoot_peak,
            },
        },
        "fault_summary": {
            "active_steps": fault_active_steps,
            "active_ratio": float(fault_active_steps / max(1, actual_sim_steps)),
            "deficit_norm_peak": fault_deficit_peak,
            "trigger_mode": str(fault_trigger_mode),
            "start_s": float(fault_start_s),
            "start_step": int(fault_start_step),
        },
        "tf14_fdi_summary": tf14_fdi_summary,
        "tf14_switch_summary": tf14_switch_summary,
        "phase_role_summary": phase_role_summary,
        "tf14_certificate_summary": tf14_certificate_summary,
        "tf14_interaction_summary": tf14_interaction_summary,
        "fail_counts": fail_counts_case,
        "progress_guard_counts": progress_guard_counts,
        "progress_boost_count": int(progress_boost_count),
        "progress_boost_ratio": float(progress_boost_count / max(1, actual_sim_steps)),
        "solver_status_hist": solver_status_case,
        "terminated_early": terminated_early_case,
        "begin_time": begin_t,
        "end_time": end_t,
        "total_time": float(end_t - begin_t),
        "avg_step_time": float((end_t - begin_t) / max(1, actual_sim_steps)),
        "sim_steps": int(actual_sim_steps),
        "sim_steps_nominal": int(sim_steps_nominal),
        "sim_steps_cap": int(sim_steps_cap),
        "eval_snr_db": float(eval_snr_db),
        "realtime_mode": bool(realtime_mode),
        "step_budget_sec": float(step_budget_sec),
        "step_runtime_hist": step_runtime_hist,
        "step_time_mean": float(np.mean(step_runtime_hist)) if len(step_runtime_hist) > 0 else np.nan,
        "step_time_max": float(np.max(step_runtime_hist)) if len(step_runtime_hist) > 0 else np.nan,
        "step_overrun_count": int(step_overrun_count),
        "step_overrun_ratio": float(step_overrun_count / max(1, len(step_runtime_hist))),
        "mpc_decimation_steps": int(mpc_decimation_steps),
        "mpc_solve_time_hist": solve_runtime_hist,
        "mpc_solve_time_mean": float(np.mean(solve_runtime_hist)) if len(solve_runtime_hist) > 0 else np.nan,
        "mpc_solve_time_max": float(np.max(solve_runtime_hist)) if len(solve_runtime_hist) > 0 else np.nan,
        "mpc_solve_success_count": int(solve_success_count),
        "mpc_solve_skip_count": int(solve_skip_count),
        "vehicle_metrics": vehicle_metrics,
        "rmse_lat_mean": rmse_lat_mean,
        "rmse_long_mean": rmse_long_mean,
        "max_lat_global": max_lat_global,
        "max_long_global": max_long_global,
        "final_s": final_s_team,
        "target_s_team": target_s_team,
        "progress_ratio": progress_ratio,
        "traj_length": target_s_team,
        "traj_samples": int(traj_length),
        "target_s_vehicles": target_s_vehicles,
        "final_s_vehicles": final_s_vehicles,
        "full_path_flags": full_path_flags,
        "full_path_reached": bool(np.all(full_path_flags)),
        "stop_reason": str(stop_reason),
        "max_wall_time_sec": float(max_wall_time_sec),
        "max_no_progress_steps": int(max_no_progress_steps),
        "no_progress_steps_last": int(no_progress_steps),
        "best_team_s": float(best_team_s),
        "adapt_mode": adapt_mode,
        "adapt_A_norm_hist": adapt_A_norm_hist,
        "adapt_B_norm_hist": adapt_B_norm_hist,
        "koopman_structure": structure_name,
        "use_rigid_coord_correction": use_rigid_coord_correction,
    }
    if use_coupled_plant:
        result.update(
            {
                "coupled_state_hist": coupled_state_hist,
                "coupled_control_hist": coupled_control_hist,
                "coupled_alloc_diag_hist": coupled_alloc_diag_hist,
                "coupled_summary": coupled_summary,
                "coupled_adapter_config": {
                    "substep_s": float(coupled_cfg.substep_s),
                    "virtual_front_scale": float(coupled_cfg.virtual_front_scale),
                    "virtual_rear_ratio": float(coupled_cfg.virtual_rear_ratio),
                    "heading_gain": float(coupled_cfg.heading_gain),
                    "speed_gain": float(coupled_cfg.speed_gain),
                    "max_vehicle_steering_deg": float(coupled_cfg.max_vehicle_steering_deg),
                    "max_zero_sum_accel_mps2": float(coupled_cfg.max_zero_sum_accel_mps2),
                },
            }
        )
    result["metrics"] = ctx["_build_case_metrics"](result)
    result["history_save"] = _save_history_if_enabled(method_cfg, result)
    return result


def run_tf14_main(ctx, payload_module, payload_cfg, change_mask):
    """Canonical TF14 runtime entry.

    Keeps the legacy tf12-style call signature so older notebook cells can be
    migrated with minimal edits, while exposing the new TF14 identity.
    """
    return run_tf12_main(ctx, payload_module, payload_cfg, change_mask)

