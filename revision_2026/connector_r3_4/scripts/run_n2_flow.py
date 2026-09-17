from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connector_adapter import DELTA_S_M
from event_substep import EventSubstepConfig, integrate
from reference_oracle import OracleConfig, solve_oracle


SPEEDS = {
    "q05": 0.0002041391858023853,
    "q50": 0.003371584129140294,
    "q95": 0.054984709782141795,
    "q99": 0.2006325726682664,
    "stress_0p25": 0.25,
    "stress_1p0": 1.0,
}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def post_duration(speed: float) -> float:
    return max(0.020, DELTA_S_M / speed + 0.012)


def first_loading_event(run: dict, surface: str) -> float | None:
    values = [event["time_s"] for event in run["events"] if event["surface"] == surface and event["direction"] == "load"]
    return min(values) if values else None


def relative(value: float, reference: float, floor: float) -> float:
    return abs(value - reference) / max(abs(reference), floor)


def terminal_error(run: dict, reference: dict, speed: float) -> float:
    q_scale = max(DELTA_S_M, abs(reference["terminal_penetration_m"]), speed * 0.002, 1e-6)
    v_scale = max(speed, abs(reference["terminal_speed_mps"]), 1e-4)
    return max(
        abs(run["terminal_penetration_m"] - reference["terminal_penetration_m"]) / q_scale,
        abs(run["terminal_speed_mps"] - reference["terminal_speed_mps"]) / v_scale,
    )


