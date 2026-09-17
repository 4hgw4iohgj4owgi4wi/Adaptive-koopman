"""EXP-R3 full three-step rerun for the evidence-selected unfrozen-Jacobian candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cli import save, sha
from .pilot_runner import ROUTE_LENGTH, SPEED, run
from .r2c_analyze import audit


PROTOCOL_SHA256 = "eb5d176e444dd5008c9d527fa0c44cef134c9a2d285833ce5c4e5ba7cb8e0b87"
CANDIDATE_ID = "EXP-R3-unfrozen-v1"
RUNS = (("2ms", 0.002), ("1ms", 0.001), ("0.5ms", 0.0005))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--protocol", required=True)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    protocol = Path(args.protocol).resolve()
    if sha(protocol) != PROTOCOL_SHA256:
        raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    selection_path = Path(args.selection).resolve()
    selection = load_json(selection_path)
    selected = selection.get("selected_for_r3")
    if selection.get("status") != "PASS" or selected not in ("lambda1", "lambda2"):
        raise SystemExit("R2c comparison has not selected exactly lambda1 or lambda2")
    lambda_internal = float(selected.removeprefix("lambda"))
    out.mkdir(parents=True)
    registration = {
        "status": "RUNNING",
        "stage": "EXP-R3/R3-recovery-full",
        "candidate_id": CANDIDATE_ID,
        "candidate_change": "Recompute dynamics Jacobian at every prediction step; all costs, constraints, horizon, finite-difference scale, plant and actuator semantics unchanged.",
        "evidence_source": "20260911_QP_FD01",
        "selected_for_r3": selected,
        "lambda_internal": lambda_internal,
        "parameter_id": "P0",
        "protocol_sha256": sha(protocol),
        "selection_report": str(selection_path),
        "selection_report_sha256": sha(selection_path),
        "runner_sha256": sha(Path(__file__).with_name("pilot_runner.py")),
        "controller_sha256": sha(Path(__file__).parent / "controllers" / "physical_tracking_pilot.py"),
        "batch_sha256": sha(__file__),
        "frozen_dynamics_jacobian": False,
        "finite_difference_scale": 1.0,
        "run_order": [name for name, _ in RUNS],
        "stop_rule": "Stop after first incomplete trajectory or failed independent hard/evidence audit.",
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
                frozen_dynamics_jacobian=False,
                finite_difference_scale=1.0,
            )
        except BaseException as error:
            metrics_path = run_dir / "metrics.json"
            metrics = load_json(metrics_path) if metrics_path.is_file() else {"status": "FAILED", "reason": f"{type(error).__name__}: {error}"}
            registration["runs"].append({"name": name, "folder": str(run_dir), "metrics": metrics})
            registration["status"] = "FAILED"
            registration["reason"] = f"{name} did not complete"
            save(out, "status.json", registration)
            raise
        metrics = load_json(run_dir / "metrics.json")
        post_audit, _ = audit(name, run_dir)
        post_audit["checks"].update({
            "maximum_plant_step_identity": abs(float(metrics["maximum_plant_step_s"]) - max_step_s) <= 1e-15,
            "selected_lambda_identity": float(metrics["lambda_internal"]) == lambda_internal,
            "parameter_p0": metrics["parameter_id"] == "P0",
            "candidate_identity": metrics.get("candidate_id") == CANDIDATE_ID,
            "unfrozen_jacobian_identity": metrics.get("frozen_dynamics_jacobian") is False,
            "finite_difference_scale_identity": float(metrics.get("finite_difference_scale", -1.0)) == 1.0,
        })
        post_audit["status"] = "PASS" if all(post_audit["checks"].values()) else "FAIL"
        registration["runs"].append({"name": name, "folder": str(run_dir), "metrics": metrics, "post_audit": post_audit})
        if post_audit["status"] != "PASS":
            registration["status"] = "FAILED"
            registration["reason"] = f"{name} failed the independent hard/evidence audit"
            save(out, "status.json", registration)
            raise SystemExit(20)
        save(out, "status.json", registration)
    registration["status"] = "COMPLETED"
    registration["reason"] = None
    save(out, "status.json", registration)
    print(json.dumps({"status": registration["status"], "candidate_id": CANDIDATE_ID, "runs": [r["name"] for r in registration["runs"]]}))


if __name__ == "__main__":
    main()
