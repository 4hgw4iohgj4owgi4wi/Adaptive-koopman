from __future__ import annotations

import json
from pathlib import Path

import pytest

from repair import load_config


def test_kr_a_protocol_is_bounded():
    root = Path(__file__).resolve().parents[1]
    cfg = load_config(root / "config/repair.json")
    assert cfg["training_allowed"] is False
    assert cfg["confirmation_allowed"] is False
    assert cfg["gamma_states"] == 330
    assert cfg["maximum_seen_outer_replays"] == 60


def test_kr_a_rejects_changed_grid(tmp_path):
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root / "config/repair.json").read_text(encoding="utf-8"))
    cfg["gamma_grid"] = cfg["gamma_grid"][:-1]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError, match="gamma grid"):
        load_config(path)


def test_kr_a_rejects_training_authority(tmp_path):
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root / "config/repair.json").read_text(encoding="utf-8"))
    cfg["training_allowed"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(ValueError, match="authority"):
        load_config(path)
