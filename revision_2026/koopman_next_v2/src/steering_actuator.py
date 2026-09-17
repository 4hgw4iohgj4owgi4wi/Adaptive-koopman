from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SteeringActuatorConfig:
    """Simulation contract for the four steering actuators.

    These values are traceable internal reference assumptions.  They are not
    hardware-calibrated parameters.
    """

    tau_delta_s: float = 0.12
    rate_max_radps: float = 1.2
    angle_max_rad: float = float(np.deg2rad(15.0))

    def validate(self) -> None:
        values = np.asarray(
            [self.tau_delta_s, self.rate_max_radps, self.angle_max_rad], dtype=float
        )
        if not np.all(np.isfinite(values)) or np.any(values <= 0.0):
            raise ValueError(f"invalid steering actuator configuration: {self}")


def step_actuator(
    delta_req_rad: np.ndarray,
    delta_act_rad: np.ndarray,
    step_s: float,
    config: SteeringActuatorConfig,
) -> dict[str, np.ndarray]:
    """Advance one exact first-order step, then apply rate and angle limits."""

    config.validate()
    request = np.asarray(delta_req_rad, dtype=float)
    actual = np.asarray(delta_act_rad, dtype=float)
    if request.shape != actual.shape:
        raise ValueError(f"request/actual shape mismatch: {request.shape} != {actual.shape}")
    if not np.all(np.isfinite(request)) or not np.all(np.isfinite(actual)):
        raise ValueError("non-finite steering request or state")
    step_s = float(step_s)
    if not np.isfinite(step_s) or step_s <= 0.0:
        raise ValueError(f"invalid actuator step: {step_s}")

    decay = float(np.exp(-step_s / config.tau_delta_s))
    free_next = request + decay * (actual - request)
    free_increment = free_next - actual
    maximum_increment = config.rate_max_radps * step_s
    rate_limited_increment = np.clip(
        free_increment, -maximum_increment, maximum_increment
    )
    before_angle_clip = actual + rate_limited_increment
    actual_next = np.clip(
        before_angle_clip, -config.angle_max_rad, config.angle_max_rad
    )
    rate = (actual_next - actual) / step_s
    return {
        "delta_act_next_rad": actual_next,
        "delta_rate_radps": rate,
        "free_next_rad": free_next,
        "rate_limited_mask": np.abs(free_increment - rate_limited_increment) > 1.0e-15,
        "angle_limited_mask": np.abs(before_angle_clip - actual_next) > 1.0e-15,
    }
