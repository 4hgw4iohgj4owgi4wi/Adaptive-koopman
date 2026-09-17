import copy

import numpy as np

from dynamics.cacalv3 import build_reference_path
from dynamics.cacalv3 import interp_path_value
from dynamics.cacalv3_payload_a1 import DEFAULT_SUBSET_WEIGHTS
from dynamics.cacalv3_payload_a1 import FK_solver
from dynamics.cacalv3_payload_a1 import build_payload_config
from dynamics.cacalv3_payload_a1 import build_team_parameter_scenarios
from dynamics.cacalv3_payload_a1 import compute_payload_force_metrics
from dynamics.cacalv3_payload_a1 import corner_states_to_team_state
from dynamics.cacalv3_payload_a1 import get_payload_config
from dynamics.cacalv3_payload_a1 import mask_to_label
from dynamics.cacalv3_payload_a1 import summarize_force_history
from dynamics.cacalv3_payload_a1 import team_to_corner_states
from dynamics.cacalv3_payload_a1 import variation_summary
from dynamics.cacalv3 import _get_rng


LAST_VARIATION_MASKS = []
LAST_VARIATION_LABELS = []


class RigidPayloadDatasetBuilderA2:
    """A2-specific team-level dataset generator for hybrid modeling."""

    def __init__(self, pars_nominal, pars_changed, payload_cfg=None):
        self.pars_nominal = dict(pars_nominal)
        self.pars_changed = dict(pars_changed)
        self.payload_cfg = get_payload_config({"payload_cfg": payload_cfg} if payload_cfg is not None else self.pars_nominal)

    def generate_team_dataset(self, num_traj, num_snaps, sensor_noise=False, SNR_DB=0):
        pars = self.pars_nominal
        pars_new = self.pars_changed

        n_states = int(pars["num_states"])
        n_inputs = int(pars["num_inputs"])
        dt = float(pars["dt"])

        if n_states != 6:
            raise ValueError("Rigid-payload A2 model expects 6 states.")
        if n_inputs != 2:
            raise ValueError("Rigid-payload A2 model expects 2 inputs.")

        rng = _get_rng(pars)
        payload_cfg = dict(self.payload_cfg)

        delta_max = float(pars.get("delta_max", 0.08))
        ax_max = float(pars.get("ax_max", 2.0))
        vx_ref = float(pars["vx_ref"])

        road_modes = pars.get("road_modes", ["dlc"])
        road_mode_probs = np.asarray(pars.get("road_mode_probs", [1.0]), dtype=float)
        road_mode_probs = road_mode_probs / np.sum(road_mode_probs)

        u_modes = pars.get("u_modes", ["feedback_dominant", "sinusoidal", "mixed"])
        u_mode_probs = np.asarray(pars.get("u_mode_probs", [0.50, 0.30, 0.20]), dtype=float)
        u_mode_probs = u_mode_probs / np.sum(u_mode_probs)

        s_margin = float(pars.get("s_margin", 15.0))
        alpha_u = float(pars.get("alpha_u", 0.70))

        x_nominal_list = []
        x_changed_list = []
        u_list = []
        variation_masks = []
        traj_meta = []

        team_s0 = 0.5 * payload_cfg["payload_length"]

        for traj_idx in range(int(num_traj)):
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
                subset_weights=pars.get("variation_subset_weights", DEFAULT_SUBSET_WEIGHTS),
            )
            team_nominal_pars = retune_team_parameters_a2(team_nominal_pars, payload_cfg=payload_cfg)
            team_changed_pars = retune_team_parameters_a2(team_changed_pars, payload_cfg=payload_cfg)

            for tpars in (team_nominal_pars, team_changed_pars):
                tpars["rng"] = rng
                tpars["s_ref"] = s_ref_path
                tpars["curvature_ref"] = kappa_ref_path
                tpars["s_upper"] = s_max + s_margin

            if rng.random() < 0.70:
                x0_team = np.array(
                    [
                        team_s0,
                        rng.uniform(-0.22, 0.22),
                        rng.uniform(-0.05, 0.05),
                        rng.uniform(vx_ref - 0.35, vx_ref + 0.35),
                        rng.uniform(-0.12, 0.12),
                        rng.uniform(-0.08, 0.08),
                    ],
                    dtype=float,
                )
            else:
                x0_team = np.array(
                    [
                        team_s0,
                        rng.uniform(-0.70, 0.70),
                        rng.uniform(-0.14, 0.14),
                        rng.uniform(max(vx_ref - 0.8, 0.5), vx_ref + 0.8),
                        rng.uniform(-0.45, 0.45),
                        rng.uniform(-0.18, 0.18),
                    ],
                    dtype=float,
                )

            x_team_nom = np.zeros((num_snaps, n_states), dtype=float)
            x_team_chg = np.zeros((num_snaps, n_states), dtype=float)
            u_team = np.zeros((num_snaps - 1, n_inputs), dtype=float)

            x_team_nom[0, :] = x0_team
            x_team_chg[0, :] = x0_team.copy()

            u_mode = str(rng.choice(u_modes, p=u_mode_probs))
            u_prev = np.zeros(n_inputs, dtype=float)
            seed_1 = rng.uniform(0.5, 4.0)
            seed_2 = rng.uniform(0.5, 4.0)

            for j in range(num_snaps - 1):
                x_now = x_team_nom[j, :]
                kappa_now = float(interp_path_value(x_now[0], s_ref_path, kappa_ref_path))
                delta_path_ff = (team_nominal_pars["lf"] + team_nominal_pars["lr"]) * kappa_now

                if u_mode == "feedback_dominant":
                    delta_ff = 0.12 * delta_max * rng.normal()
                    a_x_ff = 0.12 * ax_max * rng.normal()
                elif u_mode == "sinusoidal":
                    delta_ff = 0.55 * delta_max * np.sin(seed_1 * np.pi * j * dt) + 0.08 * delta_max * rng.normal()
                    a_x_ff = 0.55 * ax_max * np.cos(seed_2 * np.pi * j * dt) + 0.08 * ax_max * rng.normal()
                elif u_mode == "mixed":
                    delta_ff = 0.30 * delta_max * np.sin(seed_1 * np.pi * j * dt) + rng.uniform(-0.25 * delta_max, 0.25 * delta_max)
                    a_x_ff = 0.30 * ax_max * np.cos(seed_2 * np.pi * j * dt) + rng.uniform(-0.25 * ax_max, 0.25 * ax_max)
                else:
                    raise ValueError(f"Unsupported u_mode: {u_mode}")

                delta_fb = -0.34 * x_now[1] - 0.92 * x_now[2] - 0.14 * x_now[4] - 0.22 * x_now[5]
                a_x_fb = -0.62 * (x_now[3] - vx_ref)

                delta_cmd = np.clip(delta_path_ff + delta_ff + delta_fb, -delta_max, delta_max)
                ax_cmd = np.clip(a_x_ff + a_x_fb, -ax_max, ax_max)

                u_raw = np.array([delta_cmd, ax_cmd], dtype=float)
                u_now = alpha_u * u_prev + (1.0 - alpha_u) * u_raw
                u_now[0] = np.clip(u_now[0], -delta_max, delta_max)
                u_now[1] = np.clip(u_now[1], -ax_max, ax_max)
                u_team[j, :] = u_now
                u_prev = u_now.copy()

                x1_next = FK_solver(
                    x_team_nom[j, :],
                    u_team[j, :],
                    team_nominal_pars,
                    sensor_noise=False,
                    SNR_DB=SNR_DB,
                    i=j,
                )
                x2_next = FK_solver(
                    x_team_chg[j, :],
                    u_team[j, :],
                    team_changed_pars,
                    sensor_noise=sensor_noise,
                    SNR_DB=SNR_DB,
                    i=j,
                )

                x_team_nom[j + 1, :] = np.asarray(x1_next, dtype=float)
                x_team_chg[j + 1, :] = np.asarray(x2_next, dtype=float)

            x_nominal_list.append(x_team_nom)
            x_changed_list.append(x_team_chg)
            u_list.append(u_team)
            variation_masks.append(tuple(change_mask))
            traj_meta.append(
                {
                    "traj_idx": int(traj_idx),
                    "road_mode": road_mode,
                    "u_mode": u_mode,
                    "path_data": {k: np.asarray(v, dtype=float).copy() for k, v in path_data.items()},
                    "nominal_pars": copy.deepcopy(team_nominal_pars),
                    "changed_pars": copy.deepcopy(team_changed_pars),
                    "change_mask": tuple(change_mask),
                }
            )

        global LAST_VARIATION_MASKS, LAST_VARIATION_LABELS
        LAST_VARIATION_MASKS = list(variation_masks)
        LAST_VARIATION_LABELS = [mask_to_label(mask) for mask in variation_masks]

        return {
            "X_nominal": np.asarray(x_nominal_list, dtype=float),
            "X_changed": np.asarray(x_changed_list, dtype=float),
            "U": np.asarray(u_list, dtype=float),
            "traj_meta": traj_meta,
            "variation_masks": variation_masks,
            "variation_labels": LAST_VARIATION_LABELS,
            "variation_summary": variation_summary(LAST_VARIATION_LABELS),
            "payload_cfg": dict(payload_cfg),
        }


