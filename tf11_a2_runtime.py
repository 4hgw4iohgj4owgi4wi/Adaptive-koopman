import copy
import os
import pickle

import numpy as np

from control_files.a2_supervisory_controller import A2SupervisoryController
from control_files.nmpc_osqp_ppc import NonlinearMPCController
from control_files.rigid_payload_coordinator_a2 import RigidPayloadCoordinatorA2
from control_files.tube_mpc_helper_a2 import TubeMpcHelperA2
from dynamics.cacalv3_payload_a2 import RigidPayloadDatasetBuilderA2
from dynamics.cacalv3_payload_a2 import build_payload_config
from dynamics.cacalv3_payload_a2 import build_team_parameter_scenarios
from dynamics.cacalv3_payload_a2 import compute_payload_force_metrics
from dynamics.cacalv3_payload_a2 import retune_team_parameters_a2
from dynamics.cacalv3_payload_a2 import summarize_force_history
from dynamics.cacalv3_payload_a2 import team_to_corner_states
from dynamics.learned_models_control.hybrid_rigid_payload_dynamics_a2 import HybridRigidPayloadDynamicsA2


def _compute_path_geometry(x_ref, y_ref):
    x_ref = np.asarray(x_ref, dtype=float).reshape(-1)
    y_ref = np.asarray(y_ref, dtype=float).reshape(-1)
    ds_seg = np.sqrt(np.diff(x_ref) ** 2 + np.diff(y_ref) ** 2)
    s_ref = np.concatenate(([0.0], np.cumsum(ds_seg)))
    dx = np.gradient(x_ref)
    dy = np.gradient(y_ref)
    ddx = np.gradient(dx)
    ddy = np.gradient(dy)
    psi_ref = np.unwrap(np.arctan2(dy, dx))
    den = np.maximum((dx ** 2 + dy ** 2) ** 1.5, 1e-8)
    curvature_ref = (dx * ddy - dy * ddx) / den
    curvature_ref = np.nan_to_num(curvature_ref, nan=0.0, posinf=0.0, neginf=0.0)
    return s_ref, psi_ref, curvature_ref


def build_double_lane_change_reference_a2(
    *,
    path_length=60.0,
    num_points=1201,
    amp_1=1.10,
    amp_2=-1.20,
    x1=18.0,
    x2=43.0,
    sigma_1=7.2,
    sigma_2=6.5,
):
    x_ref = np.linspace(0.0, float(path_length), int(num_points))
    y_ref = (
        float(amp_1) * np.exp(-0.5 * ((x_ref - float(x1)) / float(sigma_1)) ** 2)
        + float(amp_2) * np.exp(-0.5 * ((x_ref - float(x2)) / float(sigma_2)) ** 2)
    )
    s_ref, psi_ref, curvature_ref = _compute_path_geometry(x_ref, y_ref)
    return {
        "x_ref": x_ref,
        "y_ref": y_ref,
        "s_ref": s_ref,
        "psi_ref": psi_ref,
        "curvature_ref": curvature_ref,
    }


def frenet_to_global_a2(s_arr, ey_arr, path_data):
    s_ref = np.asarray(path_data["s_ref"], dtype=float)
    x_ref = np.asarray(path_data["x_ref"], dtype=float)
    y_ref = np.asarray(path_data["y_ref"], dtype=float)
    psi_ref = np.asarray(path_data["psi_ref"], dtype=float)
    s_arr = np.asarray(s_arr, dtype=float).reshape(-1)
    ey_arr = np.asarray(ey_arr, dtype=float).reshape(-1)
    s_clip = np.clip(s_arr, s_ref[0], s_ref[-1])
    x_center = np.interp(s_clip, s_ref, x_ref)
    y_center = np.interp(s_clip, s_ref, y_ref)
    psi_center = np.interp(s_clip, s_ref, psi_ref)
    x_global = x_center - ey_arr * np.sin(psi_center)
    y_global = y_center + ey_arr * np.cos(psi_center)
    return x_global, y_global


