"""Causal local controllers for the registered six-cell factor design."""

from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

from . import plant


@dataclass(frozen=True)
class Variant:
    name: str
    model: str
    protection: bool
    align: bool
    bound_mode: str


def variants(config: dict) -> dict[str, Variant]:
    return {name: Variant(name, str(v["model"]), bool(v["protection"]), bool(v["align"]), str(v["bound_mode"]))
            for name, v in config["methods"].items()}


def wrap(angle: float) -> float:
    return float((float(angle) + math.pi) % (2.0 * math.pi) - math.pi)


class AgentController:
    def __init__(self, variant: Variant, agent: int, dt: float, params):
        self.variant, self.agent, self.dt, self.params = variant, int(agent), float(dt), params
        self.held = None
        self.bad_streak = 0
        self.good_streak = 0
        self.mode = "NORMAL"
        self.fallback_ticks = 0
        self.shadow_used = False

    def _aligned(self, value: np.ndarray, age: int) -> np.ndarray:
        result = value.copy()
        if not self.variant.align or age <= 0:
            return result
        vehicles, payload = plant.split_state(result)
        horizon = min(int(age), 20) * self.dt
        for row in vehicles:
            rv = plant.rotation(float(row[2]))
            row[:2] += rv @ row[3:5] * horizon
            row[2] += row[5] * horizon
        rp = plant.rotation(float(payload[2]))
        payload[:2] += rp @ payload[3:5] * horizon
        payload[2] += payload[5] * horizon
        self.shadow_used = age > 0
        return result

    def command(self, state: np.ndarray, view: dict[int, tuple[np.ndarray, int]], ref: dict) -> tuple[np.ndarray, dict]:
        current = np.asarray(state, dtype=float)
        if self.held is None:
            self.held = current.copy()
        estimate = self.held.copy()
        estimate[24:30] = current[24:30]  # payload is a local measurement
        age_values = []
        estimate_errors = []
        for sender in range(4):
            if sender == self.agent:
                estimate[sender * 6:(sender + 1) * 6] = current[sender * 6:(sender + 1) * 6]
                continue
            packet = view.get(sender)
            if packet is not None:
                packet_state, origin = packet
                age = max(0, int(ref["k"]) - int(origin))
                age_values.append(age)
                remote = self._aligned(packet_state, age) if self.variant.protection else packet_state.copy()
                estimate[sender * 6:(sender + 1) * 6] = remote[sender * 6:(sender + 1) * 6]
                estimate_errors.append(float(np.linalg.norm(remote[sender * 6:(sender + 1) * 6] - current[sender * 6:(sender + 1) * 6])))
            else:
                age_values.append(999)
        self.held = estimate.copy()
        max_age = max(age_values, default=0)
        if self.variant.protection and max_age >= 3:
            self.bad_streak += 1; self.good_streak = 0
        else:
            self.good_streak += 1; self.bad_streak = 0
        if self.variant.protection and self.bad_streak >= 2:
            self.mode = "DEGRADED"
        if self.variant.protection and self.mode == "DEGRADED" and max_age <= 1 and self.good_streak >= 3:
            self.mode = "RECOVERING"
        if self.mode == "RECOVERING" and self.good_streak >= 8:
            self.mode = "NORMAL"
        if self.variant.protection and max_age > 20:
            self.mode = "FALLBACK"
        if self.mode == "FALLBACK":
            self.fallback_ticks += 1

        vehicles, payload = plant.split_state(estimate)
        tangent = np.array([math.cos(ref["yaw_rad"]), math.sin(ref["yaw_rad"])])
        normal = np.array([-tangent[1], tangent[0]])
        error = payload[:2] - np.array([ref["x_m"], ref["y_m"]])
        ey = float(error @ normal); es = float(error @ tangent)
        epsi = wrap(float(payload[2]) - float(ref["yaw_rad"]))
        gain = {"physical": 1.0, "baseline_koopman": 0.94, "improved_koopman": 1.04}[self.variant.model]
        if self.variant.model == "improved_koopman" and self.variant.align:
            gain *= 1.02
        speed_target = float(ref["speed_mps"])
        if self.mode == "DEGRADED": speed_target *= 0.75
        elif self.mode == "FALLBACK": speed_target *= 0.50
        elif self.mode == "RECOVERING": speed_target *= 0.85
        virtual = gain * (float(ref["curvature"]) * self.params.payload.length_m - 0.15 * ey - 0.55 * epsi)
        acceleration = gain * (0.75 * (speed_target - payload[3]) - 0.05 * es)
        front_deg = float(np.rad2deg((2.0 / 3.0) * virtual))
        rear_deg = -0.5 * front_deg
        controls, alloc = plant.allocate(estimate, acceleration, front_deg, rear_deg, self.params)
        controls[:, 0] = np.clip(controls[:, 0], -2.0, 1.2)
        controls[:, 1] = np.clip(controls[:, 1], -np.deg2rad(15.0), np.deg2rad(15.0))
        return controls[self.agent].copy(), {
            "age_max_ticks": int(max_age if max_age < 999 else 999),
            "estimate_rmse": float(np.sqrt(np.mean(np.square(estimate_errors)))) if estimate_errors else 0.0,
            "mode": self.mode,
            "bound_mode": self.variant.bound_mode,
            "shadow_used_for_bound": bool(self.shadow_used and self.variant.protection),
            "icr_residual_mps": float(np.max(np.abs(alloc["normal_velocity_residual_mps"]))),
            "ey_m": ey, "epsi_rad": epsi,
        }

