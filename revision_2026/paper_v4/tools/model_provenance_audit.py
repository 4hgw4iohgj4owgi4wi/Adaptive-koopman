"""Audit historical backbone and formal selection metadata without evaluating data arrays."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


METHODS = ("aligned", "fixed_guard", "adaptive_guard")
GAMMAS = {0.0, 0.25, 0.5, 0.75, 1.0}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def digest_arrays(path: Path, aliases=None) -> str:
    h = hashlib.sha256()
    with np.load(path, allow_pickle=False) as archive:
        for key in sorted(archive.files):
            value = np.asarray(archive[key])
            h.update((aliases or {}).get(key, key).encode())
            h.update(str((value.shape, value.dtype)).encode())
            h.update(value.tobytes())
    return h.hexdigest().upper()


def select_gamma(records):
    if len(records) != 5 or {float(row["gamma"]) for row in records} != GAMMAS:
        raise ValueError("incomplete gamma grid")
    good = [row for row in records if row["protected"] and row["i20"] >= 5 and row["gamma"] > 0]
    options = good or [row for row in records if row["protected"]]
    if not options:
        return {"status": "NO_PROTECTED_POINT", "gamma": None, "i20": None, "finite": False}
    best = options[0]
    for row in options[1:]:
        if row["m20"] < best["m20"] - 1e-10 or (
            abs(row["m20"] - best["m20"]) <= 1e-10 and row["gamma"] < best["gamma"]
        ):
            best = row
    return dict(best, status="CANDIDATE" if good else "PROTECTED_BUT_LOW_GAIN")


def equivalent(a, b):
    if a.keys() != b.keys():
        return False
    for key in a:
        if isinstance(a[key], float) or isinstance(b[key], float):
            if not np.isclose(a[key], b[key], rtol=0.0, atol=1e-12):
                return False
        elif a[key] != b[key]:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    run = Path(args.run).resolve()
    out = Path(args.out)
    if out.exists():
        raise SystemExit("refusing to overwrite existing audit")

    backbone_path = run / "folds/fold0/backbone_import.json"
    backbone = json.loads(backbone_path.read_text(encoding="utf-8-sig"))
    parent = Path(backbone["parent_checkpoint"])
    backbone_checks = {
        "record_exists": backbone_path.is_file(),
        "parent_exists": parent.is_file(),
        "parent_hash_matches": parent.is_file() and sha256(parent) == backbone["parent_sha"].upper(),
        "frozen_backward_error_le_1e_12": float(backbone["frozen_backward_error"]) <= 1e-12,
        "refit_backward_error_le_1e_12": float(backbone["refit_backward_error"]) <= 1e-12,
        "finite_coefficient_difference": bool(np.isfinite(backbone["coefficient_max_abs_difference"])),
        "condition_below_1e14": float(backbone["regularized_condition"]) < 1e14,
    }

    expected = {
        (repeat, fold, method)
        for repeat in range(3) for fold in range(5) for method in METHODS
    }
    seen = set()
    selection_rows = []
    selected_gamma = Counter()
    identity_by_fold = defaultdict(set)
    for path in sorted((run / "formal").glob("repeat*/fold*/*/calibration/selection.json")):
        record = json.loads(path.read_text(encoding="utf-8-sig"))
        repeat = int(path.parts[-5].removeprefix("repeat"))
        fold = int(path.parts[-4].removeprefix("fold"))
        method = path.parts[-3]
        key = (repeat, fold, method)
        seen.add(key)
        checkpoint = Path(record["checkpoint"])
        recomputed = select_gamma(record["grid"])
        checks = {
            "coordinate_expected": key in expected,
            "record_coordinate_matches_path": int(record["fold"]) == fold and record["method"] == method,
            "checkpoint_exists": checkpoint.is_file(),
            "checkpoint_hash_matches": checkpoint.is_file() and sha256(checkpoint) == record["checkpoint_sha"].upper(),
            "gamma_selection_recomputes": equivalent(recomputed, record["selected"]),
            "selected_is_protected": bool(record["selected"].get("protected")),
            "selected_status_candidate": record["selected"].get("status") == "CANDIDATE",
        }
        selected_gamma[str(record["selected"].get("gamma"))] += 1
        identity_by_fold[fold].add((record["norm_sha"], record["s0_sha"]))
        selection_rows.append({
            "repeat": repeat, "fold": fold, "method": method, "path": str(path),
            "selected_gamma": record["selected"].get("gamma"), "checks": checks,
        })

    fold_identity = []
    for fold in range(5):
        norm_path = run / f"folds/fold{fold}/normalization.npz"
        s0_path = run / f"folds/fold{fold}/s0.npz"
        values = identity_by_fold[fold]
        norm_digest = digest_arrays(norm_path) if norm_path.is_file() else None
        s0_digest = digest_arrays(s0_path, {"coefficients": "coeff"}) if s0_path.is_file() else None
        fold_identity.append({
            "fold": fold, "selection_identity_pairs": [list(pair) for pair in sorted(values)],
            "one_identity_pair_across_9_selections": len(values) == 1,
            "normalization_digest": norm_digest, "s0_digest": s0_digest,
            "saved_files_match_selection_identity": len(values) == 1 and next(iter(values)) == (norm_digest, s0_digest),
        })

    selection_complete = seen == expected and len(selection_rows) == 45
    selection_checks_pass = selection_complete and all(
        all(row["checks"].values()) for row in selection_rows
    ) and all(row["saved_files_match_selection_identity"] for row in fold_identity)
    report = {
        "status": "PASS_METADATA_CHAIN" if all(backbone_checks.values()) and selection_checks_pass else "FAIL",
        "scope": "backbone/checkpoint/normalization/S0 hashes and formal gamma-selection metadata; no prediction metric recomputation and no confirmation arrays opened",
        "run": str(run), "backbone": backbone, "backbone_checks": backbone_checks,
        "formal_selection_count": len(selection_rows),
        "expected_formal_selection_count": 45,
        "coordinates_complete": selection_complete,
        "selected_gamma_counts": dict(sorted(selected_gamma.items())),
        "fold_identity": fold_identity,
        "selections": selection_rows,
        "claim_boundary": "This proves recorded file identity and deterministic selection-rule replay. It does not independently recompute m20/i20 from numeric data or qualify the model for EXP-R2 E02."
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "formal_selection_count", "coordinates_complete", "selected_gamma_counts")}))
    if report["status"] == "FAIL":
        raise SystemExit(22)


if __name__ == "__main__":
    main()
