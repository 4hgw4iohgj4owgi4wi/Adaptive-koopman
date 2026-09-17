from __future__ import annotations
from pathlib import Path


ORDER = {"train": 0, "validation": 1, "development": 2, "confirm": 3}


def assert_can_read(split: str, state_dir: Path) -> None:
    if split == "development" and not (state_dir / "model_frozen.json").exists():
        raise PermissionError("development requires frozen validation-selected model")
    if split == "confirm" and not (state_dir / "development_passed.json").exists():
        raise PermissionError("confirm requires passed development")
