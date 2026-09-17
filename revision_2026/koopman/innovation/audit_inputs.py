from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""): digest.update(block)
    return digest.hexdigest().upper()


def hash_frozen_inputs(paths: dict[str, Path]) -> dict[str, Any]:
    return {name: {"path": str(path), "sha256": sha256(path)} for name, path in paths.items()}


def locate_legacy_by_hash(project_root: Path, target: str) -> Path | None:
    for path in (project_root / "revision_2026").rglob("*.py"):
        if sha256(path) == target.upper(): return path
    return None


def _walk_seeds(value: Any, out: set[int]) -> None:
    if isinstance(value, dict):
        if "seed" in value:
            try: out.add(int(value["seed"]))
            except (TypeError, ValueError): pass
        for child in value.values(): _walk_seeds(child, out)
    elif isinstance(value, list):
        for child in value: _walk_seeds(child, out)


def audit_seed_collisions(manifest_paths: list[Path], requested: list[int]) -> dict[str, Any]:
    existing: set[int] = set(); read = []
    for path in manifest_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8")); _walk_seeds(data, existing); read.append(str(path))
        except Exception: continue
    collisions = sorted(existing & set(requested))
    return {"requested": requested, "existing_seed_count": len(existing), "collisions": collisions, "manifests_read": read}


def audit_d5_absent(results_root: Path) -> dict[str, Any]:
    target = results_root / "d5"
    source_mentions = []
    for path in results_root.parent.joinpath("innovation").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "d5" in text.lower() and path.name not in ("audit_inputs.py", "run_stage.py"): source_mentions.append(path.name)
    return {"d5_exists": target.exists(), "unexpected_source_mentions": source_mentions,
            "passed": not target.exists() and not source_mentions}


def write_code_map(paths: list[Path], output: Path) -> dict[str, Any]:
    entries = []
    lines = ["# Legacy code map", ""]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                row = {"file": str(path), "symbol": node.name, "kind": type(node).__name__,
                       "start": node.lineno, "end": getattr(node, "end_lineno", node.lineno)}
                entries.append(row); lines.append(f"- `{path.name}:{row['start']}-{row['end']}` `{row['symbol']}` ({row['kind']})")
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"entries": entries, "sha256": sha256(output)}


def schema() -> dict[str, Any]:
    vehicle_fields = ("x_m", "y_m", "yaw_rad", "vx_body_mps", "vy_body_mps", "yaw_rate_radps")
    names = []
    for car in ("FL", "FR", "RL", "RR"):
        names += [f"{car}.{field}" for field in vehicle_fields]
    names += [f"payload.{field}" for field in vehicle_fields]
    names += [f"connector.{car}.d{axis}_payload_body_m" for car in ("FL","FR","RL","RR") for axis in ("x","y")]
    names += [f"connector.{car}.vrel_{axis}_payload_body_mps" for car in ("FL","FR","RL","RR") for axis in ("x","y")]
    force = [f"payload_force.{car}.F{axis}_N" for car in ("FL","FR","RL","RR") for axis in ("x","y")]
    force += ["payload_load.Q_FR_N", "payload_load.Q_LR_N"]
    force += [f"payload_force_rate.{car}.dF{axis}_Nps" for car in ("FL","FR","RL","RR") for axis in ("x","y")]
    return {"state_s3": {"dim": 46, "names": names}, "state_main": {"dim": 30, "names": names[:30]},
            "control_u1": {"dim": 8, "order": [f"{car}.{x}" for car in ("FL","FR","RL","RR") for x in ("accel_mps2","steer_rad")]},
            "force_output": {"dim": 18, "names": force, "vehicle_order": ["FL","FR","RL","RR"], "component_order": ["Fx","Fy"]},
            "vehicle_side_force_independently_logged": False,
            "action_reaction_status": "not_identifiable_from_saved_contract"}

