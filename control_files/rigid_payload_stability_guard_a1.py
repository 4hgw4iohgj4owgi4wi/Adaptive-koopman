import numpy as np


class RigidPayloadStabilityGuardA1:
    """A1-specific guard that keeps the rigid payload controller from running away."""

    def __init__(
        self,
        *,
        beta_limit=0.18,
        r_limit=0.50,
        spread_delta_limit=0.060,
        spread_ax_limit=0.28,
        tracking_gain=None,
        stability_gain=None,
    ):
        self.beta_limit = float(beta_limit)
        self.r_limit = float(r_limit)
        self.spread_delta_limit = float(spread_delta_limit)
        self.spread_ax_limit = float(spread_ax_limit)

        if tracking_gain is None:
            tracking_gain = np.array([0.00, -0.90, -2.10, 0.00, -0.30, -0.45], dtype=float)
        if stability_gain is None:
            stability_gain = np.array([0.00, -0.50, -1.30, 0.00, -0.95, -1.20], dtype=float)
        self.tracking_gain = np.asarray(tracking_gain, dtype=float)
        self.stability_gain = np.asarray(stability_gain, dtype=float)

    def _beta(self, x):
        x = np.asarray(x, dtype=float).reshape(-1)
        return float(np.arctan2(x[4], max(x[3], 0.5)))

    def build_team_guard(self, team_state, team_ref):
        x = np.asarray(team_state, dtype=float).reshape(-1)
        xr = np.asarray(team_ref, dtype=float).reshape(-1)
        err = x - xr
        u_track = np.array(
            [
                self.tracking_gain @ err,
                0.10 * err[0] - 0.70 * err[3],
            ],
            dtype=float,
        )
        u_stab = np.array(
            [
                self.stability_gain @ err,
                -0.30 * abs(self._beta(x)) - 0.18 * abs(x[5]) - 0.45 * err[3],
            ],
            dtype=float,
        )
        beta_ratio = abs(self._beta(x)) / max(self.beta_limit, 1e-4)
        r_ratio = abs(x[5]) / max(self.r_limit, 1e-4)
        severity = max(beta_ratio, r_ratio, abs(err[1]) / 0.75, abs(err[2]) / 0.28)
        w_guard = np.clip((severity - 0.85) / 0.80, 0.0, 1.0)
        if beta_ratio > 1.25 or r_ratio > 1.25:
            w_guard = max(w_guard, 0.75)
        u_guard = (1.0 - w_guard) * u_track + w_guard * u_stab
        return u_guard, {
            "w_guard": float(w_guard),
            "severity": float(severity),
            "beta": float(self._beta(x)),
        }

    def blend_controls(self, u_team_nom, u_guard, spread_info):
        u_team_nom = np.asarray(u_team_nom, dtype=float).reshape(-1)
        u_guard = np.asarray(u_guard, dtype=float).reshape(-1)
        delta_ratio = float(spread_info.get("delta_spread", 0.0)) / max(self.spread_delta_limit, 1e-4)
        ax_ratio = float(spread_info.get("ax_spread", 0.0)) / max(self.spread_ax_limit, 1e-4)
        w_spread = np.clip(max(delta_ratio, ax_ratio) - 1.0, 0.0, 1.0)
        w_blend = 0.35 + 0.65 * w_spread
        u_out = (1.0 - w_blend) * u_team_nom + w_blend * u_guard
        return u_out, {"w_blend": float(w_blend), "w_spread": float(w_spread)}
