import itertools
import os

import numpy as np

from dynamics.cacalv3 import _add_sensor_noise
from dynamics.cacalv3 import _get_rng
from dynamics.cacalv3 import build_reference_path
from dynamics.cacalv3 import interp_path_value


PAYLOAD_CORNER_NAMES = ("front_left", "front_right", "rear_left", "rear_right")
DEFAULT_SUBSET_WEIGHTS = {1: 0.40, 2: 0.30, 3: 0.20, 4: 0.10}


LAST_VARIATION_MASKS = []
LAST_VARIATION_LABELS = []


def build_payload_config(
    payload_mass=2000.0,
    payload_length=5.0,
    payload_width=2.0,
    com_height=1.2,
    gravity=9.81,
):
    half_l = 0.5 * float(payload_length)
    half_w = 0.5 * float(payload_width)
    return {
        "payload_mass": float(payload_mass),
        "payload_length": float(payload_length),
        "payload_width": float(payload_width),
        "com_height": float(com_height),
        "gravity": float(gravity),
        "corner_offsets": (
            (half_l, half_w),
            (half_l, -half_w),
            (-half_l, half_w),
            (-half_l, -half_w),
        ),
        "corner_names": PAYLOAD_CORNER_NAMES,
    }


def get_payload_config(pars=None):
    cfg = build_payload_config()
    if pars is None:
        return cfg

    user_cfg = pars.get("payload_cfg", None)
    if user_cfg is not None:
        cfg.update(user_cfg)

    half_l = 0.5 * float(cfg["payload_length"])
    half_w = 0.5 * float(cfg["payload_width"])
    cfg["corner_offsets"] = (
        (half_l, half_w),
        (half_l, -half_w),
        (-half_l, half_w),
        (-half_l, -half_w),
    )
    cfg["corner_names"] = PAYLOAD_CORNER_NAMES
    return cfg


def _clip_state_bounds(x, s_upper=500.0):
    x = np.asarray(x, dtype=float).copy()
    x[0] = np.clip(x[0], 0.0, s_upper)
    x[1] = np.clip(x[1], -5.0, 5.0)
    x[2] = np.clip(x[2], -1.2, 1.2)
    try:
        vx_upper = max(0.5, float(os.environ.get("TF12_CLOSED_LOOP_VX_MAX", 10.0)))
    except (TypeError, ValueError):
        vx_upper = 10.0
    x[3] = np.clip(x[3], 0.5, vx_upper)
    x[4] = np.clip(x[4], -5.0, 5.0)
    x[5] = np.clip(x[5], -3.0, 3.0)
    return x


def _vehicle_template(pars):
    return {
        "m": float(pars["m"]),
        "Iz": float(pars["Iz"]),
        "lf": float(pars["lf"]),
        "lr": float(pars["lr"]),
        "Cf": float(pars["Cf"]),
        "Cr": float(pars["Cr"]),
    }


def _all_subset_masks(n=4):
    masks = []
    ids = list(range(n))
    for size in range(1, n + 1):
        masks.extend(list(itertools.combinations(ids, size)))
    return masks


def sample_variation_mask(rng, n=4, subset_weights=None):
    subset_weights = DEFAULT_SUBSET_WEIGHTS if subset_weights is None else subset_weights
    masks = _all_subset_masks(n=n)
    weights = np.array([float(subset_weights.get(len(mask), 1.0)) for mask in masks], dtype=float)
    weights = weights / np.sum(weights)
    idx = int(rng.choice(len(masks), p=weights))
    return tuple(masks[idx])


def build_changed_vehicle_param_list(
    pars_nominal,
    pars_changed,
    change_mask,
    rng,
    blend_low=0.75,
    blend_high=1.00,
):
    nominal = _vehicle_template(pars_nominal)
    changed = _vehicle_template(pars_changed)

    vehicles = []
    for vid in range(4):
        cur = dict(nominal)
        if vid in set(change_mask):
            alpha = float(rng.uniform(blend_low, blend_high))
            cur["m"] = (1.0 - alpha) * nominal["m"] + alpha * changed["m"]
            cur["Iz"] = (1.0 - alpha) * nominal["Iz"] + alpha * changed["Iz"]
            cur["Cf"] = (1.0 - alpha) * nominal["Cf"] + alpha * changed["Cf"]
            cur["Cr"] = (1.0 - alpha) * nominal["Cr"] + alpha * changed["Cr"]
        vehicles.append(cur)
    return vehicles


