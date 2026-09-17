from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


@dataclass
class _VehicleFDIState:
    residual_ewma: float = 0.0
    residual_cusum: float = 0.0
    ax_eff_est: float = 1.0
    delta_eff_est: float = 1.0
    detect_counter: int = 0
    release_counter: int = 0
    mode: str = "nominal"
    confidence: float = 0.0


class OnlineFDIMonitorTF14:
    """Online FDI + fault identification for each transport vehicle.

    The monitor uses:
    1. one-step model residuals,
    2. smoothed CUSUM residual statistics,
    3. online steering / longitudinal effectiveness estimation.

    The output is an online diagnosis that can drive a reconfigured FTC law.
    """

    def __init__(
        self,
        *,
        num_vehicles: int,
        dt: float,
        mass: float,
        Iz: float,
        lf: float,
        lr: float,
        Cf: float,
        Cr: float,
        residual_scales: Optional[Sequence[float]] = None,
        residual_ewma_beta: float = 0.82,
        residual_cusum_drift: float = 0.015,
        residual_cusum_leak: float = 0.92,
        residual_threshold: float = 0.18,
        residual_cusum_threshold: float = 0.30,
        detect_hold_steps: int = 5,
        release_hold_steps: int = 10,
        ax_eff_fault_threshold: float = 0.72,
        delta_eff_fault_threshold: float = 0.74,
        severe_eff_threshold: float = 0.35,
        eff_smooth_beta: float = 0.88,
        cmd_deadzone_delta: float = 1.5e-3,
        cmd_deadzone_ax: float = 2.0e-2,
        min_valid_delta_cmd: float = 0.025,
        min_valid_ax_cmd: float = 0.10,
        warmup_steps: int = 12,
    ) -> None:
        self.num_vehicles = int(num_vehicles)
        self.dt = float(max(dt, 1e-4))
        self.mass = float(max(mass, 1.0))
        self.Iz = float(max(Iz, 1.0))
        self.lf = float(max(lf, 1e-3))
        self.lr = float(max(lr, 1e-3))
        self.Cf = float(max(Cf, 1.0))
        self.Cr = float(max(Cr, 1.0))
        self.residual_scales = np.asarray(
            residual_scales if residual_scales is not None else [0.35, 0.10, 0.08, 0.25, 0.22, 0.20],
            dtype=float,
        ).reshape(-1)
        if self.residual_scales.size != 6:
            self.residual_scales = np.array([0.35, 0.10, 0.08, 0.25, 0.22, 0.20], dtype=float)

        self.residual_ewma_beta = float(np.clip(residual_ewma_beta, 0.0, 0.999))
        self.residual_cusum_drift = float(max(residual_cusum_drift, 0.0))
        self.residual_cusum_leak = float(np.clip(residual_cusum_leak, 0.0, 0.999))
        self.residual_threshold = float(max(residual_threshold, 1e-6))
        self.residual_cusum_threshold = float(max(residual_cusum_threshold, 1e-6))
        self.detect_hold_steps = int(max(detect_hold_steps, 1))
        self.release_hold_steps = int(max(release_hold_steps, 1))
        self.ax_eff_fault_threshold = float(np.clip(ax_eff_fault_threshold, 0.05, 1.5))
        self.delta_eff_fault_threshold = float(np.clip(delta_eff_fault_threshold, 0.05, 1.5))
        self.severe_eff_threshold = float(np.clip(severe_eff_threshold, 0.01, 1.0))
        self.eff_smooth_beta = float(np.clip(eff_smooth_beta, 0.0, 0.999))
        self.cmd_deadzone_delta = float(max(cmd_deadzone_delta, 1e-6))
        self.cmd_deadzone_ax = float(max(cmd_deadzone_ax, 1e-6))
        self.min_valid_delta_cmd = float(max(min_valid_delta_cmd, self.cmd_deadzone_delta))
        self.min_valid_ax_cmd = float(max(min_valid_ax_cmd, self.cmd_deadzone_ax))
        self.warmup_steps = int(max(warmup_steps, 0))
        self.states = [_VehicleFDIState() for _ in range(self.num_vehicles)]

    def reset(self) -> None:
        self.states = [_VehicleFDIState() for _ in range(self.num_vehicles)]

    def _predict_local_state(self, x_prev: np.ndarray, u_sent: np.ndarray) -> np.ndarray:
        s, e_y, e_psi, vx, v_y, r = np.asarray(x_prev, dtype=float).reshape(-1)
        delta, a_x = np.asarray(u_sent, dtype=float).reshape(-1)

        vx_safe = max(float(vx), 0.5)
        mass = self.mass
        Iz = self.Iz
        Cf = self.Cf
        Cr = self.Cr
        lf = self.lf
        lr = self.lr

        v_y_dot = (
            -(2.0 * Cf + 2.0 * Cr) / (mass * vx_safe) * v_y
            + (-vx_safe - (2.0 * Cf * lf - 2.0 * Cr * lr) / (mass * vx_safe)) * r
            + (2.0 * Cf / mass) * delta
        )
        r_dot = (
            -(2.0 * Cf * lf - 2.0 * Cr * lr) / (Iz * vx_safe) * v_y
            - (2.0 * Cf * lf ** 2 + 2.0 * Cr * lr ** 2) / (Iz * vx_safe) * r
            + (2.0 * Cf * lf / Iz) * delta
        )
        vx_dot = a_x + r * v_y
        e_y_dot = vx_safe * np.sin(e_psi) + v_y * np.cos(e_psi)
        e_psi_dot = r
        s_dot = max(vx_safe * np.cos(e_psi) - v_y * np.sin(e_psi), 0.0)

        x_pred = np.array(
            [
                s + self.dt * s_dot,
                e_y + self.dt * e_y_dot,
                e_psi + self.dt * e_psi_dot,
                vx + self.dt * vx_dot,
                v_y + self.dt * v_y_dot,
                r + self.dt * r_dot,
            ],
            dtype=float,
        )
        return x_pred

    def _estimate_effectiveness(
        self,
        x_prev: np.ndarray,
        x_now: np.ndarray,
        u_sent: np.ndarray,
        u_meas: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        x_prev = np.asarray(x_prev, dtype=float).reshape(-1)
        x_now = np.asarray(x_now, dtype=float).reshape(-1)
        u_sent = np.asarray(u_sent, dtype=float).reshape(-1)

        _, _, _, vx_prev, v_y_prev, r_prev = x_prev
        _, _, _, vx_now, v_y_now, r_now = x_now
        delta_cmd, ax_cmd = float(u_sent[0]), float(u_sent[1])
        vx_safe = max(float(vx_prev), 0.5)

        if u_meas is not None:
            u_meas = np.asarray(u_meas, dtype=float).reshape(-1)
            delta_meas = float(u_meas[0])
            ax_meas = float(u_meas[1])
            ax_valid = abs(ax_cmd) > self.min_valid_ax_cmd
            delta_valid = (abs(delta_cmd) > self.min_valid_delta_cmd) and (vx_safe > 0.8)
            ax_eff_raw = 1.0
            if ax_valid:
                ax_eff_raw = float(ax_meas / ax_cmd)
            delta_eff_raw = 1.0
            if delta_valid:
                delta_eff_raw = float(delta_meas / delta_cmd)
            return {
                "ax_eff_raw": float(np.clip(ax_eff_raw, 0.0, 1.5)),
                "delta_eff_raw": float(np.clip(delta_eff_raw, 0.0, 1.5)),
                "ax_valid": bool(ax_valid),
                "delta_valid": bool(delta_valid),
                "dvx": float(vx_now - vx_prev),
                "dry": float(r_now - r_prev),
                "dvy": float(v_y_now - v_y_prev),
                "measured_ratio_used": True,
            }

        ax_valid = abs(ax_cmd) > self.min_valid_ax_cmd
        ax_eff_raw = 1.0
        if ax_valid:
            vx_free = float(vx_prev + self.dt * r_prev * v_y_prev)
            denom = self.dt * ax_cmd
            if abs(denom) > 1e-8:
                ax_eff_raw = float((vx_now - vx_free) / denom)

        delta_valid = (abs(delta_cmd) > self.min_valid_delta_cmd) and (vx_safe > 0.8)
        delta_eff_raw = 1.0
        if delta_valid:
            Iz = self.Iz
            Cf = self.Cf
            Cr = self.Cr
            lf = self.lf
            lr = self.lr
            r_base = float(
                r_prev
                + self.dt
                * (
                    -(2.0 * Cf * lf - 2.0 * Cr * lr) / (Iz * vx_safe) * v_y_prev
                    - (2.0 * Cf * lf ** 2 + 2.0 * Cr * lr ** 2) / (Iz * vx_safe) * r_prev
                )
            )
            gain_delta = self.dt * (2.0 * Cf * lf / Iz) * delta_cmd
            if abs(gain_delta) > 1e-8:
                delta_eff_raw = float((r_now - r_base) / gain_delta)

        return {
            "ax_eff_raw": float(np.clip(ax_eff_raw, 0.0, 1.5)),
            "delta_eff_raw": float(np.clip(delta_eff_raw, 0.0, 1.5)),
            "ax_valid": bool(ax_valid),
            "delta_valid": bool(delta_valid),
            "dvx": float(vx_now - vx_prev),
            "dry": float(r_now - r_prev),
            "dvy": float(v_y_now - v_y_prev),
            "measured_ratio_used": False,
        }

    def update(
        self,
        *,
        k: int,
        local_states_now: np.ndarray,
        local_states_prev: np.ndarray,
        u_sent_prev: np.ndarray,
        u_meas_prev: Optional[np.ndarray] = None,
        comm_quality_global: float = 1.0,
    ) -> List[Dict[str, Any]]:
        local_states_now = np.asarray(local_states_now, dtype=float)
        local_states_prev = np.asarray(local_states_prev, dtype=float)
        u_sent_prev = np.asarray(u_sent_prev, dtype=float)
        if u_meas_prev is not None:
            u_meas_prev = np.asarray(u_meas_prev, dtype=float)
        comm_quality_global = float(np.clip(comm_quality_global, 0.0, 1.0))

        out: List[Dict[str, Any]] = []
        for v in range(self.num_vehicles):
            st = self.states[v]
            x_prev = local_states_prev[v, :]
            x_now = local_states_now[v, :]
            u_prev = u_sent_prev[v, :]
            u_prev_meas = None if u_meas_prev is None else u_meas_prev[v, :]
            x_pred = self._predict_local_state(x_prev, u_prev)
            resid = x_now - x_pred
            resid_norm = float(
                np.sqrt(np.sum((resid / np.maximum(self.residual_scales, 1e-6)) ** 2))
            )

            st.residual_ewma = float(
                self.residual_ewma_beta * st.residual_ewma
                + (1.0 - self.residual_ewma_beta) * resid_norm
            )
            st.residual_cusum = float(
                max(
                    0.0,
                    self.residual_cusum_leak * st.residual_cusum
                    + resid_norm
                    - self.residual_cusum_drift,
                )
            )

            eff = self._estimate_effectiveness(x_prev, x_now, u_prev, u_prev_meas)
            if eff["ax_valid"]:
                st.ax_eff_est = float(
                    self.eff_smooth_beta * st.ax_eff_est
                    + (1.0 - self.eff_smooth_beta) * eff["ax_eff_raw"]
                )
            else:
                st.ax_eff_est = float(0.985 * st.ax_eff_est + 0.015)
            if eff["delta_valid"]:
                st.delta_eff_est = float(
                    self.eff_smooth_beta * st.delta_eff_est
                    + (1.0 - self.eff_smooth_beta) * eff["delta_eff_raw"]
                )
            else:
                st.delta_eff_est = float(0.985 * st.delta_eff_est + 0.015)
            st.ax_eff_est = float(np.clip(st.ax_eff_est, 0.0, 1.5))
            st.delta_eff_est = float(np.clip(st.delta_eff_est, 0.0, 1.5))

            resid_alert = (
                st.residual_ewma >= self.residual_threshold
                or st.residual_cusum >= self.residual_cusum_threshold
            )
            ax_alert = bool(eff["ax_valid"]) and (st.ax_eff_est < self.ax_eff_fault_threshold)
            delta_alert = bool(eff["delta_valid"]) and (st.delta_eff_est < self.delta_eff_fault_threshold)
            detected = resid_alert or ax_alert or delta_alert
            if comm_quality_global < 0.22:
                detected = detected or (st.residual_ewma >= 0.75 * self.residual_threshold)
            if k < self.warmup_steps:
                detected = False

            if detected:
                st.detect_counter += 1
                st.release_counter = 0
            else:
                st.release_counter += 1
                st.detect_counter = max(0, st.detect_counter - 1)
                if st.release_counter >= self.release_hold_steps:
                    st.residual_cusum *= 0.5

            mode = "nominal"
            if st.detect_counter >= self.detect_hold_steps:
                ax_bad = bool(eff["ax_valid"]) and (st.ax_eff_est < self.ax_eff_fault_threshold)
                delta_bad = bool(eff["delta_valid"]) and (st.delta_eff_est < self.delta_eff_fault_threshold)
                severe = (
                    (bool(eff["ax_valid"]) and st.ax_eff_est < self.severe_eff_threshold)
                    or (bool(eff["delta_valid"]) and st.delta_eff_est < self.severe_eff_threshold)
                )
                if severe and ax_bad and delta_bad:
                    mode = "severe_dual_loss"
                elif ax_bad and delta_bad:
                    mode = "dual_degraded"
                elif ax_bad:
                    mode = "accel_degraded"
                elif delta_bad:
                    mode = "steer_degraded"
                else:
                    mode = "residual_only_alert"

            if st.release_counter >= self.release_hold_steps and not detected:
                mode = "nominal"

            conf_resid = max(0.0, (st.residual_ewma - self.residual_threshold) / max(self.residual_threshold, 1e-6))
            conf_ax = 0.0
            if eff["ax_valid"]:
                conf_ax = max(
                    0.0,
                    (self.ax_eff_fault_threshold - st.ax_eff_est)
                    / max(self.ax_eff_fault_threshold - self.severe_eff_threshold, 1e-6),
                )
            conf_delta = 0.0
            if eff["delta_valid"]:
                conf_delta = max(
                    0.0,
                    (self.delta_eff_fault_threshold - st.delta_eff_est)
                    / max(self.delta_eff_fault_threshold - self.severe_eff_threshold, 1e-6),
                )
            conf_eff = min(1.0, max(conf_ax, conf_delta))
            confidence = float(np.clip(0.30 * conf_resid + 0.90 * conf_eff, 0.0, 1.0))
            if mode == "nominal":
                confidence = 0.0

            st.mode = mode
            st.confidence = confidence
            out.append(
                {
                    "step": int(k),
                    "vehicle_index": int(v),
                    "residual": resid.tolist(),
                    "residual_norm": resid_norm,
                    "residual_ewma": float(st.residual_ewma),
                    "residual_cusum": float(st.residual_cusum),
                    "ax_eff_est": float(st.ax_eff_est),
                    "delta_eff_est": float(st.delta_eff_est),
                    "ax_valid": bool(eff["ax_valid"]),
                    "delta_valid": bool(eff["delta_valid"]),
                    "measured_ratio_used": bool(eff.get("measured_ratio_used", False)),
                    "detect_counter": int(st.detect_counter),
                    "release_counter": int(st.release_counter),
                    "detected": bool(detected),
                    "identified_mode": str(mode),
                    "confidence": float(confidence),
                    "comm_quality_global": float(comm_quality_global),
                }
            )
        return out

    @staticmethod
    def summarize(diag_hist: Sequence[Sequence[Dict[str, Any]]]) -> Dict[str, Any]:
        if len(diag_hist) == 0:
            return {
                "num_active_steps": 0,
                "num_identified_steps": 0,
                "dominant_modes": {},
                "mean_confidence": 0.0,
            }
        flat = [d for step in diag_hist for d in step]
        num_active = int(sum(1 for d in flat if bool(d.get("detected", False))))
        num_identified = int(sum(1 for d in flat if str(d.get("identified_mode", "nominal")) != "nominal"))
        mode_counts: Dict[str, int] = {}
        for d in flat:
            mode = str(d.get("identified_mode", "nominal"))
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        mean_conf = float(np.mean([float(d.get("confidence", 0.0)) for d in flat])) if len(flat) > 0 else 0.0
        return {
            "num_active_steps": num_active,
            "num_identified_steps": num_identified,
            "dominant_modes": mode_counts,
            "mean_confidence": mean_conf,
        }
