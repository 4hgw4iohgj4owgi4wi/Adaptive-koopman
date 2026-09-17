"""Paired summaries for the pre-registered factor comparisons."""

from __future__ import annotations

import csv
from pathlib import Path
import numpy as np


def _num(rows, key):
    return np.asarray([float(r[key]) for r in rows if r.get(key) not in (None, "")], float)


def paired(rows: list[dict], left: str, right: str, metric: str, seed: int = 2026090784, reps: int = 10000) -> dict:
    index = {(r["scenario"], r["family"], r["profile"]): r for r in rows}
    pairs = []
    for key, row in index.items():
        if row.get("method") != left: continue
        other = index.get(key[:-1] + (key[2],))
        # The index is method-free in this path only when rows are re-keyed below.
    grouped = {}
    for r in rows:
        grouped.setdefault((r["scenario"], r["family"], r["profile"]), {})[r["method"]] = r
    for g in grouped.values():
        if left in g and right in g:
            a, b = float(g[left][metric]), float(g[right][metric])
            pairs.append(a - b)
    values = np.asarray(pairs, float)
    if len(values) == 0:
        return {"left": left, "right": right, "metric": metric, "n": 0, "effect": None, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(int(seed))
    draws = rng.integers(0, len(values), size=(min(int(reps), 10000), len(values)))
    boot = values[draws].mean(axis=1)
    return {"left": left, "right": right, "metric": metric, "n": int(len(values)),
            "effect": float(values.mean()), "sd": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
            "ci_low": float(np.quantile(boot, 0.025)), "ci_high": float(np.quantile(boot, 0.975))}


def write_statistics(path: Path, rows: list[dict], metrics: list[tuple[str, str, str]]) -> list[dict]:
    records = [paired(rows, left, right, metric) for left, right, metric in metrics]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        fields = sorted({k for r in records for k in r})
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(records)
    return records

