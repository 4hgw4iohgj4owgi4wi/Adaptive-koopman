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


def process_snapshot() -> list[dict]:
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object {$_.Name -match 'python|matlab'} | "
        "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 3"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"process audit failed: {completed.stderr}")
    raw = completed.stdout.strip()
    if not raw:
        return []
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else [parsed]


def nvidia_snapshot() -> dict:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total,memory.used",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def historical_seeds(project: Path) -> tuple[set[int], list[dict]]:
    values: set[int] = set()
    sources: list[dict] = []
    revision = project / "revision_2026"
    for path in sorted(revision.rglob("*manifest*.csv")):
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
        except (OSError, UnicodeError, csv.Error):
            continue
        if not rows or "seed" not in rows[0]:
            continue
        found = set()
        for row in rows:
            try:
                found.add(int(float(row.get("seed", ""))))
            except (TypeError, ValueError):
                continue
        if found:
            values.update(found)
            sources.append(
                {
                    "path": str(path),
                    "count": len(found),
                    "minimum": min(found),
                    "maximum": max(found),
                }
            )
    return values, sources


def audit_parameter_sources(protocol: dict, freeze_dir: Path) -> dict:
    rows = []
    for source in protocol["actuator_parameter_sources"]:
        snapshot = ROOT / Path(source["snapshot_relative_path"])
        first_hash = sha256(snapshot) if snapshot.exists() else None
        second_hash = sha256(snapshot) if snapshot.exists() else None
        content = snapshot.read_text(encoding="utf-8").splitlines() if snapshot.exists() else []
        line_checks = []
        for expected in source["lines"]:
            number = int(expected["line"])
            actual = content[number - 1].strip() if 0 < number <= len(content) else None
            line_checks.append(
                {
                    **expected,
                    "actual_text": actual,
                    "passed": actual == expected["text"],
                }
            )
        passed = bool(
            first_hash == second_hash == source["sha256"].upper()
            and line_checks
            and all(item["passed"] for item in line_checks)
        )
        rows.append(
            {
                **source,
                "snapshot_path": str(snapshot),
                "first_sha256": first_hash,
                "second_sha256": second_hash,
                "line_checks": line_checks,
                "calibration_status": protocol["actuator"]["status"],
                "passed": passed,
            }
        )
    result = {"passed": bool(rows and all(row["passed"] for row in rows)), "sources": rows}
    write_json(freeze_dir / "actuator_parameter_sources.json", result)
    return result


def audit_seeds(project: Path, protocol: dict, freeze_dir: Path) -> dict:
    historical, sources = historical_seeds(project)
    blocks = protocol["seed_blocks"]
    allowed = set(map(int, protocol["intentional_historical_seed_reuse"]["seeds"]))
    collisions = {}
    unauthorized = {}
    for name, bounds in blocks.items():
        low, high = map(int, bounds)
        values = sorted(value for value in historical if low <= value <= high)
        collisions[name] = values
        unauthorized[name] = sorted(set(values) - allowed)
    overlaps = []
    names = list(blocks)
    for left_index, left in enumerate(names):
        left_low, left_high = map(int, blocks[left])
        for right in names[left_index + 1 :]:
            right_low, right_high = map(int, blocks[right])
            if max(left_low, right_low) <= min(left_high, right_high):
                overlaps.append([left, right])
    result = {
        "passed": not any(unauthorized.values()) and not overlaps,
        "historical_unique_seed_count": len(historical),
        "historical_sources": sources,
        "registered_blocks": blocks,
        "historical_collisions": collisions,
        "allowed_intentional_reuse": sorted(allowed),
        "unauthorized_historical_collisions": unauthorized,
        "internal_block_overlaps": overlaps,
    }
    write_json(freeze_dir / "seed_audit.json", result)
    return result


