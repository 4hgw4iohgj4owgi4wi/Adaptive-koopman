"""Q1: D10/D11 degradation dissection audit (READ-ONLY, koopman_ab.md).

Reads ONLY the frozen F4 fold rows (rows_best.csv / s0_rows.csv under the F4 run).
Never touches validation/development/confirm numeric values.

Metrics: M1 completeness, M2 per-scenario recomputation vs F4 verdict, M3 degrading
window sets, M4 component attribution, M5 tail structure, M6 oscillation structure,
M7 horizon profile, M8 force/internal profile.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

F4 = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman_predict_v3r_results\runs\20260903_041205_KFIX_R01")
OUT = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman_ab_results\runs\20260903_193821_AB_Q0_R01\q1")
VARIANTS = ("ONE16", "MH16", "MHC16", "BCV16")
SCENARIOS = ("D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11")
D5_HARD = (100, 120)


def load_csv(path):
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def jmean(rows):
    vals = [float(r["j_common"]) for r in rows]
    return sum(vals) / len(vals) if vals else float("nan")


def key(row):
    return (int(row["trajectory_id"]), int(row["window_start"]), int(row["horizon"]))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    findings = {"variants": {}}

    # ---------------- M1 completeness ----------------
    m1 = {}
    sha_of = {}
    for fold in range(5):
        fd = F4 / "f4" / f"fold_{fold}"
        m1[fold] = {"s0": None, "variants": {}}
        for variant in VARIANTS:
            p = fd / variant / "rows_best.csv"
            rows = load_csv(p)
            required = {"j_common", "e_core", "e_relative", "e_force4", "e_internal", "e_yaw",
                        "scenario", "window_start", "horizon", "divergent", "window", "trajectory_id"}
            missing = required - set(rows[0].keys()) if rows else required
            m1[fold]["variants"][variant] = {
                "rows": len(rows),
                "fields_ok": not missing,
                "missing_fields": sorted(missing) if missing else [],
            }
            sha_of[f"fold{fold}_{variant}"] = None  # hash computed in Q0; row counts here
        s0 = load_csv(fd / "s0_rows.csv")
        m1[fold]["s0"] = {"rows": len(s0)}
    findings["M1_completeness"] = m1
    m1_ok = all(
        m1[f]["variants"][v]["rows"] > 0 and m1[f]["variants"][v]["fields_ok"] for f in m1 for v in VARIANTS
    )

    # ---------------- per-variant audit loop ----------------
    for variant in VARIANTS:
        vf = {
            "M2_scenario_recompute": {},
            "M2_macro_per_fold": [],
            "M2_d5_hard_per_fold": [],
            "M3": {},
            "M4": {},
            "M5": {},
            "M6": {},
            "M7": {},
            "M8": {},
        }
        degrading_all = []
        for fold in range(5):
            fd = F4 / "f4" / f"fold_{fold}"
            cand = load_csv(fd / variant / "rows_best.csv")
            s0 = load_csv(fd / "s0_rows.csv")
            s0_by = {key(r): r for r in s0}
            cand20 = [r for r in cand if int(r["horizon"]) == 20]
            s020 = [r for r in s0 if int(r["horizon"]) == 20]

            # M2: per-scenario J20 means (fold level)
            scen = {}
            for sc in SCENARIOS:
                c = [float(r["j_common"]) for r in cand20 if r["scenario"] == sc]
                s = [float(r["j_common"]) for r in s020 if r["scenario"] == sc]
                if c and s:
                    mc, ms = sum(c) / len(c), sum(s) / len(s)
                    scen[sc] = {
                        "cand_j20": mc, "s0_j20": ms,
                        "degradation_pct": 100.0 * (ms - mc) / max(abs(ms), 0.02),
                    }
            vf["M2_scenario_recompute"][f"fold{fold}"] = scen
            macro_s = sum(scen[sc]["s0_j20"] for sc in scen) / len(scen)
            macro_c = sum(scen[sc]["cand_j20"] for sc in scen) / len(scen)
            vf["M2_macro_per_fold"].append(100.0 * (macro_s - macro_c) / max(abs(macro_s), 1e-12))
            hard_c = [float(r["j_common"]) for r in cand20 if r["scenario"] == "D5" and int(r["window_start"]) in D5_HARD]
            hard_s = [float(r["j_common"]) for r in s020 if r["scenario"] == "D5" and int(r["window_start"]) in D5_HARD]
            if hard_c and hard_s:
                vf["M2_d5_hard_per_fold"].append(
                    100.0 * (sum(hard_s) / len(hard_s) - sum(hard_c) / len(hard_c)) / max(abs(sum(hard_s) / len(hard_s)), 1e-12)
                )

            # paired per-window degradation at h=20
            pairs = []
            for r in cand20:
                s = s0_by.get(key(r))
                if s is None:
                    continue
                delta = float(r["j_common"]) - float(s["j_common"])  # >0 means candidate worse
                pairs.append({
                    "trajectory_id": r["trajectory_id"], "base_family_id": r["base_family_id"],
                    "scenario": r["scenario"], "window_class": r["window"], "window_start": int(r["window_start"]),
                    "cand_j": float(r["j_common"]), "s0_j": float(s["j_common"]),
                    "delta": delta,
                    "cand_e_core": float(r["e_core"]), "s0_e_core": float(s["e_core"]),
                    "cand_e_relative": float(r["e_relative"]), "s0_e_relative": float(s["e_relative"]),
                    "cand_e_force4": float(r["e_force4"]), "s0_e_force4": float(s["e_force4"]),
                    "cand_e_internal": float(r["e_internal"]), "s0_e_internal": float(s["e_internal"]),
                    "cand_e_yaw": float(r["e_yaw"]), "s0_e_yaw": float(s["e_yaw"]),
                    "cand_divergent": r["divergent"], "s0_divergent": s["divergent"],
                })
            # M3: degrading windows (delta > 0)
            deg = [p for p in pairs if p["delta"] > 0]
            by_scen = defaultdict(list)
            for p in deg:
                by_scen[p["scenario"]].append(p)
            by_class = defaultdict(int)
            for p in deg:
                by_class[p["window_class"]] += 1
            starts = defaultdict(int)
            for p in deg:
                starts[p["window_start"]] += 1
            vf["M3"][f"fold{fold}"] = {
                "total_h20_windows": len(pairs),
                "degrading_windows": len(deg),
                "degrading_share_pct": 100.0 * len(deg) / max(len(pairs), 1),
                "by_scenario": {k: len(v) for k, v in sorted(by_scen.items())},
                "by_scenario_share_pct": {k: 100.0 * len(v) / max(len(deg), 1) for k, v in sorted(by_scen.items())},
                "by_window_class": dict(sorted(by_class.items())),
                "window_start_hist": {k: v for k, v in sorted(starts.items())},
                "window_start_min": min((p["window_start"] for p in deg), default=None),
                "window_start_max": max((p["window_start"] for p in deg), default=None),
            }
            degrading_all.extend(deg)

            # M4: component attribution on degrading vs improving windows
            comps = ["e_core", "e_relative", "e_force4", "e_internal", "e_yaw"]
            imp = [p for p in pairs if p["delta"] < 0]
            attr = {}
            for c in comps:
                d_deg = sum(p[f"cand_{c}"] - p[f"s0_{c}"] for p in deg) / max(len(deg), 1)
                d_imp = sum(p[f"cand_{c}"] - p[f"s0_{c}"] for p in imp) / max(len(imp), 1)
                attr[c] = {"delta_mean_degrading_windows": d_deg, "delta_mean_improving_windows": d_imp}
            vf["M4"][f"fold{fold}"] = attr

            # M5: tail structure of per-window improvements (s0 - cand)
            improvements = sorted((p["s0_j"] - p["cand_j"] for p in pairs), reverse=True)
            n = len(improvements)
            total_deg = sum(max(-x, 0.0) for x in improvements)  # negative = degradation
            k5 = max(int(math.ceil(0.05 * n)), 1)
            tail5_deg = sum(max(-x, 0.0) for x in improvements[-k5:])
            vf["M5"][f"fold{fold}"] = {
                "n_windows": n,
                "p50": improvements[n // 2],
                "p90": improvements[int(0.90 * n)],
                "p95": improvements[int(0.95 * n)],
                "p99": improvements[int(0.99 * n)],
                "max": improvements[-1],
                "min": improvements[0],
                "total_degradation": total_deg,
                "tail5_degradation": tail5_deg,
                "tail_share_pct": 100.0 * tail5_deg / max(total_deg, 1e-12),
            }

            # M6: oscillation structure - error vs window_start for D10/D11 (and D7/D9 ref)
            osc = {}
            for sc in ("D7", "D9", "D10", "D11"):
                seq = sorted(
                    (p for p in pairs if p["scenario"] == sc and p["window_start"] >= 0),
                    key=lambda p: p["window_start"],
                )
                if len(seq) < 3:
                    continue
                errs = [p["cand_j"] for p in seq]
                s0s = [p["s0_j"] for p in seq]
                deltas = [p["delta"] for p in seq]
                osc[sc] = {
                    "n": len(seq),
                    "mean_cand": sum(errs) / len(errs),
                    "mean_s0": sum(s0s) / len(s0s),
                    "mean_delta": sum(deltas) / len(deltas),
                    "autocorr_lag1_delta": _autocorr(deltas, 1),
                    "autocorr_lag5_delta": _autocorr(deltas, 5),
                    "autocorr_lag10_delta": _autocorr(deltas, 10),
                    "autocorr_lag14_delta": _autocorr(deltas, 14),
                    "autocorr_lag1_s0": _autocorr(s0s, 1),
                    "flatness_s0": _flatness(s0s),
                    "flatness_cand": _flatness(errs),
                }
            vf["M6"][f"fold{fold}"] = osc

            # M7: horizon profile - degradation grows with horizon?
            hp = {}
            for h in (1, 5, 10, 20):
                ch = [r for r in cand if int(r["horizon"]) == h]
                sh = [r for r in s0 if int(r["horizon"]) == h]
                mc = sum(float(r["j_common"]) for r in ch) / len(ch)
                ms = sum(float(r["j_common"]) for r in sh) / len(sh)
                hp[str(h)] = {"cand_j": mc, "s0_j": ms, "degradation_pct": 100.0 * (ms - mc) / max(abs(ms), 0.02)}
            vf["M7"][f"fold{fold}"] = hp

            # M8: force/internal profile at h=20
            fp = {}
            for sc in ("D7", "D9", "D10", "D11"):
                c = [p for p in pairs if p["scenario"] == sc]
                if not c:
                    continue
                fp[sc] = {
                    "force4_delta_mean": sum(p["cand_e_force4"] - p["s0_e_force4"] for p in c) / len(c),
                    "internal_delta_mean": sum(p["cand_e_internal"] - p["s0_e_internal"] for p in c) / len(c),
                    "state_delta_mean": sum(p["delta"] for p in c) / len(c),
                }
            vf["M8"][f"fold{fold}"] = fp

        vf["M2_macro_mean_improvement_pct"] = sum(vf["M2_macro_per_fold"]) / len(vf["M2_macro_per_fold"])
        vf["M5_global"] = {
            "total_degrading_windows_all_folds": len(degrading_all),
            "degrading_share_pct": 100.0 * len(degrading_all) / max(5 * 1448, 1),
        }
        findings["variants"][variant] = vf

    # M2 vs F4 verdict table (macro per fold per variant)
    verdict_expected = {
        "ONE16": [0.15961811114672575, 0.6087463293560551, -0.3715182628823801, -0.6506304689537671, 0.3307660320134271],
        "MH16": [21.80559415818714, 19.61211120811561, 21.63296877215282, 16.317405387195137, 21.02262335891604],
        "MHC16": [22.001712730575584, 19.489444192684886, 22.265137394211244, 16.113476491716984, 20.639610578087986],
        "BCV16": [19.354085750449695, 16.68071343052533, 21.443587803718035, 12.843691567607202, 18.25189488012156],
    }
    m2_check = {}
    for v in VARIANTS:
        got = findings["variants"][v]["M2_macro_per_fold"]
        exp = verdict_expected[v]
        diffs = [abs(g - e) for g, e in zip(got, exp)]
        m2_check[v] = {"max_abs_diff": max(diffs), "match": max(diffs) <= 1e-9}
    findings["M2_verdict_recompute_check"] = m2_check

    findings["gates"] = {
        "M1_complete": m1_ok,
        "M2_matches_f4_verdict": all(v["match"] for v in m2_check.values()),
    }

    (OUT / "q1_findings.json").write_text(json.dumps(findings, indent=1, ensure_ascii=False), encoding="utf-8")

    # CSV products: scenario table (M2), degrading windows (M3), component attribution (M4),
    # horizon profile (M7), force profile (M8)
    with open(OUT / "scenario_table.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["variant", "fold", "scenario", "cand_j20", "s0_j20", "degradation_pct"])
        for v in VARIANTS:
            for f in range(5):
                for sc, val in findings["variants"][v]["M2_scenario_recompute"][f"fold{f}"].items():
                    w.writerow([v, f, sc, val["cand_j20"], val["s0_j20"], val["degradation_pct"]])
    with open(OUT / "degrading_windows.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["variant", "trajectory_id", "base_family_id", "scenario", "window_class",
                    "window_start", "cand_j", "s0_j", "delta", "cand_e_force4", "s0_e_force4",
                    "cand_e_internal", "s0_e_internal"])
        for v in VARIANTS:
            for f in range(5):
                fd = F4 / "f4" / f"fold_{f}"
                cand = load_csv(fd / v / "rows_best.csv")
                s0 = load_csv(fd / "s0_rows.csv")
                s0_by = {key(r): r for r in s0}
                for r in [x for x in cand if int(x["horizon"]) == 20]:
                    s = s0_by.get(key(r))
                    if s and float(r["j_common"]) > float(s["j_common"]):
                        w.writerow([v, r["trajectory_id"], r["base_family_id"], r["scenario"], r["window"],
                                    r["window_start"], r["j_common"], s["j_common"],
                                    float(r["j_common"]) - float(s["j_common"]),
                                    r["e_force4"], s["e_force4"], r["e_internal"], s["e_internal"]])
    with open(OUT / "component_attribution.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["variant", "fold", "component", "delta_mean_degrading", "delta_mean_improving"])
        for v in VARIANTS:
            for f in range(5):
                for c, val in findings["variants"][v]["M4"][f"fold{f}"].items():
                    w.writerow([v, f, c, val["delta_mean_degrading_windows"], val["delta_mean_improving_windows"]])
    with open(OUT / "horizon_profile.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["variant", "fold", "horizon", "cand_j", "s0_j", "degradation_pct"])
        for v in VARIANTS:
            for f in range(5):
                for h, val in findings["variants"][v]["M7"][f"fold{f}"].items():
                    w.writerow([v, f, h, val["cand_j"], val["s0_j"], val["degradation_pct"]])
    with open(OUT / "force_profile.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["variant", "fold", "scenario", "force4_delta_mean", "internal_delta_mean", "state_delta_mean"])
        for v in VARIANTS:
            for f in range(5):
                for sc, val in findings["variants"][v]["M8"][f"fold{f}"].items():
                    w.writerow([v, f, sc, val["force4_delta_mean"], val["internal_delta_mean"], val["state_delta_mean"]])
    with open(OUT / "oscillation_analysis.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["variant", "fold", "scenario", "n", "mean_cand", "mean_s0", "mean_delta",
                    "ac_lag1", "ac_lag5", "ac_lag10", "ac_lag14", "flatness_s0", "flatness_cand"])
        for v in VARIANTS:
            for f in range(5):
                for sc, val in findings["variants"][v]["M6"][f"fold{f}"].items():
                    w.writerow([v, f, sc, val["n"], val["mean_cand"], val["mean_s0"], val["mean_delta"],
                                val["autocorr_lag1_delta"], val["autocorr_lag5_delta"],
                                val["autocorr_lag10_delta"], val["autocorr_lag14_delta"],
                                val["flatness_s0"], val["flatness_cand"]])
    (OUT / "tail_stats.json").write_text(
        json.dumps({v: findings["variants"][v]["M5"] for v in VARIANTS}, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    print("Q1_AUDIT_DONE gates=", findings["gates"])
    print("macro_means=", {v: findings["variants"][v]["M2_macro_mean_improvement_pct"] for v in VARIANTS})


def _autocorr(seq, lag):
    n = len(seq)
    if n <= lag + 2:
        return None
    mean = sum(seq) / n
    var = sum((x - mean) ** 2 for x in seq)
    if var <= 0:
        return None
    ac = sum((seq[i] - mean) * (seq[i - lag] - mean) for i in range(lag, n)) / (n - lag)
    return ac / var


def _flatness(seq):
    """Normalized variability: std/mean (smaller = flatter)."""
    n = len(seq)
    if n < 2:
        return None
    mean = sum(seq) / n
    if abs(mean) < 1e-12:
        return None
    var = sum((x - mean) ** 2 for x in seq) / (n - 1)
    return math.sqrt(var) / abs(mean)


if __name__ == "__main__":
    main()
