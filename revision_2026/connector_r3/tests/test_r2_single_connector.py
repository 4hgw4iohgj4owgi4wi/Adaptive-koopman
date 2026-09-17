from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from connector_r3 import connector_force_r3
from schema_r3 import params_from_delta_freeze
from single_connector_dynamics_r3 import simulate


def digest(run):
    h = hashlib.sha256()
    for k in ("time_s", "delta_m", "normal_speed_mps", "raw_force_n", "elastic_force_n", "damping_force_n", "elastic_energy_j", "damping_power_w", "contact_active_raw", "smoothing_weight", "impulse_ns"):
        h.update(np.ascontiguousarray(run[k]).view(np.uint8))
    return h.hexdigest()


def first_contact_metrics(run, p, speed):
    active = np.flatnonzero(run["contact_active_raw"])
    if not len(active):
        raise RuntimeError("contact was not established")
    i = int(active[0]); t0 = run["time_s"][i]
    j = min(len(run["time_s"]) - 1, int(np.searchsorted(run["time_s"], t0 + .002)))
    r3_first = float(run["raw_force_n"][i])
    r3_2ms = float(run["raw_force_n"][j])
    v_first = max(float(run["normal_speed_mps"][i]), 0.0)
    v_2ms = max(float(run["normal_speed_mps"][j]), 0.0)
    d_first = max(float(run["delta_m"][i]), 0.0)
    d_2ms = max(float(run["delta_m"][j]), 0.0)
    v1_first = p.stiffness_npm * d_first + p.damping_nspm * v_first
    v1_2ms = p.stiffness_npm * d_2ms + p.damping_nspm * v_2ms
    return {
        "speed_mps": speed, "first_index": i, "first_delta_m": d_first,
        "r3_first_force_n": r3_first, "v1_first_force_n": v1_first,
        "first_sample_reduction": (v1_first - r3_first) / max(v1_first, 1e-12),
        "r3_force_2ms_after_n": r3_2ms, "v1_force_2ms_after_n": v1_2ms,
        "two_ms_endpoint_reduction": (v1_2ms - r3_2ms) / max(v1_2ms, 1e-12),
    }


def main() -> None:
    p = params_from_delta_freeze(Path(sys.argv[1]))
    outdir = Path(sys.argv[2]); outdir.mkdir(parents=True, exist_ok=True)
    cases = {}
    # Conservative and damped energy cases.
    conservative = simulate(replace(p, damping_nspm=0.0, ultimate_force_n=1e12), .012, 0.0, .12, 5e-5, stop_on_limit=False)
    e = conservative["total_mechanical_energy_j"]
    drift = float(np.max(np.abs(e - e[0])) / max(e[0], 1e-12)); cases["conservative"] = conservative
    damped = simulate(replace(p, ultimate_force_n=1e12), .012, 0.0, .12, 5e-5, stop_on_limit=False)
    de = np.diff(damped["total_mechanical_energy_j"]); cases["damped"] = damped

    onset = []
    for speed in (.01, .05, .25, 1.0):
        # Start 0.2 mm inside the gap, using a high-rate reference integration.
        run = simulate(replace(p, ultimate_force_n=1e12), -2e-4, speed, max(.03, 2e-4 / speed + .01), 2e-5, stop_on_limit=False)
        cases[f"contact_v{speed}"] = run
        onset.append(first_contact_metrics(run, p, speed))

    # Loading--unloading and exact smoothing-boundary probes.
    loading_unloading = simulate(replace(p, ultimate_force_n=1e12), .005, .3, .2, 2e-5, stop_on_limit=False)
    cases["loading_unloading"] = loading_unloading
    boundary = {}
    for factor in (1 - 1e-8, 1.0, 1 + 1e-8):
        d = p.smoothing_width_m * factor
        r = connector_force_r3([p.free_play_m + d, 0], [.2, 0], p)
        boundary[str(factor)] = {"delta_m": d, "weight": float(r.smoothing_weight), "force_n": float(r.raw_force_n)}

    directions = [simulate(p, -1e-4, .2, .02, 2e-5, direction=d, stop_on_limit=False)["raw_force_n"] for d in ((1,0),(-1,0),(0,1),(0,-1))]
    static_thresholds = {}
    for force in (12000 * .999, 12000, 15000 * .999, 15000):
        d = force / p.stiffness_npm
        r = connector_force_r3([p.free_play_m + d, 0], [0, 0], p)
        static_thresholds[str(force)] = {"delta_m": d, "raw_force_n": float(r.raw_force_n), "rated": bool(r.rated_force_exceeded), "ultimate": bool(r.ultimate_force_exceeded)}
    over = simulate(p, 15000 / p.stiffness_npm, 0.0, .01, 1e-4)
    cases["over_limit"] = over
    repeat = simulate(replace(p, ultimate_force_n=1e12), -2e-4, .25, .03, 2e-5, stop_on_limit=False)

    first_reductions = [x["first_sample_reduction"] for x in onset]
    endpoint_reductions = [x["two_ms_endpoint_reduction"] for x in onset]
    checks = {
        "contact_onset_limit_zero": max(float(connector_force_r3([p.free_play_m + x, 0], [1, 0], p).raw_force_n) for x in (1e-14, 1e-13, 1e-12)) < 1e-5,
        "first_contact_sample_reduction_ge_50pct_all_speeds": min(first_reductions) >= .5,
        # The protocol says first 2 ms force step; retain a literal 2 ms endpoint audit as a hard check.
        "two_ms_endpoint_reduction_ge_50pct_all_speeds": min(endpoint_reductions) >= .5,
        "post_smoothing_v1_force_equivalence": max(abs(boundary[str(f)]["force_n"] - (p.stiffness_npm * boundary[str(f)]["delta_m"] + p.damping_nspm * .2)) for f in (1.0, 1 + 1e-8)) < 1e-9,
        "conservative_energy_drift_lt_0p5pct": drift < .005,
        "damped_no_sustained_growth": float(np.quantile(de, .999)) < 1e-6,
        "four_direction_symmetry": max(float(np.max(np.abs(x - directions[0]))) for x in directions) < 1e-9,
        "loading_and_unloading_present": bool(np.any(loading_unloading["normal_speed_mps"] > 0) and np.any(loading_unloading["normal_speed_mps"] < 0)),
        "repeat_hash_equal": digest(repeat) == digest(cases["contact_v0.25"]),
        "finite": all(all(np.all(np.isfinite(v)) for v in q.values() if isinstance(v, np.ndarray)) for q in cases.values()),
        "no_negative_normal_force": all(float(np.min(q["raw_force_n"])) >= 0 for q in cases.values()),
        "ultimate_stops_without_cap": bool(over["failed"] and len(over["time_s"]) == 1 and over["raw_force_n"][0] >= 15000),
    }
    for name, run in cases.items():
        np.savez_compressed(outdir / f"{name}.npz", **run)
    result = {
        "passed": all(checks.values()), "checks": {k: bool(v) for k, v in checks.items()},
        "onset_metrics": onset, "smoothing_boundary": boundary,
        "conservative_energy_relative_drift": drift,
        "damped_max_positive_step_j": float(np.max(de)),
        "static_threshold_sweep": static_thresholds,
        "case_hashes": {k: digest(v) for k, v in cases.items()},
        "development_read": False, "confirm_read": False,
    }
    (outdir / "r2_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
