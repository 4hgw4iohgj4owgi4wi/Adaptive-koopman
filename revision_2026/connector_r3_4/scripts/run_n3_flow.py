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
sys.path.insert(0, str(ROOT / "scripts"))

import run as vehicle_runs
from four_vehicle_common import ModelParams, assemble_derivative, connector_diagnostics, initialize_state, split_state
from steering_allocator import kinematic_targets


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def loaded_state(index: int | None = None) -> tuple[ModelParams, np.ndarray]:
    params = ModelParams()
    state = initialize_state(params, 2.0)
    vehicles, _ = split_state(state)
    directions = params.payload_anchor_body_m / np.linalg.norm(params.payload_anchor_body_m, axis=1)[:, None]
    indices = range(4) if index is None else [index]
    for connector in indices:
        vehicles[connector, :2] += directions[connector] * 0.003
    state[:24] = vehicles.ravel()
    return params, state


def run_static(output: Path) -> dict:
    rows = []
    max_derivative = 0.0
    max_action = 0.0
    max_common_moment = 0.0
    max_internal_null = 0.0
    for index in range(4):
        params, state = loaded_state(index)
        total, diagnostics = assemble_derivative(state, np.zeros((4, 2)), params, "R3", True)
        without, _ = assemble_derivative(state, np.zeros((4, 2)), params, "R3", False)
        residual = total - without - diagnostics["connector_derivative"]
        connector = diagnostics["connectors"]
        derivative_residual = float(np.max(np.abs(residual)))
        action_residual = float(np.max(np.linalg.norm(connector["action_reaction_residual_n"], axis=1)))
        common_moment = float(np.max(np.abs(connector["common_origin_internal_moment_residual_nm"])))
        internal_null = float(np.linalg.norm(connector["internal_null_residual"]))
        max_derivative = max(max_derivative, derivative_residual)
        max_action = max(max_action, action_residual)
        max_common_moment = max(max_common_moment, common_moment)
        max_internal_null = max(max_internal_null, internal_null)
        rows.append(
            {
                "connector": index,
                "derivative_residual": derivative_residual,
                "action_reaction_residual_n": action_residual,
                "common_origin_moment_residual_nm": common_moment,
                "internal_null_residual": internal_null,
                "vehicle_connector_derivative_norm": float(np.linalg.norm(diagnostics["connector_derivative"][6 * index + 3 : 6 * index + 6])),
                "payload_connector_derivative_norm": float(np.linalg.norm(diagnostics["connector_derivative"][27:30])),
            }
        )
    params = ModelParams()
    left = kinematic_targets(2.0, np.deg2rad(4.0), np.deg2rad(-2.0), params)
    right = kinematic_targets(2.0, np.deg2rad(-4.0), np.deg2rad(2.0), params)
    mirror = np.asarray([1, 0, 3, 2])
    mirror_residual = max(
        float(np.max(np.abs(left["relative_heading_rad"] + right["relative_heading_rad"][mirror]))),
        float(np.max(np.abs(left["speed_mps"] - right["speed_mps"][mirror]))),
        float(np.max(np.abs(left["feedforward_steering_rad"] + right["feedforward_steering_rad"][mirror]))),
    )
    icr_residual = max(
        float(np.max(np.abs(left["normal_velocity_residual_mps"]))),
        float(np.max(np.abs(right["normal_velocity_residual_mps"]))),
    )
    checks = {
        "derivative_wiring_le_1e10": max_derivative <= 1e-10,
        "action_reaction_le_1e10_n": max_action <= 1e-10,
        "common_origin_moment_le_1e8_nm": max_common_moment <= 1e-8,
        "internal_null_scaled": max_internal_null <= 1e-8,
        "mirror_le_1e12": mirror_residual <= 1e-12,
        "icr_normal_velocity_le_1e8_mps": icr_residual <= 1e-8,
    }
    write_csv(output / "static_wiring.csv", rows)
    complete = {
        "stage": "PHYSICS_STATIC",
        "passed": all(checks.values()),
        "checks": checks,
        "maxima": {
            "derivative_residual": max_derivative,
            "action_reaction_n": max_action,
            "common_origin_moment_nm": max_common_moment,
            "internal_null": max_internal_null,
            "mirror": mirror_residual,
            "icr_normal_velocity_mps": icr_residual,
        },
    }
    if not complete["passed"]:
        complete["repair_code"] = "PHYSICS_STATIC_RESIDUAL"
        complete["next_action"] = "Repair only the coordinate/sign layer associated with the first failed residual."
    write_json(output / "complete.json", complete)
    return complete


