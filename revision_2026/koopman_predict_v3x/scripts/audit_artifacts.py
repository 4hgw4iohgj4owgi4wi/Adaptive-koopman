"""Artifact audit (E14/E18): per-fold raw rows, models, curves, identity and
complete files must exist and be referenced consistently; summaries alone are
never acceptable."""

from __future__ import annotations

from pathlib import Path

REQUIRED_F4_ARTIFACTS = [
    "warm/last.pt",
    "warm/warm_identity.json",
    "phase_stream.json",
    "s0_rows.csv",
]


def audit_f4_fold(fold_dir: Path, variants=("ONE16", "MH16", "MHC16", "BCV16")) -> dict:
    missing = []
    for required in REQUIRED_F4_ARTIFACTS:
        if not (fold_dir / required).exists():
            missing.append(required)
    for variant in variants:
        variant_dir = fold_dir / variant
        for required in ("best.pt", "best.json", "last.pt", "last.json", "train_curve.csv", "rows_best.csv"):
            if not (variant_dir / required).exists():
                missing.append(f"{variant}/{required}")
    return {"passed": len(missing) == 0, "missing": missing, "fold": str(fold_dir)}