def default_a2_config():
    payload_cfg = build_payload_config(
        payload_mass=2000.0,
        payload_length=5.0,
        payload_width=2.0,
        com_height=1.2,
        gravity=9.81,
    )
    return {
        "seed": 7,
        "dt": 0.05,
        "vx_ref": 1.6,
        "path_length": 60.0,
        "num_path_points": 1201,
        "payload_cfg": payload_cfg,
        "dataset": {
            "num_traj": 56,
            "num_snaps": 320,
            "sensor_noise": False,
            "SNR_DB": 30,
            "subset_weights": {1: 0.35, 2: 0.30, 3: 0.20, 4: 0.15},
            "save_tag": "tf11_a2_hybrid",
        },
        "system_nominal": {
            "num_states": 6,
            "num_inputs": 2,
            "m": 1500.0,
            "Iz": 2250.0,
            "lf": 1.2,
            "lr": 1.6,
            "Cf": 80000.0,
            "Cr": 80000.0,
            "uncertainty": "NA",
            "amp": 0.0,
            "road_modes": ["dlc"],
            "road_mode_probs": [1.0],
            "u_modes": ["feedback_dominant", "sinusoidal", "mixed"],
            "u_mode_probs": [0.40, 0.30, 0.30],
            "alpha_u": 0.72,
            "s_margin": 20.0,
            "delta_max": 0.16,
            "ax_max": 1.20,
        },
        "system_changed": {
            "m": 1700.0,
            "Iz": 2450.0,
            "Cf": 67000.0,
            "Cr": 66000.0,
        },
        "fit": {
            "ridge": 8e-4,
            "train_ratio": 0.80,
            "quantile": 0.985,
            "margin": 0.015,
            "blend": 0.95,
        },
        "koopman": {
            "enable": True,
            "ridge": 1.2e-3,
            "clip": np.array([1.8, 0.55, 0.20, 1.6, 0.80, 0.55], dtype=float),
            "blend_in_dynamics": 0.18,
        },
        "online_adapt": {
            "enable": True,
            "warmup_steps": 120,
            "window": 60,
            "update_every": 15,
            "ridge": 2.0e-3,
            "blend": 0.05,
            "max_delta_norm": 0.35,
            "max_delta_abs": 0.08,
            "accept_rmse_ratio": 1.03,
        },
        "mpc": {
            "horizon": 18,
            "max_sqp_iters": 2,
            "umin": np.array([-0.18, -1.10], dtype=float),
            "umax": np.array([0.18, 0.90], dtype=float),
            "xmin": np.array([0.0, -2.60, -0.70, 0.55, -3.20, -1.80], dtype=float),
            "xmax": np.array([85.0, 2.60, 0.70, 6.20, 3.20, 1.80], dtype=float),
            "Q": np.diag([0.02, 55.0, 82.0, 1.6, 7.0, 9.0]),
            "QN": np.diag([0.04, 90.0, 120.0, 2.0, 9.0, 12.0]),
            "R": np.diag([4.5, 0.70]),
            "solver_settings": {
                "verbose": False,
                "warm_start": True,
                "polish": False,
                "eps_abs": 2e-3,
                "eps_rel": 2e-3,
                "max_iter": 4500,
                "adaptive_rho": True,
            },
            "input_smooth_alpha": np.array([0.45, 0.55], dtype=float),
            "completion_tol_s": 0.60,
            "extra_steps": 90,
            "ff_gain": 0.85,
        },
        "supervisor": {
            "max_hold_steps": 3,
            "discrepancy_threshold": 0.15,
            "prescribed_time": 6.0,
            "rho_ey_0": 0.80,
            "rho_ey_inf": 0.06,
            "rho_epsi_0": 0.35,
            "rho_epsi_inf": 0.04,
            "beta_limit": 0.20,
            "r_limit": 0.55,
            "stage2_beta": 0.28,
            "stage2_r": 0.75,
        },
    }


def _team_state_clip(x, s_upper):
    x = np.asarray(x, dtype=float).copy()
    x[0] = np.clip(x[0], 0.0, float(s_upper))
    x[1] = np.clip(x[1], -2.4, 2.4)
    x[2] = np.clip(x[2], -0.65, 0.65)
    x[3] = np.clip(x[3], 0.5, 7.5)
    x[4] = np.clip(x[4], -2.5, 2.5)
    x[5] = np.clip(x[5], -1.6, 1.6)
    return x


def _solve_ridge(reg, target, ridge):
    reg = np.asarray(reg, dtype=float)
    target = np.asarray(target, dtype=float)
    lhs = reg.T @ reg + float(ridge) * np.eye(reg.shape[1], dtype=float)
    rhs = reg.T @ target
    theta = np.linalg.solve(lhs, rhs)
    return theta.T


