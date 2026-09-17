from __future__ import annotations

from dataclasses import dataclass

import numpy as np


ZERO4 = (0.0, 0.0, 0.0, 0.0)


@dataclass(frozen=True)
class ScenarioCommand:
    acceleration_mps2: float
    virtual_front_deg: float
    virtual_rear_deg: float
    phase: str
    vehicle_accel_offset_mps2: tuple[float, float, float, float] = ZERO4
    vehicle_steer_offset_deg: tuple[float, float, float, float] = ZERO4


@dataclass(frozen=True)
class ScenarioSpec:
    scenario: str
    direction: str
    duration_s: float | None
    distance_target_m: float | None
    natural_event_source: bool


SCENARIOS = ("D0", "D1", "D2", "D5", "D6", "D10")
DIRECTIONAL = frozenset({"D2", "D5", "D6", "D10"})
NATURAL_EVENT_SCENARIOS = frozenset({"D2", "D5", "D6"})


def direction_sign(direction: str) -> float:
    if direction == "left":
        return 1.0
    if direction == "right":
        return -1.0
    if direction == "none":
        return 0.0
    raise ValueError(f"unknown direction: {direction}")


def scenario_specs(names: list[str] | tuple[str, ...]) -> list[ScenarioSpec]:
    durations = {"D0": 6.0, "D1": 8.0, "D5": 9.0, "D6": 7.0, "D10": 8.0}
    specs: list[ScenarioSpec] = []
    for name in names:
        if name not in SCENARIOS:
            raise ValueError(f"unknown K2 scenario: {name}")
        directions = ("left", "right") if name in DIRECTIONAL else ("none",)
        for direction in directions:
            specs.append(
                ScenarioSpec(
                    scenario=name,
                    direction=direction,
                    duration_s=None if name == "D2" else durations[name],
                    distance_target_m=100.0 if name == "D2" else None,
                    natural_event_source=name in NATURAL_EVENT_SCENARIOS,
                )
            )
    return specs


def d2_command(
    direction: str,
    time_s: float,
    distance_m: float,
    time_at_30_s: float | None,
    deceleration_state: tuple[float, float] | None,
) -> ScenarioCommand:
    """Frozen R04 request contract used by the v2 actuator-isolation study."""

    sign = direction_sign(direction)
    if distance_m < 30.0:
        return ScenarioCommand(0.25, 0.0, 0.0, "ACCEL_TO_30M")
    since = 0.0 if time_at_30_s is None else time_s - time_at_30_s
    if since < 5.0:
        return ScenarioCommand(0.0, sign * 5.0, -sign * 2.5, "STEP_PRIMARY")
    if since < 10.0:
        return ScenarioCommand(0.0, -sign * 5.0, sign * 2.5, "STEP_REVERSE")
    if deceleration_state is None:
        raise RuntimeError("D2 deceleration state is not frozen")
    speed_at_decel, distance_at_decel = deceleration_state
    acceleration = (0.7**2 - speed_at_decel**2) / (
        2.0 * max(100.0 - distance_at_decel, 1e-12)
    )
    if not (-1.4 <= acceleration < 0.0):
        raise ValueError(f"D2 deceleration infeasible: {acceleration}")
    return ScenarioCommand(acceleration, 0.0, 0.0, "DECEL")


def command_for(
    spec: ScenarioSpec,
    time_s: float,
    distance_m: float,
    time_at_30_s: float | None,
    deceleration_state: tuple[float, float] | None,
) -> ScenarioCommand:
    sign = direction_sign(spec.direction)
    name = spec.scenario
    if name == "D0":
        return ScenarioCommand(0.0, 0.0, 0.0, "STEADY")
    if name == "D1":
        if time_s < 2.0:
            return ScenarioCommand(0.35, 0.0, 0.0, "ACCEL")
        if time_s < 5.0:
            return ScenarioCommand(0.0, 0.0, 0.0, "CRUISE")
        if time_s < 7.0:
            return ScenarioCommand(-0.50, 0.0, 0.0, "BRAKE")
        return ScenarioCommand(0.0, 0.0, 0.0, "SETTLE")
    if name == "D2":
        return d2_command(
            spec.direction,
            time_s,
            distance_m,
            time_at_30_s,
            deceleration_state,
        )
    if name == "D5":
        if 1.0 <= time_s < 2.0:
            angle = sign * 8.0 * (time_s - 1.0)
        elif 2.0 <= time_s < 6.0:
            angle = sign * 8.0
        elif 6.0 <= time_s < 7.0:
            angle = sign * 8.0 * (7.0 - time_s)
        else:
            angle = 0.0
        return ScenarioCommand(0.0, angle, -0.5 * angle, "HAIRPIN")
    if name == "D6":
        if 1.0 <= time_s < 2.0:
            angle = sign * 5.0 * (time_s - 1.0)
        elif 2.0 <= time_s < 4.0:
            angle = sign * 5.0
        elif 4.0 <= time_s < 5.0:
            angle = sign * 5.0 * (5.0 - time_s)
        else:
            angle = 0.0
        return ScenarioCommand(0.0, angle, -0.5 * angle, "LINE_CURVE_TRANSITION")
    if name == "D10":
        phase = 2.0 * np.pi * (0.35 * time_s + 0.10 * time_s**2)
        envelope = np.sin(np.pi * np.clip(time_s / 8.0, 0.0, 1.0)) ** 2
        angle = sign * 8.0 * envelope * np.sin(phase)
        acceleration = 0.12 * np.sin(2.0 * np.pi * 0.4 * time_s)
        return ScenarioCommand(float(acceleration), float(angle), float(-0.5 * angle), "BOUNDARY_CHIRP")
    raise ValueError(name)


def build_base_families(protocol: dict) -> list[dict]:
    config = protocol["k2"]
    train_start = int(protocol["seed_blocks"]["K2_PILOT_TRAIN"][0])
    validation_start = int(protocol["seed_blocks"]["K2_PILOT_VALIDATION"][0])
    rows: list[dict] = []
    for scenario_index, scenario in enumerate(config["scenarios"]):
        for split, start, count in (
            ("train", train_start, int(config["train_base_seeds_per_scenario"])),
            ("validation", validation_start, int(config["validation_base_seeds_per_scenario"])),
        ):
            for member_index in range(count):
                seed = start + 10 * scenario_index + member_index
                rows.append(
                    {
                        "base_family_id": f"K2_{split}_{scenario}_{seed}",
                        "scenario": scenario,
                        "split": split,
                        "seed": seed,
                    }
                )
    return rows
