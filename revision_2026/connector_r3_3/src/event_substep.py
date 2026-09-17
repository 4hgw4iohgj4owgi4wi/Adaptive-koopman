from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

import numpy as np

from connector_adapter import DELTA_S_M, ScalarConnector
from four_vehicle_common import ModelParams, connector_diagnostics, connector_event_surfaces, connector_kinematics, rk4_step as vehicle_rk4_step


@dataclass(frozen=True)
class EventSubstepConfig:
    outer_step_s: float = 0.002
    probe_step_s: float = 0.0005
    zone_nodes: int = 8
    min_step_s: float = 0.000002
    closure_tol_s: float = 1.0e-12
    event_time_tol_s: float = 0.000001
    root_time_tol_s: float = 1.0e-9
    surface_tol_m: float = 1.0e-8
    detector_release_tol_m: float = 1.0e-9
    simultaneous_tol_s: float = 0.000001
    max_substeps_per_outer: int = 256
    smoothing_width_m: float = DELTA_S_M
    reduced_mass_kg: float = 300.0


def _scalar_rhs(state: np.ndarray, connector: ScalarConnector, mass_kg: float) -> np.ndarray:
    force = float(connector.evaluate(float(state[0]), float(state[1]))["force_n"])
    return np.asarray([float(state[1]), -force / mass_kg], dtype=float)


def scalar_rk4_step(state: np.ndarray, dt: float, connector: ScalarConnector, mass_kg: float) -> np.ndarray:
    k1 = _scalar_rhs(state, connector, mass_kg)
    k2 = _scalar_rhs(state + 0.5 * dt * k1, connector, mass_kg)
    k3 = _scalar_rhs(state + 0.5 * dt * k2, connector, mass_kg)
    k4 = _scalar_rhs(state + dt * k3, connector, mass_kg)
    return state + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0


def scalar_two_half_rk4(state: np.ndarray, dt: float, connector: ScalarConnector, mass_kg: float):
    midpoint = scalar_rk4_step(state, 0.5 * dt, connector, mass_kg)
    endpoint = scalar_rk4_step(midpoint, 0.5 * dt, connector, mass_kg)
    return midpoint, endpoint


def _crossed(a: float, b: float, release_tol: float) -> bool:
    if abs(a) <= release_tol:
        return False
    return a * b < 0.0 or abs(b) <= release_tol


def _scalar_bisect(state: np.ndarray, dt: float, surface_m: float, connector: ScalarConnector, config: EventSubstepConfig):
    left, right = 0.0, dt
    left_value = float(state[0] - surface_m)
    while right - left > min(config.event_time_tol_s, config.root_time_tol_s):
        middle = 0.5 * (left + right)
        middle_state = scalar_rk4_step(state, middle, connector, config.reduced_mass_kg)
        middle_value = float(middle_state[0] - surface_m)
        if left_value * middle_value <= 0.0:
            right = middle
        else:
            left, left_value = middle, middle_value
    event_time = 0.5 * (left + right)
    return event_time, scalar_rk4_step(state, event_time, connector, config.reduced_mass_kg)


def _next_scalar_step(state: np.ndarray, remaining: float, config: EventSubstepConfig) -> tuple[float, bool]:
    q, velocity = float(state[0]), float(state[1])
    speed = abs(velocity)
    step = min(config.probe_step_s, remaining)
    predicted = q + velocity * step
    in_or_crosses_zone = (
        -config.surface_tol_m <= q <= config.smoothing_width_m + config.surface_tol_m
        or min(q, predicted) <= 0.0 <= max(q, predicted)
        or min(q, predicted) <= config.smoothing_width_m <= max(q, predicted)
    )
    unresolved = False
    if in_or_crosses_zone and speed > 0.0:
        zone_step = config.smoothing_width_m / (config.zone_nodes * speed)
        if zone_step < config.min_step_s:
            unresolved = True
        else:
            step = min(step, zone_step)
    if abs(velocity) > 1e-14:
        for surface in (0.0, config.smoothing_width_m):
            eta = (surface - q) / velocity
            if config.min_step_s <= eta <= step:
                step = eta
    residue = remaining - step
    if config.closure_tol_s < residue < config.min_step_s:
        step = remaining
    return min(step, remaining), unresolved


