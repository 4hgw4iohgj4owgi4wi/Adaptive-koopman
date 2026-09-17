from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

import numpy as np

from connector_adapter import DELTA_S_M, ScalarConnector


@dataclass(frozen=True)
class EventSubstepConfig:
    outer_step_s: float = 0.002
    probe_step_s: float = 0.0005
    zone_nodes: int = 8
    min_step_s: float = 0.000002
    event_time_tol_s: float = 0.000001
    surface_tol_m: float = 1.0e-8
    detector_release_tol_m: float = 1.0e-9
    max_substeps_per_outer: int = 256
    smoothing_width_m: float = DELTA_S_M
    reduced_mass_kg: float = 300.0


def _rhs(state: np.ndarray, connector: ScalarConnector, mass_kg: float) -> np.ndarray:
    q, v = float(state[0]), float(state[1])
    force = float(connector.evaluate(q, v)["force_n"])
    return np.asarray([v, -force / mass_kg], dtype=float)


def rk4_step(state: np.ndarray, dt: float, connector: ScalarConnector, mass_kg: float) -> np.ndarray:
    k1 = _rhs(state, connector, mass_kg)
    k2 = _rhs(state + 0.5 * dt * k1, connector, mass_kg)
    k3 = _rhs(state + 0.5 * dt * k2, connector, mass_kg)
    k4 = _rhs(state + dt * k3, connector, mass_kg)
    return state + dt * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0


def two_half_rk4(state: np.ndarray, dt: float, connector: ScalarConnector, mass_kg: float):
    midpoint = rk4_step(state, 0.5 * dt, connector, mass_kg)
    endpoint = rk4_step(midpoint, 0.5 * dt, connector, mass_kg)
    return midpoint, endpoint


def _crossed(a: float, b: float, tol: float) -> bool:
    if abs(a) <= tol and abs(b) <= tol:
        return False
    return (a < -tol and b >= -tol) or (a > tol and b <= tol)


def _bisect_dynamic_event(
    state: np.ndarray,
    dt: float,
    surface_m: float,
    connector: ScalarConnector,
    config: EventSubstepConfig,
) -> tuple[float, np.ndarray]:
    left_t = 0.0
    right_t = dt
    left_q = float(state[0] - surface_m)
    right_state = rk4_step(state, right_t, connector, config.reduced_mass_kg)
    right_q = float(right_state[0] - surface_m)
    if abs(left_q) <= config.surface_tol_m:
        return 0.0, state.copy()
    target_time_tol = min(config.event_time_tol_s, 1.0e-9)
    while right_t - left_t > target_time_tol:
        mid_t = 0.5 * (left_t + right_t)
        mid_state = rk4_step(state, mid_t, connector, config.reduced_mass_kg)
        mid_q = float(mid_state[0] - surface_m)
        if left_q * mid_q <= 0.0:
            right_t, right_state, right_q = mid_t, mid_state, mid_q
        else:
            left_t, left_q = mid_t, mid_q
    event_t = 0.5 * (left_t + right_t)
    return event_t, rk4_step(state, event_t, connector, config.reduced_mass_kg)


def _next_step_size(state: np.ndarray, remaining: float, config: EventSubstepConfig) -> tuple[float, bool]:
    q, speed = float(state[0]), abs(float(state[1]))
    step = min(config.probe_step_s, remaining)
    unresolved = False
    predicted = q + float(state[1]) * step
    in_or_crosses_zone = (
        -config.surface_tol_m <= q <= config.smoothing_width_m + config.surface_tol_m
        or min(q, predicted) <= config.smoothing_width_m <= max(q, predicted)
        or min(q, predicted) <= 0.0 <= max(q, predicted)
    )
    if in_or_crosses_zone and speed > 0.0:
        zone_step = config.smoothing_width_m / (config.zone_nodes * max(speed, 1.0e-12))
        if zone_step < config.min_step_s:
            unresolved = True
        else:
            step = min(step, zone_step)
    v = float(state[1])
    if abs(v) > 1.0e-14:
        for surface in (0.0, config.smoothing_width_m):
            eta = (surface - q) / v
            if config.min_step_s <= eta <= step:
                step = eta
    return max(min(step, remaining), min(remaining, config.min_step_s)), unresolved


def _initial_trace(state: np.ndarray, connector: ScalarConnector) -> dict[str, list]:
    diag = connector.evaluate(float(state[0]), float(state[1]))
    return {
        "time_s": [0.0],
        "penetration_m": [float(state[0])],
        "normal_speed_mps": [float(state[1])],
        "force_n": [float(diag["force_n"])],
        "smoothing_weight": [float(diag["smoothing_weight"])],
        "accepted_dt_s": [0.0],
    }


