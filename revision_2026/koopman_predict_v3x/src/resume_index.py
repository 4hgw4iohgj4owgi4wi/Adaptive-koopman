"""Frozen-unit audit for evaluation-only K1 recovery."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from background_core import digest_arrays, sha


def audit_units(freeze, old_run):
    units = freeze.get("units", [])
    expected = {(r, f, m) for r in range(3) for f in range(5)
                for m in ("aligned", "fixed_guard", "adaptive_guard")}
    actual = {(int(u["repeat"]), int(u["fold"]), u["method"]) for u in units}
    if len(units) != 45 or actual != expected:
        raise ValueError("formal freeze is not the registered 45-unit matrix")
    root = Path(old_run).resolve()
    seen = set()
    for unit in units:
        checkpoint = Path(unit["checkpoint"]).resolve()
        if root not in checkpoint.parents:
            raise ValueError("checkpoint escapes the frozen parent run")
        if not checkpoint.is_file() or sha(checkpoint) != unit["checkpoint_sha"]:
            raise ValueError("checkpoint missing or changed")
        key = (unit["checkpoint_sha"], unit["norm_sha"], unit["s0_sha"])
        if key in seen:
            raise ValueError("duplicate frozen model identity")
        seen.add(key)
        if not unit.get("selected", {}).get("finite", False):
            raise ValueError("frozen calibrated state is non-finite")
        if float(unit["selected"]["gamma"]) not in (0., .25, .5, .75, 1.):
            raise ValueError("unregistered gamma")
    for fold in range(5):
        witness = next(u for u in units if int(u["fold"]) == fold)
        with np.load(root / f"folds/fold{fold}/normalization.npz", allow_pickle=False) as z:
            norm = {k:z[k] for k in z.files}
        with np.load(root / f"folds/fold{fold}/s0.npz", allow_pickle=False) as z:
            coeff = z["coefficients"]
        if digest_arrays(norm) != witness["norm_sha"]:
            raise ValueError("frozen normalization snapshot changed")
        if digest_arrays({"coeff":coeff}) != witness["s0_sha"]:
            raise ValueError("frozen S0 snapshot changed")
    return {"passed": True, "units": 45, "candidate_states": 90,
            "methods": 3, "folds": 5, "repeats": 3}
