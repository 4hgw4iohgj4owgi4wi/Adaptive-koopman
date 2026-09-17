from __future__ import annotations

import csv
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from schema_r3 import params_from_delta_freeze
from single_connector_dynamics_r3 import simulate


DTS = (0.002, 0.001, 0.0005, 0.0001)
REF_DT = 0.0001
PHASE_COUNT = 32


def metrics(run: dict, delta_scale: float, speed_scale: float) -> dict:
    active = np.flatnonzero(run["contact_active_raw"])
    first = float(run["time_s"][active[0]]) if len(active) else float("nan")
    return {
        "peak_force_n": float(np.max(run["raw_force_n"])),
        # The convergence quantity is the time integral of force.  Use the
        # trapezoidal rule on each grid instead of the simulator's historical
        # left-rectangle running diagnostic, whose endpoint bias scales with dt.
        "impulse_ns": float(np.trapezoid(run["raw_force_n"], run["time_s"])),
        "terminal_delta_m": float(run["delta_m"][-1]),
        "terminal_speed_mps": float(run["normal_speed_mps"][-1]),
        "terminal_scaled_norm": float(max(abs(run["delta_m"][-1]) / delta_scale,
                                            abs(run["normal_speed_mps"][-1]) / speed_scale)),
        "first_contact_time_s": first,
        "strict_smoothing_samples": int(np.count_nonzero(
            (run["delta_m"] > 0.0) & (run["smoothing_weight"] < 1.0))),
        "finite": bool(all(np.all(np.isfinite(value)) for value in run.values()
                           if isinstance(value, np.ndarray))),
    }


def relative(value: float, reference: float) -> float:
    return abs(value - reference) / max(abs(reference), 1.0e-12)


