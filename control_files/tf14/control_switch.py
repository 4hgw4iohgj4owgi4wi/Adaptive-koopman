from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


@dataclass
class _SwitchMemory:
    global_mode: str = "nominal_koopman_mpc"
    current_target_mode: str = "nominal_koopman_mpc"
    mode_hold_counter: int = 0


class ReconfigurableFTCControllerTF14:
    """Automatic switched FTC layer driven by online diagnosis.

    Modes:
    - nominal_koopman_mpc
    - reconfigured_ftc_mpc
    - safe_degraded_consensus
    """

    def __init__(
        self,
        *,
        num_vehicles: int,
        umin: Sequence[float],
        umax: Sequence[float],
        switch_dwell_steps: int = 6,
        activation_confidence: float = 0.28,
        safe_confidence: float = 0.70,
        inverse_comp_clip_delta: float = 1.35,
        inverse_comp_clip_ax: float = 1.35,
        redistribution_gain: float = 1.00,
        safe_global_delta_scale: float = 0.80,
        safe_global_ax_scale: float = 0.75,
    ) -> None:
        self.num_vehicles = int(num_vehicles)
        self.umin = np.asarray(umin, dtype=float).reshape(-1)
        self.umax = np.asarray(umax, dtype=float).reshape(-1)
        self.switch_dwell_steps = int(max(switch_dwell_steps, 1))
        self.activation_confidence = float(np.clip(activation_confidence, 0.0, 1.0))
        self.safe_confidence = float(np.clip(safe_confidence, 0.0, 1.0))
        self.inverse_comp_clip_delta = float(max(inverse_comp_clip_delta, 1.0))
        self.inverse_comp_clip_ax = float(max(inverse_comp_clip_ax, 1.0))
        self.redistribution_gain = float(max(redistribution_gain, 0.0))
        self.safe_global_delta_scale = float(np.clip(safe_global_delta_scale, 0.05, 1.0))
        self.safe_global_ax_scale = float(np.clip(safe_global_ax_scale, 0.05, 1.0))
        self.mem = _SwitchMemory()

    def reset(self) -> None:
        self.mem = _SwitchMemory()

    def _decide_target_mode(
        self,
        diagnoses: Sequence[Dict[str, Any]],
        comm_quality_global: float,
    ) -> str:
        if len(diagnoses) == 0:
            return "nominal_koopman_mpc"
        severe = any(
            str(d.get("identified_mode", "")) == "severe_dual_loss"
            and float(d.get("confidence", 0.0)) >= self.safe_confidence
            for d in diagnoses
        )
        if severe or comm_quality_global < 0.18:
            return "safe_degraded_consensus"

        active = any(
            str(d.get("identified_mode", "nominal")) in {
                "dual_degraded",
                "accel_degraded",
                "steer_degraded",
                "severe_dual_loss",
            }
            and float(d.get("confidence", 0.0)) >= self.activation_confidence
            for d in diagnoses
        )
        if active:
            return "reconfigured_ftc_mpc"
        return "nominal_koopman_mpc"

    def _update_mode(self, diagnoses: Sequence[Dict[str, Any]], comm_quality_global: float) -> str:
        target = self._decide_target_mode(diagnoses, comm_quality_global)
        if target == self.mem.current_target_mode:
            self.mem.mode_hold_counter += 1
        else:
            self.mem.current_target_mode = target
            self.mem.mode_hold_counter = 1

        if (
            self.mem.current_target_mode != self.mem.global_mode
            and self.mem.mode_hold_counter >= self.switch_dwell_steps
        ):
            self.mem.global_mode = self.mem.current_target_mode
        elif self.mem.global_mode == "safe_degraded_consensus" and target == "reconfigured_ftc_mpc":
            self.mem.global_mode = "reconfigured_ftc_mpc"
        elif self.mem.global_mode == "reconfigured_ftc_mpc" and target == "nominal_koopman_mpc":
            if self.mem.mode_hold_counter >= self.switch_dwell_steps:
                self.mem.global_mode = "nominal_koopman_mpc"
        return self.mem.global_mode

    def apply(
        self,
        *,
        k: int,
        planned_u_stack: np.ndarray,
        diagnoses: Sequence[Dict[str, Any]],
        comm_quality_global: float,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        u_out = np.asarray(planned_u_stack, dtype=float).copy()
        global_mode = self._update_mode(diagnoses, float(comm_quality_global))
        diag_map = {int(d.get("vehicle_index", -1)): d for d in diagnoses}
        redistributed_total = np.zeros(2, dtype=float)

        if global_mode in {"reconfigured_ftc_mpc", "safe_degraded_consensus"}:
            for v in range(self.num_vehicles):
                d = diag_map.get(v, None)
                if d is None:
                    continue
                mode = str(d.get("identified_mode", "nominal"))
                conf = float(d.get("confidence", 0.0))
                if conf < self.activation_confidence:
                    continue

                ax_eff = float(np.clip(d.get("ax_eff_est", 1.0), 0.10, 1.5))
                delta_eff = float(np.clip(d.get("delta_eff_est", 1.0), 0.10, 1.5))
                u_nom = u_out[v, :].copy()
                u_send = u_nom.copy()

                if mode in {"steer_degraded", "dual_degraded", "severe_dual_loss"}:
                    gain_inv = min(1.0 / max(delta_eff, 0.15), self.inverse_comp_clip_delta)
                    u_send[0] = np.clip(u_nom[0] * gain_inv, self.umin[0], self.umax[0])
                if mode in {"accel_degraded", "dual_degraded", "severe_dual_loss"}:
                    gain_inv = min(1.0 / max(ax_eff, 0.15), self.inverse_comp_clip_ax)
                    u_send[1] = np.clip(u_nom[1] * gain_inv, self.umin[1], self.umax[1])

                predicted_fault_output = np.array(
                    [delta_eff * u_send[0], ax_eff * u_send[1]],
                    dtype=float,
                )
                predicted_deficit = u_nom - predicted_fault_output
                u_out[v, :] = u_send

                if global_mode != "nominal_koopman_mpc":
                    supporters = [vv for vv in range(self.num_vehicles) if vv != v]
                    if len(supporters) > 0:
                        comp = (self.redistribution_gain * predicted_deficit) / float(len(supporters))
                        if global_mode == "safe_degraded_consensus":
                            comp *= 1.25
                        for vv in supporters:
                            u_out[vv, 0] += comp[0]
                            u_out[vv, 1] += comp[1]
                        redistributed_total += predicted_deficit

        if global_mode == "safe_degraded_consensus":
            u_out[:, 0] *= self.safe_global_delta_scale
            u_out[:, 1] *= self.safe_global_ax_scale

        u_out[:, 0] = np.clip(u_out[:, 0], self.umin[0], self.umax[0])
        u_out[:, 1] = np.clip(u_out[:, 1], self.umin[1], self.umax[1])
        switch_diag = {
            "step": int(k),
            "global_mode": str(global_mode),
            "target_mode": str(self.mem.current_target_mode),
            "mode_hold_counter": int(self.mem.mode_hold_counter),
            "comm_quality_global": float(comm_quality_global),
            "redistributed_total_delta": float(redistributed_total[0]),
            "redistributed_total_ax": float(redistributed_total[1]),
            "active_vehicle_modes": {
                int(v): str(diag_map[v].get("identified_mode", "nominal"))
                for v in sorted(diag_map.keys())
                if str(diag_map[v].get("identified_mode", "nominal")) != "nominal"
            },
        }
        return u_out, switch_diag

    @staticmethod
    def summarize(switch_hist: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        if len(switch_hist) == 0:
            return {"mode_counts": {}, "num_switches": 0}
        mode_counts: Dict[str, int] = {}
        num_switches = 0
        prev_mode = str(switch_hist[0].get("global_mode", "nominal_koopman_mpc"))
        for item in switch_hist:
            mode = str(item.get("global_mode", "nominal_koopman_mpc"))
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
            if mode != prev_mode:
                num_switches += 1
                prev_mode = mode
        return {"mode_counts": mode_counts, "num_switches": int(num_switches)}
