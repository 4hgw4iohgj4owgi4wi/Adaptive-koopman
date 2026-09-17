"""Checkpoint save/load/validate with full identity and training state.

Fixes E01 (best vs last), E02 (best_step vs stop_step), E04 (resume exactness:
model/optimizer/best/patience/RNG/sampler position), E05 (fold_complete flag).
Every checkpoint carries source/taskbook/protocol/data SHA so loading a
checkpoint from another identity is refused (E06).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from pathlib import Path

import numpy as np
import torch


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _plain(value):
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, np.ndarray):
        return _plain(value.tolist())
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def snapshot_rng() -> dict:
    numpy_state = np.random.get_state()
    state = {
        "python_random": random.getstate(),
        "numpy": [numpy_state[0], numpy_state[1].tolist(), int(numpy_state[2]), int(numpy_state[3]), float(numpy_state[4])],
        "torch_cpu": torch.get_rng_state().tolist(),
        "torch_cuda": [torch.cuda.get_rng_state_all()[0].tolist()] if torch.cuda.is_available() else [],
    }
    return _plain(state)


def _as_nested_tuples(value):
    """JSON round-trips tuples into lists; python random needs tuples back."""
    if isinstance(value, list):
        return tuple(_as_nested_tuples(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_as_nested_tuples(item) for item in value)
    if isinstance(value, dict):
        return {key: _as_nested_tuples(item) for key, item in value.items()}
    return value


def restore_rng(state: dict) -> None:
    random.setstate(_as_nested_tuples(state["python_random"]))
    numpy_state = state["numpy"]
    np.random.set_state((numpy_state[0], np.asarray(numpy_state[1], dtype=np.uint32), int(numpy_state[2]), int(numpy_state[3]), float(numpy_state[4])))
    torch.set_rng_state(torch.ByteTensor(state["torch_cpu"]))
    if torch.cuda.is_available() and state.get("torch_cuda"):
        torch.cuda.set_rng_state_all([torch.ByteTensor(state["torch_cuda"][0])])


class EarlyStopState:
    def __init__(self, best_metric: float = float("inf"), best_step: int = 0, patience_counter: int = 0, patience: int = 2000, last_check_step: int = 0):
        self.best_metric = float(best_metric)
        self.best_step = int(best_step)
        self.patience_counter = int(patience_counter)
        self.patience = int(patience)
        self.last_check_step = int(last_check_step)

    def to_dict(self) -> dict:
        return {
            "best_metric": self.best_metric,
            "best_step": self.best_step,
            "patience_counter": self.patience_counter,
            "patience": self.patience,
            "last_check_step": self.last_check_step,
        }

    @staticmethod
    def from_dict(value: dict) -> "EarlyStopState":
        return EarlyStopState(
            best_metric=float(value.get("best_metric", float("inf"))),
            best_step=int(value.get("best_step", 0)),
            patience_counter=int(value.get("patience_counter", 0)),
            patience=int(value.get("patience", 2000)),
            last_check_step=int(value.get("last_check_step", 0)),
        )

    def observe(self, metric: float, step: int) -> bool:
        """Return True when the metric improved at this check."""
        if float(metric) < self.best_metric - 1e-12:
            self.best_metric = float(metric)
            self.best_step = int(step)
            self.patience_counter = 0
            improved = True
        else:
            self.patience_counter += int(step) - self.last_check_step
            improved = False
        self.last_check_step = int(step)
        return improved

    def should_stop(self) -> bool:
        return self.patience_counter >= self.patience


def save_checkpoint(
    path: Path,
    *,
    run_id: str,
    attempt_id: str,
    stage: str,
    variant: str,
    fold: int,
    seed: int,
    identity: dict,
    kind: str,
    model,
    optimizer=None,
    step: int = 0,
    best: EarlyStopState | None = None,
    sampler_position: int = 0,
    loss_curve: list | None = None,
    is_fold_complete: bool = False,
) -> None:
    """kind in {'warm','best','last'}."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "attempt_id": attempt_id,
        "stage": stage,
        "variant": variant,
        "fold": int(fold),
        "seed": int(seed),
        "kind": kind,
        "step": int(step),
        "sampler_position": int(sampler_position),
        "best": None if best is None else best.to_dict(),
        "best_step": None if best is None else best.best_step,
        "stop_step": int(step) if kind == "last" else None,
        "best_metric": None if best is None else best.best_metric,
        "patience_counter": None if best is None else best.patience_counter,
        "is_fold_complete": bool(is_fold_complete),
        "identity": _plain(identity),
        "rng_state": snapshot_rng(),
        "loss_curve": [] if loss_curve is None else _plain(loss_curve),
    }
    sidecar = path.with_suffix(".json")
    temporary_sidecar = sidecar.with_suffix(".json.tmp")
    temporary_sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary_sidecar, sidecar)
    torch.save(
        {
            "model_state": model.state_dict(),
            "optimizer_state": None if optimizer is None else optimizer.state_dict(),
        },
        path,
    )
    payload["model_sha256"] = _sha256_bytes(Path(path).read_bytes())
    # rewrite sidecar with the model sha (atomic, single write after all bytes stable)
    temporary_sidecar = sidecar.with_suffix(".json.tmp")
    temporary_sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary_sidecar, sidecar)


def validate_checkpoint_identity(sidecar: dict, *, expected: dict) -> None:
    for key in ("run_id", "stage", "variant", "fold", "seed"):
        if str(sidecar.get(key)) != str(expected.get(key)):
            raise RuntimeError(f"checkpoint identity mismatch on {key}: {sidecar.get(key)} vs {expected.get(key)}")
    identity = sidecar.get("identity") or {}
    for key in ("taskbook_sha256", "protocol_sha256", "source_manifest_sha256", "data_manifest_sha256"):
        if identity.get(key) != expected.get(key):
            raise RuntimeError(f"checkpoint {key} mismatch: {identity.get(key)} vs {expected.get(key)}")


def load_checkpoint(path: Path) -> dict:
    sidecar = json.loads(Path(path).with_suffix(".json").read_text(encoding="utf-8"))
    if str(sidecar.get("model_sha256", "")).upper() != _sha256_bytes(Path(path).read_bytes()):
        raise RuntimeError(f"checkpoint model SHA mismatch: {path}")
    payload = torch.load(path, map_location="cpu")
    return {"sidecar": sidecar, "model_state": payload["model_state"], "optimizer_state": payload.get("optimizer_state")}


def atomic_json_no_overwrite(path: Path, value: dict) -> None:
    """E07: immutable per-attempt artifacts; refuse to overwrite."""
    if path.exists():
        raise RuntimeError(f"refuse to overwrite immutable artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(_plain(value), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)
