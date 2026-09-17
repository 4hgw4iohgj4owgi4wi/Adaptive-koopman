from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]

from data_manifest import array_sha256, file_sha256


REQUIRED = {
    "time_s",
    "state30",
    "requested_control4x2",
    "actual_steering_rad",
    "actual_steering_rate_substeps_radps",
    "vehicle_fxyz_body4x3_n",
    "vehicle_yaw_rate4_radps",
    "payload_yaw_rate_radps",
    "system_yaw_rate_radps",
    "force_payload_body_n",
    "internal_force_vector_n",
    "payload_support_load4_n",
    "vehicle_total_normal_load4_n",
    "support_constraint_relative_residual3",
    "tire_raw_utilization",
    "action_reaction_residual4x2_n",
    "internal_null_residual3_n",
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def _load(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def _audit_row(row: dict, protocol: dict, require_replay: bool) -> dict:
    path = Path(row["raw_path"])
    arrays = _load(path)
    missing = sorted(REQUIRED - set(arrays))
    numeric = [
        np.asarray(value)
        for value in arrays.values()
        if np.asarray(value).dtype.kind not in {"O", "U", "S"}
    ]
    dt = np.diff(np.asarray(arrays["time_s"], dtype=float))
    internal = np.asarray(arrays["internal_force_vector_n"], dtype=float)
    internal_null = np.asarray(arrays["internal_null_residual3_n"], dtype=float)
    internal_relative = float(np.max(np.linalg.norm(internal_null, axis=1))) / max(
        float(np.max(np.linalg.norm(internal, axis=1))), 1.0
    )
    rate_peak = float(
        np.max(np.abs(np.asarray(arrays["actual_steering_rate_substeps_radps"], dtype=float)))
    )
    angle_peak = float(np.max(np.abs(np.asarray(arrays["actual_steering_rad"], dtype=float))))
    gates = {
        "raw_file_sha": file_sha256(path) == row["raw_file_sha256"],
        "array_sha": array_sha256(
            arrays, keys=(key for key in arrays if key not in {"params_json", "params_sha256"})
        )
        == row["trajectory_array_sha256"],
        "required_fields": not missing,
        "finite": all(np.all(np.isfinite(value)) for value in numeric),
        "time_grid": bool(
            dt.size
            and np.all(dt > 0.0)
            and np.max(np.abs(dt - float(protocol["k2"]["model_step_s"])))
            <= float(protocol["physics_gates"]["time_step_atol_s"])
        ),
        "replay": (not require_replay) or str(row["replay_hash_match"]).lower() == "true",
        "action_reaction": float(
            np.max(np.abs(np.asarray(arrays["action_reaction_residual4x2_n"], dtype=float)))
        )
        <= float(protocol["physics_gates"]["action_reaction_atol_n"]),
        "internal_null": internal_relative
        <= float(protocol["physics_gates"]["internal_null_relative_atol"]),
        "support_nonnegative": float(np.min(arrays["payload_support_load4_n"]))
        >= float(protocol["physics_gates"]["support_min_atol_n"]),
        "support_conservation": float(
            np.max(np.abs(arrays["support_constraint_relative_residual3"]))
        )
        <= float(protocol["physics_gates"]["support_constraint_relative_atol"]),
        "tire": float(np.max(arrays["tire_raw_utilization"]))
        <= float(protocol["physics_gates"]["tire_raw_utilization_max"]),
        "actuator_rate": rate_peak
        <= float(protocol["actuator"]["rate_max_radps"])
        + float(protocol["physics_gates"]["actuator_rate_atol_radps"]),
        "actuator_angle": angle_peak
        <= np.deg2rad(float(protocol["actuator"]["angle_max_deg"]))
        + float(protocol["physics_gates"]["actuator_angle_atol_rad"]),
        "summary_audit": str(row["audit_passed"]).lower() == "true",
    }
    return {
        "trajectory_id": int(row["trajectory_id"]),
        "passed": all(gates.values()),
        "failed_gates": [name for name, passed in gates.items() if not passed],
        "missing_fields": missing,
        "internal_null_relative": internal_relative,
        "rate_peak_radps": rate_peak,
        "angle_peak_rad": angle_peak,
        **{f"gate_{name}": bool(value) for name, value in gates.items()},
    }


def audit_manifest(manifest: Path, protocol_path: Path, require_replay: bool) -> dict:
    protocol = _read_json(protocol_path)
    with manifest.open("r", newline="", encoding="utf-8-sig") as stream:
        source_rows = list(csv.DictReader(stream))
    rows = [_audit_row(row, protocol, require_replay) for row in source_rows]
    identities = {
        (
            row["scenario"],
            row["parameter_family"],
            row["direction"],
            row["member"],
            row["plant"],
        )
        for row in source_rows
    }
    result = {
        "passed": bool(rows) and all(row["passed"] for row in rows),
        "trajectory_count": len(rows),
        "unique_identity_count": len(identities),
        "failed_trajectory_count": sum(not row["passed"] for row in rows),
        "require_replay": bool(require_replay),
        "rows": rows,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--require-replay", action="store_true")
    args = parser.parse_args()
    result = audit_manifest(
        Path(args.manifest), Path(args.protocol), bool(args.require_replay)
    )
    _write_json(Path(args.output), result)
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
