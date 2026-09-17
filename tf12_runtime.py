import os
import pickle
import random
import time
import gc

import numpy as np
import scipy

from control_files.a1_progress_supervisor_v2 import A1ProgressSupervisorV2
from control_files.rigid_payload_connection_compliance_a1_v1 import (
    RigidPayloadConnectionComplianceA1V1,
)
from control_files.rigid_payload_coordinator_a1 import RigidPayloadCoordinatorA1
from control_files.rigid_payload_stability_guard_a1_v2 import RigidPayloadStabilityGuardA1V2
from control_files.tf12.comm_quality_consensus import CommAwareConsensusTF12
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
    if "dlc" in name or "double_lane" in name:
        return "dlc"

    team_ref = np.asarray(result.get("ref_team_hist", []), dtype=float)
    if team_ref.ndim == 2 and team_ref.shape[0] > 4 and team_ref.shape[1] > 1:
        yy = team_ref[:, 1]
        yy = yy[np.isfinite(yy)]
        if yy.size > 0:
            y_span = float(np.max(yy) - np.min(yy))
            if y_span > 10.0:
                return "hairpin"
            if y_span <= 6.0:
                return "dlc"
    return "unknown"


def _save_history_if_enabled(method_cfg, result):
    if save_tf12_history_record is None:
        return {"enabled": False, "reason": "history_store_unavailable"}

    enabled = bool(method_cfg.get("save_history", True))
    if not enabled:
        return {"enabled": False, "reason": "disabled_by_cfg"}

    scenario_mode = _infer_scenario_mode(method_cfg, result)
    case_name = str(method_cfg.get("history_case_name", result.get("case_name", "tf12_main")))
    root_dir = str(method_cfg.get("history_root_dir", "results/history/tf12"))
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
            print(f"[TF12][history] saved npz: {out['npz_path']}")
            print(f"[TF12][history] saved json: {out['json_path']}")
        return out
    except Exception as e:
        print(f"[TF12][history][WARN] save failed: {e}")
        return {
            "enabled": False,
            "reason": "save_failed",
            "error": str(e),
            "root_dir": root_dir,
        }


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
        "road_modes": ["dlc"],
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
    method_cfg.setdefault("name", "tf12_comm_quality_consensus_bilinear_adaptive")
    method_cfg.setdefault("koopman_structure", "bilinear")
    method_cfg.setdefault("use_online_model_adaptation", True)
    method_cfg.setdefault("online_adaptation_mode", "bilinear_ridge")
    method_cfg.setdefault("use_comm_quality_consensus", True)
    method_cfg.setdefault("use_delay_compensation", True)
    method_cfg.setdefault("use_comm_constraint_tightening", True)
    method_cfg.setdefault("use_comm_degraded_fallback", True)
    # Real-time acceleration defaults (keep all functions, prioritize timely output)
    method_cfg.setdefault("realtime_mode", True)
    method_cfg.setdefault("realtime_budget_ratio", 0.65)
    method_cfg.setdefault("realtime_control_budget_sec", None)
    method_cfg.setdefault("vehicle_order_leader_first", True)
    method_cfg.setdefault("leader_always_solve", False)
    method_cfg.setdefault("mpc_decimation_steps", 8)
    method_cfg.setdefault("min_solve_vehicles_per_step", 0)
    method_cfg.setdefault("mpc_skip_on_budget", True)
    method_cfg.setdefault("mpc_min_budget_left_sec", 4.0e-3)
    method_cfg.setdefault("fast_max_sqp_iters", 1)
    method_cfg.setdefault("fast_time_limit", 8.0e-4)
    method_cfg.setdefault("fast_time_limit_min", 3.0e-4)
    method_cfg.setdefault("realtime_adapt_stride", 12)
    method_cfg.setdefault("realtime_disable_online_adapt", True)
    method_cfg.setdefault("realtime_disable_gc", True)
    method_cfg.setdefault("realtime_horizon", 14)
    method_cfg.setdefault("save_history", True)
    method_cfg.setdefault("history_root_dir", "results/history/tf12")
    method_cfg.setdefault("history_case_name", "tf12_main")
    method_cfg.setdefault("history_print_path", True)
    # TF13-ready (default OFF in TF12): fault-tolerant cooperative transport
    method_cfg.setdefault("enable_fault_tolerant_control", False)
    method_cfg.setdefault("fault_vehicle_index", 0)
    method_cfg.setdefault("fault_mode", "ax_limit")   # ax_limit | delta_limit | both
    method_cfg.setdefault("fault_start_step", 0)
    method_cfg.setdefault("fault_start_s", 0.0)
    method_cfg.setdefault("fault_ax_scale", 0.55)
    method_cfg.setdefault("fault_delta_scale", 0.60)
    method_cfg.setdefault("fault_ax_abs_limit", None)
    method_cfg.setdefault("fault_delta_abs_limit", None)
    method_cfg.setdefault("fault_tolerant_redistribution", True)
    method_cfg.setdefault("fault_comp_gain", 0.85)
    method_cfg.setdefault("fault_comp_delta_clip", 0.040)
    method_cfg.setdefault("fault_comp_ax_clip", 0.45)

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
    if bool(method_cfg.get("print_runtime_flags", True)):
        print(
            "[TF12] runtime_flags: "
            f"team_guard={use_team_stability_guard}, "
            f"progress_supervisor={use_progress_supervisor}, "
            f"connection_compliance={use_connection_compliance}, "
            f"comm_quality_consensus={use_comm_quality_consensus}, "
            f"delay_comp={use_delay_compensation}, "
            f"tightening={use_comm_constraint_tightening}, "
            f"degraded_fb={use_comm_degraded_fallback}, "
            f"fault_tolerant={enable_fault_tolerant_control}, "
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
    fault_diag_hist = []

    connection_model = RigidPayloadConnectionComplianceA1V1(
        dt=ctx["dt"],
        num_vehicles=num_vehicles,
        enabled=use_connection_compliance,
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

        ctrl_v = ctx["NonlinearMPCController"](
            dynamics_obj,
            n_case,
            ctx["dt"],
            ctx["umin_lin_noadapt"],
            ctx["umax_lin_noadapt"],
            ctx["xmin_lin_noadapt"],
            ctx["xmax_lin_noadapt"],
            ctx["Q_base_lin"],
            ctx["R_mpc_lin_noadapt"],
            ctx["QN_base_lin"],
            solver_settings_case,
            add_ppc_soft=use_ppc,
            q_slack_ey=4e4,
            q_slack_epsi=3e4,
            p_slack_ey=4e3,
            p_slack_epsi=3e3,
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

    delta_alpha = ctx["MPC_CFG"]["delta_alpha"]
    ax_alpha = ctx["MPC_CFG"]["ax_alpha"]
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

    try:
        for k in range(sim_steps_cap):
            step_t0 = time.perf_counter()
            solved_this_step = 0
            local_states_k = connection_model.corner_states_from_team(
                team_state_hist[k, :], payload_module, payload_cfg
            )
            for v in range(num_vehicles):
                xt_case[v][k, :] = ctx["clip_closed_loop_state"](
                    local_states_k[v], s_upper=team_actual_pars["s_upper"]
                )
                z_case[v][k, :] = lift_fn(xt_case[v][k, :])

            comm_consensus.push_states(k, np.vstack([xt_case[v][k, :] for v in range(num_vehicles)]))
            prev_spread = control_spread_hist[-1] if len(control_spread_hist) > 0 else None
            if use_comm_quality_consensus:
                comm_step_diag = comm_consensus.update_channel(
                    k,
                    team_state=team_state_hist[k, :],
                    control_spread=prev_spread,
                )
            else:
                comm_step_diag = {
                    "quality_global": 1.0,
                    "mean_delay_steps": 0.0,
                    "loss_ratio": 0.0,
                }

            leader_state_k = xt_case[leader_idx][k, :].copy()
            desired_u_stack = np.zeros((num_vehicles, num_inputs), dtype=float)

            if bool(method_cfg.get("vehicle_order_leader_first", True)):
                vehicle_order = [leader_idx] + [vv for vv in range(num_vehicles) if vv != leader_idx]
            else:
                vehicle_order = list(range(num_vehicles))

            for local_idx, v in enumerate(vehicle_order):
                xk_raw = xt_case[v][k, :].copy()

                if use_adaptive_weight:
                    q_adapt, qn_adapt, r_adapt, mem_new = ctx["adaptive_mpc_weights"](
                        xk_raw[1],
                        xk_raw[2],
                        ctx["Q_base_lin"],
                        ctx["QN_base_lin"],
                        ctx["R_mpc_lin_noadapt"],
                        prev_mem=weight_memory[v],
                    )
                    weight_memory[v] = mem_new
                else:
                    q_adapt, qn_adapt, r_adapt = (
                        ctx["Q_base_lin"],
                        ctx["QN_base_lin"],
                        ctx["R_mpc_lin_noadapt"],
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

                xref_win = x_ref_case_vehicles[v][:, k + 1:k + n_case + 2]
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
                            print(f"[WARN][TF12] vehicle {v + 1} MPC fallback at step {k}: {e}")
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
                    abs(xk_raw[1]) < float(ctx["MPC_CFG"].get("coop_disable_ey", 0.9))
                    and abs(xk_raw[2]) < float(ctx["MPC_CFG"].get("coop_disable_epsi", 0.35))
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
                    delta_fb_mpc, ax_cmd = ctx["apply_coop_correction"](
                        delta_fb_mpc,
                        ax_cmd,
                        xk_raw,
                        leader_state_for_v,
                        rigid_target,
                    )

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
                        bias_gate = min(abs(float(xk_raw[1])) / bias_comp_gate_ey, 1.0)
                        bias_delta = float(-bias_comp_gain * bias_gate * float(xk_raw[2]))
                        if bias_comp_delta_clip > 0.0:
                            bias_delta = float(
                                np.clip(bias_delta, -bias_comp_delta_clip, bias_comp_delta_clip)
                            )
                        delta_cmd += bias_delta
                lag_s_v = float(ref_step_v[0] - xk_raw[0])
                lag_v_v = float(ref_step_v[3] - xk_raw[3])
                local_stable = (
                    abs(xk_raw[1]) < float(method_cfg.get("local_stable_ey_th", 0.52))
                    and abs(xk_raw[2]) < float(method_cfg.get("local_stable_epsi_th", 0.24))
                    and abs(xk_raw[5]) < float(method_cfg.get("local_stable_r_th", 0.95))
                )
                delta_cmd, ax_cmd, emergency_active = ctx["apply_emergency_guard"](xk_raw, delta_cmd, ax_cmd)
                if emergency_active:
                    emg_severity = max(
                        abs(xk_raw[1]) / max(float(method_cfg.get("emergency_soft_ey_norm", 1.0)), 1e-6),
                        abs(xk_raw[2]) / max(float(method_cfg.get("emergency_soft_epsi_norm", 0.40)), 1e-6),
                        abs(xk_raw[5]) / max(float(method_cfg.get("emergency_soft_r_norm", 1.0)), 1e-6),
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
                        - 0.06 * abs(xk_raw[5])
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
                    delta_applied = delta_alpha * u_case[v][k - 1, 0] + (1.0 - delta_alpha) * delta_cmd
                    ax_applied = ax_alpha * u_case[v][k - 1, 1] + (1.0 - ax_alpha) * ax_cmd

                delta_applied = np.clip(delta_applied, ctx["umin_lin_noadapt"][0], ctx["umax_lin_noadapt"][0])
                ax_applied = np.clip(ax_applied, ctx["umin_lin_noadapt"][1], ctx["umax_lin_noadapt"][1])
                desired_u_stack[v, 0] = delta_applied
                desired_u_stack[v, 1] = ax_applied
                u_case[v][k, :] = desired_u_stack[v]

            fault_diag_step = {
                "step": int(k),
                "active": False,
                "vehicle_index": int(fault_vehicle_index),
                "mode": str(fault_mode),
                "deficit_delta": 0.0,
                "deficit_ax": 0.0,
                "deficit_norm": 0.0,
            }
            if (
                enable_fault_tolerant_control
                and (0 <= fault_vehicle_index < num_vehicles)
                and (k >= fault_start_step)
                and (team_state_hist[k, 0] >= fault_start_s)
            ):
                v_fault = int(fault_vehicle_index)
                u_nom_fault = desired_u_stack[v_fault, :].copy()
                u_fault = u_nom_fault.copy()

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

                deficit = u_nom_fault - u_fault
                desired_u_stack[v_fault, :] = u_fault

                if fault_tolerant_redistribution and num_vehicles > 1:
                    supporters = [vv for vv in range(num_vehicles) if vv != v_fault]
                    if len(supporters) > 0:
                        comp = (fault_comp_gain * deficit) / float(len(supporters))
                        comp[0] = np.clip(comp[0], -fault_comp_delta_clip, fault_comp_delta_clip)
                        comp[1] = np.clip(comp[1], -fault_comp_ax_clip, fault_comp_ax_clip)
                        for vv in supporters:
                            desired_u_stack[vv, 0] += comp[0]
                            desired_u_stack[vv, 1] += comp[1]

                desired_u_stack[:, 0] = np.clip(
                    desired_u_stack[:, 0], ctx["umin_lin_noadapt"][0], ctx["umax_lin_noadapt"][0]
                )
                desired_u_stack[:, 1] = np.clip(
                    desired_u_stack[:, 1], ctx["umin_lin_noadapt"][1], ctx["umax_lin_noadapt"][1]
                )
                fault_diag_step = {
                    "step": int(k),
                    "active": True,
                    "vehicle_index": int(v_fault),
                    "mode": str(fault_mode),
                    "u_nom_fault": u_nom_fault.tolist(),
                    "u_fault": u_fault.tolist(),
                    "deficit_delta": float(deficit[0]),
                    "deficit_ax": float(deficit[1]),
                    "deficit_norm": float(np.linalg.norm(deficit)),
                    "redistribution_enabled": bool(fault_tolerant_redistribution),
                }
                if k % max(1, int(method_cfg.get("log_interval", 100))) == 0:
                    print(
                        f"[TF12][fault] step={k} v={v_fault + 1} mode={fault_mode} "
                        f"def=({deficit[0]:+.3f},{deficit[1]:+.3f})"
                    )
            fault_diag_hist.append(fault_diag_step)

            prev_team_u = team_input_hist[k - 1, :] if k > 0 else None
            if use_comm_quality_consensus:
                desired_u_for_agg, comm_proj_diag = comm_consensus.project_vehicle_commands(
                    desired_u_stack,
                    prev_team_u=prev_team_u,
                )
            else:
                desired_u_for_agg = desired_u_stack.copy()
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
            for v in range(num_vehicles):
                u_case[v][k, :] = desired_u_for_agg[v, :]

            u_team, spread_info = coordinator.aggregate_controls(
                desired_u_for_agg, prev_team_u=prev_team_u
            )
            team_ref_step = ref_bundle["team_ref_hist"][min(k, ref_bundle["team_ref_hist"].shape[0] - 1), :]
            if use_team_stability_guard:
                u_guard, guard_diag = stability_guard.build_team_guard(
                    team_state_hist[k, :], team_ref_step
                )
                u_team, guard_blend_diag = stability_guard.blend_controls(
                    u_team, u_guard, spread_info
                )
            else:
                guard_diag = {"w_guard": 0.0, "severity": 0.0, "beta": 0.0}
                guard_blend_diag = {"w_blend": 0.0, "w_spread": 0.0}

            if use_legacy_hard_brake and (
                abs(team_state_hist[k, 1]) > 0.90 or abs(team_state_hist[k, 2]) > 0.32
            ):
                u_team[1] = min(float(u_team[1]), -0.08 - 0.18 * abs(team_state_hist[k, 2]))

            if use_progress_supervisor:
                u_team, progress_diag = progress_supervisor.apply(
                    team_state=team_state_hist[k, :],
                    team_ref=team_ref_step,
                    u_team=u_team,
                    umin=ctx["umin_lin_noadapt"],
                    umax=ctx["umax_lin_noadapt"],
                    guard_diag=guard_diag,
                    blend_diag=guard_blend_diag,
                )
                if progress_diag.get("boost_active", False):
                    progress_boost_count += 1
            else:
                progress_diag = {
                    "boost_active": False,
                    "lag_s": float(max(team_ref_step[0] - team_state_hist[k, 0], 0.0)),
                    "lag_v": float(team_ref_step[3] - team_state_hist[k, 3]),
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
                    team_state_hist[k, :],
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

            u_team[0] = np.clip(u_team[0], umin_eff[0], umax_eff[0])
            u_team[1] = np.clip(u_team[1], umin_eff[1], umax_eff[1])
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
            spread_info["fault_active"] = bool(fault_diag_step.get("active", False))
            spread_info["fault_deficit_norm"] = float(fault_diag_step.get("deficit_norm", 0.0))
            team_input_hist[k, :] = u_team
            control_spread_hist.append(spread_info)
            connection_diag_hist.append(dict(conn_diag))
            comm_diag_hist.append({
                "step": int(k),
                "quality_global": float(comm_step_diag.get("quality_global", 1.0)),
                "mean_delay_steps": float(comm_step_diag.get("mean_delay_steps", 0.0)),
                "loss_ratio": float(comm_step_diag.get("loss_ratio", 0.0)),
                "consensus_blend_mean": float(comm_proj_diag.get("blend_mean", 0.0)),
                "tighten_frac": float(comm_tight_diag.get("tighten_frac", 0.0)),
                "degrade_mix": float(comm_fb_diag.get("degrade_mix", 0.0)),
                "quality_in_mean": float(comm_proj_diag.get("quality_in_mean", 1.0)),
            })

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
                        f"[TF12][WARN] wall-time limit reached: elapsed={elapsed_wall:.2f}s >= "
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
                    f"[TF12][WARN] no-progress watchdog triggered: "
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
                    f"[TF12] step {k}/{sim_steps_cap} | fail_counts={fail_counts_case} | "
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
    if len(comm_diag_hist) > 0:
        comm_quality_mean = float(np.mean([d.get("quality_global", 1.0) for d in comm_diag_hist]))
        comm_quality_min = float(np.min([d.get("quality_global", 1.0) for d in comm_diag_hist]))
        comm_delay_mean = float(np.mean([d.get("mean_delay_steps", 0.0) for d in comm_diag_hist]))
        comm_loss_mean = float(np.mean([d.get("loss_ratio", 0.0) for d in comm_diag_hist]))
        comm_tighten_mean = float(np.mean([d.get("tighten_frac", 0.0) for d in comm_diag_hist]))
        comm_degrade_peak = float(np.max([d.get("degrade_mix", 0.0) for d in comm_diag_hist]))
    else:
        comm_quality_mean = comm_quality_min = 1.0
        comm_delay_mean = comm_loss_mean = 0.0
        comm_tighten_mean = comm_degrade_peak = 0.0
    fault_active_steps = int(np.sum([1 for d in fault_diag_hist if d.get("active", False)]))
    fault_deficit_peak = float(
        np.max([d.get("deficit_norm", 0.0) for d in fault_diag_hist]) if len(fault_diag_hist) > 0 else 0.0
    )

    result = {
        "case": method_cfg,
        "case_name": "tf12_main",
        "modules": dict(ctx.get("TF12_MODULES_MAIN", ctx.get("TF11_MODULES_MAIN", {}))),
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
        "payload_force_summary": payload_module.summarize_force_history(payload_force_hist),
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
        "fault_diag_hist": fault_diag_hist,
        "connection_compliance_enabled": bool(use_connection_compliance),
        "comm_quality_consensus_enabled": bool(use_comm_quality_consensus),
        "comm_delay_compensation_enabled": bool(use_delay_compensation),
        "comm_constraint_tightening_enabled": bool(use_comm_constraint_tightening),
        "comm_degraded_fallback_enabled": bool(use_comm_degraded_fallback),
        "fault_tolerant_enabled": bool(enable_fault_tolerant_control),
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
        },
        "fault_summary": {
            "active_steps": fault_active_steps,
            "active_ratio": float(fault_active_steps / max(1, actual_sim_steps)),
            "deficit_norm_peak": fault_deficit_peak,
        },
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
    result["metrics"] = ctx["_build_case_metrics"](result)
    result["history_save"] = _save_history_if_enabled(method_cfg, result)
    return result