def integrate(
    law: str,
    q0_m: float,
    v0_mps: float,
    duration_s: float,
    mode: str,
    config: EventSubstepConfig | None = None,
    fixed_step_s: float | None = None,
    keep_trace: bool = True,
) -> dict:
    """Scalar F2/ES/reference integration with explicit closure accounting."""
    config = config or EventSubstepConfig()
    if mode not in {"F2", "ES", "REF"}:
        raise ValueError(f"unsupported mode: {mode}")
    connector = ScalarConnector(law)
    state = np.asarray([q0_m, v0_mps], dtype=float)
    initial = state.copy()
    t = 0.0
    outer_index = 0
    impulse = damping_work = 0.0
    peak_force = float(connector.evaluate(q0_m, v0_mps)["force_n"])
    min_dt = float("inf")
    accepted_steps = max_outer_substeps = zone_steps = 0
    closure_count = 0
    closure_total = 0.0
    events: list[dict] = []
    status = "PASS"
    trace = {"time_s": [0.0], "penetration_m": [q0_m], "normal_speed_mps": [v0_mps], "force_n": [peak_force], "accepted_dt_s": [0.0]}
    while t < duration_s - config.closure_tol_s:
        outer_end = min(duration_s, (outer_index + 1) * config.outer_step_s)
        if outer_end <= t + config.closure_tol_s:
            outer_index += 1
            continue
        outer_substeps = 0
        while t < outer_end:
            remaining = outer_end - t
            if remaining <= config.closure_tol_s:
                closure_count += 1
                closure_total += remaining
                t = outer_end
                break
            if mode == "ES" and remaining < config.min_step_s:
                status = "UNRESOLVED_CLOSURE_STEP"
                break
            if mode == "ES":
                dt, unresolved = _next_scalar_step(state, remaining, config)
                if unresolved:
                    status = "UNRESOLVED_EVENT_SPEED"
                    break
            elif mode == "REF":
                dt = min(float(fixed_step_s or config.min_step_s), remaining)
            else:
                dt = remaining
            if not np.isfinite(dt) or dt <= 0.0:
                status = "INVALID_STEP"
                break
            start = state.copy()
            if mode == "ES":
                midpoint, endpoint = scalar_two_half_rk4(start, dt, connector, config.reduced_mass_kg)
            else:
                midpoint = scalar_rk4_step(start, 0.5 * dt, connector, config.reduced_mass_kg)
                endpoint = scalar_rk4_step(start, dt, connector, config.reduced_mass_kg)
            midpoint_diag = connector.evaluate(float(midpoint[0]), float(midpoint[1]))
            endpoint_diag = connector.evaluate(float(endpoint[0]), float(endpoint[1]))
            impulse += float(midpoint_diag["force_n"]) * dt
            damping_work += float(midpoint_diag["damping_power_w"]) * dt
            peak_force = max(peak_force, float(midpoint_diag["force_n"]), float(endpoint_diag["force_n"]))
            for surface, name in ((0.0, "contact"), (config.smoothing_width_m, "smoothing")):
                if _crossed(float(start[0] - surface), float(endpoint[0] - surface), config.detector_release_tol_m):
                    local_time, event_state = _scalar_bisect(start, dt, surface, connector, config)
                    absolute_time = t + local_time
                    event = {"time_s": absolute_time, "surface": name, "surface_m": surface, "direction": "load" if event_state[1] >= 0.0 else "unload", "residual_m": abs(float(event_state[0] - surface))}
                    if not any(abs(event["time_s"] - prior["time_s"]) <= config.root_time_tol_s and event["surface"] == prior["surface"] for prior in events):
                        events.append(event)
            if min(float(start[0]), float(endpoint[0])) < config.smoothing_width_m and max(float(start[0]), float(endpoint[0])) > 0.0:
                zone_steps += 1
            state = endpoint
            t += dt
            min_dt = min(min_dt, dt)
            accepted_steps += 1
            outer_substeps += 1
            if keep_trace:
                trace["time_s"].append(t); trace["penetration_m"].append(float(state[0])); trace["normal_speed_mps"].append(float(state[1])); trace["force_n"].append(float(endpoint_diag["force_n"])); trace["accepted_dt_s"].append(dt)
            if bool(endpoint_diag["ultimate_exceeded"]):
                status = "STOP_ULTIMATE_FORCE"
                break
            if not np.all(np.isfinite(state)):
                status = "NONFINITE"
                break
            if mode == "ES" and outer_substeps > config.max_substeps_per_outer:
                status = "SUBSTEP_CAP"
                break
        max_outer_substeps = max(max_outer_substeps, outer_substeps)
        if status != "PASS":
            break
        outer_index += 1
    if duration_s - t <= config.closure_tol_s:
        closure_total += max(duration_s - t, 0.0)
        t = duration_s
    final_diag = connector.evaluate(float(state[0]), float(state[1]))
    initial_ke = 0.5 * config.reduced_mass_kg * float(initial[1]) ** 2
    final_mechanical = 0.5 * config.reduced_mass_kg * float(state[1]) ** 2 + float(final_diag["elastic_energy_j"])
    result = {
        "law": law, "mode": mode, "status": status,
        "duration_requested_s": duration_s, "duration_actual_s": t,
        "initial_penetration_m": q0_m, "initial_speed_mps": v0_mps,
        "terminal_penetration_m": float(state[0]), "terminal_speed_mps": float(state[1]),
        "terminal_force_n": float(final_diag["force_n"]), "peak_force_n": peak_force,
        "impulse_ns": impulse, "damping_work_j": damping_work,
        "initial_kinetic_energy_j": initial_ke, "terminal_mechanical_energy_j": final_mechanical,
        "energy_balance_residual_j": initial_ke - final_mechanical - damping_work,
        "events": events, "accepted_steps": accepted_steps,
        "max_substeps_per_outer": max_outer_substeps,
        "min_accepted_dt_s": 0.0 if min_dt == float("inf") else min_dt,
        "smoothing_zone_accepted_steps": zone_steps,
        "closure_residual_count": closure_count, "closure_residual_total_s": closure_total,
        "config": asdict(config),
    }
    if keep_trace:
        result["trace"] = trace
    return result


