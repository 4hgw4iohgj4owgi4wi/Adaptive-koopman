import numpy as np


class A2SupervisoryController:
    """Supervisory logic for the A2 controller stack.

    It blends four ideas drawn from the added papers into a lightweight
    implementation that fits the current codebase:
    1. self-triggered MPC updates,
    2. prescribed-time performance envelopes,
    3. tracking/stability weight coordination,
    4. two-stage recovery logic near the stability boundary.
    """

    def __init__(
        self,
        *,
        dt,
        max_hold_steps=3,
        discrepancy_threshold=0.16,
        prescribed_time=6.0,
        rho_ey_0=0.80,
        rho_ey_inf=0.06,
        rho_epsi_0=0.35,
        rho_epsi_inf=0.04,
        beta_limit=0.20,
        r_limit=0.55,
        stage2_beta=0.28,
        stage2_r=0.75,
        tracking_gain=None,
        stability_gain=None,
    ):
        self.dt = float(dt)
        self.max_hold_steps = int(max(1, max_hold_steps))
        self.discrepancy_threshold = float(discrepancy_threshold)
        self.prescribed_time = float(max(self.dt, prescribed_time))

        self.rho_ey_0 = float(rho_ey_0)
        self.rho_ey_inf = float(rho_ey_inf)
        self.rho_epsi_0 = float(rho_epsi_0)
        self.rho_epsi_inf = float(rho_epsi_inf)

        self.beta_limit = float(beta_limit)
        self.r_limit = float(r_limit)
        self.stage2_beta = float(stage2_beta)
        self.stage2_r = float(stage2_r)

        if tracking_gain is None:
            tracking_gain = np.array(
                [
                    [0.00, -0.95, -2.20, 0.00, -0.30, -0.45],
                    [0.08, 0.00, 0.00, -0.65, 0.00, 0.00],
                ],
                dtype=float,
            )
        if stability_gain is None:
            stability_gain = np.array(
                [
                    [0.00, -0.60, -1.70, 0.00, -1.05, -1.45],
                    [0.00, 0.00, 0.00, -0.40, -0.20, -0.25],
                ],
                dtype=float,
            )

        self.tracking_gain = np.asarray(tracking_gain, dtype=float)
        self.stability_gain = np.asarray(stability_gain, dtype=float)

    def performance_envelope(self, step_idx):
        t_now = float(step_idx) * self.dt
        ratio = max(0.0, 1.0 - t_now / self.prescribed_time)
        rho_ey = self.rho_ey_inf + (self.rho_ey_0 - self.rho_ey_inf) * ratio ** 2
        rho_epsi = self.rho_epsi_inf + (self.rho_epsi_0 - self.rho_epsi_inf) * ratio ** 2
        return {"rho_ey": float(rho_ey), "rho_epsi": float(rho_epsi)}

    def stability_metrics(self, x_now, x_ref):
        x_now = np.asarray(x_now, dtype=float).reshape(-1)
        x_ref = np.asarray(x_ref, dtype=float).reshape(-1)
        vx_safe = max(float(x_now[3]), 0.5)
        beta = float(np.arctan2(x_now[4], vx_safe))
        err = x_now - x_ref
        env = self.performance_envelope(0)
        ey_ratio = abs(err[1]) / max(env["rho_ey"], 1e-4)
        epsi_ratio = abs(err[2]) / max(env["rho_epsi"], 1e-4)
        beta_ratio = abs(beta) / max(self.beta_limit, 1e-4)
        r_ratio = abs(x_now[5]) / max(self.r_limit, 1e-4)
        severity = max(ey_ratio, epsi_ratio, beta_ratio, r_ratio)
        return {
            "beta": beta,
            "severity": float(severity),
            "ey_ratio": float(ey_ratio),
            "epsi_ratio": float(epsi_ratio),
            "beta_ratio": float(beta_ratio),
            "r_ratio": float(r_ratio),
        }

    def stage_label(self, x_now, x_ref, step_idx):
        env = self.performance_envelope(step_idx)
        metrics = self.stability_metrics(x_now, x_ref)
        if abs(metrics["beta"]) >= self.stage2_beta or abs(np.asarray(x_now)[5]) >= self.stage2_r:
            return "recovery"
        if abs(np.asarray(x_now)[1] - np.asarray(x_ref)[1]) > 1.15 * env["rho_ey"]:
            return "recovery"
        return "tracking"

    def should_resolve(self, step_idx, x_now, x_pred_hold, last_solve_step, x_ref):
        if last_solve_step < 0:
            return True
        if (int(step_idx) - int(last_solve_step)) >= self.max_hold_steps:
            return True
        x_now = np.asarray(x_now, dtype=float).reshape(-1)
        x_pred_hold = np.asarray(x_pred_hold, dtype=float).reshape(-1)
        x_ref = np.asarray(x_ref, dtype=float).reshape(-1)
        discrepancy = np.linalg.norm(x_now - x_pred_hold, ord=2)
        if discrepancy >= self.discrepancy_threshold:
            return True
        if self.stage_label(x_now, x_ref, step_idx) == "recovery":
            return True
        return False

    def coordination_weight(self, x_now, x_ref, step_idx):
        env = self.performance_envelope(step_idx)
        x_now = np.asarray(x_now, dtype=float).reshape(-1)
        x_ref = np.asarray(x_ref, dtype=float).reshape(-1)
        vx_safe = max(float(x_now[3]), 0.5)
        beta = float(np.arctan2(x_now[4], vx_safe))
        ey_ratio = abs(x_now[1] - x_ref[1]) / max(env["rho_ey"], 1e-4)
        epsi_ratio = abs(x_now[2] - x_ref[2]) / max(env["rho_epsi"], 1e-4)
        beta_ratio = abs(beta) / max(self.beta_limit, 1e-4)
        r_ratio = abs(x_now[5]) / max(self.r_limit, 1e-4)
        severity = max(ey_ratio, epsi_ratio, beta_ratio, r_ratio)
        w_stab = np.clip((severity - 0.80) / 0.80, 0.0, 1.0)
        w_track = 1.0 - w_stab
        return float(w_track), float(w_stab)

    def estimate_cornering_stiffness_scale(self, x_now):
        x_now = np.asarray(x_now, dtype=float).reshape(-1)
        vx_safe = max(float(x_now[3]), 0.5)
        beta = abs(np.arctan2(x_now[4], vx_safe))
        lat_load = np.clip(beta / max(self.stage2_beta, 1e-4) + 0.40 * abs(x_now[5]) / max(self.stage2_r, 1e-4), 0.0, 1.2)
        front_scale = np.clip(1.0 - 0.28 * lat_load, 0.62, 1.05)
        rear_scale = np.clip(1.0 - 0.36 * lat_load, 0.55, 1.05)
        return float(front_scale), float(rear_scale)

    def auxiliary_control(self, x_now, x_ref, step_idx):
        x_now = np.asarray(x_now, dtype=float).reshape(-1)
        x_ref = np.asarray(x_ref, dtype=float).reshape(-1)
        err = x_now - x_ref
        u_track = self.tracking_gain @ err
        u_stab = self.stability_gain @ err
        stage = self.stage_label(x_now, x_ref, step_idx)
        w_track, w_stab = self.coordination_weight(x_now, x_ref, step_idx)
        if stage == "recovery":
            w_stab = max(w_stab, 0.70)
            w_track = 1.0 - w_stab
        u_aux = w_track * u_track + w_stab * u_stab
        return np.asarray(u_aux, dtype=float), {
            "stage": stage,
            "w_track": float(w_track),
            "w_stability": float(w_stab),
        }