def specs(pilot: bool) -> list[tuple[str, str, float, str, float | None]]:
    if pilot:
        return [
            ("V1-ES", "V1", 0.002, "ES", None),
            ("R3-ES", "R3", 0.002, "ES", None),
            ("V1-REF", "V1", 0.002, "ES", 0.0001),
            ("R3-REF", "R3", 0.002, "ES", 0.0001),
        ]
    return [
        ("V1-F2", "V1", 0.002, "F2", None),
        ("V1-ES", "V1", 0.002, "ES", None),
        ("R3-F2", "R3", 0.002, "F2", None),
        ("R3-ES", "R3", 0.002, "ES", None),
        ("V1-ES-H1", "V1", 0.001, "ES", None),
        ("R3-ES-H1", "R3", 0.001, "ES", None),
        ("V1-ES-H0p5", "V1", 0.0005, "ES", None),
        ("R3-ES-H0p5", "R3", 0.0005, "ES", None),
        ("V1-REF", "V1", 0.002, "ES", 0.0001),
        ("R3-REF", "R3", 0.002, "ES", 0.0001),
    ]


def run_dynamic(output: Path, pilot: bool) -> dict:
    scenarios = ("q99_contact",) if pilot else ("q99_contact", "g3_turn_reversal")
    summaries = {}
    all_metrics = []
    started = time.perf_counter()
    for scenario in scenarios:
        scenario_dir = output / scenario
        scenario_dir.mkdir(parents=True, exist_ok=True)
        metrics = []
        raw_payload = {}
        for label, law, outer_h, mode, max_step in specs(pilot):
            metric, raw = vehicle_runs.simulate_vehicle(scenario, law, label, outer_h, mode, max_step)
            metrics.append(metric)
            for key, value in raw.items():
                raw_payload[f"{label.replace('-', '_')}_{key}"] = value
        np.savez_compressed(scenario_dir / "raw_timeseries.npz", **raw_payload)
        write_csv(scenario_dir / "metrics.csv", [vehicle_runs.flatten_vehicle_metric(metric) for metric in metrics])
        by_label = {metric["run"]: metric for metric in metrics}
        comparisons = {law: vehicle_runs.n3_compare(by_label[f"{law}-ES"], by_label[f"{law}-REF"]) for law in ("V1", "R3")}
        checks = {
            "peak_force_le_5pct": all(comparisons[law]["peak_force_error_max"] <= 0.05 for law in ("V1", "R3")),
            "impulse_le_2pct": all(comparisons[law]["impulse_error_max"] <= 0.02 for law in ("V1", "R3")),
            "terminal_le_1pct": all(comparisons[law]["terminal_state_scaled_error"] <= 0.01 for law in ("V1", "R3")),
            "internal_force_le_5pct": all(comparisons[law]["internal_force_peak_error"] <= 0.05 for law in ("V1", "R3")),
            "payload_moment_le_5pct": all(comparisons[law]["payload_moment_peak_error"] <= 0.05 for law in ("V1", "R3")),
            "vehicle_moment_le_5pct": all(comparisons[law]["vehicle_moment_error_max"] <= 0.05 for law in ("V1", "R3")),
            "action_reaction": all(metric["action_reaction_max_n"] < 1e-10 for metric in metrics),
            "internal_null": all(metric["internal_null_max_n"] < 1e-8 * max(1.0, metric["internal_force_peak_n"]) for metric in metrics),
            "finite_no_limit": all(metric["status"] == "PASS" and metric["finite"] for metric in metrics),
            "regular_dt_ge_2us": all(metric["min_regular_dt_s"] >= 2e-6 for metric in metrics if metric["mode"] == "ES"),
            "no_zone_or_probe_subminimum_steps": all(metric["subminimum_by_cause"]["ZONE_RESOLUTION"] == 0 and metric["subminimum_by_cause"]["PROBE_LIMIT"] == 0 for metric in metrics if metric["mode"] == "ES"),
        }
        if scenario == "q99_contact":
            q99_r3 = by_label["R3-ES"]
            contact_ids = {event["connector_id"] for event in q99_r3["events"] if event["surface"] == "contact" and event["direction"] == "load"}
            smoothing_ids = {event["connector_id"] for event in q99_r3["events"] if event["surface"] == "smoothing" and event["direction"] == "load"}
            checks["all_q99_events_recorded"] = contact_ids == {0, 1, 2, 3} and smoothing_ids == {0, 1, 2, 3}
            checks["r3_zone_ge_8"] = all(value >= 8 for value in q99_r3["zone_steps_per_connector"])
        passed = all(checks.values())
        summaries[scenario] = {"passed": passed, "checks": checks, "comparisons": comparisons}
        all_metrics.extend(metrics)
        write_json(scenario_dir / "summary.json", summaries[scenario])
    passed = all(summary["passed"] for summary in summaries.values())
    complete = {
        "stage": "N3_PILOT" if pilot else "N3_FULL",
        "passed": passed,
        "scenarios": summaries,
        "run_count": len(all_metrics),
        "runtime_s": time.perf_counter() - started,
    }
    if not passed:
        complete["repair_code"] = "N3_CONVERGENCE_OR_PHYSICS"
        complete["next_action"] = "Open the first failed scenario summary and rerun its candidate/reference pair only."
    write_json(output / "complete.json", complete)
    return complete


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    complete = run_static(output) if args.static_only else run_dynamic(output, args.pilot)
    print(json.dumps(complete, ensure_ascii=False))
    raise SystemExit(0 if complete["passed"] else 2)


if __name__ == "__main__":
    main()
