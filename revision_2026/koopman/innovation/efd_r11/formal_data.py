from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import numpy as np

SCENARIOS = ("staged_100m", "single_lane_change", "hairpin", "connector_directional")


def jobs(base: int) -> list[dict[str, Any]]:
    result = []
    for split, offset, count in (("train", 1001, 256), ("validation", 2001, 96), ("development", 3001, 64)):
        for i in range(count):
            seed = base + offset + i
            result.append({"seed": seed, "trajectory_id": seed, "base_family_id": f"{split}_{seed}", "split": split,
                           "scenario": SCENARIOS[i % 4], "independent_mirror": False, "local_mirror": False,
                           "long_diagnostic": False, "is_augmented": False})
    return result


def coverage(rows: list[dict[str, Any]], roots: dict[str, Path]) -> dict[str, Any]:
    result = {}; active_floor = 10.; high_load = 500.
    for split in ("train", "validation", "development"):
        subset = [x for x in rows if x["split"] == split]; scenes = {s: 0 for s in SCENARIOS}
        pos = np.zeros(8, int); neg = np.zeros(8, int); reversals = np.zeros(8, int); high = 0; windows = 0; scales = []
        for row in subset:
            scenes[row["scenario"]] += 1
            with np.load(roots[split] / row["base_file"], allow_pickle=False) as s:
                force = np.asarray(s["force_payload"], float).reshape(len(s["force_payload"]), 8); q = np.asarray(s["q"], float)
                meta = json.loads(str(s["metadata_json"].item()))
            pos += np.sum(force > active_floor, axis=0); neg += np.sum(force < -active_floor, axis=0)
            sign = np.sign(np.where(np.abs(force) >= active_floor, force, 0.)); reversals += np.sum(sign[1:] * sign[:-1] < 0, axis=0)
            high += int(np.sum(np.max(np.abs(q), axis=-1) >= high_load)); windows += max((len(force) - 20) // 20 + 1, 0)
            scales.append(meta["parameter_scales"])
        parameter_ranges = {k: [float(min(x[k] for x in scales)), float(max(x[k] for x in scales))] for k in scales[0]}
        passed = len(subset) == {"train":256,"validation":96,"development":64}[split] and all(v > 0 for v in scenes.values()) and np.all(pos > 0) and np.all(neg > 0) and np.all(reversals > 0) and high > 0 and all(lo < 1. and hi > 1. for lo, hi in parameter_ranges.values())
        result[split] = {"base_families": len(subset), "analytic_mirrors": len(subset), "independent_windows": windows,
                         "scenarios": scenes, "positive_active_by_component": pos.tolist(), "negative_active_by_component": neg.tolist(),
                         "reversals_by_component": reversals.tolist(), "high_load_steps": high, "parameter_ranges": parameter_ranges,
                         "augmented_counted_in_n": False, "passed": bool(passed)}
    result["passed"] = all(result[s]["passed"] for s in ("train","validation","development")); return result
