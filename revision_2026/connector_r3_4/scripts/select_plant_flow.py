from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spectral_metrics import spectral_metrics


FULL_RUN_ID = "20260828_121615_N4_FULL_F10"
CONFIRM_100M_RUN_ID = "20260828_131135_N4_100M_CONFIRM_F14"
SCENARIOS = (
    "100m",
    "straight",
    "single_lane_change_left",
    "hairpin_left",
    "line_curve_transition_left",
    "connector_longitudinal",
    "connector_lateral",
    "connector_diagonal_1",
    "connector_diagonal_2",
)
FACTORS = ("V1-F2", "V1-ES", "R3-F2", "R3-ES")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def source_dir(results: Path, scenario: str) -> Path:
    run_id = CONFIRM_100M_RUN_ID if scenario == "100m" else FULL_RUN_ID
    return results / "flow_runs" / run_id / scenario


def load_factor(results: Path, scenario: str, factor: str) -> tuple[dict, np.ndarray]:
    directory = source_dir(results, scenario) / factor
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    with np.load(directory / "timeseries.npz") as values:
        force = values["force_norm_2ms"].copy()
    return summary, force


def spectral(force: np.ndarray) -> dict:
    connector_metrics = [spectral_metrics(force[:, index], dt_s=0.002, high_hz=25.0) for index in range(4)]
    return {
        "high_frequency_energy_sum": float(sum(item["high_frequency_energy"] for item in connector_metrics)),
        "high_frequency_fraction_max": float(max(item["high_frequency_fraction"] for item in connector_metrics)),
        "parseval_relative_error_max": float(max(item["parseval_relative_error"] for item in connector_metrics)),
        "force_rms_max_n": float(max(item["rms"] for item in connector_metrics)),
        "jump_p99_max_n": float(max(item["jump_p99"] for item in connector_metrics)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = args.project_root.resolve() / "revision_2026" / "connector_r3_4_results"
    rows = []
    summaries = {}
    for scenario in SCENARIOS:
        summaries[scenario] = {}
        for factor in FACTORS:
            summary, force = load_factor(results, scenario, factor)
            frequency = spectral(force)
            summaries[scenario][factor] = {"summary": summary, "spectral": frequency}
            rows.append(
                {
                    "scenario": scenario,
                    "factor": factor,
                    "source_run_id": CONFIRM_100M_RUN_ID if scenario == "100m" else FULL_RUN_ID,
                    "force_jump_p99_max_n": frequency["jump_p99_max_n"],
                    "high_frequency_energy_sum_n2": frequency["high_frequency_energy_sum"],
                    "high_frequency_fraction_max": frequency["high_frequency_fraction_max"],
                    "force_rms_max_n": frequency["force_rms_max_n"],
                    "parseval_relative_error_max": frequency["parseval_relative_error_max"],
                    "internal_force_peak_n": summary["internal_force_peak_n"],
                    "tension_x_peak_n": summary["tension_x_peak_n"],
                    "tension_y_peak_n": summary["tension_y_peak_n"],
                    "smoothing_exposure_max": max(summary["smoothing_exposure"]),
                    "damping_ratio_max": max(summary["damping_ratio"]),
                    "tire_raw_utilization_max": max(summary["tire_raw_utilization_max"]),
                    "steering_clipped_fraction": summary["steering_clipped_fraction"],
                }
            )
    comparison = []
    advantage_count = 0
    worse_count = 0
    tradeoff_count = 0
    for scenario in SCENARIOS:
        v1 = summaries[scenario]["V1-ES"]
        r3 = summaries[scenario]["R3-ES"]
        jump_ratio = r3["spectral"]["jump_p99_max_n"] / max(v1["spectral"]["jump_p99_max_n"], 1e-12)
        hf_ratio = r3["spectral"]["high_frequency_energy_sum"] / max(v1["spectral"]["high_frequency_energy_sum"], 1e-24)
        exposure = max(r3["summary"]["smoothing_exposure"])
        if exposure >= 0.05 and jump_ratio < 0.9 and hf_ratio < 0.9:
            advantage_count += 1
        if exposure >= 0.01 and jump_ratio > 1.1 and hf_ratio > 1.1:
            worse_count += 1
        if exposure >= 0.01 and ((jump_ratio > 1.1 and hf_ratio < 0.9) or (hf_ratio > 1.1 and jump_ratio < 0.9)):
            tradeoff_count += 1
        comparison.append(
            {
                "scenario": scenario,
                "r3_to_v1_jump_p99_ratio": jump_ratio,
                "r3_to_v1_high_frequency_energy_ratio": hf_ratio,
                "r3_smoothing_exposure_max": exposure,
                "r3_damping_ratio_max": max(r3["summary"]["damping_ratio"]),
                "r3_to_v1_internal_peak_ratio": r3["summary"]["internal_force_peak_n"] / max(v1["summary"]["internal_force_peak_n"], 1e-12),
                "r3_to_v1_tension_x_peak_ratio": r3["summary"]["tension_x_peak_n"] / max(v1["summary"]["tension_x_peak_n"], 1e-12),
                "r3_to_v1_tension_y_peak_ratio": r3["summary"]["tension_y_peak_n"] / max(v1["summary"]["tension_y_peak_n"], 1e-12),
            }
        )
    all_valid = all(
        entry["summary"]["status"] == "PASS"
        and entry["summary"]["finite"]
        and max(entry["summary"]["tire_raw_utilization_max"]) <= 0.9
        for scenario in summaries.values()
        for entry in scenario.values()
    )
    parseval_diagnostic_max = max(row["parseval_relative_error_max"] for row in rows)
    if not all_valid:
        branch = "N4_DATA_INVALID_NEEDS_REPAIR"
        selected = None
        ready_status = "NEEDS_REPAIR"
    elif advantage_count >= 2 and worse_count == 0 and tradeoff_count == 0:
        branch = "R3-ES_ADVANTAGE"
        selected = "R3-ES"
        ready_status = "READY_R3_ES_WITH_ADVANTAGE"
    elif worse_count >= 2:
        branch = "R3-ES_NEEDS_R3_5"
        selected = "V1-ES"
        ready_status = "READY_V1_ES_BASELINE_R3_5_CONTINUES"
    else:
        branch = "R3-ES_VALID_NO_CLEAR_ADVANTAGE"
        selected = "R3-ES_AND_V1-ES"
        ready_status = "READY_R3_ES_NO_CLEAR_ADVANTAGE"
    write_csv(output / "factor_metrics.csv", rows)
    write_csv(output / "r3_vs_v1.csv", comparison)
    selection = {
        "stage": "SELECT_PLANT",
        "passed": all_valid,
        "branch": branch,
        "ready_status": ready_status,
        "selected_plant_for_clean_baseline": selected,
        "advantage_scenario_count": advantage_count,
        "worse_scenario_count": worse_count,
        "tradeoff_scenario_count": tradeoff_count,
        "input_runs": {"full": FULL_RUN_ID, "100m_confirmation": CONFIRM_100M_RUN_ID},
        "thresholds": {"advantage_ratio": 0.9, "worse_ratio": 1.1, "minimum_exposure": 0.05},
        "welch_parseval_diagnostic_max": parseval_diagnostic_max,
        "welch_parseval_gate": "UNIT_TEST_ONLY_FOR_STATIONARY_SIGNAL; nonstationary maneuver value retained as diagnostic",
        "interpretation": "R3.4 remains physically valid; selection does not change its law or thresholds. A V1-ES baseline is selected when R3.4 repeatedly increases jump or high-frequency metrics in exposed scenarios.",
    }
    write_json(output / "plant_selection.json", selection)
    write_json(output / "complete.json", selection)
    print(json.dumps(selection, ensure_ascii=False))
    raise SystemExit(0 if selection["passed"] else 2)


if __name__ == "__main__":
    main()
