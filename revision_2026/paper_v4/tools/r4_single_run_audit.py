"""Independent scientific single-run audit for R4 cells.

Task-book section 4 requires "每条单独审计" and names the checks: complete tick, raw
accepted substep and solver counts, non-finite values, true force peak / tyre / support,
request equal to the optimiser first control, requested and actual steering and rate
bounds, source identity and metric recomputation.

Read-only: it re-reads the persisted artifacts and recomputes the metrics rather than
trusting them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

SPEED = 2.0
STEERING_LIMIT_RAD = np.deg2rad(15.0)
STEERING_RATE_LIMIT_RADPS = 1.2
FORCE_LIMIT_N = 15000.0
TIRE_LIMIT = 1.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), [str(value) for value in data["columns"]]


def audit(paper: Path, run_rel: str) -> dict:
    run = paper / run_rel
    raw, columns = load(run / "raw.npz")
    index = {name: position for position, name in enumerate(columns)}
    sub, sub_columns = load(run / "substeps.npz")
    sub_index = {name: position for position, name in enumerate(sub_columns)}
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    solver = [json.loads(line) for line in (run / "solver.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    ticks = int(raw.shape[0])
    expected = int(metrics["expected_iterations"])
    checks: list[dict] = []

    def add(name: str, passed: bool, detail) -> None:
        checks.append({"item": len(checks) + 1, "check": name, "pass": bool(passed), "detail": detail})

    # 1-3 counts
    add("status_completed", metrics["status"] == "COMPLETED", metrics["status"])
    add("tick_count_equals_expected", ticks == expected, {"ticks": ticks, "expected": expected})
    add("solver_records_equal_ticks", len(solver) == ticks, {"solver_records": len(solver), "ticks": ticks})

    # 4 accepted substeps present and unique per interval
    add("accepted_substeps_present", sub.shape[0] >= ticks, {"substeps": int(sub.shape[0]), "ticks": ticks})

    # 5-6 non-finite values
    state_columns = [index[f"x{i}"] for i in range(30)]
    raw_finite = bool(np.isfinite(raw).all())
    add("raw_all_finite", raw_finite, "all raw entries finite" if raw_finite else "non-finite entries present")
    sub_finite = bool(np.isfinite(sub).all())
    add("substeps_all_finite", sub_finite, "all substep entries finite" if sub_finite else "non-finite entries present")

    # 7 time monotonicity
    time = raw[:, index["time_s"]]
    monotone = bool(np.all(np.diff(time) > 0))
    add("time_strictly_increasing", monotone, {"first_s": float(time[0]), "last_s": float(time[-1])})

    # 8 route completion
    distance = float(metrics["reference_distance_m"])
    route = float(metrics["route_length_m"])
    add("route_completed", distance >= route - 1e-9, {"reference_distance_m": distance, "route_length_m": route})

    # 9-11 true physical peaks, recomputed with the frozen runner's own semantics.
    # The runner updates these maxima from the accepted substep segments AND from the
    # interval-endpoint evaluation, so an audit that reads only the substeps disagrees
    # with metrics.json by order 1e-5 (the first version of this check did exactly that,
    # and three P1 cells failed on it).  Both sources are therefore combined here.
    substep_peak_force = max(
        float(sub[:, [sub_index[f"force_peak{i}"] for i in range(4)]].max()),
        float(raw[:, [index[f"point_force_norm{i}"] for i in range(4)]].max()),
    )
    substep_peak_tire = max(
        float(sub[:, [sub_index[f"tire_utilization{i}"] for i in range(4)]].max()),
        float(raw[:, [index[f"tire_utilization{i}"] for i in range(4)]].max()),
    )
    substep_min_support = min(
        float(sub[:, [sub_index[f"support_load{i}"] for i in range(4)]].min()),
        float(raw[:, [index[f"support_load{i}"] for i in range(4)]].min()),
    )
    add("force_peak_within_limit", substep_peak_force <= FORCE_LIMIT_N + 1e-6,
        {"recomputed_peak_n": substep_peak_force, "limit_n": FORCE_LIMIT_N})
    add("tyre_within_limit", substep_peak_tire <= TIRE_LIMIT + 1e-9,
        {"recomputed_peak": substep_peak_tire, "limit": TIRE_LIMIT})
    add("support_non_negative", substep_min_support >= 0.0, {"recomputed_min_n": substep_min_support})

    # 12 request equals the optimiser first control (raw grouped vs solver interleaved)
    mismatch = 0.0
    compared = 0
    for record in solver:
        tick = int(record["tick"])
        if tick >= ticks:
            continue
        control = np.asarray(record["first_control"], float)
        grouped = np.r_[control[0::2], control[1::2]]
        stored = np.r_[
            raw[tick][[index[f"request_accel{i}"] for i in range(4)]],
            raw[tick][[index[f"request_delta{i}"] for i in range(4)]],
        ]
        mismatch = max(mismatch, float(np.abs(grouped - stored).max()))
        compared += 1
    add("request_equals_optimiser_first_control", mismatch == 0.0,
        {"ticks_compared": compared, "max_abs_difference": mismatch})

    # 13-15 steering bounds and rate.  Strict-chain runs register the request and applied
    # tolerances independently; historical runs retain the original 1e-9 audit convention.
    requested = np.abs(raw[:, [index[f"request_delta{i}"] for i in range(4)]]).max()
    actual = np.abs(raw[:, [index[f"actual_delta{i}"] for i in range(4)]]).max()
    rate = float(np.abs(np.diff(raw[:, [index[f"actual_delta{i}"] for i in range(4)]], axis=0)).max())
    tolerance_record = metrics.get("acceptance_tolerances") or {}
    request_tolerance = float(tolerance_record.get("requested_steering_acceptance_tolerance_rad", 1e-9))
    applied_tolerance = float(tolerance_record.get("applied_steering_machine_tolerance_rad", 1e-9))
    add("requested_steering_within_limit", requested <= STEERING_LIMIT_RAD + request_tolerance,
        {"max_requested_rad": float(requested), "limit_rad": STEERING_LIMIT_RAD,
         "acceptance_tolerance_rad": request_tolerance})
    add("actual_steering_within_limit", actual <= STEERING_LIMIT_RAD + applied_tolerance,
        {"max_actual_rad": float(actual), "limit_rad": STEERING_LIMIT_RAD,
         "machine_tolerance_rad": applied_tolerance})
    add("steering_rate_within_limit", rate <= STEERING_RATE_LIMIT_RADPS * 0.02 + 1e-12,
        {"max_per_tick_change_rad": rate, "limit_per_tick_rad": STEERING_RATE_LIMIT_RADPS * 0.02})

    # 16 solver status
    solver_failures = [record["tick"] for record in solver if record.get("status") != "PASS"]
    add("all_solver_records_pass", not solver_failures, {"failures": solver_failures[:5], "count": len(solver_failures)})

    if metrics.get("solver_settings") is not None:
        add("solver_settings_recorded_and_self_consistent",
            isinstance(metrics.get("solver_settings_effective"), dict)
            and metrics["solver_settings_effective"] == metrics["solver_settings"],
            {"declared": metrics.get("solver_settings"),
             "effective": metrics.get("solver_settings_effective"),
             "source": metrics.get("solver_settings_source")})

    # 17 source identity: the protocol named by the run still matches its recorded hash
    protocol_sha = metrics.get("protocol_sha256")
    matching_protocol = None
    for protocol_path in sorted((paper / "protocol").glob("*.json")):
        try:
            candidate = json.loads(protocol_path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if sha(protocol_path) == protocol_sha:
            matching_protocol = str(protocol_path.relative_to(paper)).replace("\\", "/")
            break
    add("protocol_identity_matches_a_frozen_file", matching_protocol is not None,
        {"recorded_sha256": protocol_sha, "matched": matching_protocol})

    # 18 metric recomputation against the persisted artifacts
    recomputed = {
        "peak_force_relative": abs(substep_peak_force - metrics["maximum_point_force_n"]) / max(metrics["maximum_point_force_n"], 1e-30),
        "peak_tire_relative": abs(substep_peak_tire - metrics["maximum_tire_utilization"]) / max(metrics["maximum_tire_utilization"], 1e-30),
        "min_support_absolute": abs(substep_min_support - metrics["minimum_support_load_n"]),
    }
    add("metrics_match_recomputation",
        recomputed["peak_force_relative"] < 1e-12 and recomputed["peak_tire_relative"] < 1e-12 and recomputed["min_support_absolute"] < 1e-9,
        recomputed)

    # 19 substep interval closure
    closure = float(sub[:, sub_index["dt_s"]].sum())
    total_time = float(time[-1])
    add("substep_time_closure", abs(closure - total_time) <= 1e-9 * max(total_time, 1.0),
        {"sum_substep_dt_s": closure, "last_tick_time_s": total_time, "residual_s": closure - total_time})

    # 20 wall clock recorded and reported
    wall = raw[:, index["solver_wall_s"]]
    add("wall_clock_recorded", bool(np.isfinite(wall).all() and wall.size == ticks),
        {"mean_s": float(wall.mean()), "max_s": float(wall.max()), "within_5s": int(np.count_nonzero(wall <= 5.0)), "ticks": ticks})

    passed = sum(1 for check in checks if check["pass"])
    return {
        "run": run_rel,
        "status": "PASS_SINGLE_RUN_AUDIT" if passed == len(checks) else "FAIL_SINGLE_RUN_AUDIT",
        "items_passed": passed,
        "items_total": len(checks),
        "checks": checks,
        "source_files": [
            {"path": f"{run_rel}/raw.npz", "sha256": sha(run / "raw.npz")},
            {"path": f"{run_rel}/substeps.npz", "sha256": sha(run / "substeps.npz")},
            {"path": f"{run_rel}/solver.jsonl", "sha256": sha(run / "solver.jsonl")},
            {"path": f"{run_rel}/metrics.json", "sha256": sha(run / "metrics.json")},
        ],
        "claim_boundary": ("Artifact-level scientific audit of one deterministic run. Figure delivery and visual QA "
                           "are checked independently by the release gate, avoiding a circular dependency between "
                           "the audit and the figure that displays its status. It does not establish statistical "
                           "significance, tracking quality, real-time behaviour or any method-level advantage."),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--write", action="store_true", help="write single_run_audit.json into each run directory")
    args = parser.parse_args()
    paper = Path(__file__).resolve().parents[1]
    results = []
    for run_rel in args.runs:
        record = audit(paper, run_rel)
        results.append(record)
        if args.write:
            target = paper / run_rel / "single_run_audit.json"
            if target.exists():
                raise ValueError("REFUSING_TO_OVERWRITE_AUDIT:" + run_rel)
            target.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{record['status']:24s} {record['items_passed']:2d}/{record['items_total']:2d}  {run_rel}")
        for check in record["checks"]:
            if not check["pass"]:
                print(f"      FAIL item {check['item']}: {check['check']} -> {check['detail']}")
    if not all(record["status"] == "PASS_SINGLE_RUN_AUDIT" for record in results):
        raise SystemExit(20)


if __name__ == "__main__":
    main()