def _vehicle_propagate(state: np.ndarray, controls: np.ndarray, dt: float, params: ModelParams, law: str) -> np.ndarray:
    midpoint = vehicle_rk4_step(state, controls, 0.5 * dt, params, law)
    return vehicle_rk4_step(midpoint, controls, 0.5 * dt, params, law)


def _vector_crossings(start: np.ndarray, middle: np.ndarray, endpoint: np.ndarray, config: EventSubstepConfig):
    crossings = []
    for connector in range(start.shape[0]):
        for surface_index, name in ((0, "contact"), (1, "smoothing")):
            for left_fraction, right_fraction, left, right in ((0.0, 0.5, start[connector, surface_index], middle[connector, surface_index]), (0.5, 1.0, middle[connector, surface_index], endpoint[connector, surface_index])):
                if _crossed(float(left), float(right), config.detector_release_tol_m):
                    crossings.append((connector, surface_index, name, left_fraction, right_fraction))
    return crossings


def _bisect_vehicle_event(state: np.ndarray, controls: np.ndarray, dt: float, params: ModelParams, law: str, connector: int, surface_index: int, left_fraction: float, right_fraction: float, config: EventSubstepConfig):
    left = left_fraction * dt
    right = right_fraction * dt
    left_state = _vehicle_propagate(state, controls, left, params, law) if left > 0.0 else state
    left_value = float(connector_event_surfaces(left_state, params)[connector, surface_index])
    while right - left > min(config.event_time_tol_s, config.root_time_tol_s):
        middle = 0.5 * (left + right)
        middle_state = _vehicle_propagate(state, controls, middle, params, law)
        middle_value = float(connector_event_surfaces(middle_state, params)[connector, surface_index])
        if left_value * middle_value <= 0.0:
            right = middle
        else:
            left, left_value = middle, middle_value
    event_time = 0.5 * (left + right)
    event_state = _vehicle_propagate(state, controls, event_time, params, law)
    return event_time, event_state