def fit_koopman_model_a2(dataset, cfg):
    x_changed = np.asarray(dataset["X_changed"], dtype=float)
    u_data = np.asarray(dataset["U"], dtype=float)
    n_traj = int(x_changed.shape[0])
    n_train = max(1, int(float(cfg["fit"]["train_ratio"]) * n_traj))

    feat_rows = []
    u_rows = []
    y_rows = []
    for i in range(n_train):
        x_traj = x_changed[i]
        u_traj = u_data[i]
        for k in range(u_traj.shape[0]):
            xk = x_traj[k, :]
            uk = u_traj[k, :]
            feat_rows.append(HybridRigidPayloadDynamicsA2.lift_state(xk))
            u_rows.append(uk)
            y_rows.append(x_traj[k + 1, :] - xk)

    feat = np.asarray(feat_rows, dtype=float)
    u_mat = np.asarray(u_rows, dtype=float)
    y = np.asarray(y_rows, dtype=float)

    feat_mu = np.mean(feat, axis=0)
    feat_scale = np.std(feat, axis=0) + 1e-6
    u_mu = np.mean(u_mat, axis=0)
    u_scale = np.std(u_mat, axis=0) + 1e-6

    feat_n = (feat - feat_mu) / feat_scale
    u_n = (u_mat - u_mu) / u_scale
    reg = np.concatenate((feat_n, u_n, np.ones((feat_n.shape[0], 1), dtype=float)), axis=1)

    k_mat = _solve_ridge(reg, y, cfg["koopman"]["ridge"])

    def predict_split(i_start, i_end):
        pred = []
        ref = []
        for i in range(i_start, i_end):
            x_traj = x_changed[i]
            u_traj = u_data[i]
            for k in range(u_traj.shape[0]):
                xk = x_traj[k, :]
                uk = u_traj[k, :]
                feat_k = HybridRigidPayloadDynamicsA2.lift_state(xk)
                feat_kn = (feat_k - feat_mu) / feat_scale
                uk_n = (uk - u_mu) / u_scale
                reg_k = np.concatenate((feat_kn, uk_n, np.array([1.0], dtype=float)))
                pred.append(k_mat @ reg_k)
                ref.append(x_traj[k + 1, :] - xk)
        if len(pred) == 0:
            return np.zeros((0, y.shape[1]), dtype=float), np.zeros((0, y.shape[1]), dtype=float)
        return np.asarray(pred, dtype=float), np.asarray(ref, dtype=float)

    pred_train, ref_train = predict_split(0, n_train)
    pred_val, ref_val = predict_split(n_train, n_traj)
    if pred_val.size == 0:
        pred_val, ref_val = pred_train.copy(), ref_train.copy()

    train_rmse = float(np.sqrt(np.mean((pred_train - ref_train) ** 2))) if pred_train.size else np.inf
    val_rmse = float(np.sqrt(np.mean((pred_val - ref_val) ** 2))) if pred_val.size else np.inf
    y_scale = np.std(y, axis=0) + 1e-6
    train_nrmse = (
        float(np.sqrt(np.mean(((pred_train - ref_train) / y_scale.reshape(1, -1)) ** 2)))
        if pred_train.size
        else np.inf
    )
    val_nrmse = (
        float(np.sqrt(np.mean(((pred_val - ref_val) / y_scale.reshape(1, -1)) ** 2)))
        if pred_val.size
        else np.inf
    )
    clip_bound = np.asarray(cfg["koopman"]["clip"], dtype=float).reshape(-1)

    return {
        "K": k_mat,
        "feat_mu": feat_mu,
        "feat_scale": feat_scale,
        "u_mu": u_mu,
        "u_scale": u_scale,
        "clip_bound": clip_bound,
        "train_rmse": train_rmse,
        "val_rmse": val_rmse,
        "train_nrmse": train_nrmse,
        "val_nrmse": val_nrmse,
    }


def _update_koopman_model_online(koopman_model, reg_mat, y_mat, adapt_cfg):
    k_current = np.asarray(koopman_model["K"], dtype=float)
    pred_current = reg_mat @ k_current.T
    rmse_current = float(np.sqrt(np.mean((pred_current - y_mat) ** 2)))
    k_fit = _solve_ridge(reg_mat, y_mat, adapt_cfg["ridge"])
    delta = k_fit - k_current

    max_delta_norm = float(adapt_cfg["max_delta_norm"])
    delta_norm = float(np.linalg.norm(delta))
    if delta_norm > max_delta_norm and delta_norm > 1e-8:
        delta *= max_delta_norm / delta_norm

    max_delta_abs = float(adapt_cfg["max_delta_abs"])
    delta = np.clip(delta, -max_delta_abs, max_delta_abs)

    blend = float(np.clip(adapt_cfg["blend"], 0.0, 1.0))
    k_new = k_current + blend * delta
    pred_new = reg_mat @ k_new.T
    rmse_new = float(np.sqrt(np.mean((pred_new - y_mat) ** 2)))

    model_new = copy.deepcopy(koopman_model)
    model_new["K"] = k_new
    return model_new, delta_norm, rmse_current, rmse_new


