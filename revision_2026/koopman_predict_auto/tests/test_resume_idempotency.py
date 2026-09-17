import json
from pathlib import Path

import pytest

import numpy as np

from auto_pipeline import (
    atomic_json,
    max_abs_field_difference,
    resolve_resume,
    stage_lock,
)


def test_atomic_complete_has_no_temporary_residue(tmp_path: Path):
    output = tmp_path / "complete.json"
    atomic_json(output, {"passed": True, "count": 126})
    assert json.loads(output.read_text(encoding="utf-8"))["count"] == 126
    assert not output.with_suffix(".json.tmp").exists()


def test_stage_lock_rejects_duplicate_submit(tmp_path: Path):
    stage = tmp_path / "n4"
    stage.mkdir()
    with stage_lock(stage):
        with pytest.raises(RuntimeError):
            with stage_lock(stage):
                pass
    with stage_lock(stage):
        pass


def test_resume_run_cannot_escape_results_root(tmp_path: Path):
    results = tmp_path / "results"
    run = results / "runs" / "R01"
    run.mkdir(parents=True)
    assert resolve_resume(results, "R01") == run.resolve()
    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(ValueError):
        resolve_resume(results, str(outside))


def test_a0_field_comparator_handles_boolean_without_subtraction():
    assert max_abs_field_difference(
        np.asarray([True, False]), np.asarray([True, False])
    ) == 0.0
    assert max_abs_field_difference(
        np.asarray([True, False]), np.asarray([False, False])
    ) == float("inf")
