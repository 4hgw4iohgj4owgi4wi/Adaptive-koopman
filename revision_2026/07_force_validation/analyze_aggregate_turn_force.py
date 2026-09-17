"""Quantify the current aggregate payload inertial-force proxy by curvature.

Important: these are not per-connector forces.
"""

import csv
import json
import math
import sys
from pathlib import Path


path = Path(sys.argv[1])
rows = []
with path.open("r", encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        rows.append({k: float(v) for k, v in row.items()})

abs_k = sorted(abs(r["kappa"]) for r in rows)
q25 = abs_k[int(0.25 * (len(abs_k) - 1))]
q75 = abs_k[int(0.75 * (len(abs_k) - 1))]


def group_stats(group):
    n = len(group)
    norm = [math.hypot(r["fx_payload"], r["fy_payload"]) for r in group]
    angle = [math.degrees(math.atan2(r["fy_payload"], r["fx_payload"])) for r in group]
    return {
        "n": n,
        "mean_abs_fx": sum(abs(r["fx_payload"]) for r in group) / n,
        "mean_abs_fy": sum(abs(r["fy_payload"]) for r in group) / n,
        "mean_abs_mz": sum(abs(r["mz_payload"]) for r in group) / n,
        "rms_planar_resultant": math.sqrt(sum(v * v for v in norm) / n),
        "peak_planar_resultant": max(norm),
        "circular_resultant_direction_deg": math.degrees(
            math.atan2(
                sum(math.sin(math.radians(a)) for a in angle),
                sum(math.cos(math.radians(a)) for a in angle),
            )
        ),
        "corner_load_spread_mean": sum(r["corner_load_spread"] for r in group) / n,
        "corner_load_spread_peak": max(r["corner_load_spread"] for r in group),
    }


low = [r for r in rows if abs(r["kappa"]) <= q25]
high = [r for r in rows if abs(r["kappa"]) >= q75]
result = {
    "warning": "Aggregate inertial force/moment only; not per-connector forces.",
    "source": str(path),
    "abs_curvature_q25": q25,
    "abs_curvature_q75": q75,
    "low_curvature": group_stats(low),
    "high_curvature": group_stats(high),
}
print(json.dumps(result, indent=2, ensure_ascii=False))
Path(__file__).with_name("aggregate_turn_force_audit.json").write_text(
    json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
)
