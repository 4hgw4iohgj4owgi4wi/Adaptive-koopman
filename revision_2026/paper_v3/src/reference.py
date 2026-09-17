"""Common, method-independent references and deterministic event windows."""

from __future__ import annotations

import math
from pathlib import Path
import csv
import hashlib
import json
import numpy as np


def _path(scenario: str, s: float) -> tuple[float, float]:
    z = float(np.clip(s / 100.0, 0.0, 1.0))
    if scenario == "100m_accel_turn":
        y = 1.5 * math.sin(2.0 * math.pi * np.clip((s - 30.0) / 70.0, 0.0, 1.0))
    elif scenario == "single_lane_change":
        y = 2.5 * math.sin(2.0 * math.pi * np.clip((s - 20.0) / 40.0, 0.0, 1.0))
    else:
        y = 7.5 * math.sin(math.pi * z) + 0.8 * math.sin(2.0 * math.pi * z)
    return float(s), float(y)


def build_reference(scenario: str, ticks: int, dt: float) -> list[dict]:
    rows: list[dict] = []
    for k in range(int(ticks) + 1):
        s = 100.0 * min(k / max(int(ticks), 1), 1.0)
        s_prev = 100.0 * min(max(k - 1, 0) / max(int(ticks), 1), 1.0)
        s_next = 100.0 * min((k + 1) / max(int(ticks), 1), 1.0)
        x, y = _path(scenario, s)
        xp, yp = _path(scenario, s_prev)
        xn, yn = _path(scenario, s_next)
        dx, dy = (xn - xp) / max(2.0 * dt, 1e-12), (yn - yp) / max(2.0 * dt, 1e-12)
        ddx, ddy = (xn - 2.0 * x + xp) / max(dt * dt, 1e-12), (yn - 2.0 * y + yp) / max(dt * dt, 1e-12)
        speed = float(math.hypot(dx, dy))
        yaw = float(math.atan2(dy, dx))
        curvature = float((dx * ddy - dy * ddx) / max((dx * dx + dy * dy) ** 1.5, 1e-12))
        rows.append({"k": k, "t_s": k * dt, "s_m": s, "x_m": x, "y_m": y, "yaw_rad": yaw,
                     "speed_mps": speed, "curvature": curvature, "phase": "route"})
    return rows


def event_ticks(reference: list[dict], scenario: str) -> dict:
    s = np.asarray([r["s_m"] for r in reference], float)
    kappa = np.abs(np.asarray([r["curvature"] for r in reference], float))
    k30 = int(np.flatnonzero(s >= 30.0)[0])
    threshold = max(0.2 * float(np.max(kappa)), 1e-9)
    over = np.flatnonzero(kappa >= threshold)
    if len(over) == 0:
        turn = k30
        turn_last = k30
    else:
        turn = int(over[0]); turn_last = int(over[-1])
    if scenario == "100m_accel_turn":
        candidates = [k30, k30 + 250, k30 + 500]
    elif scenario == "single_lane_change":
        middle = int((turn + turn_last) // 2)
        candidates = [turn, middle, min(turn_last + 1, len(reference) - 1)]
    else:
        middle = int((turn + turn_last) // 2)
        candidates = [turn, middle, min(turn_last + 1, len(reference) - 1)]
    if not all(0 <= k < len(reference) for k in candidates):
        raise ValueError(f"reference does not contain all registered event candidates: {candidates}")
    ks = max(int(candidates[0]) - 5, 50)
    ke = ks + 250
    if ke >= len(reference) - 100:
        raise ValueError(f"reference tail too short for event window: ks={ks}, ke={ke}, n={len(reference)}")
    return {"k_event": int(candidates[0]), "candidate_1": int(candidates[0]),
            "candidate_2": int(candidates[1]), "candidate_3": int(candidates[2]),
            "k_s": ks, "k_e": ke, "duration_s": 5.0, "threshold": threshold}


def reference_sha(rows: list[dict]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def write_reference(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        fields = list(rows[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)

