"""AR1/AR2: fallback composition + F4 eight-gate recomputation (koopman_ab.md).

Pure post-processing over frozen F4 fold rows.  compose_fallback(spec) mixes
candidate (MH16) rows with S0 rows on the spec trigger set; recompute_gates
evaluates the F4 candidate gates with the E19-corrected semantics
(worst scenario degradation <= 3%, taskbook wording).

Reads only F4 train-fold rows; no validation/development/confirm access.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

F4 = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman_predict_v3r_results\runs\20260903_041205_KFIX_R01")
SCEN = ("D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11")
D5_HARD = (100, 120)


def load(path):
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def key(r):
    return (int(r["trajectory_id"]), int(r["window_start"]), int(r["horizon"]))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def triggered(row, spec):
    t = spec["trigger"]
    if t["type"] == "scenario_set":
        return row["scenario"] in t["scenarios"]
    if t["type"] == "window_set":
        if row["scenario"] not in t["scenarios"]:
            return False
        if "window_classes" in t and row["window"] not in t["window_classes"]:
            return False
        if "window_starts" in t and int(row["window_start"]) not in t["window_starts"]:
            return False
        return True
    raise ValueError(f"unknown trigger type: {t['type']}")


def compose(spec, out_dir: Path):
    """Combine candidate rows with S0 rows on the trigger set, per fold."""
    out_dir.mkdir(parents=True, exist_ok=True)
    variant = spec["candidate"]["variant"]
    for fold in range(5):
        fd = F4 / "f4" / f"fold_{fold}"
        cand = load(fd / variant / "rows_best.csv")
        s0 = load(fd / "s0_rows.csv")
        s0_by = {key(r): r for r in s0}
        fieldnames = list(cand[0].keys())
        replaced = 0
        total_trigger = 0
        composed = []
        for r in cand:
            if triggered(r, spec):
                total_trigger += 1
                s = s0_by.get(key(r))
                if s is None:
                    raise RuntimeError(f"S0 row missing for {key(r)} in fold {fold}")
                # swap in the S0 prediction row projected onto the candidate schema;
                # S0-only columns (j_full/e_actuator/actuator_rmse_rad) are dropped
                s_row = {field: s.get(field, "") for field in fieldnames}
                s_row["seed_label"] = r["seed_label"]
                s_row["model_kind"] = r["model_kind"]
                s_row["variant"] = r["variant"]
                composed.append(s_row)
                replaced += 1
            else:
                composed.append(r)
        out_csv = out_dir / f"composed_fold{fold}.csv"
        with open(out_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(composed)
        print(f"fold{fold}: total_trigger_windows={total_trigger} replaced={replaced}")
    return out_dir


def jmean(rows):
    vals = [float(r["j_common"]) for r in rows]
    return sum(vals) / len(vals) if vals else float("nan")


def fold_macro(rows):
    h20 = [r for r in rows if int(r["horizon"]) == 20]
    scen = {}
    for r in h20:
        scen.setdefault(r["scenario"], []).append(float(r["j_common"]))
    if not scen:
        return float("nan")
    return float(sum(sum(v) / len(v) for v in scen.values()) / len(scen))


def recompute_gates(rows_dir: Path, out_path: Path, variant_label: str):
    """F4 eight gates on composed rows vs S0, E19-corrected scenario semantics."""
    gate_cfg = {
        "d5_hard_degradation_max_percent": 3.0,
        "macro_positive_fold_min": 4,
        "macro_improvement_min_percent": 5.0,
        "scenario_degradation_max_percent": 3.0,
        "scenario_denominator_floor": 0.02,
        "force_internal_degradation_max_percent": 5.0,
    }
    macro_improvements, d5_hard_improvements, scenario_worse, force_deg, internal_deg = [], [], [], [], []
    divergent_total = 0
    for fold in range(5):
        rows = load(rows_dir / f"composed_fold{fold}.csv")
        s0 = load(F4 / "f4" / f"fold_{fold}" / "s0_rows.csv")
        mc, ms = fold_macro(rows), fold_macro(s0)
        macro_improvements.append(100.0 * (ms - mc) / max(abs(ms), 1e-12))
        hard_c = [float(r["j_common"]) for r in rows if int(r["horizon"]) == 20 and r["scenario"] == "D5" and int(r["window_start"]) in D5_HARD]
        hard_s = [float(r["j_common"]) for r in s0 if int(r["horizon"]) == 20 and r["scenario"] == "D5" and int(r["window_start"]) in D5_HARD]
        if hard_c and hard_s:
            hs, hc = sum(hard_s) / len(hard_s), sum(hard_c) / len(hard_c)
            d5_hard_improvements.append(100.0 * (hs - hc) / max(abs(hs), 1e-12))
        for sc in SCEN:
            c = jmean([r for r in rows if int(r["horizon"]) == 20 and r["scenario"] == sc])
            s = jmean([r for r in s0 if int(r["horizon"]) == 20 and r["scenario"] == sc])
            if math.isfinite(c) and math.isfinite(s):
                scenario_worse.append(100.0 * (c - s) / max(abs(s), float(gate_cfg["scenario_denominator_floor"])))
        fc = float(sum(float(r["force8_rmse_n"]) for r in rows if int(r["horizon"]) == 20)) / max(
            sum(1 for r in rows if int(r["horizon"]) == 20), 1)
        fs = float(sum(float(r["force8_rmse_n"]) for r in s0 if int(r["horizon"]) == 20)) / max(
            sum(1 for r in s0 if int(r["horizon"]) == 20), 1)
        ic = float(sum(float(r["internal8_rmse_n"]) for r in rows if int(r["horizon"]) == 20)) / max(
            sum(1 for r in rows if int(r["horizon"]) == 20), 1)
        iss = float(sum(float(r["internal8_rmse_n"]) for r in s0 if int(r["horizon"]) == 20)) / max(
            sum(1 for r in s0 if int(r["horizon"]) == 20), 1)
        force_deg.append(100.0 * (fc - fs) / max(abs(fs), 1e-12))
        internal_deg.append(100.0 * (ic - iss) / max(abs(iss), 1e-12))
        divergent_total += int(sum(1 for r in rows if int(r["horizon"]) == 20 and str(r["divergent"]) == "True"))
    macro_mean = sum(macro_improvements) / len(macro_improvements)
    positive_folds = sum(1 for v in macro_improvements if v > 0)
    gates = {
        "finite_and_no_divergence": divergent_total == 0,
        "d5_hard_fold_gate": all(math.isfinite(v) and v >= -3.0 for v in d5_hard_improvements),
        "macro_positive_folds": positive_folds >= int(gate_cfg["macro_positive_fold_min"]),
        "macro_improvement_5pct": macro_mean >= float(gate_cfg["macro_improvement_min_percent"]),
        "scenario_degradation": max(scenario_worse, default=-1e9) <= float(gate_cfg["scenario_degradation_max_percent"]),
        "force_not_worse_5pct": max(force_deg, default=-1e9) <= float(gate_cfg["force_internal_degradation_max_percent"]),
        "internal_not_worse_5pct": max(internal_deg, default=-1e9) <= float(gate_cfg["force_internal_degradation_max_percent"]),
    }
    result = {
        "variant_label": variant_label,
        "macro_mean_improvement_percent": macro_mean,
        "macro_improvements_per_fold": macro_improvements,
        "d5_hard_improvements_per_fold": d5_hard_improvements,
        "worst_scenario_worse_pct": max(scenario_worse, default=None),
        "scenario_worse_per_fold_max": [max(scenario_worse[i * 12:(i + 1) * 12] if len(scenario_worse) > i * 12 else []) for i in range(5)],
        "positive_folds": positive_folds,
        "divergent_count_20": divergent_total,
        "gates": gates,
        "passed": all(gates.values()),
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, ensure_ascii=False)
    return result


def make_spec(rule_type, out_path, variant="MH16"):
    spec = {
        "rule": "fallback_composition",
        "spec_id": rule_type,
        "description": "per koopman_ab.md AR; Q2 authorized route AR' (D1 fallback); Q1 finding: D1 worst scenario (connector_event start~360 force collapse)",
        "trigger": rule_type,
        "candidate": {"run_id": F4.name, "variant": variant, "rows_pattern": "f4/fold_{f}/VARIANT/rows_best.csv"},
        "s0": {"run_id": F4.name, "rows_pattern": "f4/fold_{f}/s0_rows.csv"},
        "taskbook_ab_sha256": "C835AE567FCC24805C2C9BBBDEFA300361B6F3AA39D80963BD1FCA2C481ECFC6",
        "q1_findings_ref": "q1/q1_findings.json + q1_deep_findings.json (run 20260903_193821_AB_Q0_R01)",
        "note": "spec hashable & reusable across AR2/V0/C0; trigger data is scenario/window labels only (no future info)",
    }
    text = json.dumps(spec, sort_keys=True, ensure_ascii=False)
    spec["sha256"] = sha256_text(text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=2, ensure_ascii=False)
    return spec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, choices=["spec_A_scenario_D1", "spec_B_window_D1_connector"])
    ap.add_argument("--out-root", required=True)
    args = ap.parse_args()
    base = Path(args.out_root)
    if args.spec == "spec_A_scenario_D1":
        spec = {"type": "scenario_set", "scenarios": ["D1"]}
    else:
        spec = {"type": "window_set", "scenarios": ["D1"], "window_classes": ["connector_event"]}
    spec_file = base / "ar1" / f"{args.spec}.json"
    full_spec = make_spec(spec, spec_file)
    rows_dir = base / "ar2" / args.spec
    compose(full_spec, rows_dir)
    result = recompute_gates(rows_dir, base / "ar2" / f"gates_{args.spec}.json", args.spec)
    print(json.dumps({k: result[k] for k in ("macro_mean_improvement_percent", "positive_folds", "divergent_count_20", "passed", "gates")}, indent=1))