def compose_team_parameters(pars_template, vehicle_pars_list, payload_cfg=None):
    payload_cfg = get_payload_config({"payload_cfg": payload_cfg} if payload_cfg is not None else None)
    team_pars = dict(pars_template)
    team_pars["payload_cfg"] = dict(payload_cfg)
    team_pars["vehicle_pars_list"] = [dict(v) for v in vehicle_pars_list]

    payload_mass = float(payload_cfg["payload_mass"])
    payload_length = float(payload_cfg["payload_length"])
    payload_width = float(payload_cfg["payload_width"])
    corner_offsets = payload_cfg["corner_offsets"]

    total_vehicle_mass = float(sum(v["m"] for v in vehicle_pars_list))
    total_mass = payload_mass + total_vehicle_mass

    payload_Iz = payload_mass * (payload_length ** 2 + payload_width ** 2) / 12.0
    total_Iz = payload_Iz
    for vpars, (dx, dy) in zip(vehicle_pars_list, corner_offsets):
        total_Iz += float(vpars["Iz"]) + float(vpars["m"]) * (dx ** 2 + dy ** 2)

    lf_eq = 0.5 * payload_length + float(np.mean([v["lf"] for v in vehicle_pars_list]))
    lr_eq = 0.5 * payload_length + float(np.mean([v["lr"] for v in vehicle_pars_list]))
    Cf_eq = float(np.sum([v["Cf"] for v in vehicle_pars_list]))
    Cr_eq = float(np.sum([v["Cr"] for v in vehicle_pars_list]))

    team_pars["m"] = total_mass
    team_pars["Iz"] = total_Iz
    team_pars["lf"] = lf_eq
    team_pars["lr"] = lr_eq
    team_pars["Cf"] = Cf_eq
    team_pars["Cr"] = Cr_eq
    team_pars["payload_equivalent_Iz"] = payload_Iz
    team_pars["payload_total_mass"] = total_mass
    team_pars["payload_vehicle_mass_total"] = total_vehicle_mass
    return team_pars


def build_team_parameter_scenarios(
    pars_nominal,
    pars_changed,
    payload_cfg=None,
    rng=None,
    change_mask=None,
    subset_weights=None,
):
    rng = _get_rng(pars_nominal) if rng is None else rng
    payload_cfg = get_payload_config({"payload_cfg": payload_cfg} if payload_cfg is not None else pars_nominal)

    nominal_vehicle_pars = [_vehicle_template(pars_nominal) for _ in range(4)]
    if change_mask is None:
        change_mask = sample_variation_mask(rng, n=4, subset_weights=subset_weights)
    changed_vehicle_pars = build_changed_vehicle_param_list(pars_nominal, pars_changed, change_mask, rng)

    team_nominal = compose_team_parameters(pars_nominal, nominal_vehicle_pars, payload_cfg=payload_cfg)
    team_changed = compose_team_parameters(pars_changed, changed_vehicle_pars, payload_cfg=payload_cfg)

    team_nominal["variation_mask"] = tuple()
    team_changed["variation_mask"] = tuple(change_mask)
    return team_nominal, team_changed, tuple(change_mask)


def team_to_corner_states(team_state, payload_cfg=None):
    payload_cfg = get_payload_config({"payload_cfg": payload_cfg} if payload_cfg is not None else None)
    x_team = np.asarray(team_state, dtype=float).reshape(-1)
    s_c, ey_c, epsi_c, vx_c, vy_c, r_c = x_team

    cpsi = np.cos(epsi_c)
    spsi = np.sin(epsi_c)

    states = []
    for dx, dy in payload_cfg["corner_offsets"]:
        ds = dx * cpsi - dy * spsi
        dey = dx * spsi + dy * cpsi
        vx_local = vx_c - r_c * dy
        vy_local = vy_c + r_c * dx
        states.append(np.array([
            s_c + ds,
            ey_c + dey,
            epsi_c,
            vx_local,
            vy_local,
            r_c,
        ], dtype=float))
    return states


