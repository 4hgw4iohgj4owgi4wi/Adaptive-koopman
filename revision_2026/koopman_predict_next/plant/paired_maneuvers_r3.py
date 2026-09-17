from __future__ import annotations

from dataclasses import dataclass

import numpy as np


ZERO4 = (0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class ManeuverCommand:
    acceleration_mps2: float
    virtual_front_deg: float
    virtual_rear_deg: float
    phase: str
    vehicle_accel_offset_mps2: tuple[float, float, float, float] = ZERO4
    vehicle_steer_offset_deg: tuple[float, float, float, float] = ZERO4


def staged_100m_command(distance_m, time_since_30_s, v_d=None, s_d=None):
    if distance_m < 30:
        return ManeuverCommand(0.25, 0.0, 0.0, "ACCEL")
    if time_since_30_s < 5:
        return ManeuverCommand(0.0, 2.25, -1.125, "STEP_POS")
    if time_since_30_s < 10:
        return ManeuverCommand(0.0, -2.25, 1.125, "STEP_NEG")
    if v_d is None or s_d is None:
        raise ValueError("deceleration phase requires measured v_d and s_d")
    acceleration = (0.7**2 - v_d**2) / (2 * max(100 - s_d, 1e-12))
    if not (-1.4 <= acceleration < 0):
        raise ValueError("100m deceleration contract infeasible")
    return ManeuverCommand(acceleration, 0.0, 0.0, "DECEL")


def _zero_mean(values: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    array = np.asarray(values, dtype=float)
    array -= np.mean(array)
    return tuple(float(item) for item in array)


def _directional_command(name: str, t: float, seed: int) -> ManeuverCommand:
    active = 0.5 <= t < 1.0
    scale = 1.0 + 0.02 * (int(seed) % 5)
    acceleration = 0.05 * scale if active else 0.0
    steering = 0.25 * scale if active else 0.0
    if "longitudinal" in name:
        accel, steer = (acceleration, acceleration, -acceleration, -acceleration), ZERO4
    elif "lateral" in name:
        lateral_steering = 1.25 * steering
        accel, steer = ZERO4, (lateral_steering, -lateral_steering, lateral_steering, -lateral_steering)
    elif "diagonal_1" in name:
        accel, steer = (
            (acceleration, -acceleration, -acceleration, acceleration),
            (steering, -steering, -steering, steering),
        )
    elif "diagonal_2" in name:
        accel, steer = (
            (-acceleration, acceleration, acceleration, -acceleration),
            (-steering, steering, steering, -steering),
        )
    else:
        raise ValueError(f"unknown directional connector maneuver: {name}")
    return ManeuverCommand(0.0, 0.0, 0.0, name.upper(), _zero_mean(accel), _zero_mean(steer))


def scenario_command(name, t, seed=0):
    sign = -1 if name.endswith("right") else 1
    if name.startswith("straight"):
        return ManeuverCommand(0.0, 0.0, 0.0, "STRAIGHT")
    if name.startswith("single_lane_change"):
        angle = sign * 4 * np.sin(np.pi * np.clip((t - 1) / 4, 0, 1))
        return ManeuverCommand(0.0, angle, -0.5 * angle, "LANE_CHANGE")
    if name.startswith("hairpin"):
        if 1.0 <= t < 2.0:
            angle = sign * 8.0 * (t - 1.0)
        elif 2.0 <= t < 6.0:
            angle = sign * 8.0
        elif 6.0 <= t < 7.0:
            angle = sign * 8.0 * (7.0 - t)
        else:
            angle = 0.0
        return ManeuverCommand(0.0, angle, -0.5 * angle, "HAIRPIN")
    if name.startswith("line_curve_transition"):
        if 1.0 <= t < 2.0:
            angle = sign * 4.0 * (t - 1.0)
        elif 2.0 <= t < 4.0:
            angle = sign * 4.0
        elif 4.0 <= t < 5.0:
            angle = sign * 4.0 * (5.0 - t)
        else:
            angle = 0.0
        return ManeuverCommand(0.0, angle, -0.5 * angle, "TRANSITION")
    if name.startswith("connector_"):
        return _directional_command(name, t, seed)
    raise ValueError(name)
