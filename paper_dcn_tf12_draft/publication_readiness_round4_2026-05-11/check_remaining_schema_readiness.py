from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "paper_dcn_tf12_draft" / "publication_readiness_round4_2026-05-11"
DATA_DIR = ROOT / "tf14_remaining_experiments_20260509" / "data"


REQUIRED_SUMMARY_COLUMNS = {
    "experiment",
    "scenario",
    "method",
    "num_runs",
    "RMSE_y",
    "RMSE_s",
    "full_path_reached",
}

ROUND2_REQUIRED_DERIVED_COLUMNS = {
    "method_id",
    "seed",
    "comm_trace_id",
    "fault_trace_id",
    "topology_trace_id",
    "success",
    "failure_type",
    "constraint_violation_count",
    "fallback_count",
    "intervention_count",
    "nan_class",
}

SAFETY_COLUMNS = {
    "force_norm_peak",
    "force_norm_rate_rms",
    "connection_util_max",
    "connection_violation_count",
    "corner_load_spread_peak",
}


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def is_nan_like(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    try:
        return math.isnan(float(text))
    except ValueError:
        return text.lower() in {"nan", "none", "null"}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: list[str] = []
    report.append("# Round4 Remaining Schema Readiness Check")
    report.append("")

    manifest_path = DATA_DIR / "tf14_remaining_manifest.json"
    summary_path = DATA_DIR / "tf14_remaining_summary.csv"
    runs_path = DATA_DIR / "tf14_remaining_runs.csv"

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report.append("## Manifest")
        for key in [
            "generated_at",
            "final_statistics_ready",
            "minimum_group_n",
            "num_runs",
            "experiments",
        ]:
            report.append(f"- `{key}`: `{manifest.get(key)}`")
        report.append("")
    else:
        report.append("## Manifest")
        report.append("- MISSING: `tf14_remaining_manifest.json`")
        report.append("")

    summary_rows, summary_cols = read_csv(summary_path)
    run_rows, run_cols = read_csv(runs_path)

    report.append("## CSV Presence")
    report.append(f"- summary exists: `{summary_path.exists()}`, rows: `{len(summary_rows)}`, columns: `{len(summary_cols)}`")
    report.append(f"- runs exists: `{runs_path.exists()}`, rows: `{len(run_rows)}`, columns: `{len(run_cols)}`")
    report.append("")

    report.append("## Current Required Columns")
    missing_summary = sorted(REQUIRED_SUMMARY_COLUMNS - set(summary_cols))
    report.append(f"- missing summary columns: `{missing_summary}`")
    missing_round2 = sorted(ROUND2_REQUIRED_DERIVED_COLUMNS - set(run_cols) - set(summary_cols))
    report.append(f"- missing Round2 derived/provenance columns: `{missing_round2}`")
    report.append("")

    report.append("## Group Counts")
    group_counts: Counter[tuple[str, str, str]] = Counter()
    for row in run_rows:
        group_counts[(row.get("experiment", ""), row.get("scenario", ""), row.get("method", ""))] += 1
    if group_counts:
        min_n = min(group_counts.values())
        max_n = max(group_counts.values())
        report.append(f"- groups: `{len(group_counts)}`")
        report.append(f"- min group n: `{min_n}`")
        report.append(f"- max group n: `{max_n}`")
        not_final = [g for g, n in group_counts.items() if n < 20]
        report.append(f"- groups with n<20: `{len(not_final)}`")
    else:
        report.append("- groups: `0`")
        report.append("- groups with n<20: `unknown/no run rows`")
    report.append("")

    report.append("## Experiment/Method Coverage")
    methods_by_exp: dict[str, set[str]] = defaultdict(set)
    scenarios_by_exp: dict[str, set[str]] = defaultdict(set)
    for row in run_rows:
        methods_by_exp[row.get("experiment", "")].add(row.get("method", ""))
        scenarios_by_exp[row.get("experiment", "")].add(row.get("scenario", ""))
    for exp in sorted(methods_by_exp):
        report.append(f"- `{exp}` methods: `{sorted(methods_by_exp[exp])}`")
        report.append(f"- `{exp}` scenarios: `{sorted(scenarios_by_exp[exp])}`")
    report.append("")

    report.append("## Safety NaN Scan")
    missing_safety_cols = sorted(SAFETY_COLUMNS - set(run_cols))
    report.append(f"- missing safety columns in run CSV: `{missing_safety_cols}`")
    if not missing_safety_cols:
        total_e7 = 0
        nan_e7 = 0
        nan_non_e7 = 0
        for row in run_rows:
            has_nan = any(is_nan_like(row.get(col)) for col in SAFETY_COLUMNS)
            if row.get("experiment") == "E7":
                total_e7 += 1
                if has_nan:
                    nan_e7 += 1
            elif has_nan:
                nan_non_e7 += 1
        report.append(f"- E7 safety rows: `{total_e7}`")
        report.append(f"- E7 rows with safety NaN/missing: `{nan_e7}`")
        report.append(f"- non-E7 rows with safety NaN/missing: `{nan_non_e7}`")
    report.append("")

    report.append("## Publication Gate Verdict")
    verdicts = []
    if group_counts and min(group_counts.values()) >= 20:
        verdicts.append("PASS paired n>=20")
    else:
        verdicts.append("FAIL paired n>=20")
    if not missing_round2:
        verdicts.append("PASS Round2 provenance schema")
    else:
        verdicts.append("FAIL Round2 provenance schema")
    if not missing_safety_cols:
        verdicts.append("PASS safety columns present")
    else:
        verdicts.append("FAIL safety columns present")
    for item in verdicts:
        report.append(f"- {item}")

    out_path = OUT_DIR / "remaining_schema_readiness_report.md"
    out_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
