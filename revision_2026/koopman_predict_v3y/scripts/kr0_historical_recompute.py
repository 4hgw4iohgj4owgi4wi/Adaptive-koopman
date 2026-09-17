"""KR0 historical recomputation (koopman_refine.md KR0 action 2).

Independently recomputes the S0/T0/T1/T2 1/5/10/20-step improvement table from
the 20 frozen outer rows CSVs (5 folds x 4 methods) with the layered hierarchy
window -> trajectory -> family -> scenario -> 12-scenario equal weight, and
compares to the local guard/horizons.csv main table (target values).
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

REV = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026")
KG_RUN = REV / "koopman_predict_v3t_results" / "runs" / "20260904_142331_KG_R02"
OUT = REV / "koopman_predict_v3u_results" / "runs" / "20260904_204301_KR_R01" / "kr0"
METHODS = ("S0", "T0", "T1", "T2")
HORIZONS = (1, 5, 10, 20)

# expected main table from the local guard delivery (horizons.csv)
EXPECTED = {
    ("T0", 1): -16.582657268711895, ("T0", 5): 19.50713062166618,
    ("T0", 10): 19.09694622994103, ("T0", 20): 13.795178816458657,
    ("T1", 1): -3.664807612138168, ("T1", 5): 22.447335792700855,
    ("T1", 10): 20.735560555328423, ("T1", 20): 16.91601416322641,
    ("T2", 1): -0.24555379085933723, ("T2", 5): 22.5804726251038,
    ("T2", 10): 22.518684982971198, ("T2", 20): 19.511107474656736,
}


def read_rows(path):
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def layered_scenario_value(rows):
    """window -> trajectory -> family -> scenario mean; scenario value =
    mean over families of (mean over trajectories of (mean over windows)).
    Families are pooled across folds (each outer family appears exactly once)."""
    scen_fams = defaultdict(lambda: defaultdict(list))  # scenario -> family -> [traj means]
    traj_cache = {}
    for r in rows:
        key = (r["scenario"], r["family"], r["trajectory"])
        traj_cache.setdefault(key, []).append(float(r["j_common"]))
    for (sc, family, _traj), js in traj_cache.items():
        scen_fams[sc][family].append(float(np.mean(js)))
    scenario_values = {}
    for sc, fams in scen_fams.items():
        fam_means = [float(np.mean(js)) for js in fams.values()]
        scenario_values[sc] = float(np.mean(fam_means)) if fam_means else float("nan")
    return scenario_values


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Per method and horizon: layer rows window->trajectory->family->scenario per fold,
    # then average the fold scenario values, then 12-scenario equal weight.
    final = {}
    for method in METHODS:
        scen_by_h = {}
        for h in HORIZONS:
            all_rows = []
            for fold in range(5):
                path = KG_RUN / "g4" / f"fold_{fold}" / "outer" / f"{method}_rows.csv"
                all_rows.extend(r for r in read_rows(path) if int(r["horizon"]) == h)
            scen_by_h[h] = layered_scenario_value(all_rows)
        final[method] = scen_by_h
    result_rows = []
    comparisons = []
    for method in ("T0", "T1", "T2"):
        for h in HORIZONS:
            m0 = float(np.mean(list(final["S0"][h].values())))
            m = float(np.mean(list(final[method][h].values())))
            improvement = 100.0 * (m0 - m) / max(m0, 1e-12)
            expected = EXPECTED[(method, h)]
            diff = improvement - expected
            result_rows.append({
                "method": method, "horizon": h,
                "recomputed_s0": m0, "recomputed_candidate": m,
                "recomputed_improvement_pct": improvement,
                "expected_improvement_pct": expected,
                "abs_diff": abs(diff),
            })
            comparisons.append(abs(diff))
    with open(OUT / "historical_recompute.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(result_rows[0].keys()))
        writer.writeheader()
        writer.writerows(result_rows)
    max_diff = max(comparisons)
    ok = max_diff <= 1e-6
    (OUT / "historical_recompute.json").write_text(
        json.dumps({"max_abs_diff": max_diff, "match": ok, "n_comparisons": len(comparisons),
                    "note": "layered window->trajectory->family->scenario, 12-scenario equal weight, pooled over folds",
                    "source": "g4/fold_*/outer/*_rows.csv (20 files)"}, indent=1), encoding="utf-8")
    print("HISTORICAL_RECOMPUTE max_abs_diff=", max_diff, "match=", ok)
    for row in result_rows[:6]:
        print(f"{row['method']} h{row['horizon']}: recomputed={row['recomputed_improvement_pct']:.6f} expected={row['expected_improvement_pct']:.6f} diff={row['abs_diff']:.2e}")


if __name__ == "__main__":
    main()
