"""SHA-256 identity and host snapshot for the isolated run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import socket
import subprocess
import sys


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def tree_identity(paths: list[Path]) -> dict[str, str]:
    result = {}
    for path in paths:
        if path.is_file(): result[str(path)] = sha256(path)
    return result


def snapshot(project: Path, config: dict) -> dict:
    gpu = "unavailable"
    try:
        gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], text=True, timeout=20).strip()
    except Exception as exc:
        gpu = f"query_failed:{type(exc).__name__}"
    return {"host": socket.gethostname(), "host_role": config["host_role"], "platform": platform.platform(),
            "python": sys.executable, "python_version": sys.version, "gpu": gpu,
            "cuda_visible_devices": __import__("os").environ.get("CUDA_VISIBLE_DEVICES", ""),
            "project": str(project), "protocol_id": config["protocol_id"]}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

