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
    member: str = "none"


SCENARIOS = tuple(f"D{index}" for index in range(12))
DIRECTIONAL = frozenset({"D2", "D3", "D4", "D5", "D6", "D8", "D10", "D11"})
NATURAL_EVENT_SCENARIOS = frozenset({"D2", "D3", "D4", "D5", "D6", "D8", "D10", "D11"})


def direction_sign(direction: str) -> float:
    if direction == "left":
        return 1.0
    if direction == "right":
        return -1.0
    if direction == "none":
        return 0.0
    raise ValueError(f"unknown direction: {direction}")


def scenario_specs(names: list[str] | tuple[str, ...]) -> list[ScenarioSpec]:
    durations = {
        "D0": 6.0,
        "D1": 8.0,
        "D3": 8.0,
        "D4": 8.0,
        "D5": 9.0,
        "D6": 7.0,
        "D7": 6.0,
        "D8": 6.0,
        "D9": 6.0,
        "D10": 8.0,
        "D11": 10.0,
    }
    specs: list[ScenarioSpec] = []
    for name in names:
        if name not in SCENARIOS:
            raise ValueError(f"unknown predict scenario: {name}")
        identities = (
            (("none", "A"), ("none", "B"))
            if name == "D9"
            else tuple(
                (direction, "none")
                for direction in (("left", "right") if name in DIRECTIONAL else ("none",))
            )
        )
        for direction, member in identities:
            specs.append(
                ScenarioSpec(
                    scenario=name,
                    direction=direction,
                    duration_s=None if name == "D2" else durations[name],
                    distance_target_m=100.0 if name == "D2" else None,
                    natural_event_source=name in NATURAL_EVENT_SCENARIOS,
                    member=member,
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
    if name == "D3":
        if 1.0 <= time_s < 2.0:
            # Half-cosine entry has zero slope at both ends.
            weight = 0.5 - 0.5 * np.cos(np.pi * (time_s - 1.0))
        elif 2.0 <= time_s < 6.0:
            weight = 1.0
        elif 6.0 <= time_s < 7.0:
            weight = 0.5 + 0.5 * np.cos(np.pi * (time_s - 6.0))
        else:
            weight = 0.0
        angle = sign * 4.0 * weight
        return ScenarioCommand(0.0, float(angle), float(-0.5 * angle), "STEADY_CURVE")
    if name == "D4":
        angle = (
            sign * 4.0 * np.sin(2.0 * np.pi * (time_s - 1.0) / 4.0)
            if 1.0 <= time_s < 5.0
            else 0.0
        )
        return ScenarioCommand(0.0, float(angle), float(-0.5 * angle), "SINGLE_LANE_CHANGE")
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
    if name == "D7":
        if 1.0 <= time_s < 3.0:
            multiplier = 1.0
            phase = "INTERNAL_LONGITUDINAL_PRIMARY"
        elif 3.0 <= time_s < 5.0:
            multiplier = -1.0
            phase = "INTERNAL_LONGITUDINAL_REVERSE"
        else:
            multiplier = 0.0
            phase = "IDLE"
        offsets = tuple(multiplier * value for value in (0.20, 0.20, -0.20, -0.20))
        return ScenarioCommand(0.0, 0.0, 0.0, phase, offsets, ZERO4)
    if name == "D8":
        if 1.0 <= time_s < 3.0:
            multiplier = sign
            phase = "INTERNAL_LATERAL_PRIMARY"
        elif 3.0 <= time_s < 5.0:
            multiplier = -sign
            phase = "INTERNAL_LATERAL_REVERSE"
        else:
            multiplier = 0.0
            phase = "IDLE"
        # FL, FR, RL, RR: left-side vehicles oppose right-side vehicles.
        offsets = tuple(multiplier * value for value in (0.8, -0.8, 0.8, -0.8))
        return ScenarioCommand(0.0, 0.0, 0.0, phase, ZERO4, offsets)
    if name == "D9":
        if spec.member not in {"A", "B"}:
            raise ValueError(f"D9 requires member A or B, found {spec.member}")
        if 1.0 <= time_s < 3.0:
            multiplier = 1.0
            phase = f"DIAGONAL_{spec.member}_PRIMARY"
        elif 3.0 <= time_s < 5.0:
            multiplier = -1.0
            phase = f"DIAGONAL_{spec.member}_REVERSE"
        else:
            multiplier = 0.0
            phase = "IDLE"
        diagonal = (1.0, -1.0, -1.0, 1.0)
        if spec.member == "A":
            acceleration_offsets = tuple(multiplier * 0.15 * value for value in diagonal)
            steering_offsets = ZERO4
        else:
            acceleration_offsets = ZERO4
            steering_offsets = tuple(multiplier * 0.6 * value for value in diagonal)
        return ScenarioCommand(
            0.0,
            0.0,
            0.0,
            phase,
            acceleration_offsets,
            steering_offsets,
        )
    if name == "D10":
        phase = 2.0 * np.pi * (0.35 * time_s + 0.10 * time_s**2)
        envelope = np.sin(np.pi * np.clip(time_s / 8.0, 0.0, 1.0)) ** 2
        angle = sign * 8.0 * envelope * np.sin(phase)
        acceleration = 0.12 * np.sin(2.0 * np.pi * 0.4 * time_s)
        return ScenarioCommand(float(acceleration), float(angle), float(-0.5 * angle), "BOUNDARY_CHIRP")
    if name == "D11":
        if time_s < 1.0:
            envelope = 0.5 - 0.5 * np.cos(np.pi * time_s)
        elif time_s <= 9.0:
            envelope = 1.0
        elif time_s < 10.0:
            envelope = 0.5 + 0.5 * np.cos(np.pi * (time_s - 9.0))
        else:
            envelope = 0.0
        acceleration = envelope * 0.15 * np.sin(2.0 * np.pi * 0.25 * time_s)
        angle = sign * envelope * 4.0 * np.sin(2.0 * np.pi * 0.18 * time_s)
        return ScenarioCommand(
            float(acceleration),
            float(angle),
            float(-0.5 * angle),
            "MIXED_GENERALIZATION",
        )
    raise ValueError(name)


def build_predict_pilot_identities(protocol: dict) -> list[dict]:
    """Expand the frozen N4 pilot identities without running any trajectory."""

    scenario_config = protocol["scenarios"]
    order = tuple(scenario_config["order"])
    if order != SCENARIOS:
        raise ValueError(f"scenario order drift: {order}")
    families = tuple(protocol["n4_parameter_families"])
    plants = tuple(protocol["plants"])
    rows: list[dict] = []
    trajectory_id = 0
    for scenario in order:
        specs = scenario_specs([scenario])
        for family in families:
            base_family_id = f"N4_{scenario}_{family['parameter_family']}"
            for spec in specs:
                for plant in plants:
                    rows.append(
                        {
                            "trajectory_id": trajectory_id,
                            "base_family_id": base_family_id,
                            "scenario": scenario,
                            "parameter_family": str(family["parameter_family"]),
                            "seed": int(family["seed"]),
                            "direction": spec.direction,
                            "member": spec.member,
                            "plant": str(plant["plant"]),
                            "law": str(plant["law"]),
                            "actuator_mode": "A3",
                            "duration_s": spec.duration_s,
                            "distance_target_m": spec.distance_target_m,
                            "dry_run_only": True,
                        }
                    )
                    trajectory_id += 1
    return rows


def audit_predict_pilot_identities(rows: list[dict], protocol: dict) -> dict:
    identity_fields = (
        "scenario",
        "parameter_family",
        "seed",
        "direction",
        "member",
        "plant",
        "actuator_mode",
    )
    identities = [tuple(row[field] for field in identity_fields) for row in rows]
    families = {row["base_family_id"] for row in rows}
    scenarios = {row["scenario"] for row in rows}
    expected = protocol["n3"]
    passed = (
        len(rows) == int(expected["expected_saved_trajectory_count"])
        and len(identities) == len(set(identities))
        and len(families) == int(expected["expected_base_family_count"])
        and len(scenarios) == int(expected["expected_scenario_count"])
    )
    return {
        "passed": passed,
        "trajectory_count": len(rows),
        "unique_identity_count": len(set(identities)),
        "base_family_count": len(families),
        "scenario_count": len(scenarios),
        "raw_files_written": 0,
    }


def build_auto_smoke_identities(protocol: dict) -> list[dict]:
    """Select the six predeclared load types without choosing easy outcomes."""

    all_rows = build_predict_pilot_identities(protocol)
    selectors = (
        ("D0", "P0", "none", "none", "V1-ES"),
        ("D2", "P0", "left", "none", "R3-ES"),
        ("D4", "P1", "right", "none", "V1-ES"),
        ("D5", "P1", "left", "none", "R3-ES"),
        ("D7", "P2", "none", "none", "V1-ES"),
        ("D9", "P2", "none", "B", "R3-ES"),
    )
    selected = []
    for scenario, family, direction, member, plant in selectors:
        match = [
            row
            for row in all_rows
            if (
                row["scenario"],
                row["parameter_family"],
                row["direction"],
                row["member"],
                row["plant"],
            )
            == (scenario, family, direction, member, plant)
        ]
        if len(match) != 1:
            raise ValueError(f"smoke selector is not unique: {selectors}")
        selected.append({**match[0], "smoke_id": len(selected)})
    return selected


def build_future_trajectory_identities(protocol: dict) -> list[dict]:
    """Expand train/validation/development; confirm is deliberately absent."""

    rows: list[dict] = []
    trajectory_id = 0
    contract = protocol["future_split_contract"]
    for split in ("train", "validation", "development"):
        split_config = contract[split]
        seed = int(split_config["seed_start"])
        per_scenario = int(split_config["base_family_count_per_scenario"])
        for scenario in protocol["scenarios"]["order"]:
            specs = scenario_specs([scenario])
            for family_index in range(per_scenario):
                base_family_id = f"{split}_{scenario}_{seed}"
                for spec in specs:
                    for plant in protocol["plants"]:
                        rows.append(
                            {
                                "trajectory_id": trajectory_id,
                                "base_family_id": base_family_id,
                                "split": split,
                                "scenario": scenario,
                                "parameter_family": f"{split}_{family_index:02d}",
                                "seed": seed,
                                "direction": spec.direction,
                                "member": spec.member,
                                "plant": str(plant["plant"]),
                                "law": str(plant["law"]),
                                "actuator_mode": "A3",
                                "duration_s": spec.duration_s,
                                "distance_target_m": spec.distance_target_m,
                            }
                        )
                        trajectory_id += 1
                seed += 1
        if seed - 1 != int(split_config["seed_end"]):
            raise ValueError(f"{split} seed block expansion drift")
    return rows


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
