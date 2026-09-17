from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Iterable


ROOT = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main")
ROUND = ROOT / "paper_dcn_tf12_draft" / "publication_readiness_round10_2026-05-11"
SOURCES = [
    ROUND / "e2_n20_mixed_fault_ablation" / "data" / "tf14_remaining_runs.csv",
    ROUND / "e2_shard_2027_2032" / "data" / "tf14_remaining_runs.csv",
    ROUND / "e2_shard_2033_2038" / "data" / "tf14_remaining_runs.csv",
    ROUND / "e2_shard_2039_2045" / "data" / "tf14_remaining_runs.csv",
]
OUT = ROUND / "e2_n20_mixed_fault_ablation_merged"
DATA = OUT / "data"


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def as_float(value: object, default: float = float("nan")) -> float:
    try:
        return float(value)
    except Exception:
        return default


def aggregate(rows: Iterable[dict[str, str]]) -> list[dict[str, object]]:
    numeric_cols = [
        "rmse_lat_mean",
        "rmse_long_mean",
        "max_lat_global",
        "max_long_global",
        "full_path_reached",
        "connection_max_utilization",
        "connection_violation_count",
        "certificate_ok_ratio",
        "certificate_min_margin",
        "force_norm_peak",
        "force_norm_rms",
        "force_norm_rate_rms",
        "fallback_count",
        "constraint_violation_count",
        "success",
    ]
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row.get("experiment", ""), row.get("scenario", ""), row.get("method", ""))].append(row)
    out: list[dict[str, object]] = []
    for (experiment, scenario, method), group in sorted(groups.items()):
        item: dict[str, object] = {
            "experiment": experiment,
            "scenario": scenario,
            "method": method,
            "num_runs": len(group),
        }
        for col in numeric_cols:
            vals = [as_float(r.get(col)) for r in group]
            vals = [v for v in vals if v == v]
            if vals:
                item[f"{col}_mean"] = mean(vals)
                item[f"{col}_std"] = pstdev(vals) if len(vals) > 1 else 0.0
        out.append(item)
    return out


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    by_key: dict[tuple[str, str, str, str], dict[str, str]] = {}
    source_counts: dict[str, int] = {}
    for source in SOURCES:
        rows = read_rows(source)
        source_counts[str(source)] = len(rows)
        for row in rows:
            key = (row.get("experiment", ""), row.get("seed", ""), row.get("scenario", ""), row.get("method", ""))
            if not all(key):
                continue
            current = by_key.get(key)
            if current is None:
                by_key[key] = row
                continue
            # Prefer successful rows; otherwise keep the latest encountered row.
            if current.get("success") != "1" and row.get("success") == "1":
                by_key[key] = row
            elif current.get("failure_type") == "runtime_exception" and row.get("failure_type") != "runtime_exception":
                by_key[key] = row

    merged = list(by_key.values())
    merged.sort(key=lambda r: (r.get("experiment", ""), r.get("scenario", ""), r.get("method", ""), int(as_float(r.get("seed"), -1))))
    summary = aggregate(merged)
    write_csv(DATA / "tf14_remaining_runs.csv", merged)
    write_csv(DATA / "tf14_remaining_summary.csv", summary)
    min_group_n = min((int(row["num_runs"]) for row in summary), default=0)
    manifest = {
        "stage": "round10_e2_shard_merge",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "sources": source_counts,
        "num_runs_total": len(merged),
        "minimum_group_n": min_group_n,
        "final_statistics_ready": bool(summary) and min_group_n >= 20,
        "outputs": {
            "runs_csv": str(DATA / "tf14_remaining_runs.csv"),
            "summary_csv": str(DATA / "tf14_remaining_summary.csv"),
        },
    }
    (DATA / "tf14_remaining_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(DATA / "tf14_remaining_runs.csv")
    print(DATA / "tf14_remaining_summary.csv")
    print(DATA / "tf14_remaining_manifest.json")


if __name__ == "__main__":
    main()
