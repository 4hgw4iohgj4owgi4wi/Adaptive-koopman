from pathlib import Path
import json
import pytest

from contracts import validate_protocol


@pytest.mark.batch_q1
def test_protocol_freezes_q1_without_training():
    p=Path(__file__).resolve().parents[1]/"config"/"protocol.json"
    cfg=validate_protocol(p)
    assert cfg["training_allowed"] is False
    assert cfg["candidate_states"]==90 and cfg["next_stage"]=="STOP_AFTER_K1_VERDICT"


@pytest.mark.batch_q1
def test_worker_preserves_integer_child_exit():
    source=(Path(__file__).resolve().parents[1]/"scripts"/"worker.ps1").read_text(encoding="utf-8")
    assert "$code=[int]$LASTEXITCODE" in source
    assert "exit $code" in source


@pytest.mark.batch_q1
def test_launcher_is_once_and_q1_only():
    source=(Path(__file__).resolve().parents[1]/"scripts"/"launch.ps1").read_text(encoding="utf-8")
    assert "New-ScheduledTaskTrigger -Once" in source
    assert "ValidateSet('Q1')" in source