def generate_a2_dataset(payload_module, cfg, *, save=True):
    seed = int(cfg["seed"])
    np.random.seed(seed)
    pars_nominal = dict(cfg["system_nominal"])
    pars_nominal.update(
        {
            "num_states": 6,
            "num_inputs": 2,
            "dt": float(cfg["dt"]),
            "vx_ref": float(cfg["vx_ref"]),
            "seed": seed,
            "payload_cfg": dict(cfg["payload_cfg"]),
            "variation_subset_weights": dict(cfg["dataset"]["subset_weights"]),
        }
    )
    pars_changed = dict(pars_nominal)
    pars_changed.update(cfg["system_changed"])

    builder = RigidPayloadDatasetBuilderA2(
        pars_nominal=pars_nominal,
        pars_changed=pars_changed,
        payload_cfg=cfg["payload_cfg"],
    )
    dataset = builder.generate_team_dataset(
        num_traj=int(cfg["dataset"]["num_traj"]),
        num_snaps=int(cfg["dataset"]["num_snaps"]),
        sensor_noise=bool(cfg["dataset"]["sensor_noise"]),
        SNR_DB=float(cfg["dataset"]["SNR_DB"]),
    )
    dataset["pars_nominal"] = pars_nominal
    dataset["pars_changed"] = pars_changed

    if save:
        os.makedirs("saved_data/payload_team", exist_ok=True)
        save_tag = str(cfg["dataset"]["save_tag"])
        np.savez_compressed(
            f"saved_data/payload_team/offline_dataset_{save_tag}.npz",
            X_nominal=dataset["X_nominal"],
            X_changed=dataset["X_changed"],
            U=dataset["U"],
        )
        with open(f"saved_data/payload_team/offline_dataset_{save_tag}.pkl", "wb") as f:
            pickle.dump(
                {
                    "cfg": cfg,
                    "variation_summary": dataset["variation_summary"],
                },
                f,
            )
    return dataset


def fit_hybrid_residual_model_a2(payload_module, dataset, cfg):
    x_changed = np.asarray(dataset["X_changed"], dtype=float)
    u_data = np.asarray(dataset["U"], dtype=float)
    traj_meta = list(dataset["traj_meta"])
    n_traj = int(x_changed.shape[0])
    n_train = max(1, int(float(cfg["fit"]["train_ratio"]) * n_traj))

    feat_rows = []
    u_rows = []
    y_rows = []
    for i in range(n_train):
        x_traj = x_changed[i]
        u_traj = u_data[i]
        nominal_pars = copy.deepcopy(traj_meta[i]["nominal_pars"])
        for k in range(u_traj.shape[0]):
            xk = x_traj[k, :]
            uk = u_traj[k, :]
            x_nom_next = payload_module.FK_solver(xk, uk, nominal_pars, sensor_noise=False, SNR_DB=0, i=k)
            feat_rows.append(HybridRigidPayloadDynamicsA2.lift_state(xk))
            u_rows.append(uk)
            y_rows.append(x_traj[k + 1, :] - np.asarray(x_nom_next, dtype=float))

    feat = np.asarray(feat_rows, dtype=float)
    u_mat = np.asarray(u_rows, dtype=float)
    y = np.asarray(y_rows, dtype=float)

    feat_mu = np.mean(feat, axis=0)
    feat_scale = np.std(feat, axis=0) + 1e-6
    u_mu = np.mean(u_mat, axis=0)
    u_scale = np.std(u_mat, axis=0) + 1e-6

    feat_n = (feat - feat_mu) / feat_scale
    u_n = (u_mat - u_mu) / u_scale
    reg = np.concatenate((feat_n, u_n, np.ones((feat_n.shape[0], 1), dtype=float)), axis=1)

    ridge = float(cfg["fit"]["ridge"])
    lhs = reg.T @ reg + ridge * np.eye(reg.shape[1], dtype=float)
    rhs = reg.T @ y
    theta = np.linalg.solve(lhs, rhs)
    w = theta.T

    def predict_for_split(i_start, i_end):
        preds = []
        refs = []
        for i in range(i_start, i_end):
            x_traj = x_changed[i]
            u_traj = u_data[i]
            nominal_pars = copy.deepcopy(traj_meta[i]["nominal_pars"])
            for k in range(u_traj.shape[0]):
                xk = x_traj[k, :]
                uk = u_traj[k, :]
                x_nom_next = payload_module.FK_solver(xk, uk, nominal_pars, sensor_noise=False, SNR_DB=0, i=k)
                feat_k = HybridRigidPayloadDynamicsA2.lift_state(xk)
                feat_kn = (feat_k - feat_mu) / feat_scale
                uk_n = (uk - u_mu) / u_scale
                reg_k = np.concatenate((feat_kn, uk_n, np.array([1.0], dtype=float)))
                dx_pred = w @ reg_k
                preds.append(dx_pred)
                refs.append(x_traj[k + 1, :] - np.asarray(x_nom_next, dtype=float))
        preds = np.asarray(preds, dtype=float)
        refs = np.asarray(refs, dtype=float)
        return preds, refs

    pred_train, ref_train = predict_for_split(0, n_train)
    pred_val, ref_val = predict_for_split(n_train, n_traj)
    if pred_val.size == 0:
        pred_val, ref_val = pred_train.copy(), ref_train.copy()

    train_err = pred_train - ref_train
    val_err = pred_val - ref_val

    tube_helper = TubeMpcHelperA2.from_prediction_errors(
        val_err,
        quantile=float(cfg["fit"]["quantile"]),
        margin=float(cfg["fit"]["margin"]),
    )
    disturbance_cap = np.array([0.60, 0.25, 0.08, 0.25, 0.35, 0.15], dtype=float)
    tube_helper.disturbance_bound = np.minimum(tube_helper.disturbance_bound, disturbance_cap)
    koopman_model = None
    if bool(cfg.get("koopman", {}).get("enable", False)):
        koopman_model = fit_koopman_model_a2(dataset, cfg)

    model = {
        "W": w,
        "feat_mu": feat_mu,
        "feat_scale": feat_scale,
        "u_mu": u_mu,
        "u_scale": u_scale,
        "blend": float(cfg["fit"]["blend"]),
        "disturbance_bound": tube_helper.disturbance_bound.copy(),
        "clip_bound": np.maximum(0.05, 2.2 * tube_helper.disturbance_bound),
        "train_rmse": float(np.sqrt(np.mean(train_err ** 2))),
        "val_rmse": float(np.sqrt(np.mean(val_err ** 2))),
        "train_err": train_err,
        "val_err": val_err,
        "tube_helper": tube_helper,
        "koopman_model": koopman_model,
    }
    return model