def diagnose(rows: list[dict]) -> dict:
    es = [row for row in rows if row["integrator"] == "ES"]
    by_metric = {}
    for metric in ("peak_force_relative_error", "impulse_relative_error", "terminal_state_scaled_error", "contact_time_abs_error_s"):
        values = np.asarray([row[metric] for row in es], dtype=float)
        by_metric[metric] = {"maximum": float(np.max(values)), "median": float(np.median(values)), "std": float(np.std(values))}
    worst = max(es, key=lambda row: max(row["peak_force_relative_error"] / 0.05, row["impulse_relative_error"] / 0.02, row["terminal_state_scaled_error"] / 0.01, row["contact_time_abs_error_s"] / 2e-6))
    if worst["peak_force_relative_error"] > 0.05 and worst["impulse_relative_error"] <= 0.02:
        pattern = "PEAK_SAMPLING_OR_LOCAL_EXTREMUM"
    elif worst["impulse_relative_error"] > 0.02 and worst["peak_force_relative_error"] <= 0.05:
        pattern = "QUADRATURE_OR_EVENT_RESTART"
    elif worst["terminal_state_scaled_error"] > 0.01:
        pattern = "STATE_ADVANCE_OR_SCALE"
    elif worst["contact_time_abs_error_s"] > 2e-6:
        pattern = "ROOT_BRACKET_OR_TOLERANCE"
    else:
        pattern = "WITHIN_TARGET"
    return {"metric_distribution": by_metric, "worst_case": worst, "pattern": pattern}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    labels = ["q95"] if args.pilot else list(SPEEDS)
    config = EventSubstepConfig()
    oracle_config = OracleConfig(rtol=2.5e-12, atol_q=2.5e-14, atol_v=2.5e-12, atol_j=2.5e-13)
    references = {}
    rows = []
    started = time.perf_counter()
    for speed_label in labels:
        speed = SPEEDS[speed_label]
        post = post_duration(speed)
        for law in ("V1", "R3"):
            reference = solve_oracle(law, 0.0, speed, post, oracle_config)
            references[f"{speed_label}|{law}"] = reference
            for phase_index in range(32):
                phase = phase_index * config.outer_step_s / 32.0
                contact_time = config.outer_step_s + phase
                for mode in ("F2", "ES"):
                    run = integrate(law, -speed * contact_time, speed, contact_time + post, mode, config, keep_trace=False)
                    contact = first_loading_event(run, "contact")
                    peak_floor = 50.0
                    impulse_floor = 50.0 * post
                    row = {
                        "speed_label": speed_label,
                        "speed_mps": speed,
                        "phase_index": phase_index,
                        "phase_s": phase,
                        "law": law,
                        "integrator": mode,
                        "factor": f"{law}-{mode}",
                        "duration_s": contact_time + post,
                        "status": run["status"],
                        "contact_time_s": contact if contact is not None else "",
                        "expected_contact_time_s": contact_time,
                        "contact_time_abs_error_s": abs(contact - contact_time) if contact is not None else float("inf"),
                        "smoothing_zone_accepted_steps": run["smoothing_zone_accepted_steps"],
                        "peak_force_n": run["peak_force_n"],
                        "impulse_ns": run["impulse_ns"],
                        "terminal_penetration_m": run["terminal_penetration_m"],
                        "terminal_speed_mps": run["terminal_speed_mps"],
                        "energy_balance_residual_j": run["energy_balance_residual_j"],
                        "accepted_steps": run["accepted_steps"],
                        "min_accepted_dt_s": run["min_accepted_dt_s"],
                        "time_conservation_residual_s": run["time_conservation_residual_s"],
                        "peak_force_relative_error": relative(run["peak_force_n"], reference["peak_force_n"], peak_floor),
                        "impulse_relative_error": relative(run["impulse_ns"], reference["impulse_ns"], impulse_floor),
                        "terminal_state_scaled_error": terminal_error(run, reference, speed),
                        "finite": bool(all(np.isfinite(run[key]) for key in ("peak_force_n", "impulse_ns", "terminal_penetration_m", "terminal_speed_mps", "energy_balance_residual_j"))),
                    }
                    rows.append(row)
    write_csv(output / "single_connector_factorial.csv", rows)
    write_json(output / "tight_oracle.json", references)
    diagnostic = diagnose(rows)
    write_json(output / "diagnosis.json", diagnostic)
    es = [row for row in rows if row["integrator"] == "ES"]
    r3_es = [row for row in es if row["law"] == "R3"]
    checks = {
        "row_count": len(rows) == (128 if args.pilot else 768),
        "peak_le_5pct": all(row["peak_force_relative_error"] <= 0.05 for row in es),
        "impulse_le_2pct": all(row["impulse_relative_error"] <= 0.02 for row in es),
        "terminal_le_1pct": all(row["terminal_state_scaled_error"] <= 0.01 for row in es),
        "contact_le_2us": all(row["contact_time_abs_error_s"] <= 2e-6 for row in es),
        "r3_zone_steps_ge_8": all(row["smoothing_zone_accepted_steps"] >= 8 for row in r3_es),
        "physical_dt_ge_2us": all(row["min_accepted_dt_s"] >= config.min_step_s for row in es),
        "finite_pass": all(row["status"] == "PASS" and row["finite"] for row in rows),
        "time_conservation": all(row["time_conservation_residual_s"] <= 1e-12 for row in rows),
    }
    passed = all(checks.values())
    worst = diagnostic["worst_case"]
    worst_run = integrate(
        worst["law"],
        -worst["speed_mps"] * worst["expected_contact_time_s"],
        worst["speed_mps"],
        worst["duration_s"],
        worst["integrator"],
        config,
        keep_trace=True,
    )
    numeric_trace = {key: np.asarray(value) for key, value in worst_run["trace"].items() if key in {"time_s", "penetration_m", "normal_speed_mps", "force_n", "accepted_dt_s"}}
    np.savez_compressed(output / "worst_trace.npz", **numeric_trace)
    write_json(output / "worst_step_records.json", worst_run["step_records"])
    complete = {
        "stage": "N2_PILOT" if args.pilot else "N2_FULL",
        "passed": passed,
        "rows": len(rows),
        "checks": checks,
        "worst_es": {
            "peak": max(row["peak_force_relative_error"] for row in es),
            "impulse": max(row["impulse_relative_error"] for row in es),
            "terminal": max(row["terminal_state_scaled_error"] for row in es),
            "contact_s": max(row["contact_time_abs_error_s"] for row in es),
        },
        "minimum_r3_zone_steps": min(row["smoothing_zone_accepted_steps"] for row in r3_es),
        "runtime_s": time.perf_counter() - started,
    }
    if not passed:
        complete["repair_code"] = diagnostic["pattern"]
        complete["next_action"] = "Re-run the worst phase and its two adjacent phases after applying only the diagnosed numerical repair."
    write_json(output / "complete.json", complete)
    print(json.dumps(complete, ensure_ascii=False))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