def corner_states_to_team_state(corner_states, payload_cfg=None):
    payload_cfg = get_payload_config({"payload_cfg": payload_cfg} if payload_cfg is not None else None)
    x_corner = np.asarray(corner_states, dtype=float)
    if x_corner.shape[0] != 4 or x_corner.shape[1] != 6:
        raise ValueError("corner_states must have shape (4, 6)")

    epsi_c = float(np.mean(x_corner[:, 2]))
    r_c = float(np.mean(x_corner[:, 5]))
    cpsi = np.cos(epsi_c)
    spsi = np.sin(epsi_c)

    s_vals, ey_vals, vx_vals, vy_vals = [], [], [], []
    for idx, (dx, dy) in enumerate(payload_cfg["corner_offsets"]):
        ds = dx * cpsi - dy * spsi
        dey = dx * spsi + dy * cpsi
        s_vals.append(x_corner[idx, 0] - ds)
        ey_vals.append(x_corner[idx, 1] - dey)
        vx_vals.append(x_corner[idx, 3] + r_c * dy)
        vy_vals.append(x_corner[idx, 4] - r_c * dx)

    return np.array([
        float(np.mean(s_vals)),
        float(np.mean(ey_vals)),
        epsi_c,
        float(np.mean(vx_vals)),
        float(np.mean(vy_vals)),
        r_c,
    ], dtype=float)


def aggregate_team_control(u_vehicle_stack):
    u_arr = np.asarray(u_vehicle_stack, dtype=float)
    if u_arr.ndim != 2 or u_arr.shape[1] != 2:
        raise ValueError("u_vehicle_stack must have shape (n_vehicle, 2)")

    u_team = np.mean(u_arr, axis=0)
    diag = {
        "delta_spread": float(np.std(u_arr[:, 0])),
        "ax_spread": float(np.std(u_arr[:, 1])),
        "delta_mean": float(u_team[0]),
        "ax_mean": float(u_team[1]),
    }
    return u_team.astype(float), diag


def _team_rhs(x_state, u_team, pars, i_step=0, return_aux=False):
    dt = float(pars["dt"])
    del dt

    mass = float(pars["m"])
    Iz = float(pars["Iz"])
    lf = float(pars["lf"])
    lr = float(pars["lr"])
    Cf = float(pars["Cf"])
    Cr = float(pars["Cr"])

    x_state = np.asarray(x_state, dtype=float).reshape(-1)
    u_team = np.asarray(u_team, dtype=float).reshape(-1)

    uncertainty_type = pars.get("uncertainty", "NA")
    amp = float(pars.get("amp", 0.0))
    freq = float(pars.get("freq", 1.0))
    dt_step = float(pars["dt"])

    if uncertainty_type == "constant":
        uncertainty_factor = amp
    elif uncertainty_type == "periodic":
        uncertainty_factor = amp * np.sin(2 * np.pi * freq * i_step * dt_step)
    else:
        uncertainty_factor = 0.0

    delta_eff = float(u_team[0]) + 0.5 * uncertainty_factor
    ax_eff = float(u_team[1]) + uncertainty_factor

    s_ref_arr = np.asarray(pars["s_ref"], dtype=float)
    curvature_ref_arr = np.asarray(pars["curvature_ref"], dtype=float)

    s, e_y, e_psi, vx, v_y, r = x_state
    vx_safe = max(float(vx), 0.5)
    kappa = float(interp_path_value(s, s_ref_arr, curvature_ref_arr))

    raw_denom = 1.0 - kappa * e_y
    if abs(raw_denom) < 1e-3:
        denom = np.sign(raw_denom) * 1e-3 if raw_denom != 0 else 1e-3
    else:
        denom = raw_denom

    s_dot = (vx_safe * np.cos(e_psi) - v_y * np.sin(e_psi)) / denom
    e_y_dot = vx_safe * np.sin(e_psi) + v_y * np.cos(e_psi)
    e_psi_dot = r - kappa * s_dot

    v_y_dot = (
        -(2.0 * Cf + 2.0 * Cr) / (mass * vx_safe) * v_y
        + (-vx_safe - (2.0 * Cf * lf - 2.0 * Cr * lr) / (mass * vx_safe)) * r
        + (2.0 * Cf / mass) * delta_eff
    )

    r_dot = (
        -(2.0 * Cf * lf - 2.0 * Cr * lr) / (Iz * vx_safe) * v_y
        - (2.0 * Cf * lf ** 2 + 2.0 * Cr * lr ** 2) / (Iz * vx_safe) * r
        + (2.0 * Cf * lf / Iz) * delta_eff
    )

    vx_dot = ax_eff + r * v_y

    dxdt = np.array([s_dot, e_y_dot, e_psi_dot, vx_dot, v_y_dot, r_dot], dtype=float)

    if not return_aux:
        return dxdt

    ay_body = v_y_dot + vx_safe * r
    ax_body = vx_dot - r * v_y
    aux = {
        "kappa": kappa,
        "delta_eff": delta_eff,
        "ax_eff": ax_eff,
        "ax_body": float(ax_body),
        "ay_body": float(ay_body),
    }
    return dxdt, aux


