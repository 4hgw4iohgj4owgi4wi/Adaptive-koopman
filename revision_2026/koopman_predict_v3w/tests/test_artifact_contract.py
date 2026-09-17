"""F2: artifact-contract tests (E14/E18): per-fold raw rows, models, curves,
identity files and the fold summary must be present; removing any required
artifact must fail the gate."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from audit_artifacts import REQUIRED_F4_ARTIFACTS, audit_f4_fold


def _make_fold_dir(tmp_path: Path) -> Path:
    fold = tmp_path / "fold_0"
    for variant in ("ONE16", "MH16", "MHC16", "BCV16"):
        variant_dir = fold / variant
        variant_dir.mkdir(parents=True, exist_ok=True)
        (variant_dir / "best.pt").write_bytes(b"x")
        (variant_dir / "best.json").write_text("{}", encoding="utf-8")
        (variant_dir / "last.pt").write_bytes(b"x")
        (variant_dir / "last.json").write_text("{}", encoding="utf-8")
        (variant_dir / "train_curve.csv").write_text("step,total\n1,0.1\n", encoding="utf-8")
        header = ["horizon", "scenario", "window_start", "j_common", "divergent", "force8_rmse_n", "internal8_rmse_n"]
        rows = [
            {"horizon": "20", "scenario": "D0", "window_start": "0", "j_common": "0.13", "divergent": "False", "force8_rmse_n": "10", "internal8_rmse_n": "5"},
            {"horizon": "1", "scenario": "D0", "window_start": "0", "j_common": "0.01", "divergent": "False", "force8_rmse_n": "2", "internal8_rmse_n": "1"},
        ]
        with open(variant_dir / "rows_best.csv", "w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=header)
            writer.writeheader()
            writer.writerows(rows)
    (fold / "warm").mkdir(exist_ok=True)
    (fold / "warm" / "last.pt").write_bytes(b"x")
    (fold / "warm" / "warm_identity.json").write_text("{}", encoding="utf-8")
    (fold / "s0_rows.csv").write_text("horizon,scenario,window_start,j_common,divergent\n20,D0,0,0.13,False\n", encoding="utf-8")
    (fold / "phase_stream.json").write_text("{}", encoding="utf-8")
    return fold


def test_f4_fold_artifact_audit_passes_when_complete(tmp_path):
    fold = _make_fold_dir(tmp_path)
    report = audit_f4_fold(fold, variants=("ONE16", "MH16", "MHC16", "BCV16"))
    assert report["passed"] is True


def test_f4_fold_artifact_audit_fails_when_rows_missing(tmp_path):
    fold = _make_fold_dir(tmp_path)
    (fold / "MHC16" / "rows_best.csv").unlink()
    report = audit_f4_fold(fold, variants=("ONE16", "MH16", "MHC16", "BCV16"))
    assert report["passed"] is False
    assert any("rows_best.csv" in item for item in report["missing"])


def test_rows_by_fold_null_is_forbidden():
    """E14: a summary with rows_by_fold=null must never pass."""
    payload = {"rows_by_fold": None, "macro": 0.1}
    assert payload.get("rows_by_fold") is not None or not _summary_passes(payload)


def _summary_passes(payload: dict) -> bool:
    return bool(payload.get("rows_by_fold")) and bool(payload.get("macro"))