def _vehicle_step_size(state: np.ndarray, remaining: float, params: ModelParams, config: EventSubstepConfig, max_step_s: float) -> tuple[float, bool]:
    kinematics = connector_kinematics(state, params)
    gaps = kinematics["signed_gap_m"]
    speeds = kinematics["normal_speed_mps"]
    step = min(max_step_s, remaining)
    unresolved = False
    predicted = gaps + speeds * step
    for gap, predicted_gap, speed in zip(gaps, predicted, speeds):
        in_or_crosses = (-config.surface_tol_m <= gap <= config.smoothing_width_m + config.surface_tol_m or min(gap, predicted_gap) <= 0.0 <= max(gap, predicted_gap) or min(gap, predicted_gap) <= config.smoothing_width_m <= max(gap, predicted_gap))
        if in_or_crosses and abs(speed) > 0.0:
            zone_step = config.smoothing_width_m / (config.zone_nodes * abs(speed))
            if zone_step < config.min_step_s:
                unresolved = True
            else:
                step = min(step, zone_step)
    residue = remaining - step
    if config.closure_tol_s < residue < config.min_step_s:
        step = remaining
    return min(step, remaining), unresolved


def _empty_step_audit() -> dict:
    return {
        "force_impulse_world_ns": np.zeros((4, 2)), "force_peak_n": np.zeros(4),
        "damping_work_j": np.zeros(4), "payload_moment_peak_nm": 0.0,
        "vehicle_moment_peak_nm": np.zeros(4), "internal_force_peak_n": 0.0,
        "action_reaction_max_n": 0.0, "internal_null_max_n": 0.0,
        "zone_steps_per_connector": np.zeros(4, dtype=int), "events": [],
        "accepted_steps": 0, "min_physical_dt_s": float("inf"), "max_physical_dt_s": 0.0,
        "closure_residual_count": 0, "closure_residual_total_s": 0.0,
        "status": "PASS", "duration_actual_s": 0.0,
    }


def _accumulate_diag(audit: dict, diag: dict, dt: float) -> None:
    audit["force_impulse_world_ns"] += diag["force_payload_world_n"] * dt
    audit["force_peak_n"] = np.maximum(audit["force_peak_n"], diag["force_norm_n"])
    audit["damping_work_j"] += diag["damping_power_w"] * dt
    audit["payload_moment_peak_nm"] = max(audit["payload_moment_peak_nm"], abs(float(diag["payload_moment_total_nm"])))
    audit["vehicle_moment_peak_nm"] = np.maximum(audit["vehicle_moment_peak_nm"], np.abs(diag["vehicle_moment_nm"]))
    audit["internal_force_peak_n"] = max(audit["internal_force_peak_n"], float(diag["internal_force_norm_n"]))
    audit["action_reaction_max_n"] = max(audit["action_reaction_max_n"], float(np.max(np.abs(diag["action_reaction_residual_n"]))))
    audit["internal_null_max_n"] = max(audit["internal_null_max_n"], float(np.linalg.norm(diag["internal_null_residual"])))