def FK_solver(x, u, pars, sensor_noise=False, SNR_DB=0, i=0):
    dt = float(pars["dt"])
    rng = _get_rng(pars)

    x = np.asarray(x, dtype=float).reshape(-1)
    u = np.asarray(u, dtype=float).reshape(-1)

    k1 = _team_rhs(x, u, pars, i_step=i)
    k2 = _team_rhs(x + 0.5 * dt * k1, u, pars, i_step=i)
    k3 = _team_rhs(x + 0.5 * dt * k2, u, pars, i_step=i)
    k4 = _team_rhs(x + dt * k3, u, pars, i_step=i)

    x_next = x + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

    if sensor_noise:
        x_next = _add_sensor_noise(x_next, pars, SNR_DB=SNR_DB, rng=rng)

    s_upper = float(pars.get("s_upper", max(500.0, x_next[0] + 10.0)))
    return _clip_state_bounds(x_next, s_upper=s_upper)


def compute_payload_force_metrics(team_state, team_input, team_pars, i_step=0):
    xdot, aux = _team_rhs(team_state, team_input, team_pars, i_step=i_step, return_aux=True)
    payload_cfg = get_payload_config(team_pars)

    payload_mass = float(payload_cfg["payload_mass"])
    payload_length = float(payload_cfg["payload_length"])
    payload_width = float(payload_cfg["payload_width"])
    com_height = float(payload_cfg["com_height"])
    gravity = float(payload_cfg["gravity"])
    payload_Iz = float(team_pars.get(
        "payload_equivalent_Iz",
        payload_mass * (payload_length ** 2 + payload_width ** 2) / 12.0,
    ))

    ax_body = float(aux["ax_body"])
    ay_body = float(aux["ay_body"])
    r_dot = float(xdot[5])

    fx_payload = payload_mass * ax_body
    fy_payload = payload_mass * ay_body
    mz_payload = payload_Iz * r_dot

    static_load = payload_mass * gravity / 4.0
    d_long = payload_mass * ax_body * com_height / max(2.0 * payload_length, 1e-6)
    d_lat = payload_mass * ay_body * com_height / max(2.0 * payload_width, 1e-6)

    fl = static_load - d_long - d_lat
    fr = static_load - d_long + d_lat
    rl = static_load + d_long - d_lat
    rr = static_load + d_long + d_lat
    corner_loads = np.array([fl, fr, rl, rr], dtype=float)

    return {
        "ax_body": ax_body,
        "ay_body": ay_body,
        "fx_payload": float(fx_payload),
        "fy_payload": float(fy_payload),
        "mz_payload": float(mz_payload),
        "corner_normal_loads": corner_loads,
        "kappa": float(aux["kappa"]),
        "r_dot": r_dot,
    }


def summarize_force_history(force_hist):
    if len(force_hist) == 0:
        return {}

    fx = np.array([item["fx_payload"] for item in force_hist], dtype=float)
    fy = np.array([item["fy_payload"] for item in force_hist], dtype=float)
    mz = np.array([item["mz_payload"] for item in force_hist], dtype=float)
    corner_loads = np.array([item["corner_normal_loads"] for item in force_hist], dtype=float)

    return {
        "fx_peak_abs": float(np.max(np.abs(fx))),
        "fy_peak_abs": float(np.max(np.abs(fy))),
        "mz_peak_abs": float(np.max(np.abs(mz))),
        "corner_load_min": float(np.min(corner_loads)),
        "corner_load_max": float(np.max(corner_loads)),
    }


