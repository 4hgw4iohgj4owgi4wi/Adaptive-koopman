"""KC1: merge pure input7/input11 scenario metrics -> 11-over-7 improvements."""
import csv
import json
from collections import defaultdict
from pathlib import Path

KC1 = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman_predict_v3v_results\runs\20260904_224212_KC_R01\kc1")
SCEN = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11"]


def load(tag):
    with open(KC1 / f"scenario_metrics_{tag}.csv", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def pooled_hierarchy(rows, horizon):
    """family-weighted scenario mean over folds (each inner family appears once)."""
    scen_fams = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if int(r["horizon"]) != horizon or int(r["n_windows"]) == 0:
            continue
        # rows carry fold but not family; family is one per scenario per fold in inner;
        # use fold as the family bucket only if n==1 family per (fold,scenario); inner has
        # exactly one family per scenario per fold, so fold-bucket == family value.
        scen_fams[r["scenario"]][f"{r['fold']}_{r['scenario']}"].append(float(r["j_common"]))
    out = {}
    for sc in SCEN:
        fams = scen_fams.get(sc, {})
        if not fams:
            out[sc] = None
            continue
        out[sc] = sum(sum(v) / len(v) for v in fams.values()) / len(fams)
    return out


def main():
    r7 = load("input7_pure")
    r11 = load("input11_pure")
    out_rows = []
    for h in (1, 5, 10, 20):
        p7 = pooled_hierarchy(r7, h)
        p11 = pooled_hierarchy(r11, h)
        for sc in SCEN:
            a, b = p7.get(sc), p11.get(sc)
            if a is None or b is None:
                out_rows.append({"scenario": sc, "horizon": h, "e7": "", "e11": "", "improvement_pct": "", "abs_diff": ""})
                continue
            imp = 100.0 * (a - b) / max(a, 1e-12)
            out_rows.append({
                "scenario": sc, "horizon": h, "e7": f"{a:.6f}", "e11": f"{b:.6f}",
                "improvement_pct": f"{imp:+.3f}", "abs_diff": f"{a - b:.6f}",
            })
    with open(KC1 / "input7_vs11_pure_table.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print("scenario,h1_imp,h20_imp")
    by_sc = {}
    for r in out_rows:
        by_sc.setdefault(r["scenario"], {})[int(r["horizon"])] = float(r["improvement_pct"]) if r["improvement_pct"] else None
    for sc in SCEN:
        d = by_sc[sc]
        print(f"{sc}: h1={d.get(1):+.2f}% h5={d.get(5):+.2f}% h10={d.get(10):+.2f}% h20={d.get(20):+.2f}%")


if __name__ == "__main__":
    main()
