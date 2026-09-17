from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np


PARAMETER_UNITS = {
    "vehicle.mass_kg": "kg",
    "vehicle.yaw_inertia_kgm2": "kg*m^2",
    "vehicle.lf_m": "m",
    "vehicle.lr_m": "m",
    "vehicle.cf_nprad": "N/rad",
    "vehicle.cr_nprad": "N/rad",
    "vehicle.mu": "1",
    "vehicle.gravity_mps2": "m/s^2",
    "payload.mass_kg": "kg",
    "payload.length_m": "m",
    "payload.width_m": "m",
    "payload.cog_height_m": "m",
    "payload.gravity_mps2": "m/s^2",
    "payload.yaw_inertia_kgm2": "kg*m^2",
    "connector.stiffness_npm": "N/m",
    "connector.damping_nspm": "N*s/m",
    "connector.free_play_m": "m",
    "connector.smoothing_width_m": "m",
    "connector.rated_force_n": "N",
    "connector.ultimate_force_n": "N",
    "vehicle_anchor_body_m": "m",
}


def _plain(value: object) -> object:
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, np.ndarray):
        return _plain(value.tolist())
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, float):
        if not np.isfinite(value):
            raise ValueError("non-finite parameter")
        return float(value)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"unsupported canonical value: {type(value)!r}")


def canonical_json(value: object) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def canonical_params(params: object) -> dict:
    payload = _plain(params)
    if not isinstance(payload, dict):
        raise TypeError("ModelParams must canonicalize to a mapping")
    payload.setdefault("derived", {})
    payload["derived"]["payload_yaw_inertia_kgm2"] = float(params.payload.yaw_inertia_kgm2)
    return {
        "schema": "ModelParams.resolved.v1",
        "values": payload,
        "units": dict(PARAMETER_UNITS),
    }


def params_sha256(params: object) -> str:
    return text_sha256(canonical_json(canonical_params(params)))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def array_sha256(arrays: Mapping[str, np.ndarray], keys: Iterable[str] | None = None) -> str:
    digest = hashlib.sha256()
    selected = sorted(keys if keys is not None else arrays)
    for key in selected:
        value = np.asarray(arrays[key])
        digest.update(str(key).encode("utf-8"))
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        if value.dtype.kind in {"O", "U", "S"}:
            digest.update(canonical_json(value.tolist()).encode("utf-8"))
        else:
            digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest().upper()


def assign_split(base_family_id: str, registered: Mapping[str, str]) -> str:
    if base_family_id not in registered:
        raise KeyError(f"unregistered base family: {base_family_id}")
    split = str(registered[base_family_id])
    if split not in {"train", "validation"}:
        raise ValueError(f"K2 split must be train/validation, found {split}")
    return split


def validate_manifest(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("empty data manifest")
    splits: dict[str, set[str]] = {}
    members: dict[str, set[tuple[str, str]]] = {}
    trajectory_ids = set()
    duplicate_trajectory_ids = 0
    missing_parameter_identity = 0
    for row in rows:
        base = str(row["base_family_id"])
        splits.setdefault(base, set()).add(str(row["split"]))
        members.setdefault(base, set()).add((str(row["direction"]), str(row["plant"])))
        trajectory_id = int(row["trajectory_id"])
        duplicate_trajectory_ids += int(trajectory_id in trajectory_ids)
        trajectory_ids.add(trajectory_id)
        missing_parameter_identity += int(not row.get("params_json") or not row.get("params_sha256"))
    cross = {base: sorted(values) for base, values in splits.items() if len(values) != 1}
    return {
        "row_count": len(rows),
        "base_family_count": len(splits),
        "cross_split_base_family_count": len(cross),
        "cross_split_base_families": cross,
        "duplicate_trajectory_id_count": duplicate_trajectory_ids,
        "missing_parameter_identity_count": missing_parameter_identity,
        "base_family_members": {
            base: [list(item) for item in sorted(values)] for base, values in sorted(members.items())
        },
        "allowed_splits": ["train", "validation"],
        "normalization_source_splits": ["train"],
    }
