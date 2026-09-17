import numpy as np


class A1ProgressSupervisorV2:
    """Progress-aware longitudinal supervisor for TF11-A1 rigid payload runs.

    Purpose:
    - Avoid persistent over-braking when the team is already behind reference.
    - Keep recovery conservative when lateral/yaw states are not stable.
    """

    def __init__(
        self,
        *,
        lag_activate_s=1.2,
        lag_full_s=4.5,
        stable_ey=0.55,
        stable_epsi=0.24,
        stable_beta=0.18,
        stable_r=0.75,
        recover_ax_min=-0.12,
        recover_ax_max=0.65,
        k_lag_s=0.10,
        k_lag_v=0.65,
        k_damp_vy=0.10,
        k_damp_r=0.10,
    ):
        self.lag_activate_s = float(lag_activate_s)
        self.lag_full_s = float(max(lag_full_s, lag_activate_s + 1e-3))
        self.stable_ey = float(stable_ey)
        self.stable_epsi = float(stable_epsi)
        self.stable_beta = float(stable_beta)
        self.stable_r = float(stable_r)
        self.recover_ax_min = float(recover_ax_min)
        self.recover_ax_max = float(recover_ax_max)
        self.k_lag_s = float(k_lag_s)
        self.k_lag_v = float(k_lag_v)
        self.k_damp_vy = float(k_damp_vy)
        self.k_damp_r = float(k_damp_r)

    def _beta(self, x):
        x = np.asarray(x, dtype=float).reshape(-1)
        return float(np.arctan2(x[4], max(x[3], 0.5)))

    def apply(
        self,
        *,
        team_state,
        team_ref,
        u_team,
        umin,
        umax,
        guard_diag=None,
        blend_diag=None,
    ):
        x = np.asarray(team_state, dtype=float).reshape(-1)
        xr = np.asarray(team_ref, dtype=float).reshape(-1)
        u = np.asarray(u_team, dtype=float).reshape(-1).copy()
        umin = np.asarray(umin, dtype=float).reshape(-1)
        umax = np.asarray(umax, dtype=float).reshape(-1)

        lag_s = float(np.clip(xr[0] - x[0], 0.0, 20.0))
        lag_v = float(np.clip(xr[3] - x[3], -4.0, 4.0))
        beta = self._beta(x)

        stable = (
            abs(x[1]) <= self.stable_ey
            and abs(x[2]) <= self.stable_epsi
            and abs(beta) <= self.stable_beta
            and abs(x[5]) <= self.stable_r
        )

        if lag_s <= self.lag_activate_s or (not stable):
            return u, {
                "boost_active": False,
                "lag_s": lag_s,
                "lag_v": lag_v,
                "stable": bool(stable),
                "recover_ax": None,
                "recover_mix": 0.0,
            }

        recover_ax = (
            self.k_lag_s * lag_s
            + self.k_lag_v * max(lag_v, 0.0)
            - self.k_damp_vy * abs(x[4])
            - self.k_damp_r * abs(x[5])
        )
        recover_ax = float(np.clip(recover_ax, self.recover_ax_min, self.recover_ax_max))

        recover_mix = np.clip(
            (lag_s - self.lag_activate_s) / max(self.lag_full_s - self.lag_activate_s, 1e-6),
            0.0,
            1.0,
        )
        if guard_diag is not None:
            recover_mix *= float(np.clip(1.0 - float(guard_diag.get("w_guard", 0.0)), 0.0, 1.0))
        if blend_diag is not None:
            recover_mix *= float(np.clip(1.0 - 0.35 * float(blend_diag.get("w_blend", 0.0)), 0.0, 1.0))

        ax_new = (1.0 - recover_mix) * u[1] + recover_mix * max(float(u[1]), recover_ax)
        u[1] = float(np.clip(ax_new, umin[1], umax[1]))
        u[0] = float(np.clip(u[0], umin[0], umax[0]))

        return u, {
            "boost_active": bool(recover_mix > 1e-6),
            "lag_s": lag_s,
            "lag_v": lag_v,
            "stable": bool(stable),
            "recover_ax": recover_ax,
            "recover_mix": float(recover_mix),
        }

