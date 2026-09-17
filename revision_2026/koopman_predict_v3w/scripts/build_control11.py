"""control11 cache derivation (koopman_input_protocol.md section 2).

Reads raw npz (requested_control4x2, base_acceleration_mps2) + existing n5
control7 caches; writes n5_cache11/<same name>.npz with an extra control11
column block [control7 | four accel differentials].  Verifies:
- control11[:, :7] bitwise-equal to control7
- requested accel recoverable from control11 diffs + virtual accel (<=1e-12)
No plant reruns, no label changes, old caches untouched.
"""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
N5_MANI = REV / "koopman_predict_auto_results" / "runs" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5" / "data_manifest.csv"
SRC_CACHE = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5" / "cache"
DST_CACHE = REV / "koopman_predict_auto_data" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5_cache11"
DST_CACHE.mkdir(parents=True, exist_ok=True)


def load_npz(path):
    with np.load(path, allow_pickle=False) as arch:
        return {k: arch[k] for k in arch.files}


def save_npz(path, data):
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **data)
    tmp.replace(path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    manifest = list(csv.DictReader(open(N5_MANI, encoding="utf-8-sig")))
    done = 0
    errors = []
    manifest_rows = []
    for row in manifest:
        raw_path = Path(row["raw_path"])
        cache_path = Path(row["cache_path"])
        if not raw_path.is_absolute():
            raw_path = REV / raw_path
        if not cache_path.is_absolute():
            cache_path = REV / cache_path
        out_path = DST_CACHE / cache_path.name
        try:
            raw = load_npz(raw_path)
            old = load_npz(cache_path)
            requested = np.asarray(raw["requested_control4x2"], dtype=float)
            base_acc = np.asarray(raw["base_acceleration_mps2"], dtype=float)
            control7 = np.asarray(old["control7"], dtype=float)
            if control7.shape[0] != len(base_acc) - 1:
                raise ValueError(f"control7 length mismatch {control7.shape} vs raw {len(base_acc)} in {raw_path.name}")
            diff = requested[1:, :, 0] - base_acc[1:, None]
            control11 = np.c_[control7, diff]
            # verification 1: first 7 columns identical to old control7
            max_fwd = float(np.max(np.abs(control11[:, :7] - control7)))
            # verification 2: recover requested accel
            recovered = control11[:, 7:] + base_acc[1:, None]
            max_rec = float(np.max(np.abs(recovered - requested[1:, :, 0])))
            if max_fwd != 0.0 or max_rec > 1e-12:
                raise ValueError(f"verification failed fwd={max_fwd} rec={max_rec} in {raw_path.name}")
            new_cache = dict(old)
            new_cache["control11"] = control11
            save_npz(out_path, new_cache)
            manifest_rows.append({
                "trajectory_id": row["trajectory_id"], "base_family_id": row["base_family_id"],
                "scenario": row["scenario"], "cache11_path": str(out_path),
                "cache11_sha256": sha256(out_path), "control7_match": True,
                "recover_error_max": max_rec,
            })
            done += 1
        except Exception as exc:  # noqa: BLE001 - record and continue; errors fail the run
            errors.append({"raw": str(raw_path), "error": str(exc)})
    if errors:
        (DST_CACHE / "derivation_errors.json").write_text(json.dumps(errors, indent=1), encoding="utf-8")
        raise SystemExit(f"derivation errors: {len(errors)}; first: {errors[0]}")
    (DST_CACHE / "cache11_manifest.csv").write_text(
        "trajectory_id,base_family_id,scenario,cache11_path,cache11_sha256,control7_match,recover_error_max\n"
        + "".join(
            f"{m['trajectory_id']},{m['base_family_id']},{m['scenario']},{m['cache11_path']},{m['cache11_sha256']},{m['control7_match']},{m['recover_error_max']}\n"
            for m in manifest_rows
        ),
        encoding="utf-8",
    )
    print(f"CACHE11_DONE count={done}")
    print(f"CACHE11_MANIFEST={DST_CACHE / 'cache11_manifest.csv'}")


if __name__ == "__main__":
    main()
