from __future__ import annotations

import csv
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import scipy
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contracts import json_sha256, sha256, source_manifest, write_json
from data_manifest import file_sha256


def process_snapshot() -> list[dict]:
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object {$_.Name -match '^(python|matlab)(.exe)?$'} | "
        "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 3"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    if not completed.stdout.strip():
        return []
    value = json.loads(completed.stdout)
    return value if isinstance(value, list) else [value]


def audit_seeds(project: Path, protocol: dict) -> dict:
    historical: set[int] = set()
    sources = []
    for path in sorted((project / "revision_2026").rglob("*manifest*.csv")):
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
        except (OSError, UnicodeError, csv.Error):
            continue
        found = set()
        for row in rows:
            try:
                found.add(int(float(row.get("seed", ""))))
            except (TypeError, ValueError):
                continue
        if found:
            historical.update(found)
            sources.append({"path": str(path), "seeds": sorted(found)})
    allowed = set(map(int, protocol["intentional_historical_seed_reuse"]["seeds"]))
    unauthorized = {}
    blocks = protocol["seed_blocks"]
    for name, bounds in blocks.items():
        low, high = map(int, bounds)
        unauthorized[name] = sorted(
            seed for seed in historical if low <= seed <= high and seed not in allowed
        )
    overlaps = []
    names = list(blocks)
    for left_index, left in enumerate(names):
        ll, lh = map(int, blocks[left])
        for right in names[left_index + 1 :]:
            rl, rh = map(int, blocks[right])
            if max(ll, rl) <= min(lh, rh):
                overlaps.append([left, right])
    return {
        "passed": not any(unauthorized.values()) and not overlaps,
        "historical_sources": sources,
        "allowed_intentional_reuse": sorted(allowed),
        "unauthorized_historical_collisions": unauthorized,
        "internal_block_overlaps": overlaps,
    }


