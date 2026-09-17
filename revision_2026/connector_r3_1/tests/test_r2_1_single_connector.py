from __future__ import annotations

import csv
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from connector_r3 import connector_force_r3
from schema_r3 import params_from_delta_freeze
from single_connector_dynamics_r3 import simulate


DT_REF = 2.0e-5
PHASE_COUNT = 32


def digest(run: dict) -> str:
    h = hashlib.sha256()
    for key in ("time_s", "delta_m", "normal_speed_mps", "raw_force_n",
                "elastic_force_n", "damping_force_n", "elastic_energy_j",
                "damping_power_w", "contact_active_raw", "smoothing_weight"):
        h.update(np.ascontiguousarray(run[key]).view(np.uint8))
    return h.hexdigest()


def cumulative_trapezoid(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    return np.r_[0.0, np.cumsum(0.5 * (y[:-1] + y[1:]) * np.diff(x))]


def phase_run(params, speed: float, phase_s: float) -> dict:
    contact_time = 12 * DT_REF + phase_s
    duration = contact_time + 0.0045
    return simulate(replace(params, ultimate_force_n=1.0e12), -speed * contact_time,
                    speed, duration, DT_REF, stop_on_limit=False)


def onset_metrics(run: dict, params, speed: float, phase_s: float) -> dict:
    active = np.flatnonzero(run["contact_active_raw"])
    if not len(active):
        raise RuntimeError("contact not established")
    i = int(active[0])
    t0 = float(run["time_s"][i])
    j = min(len(run["time_s"]) - 1,
            int(np.searchsorted(run["time_s"], t0 + 0.002, side="left")))
    delta_i = max(float(run["delta_m"][i]), 0.0)
    vn_i = max(float(run["normal_speed_mps"][i]), 0.0)
    delta_j = max(float(run["delta_m"][j]), 0.0)
    vn_j = max(float(run["normal_speed_mps"][j]), 0.0)
    v1_i = params.stiffness_npm * delta_i + params.damping_nspm * vn_i
    v1_j = params.stiffness_npm * delta_j + params.damping_nspm * vn_j
    r3_i = float(run["raw_force_n"][i])
    r3_j = float(run["raw_force_n"][j])
    return {
        "speed_mps": speed,
        "phase_s": phase_s,
        "first_time_s": t0,
        "first_delta_m": delta_i,
        "first_smoothing_weight": float(run["smoothing_weight"][i]),
        "v1_first_force_n": v1_i,
        "r3_first_force_n": r3_i,
        "first_sample_reduction": (v1_i - r3_i) / max(v1_i, 1.0e-12),
        "v1_force_2ms_n": v1_j,
        "r3_force_2ms_n": r3_j,
        "two_ms_endpoint_reduction": (v1_j - r3_j) / max(v1_j, 1.0e-12),
    }


def main() -> None:
    freeze_path = Path(sys.argv[1]).resolve()
    support_path = Path(sys.argv[2]).resolve()
    outdir = Path(sys.argv[3]).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    params = params_from_delta_freeze(freeze_path)
    support = json.loads(support_path.read_text(encoding="utf-8"))
    if not support.get("passed") or support.get("development_read") or support.get("confirm_read"):
        raise SystemExit("invalid train-only support audit")
    support_speeds = support["support_test_speeds_mps"]

    phase_rows = []
    representative_runs = {}
    phases = np.arange(PHASE_COUNT, dtype=float) * DT_REF / PHASE_COUNT
    for label in ("q05", "q50", "q95", "q99"):
        speed = float(support_speeds[label])
        for phase in phases:
            run = phase_run(params, speed, float(phase))
            row = onset_metrics(run, params, speed, float(phase))
            row["speed_label"] = label
            phase_rows.append(row)
        representative_runs[f"support_{label}"] = phase_run(params, speed, 0.37 * DT_REF)
    for speed in (0.25, 1.0):
        representative_runs[f"stress_{speed:g}"] = phase_run(params, speed, 0.37 * DT_REF)

    with (outdir / "phase_sweep.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(phase_rows[0]))
        writer.writeheader()
        writer.writerows(phase_rows)

    two_ms = []
    for name, run in representative_runs.items():
        speed = float(name.split("_")[-1]) if name.startswith("stress_") else float(support_speeds[name.split("_")[-1]])
        row = onset_metrics(run, params, speed, 0.37 * DT_REF)
        row["case"] = name
        row["domain"] = "stress" if name.startswith("stress_") else "support"
        two_ms.append(row)
        np.savez_compressed(outdir / f"{name}.npz", **run)
    with (outdir / "two_ms_diagnostics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(two_ms[0]))
        writer.writeheader()
        writer.writerows(two_ms)

    # E1: genuinely activated physical free-system damping and matched zero-damping control.
    e1 = simulate(replace(params, ultimate_force_n=1.0e12), 0.25 * params.smoothing_width_m,
                  0.1, 0.04, 2.0e-6, stop_on_limit=False)
    e1_zero = simulate(replace(params, damping_nspm=0.0, ultimate_force_n=1.0e12),
                       0.25 * params.smoothing_width_m, 0.1, 0.04, 2.0e-6,
                       stop_on_limit=False)
    dissipated = cumulative_trapezoid(e1["damping_power_w"], e1["time_s"])
    balance = e1["total_mechanical_energy_j"] - e1["total_mechanical_energy_j"][0] + dissipated
    balance_abs = float(np.max(np.abs(balance)))
    balance_scaled = balance_abs / max(float(e1["total_mechanical_energy_j"][0]),
                                       float(dissipated[-1]), 1.0e-12)
    np.savez_compressed(outdir / "e1_damped.npz", **e1, cumulative_dissipation_j=dissipated,
                        energy_balance_residual_j=balance)
    np.savez_compressed(outdir / "e1_zero_damping.npz", **e1_zero)

    # E2: prescribed loading/unloading cycle fully inside the smoothing zone.
    t = np.linspace(0.0, 0.1, 20001)
    omega = 2.0 * np.pi / 0.1
    delta = 0.5 * params.smoothing_width_m * (1.0 - np.cos(omega * t))
    speed = 0.5 * params.smoothing_width_m * omega * np.sin(omega * t)
    result = connector_force_r3(
        np.c_[params.free_play_m + delta, np.zeros_like(delta)],
        np.c_[speed, np.zeros_like(speed)], params)
    e2_work = float(np.trapz(result.damping_power_w, t))
    e2_unload_max = float(np.max(np.abs(result.damping_force_n[speed < 0.0])))
    with (outdir / "e2_prescribed_cycle.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "delta_m", "normal_speed_mps", "smoothing_weight",
                         "elastic_force_n", "damping_force_n", "damping_power_w"])
        writer.writerows(zip(t, delta, speed, result.smoothing_weight,
                             result.elastic_force_n, result.damping_force_n,
                             result.damping_power_w))

    conservative = simulate(replace(params, damping_nspm=0.0, ultimate_force_n=1.0e12),
                            0.012, 0.0, 0.12, 5.0e-5, stop_on_limit=False)
    cons_energy = conservative["total_mechanical_energy_j"]
    cons_drift = float(np.max(np.abs(cons_energy - cons_energy[0])) / max(cons_energy[0], 1e-12))

    boundary_force = max(float(connector_force_r3(
        [params.free_play_m + x, 0.0], [1.0, 0.0], params).raw_force_n)
        for x in (1.0e-14, 1.0e-13, 1.0e-12))
    equivalence_error = max(abs(float(connector_force_r3(
        [params.free_play_m + d, 0.0], [v, 0.0], params).raw_force_n)
        - (params.stiffness_npm * d + params.damping_nspm * v))
        for d in (params.smoothing_width_m, 2 * params.smoothing_width_m, 0.01)
        for v in (0.01, 0.2, 1.0))
    directions = [simulate(params, -1e-4, 0.2, 0.02, DT_REF, direction=d,
                           stop_on_limit=False)["raw_force_n"]
                  for d in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    direction_error = max(float(np.max(np.abs(value - directions[0]))) for value in directions)
    repeat_a = phase_run(params, float(support_speeds["q95"]), 0.37 * DT_REF)
    repeat_b = phase_run(params, float(support_speeds["q95"]), 0.37 * DT_REF)
    over = simulate(params, params.ultimate_force_n / params.stiffness_npm,
                    0.0, 0.01, 1.0e-4)

    per_speed_min = {
        label: min(row["first_sample_reduction"] for row in phase_rows if row["speed_label"] == label)
        for label in ("q05", "q50", "q95", "q99")
    }
    finite_runs = list(representative_runs.values()) + [e1, e1_zero, conservative, repeat_a, repeat_b, over]
    finite = all(all(np.all(np.isfinite(value)) for value in run.values()
                     if isinstance(value, np.ndarray)) for run in finite_runs)
    nonnegative = all(float(np.min(run["raw_force_n"])) >= 0.0 for run in finite_runs)
    checks = {
        "boundary_force_tends_zero": boundary_force < 1.0e-5,
        "support_phase_worst_reduction_ge_50pct": min(per_speed_min.values()) >= 0.5,
        "e1_damping_activated": bool(np.max(e1["damping_power_w"]) > 0.0 and np.count_nonzero(e1["damping_power_w"] > 1.0e-12) > 0),
        "e1_damped_and_control_hash_differ": digest(e1) != digest(e1_zero),
        "e1_energy_balance_abs_le_2e_4_j": balance_abs <= 2.0e-4,
        "e1_energy_balance_scaled_le_2e_4": balance_scaled <= 2.0e-4,
        "e2_positive_dissipated_work": e2_work > 0.0,
        "e2_unloading_has_zero_damping": e2_unload_max <= 1.0e-12,
        "conservative_energy_drift_lt_0p5pct": cons_drift < 0.005,
        "post_smoothing_v1_equivalence": equivalence_error < 1.0e-9,
        "four_direction_symmetry": direction_error < 1.0e-9,
        "repeat_hash_equal": digest(repeat_a) == digest(repeat_b),
        "finite": finite,
        "no_negative_normal_force": nonnegative,
        "ultimate_stops_without_cap": bool(over["failed"] and len(over["time_s"]) == 1 and over["raw_force_n"][0] >= params.ultimate_force_n),
    }
    payload = {
        "passed": all(checks.values()),
        "classification": "post-R2 repaired R2.1 gate",
        "checks": {key: bool(value) for key, value in checks.items()},
        "phase_count_per_support_speed": PHASE_COUNT,
        "support_speeds_mps": support_speeds,
        "support_worst_first_sample_reduction": per_speed_min,
        "two_ms_endpoint_diagnostics": two_ms,
        "e1": {
            "initial_delta_m": 0.25 * params.smoothing_width_m,
            "initial_speed_mps": 0.1,
            "dt_s": 2.0e-6,
            "max_damping_power_w": float(np.max(e1["damping_power_w"])),
            "positive_power_samples": int(np.count_nonzero(e1["damping_power_w"] > 1.0e-12)),
            "dissipated_work_j": float(dissipated[-1]),
            "energy_balance_max_abs_j": balance_abs,
            "energy_balance_max_scaled": balance_scaled,
            "damped_hash": digest(e1),
            "zero_damping_hash": digest(e1_zero),
        },
        "e2": {"dissipated_work_j": e2_work, "unloading_max_damping_force_n": e2_unload_max},
        "conservative_energy_relative_drift": cons_drift,
        "boundary_force_limit_n": boundary_force,
        "post_smoothing_equivalence_max_abs_n": equivalence_error,
        "direction_symmetry_max_abs_n": direction_error,
        "development_read": False,
        "confirm_read": False,
    }
    (outdir / "r2_1_results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    raise SystemExit(0 if payload["passed"] else 2)


if __name__ == "__main__":
    main()