def generate_team_dataset_a2(num_traj, num_snaps, pars, pars_new, sensor_noise=False, SNR_DB=0):
    builder = RigidPayloadDatasetBuilderA2(pars, pars_new, payload_cfg=pars.get("payload_cfg", None))
    return builder.generate_team_dataset(
        num_traj=num_traj,
        num_snaps=num_snaps,
        sensor_noise=sensor_noise,
        SNR_DB=SNR_DB,
    )


def retune_team_parameters_a2(team_pars, payload_cfg=None):
    """A2-equivalent rigid-payload parameter reduction.

    The original A1 aggregate model over-counts the equivalent wheelbase and
    lateral stiffness for a rigid four-corner carrying platform. For A2 we use
    a simpler and more stable center-rigid-body equivalent:
    - front/rear lever arms = half payload length,
    - front cornering stiffness = front-row vehicle pair,
    - rear cornering stiffness = rear-row vehicle pair.
    """
    payload_cfg = get_payload_config({"payload_cfg": payload_cfg} if payload_cfg is not None else team_pars)
    team_out = copy.deepcopy(team_pars)
    vehicle_pars = list(team_out.get("vehicle_pars_list", []))
    if len(vehicle_pars) >= 4:
        half_l = 0.5 * float(payload_cfg["payload_length"])
        team_out["lf"] = half_l
        team_out["lr"] = half_l
        team_out["Cf"] = float(vehicle_pars[0]["Cf"]) + float(vehicle_pars[1]["Cf"])
        team_out["Cr"] = float(vehicle_pars[2]["Cr"]) + float(vehicle_pars[3]["Cr"])
    return team_out
