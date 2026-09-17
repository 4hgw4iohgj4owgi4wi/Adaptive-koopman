from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class _VehicleRole:
    front: float
    rear: float
    left: float
    right: float
    side_sign: float


class PhaseRoleSchedulerTF14:
    """Phase- and role-aware supervisory trim for four-corner transport.

    This layer is intentionally small: MPC remains the primary controller, while
    the scheduler adds bounded trims according to path phase, vehicle corner
    role, FDI state and communication quality.
    """

    def __init__(
        self,
        *,
        num_vehicles: int,
        dt: float,
        umin: Sequence[float],
        umax: Sequence[float],
        cfg: Dict[str, Any] | None = None,
    ) -> None:
        self.num_vehicles = int(num_vehicles)
        self.dt = float(max(dt, 1e-4))
        self.umin = np.asarray(umin, dtype=float).reshape(-1)
        self.umax = np.asarray(umax, dtype=float).reshape(-1)
        self.cfg = dict(cfg or {})

    def _get(self, key: str, default: float) -> float:
        return float(self.cfg.get(key, default))

    @staticmethod
    def _role(v: int) -> _VehicleRole:
        # Vehicle order used by the notebooks: 0 front-left, 1 front-right,
        # 2 rear-left, 3 rear-right.
        front = 1.0 if v in (0, 1) else 0.0
        rear = 1.0 - front
        left = 1.0 if v in (0, 2) else 0.0
        right = 1.0 - left
        side_sign = 1.0 if left > 0.5 else -1.0
        return _VehicleRole(front=front, rear=rear, left=left, right=right, side_sign=side_sign)

    def phase_name(self, curvature: float, curvature_prev: float, curvature_next: float) -> str:
        curv = abs(float(curvature))
        dcurv_in = abs(float(curvature) - float(curvature_prev))
        dcurv_out = abs(float(curvature_next) - float(curvature))
        th = self._get("phase_curv_threshold", 0.006)
        core_th = self._get("phase_core_curv_threshold", 0.015)
        dth = self._get("phase_dcurv_threshold", 0.0015)
        if curv < th:
            return "straight"
        if curv >= core_th:
            return "turn_core"
        if dcurv_in >= dth and dcurv_out < dcurv_in:
            return "turn_entry"
        if dcurv_out >= dth:
            return "turn_exit"
        return "turn_transition"

    def adjust(
        self,
        *,
        k: int,
        vehicle_index: int,
        x_raw: np.ndarray,
        ref_step: np.ndarray,
        curvature: float,
        curvature_prev: float,
        curvature_next: float,
        delta_cmd: float,
        ax_cmd: float,
        diagnoses: Sequence[Dict[str, Any]],
        comm_quality_global: float,
    ) -> Tuple[float, float, Dict[str, Any]]:
        v = int(vehicle_index)
        role = self._role(v)
        x = np.asarray(x_raw, dtype=float).reshape(-1)
        ref = np.asarray(ref_step, dtype=float).reshape(-1)
        phase = self.phase_name(curvature, curvature_prev, curvature_next)

        e_s = float(ref[0] - x[0]) if ref.size > 0 else 0.0
        e_y = float(x[1]) if x.size > 1 else 0.0
        e_psi = float(x[2]) if x.size > 2 else 0.0
        vx = float(x[3]) if x.size > 3 else 0.0
        r = float(x[5]) if x.size > 5 else 0.0
        vx_ref = float(ref[3]) if ref.size > 3 else vx

        curv = float(curvature)
        abs_curv = abs(curv)
        turn_sign = 1.0 if curv >= 0.0 else -1.0
        q_comm = float(np.clip(comm_quality_global, 0.0, 1.0))
        diag_map = {int(d.get("vehicle_index", -1)): d for d in diagnoses}
        this_diag = diag_map.get(v, {})
        active_faults = [
            int(d.get("vehicle_index", -1))
            for d in diagnoses
            if str(d.get("identified_mode", "nominal")) not in {"nominal", "residual_only_alert"}
            and float(d.get("confidence", 0.0)) >= self._get("fault_conf_threshold", 0.12)
        ]
        is_fault_vehicle = v in active_faults
        is_support_vehicle = (len(active_faults) > 0) and (not is_fault_vehicle)

        front_delta = self._get("front_delta_trim", 0.075) * role.front
        rear_yaw = self._get("rear_yaw_damp", 0.020) * role.rear
        side_outer = -turn_sign * role.side_sign
        outer_ax = self._get("outer_ax_trim", 0.035) * side_outer * min(abs_curv / 0.020, 1.5)

        phase_gain = {
            "straight": self._get("straight_gain", 0.25),
            "turn_entry": self._get("entry_gain", 1.00),
            "turn_core": self._get("core_gain", 0.90),
            "turn_exit": self._get("exit_gain", 0.75),
            "turn_transition": self._get("transition_gain", 0.65),
        }.get(phase, 0.5)

        lat_gain = self._get("lat_error_delta_gain", 0.018)
        if role.rear > 0.5:
            lat_gain = self._get("rear_lat_error_delta_gain", lat_gain)
        else:
            lat_gain = self._get("front_lat_error_delta_gain", lat_gain)
        heading_gain = self._get("heading_error_delta_gain", 0.045)
        if role.rear > 0.5:
            heading_gain = self._get("rear_heading_error_delta_gain", heading_gain)
        else:
            heading_gain = self._get("front_heading_error_delta_gain", heading_gain)

        delta_trim = 0.0
        delta_trim += phase_gain * front_delta * curv
        delta_trim += -lat_gain * phase_gain * e_y
        delta_trim += -heading_gain * phase_gain * e_psi
        delta_trim += -rear_yaw * r

        ax_trim = 0.0
        progress_gain = self._get("progress_ax_gain", 0.060)
        if role.rear > 0.5:
            progress_gain = self._get("rear_progress_ax_gain", progress_gain)
        ax_trim += progress_gain * np.clip(e_s, -1.5, 1.8)
        ax_trim += self._get("speed_ax_gain", 0.080) * np.clip(vx_ref - vx, -1.2, 1.2)
        ax_trim += outer_ax
        if phase in {"turn_entry", "turn_core"}:
            ax_trim -= self._get("curv_slowdown_gain", 0.030) * min(abs_curv / 0.020, 1.8) * max(vx - vx_ref, 0.0)

        profile = phase
        if q_comm < self._get("comm_quality_soft_threshold", 0.55):
            comm_damp = self._get("comm_delta_damp", 0.92)
            delta_cmd *= comm_damp
            ax_trim *= self._get("comm_ax_trim_scale", 0.85)
            profile = f"{profile}+comm_safe"

        if is_fault_vehicle:
            delta_trim *= self._get("fault_vehicle_trim_scale", 0.65)
            ax_trim *= self._get("fault_vehicle_trim_scale", 0.65)
            profile = f"{profile}+fault_limited"
        elif is_support_vehicle:
            ax_trim += self._get("support_ax_boost", 0.055)
            delta_trim += self._get("support_delta_boost", 0.006) * turn_sign * side_outer
            profile = f"{profile}+support"

        delta_clip = self._get("delta_trim_clip", 0.035)
        ax_clip = self._get("ax_trim_clip", 0.18)
        delta_trim = float(np.clip(delta_trim, -delta_clip, delta_clip))
        ax_trim = float(np.clip(ax_trim, -ax_clip, ax_clip))

        delta_out = float(np.clip(delta_cmd + delta_trim, self.umin[0], self.umax[0]))
        ax_out = float(np.clip(ax_cmd + ax_trim, self.umin[1], self.umax[1]))
        diag = {
            "step": int(k),
            "vehicle_index": v,
            "phase": phase,
            "profile": profile,
            "curvature": curv,
            "comm_quality_global": q_comm,
            "delta_trim": delta_trim,
            "ax_trim": ax_trim,
            "active_faults": active_faults,
            "this_mode": str(this_diag.get("identified_mode", "nominal")),
            "this_confidence": float(this_diag.get("confidence", 0.0)),
        }
        return delta_out, ax_out, diag

    @staticmethod
    def summarize(diag_hist: Sequence[Sequence[Dict[str, Any]]]) -> Dict[str, Any]:
        flat = [d for step in diag_hist for d in step]
        if not flat:
            return {"num_steps": 0, "phase_counts": {}, "mean_abs_delta_trim": 0.0, "mean_abs_ax_trim": 0.0}
        phase_counts: Dict[str, int] = {}
        for d in flat:
            phase = str(d.get("phase", "unknown"))
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
        return {
            "num_steps": len(flat),
            "phase_counts": phase_counts,
            "mean_abs_delta_trim": float(np.mean([abs(float(d.get("delta_trim", 0.0))) for d in flat])),
            "mean_abs_ax_trim": float(np.mean([abs(float(d.get("ax_trim", 0.0))) for d in flat])),
            "max_abs_delta_trim": float(np.max([abs(float(d.get("delta_trim", 0.0))) for d in flat])),
            "max_abs_ax_trim": float(np.max([abs(float(d.get("ax_trim", 0.0))) for d in flat])),
        }