def main() -> None:
    freeze_path = Path(sys.argv[1]).resolve()
    support_path = Path(sys.argv[2]).resolve()
    r2_path = Path(sys.argv[3]).resolve()
    outdir = Path(sys.argv[4]).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    params = params_from_delta_freeze(freeze_path)
    support = json.loads(support_path.read_text(encoding="utf-8"))
    r2 = json.loads(r2_path.read_text(encoding="utf-8"))
    if not support.get("passed") or not r2.get("passed"):
        raise SystemExit("R3a requires passed S1 and R2.1")

    speed_cases = {
        key: float(support["support_test_speeds_mps"][key])
        for key in ("q50", "q95", "q99")
    }
    speed_cases.update({"stress_0p25": 0.25, "stress_1p0": 1.0})
    comparison_rows = []
    numeric_checks = []
    for label, speed in speed_cases.items():
        runs = {}
        delta_scale = max(params.smoothing_width_m, speed * 0.02, 0.001)
        speed_scale = max(speed, 0.1)
        for dt in DTS:
            run = simulate(replace(params, ultimate_force_n=1.0e12), 0.0, speed,
                           0.02, dt, stop_on_limit=False)
            runs[dt] = run
            np.savez_compressed(outdir / f"onset_{label}_dt_{dt:.4f}.npz", **run)
        reference = metrics(runs[REF_DT], delta_scale, speed_scale)
        for dt in DTS:
            value = metrics(runs[dt], delta_scale, speed_scale)
            terminal_error = max(
                abs(value["terminal_delta_m"] - reference["terminal_delta_m"]) / delta_scale,
                abs(value["terminal_speed_mps"] - reference["terminal_speed_mps"]) / speed_scale,
            )
            row = {
                "case": label, "kind": "onset", "speed_mps": speed, "dt_s": dt,
                **value,
                "peak_force_relative_error": relative(value["peak_force_n"], reference["peak_force_n"]),
                "impulse_relative_error": relative(value["impulse_ns"], reference["impulse_ns"]),
                "terminal_state_scaled_error": terminal_error,
                "contact_time_abs_error_s": abs(value["first_contact_time_s"] - reference["first_contact_time_s"]),
            }
            comparison_rows.append(row)
            if dt == 0.002:
                numeric_checks.append({
                    "case": label,
                    "peak_pass": row["peak_force_relative_error"] <= 0.05,
                    "impulse_pass": row["impulse_relative_error"] <= 0.02,
                    "terminal_pass": terminal_error <= 0.01,
                    "contact_time_pass": row["contact_time_abs_error_s"] <= 0.002 + 1.0e-15,
                    "finite": value["finite"],
                })

    for force_n in (2000.0, 8000.0, 12000.0, 14000.0):
        label = f"elastic_{int(force_n)}n"
        delta0 = force_n / params.stiffness_npm
        runs = {}
        for dt in DTS:
            run = simulate(replace(params, ultimate_force_n=1.0e12), delta0, 0.0,
                           0.02, dt, stop_on_limit=False)
            runs[dt] = run
            np.savez_compressed(outdir / f"{label}_dt_{dt:.4f}.npz", **run)
        delta_scale = max(delta0, 0.001)
        reference = metrics(runs[REF_DT], delta_scale, 1.0)
        for dt in DTS:
            value = metrics(runs[dt], delta_scale, 1.0)
            terminal_error = max(
                abs(value["terminal_delta_m"] - reference["terminal_delta_m"]) / delta_scale,
                abs(value["terminal_speed_mps"] - reference["terminal_speed_mps"]),
            )
            row = {
                "case": label, "kind": "high_load_release", "speed_mps": 0.0, "dt_s": dt,
                **value,
                "peak_force_relative_error": relative(value["peak_force_n"], reference["peak_force_n"]),
                "impulse_relative_error": relative(value["impulse_ns"], reference["impulse_ns"]),
                "terminal_state_scaled_error": terminal_error,
                "contact_time_abs_error_s": abs(value["first_contact_time_s"] - reference["first_contact_time_s"]),
            }
            comparison_rows.append(row)
            if dt == 0.002:
                numeric_checks.append({
                    "case": label,
                    "peak_pass": row["peak_force_relative_error"] <= 0.05,
                    "impulse_pass": row["impulse_relative_error"] <= 0.02,
                    "terminal_pass": terminal_error <= 0.01,
                    "contact_time_pass": row["contact_time_abs_error_s"] <= 0.002 + 1.0e-15,
                    "finite": value["finite"],
                })

    with (outdir / "dt_comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparison_rows[0]))
        writer.writeheader()
        writer.writerows(comparison_rows)

    resolution_rows = []
    for label in ("q50", "q95", "q99"):
        speed = speed_cases[label]
        tau = params.smoothing_width_m / speed
        for phase_index in range(PHASE_COUNT):
            phase = phase_index * 0.002 / PHASE_COUNT
            contact_time = 0.004 + phase
            grid = np.arange(0.0, contact_time + tau + 0.0041, 0.002)
            nodes = int(np.count_nonzero((grid > contact_time) & (grid < contact_time + tau)))
            resolution_rows.append({
                "speed_label": label, "speed_mps": speed, "phase_index": phase_index,
                "phase_s": phase, "tau_nominal_s": tau, "strict_inside_zone_nodes": nodes,
            })
    with (outdir / "plant_step_resolution.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(resolution_rows[0]))
        writer.writeheader()
        writer.writerows(resolution_rows)

    resolution_summary = {}
    for label in ("q50", "q95", "q99"):
        values = np.asarray([row["strict_inside_zone_nodes"] for row in resolution_rows
                             if row["speed_label"] == label])
        resolution_summary[label] = {
            "speed_mps": speed_cases[label],
            "tau_nominal_s": params.smoothing_width_m / speed_cases[label],
            "node_min": int(np.min(values)),
            "node_median": float(np.median(values)),
            "node_max": int(np.max(values)),
            "fraction_le_one_node": float(np.mean(values <= 1)),
            "median_at_least_two": bool(np.median(values) >= 2),
        }
    resolvable = all(value["median_at_least_two"] for value in resolution_summary.values())
    numeric_pass = all(all(check[key] for key in ("peak_pass", "impulse_pass",
                                                   "terminal_pass", "contact_time_pass", "finite"))
                       for check in numeric_checks)
    result = {
        "passed": bool(resolvable and numeric_pass),
        "classification": "R3a plant-step resolvability and single-connector convergence",
        "checks": {
            "support_smoothing_zone_resolvable_at_2ms": bool(resolvable),
            "all_2ms_numeric_convergence_checks_pass": bool(numeric_pass),
        },
        "resolution_by_support_speed": resolution_summary,
        "numeric_checks_2ms_vs_0p1ms": numeric_checks,
        "four_vehicle_representative_load": (
            "NOT_RUN_PRECONDITION_R3A_RESOLUTION_FAILED" if not resolvable
            else "NOT_IMPLEMENTED_REQUIRES_R3B_CONTINUATION"
        ),
        "development_read": False,
        "confirm_read": False,
    }
    (outdir / "r3_dt_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