def run_tf11_a2_main(payload_module, cfg, model, *, path_data=None, change_mask=(0, 1, 2, 3), verbose=True):
    np.random.seed(int(cfg["seed"]))
    if path_data is None:
        path_data = build_double_lane_change_reference_a2(
            path_length=float(cfg["path_length"]),
            num_points=int(cfg["num_path_points"]),
        )

    s_ref = np.asarray(path_data["s_ref"], dtype=float)
    curvature_ref = np.asarray(path_data["curvature_ref"], dtype=float)
    psi_ref = np.asarray(path_data["psi_ref"], dtype=float)
    traj_length = int(s_ref.size)
    sim_steps_nominal = traj_length - 1
    sim_steps_cap = sim_steps_nominal + int(cfg["mpc"]["extra_steps"])
    horizon = int(cfg["mpc"]["horizon"])

    team_ref_hist = np.column_stack(
        (
            s_ref,
            np.zeros_like(s_ref),
            np.zeros_like(psi_ref),
            np.full_like(s_ref, float(cfg["vx_ref"])),
            np.zeros_like(s_ref),
            np.zeros_like(s_ref),
        )
    )

    pars_nominal = dict(cfg["system_nominal"])
    pars_nominal.update(
        {
            "num_states": 6,
            "num_inputs": 2,
            "dt": float(cfg["dt"]),
            "vx_ref": float(cfg["vx_ref"]),
            "seed": int(cfg["seed"]),
            "payload_cfg": dict(cfg["payload_cfg"]),
            "s_ref": s_ref,
            "curvature_ref": curvature_ref,
            "s_upper": float(s_ref[-1] + cfg["system_nominal"].get("s_margin", 20.0)),
        }
    )
    pars_changed = dict(pars_nominal)
    pars_changed.update(cfg["system_changed"])

    rng = np.random.default_rng(int(cfg["seed"]))
    team_nominal_pars, team_actual_pars, payload_change_mask = build_team_parameter_scenarios(
        pars_nominal=pars_nominal,
        pars_changed=pars_changed,
        payload_cfg=cfg["payload_cfg"],
        rng=rng,
        change_mask=tuple(change_mask),
        subset_weights=cfg["dataset"]["subset_weights"],
    )
    team_nominal_pars = retune_team_parameters_a2(team_nominal_pars, payload_cfg=cfg["payload_cfg"])
    team_actual_pars = retune_team_parameters_a2(team_actual_pars, payload_cfg=cfg["payload_cfg"])
    for tpars in (team_nominal_pars, team_actual_pars):
        tpars["s_ref"] = s_ref
        tpars["curvature_ref"] = curvature_ref
        tpars["s_upper"] = float(s_ref[-1] + cfg["system_nominal"].get("s_margin", 20.0))

    def clip_state(x):
        return _team_state_clip(x, s_upper=team_actual_pars["s_upper"])

    dynamics_obj = HybridRigidPayloadDynamicsA2(
        payload_module=payload_module,
        nominal_pars=team_nominal_pars,
        residual_model=model,
        koopman_model=model.get("koopman_model", None),
        koopman_blend=float(cfg.get("koopman", {}).get("blend_in_dynamics", 0.0)),
        clip_fn=clip_state,
    )
    supervisor = A2SupervisoryController(dt=float(cfg["dt"]), **cfg["supervisor"])
    tube_helper = model["tube_helper"]
    coordinator = RigidPayloadCoordinatorA2(payload_module=payload_module, payload_cfg=cfg["payload_cfg"])
    ref_bundle = coordinator.build_reference_bundle(team_ref_hist, horizon_pad=sim_steps_cap + horizon + 3 - traj_length)

    umin_base = np.asarray(cfg["mpc"]["umin"], dtype=float)
    umax_base = np.asarray(cfg["mpc"]["umax"], dtype=float)
    xmin_base = np.asarray(cfg["mpc"]["xmin"], dtype=float).copy()
    xmax_base = np.asarray(cfg["mpc"]["xmax"], dtype=float).copy()
    xmax_base[0] = float(team_actual_pars["s_upper"])

    xmin_tight, xmax_tight = tube_helper.tighten_state_bounds(xmin_base, xmax_base)
    umin_tight, umax_tight = tube_helper.tighten_input_bounds(umin_base, umax_base)

    x0_team = np.array(
        [
            0.5 * float(cfg["payload_cfg"]["payload_length"]),
            0.0,
            0.0,
            float(cfg["vx_ref"]),
            0.0,
            0.0,
        ],
        dtype=float,
    )
    x0_team = clip_state(x0_team)
    x_ref0 = coordinator.window_team_reference(ref_bundle, 0, horizon)
    z_init = np.tile(x0_team.reshape(1, -1), (horizon + 1, 1))
    u_init = np.zeros((horizon, 2), dtype=float)

    controller = NonlinearMPCController(
        dynamics_obj,
        horizon,
        float(cfg["dt"]),
        umin_tight,
        umax_tight,
        xmin_tight,
        xmax_tight,
        np.asarray(cfg["mpc"]["Q"], dtype=float),
        np.asarray(cfg["mpc"]["R"], dtype=float),
        np.asarray(cfg["mpc"]["QN"], dtype=float),
        dict(cfg["mpc"]["solver_settings"]),
        add_ppc_soft=False,
    )
    controller.construct_controller(z_init, u_init, x_ref0)

    team_hist = np.zeros((sim_steps_cap + 1, 6), dtype=float)
    team_hist[0, :] = x0_team
    input_hist = np.zeros((sim_steps_cap, 2), dtype=float)
    input_nom_hist = np.zeros((sim_steps_cap, 2), dtype=float)
    force_hist = []
    solve_status = []
    solve_flags = []
    stage_hist = []
    weight_hist = []
    pred_hold_hist = np.zeros((sim_steps_cap + 1, 6), dtype=float)
    pred_hold_hist[0, :] = x0_team

    held_u_seq = np.zeros((horizon, 2), dtype=float)
    hold_seq_idx = 0
    last_solve_step = -1
    stop_idx = sim_steps_cap

    adapt_cfg = dict(cfg.get("online_adapt", {}))
    online_adapt_enable = bool(adapt_cfg.get("enable", False)) and (model.get("koopman_model", None) is not None)
    warmup_steps = int(adapt_cfg.get("warmup_steps", 40))
    adapt_window = int(adapt_cfg.get("window", 60))
    adapt_every = int(adapt_cfg.get("update_every", 8))
    adapt_reg_hist = []
    adapt_target_hist = []
    koopman_update_steps = []
    koopman_delta_norm_hist = []
    koopman_val_rmse_hist = []
    koopman_adapt_skip_count = 0

    for k in range(sim_steps_cap):
        x_now = team_hist[k, :].copy()
        x_ref_step = ref_bundle["team_ref_hist_padded"][min(k, ref_bundle["team_ref_hist_padded"].shape[0] - 1), :]

        front_scale, rear_scale = supervisor.estimate_cornering_stiffness_scale(x_now)
        dynamics_obj.set_cornering_stiffness_scale(front_scale=front_scale, rear_scale=rear_scale)

        need_solve = supervisor.should_resolve(
            step_idx=k,
            x_now=x_now,
            x_pred_hold=pred_hold_hist[k, :],
            last_solve_step=last_solve_step,
            x_ref=x_ref_step,
        )
        solve_flags.append(bool(need_solve))

        if need_solve:
            xref_win = coordinator.window_team_reference(ref_bundle, k, horizon)
            try:
                controller.solve_to_convergence(
                    xref_win,
                    x_now,
                    controller.z_init,
                    controller.u_init,
                    max_iter=int(cfg["mpc"]["max_sqp_iters"]),
                    eps=1e-3,
                )
                controller.update_initial_guess_()
                held_u_seq = np.asarray(controller.cur_u, dtype=float).copy()
                hold_seq_idx = 1
                u_nom = held_u_seq[0, :].copy()
                last_solve_step = k
                solve_status.append(str(controller.last_solve_info.get("status", "solved")))
            except Exception as e:
                u_nom = held_u_seq[min(max(hold_seq_idx - 1, 0), horizon - 1), :].copy()
                solve_status.append(f"fallback:{e.__class__.__name__}")
        else:
            u_nom = held_u_seq[min(hold_seq_idx, horizon - 1), :].copy()
            hold_seq_idx = min(hold_seq_idx + 1, horizon - 1)
            solve_status.append("hold")

        u_aux, super_diag = supervisor.auxiliary_control(x_now, x_ref_step, k)
        u_tube = tube_helper.ancillary_control(x_now, x_ref_step)
        kappa_now = float(curvature_ref[min(k, curvature_ref.shape[0] - 1)])
        delta_ff = float(cfg["mpc"]["ff_gain"]) * (team_nominal_pars["lf"] + team_nominal_pars["lr"]) * kappa_now
        ax_ff = 0.55 * (x_ref_step[3] - x_now[3])
        e_team = x_now - x_ref_step
        u_track_fb = np.array(
            [
                delta_ff - 0.55 * e_team[1] - 1.20 * e_team[2] - 0.20 * x_now[4] - 0.28 * x_now[5],
                0.85 * (x_ref_step[3] - x_now[3]),
            ],
            dtype=float,
        )
        if solve_status[-1].startswith("fallback"):
            u_nom = u_track_fb.copy()
        u_cmd = 0.35 * u_nom + 0.65 * u_track_fb + 0.18 * u_tube + 0.65 * u_aux + np.array([0.0, ax_ff], dtype=float)
        if super_diag["stage"] == "recovery":
            u_cmd[1] = min(float(u_cmd[1]), -0.12 - 0.30 * abs(np.arctan2(x_now[4], max(x_now[3], 0.5))))
        elif x_now[3] < x_ref_step[3] - 0.25:
            u_cmd[1] = max(float(u_cmd[1]), 0.10)
        u_cmd = np.clip(u_cmd, umin_base, umax_base)

        if k > 0:
            alpha = np.asarray(cfg["mpc"]["input_smooth_alpha"], dtype=float)
            u_cmd = alpha * input_hist[k - 1, :] + (1.0 - alpha) * u_cmd
        u_cmd = np.clip(u_cmd, umin_base, umax_base)

        x_next = payload_module.FK_solver(
            x_now,
            u_cmd,
            team_actual_pars,
            sensor_noise=False,
            SNR_DB=0,
            i=k,
        )
        x_next = clip_state(x_next)
        if x_next[0] < x_now[0] + 0.02:
            x_next[0] = min(team_actual_pars["s_upper"], x_now[0] + 0.02)
        if x_next[3] < 0.70:
            x_next[3] = 0.70

        if online_adapt_enable and dynamics_obj.koopman_model is not None:
            km = dynamics_obj.koopman_model
            feat_now = HybridRigidPayloadDynamicsA2.lift_state(x_now)
            feat_n = (feat_now - np.asarray(km["feat_mu"], dtype=float)) / np.maximum(
                np.asarray(km["feat_scale"], dtype=float), 1e-6
            )
            u_n = (u_cmd - np.asarray(km["u_mu"], dtype=float)) / np.maximum(
                np.asarray(km["u_scale"], dtype=float), 1e-6
            )
            reg_k = np.concatenate((feat_n, u_n, np.array([1.0], dtype=float)))
            adapt_reg_hist.append(reg_k)
            adapt_target_hist.append(np.asarray(x_next - x_now, dtype=float).copy())

            if (
                (k + 1) >= warmup_steps
                and (k + 1) % max(1, adapt_every) == 0
                and len(adapt_reg_hist) >= max(8, adapt_window)
            ):
                reg_mat = np.asarray(adapt_reg_hist[-adapt_window:], dtype=float)
                y_mat = np.asarray(adapt_target_hist[-adapt_window:], dtype=float)
                km_new, delta_norm, rmse_cur, rmse_new = _update_koopman_model_online(
                    dynamics_obj.koopman_model, reg_mat, y_mat, adapt_cfg
                )
                accept_ratio = float(adapt_cfg.get("accept_rmse_ratio", 1.03))
                if rmse_new <= accept_ratio * rmse_cur:
                    dynamics_obj.update_koopman_model(km_new)
                    koopman_update_steps.append(int(k))
                    koopman_delta_norm_hist.append(delta_norm)
                    koopman_val_rmse_hist.append(rmse_new)
                else:
                    koopman_adapt_skip_count += 1

        team_hist[k + 1, :] = x_next
        input_hist[k, :] = u_cmd
        input_nom_hist[k, :] = u_nom
        pred_hold_hist[k + 1, :] = dynamics_obj.eval_dot(x_now, u_nom)
        force_hist.append(compute_payload_force_metrics(x_now, u_cmd, team_actual_pars, i_step=k))
        stage_hist.append(super_diag["stage"])
        weight_hist.append([super_diag["w_track"], super_diag["w_stability"]])

        if (
            x_next[0] >= team_ref_hist[-1, 0] - float(cfg["mpc"]["completion_tol_s"])
            and abs(x_next[1]) <= 0.12
            and abs(x_next[2]) <= 0.08
        ):
            stop_idx = k + 1
            break

    team_hist = team_hist[: stop_idx + 1, :]
    input_hist = input_hist[:stop_idx, :]
    input_nom_hist = input_nom_hist[:stop_idx, :]
    pred_hold_hist = pred_hold_hist[: stop_idx + 1, :]
    ref_team_hist_eval = ref_bundle["team_ref_hist_padded"][: team_hist.shape[0], :]
    corner_histories = coordinator.team_hist_to_corner_histories(team_hist)
    corner_ref_histories = [
        ref_hist[: team_hist.shape[0], :].copy() for ref_hist in ref_bundle["corner_ref_histories"]
    ]
    team_err = coordinator.compute_team_errors(team_hist, ref_team_hist_eval)
    corner_err = coordinator.compute_corner_errors(corner_histories, corner_ref_histories)
    force_summary = summarize_force_history(force_hist)

    phase_plane = np.column_stack((team_hist[:, 4], team_hist[:, 5]))
    beta_hist = np.arctan2(team_hist[:, 4], np.maximum(team_hist[:, 3], 0.5))
    solve_ratio = float(np.mean(np.asarray(solve_flags, dtype=float))) if solve_flags else 1.0
    metrics = {
        "rmse_e_y": float(np.sqrt(np.mean(team_err["e_y"] ** 2))),
        "rmse_e_psi": float(np.sqrt(np.mean(team_err["e_psi"] ** 2))),
        "rmse_e_vx": float(np.sqrt(np.mean(team_err["e_vx"] ** 2))),
        "max_abs_beta": float(np.max(np.abs(beta_hist))),
        "max_abs_r": float(np.max(np.abs(team_hist[:, 5]))),
        "final_s": float(team_hist[-1, 0]),
        "target_s": float(team_ref_hist[-1, 0]),
        "completion_ratio": float(team_hist[-1, 0] / max(team_ref_hist[-1, 0], 1e-6)),
        "solve_ratio": solve_ratio,
        "num_steps": int(team_hist.shape[0] - 1),
    }
    if model.get("koopman_model", None) is not None:
        metrics["koopman_train_rmse"] = float(model["koopman_model"]["train_rmse"])
        metrics["koopman_val_rmse"] = float(model["koopman_model"]["val_rmse"])
        metrics["koopman_train_nrmse"] = float(model["koopman_model"]["train_nrmse"])
        metrics["koopman_val_nrmse"] = float(model["koopman_model"]["val_nrmse"])
    metrics["koopman_update_count"] = int(len(koopman_update_steps))
    metrics["koopman_skip_count"] = int(koopman_adapt_skip_count)
    metrics["koopman_delta_norm_mean"] = float(np.mean(koopman_delta_norm_hist)) if koopman_delta_norm_hist else 0.0
    metrics.update(force_summary)

    if verbose:
        print("[A2] train_rmse:", model["train_rmse"], "val_rmse:", model["val_rmse"])
        print("[A2] disturbance bound:", np.round(model["disturbance_bound"], 4))
        if model.get("koopman_model", None) is not None:
            print(
                "[A2] koopman rmse train/val:",
                model["koopman_model"]["train_rmse"],
                model["koopman_model"]["val_rmse"],
            )
            print(
                "[A2] koopman nrmse train/val:",
                model["koopman_model"]["train_nrmse"],
                model["koopman_model"]["val_nrmse"],
            )
        if koopman_update_steps:
            print(
                "[A2] online koopman updates:",
                len(koopman_update_steps),
                "mean_delta_norm:",
                float(np.mean(koopman_delta_norm_hist)),
                "skip:",
                int(koopman_adapt_skip_count),
            )
        print("[A2] metrics:", metrics)

    return {
        "cfg": cfg,
        "path_data": path_data,
        "model": model,
        "payload_change_mask": tuple(payload_change_mask),
        "team_nominal_pars": team_nominal_pars,
        "team_actual_pars": team_actual_pars,
        "team_state_hist": team_hist,
        "team_input_hist": input_hist,
        "team_input_nominal_hist": input_nom_hist,
        "team_ref_hist": ref_team_hist_eval,
        "corner_state_histories": corner_histories,
        "corner_ref_histories": corner_ref_histories,
        "payload_force_hist": force_hist,
        "payload_force_summary": force_summary,
        "team_error_hist": team_err,
        "corner_error_histories": corner_err,
        "solve_flags": solve_flags,
        "solve_status": solve_status,
        "stage_hist": stage_hist,
        "weight_hist": np.asarray(weight_hist, dtype=float),
        "phase_plane": phase_plane,
        "beta_hist": beta_hist,
        "pred_hold_hist": pred_hold_hist,
        "online_koopman_enabled": bool(online_adapt_enable),
        "koopman_update_steps": np.asarray(koopman_update_steps, dtype=int),
        "koopman_delta_norm_hist": np.asarray(koopman_delta_norm_hist, dtype=float),
        "koopman_online_rmse_hist": np.asarray(koopman_val_rmse_hist, dtype=float),
        "koopman_adapt_skip_count": int(koopman_adapt_skip_count),
        "koopman_model_final": copy.deepcopy(dynamics_obj.koopman_model),
        "metrics": metrics,
    }
