"""F2: split-guard fault injection (E08/E09): F/M stages reading the old
validation or confirm must raise, and access is machine-logged."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from split_guard import SplitAccessDenied, SplitGuard


def _protocol_with_policy(stage_policy: dict) -> dict:
    return {"split_guards": {"F3": stage_policy}}


def test_f3_reading_validation_denied(tmp_path):
    guard = SplitGuard(tmp_path / "split_access.jsonl", _protocol_with_policy(
        {"train": "allow", "validation": "deny", "development": "deny", "confirm": "deny"}
    ), "F3")
    guard.assert_allowed("train", path="x", purpose="ok")
    with pytest.raises(SplitAccessDenied):
        guard.assert_allowed("validation", path="old_validation", purpose="AF stress")
    with pytest.raises(SplitAccessDenied):
        guard.assert_allowed("development", path="dev", purpose="selection")
    with pytest.raises(SplitAccessDenied):
        guard.assert_allowed("confirm", path="confirm", purpose="anything")
    records = [json.loads(line) for line in (tmp_path / "split_access.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 4
    assert records[0]["allowed"] is True
    assert records[1]["allowed"] is False and records[1]["split"] == "validation"


def test_stage_without_policy_defaults_to_deny(tmp_path):
    guard = SplitGuard(tmp_path / "split_access.jsonl", _protocol_with_policy({}), "F3")
    with pytest.raises(SplitAccessDenied):
        guard.assert_allowed("train", path="x", purpose="no policy")