def _append_trace(trace: dict[str, list], t: float, state: np.ndarray, dt: float, connector: ScalarConnector):
    diag = connector.evaluate(float(state[0]), float(state[1]))
    trace["time_s"].append(float(t))
    trace["penetration_m"].append(float(state[0]))
    trace["normal_speed_mps"].append(float(state[1]))
    trace["force_n"].append(float(diag["force_n"]))
    trace["smoothing_weight"].append(float(diag["smoothing_weight"]))
    trace["accepted_dt_s"].append(float(dt))


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
    """Integrate a scalar connector using F2, ES, or a fixed-step reference."""
    config = config or EventSubstepConfig()
    connector = ScalarConnector(law)
    state = np.asarray([q0_m, v0_mps], dtype=float)
    initial_state = state.copy()
    trace = _initial_trace(state, connector)
    events: list[dict] = []
    t = 0.0
    impulse = 0.0
    damping_work = 0.0
    peak_force = float(connector.evaluate(q0_m, v0_mps)["force_n"])
    min_dt = float("inf")
    total_steps = 0
    max_outer_substeps = 0
    zone_steps = 0
    unresolved = False
    status = "PASS"
    outer = config.outer_step_s
    if mode not in {"F2", "ES", "REF"}:
        raise ValueError(f"unsupported mode: {mode}")
    while t < duration_s - 1.0e-15:
        outer_end = min(duration_s, (np.floor((t + 1.0e-15) / outer) + 1.0) * outer)
        if outer_end <= t + 1.0e-15:
            outer_end = min(duration_s, t + outer)
        outer_substeps = 0
        while t < outer_end - 1.0e-15:
            remaining = outer_end - t
            if mode == "ES":
                dt, local_unresolved = _next_step_size(state, remaining, config)
                unresolved = unresolved or local_unresolved
                if local_unresolved:
                    status = "UNRESOLVED_EVENT_SPEED"
                    break
            elif mode == "REF":
                dt = min(float(fixed_step_s or config.min_step_s), remaining)
            else:
                dt = remaining
            if dt <= 0.0 or not np.isfinite(dt):
                status = "INVALID_STEP"
                break
            start = state.copy()
            if mode == "ES":
                midpoint, endpoint = two_half_rk4(start, dt, connector, config.reduced_mass_kg)
            else:
                midpoint = rk4_step(start, 0.5 * dt, connector, config.reduced_mass_kg)
                endpoint = rk4_step(start, dt, connector, config.reduced_mass_kg)
            mid_diag = connector.evaluate(float(midpoint[0]), float(midpoint[1]))
            impulse += float(mid_diag["force_n"]) * dt
            damping_work += float(mid_diag["damping_power_w"]) * dt
            peak_force = max(peak_force, float(mid_diag["force_n"]))
            for surface, name in ((0.0, "contact"), (config.smoothing_width_m, "smoothing")):
                a = float(start[0] - surface)
                b = float(endpoint[0] - surface)
                if _crossed(a, b, config.detector_release_tol_m):
                    local_time, event_state = _bisect_dynamic_event(start, dt, surface, connector, config)
                    absolute_time = t + local_time
                    direction = "load" if float(event_state[1]) >= 0.0 else "unload"
                    if not events or abs(absolute_time - events[-1]["time_s"]) > 1.0e-12 or events[-1]["surface"] != name:
                        events.append({
                            "time_s": absolute_time,
                            "surface": name,
                            "surface_m": surface,
                            "direction": direction,
                            "residual_m": abs(float(event_state[0] - surface)),
                        })
            q_lo = min(float(start[0]), float(endpoint[0]))
            q_hi = max(float(start[0]), float(endpoint[0]))
            if q_lo < config.smoothing_width_m and q_hi > 0.0:
                zone_steps += 1
            state = endpoint
            t += dt
            min_dt = min(min_dt, dt)
            total_steps += 1
            outer_substeps += 1
            if keep_trace:
                _append_trace(trace, t, state, dt, connector)
            end_diag = connector.evaluate(float(state[0]), float(state[1]))
            peak_force = max(peak_force, float(end_diag["force_n"]))
            if bool(end_diag["ultimate_exceeded"]):
                status = "STOP_ULTIMATE_FORCE"
                break
            if not np.all(np.isfinite(state)) or not np.isfinite(impulse):
                status = "NONFINITE"
                break
            # The 256 cap governs the adaptive event solver.  The registered
            # 2 us reference necessarily takes 1000 fixed microsteps per
            # 2 ms outer interval and is not an event-substep trajectory.
            if mode == "ES" and outer_substeps > config.max_substeps_per_outer:
                status = "SUBSTEP_CAP"
                break
        max_outer_substeps = max(max_outer_substeps, outer_substeps)
        if status != "PASS":
            break
    final_diag = connector.evaluate(float(state[0]), float(state[1]))
    initial_ke = 0.5 * config.reduced_mass_kg * float(initial_state[1]) ** 2
    final_mechanical = (
        0.5 * config.reduced_mass_kg * float(state[1]) ** 2
        + float(final_diag["elastic_energy_j"])
    )
    result = {
        "law": law,
        "mode": mode,
        "status": status,
        "duration_requested_s": duration_s,
        "duration_actual_s": t,
        "initial_penetration_m": q0_m,
        "initial_speed_mps": v0_mps,
        "terminal_penetration_m": float(state[0]),
        "terminal_speed_mps": float(state[1]),
        "terminal_force_n": float(final_diag["force_n"]),
        "peak_force_n": peak_force,
        "impulse_ns": impulse,
        "damping_work_j": damping_work,
        "initial_kinetic_energy_j": initial_ke,
        "terminal_mechanical_energy_j": final_mechanical,
        "energy_balance_residual_j": initial_ke - final_mechanical - damping_work,
        "events": events,
        "accepted_steps": total_steps,
        "max_substeps_per_outer": max_outer_substeps,
        "min_accepted_dt_s": 0.0 if min_dt == float("inf") else min_dt,
        "smoothing_zone_accepted_steps": zone_steps,
        "unresolved_event_speed": unresolved,
        "config": asdict(config),
    }
    if keep_trace:
        result["trace"] = trace
    return result


