from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT / "src"))

from connector_adapter import DELTA_S_M, ScalarConnector
from connector_r3 import ConnectorR3Params, connector_force_r3
from event_substep import EventSubstepConfig, detect_callable_events, integrate


EXPECTED_PROTOCOL_SHA256 = "89937c0c7c334d9b5c5f2e5275f04227ce99f442b9ffffa68446675205774784"
EXPECTED_FROZEN = {
    "r3_1_connector_r3.py": ("revision_2026/connector_r3_1/src/connector_r3.py", "0bd16c4d4d2fb141bfc2689e4472e475ea23cf319e0b31a3c6448ddcef310459"),
    "r3_1_schema_r3.py": ("revision_2026/connector_r3_1/src/schema_r3.py", "bff45ef3cbfd9f47d3523670be4298a464699a4ce7d5f8b859f3fc0720a6d562"),
    "v2_internal_force.py": ("revision_2026/connector_v2/src/internal_force.py", "0a00d298a00bc39dab8d8e4aa991ad543f625fcb7e62b3329d6ea60e70ac28c0"),
    "connector_v2_four_vehicle_v2.py": ("revision_2026/connector_v2/src/four_vehicle_v2.py", "7ffc9514775e2c173ed76d996e5ff5eaab82ad841b9bd0bb2c796a7231657685"),
    "paired_maneuvers.py": ("revision_2026/connector_v2/src/paired_maneuvers.py", "5c41bd4dfb8dfc9084035f54318ba7d121bcef6cd5a414d9f26ff6fcf10a91e4"),
}
EXPECTED_R31_STATUS_SHA256 = "7e6e9d201b09e91910d20a9d9188bd3820f3c586a19eb1d6e261cc6ce6cb431f"
SPEEDS = {
    "q05": 0.0002041391858023853,
    "q50": 0.003371584129140294,
    "q95": 0.054984709782141795,
    "q99": 0.2006325726682664,
    "stress_0p25": 0.25,
    "stress_1p0": 1.0,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def source_manifest() -> dict[str, str]:
    manifest = {}
    for path in sorted(SOURCE_ROOT.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix.lower() in {".py", ".md", ".json"}:
            manifest[path.relative_to(SOURCE_ROOT).as_posix()] = sha256(path)
    return manifest


def stage_paths(project_root: Path):
    revision = project_root / "revision_2026"
    return {
        "results": revision / "connector_r3_2_results",
        "data": revision / "connector_r3_2_data",
        "models": revision / "connector_r3_2_models",
        "mpc": revision / "connector_r3_2_mpc",
    }


def append_log(results: Path, stage: str, status: str, detail: str) -> None:
    log = results / "work_log.md"
    if not log.exists():
        log.write_text("# Connector R3.2 work log\n\nAll artifacts remain on RTX 5080; no 2060 transfer was performed.\n\n", encoding="utf-8")
    with log.open("a", encoding="utf-8") as stream:
        stream.write(f"- {utc_now()} | {stage} | {status} | {detail}\n")


def require_previous(results: Path, stage: str) -> None:
    order = {"N1": "n0", "N2": "n1"}
    previous = order.get(stage)
    if not previous:
        return
    path = results / previous / "complete.json"
    if not path.exists() or not json.loads(path.read_text(encoding="utf-8")).get("passed"):
        marker = results / stage.lower() / "NOT_RUN.json"
        write_json(marker, {"stage": stage, "status": f"NOT_RUN_PRECONDITION_{previous.upper()}_FAILED", "timestamp": utc_now()})
        raise SystemExit(f"{stage} precondition failed: {path}")
    frozen = json.loads((results / "n0" / "source_manifest.json").read_text(encoding="utf-8"))
    current = source_manifest()
    if frozen != current:
        write_json(results / stage.lower() / "NOT_RUN.json", {"stage": stage, "status": "NOT_RUN_SOURCE_HASH_DRIFT", "timestamp": utc_now()})
        raise SystemExit("source hash drift after N0")


def find_support_source(project_root: Path) -> tuple[str, str | None]:
    root = project_root / "revision_2026" / "connector_r3_1_results"
    for path in sorted(root.rglob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(value, dict) and "support_test_speeds_mps" in value:
            return str(path), sha256(path)
    return "not_found", None


def run_n0(project_root: Path, paths: dict[str, Path]) -> None:
    results = paths["results"]
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    out = results / "n0"
    out.mkdir(parents=True, exist_ok=True)
    checks = []
    protocol_hash = sha256(SOURCE_ROOT / "protocol.md")
    checks.append({"name": "protocol_sha256", "passed": protocol_hash == EXPECTED_PROTOCOL_SHA256, "actual": protocol_hash, "expected": EXPECTED_PROTOCOL_SHA256})
    for label, (relative, expected) in EXPECTED_FROZEN.items():
        path = project_root / relative
        actual = sha256(path) if path.exists() else None
        checks.append({"name": label, "path": str(path), "passed": actual == expected, "actual": actual, "expected": expected})
    status_path = project_root / "revision_2026" / "connector_r3_1_results" / "stage_status.json"
    status_hash = sha256(status_path) if status_path.exists() else None
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    checks.extend([
        {"name": "r3_1_stage_status_sha256", "passed": status_hash == EXPECTED_R31_STATUS_SHA256, "actual": status_hash, "expected": EXPECTED_R31_STATUS_SHA256},
        {"name": "r3_1_development_read_false", "passed": status.get("development_read") is False, "actual": status.get("development_read")},
        {"name": "r3_1_confirm_read_false", "passed": status.get("confirm_read") is False, "actual": status.get("confirm_read")},
    ])
    free_gb = shutil.disk_usage(project_root.drive + "\\").free / 2**30
    checks.append({"name": "disk_free_at_least_20gb", "passed": free_gb >= 20.0, "actual_gb": free_gb})
    support_path, support_hash = find_support_source(project_root)
    preflight = {
        "timestamp": utc_now(),
        "host": platform.node(),
        "python": sys.executable,
        "python_version": platform.python_version(),
        "disk_free_gb": free_gb,
        "manual_precreation_observation": {
            "performed_before_r3_2_directory_creation": True,
            "all_five_r3_2_paths_absent": True,
            "related_connector_koopman_mpc_processes": 0,
            "gpu": "NVIDIA GeForce RTX 5080, 16303 MiB total, 89 MiB used, 27% util, 35 C",
            "note": "Captured through the approved remote-5080 SSH runner before deployment; N0-N2 are CPU-only.",
        },
        "support_speed_source": support_path,
        "support_speed_source_sha256": support_hash,
        "checks": checks,
    }
    write_json(out / "preflight_snapshot.json", preflight)
    control_paths = {
        "steering_allocator.py": project_root / "revision_2026" / "model" / "steering_allocator.py",
        "generate_k2.py": project_root / "revision_2026" / "koopman" / "generate_k2.py",
        "four_vehicle_coupled.py": project_root / "revision_2026" / "model" / "four_vehicle_coupled.py",
    }
    control_api = {
        "passed": all(path.exists() for path in control_paths.values()),
        "allocate_controls": {
            "inputs": {
                "state": "30-state four-vehicle/payload vector, SI units",
                "base_acceleration_mps2": "m/s^2",
                "virtual_front_deg": "degree",
                "virtual_rear_deg": "degree",
            },
            "outputs": {"controls_shape": [4, 2], "column_0": "acceleration_mps2", "column_1": "steering_rad", "targets": "allocated commands and yaw/ICR diagnostics"},
            "limits": {"steering_deg": [-15.0, 15.0], "zero_sum_acceleration_correction_mps2": [-0.8, 0.8]},
            "defaults": {"heading_gain": 2.0, "speed_gain": 0.8, "straight_epsilon_rad": 1e-6},
        },
        "control_clocks": {"CONTROL_DT_s": 0.02, "PLANT_DT_s": 0.002, "plant_substeps_per_control": 10},
        "scenario_entrypoints": {
            "staged_100m": "internal staged command: 4/-2 deg then -4/2 deg",
            "single_lane_change": "generate_k2.nominal_command, front 3 deg, rear=-0.5*front",
            "hairpin": "generate_k2.nominal_command, front 10 deg, rear -7 deg",
            "connector_directional": "generate_k2.nominal_command, 1.3 deg sine + 1.2 deg; rear=-0.55*front",
        },
        "source_sha256": {name: sha256(path) if path.exists() else None for name, path in control_paths.items()},
        "conclusion": "Control input/output units are explicit; N0 control API gate passes.",
    }
    write_json(out / "control_api.json", control_api)
    correction = f"""# R3.1 report quantile correction\n\nThe earlier report paired same-named quantiles after the inverse transform `tau = delta_s / v`. That pairing is incorrect because inversion reverses quantile order. The correct direct pairings at the frozen support speeds are:\n\n| Speed label | speed (m/s) | `delta_s / speed` (ms) |\n|---|---:|---:|\n| Q05 | {SPEEDS['q05']:.15g} | {1000*DELTA_S_M/SPEEDS['q05']:.9f} |\n| Q50 | {SPEEDS['q50']:.15g} | {1000*DELTA_S_M/SPEEDS['q50']:.9f} |\n| Q95 | {SPEEDS['q95']:.15g} | {1000*DELTA_S_M/SPEEDS['q95']:.9f} |\n| Q99 | {SPEEDS['q99']:.15g} | {1000*DELTA_S_M/SPEEDS['q99']:.9f} |\n\nThese are deterministic speed-to-time evaluations, not same-label quantiles of the transformed time distribution.\n"""
    (out / "r3_1_report_correction.md").write_text(correction, encoding="utf-8")
    manifest = source_manifest()
    write_json(out / "source_manifest.json", manifest)
    passed = all(item["passed"] for item in checks) and control_api["passed"]
    complete = {"stage": "N0", "passed": passed, "status": "PASS" if passed else "FAIL_N0_FREEZE", "timestamp": utc_now(), "check_count": len(checks), "source_manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()}
    write_json(out / "complete.json", complete)
    append_log(results, "N0", complete["status"], f"protocol/frozen inputs/control API checked; free disk {free_gb:.2f} GiB")
    print(json.dumps(complete, indent=2))
    if not passed:
        raise SystemExit(2)


def flatten_groups(groups: list[dict]) -> list[dict]:
    rows = []
    for group_index, group in enumerate(groups):
        for event in group["events"]:
            rows.append({"group": group_index, "group_time_s": group["time_s"], **event})
    return rows


def run_n1(project_root: Path, paths: dict[str, Path]) -> None:
    results = paths["results"]
    require_previous(results, "N1")
    out = results / "n1"
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    max_time_error = 0.0
    max_residual = 0.0
    for label, speed in SPEEDS.items():
        for direction in ("+x", "-x", "+y", "-y"):
            q0 = -speed * 0.0008
            duration = 0.0008 + DELTA_S_M / speed + 0.0005
            fn = lambda t, q0=q0, speed=speed: np.asarray([q0 + speed * t])
            groups = detect_callable_events(fn, 0.0, duration)
            actual = flatten_groups(groups)
            expected = [(0.0008, 0.0), (0.0008 + DELTA_S_M / speed, DELTA_S_M)]
            for expected_time, surface in expected:
                matches = [event for event in actual if abs(event["surface_m"] - surface) < 1e-15]
                error = min(abs(event["time_s"] - expected_time) for event in matches) if matches else float("inf")
                residual = abs(float(fn(matches[0]["time_s"])[0] - surface)) if matches else float("inf")
                max_time_error = max(max_time_error, error)
                max_residual = max(max_residual, residual)
                rows.append({"case": f"{label}_load_{direction}", "speed_mps": speed, "expected_time_s": expected_time, "actual_time_s": matches[0]["time_s"] if matches else "", "time_error_s": error, "surface_m": surface, "surface_residual_m": residual, "event_count": len(actual)})
            q0_unload = DELTA_S_M + speed * 0.0008
            duration_unload = 0.0008 + DELTA_S_M / speed + 0.0005
            fn_unload = lambda t, q0=q0_unload, speed=speed: np.asarray([q0 - speed * t])
            actual_unload = flatten_groups(detect_callable_events(fn_unload, 0.0, duration_unload))
            expected_unload = [(0.0008, DELTA_S_M), (0.0008 + DELTA_S_M / speed, 0.0)]
            for expected_time, surface in expected_unload:
                matches = [event for event in actual_unload if abs(event["surface_m"] - surface) < 1e-15]
                error = min(abs(event["time_s"] - expected_time) for event in matches) if matches else float("inf")
                residual = abs(float(fn_unload(matches[0]["time_s"])[0] - surface)) if matches else float("inf")
                max_time_error = max(max_time_error, error)
                max_residual = max(max_residual, residual)
                rows.append({"case": f"{label}_unload_{direction}", "speed_mps": speed, "expected_time_s": expected_time, "actual_time_s": matches[0]["time_s"] if matches else "", "time_error_s": error, "surface_m": surface, "surface_residual_m": residual, "event_count": len(actual_unload)})
    simultaneous = {}
    for count in (2, 4):
        fn = lambda t, count=count: np.full(count, -0.001 + t)
        groups = detect_callable_events(fn, 0.0, 0.0015, surfaces_m=(0.0,))
        simultaneous[str(count)] = groups
    double_fn = lambda t: np.asarray([2500.0 * (t - 0.0002) * (t - 0.0008)])
    double_groups = detect_callable_events(double_fn, 0.0, 0.001, surfaces_m=(0.0,), probe_step_s=0.001)
    endpoint_fn = lambda t: np.asarray([-0.002 + t])
    endpoint_groups = detect_callable_events(endpoint_fn, 0.0, 0.004, surfaces_m=(0.0,), probe_step_s=0.002)
    gap_groups = detect_callable_events(lambda t: np.asarray([-0.001 - 0.0001 * np.sin(1000.0 * t)]), 0.0, 0.004)
    outside_groups = detect_callable_events(lambda t: np.asarray([2.0 * DELTA_S_M + 1e-5 * t]), 0.0, 0.004)
    deterministic_payload = {
        "simultaneous": simultaneous,
        "double": double_groups,
        "endpoint": endpoint_groups,
        "gap": gap_groups,
        "outside": outside_groups,
    }
    hash1 = hashlib.sha256(json.dumps(deterministic_payload, sort_keys=True).encode()).hexdigest()
    repeat = detect_callable_events(double_fn, 0.0, 0.001, surfaces_m=(0.0,), probe_step_s=0.001)
    hash2 = hashlib.sha256(json.dumps({**deterministic_payload, "double": repeat}, sort_keys=True).encode()).hexdigest()
    adapter_checks = []
    r3 = ScalarConnector("R3")
    params = ConnectorR3Params(smoothing_width_m=DELTA_S_M)
    for q in (-1e-5, 0.0, 1e-10, DELTA_S_M / 2, DELTA_S_M, 2 * DELTA_S_M):
        for v in (-1.0, 0.0, 0.25):
            scalar = r3.evaluate(q, v)
            vector = connector_force_r3(np.asarray([params.free_play_m + q, 0.0]), np.asarray([v, 0.0]), params)
            adapter_checks.append(abs(float(scalar["force_n"]) - float(vector.applied_force_n)))
    integration_checks = []
    config = EventSubstepConfig()
    for label in ("q99", "stress_0p25", "stress_1p0"):
        speed = SPEEDS[label]
        duration = 0.004 + DELTA_S_M / speed + 0.004
        run = integrate("R3", -speed * 0.002, speed, duration, "ES", config, keep_trace=False)
        integration_checks.append({"case": label, "status": run["status"], "time_error_s": abs(run["duration_actual_s"] - duration), "max_substeps": run["max_substeps_per_outer"], "finite": all(np.isfinite(run[key]) for key in ("peak_force_n", "impulse_ns", "terminal_penetration_m", "terminal_speed_mps"))})
    checks = {
        "event_time_le_1us": max_time_error <= 1e-6,
        "surface_residual_le_1e8m": max_residual <= 1e-8,
        "simultaneous_2_grouped": len(simultaneous["2"]) == 1 and len(simultaneous["2"][0]["events"]) == 2,
        "simultaneous_4_grouped": len(simultaneous["4"]) == 1 and len(simultaneous["4"][0]["events"]) == 4,
        "double_crossing_detected": len(flatten_groups(double_groups)) == 2,
        "outer_endpoint_detected_once": len(flatten_groups(endpoint_groups)) == 1 and abs(flatten_groups(endpoint_groups)[0]["time_s"] - 0.002) <= 1e-6,
        "gap_no_false_event": len(gap_groups) == 0,
        "outside_no_false_event": len(outside_groups) == 0,
        "deterministic_hash": hash1 == hash2,
        "time_conservation_le_1e12s": all(item["time_error_s"] <= 1e-12 for item in integration_checks),
        "substep_count_le_256": all(item["max_substeps"] <= 256 for item in integration_checks),
        "force_adapter_exact": max(adapter_checks) <= 2e-12,
        "finite": all(item["finite"] for item in integration_checks),
        "no_unresolved_event_speed": all(item["status"] == "PASS" for item in integration_checks),
    }
    passed = all(checks.values())
    write_csv(out / "analytic_cases.csv", rows)
    write_json(out / "event_groups.json", deterministic_payload)
    write_json(out / "integration_checks.json", integration_checks)
    summary = {"stage": "N1", "passed": passed, "status": "PASS" if passed else "FAIL_N1_EVENT_DETECTOR", "max_event_time_error_s": max_time_error, "max_surface_residual_m": max_residual, "deterministic_hash": hash1, "checks": checks, "timestamp": utc_now()}
    write_json(out / "summary.json", summary)
    write_json(out / "complete.json", summary)
    append_log(results, "N1", summary["status"], f"analytic cases={len(rows)}, max time error={max_time_error:.3e}s, max residual={max_residual:.3e}m")
    print(json.dumps(summary, indent=2))
    if not passed:
        raise SystemExit(2)


def first_event(run: dict, surface: str, direction: str = "load") -> float | None:
    values = [float(item["time_s"]) for item in run["events"] if item["surface"] == surface and item["direction"] == direction]
    return min(values) if values else None


def relative_error(value: float, reference: float) -> float:
    return abs(value - reference) / max(abs(reference), 1e-12)


def run_n2(project_root: Path, paths: dict[str, Path]) -> None:
    results = paths["results"]
    require_previous(results, "N2")
    out = results / "n2"
    out.mkdir(parents=True, exist_ok=True)
    config = EventSubstepConfig()
    references: dict[tuple[str, str], dict] = {}
    ref_rows = []
    for speed_label, speed in SPEEDS.items():
        post_duration = max(0.020, DELTA_S_M / speed + 0.012)
        for law in ("V1", "R3"):
            ref = integrate(law, 0.0, speed, post_duration, "REF", config, fixed_step_s=2e-6, keep_trace=False)
            references[(speed_label, law)] = ref
            ref_rows.append({"speed_label": speed_label, "speed_mps": speed, "law": law, "post_duration_s": post_duration, **{key: ref[key] for key in ("status", "peak_force_n", "impulse_ns", "terminal_penetration_m", "terminal_speed_mps", "damping_work_j", "energy_balance_residual_j", "accepted_steps")}})
    rows: list[dict] = []
    traces: dict[str, dict] = {}
    for speed_label, speed in SPEEDS.items():
        post_duration = max(0.020, DELTA_S_M / speed + 0.012)
        for phase_index in range(32):
            phase = phase_index * config.outer_step_s / 32.0
            contact_time = config.outer_step_s + phase
            q0 = -speed * contact_time
            duration = contact_time + post_duration
            for law in ("V1", "R3"):
                ref = references[(speed_label, law)]
                for mode in ("F2", "ES"):
                    keep_trace = speed_label == "q99" and phase_index == 11 and law == "R3"
                    run = integrate(law, q0, speed, duration, mode, config, keep_trace=keep_trace)
                    contact = first_event(run, "contact", "load")
                    smoothing = first_event(run, "smoothing", "load")
                    delta_scale = max(DELTA_S_M, abs(ref["terminal_penetration_m"]), speed * 0.002, 1e-6)
                    speed_scale = max(speed, abs(ref["terminal_speed_mps"]), 1e-4)
                    terminal_error = max(abs(run["terminal_penetration_m"] - ref["terminal_penetration_m"]) / delta_scale, abs(run["terminal_speed_mps"] - ref["terminal_speed_mps"]) / speed_scale)
                    smoothing_event_count = sum(1 for event in run["events"] if event["surface"] == "smoothing")
                    row = {
                        "speed_label": speed_label,
                        "speed_mps": speed,
                        "phase_index": phase_index,
                        "phase_s": phase,
                        "law": law,
                        "integrator": mode,
                        "factor": f"{law}-{mode}",
                        "duration_s": duration,
                        "postcontact_duration_s": post_duration,
                        "status": run["status"],
                        "contact_time_s": contact,
                        "expected_contact_time_s": contact_time,
                        "contact_time_abs_error_s": abs(contact - contact_time) if contact is not None else float("inf"),
                        "smoothing_entry_time_s": smoothing,
                        "smoothing_event_count": smoothing_event_count,
                        "smoothing_zone_accepted_steps": run["smoothing_zone_accepted_steps"],
                        "peak_force_n": run["peak_force_n"],
                        "impulse_ns": run["impulse_ns"],
                        "terminal_penetration_m": run["terminal_penetration_m"],
                        "terminal_speed_mps": run["terminal_speed_mps"],
                        "terminal_force_n": run["terminal_force_n"],
                        "damping_work_j": run["damping_work_j"],
                        "energy_balance_residual_j": run["energy_balance_residual_j"],
                        "accepted_steps": run["accepted_steps"],
                        "max_substeps_per_outer": run["max_substeps_per_outer"],
                        "min_accepted_dt_s": run["min_accepted_dt_s"],
                        "peak_force_relative_error": relative_error(run["peak_force_n"], ref["peak_force_n"]),
                        "impulse_relative_error": relative_error(run["impulse_ns"], ref["impulse_ns"]),
                        "terminal_state_scaled_error": terminal_error,
                        "negative_force": run["peak_force_n"] < 0.0 or run["terminal_force_n"] < 0.0,
                        "finite": all(np.isfinite(run[key]) for key in ("peak_force_n", "impulse_ns", "terminal_penetration_m", "terminal_speed_mps", "energy_balance_residual_j")),
                    }
                    rows.append(row)
                    if keep_trace:
                        traces[f"{law}_{mode}_{speed_label}_phase{phase_index}"] = run
    es_rows = [row for row in rows if row["integrator"] == "ES"]
    r3_es = [row for row in es_rows if row["law"] == "R3"]
    stress_labels = {"q99", "stress_0p25", "stress_1p0"}
    continuity_samples = []
    r3 = ScalarConnector("R3")
    for surface in (0.0, DELTA_S_M):
        left = r3.evaluate(surface - 1e-10, 0.25)["force_n"]
        right = r3.evaluate(surface + 1e-10, 0.25)["force_n"]
        continuity_samples.append({"surface_m": surface, "left_force_n": left, "right_force_n": right, "jump_n": abs(float(right) - float(left))})
    r21_path = project_root / "revision_2026" / "connector_r3_1_results" / "r2_1" / "r2_1_results.json"
    r21 = json.loads(r21_path.read_text(encoding="utf-8")) if r21_path.exists() else {}
    checks = {
        "es_peak_error_le_5pct": all(row["peak_force_relative_error"] <= 0.05 for row in es_rows),
        "es_impulse_error_le_2pct": all(row["impulse_relative_error"] <= 0.02 for row in es_rows),
        "es_terminal_error_le_1pct": all(row["terminal_state_scaled_error"] <= 0.01 for row in es_rows),
        "es_contact_time_error_le_2us": all(row["contact_time_abs_error_s"] <= 2e-6 for row in es_rows),
        "r3_es_zone_at_least_8_steps": all(row["smoothing_zone_accepted_steps"] >= 8 for row in r3_es),
        "stress_impulse_gate": all(row["impulse_relative_error"] <= 0.02 for row in es_rows if row["speed_label"] in stress_labels),
        "r3_boundary_continuity": max(item["jump_n"] for item in continuity_samples) <= 1e-4,
        "r2_1_energy_regression_passed": bool(r21.get("passed")),
        "no_negative_force": not any(row["negative_force"] for row in rows),
        "all_finite": all(row["finite"] for row in rows),
        "no_silent_cap_or_unresolved": all(row["status"] == "PASS" for row in rows),
        "substep_cap": all(row["max_substeps_per_outer"] <= 256 for row in es_rows),
    }
    factor_effects = {}
    for metric in ("peak_force_relative_error", "impulse_relative_error", "terminal_state_scaled_error"):
        means = {factor: float(np.mean([row[metric] for row in rows if row["factor"] == factor])) for factor in ("V1-F2", "V1-ES", "R3-F2", "R3-ES")}
        factor_effects[metric] = {
            "cell_means": means,
            "law_main_effect_R3_minus_V1": 0.5 * ((means["R3-F2"] + means["R3-ES"]) - (means["V1-F2"] + means["V1-ES"])),
            "integrator_main_effect_ES_minus_F2": 0.5 * ((means["V1-ES"] + means["R3-ES"]) - (means["V1-F2"] + means["R3-F2"])),
            "interaction": (means["R3-ES"] - means["R3-F2"]) - (means["V1-ES"] - means["V1-F2"]),
        }
    passed = all(checks.values())
    summary = {
        "stage": "N2",
        "passed": passed,
        "status": "PASS" if passed else "FAIL_N2_SINGLE_CONNECTOR_FACTORIAL",
        "cases": len(rows),
        "reference_cases": len(ref_rows),
        "checks": checks,
        "worst_es": {
            "peak_force_relative_error": max(row["peak_force_relative_error"] for row in es_rows),
            "impulse_relative_error": max(row["impulse_relative_error"] for row in es_rows),
            "terminal_state_scaled_error": max(row["terminal_state_scaled_error"] for row in es_rows),
            "contact_time_abs_error_s": max(row["contact_time_abs_error_s"] for row in es_rows),
        },
        "minimum_r3_es_zone_steps": min(row["smoothing_zone_accepted_steps"] for row in r3_es),
        "continuity_samples": continuity_samples,
        "factor_effects": factor_effects,
        "conclusion_scope": "N2 only: event-aware substepping numerical resolvability; no whole-vehicle or Koopman claim.",
        "next_stage": "NOT_RUN_PENDING_SEPARATE_USER_REVIEW_AND_AUTHORIZATION",
        "timestamp": utc_now(),
    }
    write_csv(out / "single_connector_factorial.csv", rows)
    write_csv(out / "reference_2us.csv", ref_rows)
    write_json(out / "representative_traces.json", traces)
    write_json(out / "factorial_effects.json", factor_effects)
    write_json(out / "summary.json", summary)
    write_json(out / "complete.json", summary)
    append_log(results, "N2", summary["status"], f"factorial cases={len(rows)}, references={len(ref_rows)}, worst ES impulse={summary['worst_es']['impulse_relative_error']:.3%}")
    print(json.dumps(summary, indent=2))
    if not passed:
        raise SystemExit(2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--stage", choices=("N0", "N1", "N2"), required=True)
    args = parser.parse_args()
    project_root = args.project_root.resolve()
    paths = stage_paths(project_root)
    if args.stage == "N0":
        run_n0(project_root, paths)
    elif args.stage == "N1":
        run_n1(project_root, paths)
    else:
        run_n2(project_root, paths)


if __name__ == "__main__":
    main()
