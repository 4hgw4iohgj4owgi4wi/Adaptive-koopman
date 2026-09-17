"""Gate-locked EXP-R2 R3 runner for the R2c-selected candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cli import save, sha
from .pilot_runner import ROUTE_LENGTH, SPEED, run
from .r2c_analyze import audit


RUNS = (("1ms", 0.001), ("0.5ms", 0.0005))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--baseline-2ms", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    selection_path = Path(args.selection)
    baseline = Path(args.baseline_2ms)
    selection = load_json(selection_path)
    selected = selection.get("selected_for_r3")
    if selection.get("status") != "PASS" or selected not in ("lambda1", "lambda2"):
        raise SystemExit("R2c comparison has not selected exactly lambda1 or lambda2")
    lambda_internal = float(selected.removeprefix("lambda"))
    baseline_metrics = load_json(baseline / "metrics.json")
    baseline_checks = {
        "completed": baseline_metrics.get("status") == "COMPLETED"
        and bool(baseline_metrics.get("trajectory_completed")),
        "parameter_p0": baseline_metrics.get("parameter_id") == "P0",
        "lambda_identity": float(baseline_metrics.get("lambda_internal")) == lambda_internal,
        "two_ms_identity": float(baseline_metrics.get("maximum_plant_step_s")) == 0.002,
        "route_identity": abs(float(baseline_metrics.get("route_length_m")) - ROUTE_LENGTH) <= 1e-12,
    }
    if not all(baseline_checks.values()):
        raise SystemExit(f"Selected 2 ms baseline identity failed: {baseline_checks}")
    out.mkdir(parents=True, exist_ok=False)
    registration = {
        "status": "RUNNING",
        "stage": "EXP-R2/R3",
        "selected_for_r3": selected,
        "lambda_internal": lambda_internal,
        "parameter_id": "P0",
        "baseline_2ms": str(baseline),
        "baseline_checks": baseline_checks,
        "new_run_order": [name for name, _ in RUNS],
        "stop_rule": "stop after the first non-COMPLETED run",
        "selection_report_sha256": sha(selection_path),
        "runner_sha256": sha(Path(__file__).with_name("pilot_runner.py")),
        "batch_sha256": sha(__file__),
        "runs": [],
    }
    save(out, "registration.json", registration)
    save(out, "status.json", registration)
    for name, max_step_s in RUNS:
        run_dir = out / name
        try:
            run(
                run_dir,
                parameter_id="P0",
                max_step_s=max_step_s,
                lambda_internal=lambda_internal,
                segment_s=ROUTE_LENGTH / SPEED,
            )
        except SystemExit as error:
            metrics_path = run_dir / "metrics.json"
            metrics = load_json(metrics_path) if metrics_path.is_file() else {"status": "FAILED", "reason": str(error)}
            registration["runs"].append({"name": name, "folder": str(run_dir), "metrics": metrics})
            registration["status"] = "FAILED"
            registration["reason"] = f"{name} did not complete"
            save(out, "status.json", registration)
            raise
        except Exception as error:
            registration["runs"].append(
                {"name": name, "folder": str(run_dir), "exception": f"{type(error).__name__}: {error}"}
            )
            registration["status"] = "FAILED"
            registration["reason"] = f"{name} raised an unexpected exception"
            save(out, "status.json", registration)
            raise
        metrics = load_json(run_dir / "metrics.json")
        post_audit, _ = audit(name, run_dir)
        post_audit["checks"]["maximum_plant_step_identity"] = bool(
            abs(float(metrics["maximum_plant_step_s"]) - max_step_s) <= 1e-15
        )
        post_audit["checks"]["selected_lambda_identity"] = bool(
            float(metrics["lambda_internal"]) == lambda_internal
        )
        post_audit["checks"]["parameter_p0"] = metrics["parameter_id"] == "P0"
        post_audit["status"] = "PASS" if all(post_audit["checks"].values()) else "FAIL"
        registration["runs"].append(
            {"name": name, "folder": str(run_dir), "metrics": metrics, "post_audit": post_audit}
        )
        if post_audit["status"] != "PASS":
            registration["status"] = "FAILED"
            registration["reason"] = f"{name} failed the independent post-run hard/evidence audit"
            save(out, "status.json", registration)
            raise SystemExit(20)
        save(out, "status.json", registration)
    registration["status"] = "COMPLETED"
    registration["reason"] = None
    save(out, "status.json", registration)
    print(json.dumps({"status": registration["status"], "runs": [item["name"] for item in registration["runs"]]}))


if __name__ == "__main__":
    main()