def run(project: Path, protocol: dict, run_dir: Path) -> dict:
    started = time.perf_counter()
    output = run_dir / "f0"
    output.mkdir(parents=True, exist_ok=False)
    processes = process_snapshot()
    own = [
        row
        for row in processes
        if int(row.get("ProcessId", -1)) == os.getpid()
        or "koopman_focus\\scripts\\run.py" in str(row.get("CommandLine", ""))
    ]
    unknown = [row for row in processes if row not in own]
    disk = shutil.disk_usage(project)
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    environment = {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "python_executable": sys.executable,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": gpu_name,
        "cuda_runtime": torch.version.cuda,
        "disk_free_gib": disk.free / 1024**3,
        "python_matlab_processes": processes,
        "unknown_python_matlab_processes": unknown,
        "git_repository": (project / ".git").exists(),
    }
    write_json(output / "environment.json", environment)

    historical_root = project / Path(protocol["historical_source_root"])
    plant_root = project / Path(protocol["plant_source_root"])
    historical_sha = json_sha256(source_manifest(historical_root))
    plant_sha = json_sha256(source_manifest(plant_root))
    source_identity = {
        "historical_source_manifest_sha256": historical_sha,
        "historical_source_expected_sha256": protocol["historical_source_manifest_sha256"],
        "historical_source_passed": historical_sha == protocol["historical_source_manifest_sha256"],
        "plant_source_manifest_sha256": plant_sha,
        "plant_source_expected_sha256": protocol["plant_source_manifest_sha256"],
        "plant_source_passed": plant_sha == protocol["plant_source_manifest_sha256"],
        "focus_source_manifest": source_manifest(ROOT),
        "focus_source_manifest_sha256": json_sha256(source_manifest(ROOT)),
    }
    write_json(output / "source_identity.json", source_identity)

    parent = protocol["parent_p2"]
    parent_run = project / Path(parent["run_root"])
    checks = {
        "complete": (parent_run / "complete.json", parent["complete_sha256"]),
        "manifest": (parent_run / "p2" / "data_manifest.csv", parent["manifest_sha256"]),
        "physics_audit": (parent_run / "p2" / "physics_audit_v2.csv", parent["physics_audit_sha256"]),
        "independent_audit": (parent_run / "p2" / "independent_audit.json", parent["independent_audit_sha256"]),
    }
    parent_files = []
    for name, (path, expected) in checks.items():
        actual = sha256(path) if path.exists() else None
        parent_files.append(
            {"name": name, "path": str(path), "expected_sha256": expected, "actual_sha256": actual, "passed": actual == expected}
        )
    manifest_path = checks["manifest"][0]
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as stream:
        manifest = list(csv.DictReader(stream))
    raw_root = project / Path(parent["data_root"])
    raw_rows = []
    for row in manifest:
        path = raw_root / Path(row["raw_path"]).name
        actual = file_sha256(path) if path.exists() else None
        raw_rows.append(
            {
                "trajectory_id": int(row["trajectory_id"]),
                "path": str(path),
                "expected_sha256": row["raw_file_sha256"],
                "actual_sha256": actual,
                "passed": actual == row["raw_file_sha256"],
            }
        )
    parent_evidence = {
        "files": parent_files,
        "raw": raw_rows,
        "manifest_row_count": len(manifest),
        "raw_hash_mismatch_count": sum(not row["passed"] for row in raw_rows),
        "passed": all(row["passed"] for row in parent_files)
        and len(manifest) == 24
        and all(row["passed"] for row in raw_rows),
    }
    write_json(output / "parent_evidence.json", parent_evidence)

    taskbook_sha = sha256(ROOT / "protocol.md")
    parent_taskbook_sha = sha256(ROOT / "parent_protocol.md")
    shutil.copy2(ROOT / "protocol.md", output / "protocol_snapshot.md")
    shutil.copy2(ROOT / "parent_protocol.md", output / "parent_protocol_snapshot.md")
    seed_audit = audit_seeds(project, protocol)
    write_json(output / "seed_audit.json", seed_audit)
    required_dirs = [
        project / "revision_2026" / "koopman_focus",
        project / "revision_2026" / "koopman_focus_data",
        project / "revision_2026" / "koopman_focus_models",
        project / "revision_2026" / "koopman_focus_results",
    ]
    passed = bool(
        environment["hostname"].upper() == protocol["project_host"].upper()
        and environment["cuda_available"]
        and "RTX 5080" in str(gpu_name)
        and environment["disk_free_gib"] >= float(protocol["resource_limits"]["minimum_free_gib"])
        and not unknown
        and not environment["git_repository"]
        and all(path.is_dir() for path in required_dirs)
        and source_identity["historical_source_passed"]
        and source_identity["plant_source_passed"]
        and parent_evidence["passed"]
        and taskbook_sha == protocol["taskbook_sha256"]
        and parent_taskbook_sha == protocol["parent_taskbook_sha256"]
        and seed_audit["passed"]
    )
    complete = {
        "stage": "F0",
        "passed": passed,
        "taskbook_sha256": taskbook_sha,
        "parent_taskbook_sha256": parent_taskbook_sha,
        "focus_source_manifest_sha256": source_identity["focus_source_manifest_sha256"],
        "historical_source_manifest_sha256": historical_sha,
        "plant_source_manifest_sha256": plant_sha,
        "parent_raw_count": len(raw_rows),
        "parent_raw_hash_mismatch_count": parent_evidence["raw_hash_mismatch_count"],
        "unknown_process_count": len(unknown),
        "seed_collision_count": sum(len(values) for values in seed_audit["unauthorized_historical_collisions"].values()),
        "free_gib": environment["disk_free_gib"],
        "runtime_s": time.perf_counter() - started,
        "artifacts": {
            "environment": str(output / "environment.json"),
            "source_identity": str(output / "source_identity.json"),
            "parent_evidence": str(output / "parent_evidence.json"),
            "seed_audit": str(output / "seed_audit.json"),
        },
    }
    if not passed:
        complete.update(
            {
                "repair_code": "F0_IDENTITY_ENVIRONMENT_OR_SEED_FAILED",
                "next_action": "Inspect F0 artifacts; do not run F1.",
            }
        )
    write_json(output / "complete.json", complete)
    return complete