def advance_outer_step(state: np.ndarray, controls: np.ndarray, law: str, params: ModelParams, duration_s: float, mode: str, config: EventSubstepConfig | None = None, max_step_s: float | None = None) -> tuple[np.ndarray, dict]:
    """Advance one external interval and truly split at the earliest event."""
    config = config or EventSubstepConfig()
    if mode not in {"F2", "ES"}:
        raise ValueError("vehicle mode must be F2 or ES")
    audit = _empty_step_audit()
    state = np.asarray(state, dtype=float).copy()
    t = 0.0
    max_step = float(max_step_s or config.probe_step_s)
    while t < duration_s:
        remaining = duration_s - t
        if remaining <= config.closure_tol_s:
            audit["closure_residual_count"] += 1
            audit["closure_residual_total_s"] += remaining
            t = duration_s
            break
        if mode == "ES" and remaining < config.min_step_s:
            audit["status"] = "UNRESOLVED_CLOSURE_STEP"
            break
        if mode == "F2":
            dt = remaining
        else:
            dt, unresolved = _vehicle_step_size(state, remaining, params, config, max_step)
            if unresolved:
                audit["status"] = "UNRESOLVED_EVENT_SPEED"
                break
        start = state.copy()
        event_group = []
        if mode == "ES":
            middle_probe = _vehicle_propagate(start, controls, 0.5 * dt, params, law)
            endpoint_probe = _vehicle_propagate(start, controls, dt, params, law)
            crossings = _vector_crossings(connector_event_surfaces(start, params), connector_event_surfaces(middle_probe, params), connector_event_surfaces(endpoint_probe, params), config)
            roots = []
            for connector, surface_index, name, left_fraction, right_fraction in crossings:
                event_dt, event_state = _bisect_vehicle_event(start, controls, dt, params, law, connector, surface_index, left_fraction, right_fraction, config)
                roots.append((event_dt, connector, surface_index, name, event_state))
            if roots:
                roots.sort(key=lambda value: value[0])
                earliest = roots[0][0]
                if config.closure_tol_s < earliest < config.min_step_s:
                    audit["status"] = "UNRESOLVED_EVENT_SPEED"
                    break
                if earliest > config.closure_tol_s:
                    dt = earliest
                event_group = [root for root in roots if abs(root[0] - earliest) <= config.simultaneous_tol_s]
        if mode == "F2":
            midpoint = vehicle_rk4_step(start, controls, 0.5 * dt, params, law)
            endpoint = vehicle_rk4_step(start, controls, dt, params, law)
        else:
            midpoint = vehicle_rk4_step(start, controls, 0.5 * dt, params, law)
            endpoint = vehicle_rk4_step(midpoint, controls, 0.5 * dt, params, law)
        midpoint_diag = connector_diagnostics(midpoint, params, law)
        endpoint_diag = connector_diagnostics(endpoint, params, law)
        _accumulate_diag(audit, midpoint_diag, dt)
        audit["force_peak_n"] = np.maximum(audit["force_peak_n"], endpoint_diag["force_norm_n"])
        start_gaps = connector_kinematics(start, params)["signed_gap_m"]
        endpoint_gaps = connector_kinematics(endpoint, params)["signed_gap_m"]
        for connector in range(4):
            if min(start_gaps[connector], endpoint_gaps[connector]) < config.smoothing_width_m and max(start_gaps[connector], endpoint_gaps[connector]) > 0.0:
                audit["zone_steps_per_connector"][connector] += 1
        absolute_base = t
        for event_dt, connector, surface_index, name, _ in event_group:
            event_surface = 0.0 if surface_index == 0 else config.smoothing_width_m
            event_gap = connector_kinematics(endpoint, params)["signed_gap_m"][connector]
            event_speed = connector_kinematics(endpoint, params)["normal_speed_mps"][connector]
            event = {"time_offset_s": absolute_base + dt, "connector_id": int(connector), "surface": name, "direction": "load" if event_speed >= 0.0 else "unload", "residual_m": abs(float(event_gap - event_surface))}
            if not any(abs(event["time_offset_s"] - prior["time_offset_s"]) <= config.root_time_tol_s and event["connector_id"] == prior["connector_id"] and event["surface"] == prior["surface"] for prior in audit["events"]):
                audit["events"].append(event)
        state = endpoint
        t += dt
        audit["accepted_steps"] += 1
        audit["min_physical_dt_s"] = min(audit["min_physical_dt_s"], dt)
        audit["max_physical_dt_s"] = max(audit["max_physical_dt_s"], dt)
        if np.any(endpoint_diag["ultimate_force_exceeded"]):
            audit["status"] = "STOP_ULTIMATE_FORCE"
            break
        if not np.all(np.isfinite(state)):
            audit["status"] = "NONFINITE"
            break
        if mode == "ES" and audit["accepted_steps"] > config.max_substeps_per_outer:
            audit["status"] = "SUBSTEP_CAP"
            break
    if duration_s - t <= config.closure_tol_s:
        audit["closure_residual_total_s"] += max(duration_s - t, 0.0)
        t = duration_s
    audit["duration_actual_s"] = t
    if audit["min_physical_dt_s"] == float("inf"):
        audit["min_physical_dt_s"] = 0.0
    audit["endpoint_diagnostics"] = connector_diagnostics(state, params, law)
    return state, audit


