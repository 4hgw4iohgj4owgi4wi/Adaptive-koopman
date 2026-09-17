from __future__ import annotations

"""Koopman predict v2 common contracts: identity hashing, JSON/CSV IO, run allocation."""

import csv
import hashlib
import json
import os
import platform
import shutil
import time
from datetime import datetime
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def file_sha256(path: Path) -> str:
    return sha256(path)


def json_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _plain(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, np.ndarray):
        return _plain(value.tolist())
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_plain(value), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_plain(value), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refuse to write empty CSV: {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows([_plain(row) for row in rows])
    os.replace(temporary, path)


def append_log(path: Path, heading: str, facts: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n## {datetime.now().astimezone().isoformat(timespec='seconds')} — {heading}\n\n"
            f"- 主机：`{platform.node()}`\n"
            f"- 命令：`{' '.join(__import__('sys').argv)}`\n"
            f"- 事实：`{json.dumps(_plain(facts), ensure_ascii=False, allow_nan=False)}`\n"
        )


def append_decision(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(_plain(payload), ensure_ascii=False, allow_nan=False) + "\n")


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def array_sha256(arrays: dict[str, np.ndarray], keys: list[str] | None = None) -> str:
    digest = hashlib.sha256()
    for key in sorted(keys if keys is not None else arrays):
        value = np.asarray(arrays[key])
        digest.update(str(key).encode("utf-8"))
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        if value.dtype.kind in {"O", "U", "S"}:
            digest.update(json.dumps(value.tolist(), sort_keys=True, ensure_ascii=False).encode("utf-8"))
        else:
            digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest().upper()


def allocate_run(results_root: Path, run_tag: str) -> Path:
    runs = results_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for revision in range(1, 100):
        candidate = runs / f"{stamp}_KOOPMAN_V2_{run_tag}_R{revision:02d}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError("cannot allocate unique v2 run")


def resolve_resume(results_root: Path, value: str) -> Path:
    selected = Path(value)
    if not selected.is_absolute():
        selected = results_root / "runs" / selected
    selected = selected.resolve()
    if selected.parent != (results_root / "runs").resolve() or not selected.is_dir():
        raise ValueError(f"invalid resume run: {selected}")
    return selected


def disk_free_gib(path: Path) -> float:
    usage = shutil.disk_usage(Path(path).anchor)
    return usage.free / 1024**3


def environment_manifest(project_root: Path) -> dict:
    import numpy as np

    result = {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python_executable": __import__("sys").executable,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "cwd": str(Path.cwd()),
        "project_root": str(project_root),
        "disk_free_gib": disk_free_gib(project_root),
        "now": datetime.now().astimezone().isoformat(timespec="seconds"),
        "thread_environment": {
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
        },
    }
    return result
