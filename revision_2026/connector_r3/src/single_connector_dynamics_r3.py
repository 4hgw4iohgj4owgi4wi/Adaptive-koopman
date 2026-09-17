from __future__ import annotations

import numpy as np

from connector_r3 import ConnectorR3Params, connector_force_r3


def simulate(
    params: ConnectorR3Params,
    delta0: float,
    v0: float,
    duration: float = 0.15,
    dt: float = 2.0e-5,
    reduced_mass_kg: float = 300.0,
    direction=(1.0, 0.0),
    stop_on_limit: bool = True,
):
    direction = np.asarray(direction, float); direction /= np.linalg.norm(direction)
    steps = int(round(duration / dt)) + 1
    t = np.arange(steps) * dt
    y = np.asarray([delta0, v0], float)
    rows = []
    failed = False

    def rhs(q):
        delta, vel = q
        res = connector_force_r3((params.free_play_m + delta) * direction, vel * direction, params)
        return np.asarray([vel, -float(res.applied_force_n) / reduced_mass_kg]), res

    for i in range(steps):
        _, res = rhs(y)
        rows.append((
            t[i], y[0], y[1], float(res.raw_force_n), float(res.elastic_force_n),
            float(res.damping_force_n), float(res.elastic_energy_j),
            float(res.damping_power_w), bool(res.contact_active_raw),
            bool(res.load_active_effective), float(res.smoothing_weight),
        ))
        if stop_on_limit and bool(res.ultimate_force_exceeded):
            failed = True
            break
        if i == steps - 1:
            break
        k1, _ = rhs(y); k2, _ = rhs(y + 0.5 * dt * k1)
        k3, _ = rhs(y + 0.5 * dt * k2); k4, _ = rhs(y + dt * k3)
        y = y + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6
    a = np.asarray(rows, float)
    kinetic = 0.5 * reduced_mass_kg * a[:, 2] ** 2
    return {
        "time_s": a[:, 0], "delta_m": a[:, 1], "normal_speed_mps": a[:, 2],
        "raw_force_n": a[:, 3], "elastic_force_n": a[:, 4], "damping_force_n": a[:, 5],
        "elastic_energy_j": a[:, 6], "damping_power_w": a[:, 7],
        "contact_active_raw": a[:, 8] > .5, "load_active_effective": a[:, 9] > .5,
        "smoothing_weight": a[:, 10], "kinetic_energy_j": kinetic,
        "total_mechanical_energy_j": kinetic + a[:, 6],
        "impulse_ns": np.cumsum(a[:, 3]) * dt, "failed": failed, "dt": dt,
    }
