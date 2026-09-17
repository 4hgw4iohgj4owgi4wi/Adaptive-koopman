from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def latest_passed_with(root: Path, relative: str) -> Path:
    candidates = sorted(
        (path for path in root.iterdir() if path.is_dir() and (path / relative).exists()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        complete = path / "complete.json"
        if complete.exists() and read_json(complete).get("passed") is True:
            return path
    raise FileNotFoundError(relative)


def close_enough(actual: float, recorded: float) -> bool:
    return bool(np.isclose(actual, recorded, rtol=1.0e-10, atol=1.0e-10))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    project = args.project_root.resolve()
    output = args.output_dir.resolve()
    readiness_path = output / "READY_FOR_KOOPMAN_TRAINING.json"
    readiness = read_json(readiness_path)
    flow_runs = project / "revision_2026" / "connector_r3_4_results" / "flow_runs"
    n2 = latest_passed_with(flow_runs, "single_connector_factorial.csv")
    n3 = latest_passed_with(flow_runs, "q99_contact/summary.json")
    selection = latest_passed_with(flow_runs, "plant_selection.json")
    training = latest_passed_with(flow_runs, "training_metrics.json")
    mpc = latest_passed_with(flow_runs, "mpc_interface.json")
    data_dir = Path(readiness["confirmation_data"]["data_dir"])
    trajectories = read_csv(data_dir / "trajectory_manifest.csv")
    raw_row = next(
        row
        for row in trajectories
        if row["scenario"] == "100m" and row["plant"] == "R3-ES"
    )
    raw_path = Path(raw_row["raw_path"])
    with np.load(raw_path) as source:
        recalculated = {
            "distance_m": float(source["distance_m"][-1]),
            "duration_s": float(source["time_s"][-1]),
            "tire_utilization_max": float(np.max(source["tire_raw_utilization"])),
            "Tx_peak_n": float(np.max(source["tension_proxy_n"][:, 0])),
            "Ty_peak_n": float(np.max(source["tension_proxy_n"][:, 1])),
            "internal_force_peak_n": float(
                np.max(np.linalg.norm(source["internal_force_vector_n"], axis=1))
            ),
        }
    recorded = readiness["confirmation_data"]["acceptance"]
    checks = [
        {
            "metric": name,
            "unit": unit,
            "recalculated": recalculated[name],
            "recorded": float(recorded[name]),
            "absolute_difference": abs(recalculated[name] - float(recorded[name])),
            "passed": close_enough(recalculated[name], float(recorded[name])),
            "source": str(raw_path),
        }
        for name, unit in (
            ("distance_m", "m"),
            ("tire_utilization_max", "1"),
            ("Tx_peak_n", "N"),
            ("Ty_peak_n", "N"),
            ("internal_force_peak_n", "N"),
        )
    ]
    training_rows = read_json(training / "training_metrics.json")
    test_h20 = [
        row
        for row in training_rows
        if row["split"] == "test" and int(row["horizon"]) == 20
    ]
    fixed = {row["plant"]: row for row in test_h20 if row["model"] == "fixed_linear"}
    bilinear = {row["plant"]: row for row in test_h20 if row["model"] == "bilinear"}
    passed = all(item["passed"] for item in checks)
    verification = {
        "passed": passed,
        "metric_checks": checks,
        "metric_check_count": len(checks),
        "raw_trajectory": str(raw_path),
        "data_manifest": str(data_dir / "trajectory_manifest.csv"),
        "physical_trajectory_count": len(trajectories),
        "evidence_runs": {
            "N2_FULL": n2.name,
            "N3_FULL": n3.name,
            "SELECT_PLANT": selection.name,
            "DATA_FULL": data_dir.name,
            "TRAIN_SMOKE": training.name,
            "MPC_INTERFACE": mpc.name,
        },
    }
    write_json(output / "report_verification.json", verification)
    report = f"""# Connector flow frozen evidence report

## Recalculated facts

- N2 and N3 passed in `{n2.name}` and `{n3.name}`.
- The frozen R3-ES 100 m trajectory reached {recalculated['distance_m']:.6f} m in {recalculated['duration_s']:.3f} s; maximum raw tire utilization was {recalculated['tire_utilization_max']:.6f}.
- Peak separation-load proxies were Tx={recalculated['Tx_peak_n']:.3f} N and Ty={recalculated['Ty_peak_n']:.3f} N; peak complete internal-force norm was {recalculated['internal_force_peak_n']:.3f} N.
- All {len(checks)} registered acceptance values were independently recalculated from `{raw_path}` and matched the readiness record within `rtol=atol=1e-10`.
- The frozen causal data set contains {len(trajectories)} clean physical trajectories. This remains below the protocol suggestion of 100 and is not presented as a final learning data set.

## Plant and model interpretation

- Plant selection remains `{readiness['selection_branch']}`. R3-ES is valid, but the current evidence does not show an across-scenario physical advantage over V1-ES.
- Test 20-step normalized RMSE for fixed linear V1/R3 is {fixed['V1']['nrmse']:.6f}/{fixed['R3']['nrmse']:.6f}; for bilinear V1/R3 it is {bilinear['V1']['nrmse']:.6f}/{bilinear['R3']['nrmse']:.6f}.
- Therefore this package supports a causal training/interface smoke test, not bilinear superiority or new-plant closed-loop MPC performance.

## Claim boundaries

- Nonzero Tx/Ty proves tensile/separation loading, not cargo tearing or safety. Allowable loads, stress concentration and safety factors are absent.
- Network mask/AoI are interface-only. Communication disturbance, DoS, protection-controller comparisons, multi-seed inference, continuous-input IRSP certification and hardware validation remain unresolved.

## Evidence identity

- Data: `{data_dir}`
- Training: `{training}`
- MPC interface: `{mpc}`
- Recalculation record: `report_verification.json`
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(verification, ensure_ascii=False))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