def single_vehicle_data_gen_multi(num_traj, num_snaps, pars, pars_new, sensor_noise=False, SNR_DB=0):
    n_states = int(pars["num_states"])
    n_inputs = int(pars["num_inputs"])
    dt = float(pars["dt"])

    if n_states != 6:
        raise ValueError("Rigid-payload A1 model expects 6 states.")
    if n_inputs != 2:
        raise ValueError("Rigid-payload A1 model expects 2 inputs.")

    rng = _get_rng(pars)
    payload_cfg = get_payload_config(pars)

    delta_max = float(pars.get("delta_max", 0.08))
    ax_max = float(pars.get("ax_max", 2.0))
    vx_ref = float(pars["vx_ref"])

    road_modes = pars.get("road_modes", ["straight", "sin", "const", "dlc"])
    road_mode_probs = np.asarray(pars.get("road_mode_probs", [0.15, 0.15, 0.10, 0.60]), dtype=float)
    road_mode_probs = road_mode_probs / np.sum(road_mode_probs)

    u_modes = pars.get("u_modes", ["feedback_dominant", "sinusoidal", "mixed"])
    u_mode_probs = np.asarray(pars.get("u_mode_probs", [0.50, 0.30, 0.20]), dtype=float)
    u_mode_probs = u_mode_probs / np.sum(u_mode_probs)

    s_margin = float(pars.get("s_margin", 15.0))
    alpha_u = float(pars.get("alpha_u", 0.70))

    X_nominal_list = []
    X_changed_list = []
    U_list = []
    variation_masks = []

    team_s0 = 0.5 * payload_cfg["payload_length"]

    for _ in range(num_traj):
        road_mode = str(rng.choice(road_modes, p=road_mode_probs))
        path_data = build_reference_path(
            num_snaps=num_snaps,
            dt=dt,
            vx_ref=vx_ref,
            road_mode=road_mode,
            rng=rng,
        )
        s_ref_path = np.asarray(path_data["s_ref"], dtype=float)
        kappa_ref_path = np.asarray(path_data["curvature_ref"], dtype=float)
        s_max = float(s_ref_path[-1])

        team_nominal_pars, team_changed_pars, change_mask = build_team_parameter_scenarios(
            pars_nominal=pars,
            pars_changed=pars_new,
            payload_cfg=payload_cfg,
            rng=rng,
            change_mask=None,
            subset_weights=pars.get("variation_subset_weights", None),
        )

        for tpars in (team_nominal_pars, team_changed_pars):
            tpars["rng"] = rng
            tpars["s_ref"] = s_ref_path
            tpars["curvature_ref"] = kappa_ref_path
            tpars["s_upper"] = s_max + s_margin

        if rng.random() < 0.75:
            x0_team = np.array([
                team_s0,
                rng.uniform(-0.20, 0.20),
                rng.uniform(-0.05, 0.05),
                rng.uniform(vx_ref - 0.4, vx_ref + 0.4),
                rng.uniform(-0.15, 0.15),
                rng.uniform(-0.08, 0.08),
            ], dtype=float)
        else:
            x0_team = np.array([
                team_s0,
                rng.uniform(-0.80, 0.80),
                rng.uniform(-0.15, 0.15),
                rng.uniform(max(vx_ref - 1.0, 0.5), vx_ref + 1.0),
                rng.uniform(-0.50, 0.50),
                rng.uniform(-0.20, 0.20),
            ], dtype=float)

        X_team_nom = np.zeros((num_snaps, n_states), dtype=float)
        X_team_chg = np.zeros((num_snaps, n_states), dtype=float)
        U_team = np.zeros((num_snaps - 1, n_inputs), dtype=float)

        X_team_nom[0, :] = x0_team
        X_team_chg[0, :] = x0_team.copy()

        u_mode = str(rng.choice(u_modes, p=u_mode_probs))
        u_prev = np.zeros(n_inputs, dtype=float)
        seed_1 = rng.uniform(0.5, 4.0)
        seed_2 = rng.uniform(0.5, 4.0)

        for j in range(num_snaps - 1):
            x_now = X_team_nom[j, :]
            kappa_now = float(interp_path_value(x_now[0], s_ref_path, kappa_ref_path))
            delta_path_ff = (team_nominal_pars["lf"] + team_nominal_pars["lr"]) * kappa_now

            if u_mode == "feedback_dominant":
                delta_ff = 0.15 * delta_max * rng.normal()
                a_x_ff = 0.15 * ax_max * rng.normal()
            elif u_mode == "sinusoidal":
                delta_ff = 0.70 * delta_max * np.sin(seed_1 * np.pi * j * dt) + 0.10 * delta_max * rng.normal()
                a_x_ff = 0.70 * ax_max * np.cos(seed_2 * np.pi * j * dt) + 0.10 * ax_max * rng.normal()
            elif u_mode == "mixed":
                delta_ff = 0.35 * delta_max * np.sin(seed_1 * np.pi * j * dt) + rng.uniform(-0.30 * delta_max, 0.30 * delta_max)
                a_x_ff = 0.35 * ax_max * np.cos(seed_2 * np.pi * j * dt) + rng.uniform(-0.30 * ax_max, 0.30 * ax_max)
            else:
                raise ValueError(f"Unsupported u_mode: {u_mode}")

            delta_fb = -0.35 * x_now[1] - 0.90 * x_now[2] - 0.12 * x_now[4] - 0.20 * x_now[5]
            a_x_fb = -0.60 * (x_now[3] - vx_ref)

            delta_cmd = np.clip(delta_path_ff + delta_ff + delta_fb, -delta_max, delta_max)
            ax_cmd = np.clip(a_x_ff + a_x_fb, -ax_max, ax_max)

            u_raw = np.array([delta_cmd, ax_cmd], dtype=float)
            u_now = alpha_u * u_prev + (1.0 - alpha_u) * u_raw
            u_now[0] = np.clip(u_now[0], -delta_max, delta_max)
            u_now[1] = np.clip(u_now[1], -ax_max, ax_max)
            U_team[j, :] = u_now
            u_prev = u_now.copy()

            x1_next = FK_solver(
                X_team_nom[j, :],
                U_team[j, :],
                team_nominal_pars,
                sensor_noise=False,
                SNR_DB=SNR_DB,
                i=j,
            )
            x2_next = FK_solver(
                X_team_chg[j, :],
                U_team[j, :],
                team_changed_pars,
                sensor_noise=sensor_noise,
                SNR_DB=SNR_DB,
                i=j,
            )

            X_team_nom[j + 1, :] = _clip_state_bounds(x1_next, s_upper=s_max + s_margin)
            X_team_chg[j + 1, :] = _clip_state_bounds(x2_next, s_upper=s_max + s_margin)

        corner_nom = [np.zeros((num_snaps, n_states), dtype=float) for _ in range(4)]
        corner_chg = [np.zeros((num_snaps, n_states), dtype=float) for _ in range(4)]
        for j in range(num_snaps):
            states_nom_j = team_to_corner_states(X_team_nom[j, :], payload_cfg=payload_cfg)
            states_chg_j = team_to_corner_states(X_team_chg[j, :], payload_cfg=payload_cfg)
            for vid in range(4):
                corner_nom[vid][j, :] = states_nom_j[vid]
                corner_chg[vid][j, :] = states_chg_j[vid]

        for vid in range(4):
            X_nominal_list.append(corner_nom[vid])
            X_changed_list.append(corner_chg[vid])
            U_list.append(U_team.copy())
            variation_masks.append(tuple(change_mask))

    global LAST_VARIATION_MASKS, LAST_VARIATION_LABELS
    LAST_VARIATION_MASKS = list(variation_masks)
    LAST_VARIATION_LABELS = [mask_to_label(mask) for mask in variation_masks]

    return (
        np.asarray(X_nominal_list, dtype=float),
        np.asarray(X_changed_list, dtype=float),
        np.asarray(U_list, dtype=float),
    )


def mask_to_label(mask):
    if mask is None or len(mask) == 0:
        return "nominal"
    return "veh_" + "_".join(str(int(idx) + 1) for idx in mask)


def variation_summary(labels):
    if labels is None or len(labels) == 0:
        return {}
    values, counts = np.unique(np.asarray(labels, dtype=object), return_counts=True)
    return {str(v): int(c) for v, c in zip(values, counts)}
