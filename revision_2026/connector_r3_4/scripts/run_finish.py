from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from import_audit import audit_paths


STAGES = (
    "FLOW_C1",
    "N2_PILOT",
    "N2_FULL",
    "PHYSICS_STATIC",
    "N3_PILOT",
    "N3_FULL",
    "N4_PILOT",
    "N4_FULL",
    "SELECT_PLANT",
    "DATA_PILOT",
    "DATA_FULL",
    "TRAIN_SMOKE",
    "MPC_INTERFACE",
    "FINAL",
)

SCRIPT_ENTRY = {
    "N2_PILOT": ("run_n2_flow.py", ["--pilot"]),
    "N2_FULL": ("run_n2_flow.py", []),
    "PHYSICS_STATIC": ("run_n3_flow.py", ["--static-only"]),
    "N3_PILOT": ("run_n3_flow.py", ["--pilot"]),
    "N3_FULL": ("run_n3_flow.py", []),
    "N4_PILOT": ("run_maneuvers_flow.py", ["--pilot"]),
    "N4_FULL": ("run_maneuvers_flow.py", []),
    "SELECT_PLANT": ("select_plant_flow.py", []),
    "DATA_PILOT": ("generate_data_flow.py", ["--pilot"]),
    "DATA_FULL": ("generate_data_flow.py", []),
    "TRAIN_SMOKE": ("train_smoke_flow.py", []),
    "MPC_INTERFACE": ("verify_mpc_interface_flow.py", []),
    "FINAL": ("verify_repro.py", []),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def source_manifest() -> dict[str, str]:
    result = {}
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix.lower() in {".py", ".md", ".json"}:
            result[path.relative_to(ROOT).as_posix()] = sha256(path)
    return result


def manifest_digest(manifest: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()


def collect_test_ids(tests: Path, env: dict[str, str]) -> tuple[list[str], subprocess.CompletedProcess]:
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", str(tests), "--collect-only", "-q", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        env=env,
    )
    ids = [line.strip() for line in completed.stdout.splitlines() if "::test_" in line]
    return ids, completed


def run_flow_c1(project: Path, run_dir: Path) -> dict:
    results = project / "revision_2026" / "connector_r3_4_results"
    release = json.loads((results / "s4_review" / "release.json").read_text(encoding="utf-8"))
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    old = [str(path) for path in sorted((ROOT / "tests").glob("test_*.py")) if not path.name.startswith("test_finish_")]
    old_run = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", *old, "-q", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        env=env,
    )
    ids, collection = collect_test_ids(ROOT / "tests", env)
    all_run = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", str(ROOT / "tests"), "-q", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        env=env,
    )
    production = list((ROOT / "src").glob("*.py")) + list((ROOT / "scripts").glob("*.py"))
    forbidden = audit_paths(production, root=ROOT)
    contract = {
        "test_ids": ids,
        "count": len(ids),
        "sha256": {path.relative_to(ROOT).as_posix(): sha256(path) for path in sorted((ROOT / "tests").glob("test_*.py"))},
    }
    write_json(run_dir / "test_contract.json", contract)
    write_json(run_dir / "import_audit.json", {"findings": forbidden, "passed": not forbidden})
    passed = (
        release.get("approved") is True
        and old_run.returncode == 0
        and "18 passed" in old_run.stdout
        and collection.returncode == 0
        and all_run.returncode == 0
        and not forbidden
        and len(ids) >= 35
    )
    complete = {
        "stage": "FLOW_C1",
        "passed": passed,
        "old_tests": old_run.stdout.strip(),
        "all_tests": all_run.stdout.strip(),
        "test_count": len(ids),
        "forbidden_imports": forbidden,
        "release_approved": release.get("approved") is True,
    }
    write_json(run_dir / "complete.json", complete)
    return complete


def run_child(project: Path, stage: str, run_dir: Path) -> dict:
    script_name, extra = SCRIPT_ENTRY[stage]
    script = ROOT / "scripts" / script_name
    if not script.exists():
        return {
            "stage": stage,
            "passed": False,
            "repair_code": "MISSING_STAGE_ENTRY",
            "next_action": f"Implement scripts/{script_name} to the protocol_flow.md output contract.",
        }
    command = [
        sys.executable,
        "-B",
        str(script),
        "--project-root",
        str(project),
        "--output-dir",
        str(run_dir),
        *extra,
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    (run_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (run_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    complete_path = run_dir / "complete.json"
    payload = json.loads(complete_path.read_text(encoding="utf-8")) if complete_path.exists() else {}
    payload.update({"stage": stage, "returncode": completed.returncode})
    payload["passed"] = completed.returncode == 0 and payload.get("passed") is True
    if not payload["passed"] and "repair_code" not in payload:
        payload["repair_code"] = "STAGE_EXECUTION_FAILED"
        payload["next_action"] = f"Inspect {run_dir / 'stderr.txt'} and the stage diagnostics, then run the smallest failing subset."
    write_json(complete_path, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--repair-revision", default="F03")
    parser.add_argument("--resume-run-id")
    args = parser.parse_args()
    project = args.project_root.resolve()
    results = project / "revision_2026" / "connector_r3_4_results"
    flow_runs = results / "flow_runs"
    manifest = source_manifest()
    source_hash = manifest_digest(manifest)
    config_hash = sha256(args.config) if args.config and args.config.exists() else None
    if args.resume_run_id:
        run_id = args.resume_run_id
        run_dir = flow_runs / run_id
        metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
        expected = (args.stage, args.repair_revision, source_hash, config_hash)
        actual = (metadata["stage"], metadata["repair_revision"], metadata["source_manifest_sha256"], metadata["config_sha256"])
        if expected != actual:
            raise SystemExit("resume identity mismatch")
    else:
        timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        run_id = f"{timestamp}_{args.stage}_{args.repair_revision}"
        run_dir = flow_runs / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        write_json(
            run_dir / "run_metadata.json",
            {
                "run_id": run_id,
                "stage": args.stage,
                "repair_revision": args.repair_revision,
                "source_manifest_sha256": source_hash,
                "source_manifest": manifest,
                "config_sha256": config_hash,
                "protocol_flow_sha256": sha256(ROOT / "protocol_flow.md"),
            },
        )
    complete = run_flow_c1(project, run_dir) if args.stage == "FLOW_C1" else run_child(project, args.stage, run_dir)
    if complete.get("passed"):
        status = "READY_NEXT"
        next_action = {"status": status, "completed_stage": args.stage, "next_action": "Run the next registered protocol stage."}
    else:
        status = "NEEDS_REPAIR"
        next_action = {
            "status": status,
            "completed_stage": args.stage,
            "repair_code": complete.get("repair_code", "VALIDATION_FAILED"),
            "next_action": complete.get("next_action", "Inspect complete.json and run the smallest failing test or case."),
        }
    flow_status = {"run_id": run_id, "stage": args.stage, "status": status, "passed": bool(complete.get("passed")), "run_dir": str(run_dir)}
    write_json(run_dir / "next_action.json", next_action)
    write_json(results / "flow_status.json", flow_status)
    write_json(results / "next_action.json", next_action)
    print(json.dumps(flow_status, ensure_ascii=False))
    raise SystemExit(0 if complete.get("passed") else 2)


if __name__ == "__main__":
    main()
