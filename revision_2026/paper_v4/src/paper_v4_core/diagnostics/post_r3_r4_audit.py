"""Independent single-run audit for POST-R3 C1/R4 runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ..cli import save, sha
from ..e01_100m import params
from ..r2c_analyze import audit, load
from .post_r3_r4_runner import expanded_parameters


EXPECTED_STEPS = {"2ms": 0.002, "1ms": 0.001, "0.5ms": 0.0005}


def run_audit(label: str, folder: Path, protocol_path: Path) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    expected_runner = next(item["sha256"] for item in protocol["identity_files"] if item["path"].endswith("post_r3_r4_runner.py"))
    row, arrays = audit(label, folder, expected_runner_sha256=expected_runner)
    _, _, _, _, metrics, _ = load(folder)
    run = protocol["run"]
    checks = {
        "protocol_sha_identity": metrics.get("protocol_sha256") == sha(protocol_path),
        "candidate_identity": metrics.get("candidate_id") == "EXP-R3-unfrozen-v1" == run.get("candidate_id"),
        "implementation_identity": metrics.get("implementation_id") == "POST-R3-C1-parallel8-v1",
        "parameter_identity": metrics.get("parameter_id") == run.get("parameter_id"),
        "absolute_parameter_identity": metrics.get("parameter_values") == protocol.get("absolute_parameters") == expanded_parameters(params(run["parameter_id"])),
        "maximum_step_identity": bool(np.isclose(metrics.get("maximum_plant_step_s"), run["plant_max_step_ms"] / 1000.0, rtol=0.0, atol=1e-15)),
        "unfrozen_jacobian_identity": metrics.get("frozen_dynamics_jacobian") is False,
        "finite_difference_scale_identity": metrics.get("finite_difference_scale") == 1.0,
        "parallel_worker_identity": metrics.get("workers") == 8,
        "deadline_identity": metrics.get("deadline_unix") == run.get("deadline_unix"),
    }
    row["checks"].update({name: bool(value) for name, value in checks.items()})
    raw, columns, *_ = arrays
    request = raw[:, [columns[f"request_delta{i}"] for i in range(4)]]
    actual = raw[:, [columns[f"actual_delta{i}"] for i in range(4)]]
    row["input_diagnostics"] = {
        "request_steering_total_variation_deg": np.rad2deg(np.sum(np.abs(np.diff(request, axis=0)), axis=0)).tolist(),
        "actual_steering_total_variation_deg": np.rad2deg(np.sum(np.abs(np.diff(actual, axis=0)), axis=0)).tolist(),
        "request_limit_active_fraction": float(np.mean(np.isclose(np.abs(request), np.deg2rad(15.0), atol=1e-9))),
        "actual_limit_active_fraction": float(np.mean(np.isclose(np.abs(actual), np.deg2rad(15.0), atol=1e-9))),
    }
    row["status"] = "PASS" if all(row["checks"].values()) else "FAIL"
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", choices=tuple(EXPECTED_STEPS), required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_AUDIT")
    result = run_audit(args.label, args.run.resolve(), args.protocol.resolve())
    save(args.out.parent, args.out.name, result)
    print(json.dumps({"status": result["status"], "failed_checks": [key for key, value in result["checks"].items() if not value]}))
    if result["status"] != "PASS":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
