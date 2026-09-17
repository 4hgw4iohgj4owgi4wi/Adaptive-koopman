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

from contracts import sha256, write_json


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
    value = completed.stdout.strip()
    if not value:
        return []
    parsed = json.loads(value)
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
        relative = path.relative_to(revision)
        if relative.parts and relative.parts[0] in {"koopman_next_data", "koopman_next_results"}:
            continue
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
        except (OSError, UnicodeError, csv.Error):
            continue
        if not rows or "seed" not in rows[0]:
            continue
        file_values: set[int] = set()
        for row in rows:
            raw = row.get("seed", "")
            if raw in {"", None}:
                continue
            try:
                file_values.add(int(float(raw)))
            except ValueError:
                continue
        if file_values:
            values.update(file_values)
            sources.append(
                {
                    "path": str(path),
                    "count": len(file_values),
                    "minimum": min(file_values),
                    "maximum": max(file_values),
                }
            )
    return values, sources


def run(project: Path, protocol: dict, run_dir: Path) -> dict:
    started = time.perf_counter()
    freeze_dir = run_dir / "freeze"
    freeze_dir.mkdir(parents=True, exist_ok=False)
    for relative in (
        "revision_2026/koopman_next_data/pilot",
        "revision_2026/koopman_next_data/full",
        "revision_2026/koopman_next_data/confirm",
        "revision_2026/koopman_next_models",
        "revision_2026/koopman_next_results",
        "revision_2026/koopman_next_mpc",
    ):
        (project / relative).mkdir(parents=True, exist_ok=True)

    processes = process_snapshot()
    self_processes = [
        item
        for item in processes
        if int(item.get("ProcessId", -1)) == os.getpid()
        or "koopman_next\\scripts\\run.py" in str(item.get("CommandLine", ""))
    ]
    unknown_processes = [item for item in processes if item not in self_processes]
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
        "unknown_python_matlab_processes": unknown_processes,
        "nvidia_smi": nvidia_snapshot(),
        "git_repository": (project / ".git").exists(),
    }
    write_json(freeze_dir / "environment.json", environment)

    hash_rows = []
    all_hashes_pass = True
    for relative, expected in protocol["expected_upstream_sha256"].items():
        path = project / Path(relative)
        actual = sha256(path) if path.exists() else None
        passed = actual == expected.upper()
        all_hashes_pass &= passed
        hash_rows.append(
            {
                "relative_path": relative,
                "path": str(path),
                "expected_sha256": expected.upper(),
                "actual_sha256": actual,
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else None,
                "passed": passed,
            }
        )
    write_json(freeze_dir / "source_hashes.json", {"passed": all_hashes_pass, "files": hash_rows})

    historical, sources = historical_seeds(project)
    blocks = protocol["seed_blocks"]
    block_collisions = {}
    internal_overlaps = []
    names = list(blocks)
    for name, bounds in blocks.items():
        low, high = map(int, bounds)
        collision = sorted(value for value in historical if low <= value <= high)
        block_collisions[name] = collision
    for left_index, left in enumerate(names):
        left_low, left_high = map(int, blocks[left])
        for right in names[left_index + 1 :]:
            right_low, right_high = map(int, blocks[right])
            if max(left_low, right_low) <= min(left_high, right_high):
                internal_overlaps.append([left, right])
    seed_passed = not any(block_collisions.values()) and not internal_overlaps
    seed_audit = {
        "passed": seed_passed,
        "historical_unique_seed_count": len(historical),
        "historical_seed_min": min(historical) if historical else None,
        "historical_seed_max": max(historical) if historical else None,
        "historical_sources": sources,
        "registered_blocks": blocks,
        "historical_collisions": block_collisions,
        "internal_block_overlaps": internal_overlaps,
    }
    write_json(freeze_dir / "seed_audit.json", seed_audit)

    snapshot = freeze_dir / "protocol.md"
    shutil.copy2(ROOT / "protocol.md", snapshot)
    os.chmod(snapshot, 0o444)
    taskbook_sha256 = sha256(ROOT / "protocol.md")
    taskbook_match = taskbook_sha256 == str(protocol["taskbook_sha256"]).upper()
    minimum_free = float(protocol["resource_limits"]["minimum_free_gib"])
    passed = bool(
        environment["hostname"].upper() == protocol["project_host"].upper()
        and environment["cuda_available"]
        and "RTX 5080" in str(environment["gpu"])
        and environment["disk_free_gib"] >= minimum_free
        and not unknown_processes
        and all_hashes_pass
        and seed_passed
        and not environment["git_repository"]
        and taskbook_match
    )
    complete = {
        "stage": "K0",
        "passed": passed,
        "environment_path": str(freeze_dir / "environment.json"),
        "source_hashes_path": str(freeze_dir / "source_hashes.json"),
        "seed_audit_path": str(freeze_dir / "seed_audit.json"),
        "protocol_snapshot_path": str(snapshot),
        "upstream_hash_count": len(hash_rows),
        "upstream_hash_mismatch_count": sum(not row["passed"] for row in hash_rows),
        "unknown_process_count": len(unknown_processes),
        "seed_collision_count": sum(len(value) for value in block_collisions.values()),
        "taskbook_sha256": taskbook_sha256,
        "taskbook_hash_match": taskbook_match,
        "free_gib": environment["disk_free_gib"],
        "runtime_s": time.perf_counter() - started,
    }
    if not passed:
        complete.update(
            {
                "repair_code": "K0_FREEZE_IDENTITY_OR_ENVIRONMENT_FAILED",
                "next_action": "Inspect environment/source_hashes/seed_audit; do not create data or models.",
            }
        )
    write_json(freeze_dir / "complete.json", complete)
    return complete