def run(project: Path, protocol: dict, run_dir: Path) -> dict:
    started = time.perf_counter()
    freeze_dir = run_dir / "freeze"
    freeze_dir.mkdir(parents=True, exist_ok=False)
    for relative in (
        "revision_2026/koopman_next_v2_data/p2",
        "revision_2026/koopman_next_v2_models",
        "revision_2026/koopman_next_v2_results",
    ):
        (project / relative).mkdir(parents=True, exist_ok=True)

    processes = process_snapshot()
    self_processes = [
        item
        for item in processes
        if int(item.get("ProcessId", -1)) == os.getpid()
        or "koopman_next_v2\\scripts\\run.py" in str(item.get("CommandLine", ""))
    ]
    unknown = [item for item in processes if item not in self_processes]
    disk = shutil.disk_usage(project)
    environment = {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "python_executable": sys.executable,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "cuda_runtime": torch.version.cuda,
        "disk_free_bytes": disk.free,
        "disk_free_gib": disk.free / 1024**3,
        "python_matlab_processes": processes,
        "unknown_python_matlab_processes": unknown,
        "nvidia_smi": nvidia_snapshot(),
        "git_repository": (project / ".git").exists(),
    }
    write_json(freeze_dir / "environment.json", environment)

    hash_rows = []
    for relative, expected in protocol["expected_upstream_sha256"].items():
        path = project / Path(relative)
        actual = sha256(path) if path.exists() else None
        hash_rows.append(
            {
                "relative_path": relative,
                "path": str(path),
                "expected_sha256": expected.upper(),
                "actual_sha256": actual,
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else None,
                "passed": actual == expected.upper(),
            }
        )
    historical_source = project / Path(protocol["historical_source_root"])
    historical_manifest = source_manifest(historical_source) if historical_source.exists() else {}
    historical_manifest_sha = json_sha256(historical_manifest) if historical_manifest else None
    historical_passed = (
        historical_manifest_sha == protocol["historical_source_manifest_sha256"].upper()
    )
    source_hashes = {
        "passed": bool(all(row["passed"] for row in hash_rows) and historical_passed),
        "files": hash_rows,
        "historical_source_root": str(historical_source),
        "historical_source_manifest_sha256": historical_manifest_sha,
        "expected_historical_source_manifest_sha256": protocol[
            "historical_source_manifest_sha256"
        ].upper(),
        "historical_source_passed": historical_passed,
    }
    write_json(freeze_dir / "source_hashes.json", source_hashes)
    actuator_sources = audit_parameter_sources(protocol, freeze_dir)
    seed_audit = audit_seeds(project, protocol, freeze_dir)

    snapshot = freeze_dir / "protocol_snapshot.md"
    shutil.copy2(ROOT / "protocol.md", snapshot)
    taskbook_sha = sha256(ROOT / "protocol.md")
    taskbook_match = taskbook_sha == protocol["taskbook_sha256"].upper()
    minimum_free = float(protocol["resource_limits"]["minimum_free_gib"])
    passed = bool(
        environment["hostname"].upper() == protocol["project_host"].upper()
        and environment["cuda_available"]
        and "RTX 5080" in str(environment["gpu"])
        and environment["disk_free_gib"] >= minimum_free
        and not unknown
        and source_hashes["passed"]
        and actuator_sources["passed"]
        and seed_audit["passed"]
        and not environment["git_repository"]
        and taskbook_match
    )
    complete = {
        "stage": "P0",
        "passed": passed,
        "environment_path": str(freeze_dir / "environment.json"),
        "source_hashes_path": str(freeze_dir / "source_hashes.json"),
        "actuator_parameter_sources_path": str(
            freeze_dir / "actuator_parameter_sources.json"
        ),
        "seed_audit_path": str(freeze_dir / "seed_audit.json"),
        "protocol_snapshot_path": str(snapshot),
        "upstream_hash_count": len(hash_rows),
        "upstream_hash_mismatch_count": sum(not row["passed"] for row in hash_rows),
        "unknown_process_count": len(unknown),
        "seed_collision_count": sum(
            len(value) for value in seed_audit["unauthorized_historical_collisions"].values()
        ),
        "taskbook_sha256": taskbook_sha,
        "taskbook_hash_match": taskbook_match,
        "actuator_parameter_status": protocol["actuator"]["status"],
        "free_gib": environment["disk_free_gib"],
        "runtime_s": time.perf_counter() - started,
    }
    if not passed:
        complete.update(
            {
                "repair_code": "P0_FREEZE_IDENTITY_OR_ENVIRONMENT_FAILED",
                "next_action": (
                    "Inspect environment/source hashes/actuator sources/seed audit; "
                    "do not run P1."
                ),
            }
        )
    write_json(freeze_dir / "complete.json", complete)
    return complete
