from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def json_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().upper()


def source_manifest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or any(
            part in {"__pycache__", ".pytest_cache"} for part in path.parts
        ):
            continue
        if path.suffix.lower() not in {".py", ".json", ".md"}:
            continue
        result[path.relative_to(root).as_posix()] = sha256(path)
    return result


@dataclass(frozen=True)
class RunContract:
    project_root: Path
    source_root: Path
    results_root: Path
    protocol_path: Path

    @property
    def protocol(self) -> dict:
        return json.loads(self.protocol_path.read_text(encoding="utf-8"))

    def input_identity(self) -> dict:
        manifest = source_manifest(self.source_root)
        return {
            "protocol_sha256": sha256(self.protocol_path),
            "source_manifest": manifest,
            "source_manifest_sha256": json_sha256(manifest),
        }

    def require_previous(self, stage: str) -> None:
        required = {"P0": (), "P1": ("P0",), "P2": ("P0", "P1")}.get(stage)
        if stage not in {"P0", "P1", "P2"}:
            raise ValueError(f"stage is outside current authorization: {stage}")
        if not required:
            return
        status_path = self.results_root / "stage_status.json"
        if not status_path.exists():
            raise RuntimeError(f"missing prior stage status for {stage}")
        status = json.loads(status_path.read_text(encoding="utf-8-sig"))
        current = self.input_identity()
        for prior_stage in required:
            prior = status.get("stages", {}).get(prior_stage, {})
            if prior.get("status") != "PASS":
                raise RuntimeError(f"{stage} requires {prior_stage}=PASS, found {prior}")
            complete_path = Path(prior.get("run_dir", "")) / "complete.json"
            if not complete_path.exists():
                raise RuntimeError(f"{stage} cannot verify {prior_stage}: missing {complete_path}")
            complete = json.loads(complete_path.read_text(encoding="utf-8-sig"))
            for key in ("protocol_sha256", "source_manifest_sha256"):
                if complete.get(key) != current[key]:
                    raise RuntimeError(
                        f"{stage} requires current-identity {prior_stage}; {key} "
                        f"expected {current[key]}, found {complete.get(key)}"
                    )
