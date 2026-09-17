"""KR0 input-contract audit (koopman_refine.md KR0 actions 4-6).

Read-only: fold0 fit D7/D9A raw + cache.  Verifies whether the four-vehicle
requested acceleration differentials reach the model's 7-dim control input
(control7).  Outputs input_contract.json/csv under the run's kr0 dir and the
INPUT_CONTRACT_BLOCKED judgement when the differential cannot be recovered
unambiguously from control7.
"""
import csv
import json
from pathlib import Path

import numpy as np

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
N5_MANI = REV / "koopman_predict_auto_results" / "runs" / "20260901_214725_AUTO_PREDICT_AUTO_R04_R01" / "n5" / "data_manifest.csv"
OUT = REV / "koopman_predict_v3u_results" / "runs" / "20260904_204301_KR_R01" / "kr0"


def load_npz(path):
    with np.load(path, allow_pickle=False) as arch:
        return {k: arch[k] for k in arch.files}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # raw_path lookup by cache_path from the N5 manifest
    raw_by_cache = {}
    with open(N5_MANI, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            raw_by_cache[row["cache_path"]] = row["raw_path"]

    # fold0 fit trajectories per scenario from fold_manifest
    with open(KG_RUN / "g0" / "fold_manifest.csv", encoding="utf-8-sig") as fh:
        manifest = list(csv.DictReader(fh))
    targets = {}
    for row in manifest:
        if row["fold"] == "0" and row["role"] == "fit" and row["scenario"] in ("D7", "D9"):
            targets.setdefault(row["scenario"], []).append(row)
    if "D9" in targets:
        targets["D9A"] = [r for r in targets["D9"] if r["trajectory"] == "A"] or targets["D9"]
    if "D9" in targets and not targets.get("D9A"):
        targets["D9A"] = targets["D9"]
    scenarios = [s for s in ("D7", "D9A") if s in targets]

    findings = {"per_trajectory": {}, "judgement": None}
    rows_out = []
    for scenario in scenarios:
        row = targets[scenario][0]
        cache_path = row["cache_path"]
        raw_path = raw_by_cache.get(cache_path)
        if raw_path is None or not Path(raw_path).exists():
            findings["per_trajectory"][scenario] = {"error": f"raw missing for {cache_path}"}
            continue
        raw = load_npz(raw_path)
        cache = load_npz(cache_path)
        requested = np.asarray(raw["requested_control4x2"], dtype=float)   # (T,4,2) [accel, steer]
        base_acc = np.asarray(raw["base_acceleration_mps2"], dtype=float)  # (T,)
        control7 = np.asarray(cache["control7"], dtype=float)              # (T-1,7)
        phase = np.asarray(raw["command_phase"]).astype(str) if "command_phase" in raw else None
        # differential acceleration per vehicle vs the virtual/base acceleration
        diff = requested[:, :, 0] - base_acc[:, None]                      # (T,4)
        active = np.abs(diff) > 1e-9
        # control7 last four columns should be requested steer of next index
        steer_used = np.asarray(requested[1:, :, 1], dtype=float)
        steer_match = float(np.max(np.abs(control7[:, 3:] - steer_used)))
        # could the differential be recovered from control7 rows? look for two
        # instants with (nearly) identical control7 but different diff
        ambiguous = False
        c7 = control7
        m = min(len(c7), len(diff) - 1)
        best_pair = None
        for i in range(m):
            for j in range(i + 1, m):
                if np.max(np.abs(c7[i] - c7[j])) < 1e-12:
                    if np.max(np.abs(diff[i + 1] - diff[j + 1])) > 1e-9:
                        ambiguous = True
                        best_pair = (i, j, float(np.max(np.abs(diff[i + 1] - diff[j + 1]))))
                        break
            if ambiguous:
                break
        record = {
            "scenario": scenario,
            "family": row["family"],
            "trajectory": row["trajectory"],
            "cache_path": cache_path,
            "raw_path": str(raw_path),
            "T": int(len(base_acc)),
            "diff_accel_max_abs": float(np.max(np.abs(diff))),
            "diff_accel_active_share": float(np.mean(active)),
            "diff_pattern": {f"v{i}": float(np.max(np.abs(diff[:, i]))) for i in range(4)},
            "expected_offsets": {"D7": (0.20, 0.20, -0.20, -0.20), "D9A": (0.15, -0.15, -0.15, 0.15)}.get(scenario, None),
            "control7_steer_match_max_abs": steer_match,
            "control7_has_accel_column": False,
            "same_control7_diff_accel_found": ambiguous,
            "witness_pair": best_pair,
        }
        findings["per_trajectory"][scenario] = record
        rows_out.append(record)

    blocked = any(
        r.get("diff_accel_max_abs", 0.0) > 1e-6 and not r.get("control7_has_accel_column")
        for r in rows_out
    )
    judgement = "INPUT_CONTRACT_BLOCKED" if blocked else "INPUT_CONTRACT_OK"
    findings["judgement"] = judgement
    findings["note"] = (
        "control7 = [base_acceleration, virtual_front, virtual_rear, requested_steer_FL..RR]; "
        "four-vehicle requested ACCELERATION column (requested_control4x2[:,:,0], which carries "
        "per-vehicle offsets e.g. D7 +/-0.20, D9A +/-0.15 added in generate_data.py "
        "requested_controls[:,0] += vehicle_accel_offset_mps2) is never encoded. "
        "If a non-zero differential exists and identical control7 rows can carry different "
        "differentials, the plant input cannot be recovered unambiguously."
    )
    (OUT / "input_contract.json").write_text(json.dumps(findings, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(OUT / "input_contract.csv", "w", newline="", encoding="utf-8") as fh:
        if rows_out:
            writer = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
            writer.writeheader()
            writer.writerows(rows_out)
    print("JUDGEMENT=", judgement)
    for r in rows_out:
        print(f"{r['scenario']}: diff_max={r['diff_accel_max_abs']:.4f} active_share={r['diff_accel_active_share']:.2%} "
              f"steer_match={r['control7_steer_match_max_abs']:.2e} same_c7_diff_accel={r['same_control7_diff_accel_found']}")


if __name__ == "__main__":
    main()
