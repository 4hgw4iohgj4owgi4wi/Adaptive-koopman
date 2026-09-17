from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from contracts import build_future_split_ledger
from dataset import (
    normalization_from_visible_train,
    trajectory_window_records,
    validate_base_family_split_contract,
)


ROOT = Path(__file__).resolve().parents[1]


def test_family_isolation_and_fault_injection() -> None:
    family = np.asarray(["a", "a", "b", "b"])
    split = np.asarray(["train", "train", "validation", "validation"])
    assert validate_base_family_split_contract(family, split)["passed"]
    leaked = split.copy()
    leaked[1] = "validation"
    with pytest.raises(ValueError, match="cross splits"):
        validate_base_family_split_contract(family, leaked)


def test_normalization_is_train_only_and_confirm_is_invisible() -> None:
    combined = {
        "split": np.asarray(["train", "train", "validation", "development"]),
        "state": np.asarray([[1.0], [3.0], [100.0], [200.0]]),
    }
    normalization = normalization_from_visible_train(combined, ("state",))
    np.testing.assert_allclose(normalization["state_mean"], [2.0])
    np.testing.assert_allclose(normalization["state_scale"], [1.0])
    with pytest.raises(ValueError, match="confirm"):
        normalization_from_visible_train(
            {"split": np.asarray(["train", "confirm"]), "state": np.asarray([[1.0], [2.0]])},
            ("state",),
        )


def test_windows_cannot_cross_trajectory_endpoint() -> None:
    rows = trajectory_window_records(
        trajectory_id="T1",
        source_index=np.arange(45),
        control_signal=np.r_[np.zeros((20, 1)), np.ones((25, 1))],
        connector_event_signal=np.zeros((45, 1)),
        steps=20,
    )
    assert len(rows) == 2
    assert all(row["within_single_trajectory"] for row in rows)
    assert rows[-1]["source_index_end"] == 39
    with pytest.raises(ValueError, match="contiguous"):
        trajectory_window_records(
            trajectory_id="bad",
            source_index=np.asarray([0, 1, 9, 10]),
            control_signal=np.zeros((4, 1)),
            connector_event_signal=np.zeros((4, 1)),
            steps=2,
        )


def test_future_split_ledger_hides_confirm() -> None:
    protocol = json.loads(
        (ROOT / "config" / "protocol_predict_next.json").read_text(encoding="utf-8")
    )
    ledger = build_future_split_ledger(protocol)
    assert ledger["audit"]["visible_base_family_count"] == 192
    assert ledger["confirm"]["visible"] is False
    assert ledger["audit"]["confirm_visible_row_count"] == 0
    with pytest.raises(PermissionError, match="invisible"):
        build_future_split_ledger(protocol, include_confirm=True)

