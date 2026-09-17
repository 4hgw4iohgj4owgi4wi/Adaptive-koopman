from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

import numpy as np


class SwitchedFTCCertificateTF14:
    """Online Lyapunov-style certificate recorder for TF14.

    This is not the proof itself; it records the quantities used by the proof:
    - mode-dependent quadratic Lyapunov value,
    - one-step upper bound under switched FTC,
    - observed contraction margin.
    """

    def __init__(
        self,
        *,
        dt: float,
        lambda_nominal: float = 0.08,
        lambda_reconfigured: float = 0.06,
        lambda_safe: float = 0.04,
        gamma_disturbance: float = 0.85,
        gamma_identification: float = 0.55,
    ) -> None:
        self.dt = float(max(dt, 1e-4))
        self.lambda_map = {
            "nominal_koopman_mpc": float(lambda_nominal),
            "reconfigured_ftc_mpc": float(lambda_reconfigured),
            "safe_degraded_consensus": float(lambda_safe),
        }
        self.gamma_disturbance = float(max(gamma_disturbance, 0.0))
        self.gamma_identification = float(max(gamma_identification, 0.0))
        self.P_map = {
            "nominal_koopman_mpc": np.diag([0.8, 3.5, 2.8, 0.9, 0.8, 1.4]),
            "reconfigured_ftc_mpc": np.diag([1.0, 4.5, 3.8, 1.0, 0.9, 1.7]),
            "safe_degraded_consensus": np.diag([1.4, 5.5, 4.8, 1.2, 1.1, 2.0]),
        }
        self.prev_V = None
        self.prev_bound = None

    def reset(self) -> None:
        self.prev_V = None
        self.prev_bound = None

    def _mode_matrix(self, mode: str) -> np.ndarray:
        return self.P_map.get(mode, self.P_map["nominal_koopman_mpc"])

    def _mode_lambda(self, mode: str) -> float:
        return self.lambda_map.get(mode, self.lambda_map["nominal_koopman_mpc"])

    def update(
        self,
        *,
        k: int,
        team_state: Sequence[float],
        team_ref: Sequence[float],
        mode: str,
        diagnoses: Sequence[Mapping[str, Any]],
        comm_quality_global: float,
    ) -> Dict[str, Any]:
        x = np.asarray(team_state, dtype=float).reshape(-1)
        xr = np.asarray(team_ref, dtype=float).reshape(-1)
        err = x - xr
        P = self._mode_matrix(mode)
        lam = self._mode_lambda(mode)
        V = float(err.T @ P @ err)
        ident_err = 0.0
        for d in diagnoses:
            ax_eff = float(d.get("ax_eff_est", 1.0))
            delta_eff = float(d.get("delta_eff_est", 1.0))
            ident_err += abs(1.0 - ax_eff) + abs(1.0 - delta_eff)
        ident_err = float(ident_err)
        disturbance_level = float(max(0.0, 1.0 - comm_quality_global))
        predicted_upper = float(
            (1.0 - lam * self.dt) * V
            + self.gamma_disturbance * disturbance_level ** 2
            + self.gamma_identification * ident_err ** 2
        )
        if self.prev_V is None:
            contraction_margin = np.nan
        else:
            contraction_margin = float(self.prev_bound - V)
        self.prev_V = V
        self.prev_bound = predicted_upper
        return {
            "step": int(k),
            "mode": str(mode),
            "V": V,
            "predicted_upper": predicted_upper,
            "contraction_margin": contraction_margin,
            "disturbance_level": disturbance_level,
            "identification_error": ident_err,
            "certificate_ok": bool(np.isnan(contraction_margin) or contraction_margin >= -1e-4),
        }

    @staticmethod
    def summarize(cert_hist: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        if len(cert_hist) == 0:
            return {"mean_V": np.nan, "certificate_ok_ratio": np.nan}
        V_vals = np.array([float(x.get("V", np.nan)) for x in cert_hist], dtype=float)
        ok_vals = np.array([1.0 if bool(x.get("certificate_ok", False)) else 0.0 for x in cert_hist], dtype=float)
        margins = np.array([float(x.get("contraction_margin", np.nan)) for x in cert_hist], dtype=float)
        return {
            "mean_V": float(np.nanmean(V_vals)),
            "max_V": float(np.nanmax(V_vals)),
            "certificate_ok_ratio": float(np.nanmean(ok_vals)),
            "min_contraction_margin": float(np.nanmin(margins)),
        }