def detect_callable_events(value_fn: Callable[[float], np.ndarray], t0_s: float, t1_s: float, surfaces_m: tuple[float, ...] = (0.0, DELTA_S_M), probe_step_s: float = 0.0005, time_tol_s: float = 0.000001, surface_tol_m: float = 1.0e-8, simultaneous_tol_s: float = 0.000001) -> list[dict]:
    """Analytic detector retained for N1 load/unload/double-crossing regression."""
    count = max(1, int(np.ceil((t1_s - t0_s) / probe_step_s)))
    grid = np.linspace(t0_s, t1_s, count + 1)
    raw = []
    def bisect(index: int, surface: float, left: float, right: float) -> float:
        fl = float(value_fn(left)[index] - surface)
        while right - left > min(time_tol_s, 1e-9):
            middle = 0.5 * (left + right); fm = float(value_fn(middle)[index] - surface)
            if fl * fm <= 0.0: right = middle
            else: left, fl = middle, fm
        return 0.5 * (left + right)
    def scan(index: int, surface: float, left: float, right: float, depth: int = 0):
        middle = 0.5 * (left + right)
        samples = [(left, middle), (middle, right)]
        found = False
        for a, b in samples:
            fa, fb = float(value_fn(a)[index] - surface), float(value_fn(b)[index] - surface)
            if abs(fa) <= surface_tol_m: raw.append({"time_s": a, "connector": index, "surface_m": surface}); found = True
            if fa * fb < 0.0 or abs(fb) <= surface_tol_m: raw.append({"time_s": bisect(index, surface, a, b), "connector": index, "surface_m": surface}); found = True
        if not found and depth < 4 and right - left > 2.0 * time_tol_s:
            quarter, three_quarter = 0.5 * (left + middle), 0.5 * (middle + right)
            values = [float(value_fn(x)[index] - surface) for x in (left, quarter, middle, three_quarter, right)]
            if min(values) <= 0.0 <= max(values):
                scan(index, surface, left, middle, depth + 1); scan(index, surface, middle, right, depth + 1)
    connector_count = int(np.asarray(value_fn(t0_s)).size)
    for index in range(connector_count):
        for surface in surfaces_m:
            for left, right in zip(grid[:-1], grid[1:]): scan(index, surface, float(left), float(right))
    unique = []
    for event in sorted(raw, key=lambda item: (item["time_s"], item["connector"], item["surface_m"])):
        if not any(abs(event["time_s"] - prior["time_s"]) <= time_tol_s and event["connector"] == prior["connector"] and event["surface_m"] == prior["surface_m"] for prior in unique): unique.append(event)
    groups = []
    for event in unique:
        if not groups or event["time_s"] - groups[-1]["time_s"] > simultaneous_tol_s: groups.append({"time_s": event["time_s"], "events": [event]})
        else: groups[-1]["events"].append(event)
    return groups

