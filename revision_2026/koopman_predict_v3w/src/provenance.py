"""Attempt-level immutable provenance (E07/E14/E18).

Every attempt writes source/protocol/taskbook/data identities once; a second
write to the same path raises.  Artifact manifests enumerate products with
sizes and SHA256 so evidence packages close (E18) and raw rows are never
replaced by summaries (E14).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def json_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def write_once(path: Path, value: dict) -> None:
    if path.exists():
        raise RuntimeError(f"refuse to overwrite immutable artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def source_manifest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or any(
            part in {"__pycache__", ".pytest_cache", "runs", "results", "models", "checkpoints"}
            for part in path.parts
        ):
            continue
        if path.suffix.lower() in {".pyc", ".tmp", ".lock", ".partial"}:
            continue
        if path.suffix.lower() not in {".py", ".json", ".md"}:
            continue
        result[path.relative_to(root).as_posix()] = sha256_file(path)
    return result


def artifact_manifest(directory: Path, pattern: str = "*") -> dict:
    manifest: dict[str, object] = {"directory": str(directory), "artifacts": []}
    for path in sorted(Path(directory).rglob(pattern)):
        if path.is_file() and path.suffix != ".tmp":
            manifest["artifacts"].append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest["sha256"] = json_sha256({item["path"]: item["sha256"] for item in manifest["artifacts"]})
    return manifest
