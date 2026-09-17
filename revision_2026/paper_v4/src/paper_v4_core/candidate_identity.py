"""Versioned, read-only candidate identity audit for EXP-R4 U1."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cli import save, sha
from .r2c_analyze import audit


PAPER = Path(__file__).resolve().parents[2]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def audit_run(run_dir: Path, contracts_path: Path, candidate_id: str) -> dict:
    contracts = load(contracts_path)
    candidate = contracts["candidates"][candidate_id]
    registration = load(run_dir / "registration.json")
    metrics = load(run_dir / "2ms" / "metrics.json")
    preflight_path = PAPER / candidate["preflight_imports"]
    preflight = load(preflight_path)
    snapshot = PAPER / candidate["source_snapshot"]

    snapshot_files = {
        str(path.relative_to(snapshot)).replace("\\", "/"): sha(path)
        for path in sorted(snapshot.rglob("*.py"))
    }
    plant_expected = {
        Path(row["path"]).name: row["sha256"].lower()
        for row in preflight["runtime_modules"]
        if ".plant." in row["module"] or row["module"] == "paper_v4_core.plant"
    }
    plant_actual = {
        path.name: sha(path)
        for path in sorted((snapshot / "plant").glob("*.py"))
    }
    checks = {
        "candidate_id": registration.get("candidate_id") == candidate_id == metrics.get("candidate_id"),
        "protocol_sha256": registration.get("protocol_sha256", "").lower() == candidate["protocol_sha256"],
        "runner_registration": registration.get("runner_sha256", "").lower() == candidate["runner_sha256"],
        "runner_metrics": metrics.get("source_sha256", "").lower() == candidate["runner_sha256"],
        "runner_snapshot": snapshot_files.get("pilot_runner.py") == candidate["runner_sha256"],
        "controller_registration": registration.get("controller_sha256", "").lower() == candidate["controller_sha256"],
        "controller_snapshot": snapshot_files.get("controllers/physical_tracking_pilot.py") == candidate["controller_sha256"],
        "batch_registration": registration.get("batch_sha256", "").lower() == candidate["batch_sha256"],
        "batch_snapshot": snapshot_files.get("r3_recovery_batch.py") == candidate["batch_sha256"],
        "jacobian_mode": registration.get("frozen_dynamics_jacobian") is candidate["frozen_dynamics_jacobian"] and metrics.get("frozen_dynamics_jacobian") is candidate["frozen_dynamics_jacobian"],
        "finite_difference_scale": float(registration.get("finite_difference_scale", -1)) == float(candidate["finite_difference_scale"]) == float(metrics.get("finite_difference_scale", -2)),
        "recursive_plant_manifest_complete": plant_expected == plant_actual and len(plant_actual) >= 9,
        "preflight_precedes_run": preflight_path.stat().st_mtime_ns < (run_dir / "registration.json").stat().st_mtime_ns,
        "source_snapshot_complete": len(snapshot_files) >= 13,
    }
    physics, _ = audit("2ms", run_dir / "2ms", expected_runner_sha256=candidate["runner_sha256"])
    checks["independent_physics_and_evidence_audit"] = physics["status"] == "PASS"
    return {
        "schema_version": "EXP-R4-U1-run-identity-audit-v1",
        "status": "PASS_RECONSTRUCTED_IDENTITY" if all(checks.values()) else "SOURCE_UNRESOLVED",
        "scope": "Read-only re-audit; original registration/status/raw evidence are not modified.",
        "candidate_id": candidate_id,
        "run": str(run_dir),
        "contracts": str(contracts_path),
        "checks": checks,
        "expected": candidate,
        "recorded": {
            "runner_sha256": registration.get("runner_sha256"),
            "controller_sha256": registration.get("controller_sha256"),
            "batch_sha256": registration.get("batch_sha256"),
            "protocol_sha256": registration.get("protocol_sha256"),
        },
        "preflight_imports": str(preflight_path),
        "snapshot_files": snapshot_files,
        "physics_reaudit": physics,
        "limitation": "The launch recorded runner/controller/batch hashes and a preceding recursive plant manifest; the preserved source snapshot was made post-run, so this is reconstructed identity rather than a signed run-time bundle.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--contracts", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    report = audit_run(Path(args.run).resolve(), Path(args.contracts).resolve(), args.candidate)
    out.mkdir(parents=True)
    save(out, "identity_reaudit.json", report)
    print(json.dumps({"status": report["status"], "failed": [k for k, v in report["checks"].items() if not v]}))
    if report["status"] != "PASS_RECONSTRUCTED_IDENTITY":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