def detect_callable_events(
    value_fn: Callable[[float], np.ndarray],
    t0_s: float,
    t1_s: float,
    surfaces_m: tuple[float, ...] = (0.0, DELTA_S_M),
    probe_step_s: float = 0.0005,
    time_tol_s: float = 0.000001,
    surface_tol_m: float = 1.0e-8,
    simultaneous_tol_s: float = 0.000001,
) -> list[dict]:
    """Detect grouped surface crossings, including a midpoint-revealed double crossing."""
    span = t1_s - t0_s
    count = max(1, int(np.ceil(span / probe_step_s)))
    grid = np.linspace(t0_s, t1_s, count + 1)
    raw: list[dict] = []

    def bisect(connector_index: int, surface: float, left: float, right: float) -> float:
        fl = float(value_fn(left)[connector_index] - surface)
        # The registered 1 us timing tolerance alone is insufficient to meet
        # the independent 1e-8 m surface gate at 1 m/s. Refine to 1 ns so both
        # bounds are met without using the answer from the analytic case.
        target_time_tol = min(time_tol_s, 1.0e-9)
        while right - left > target_time_tol:
            mid = 0.5 * (left + right)
            fm = float(value_fn(mid)[connector_index] - surface)
            if fl * fm <= 0.0:
                right = mid
            else:
                left, fl = mid, fm
        return 0.5 * (left + right)

    def scan(connector_index: int, surface: float, left: float, right: float, depth: int = 0):
        middle = 0.5 * (left + right)
        vl = float(value_fn(left)[connector_index] - surface)
        vm = float(value_fn(middle)[connector_index] - surface)
        vr = float(value_fn(right)[connector_index] - surface)
        pieces = ((left, middle, vl, vm), (middle, right, vm, vr))
        found = False
        for a, b, fa, fb in pieces:
            if abs(fa) <= surface_tol_m:
                raw.append({"time_s": a, "connector": connector_index, "surface_m": surface})
                found = True
            if fa * fb < 0.0 or abs(fb) <= surface_tol_m:
                raw.append({"time_s": bisect(connector_index, surface, a, b), "connector": connector_index, "surface_m": surface})
                found = True
        if not found and depth < 4 and right - left > 2.0 * time_tol_s:
            quarter = 0.5 * (left + middle)
            three_quarter = 0.5 * (middle + right)
            samples = (vl, float(value_fn(quarter)[connector_index] - surface), vm, float(value_fn(three_quarter)[connector_index] - surface), vr)
            if min(samples) <= 0.0 <= max(samples):
                scan(connector_index, surface, left, middle, depth + 1)
                scan(connector_index, surface, middle, right, depth + 1)

    connector_count = int(np.asarray(value_fn(t0_s)).size)
    for i in range(connector_count):
        for surface in surfaces_m:
            for left, right in zip(grid[:-1], grid[1:]):
                scan(i, surface, float(left), float(right))
    unique: list[dict] = []
    for event in sorted(raw, key=lambda item: (item["time_s"], item["connector"], item["surface_m"])):
        duplicate = any(
            abs(event["time_s"] - prior["time_s"]) <= time_tol_s
            and event["connector"] == prior["connector"]
            and event["surface_m"] == prior["surface_m"]
            for prior in unique
        )
        if not duplicate:
            unique.append(event)
    groups: list[dict] = []
    for event in unique:
        if not groups or event["time_s"] - groups[-1]["time_s"] > simultaneous_tol_s:
            groups.append({"time_s": event["time_s"], "events": [event]})
        else:
            groups[-1]["events"].append(event)
    return groups
