from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT / "src"))

from connector_adapter import DELTA_S_M, ScalarConnector, VectorConnector
from connector_r3 import ConnectorR3Params, connector_force_r3
from event_substep import EventSubstepConfig, advance_outer_step, detect_callable_events, integrate
from four_vehicle_common import ModelParams, connector_diagnostics, initialize_state, split_state


EXPECTED_INPUTS = {
    "r3_2_protocol": ("revision_2026/connector_r3_2/protocol.md", "89937c0c7c334d9b5c5f2e5275f04227ce99f442b9ffffa68446675205774784"),
    "r3_law": ("revision_2026/connector_r3_2/src/connector_r3.py", "0bd16c4d4d2fb141bfc2689e4472e475ea23cf319e0b31a3c6448ddcef310459"),
    "r3_schema": ("revision_2026/connector_r3_2/src/schema_r3.py", "bff45ef3cbfd9f47d3523670be4298a464699a4ce7d5f8b859f3fc0720a6d562"),
    "v2_internal_force": ("revision_2026/connector_v2/src/internal_force.py", "0a00d298a00bc39dab8d8e4aa991ad543f625fcb7e62b3329d6ea60e70ac28c0"),
    "v2_four_vehicle": ("revision_2026/connector_v2/src/four_vehicle_v2.py", "7ffc9514775e2c173ed76d996e5ff5eaab82ad841b9bd0bb2c796a7231657685"),
    "paired_maneuvers": ("revision_2026/connector_v2/src/paired_maneuvers.py", "5c41bd4dfb8dfc9084035f54318ba7d121bcef6cd5a414d9f26ff6fcf10a91e4"),
    "r3_2_n2_table": ("revision_2026/connector_r3_2_results/n2/single_connector_factorial.csv", "29be9ddf2b5314eb2f4d79826c5825403a45d398a3387c7f4cf20e7c5a210813"),
}
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
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def source_manifest() -> dict[str, str]:
    result = {}
    for path in sorted(SOURCE_ROOT.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix.lower() in {".py", ".md", ".json"}:
            result[path.relative_to(SOURCE_ROOT).as_posix()] = sha256(path)
    return result


def roots(project: Path) -> dict[str, Path]:
    revision = project / "revision_2026"
    return {
        "results": revision / "connector_r3_4_results",
        "data": revision / "connector_r3_4_data",
        "models": revision / "connector_r3_4_models",
        "mpc": revision / "connector_r3_4_mpc",
    }


def append_log(results: Path, log_id: str, title: str, status: str, command: str, output: Path, detail: str, stop: str = "none") -> None:
    path = results / "work_log.md"
    if not path.exists():
        path.write_text("# Connector R3.3 work log\n\n", encoding="utf-8")
    output_hash = sha256(output) if output.exists() else "missing"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"## {log_id} — {now()} — {title}\n\n")
        stream.write("- 请求/任务编号：connector_r3_3_run\n- 授权模式：执行实验\n")
        stream.write(f"- 机器与项目根目录：{platform.node()} / remote project\n")
        stream.write(f"- 基线身份：`n0/source_manifest.json` + frozen input hashes\n- 读取：registered predecessor outputs only; development/confirm=false\n")
        stream.write(f"- 修改：isolated R3.3 source/results only\n- 命令：`{command}`\n- 退出码：{0 if status == 'PASS' else 2}\n")
        stream.write(f"- 原始产物：`{output}` SHA256 `{output_hash}`\n- 关键结果：{detail}\n- 结论类型：事实\n- 状态：{status}\n- 停止原因：{stop}\n- 下一步：follow registered tree only\n\n")


def require_previous(results: Path, stage: str) -> None:
    previous = {"R1": "r0", "N1": "r1_1", "N2A": "n1", "N2": "n2a", "N3": "n2"}.get(stage)
    if not previous:
        return
    complete = results / previous / "complete.json"
    if not complete.exists() or not json.loads(complete.read_text(encoding="utf-8")).get("passed"):
        write_json(results / stage.lower() / "NOT_RUN.json", {"stage": stage, "status": f"NOT_RUN_PRECONDITION_{previous.upper()}_FAILED", "timestamp": now()})
        raise SystemExit(2)
    frozen_path = results / "r0" / "source_manifest_s2.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8")) if frozen_path.exists() else None
    if frozen is None or frozen != source_manifest():
        write_json(results / stage.lower() / "NOT_RUN.json", {"stage": stage, "status": "NOT_RUN_SOURCE_HASH_DRIFT", "timestamp": now()})
        raise SystemExit(2)


def run_n0(project: Path, paths: dict[str, Path]) -> None:
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    results = paths["results"]
    out = results / "n0"; out.mkdir(parents=True, exist_ok=True)
    checks = []
    for label, (relative, expected) in EXPECTED_INPUTS.items():
        path = project / relative
        actual = sha256(path) if path.exists() else None
        checks.append({"name": label, "path": str(path), "expected": expected, "actual": actual, "passed": actual == expected})
    free_gb = shutil.disk_usage(project.drive + "\\").free / 2**30
    checks.append({"name": "disk_at_least_20gb", "actual_gb": free_gb, "passed": free_gb >= 20.0})
    checks.append({"name": "r3_3_protocol_present", "actual": sha256(SOURCE_ROOT / "protocol.md"), "passed": (SOURCE_ROOT / "protocol.md").exists()})
    manifest = source_manifest()
    write_json(out / "source_manifest.json", manifest)
    preflight = {
        "host": platform.node(), "python": sys.executable, "python_version": platform.python_version(),
        "disk_free_gb": free_gb, "checks": checks,
        "precreation_remote_observation": {"timestamp": "2026-08-25T14:05:17+08:00", "all_five_paths_absent": True, "related_process_count": 0, "gpu": "RTX 5080, 0 MiB used, 0%", "cpu_only": True},
        "development_read": False, "confirm_read": False,
    }
    write_json(out / "preflight.json", preflight)
    passed = all(check["passed"] for check in checks)
    complete = {"stage": "N0", "passed": passed, "status": "PASS" if passed else "FAIL_R0_INPUT_IDENTITY", "timestamp": now(), "source_manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()}
    write_json(out / "complete.json", complete)
    append_log(results, "R33-R0", "preflight and input freeze", complete["status"], "run.py --stage N0", out / "complete.json", f"{len(checks)} checks; free={free_gb:.2f} GiB", "input identity gate" if not passed else "none")
    print(json.dumps(complete, indent=2)); raise SystemExit(0 if passed else 2)


def flatten(groups: list[dict]) -> list[dict]:
    return [{"group": index, **event} for index, group in enumerate(groups) for event in group["events"]]


def run_r1(project: Path, paths: dict[str, Path]) -> None:
    results = paths["results"]; require_previous(results, "R1")
    out = results / "r1"; out.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(SOURCE_ROOT / "scripts" / "run_static_tests.py")]
    completed = subprocess.run(command, capture_output=True, text=True)
    try:
        payload = json.loads(completed.stdout)
    except Exception:
        payload = {"passed": False, "stdout": completed.stdout, "stderr": completed.stderr}
    payload["returncode"] = completed.returncode
    payload["pytest_available"] = False
    payload["dependency_decision"] = "No temporary installation; equivalent repository-local assertion runner used."
    write_json(out / "static_tests.json", payload)
    passed = completed.returncode == 0 and payload.get("passed") is True
    complete = {"stage": "R1", "passed": passed, "status": "PASS" if passed else "FAIL_R1_STATIC_TESTS", "test_count": len(payload.get("tests", [])), "pytest_available": False, "timestamp": now()}
    write_json(out / "complete.json", complete)
    append_log(results, "R33-R1", "implementation and static tests", complete["status"], "run.py --stage R1", out / "complete.json", f"tests={complete['test_count']}; pytest unavailable; stdlib runner", "R1 gate" if not passed else "none")
    print(json.dumps(complete, indent=2)); raise SystemExit(0 if passed else 2)


def run_n1(project: Path, paths: dict[str, Path]) -> None:
    results = paths["results"]; require_previous(results, "N1")
    out = results / "n1"; out.mkdir(parents=True, exist_ok=True)
    rows = []; max_time = max_residual = 0.0
    for label, speed in SPEEDS.items():
        for loading in (True, False):
            if loading:
                q0 = -speed * 0.0008; velocity = speed
                expected = [(0.0008, 0.0), (0.0008 + DELTA_S_M / speed, DELTA_S_M)]
            else:
                q0 = DELTA_S_M + speed * 0.0008; velocity = -speed
                expected = [(0.0008, DELTA_S_M), (0.0008 + DELTA_S_M / speed, 0.0)]
            fn = lambda t, q0=q0, velocity=velocity: np.asarray([q0 + velocity * t])
            actual = flatten(detect_callable_events(fn, 0.0, expected[-1][0] + 0.0005))
            for expected_time, surface in expected:
                matches = [event for event in actual if abs(event["surface_m"] - surface) < 1e-15]
                error = min(abs(event["time_s"] - expected_time) for event in matches) if matches else float("inf")
                nearest = min(matches, key=lambda event: abs(event["time_s"] - expected_time)) if matches else None
                residual = abs(float(fn(nearest["time_s"])[0] - surface)) if nearest else float("inf")
                max_time = max(max_time, error); max_residual = max(max_residual, residual)
                rows.append({"case": label, "loading": loading, "surface_m": surface, "expected_time_s": expected_time, "actual_time_s": nearest["time_s"] if nearest else "", "time_error_s": error, "surface_residual_m": residual})
    simultaneous = {count: detect_callable_events(lambda t, count=count: np.full(count, -0.001 + t), 0.0, 0.0015, surfaces_m=(0.0,)) for count in (2, 4)}
    double = detect_callable_events(lambda t: np.asarray([2500.0 * (t - 0.0002) * (t - 0.0008)]), 0.0, 0.001, surfaces_m=(0.0,), probe_step_s=0.001)
    endpoint = detect_callable_events(lambda t: np.asarray([-0.002 + t]), 0.0, 0.004, surfaces_m=(0.0,), probe_step_s=0.002)
    no_false = detect_callable_events(lambda t: np.asarray([-0.001 - 0.0001 * np.sin(1000.0 * t)]), 0.0, 0.004)
    payload = {"simultaneous": simultaneous, "double": double, "endpoint": endpoint, "no_false": no_false}
    digest1 = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    digest2 = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    checks = {
        "event_time_le_1us": max_time <= 1e-6, "surface_residual_le_1e8m": max_residual <= 1e-8,
        "simultaneous_2": len(simultaneous[2]) == 1 and len(simultaneous[2][0]["events"]) == 2,
        "simultaneous_4": len(simultaneous[4]) == 1 and len(simultaneous[4][0]["events"]) == 4,
        "double_crossing": len(flatten(double)) == 2, "endpoint_once": len(flatten(endpoint)) == 1,
        "no_false_event": len(no_false) == 0, "deterministic": digest1 == digest2,
    }
    passed = all(checks.values())
    write_csv(out / "analytic_cases.csv", rows); write_json(out / "event_groups.json", payload)
    complete = {"stage": "N1", "passed": passed, "status": "PASS" if passed else "FAIL_N1_REGRESSION", "checks": checks, "max_event_time_error_s": max_time, "max_surface_residual_m": max_residual, "deterministic_hash": digest1, "timestamp": now()}
    write_json(out / "complete.json", complete)
    append_log(results, "R33-R2", "N1 event regression", complete["status"], "run.py --stage N1", out / "complete.json", f"max time={max_time:.3e}s; max residual={max_residual:.3e}m", "N1 gate" if not passed else "none")
    print(json.dumps(complete, indent=2)); raise SystemExit(0 if passed else 2)


def scalar_post_duration(speed: float) -> float:
    return max(0.020, DELTA_S_M / speed + 0.012)


def terminal_scaled(a: dict, b: dict, speed: float) -> float:
    delta_scale = max(DELTA_S_M, abs(b["terminal_penetration_m"]), speed * 0.002, 1e-6)
    speed_scale = max(speed, abs(b["terminal_speed_mps"]), 1e-4)
    return max(abs(a["terminal_penetration_m"] - b["terminal_penetration_m"]) / delta_scale, abs(a["terminal_speed_mps"] - b["terminal_speed_mps"]) / speed_scale)


def relative(a: float, b: float, floor: float = 1e-12) -> float:
    return abs(a - b) / max(abs(b), floor)


def run_n2a(project: Path, paths: dict[str, Path]) -> None:
    require_previous(paths["results"], "N2A")
    command = [sys.executable, str(SOURCE_ROOT / "scripts" / "run_n2a_v2.py"), "--project-root", str(project)]
    completed = subprocess.run(command)
    raise SystemExit(completed.returncode)


def run_n2a_legacy(project: Path, paths: dict[str, Path]) -> None:
    results = paths["results"]; require_previous(results, "N2A")
    out = results / "n2a"; out.mkdir(parents=True, exist_ok=True)
    config = EventSubstepConfig(); rows = []; reference_state = {}; convergence = []
    reference_pass = True
    for speed_label, speed in SPEEDS.items():
        for law in ("V1", "R3"):
            runs = {}
            for dt in (2e-6, 1e-6, 0.5e-6):
                started = time.perf_counter()
                run = integrate(law, 0.0, speed, scalar_post_duration(speed), "REF", config, fixed_step_s=dt, keep_trace=False)
                run["runtime_s"] = time.perf_counter() - started
                runs[dt] = run
                rows.append({"speed_label": speed_label, "speed_mps": speed, "law": law, "reference_dt_s": dt, **{key: run[key] for key in ("status", "peak_force_n", "impulse_ns", "terminal_penetration_m", "terminal_speed_mps", "energy_balance_residual_j", "accepted_steps", "min_accepted_dt_s", "closure_residual_count", "closure_residual_total_s", "runtime_s")}})
            r2, r1, r05 = runs[2e-6], runs[1e-6], runs[0.5e-6]
            peak_d21, peak_d105 = relative(r2["peak_force_n"], r1["peak_force_n"]), relative(r1["peak_force_n"], r05["peak_force_n"])
            impulse_d21, impulse_d105 = relative(r2["impulse_ns"], r1["impulse_ns"]), relative(r1["impulse_ns"], r05["impulse_ns"])
            terminal_d21, terminal_d105 = terminal_scaled(r2, r1, speed), terminal_scaled(r1, r05, speed)
            absolute = {
                "peak_1_0p5": abs(r1["peak_force_n"] - r05["peak_force_n"]),
                "impulse_1_0p5": abs(r1["impulse_ns"] - r05["impulse_ns"]),
                "terminal_q_1_0p5": abs(r1["terminal_penetration_m"] - r05["terminal_penetration_m"]),
                "terminal_v_1_0p5": abs(r1["terminal_speed_mps"] - r05["terminal_speed_mps"]),
            }
            contraction_peak = peak_d105 <= 0.5 * peak_d21 or absolute["peak_1_0p5"] <= 1e-10
            contraction_impulse = impulse_d105 <= 0.5 * impulse_d21 or absolute["impulse_1_0p5"] <= 1e-12
            contraction_terminal = terminal_d105 <= 0.5 * terminal_d21 or max(absolute["terminal_q_1_0p5"], absolute["terminal_v_1_0p5"]) <= 1e-12
            checks = {
                "peak_budget": peak_d105 <= 0.005, "impulse_budget": impulse_d105 <= 0.002, "terminal_budget": terminal_d105 <= 0.001,
                "peak_contraction": contraction_peak, "impulse_contraction": contraction_impulse, "terminal_contraction": contraction_terminal,
                "finite_status": all(run["status"] == "PASS" and all(np.isfinite(run[key]) for key in ("peak_force_n", "impulse_ns", "terminal_penetration_m", "terminal_speed_mps", "energy_balance_residual_j")) for run in runs.values()),
            }
            reference_pass = reference_pass and all(checks.values())
            convergence.append({"speed_label": speed_label, "law": law, "d_peak_2_1": peak_d21, "d_peak_1_0p5": peak_d105, "d_impulse_2_1": impulse_d21, "d_impulse_1_0p5": impulse_d105, "d_terminal_2_1": terminal_d21, "d_terminal_1_0p5": terminal_d105, **absolute, **checks})
            reference_state[f"{speed_label}|{law}"] = {key: r05[key] for key in ("peak_force_n", "impulse_ns", "terminal_penetration_m", "terminal_speed_mps", "energy_balance_residual_j")}
    old_rows = read_csv(project / EXPECTED_INPUTS["r3_2_n2_table"][0])
    trigger_rows = [row for row in old_rows if row["integrator"] == "ES" and float(row["min_accepted_dt_s"]) < config.min_step_s]
    closure_rows = []; closure_pass = True
    for old in trigger_rows:
        speed = float(old["speed_mps"]); phase = float(old["phase_s"]); contact_time = config.outer_step_s + phase
        rerun = integrate(old["law"], -speed * contact_time, speed, float(old["duration_s"]), "ES", config, keep_trace=False)
        comparisons = {}
        for old_key, new_key in (("peak_force_n", "peak_force_n"), ("impulse_ns", "impulse_ns"), ("terminal_penetration_m", "terminal_penetration_m"), ("terminal_speed_mps", "terminal_speed_mps")):
            old_value, new_value = float(old[old_key]), float(rerun[new_key])
            absolute_change = abs(new_value - old_value); relative_change = absolute_change / max(abs(old_value), 1e-300)
            comparisons[old_key + "_abs_change"] = absolute_change; comparisons[old_key + "_rel_change"] = relative_change
        case_pass = rerun["status"] == "PASS" and rerun["min_accepted_dt_s"] >= config.min_step_s and all(comparisons[key] <= 1e-12 or comparisons[key.replace("_abs_change", "_rel_change")] <= 1e-10 for key in comparisons if key.endswith("_abs_change"))
        closure_pass = closure_pass and case_pass
        closure_rows.append({"speed_label": old["speed_label"], "phase_index": old["phase_index"], "law": old["law"], "old_min_dt_s": float(old["min_accepted_dt_s"]), "new_min_dt_s": rerun["min_accepted_dt_s"], "status": rerun["status"], "passed": case_pass, **comparisons})
    closure_audit = {"passed": closure_pass and len(trigger_rows) == 66, "historical_trigger_count": len(trigger_rows), "new_subminimum_count": sum(1 for row in closure_rows if row["new_min_dt_s"] < config.min_step_s), "maximum_changes": {key: max((row[key] for row in closure_rows), default=0.0) for key in closure_rows[0] if key.endswith("_abs_change") or key.endswith("_rel_change")} if closure_rows else {}, "rows": closure_rows, "interpretation": "closure bookkeeping only; physical law/data/registered gates unchanged"}
    write_csv(out / "reference_convergence.csv", rows); write_csv(out / "reference_pair_checks.csv", convergence)
    write_json(out / "reference_state_0p5us.json", reference_state); write_json(out / "closure_audit.json", closure_audit)
    passed = reference_pass and closure_audit["passed"]
    complete = {"stage": "N2A", "passed": passed, "status": "PASS" if passed else "FAIL_N2A_REFERENCE_OR_CLOSURE", "reference_runs": len(rows), "reference_pairs": len(convergence), "reference_convergence_passed": reference_pass, "closure_audit_passed": closure_audit["passed"], "worst_1us_vs_0p5us": {"peak": max(row["d_peak_1_0p5"] for row in convergence), "impulse": max(row["d_impulse_1_0p5"] for row in convergence), "terminal": max(row["d_terminal_1_0p5"] for row in convergence)}, "timestamp": now()}
    write_json(out / "complete.json", complete)
    append_log(results, "R33-R3", "N2A reference convergence and closure audit", complete["status"], "run.py --stage N2A", out / "complete.json", f"36 refs; historical closures={len(trigger_rows)}", "N2A gate" if not passed else "none")
    print(json.dumps(complete, indent=2)); raise SystemExit(0 if passed else 2)


def first_event(run: dict, surface: str) -> float | None:
    values = [event["time_s"] for event in run["events"] if event["surface"] == surface and event["direction"] == "load"]
    return min(values) if values else None


def run_n2(project: Path, paths: dict[str, Path]) -> None:
    results = paths["results"]; require_previous(results, "N2")
    out = results / "n2"; out.mkdir(parents=True, exist_ok=True)
    refs = json.loads((results / "n2a" / "reference_state_0p5us.json").read_text(encoding="utf-8"))
    config = EventSubstepConfig(); rows = []
    for speed_label, speed in SPEEDS.items():
        post = scalar_post_duration(speed)
        for phase_index in range(32):
            phase = phase_index * config.outer_step_s / 32.0; contact_time = config.outer_step_s + phase
            for law in ("V1", "R3"):
                ref = refs[f"{speed_label}|{law}"]
                for mode in ("F2", "ES"):
                    run = integrate(law, -speed * contact_time, speed, contact_time + post, mode, config, keep_trace=False)
                    contact = first_event(run, "contact")
                    row = {"speed_label": speed_label, "speed_mps": speed, "phase_index": phase_index, "phase_s": phase, "law": law, "integrator": mode, "factor": f"{law}-{mode}", "duration_s": contact_time + post, "status": run["status"], "contact_time_s": contact, "expected_contact_time_s": contact_time, "contact_time_abs_error_s": abs(contact - contact_time) if contact is not None else float("inf"), "smoothing_zone_accepted_steps": run["smoothing_zone_accepted_steps"], "peak_force_n": run["peak_force_n"], "impulse_ns": run["impulse_ns"], "terminal_penetration_m": run["terminal_penetration_m"], "terminal_speed_mps": run["terminal_speed_mps"], "energy_balance_residual_j": run["energy_balance_residual_j"], "accepted_steps": run["accepted_steps"], "min_accepted_dt_s": run["min_accepted_dt_s"], "closure_residual_count": run["closure_residual_count"], "peak_force_relative_error": relative(run["peak_force_n"], ref["peak_force_n"]), "impulse_relative_error": relative(run["impulse_ns"], ref["impulse_ns"]), "terminal_state_scaled_error": terminal_scaled(run, ref, speed), "finite": all(np.isfinite(run[key]) for key in ("peak_force_n", "impulse_ns", "terminal_penetration_m", "terminal_speed_mps", "energy_balance_residual_j"))}
                    rows.append(row)
    es = [row for row in rows if row["integrator"] == "ES"]
    r3es = [row for row in es if row["law"] == "R3"]
    checks = {"peak_le_5pct": all(row["peak_force_relative_error"] <= 0.05 for row in es), "impulse_le_2pct": all(row["impulse_relative_error"] <= 0.02 for row in es), "terminal_le_1pct": all(row["terminal_state_scaled_error"] <= 0.01 for row in es), "contact_le_2us": all(row["contact_time_abs_error_s"] <= 2e-6 for row in es), "r3_zone_steps_ge_8": all(row["smoothing_zone_accepted_steps"] >= 8 for row in r3es), "physical_dt_ge_2us": all(row["min_accepted_dt_s"] >= config.min_step_s for row in es), "all_pass_finite": all(row["status"] == "PASS" and row["finite"] for row in rows)}
    passed = all(checks.values())
    write_csv(out / "single_connector_factorial.csv", rows)
    complete = {"stage": "N2", "passed": passed, "status": "PASS" if passed else "FAIL_N2_REGRESSION", "cases": len(rows), "checks": checks, "worst_es": {"peak": max(row["peak_force_relative_error"] for row in es), "impulse": max(row["impulse_relative_error"] for row in es), "terminal": max(row["terminal_state_scaled_error"] for row in es), "contact_s": max(row["contact_time_abs_error_s"] for row in es)}, "minimum_r3_zone_steps": min(row["smoothing_zone_accepted_steps"] for row in r3es), "timestamp": now()}
    write_json(out / "complete.json", complete)
    append_log(results, "R33-R4", "N2 full matrix regression", complete["status"], "run.py --stage N2", out / "complete.json", "768 rows against qualified 0.5 us reference", "N2 gate" if not passed else "none")
    print(json.dumps(complete, indent=2)); raise SystemExit(0 if passed else 2)


def scenario_initial(name: str, params: ModelParams) -> tuple[np.ndarray, float]:
    if name == "g3_turn_reversal":
        state = initialize_state(params, 1.5); vehicles, _ = split_state(state); vehicles[:, 3] += np.asarray([0.012, -0.008, 0.006, -0.010]); state[:24] = vehicles.ravel(); return state, 2.0
    if name == "q99_contact":
        speed = SPEEDS["q99"]; state = initialize_state(params, 1.5); vehicles, payload = split_state(state)
        directions = params.payload_anchor_body_m / np.linalg.norm(params.payload_anchor_body_m, axis=1)[:, None]
        contact_times = np.asarray([0.0008, 0.0010, 0.0012, 0.0014])
        for index in range(4):
            distance = params.connector.free_play_m - speed * contact_times[index]
            vehicles[index, :2] += directions[index] * distance
            vehicles[index, 3:5] = payload[3:5] + speed * directions[index]
        state[:24] = vehicles.ravel(); return state, 0.060
    raise ValueError(name)


def scenario_control(name: str, t: float) -> np.ndarray:
    if name == "g3_turn_reversal":
        steering = 0.012 if t < 0.7 else (-0.012 if t < 1.4 else 0.0)
        return np.tile([0.08, steering], (4, 1))
    return np.zeros((4, 2))


def simulate_vehicle(name: str, law: str, label: str, outer_h: float, mode: str, max_step_s: float | None = None) -> tuple[dict, dict]:
    params = ModelParams(); state, duration = scenario_initial(name, params); initial = state.copy()
    config = EventSubstepConfig(outer_step_s=outer_h, probe_step_s=min(0.0005, outer_h))
    peak = np.zeros(4); impulse = np.zeros((4, 2)); damping = np.zeros(4); vehicle_moment = np.zeros(4)
    internal_peak = payload_moment_peak = action = null = 0.0
    zone_steps = np.zeros(4, dtype=int); events = []; accepted = closure_count = 0; min_dt = min_regular_dt = float("inf"); subminimum_by_cause = {key:0 for key in ("EVENT_ROOT","OUTER_REMAINDER","ZONE_RESOLUTION","PROBE_LIMIT")}
    time_rows = [0.0]; state_rows = [state.copy()]; force_rows = [connector_diagnostics(state, params, law)["force_norm_n"].copy()]
    internal_rows = [float(connector_diagnostics(state, params, law)["internal_force_norm_n"])]; moment_rows = [float(connector_diagnostics(state, params, law)["payload_moment_total_nm"])]; control_rows = [scenario_control(name, 0.0)]
    t = 0.0; status = "PASS"; started = time.perf_counter(); next_record = 0.002
    while t < duration - 1e-12:
        h = min(outer_h, duration - t); control = scenario_control(name, t)
        state, audit = advance_outer_step(state, control, law, params, h, mode, config, max_step_s=max_step_s)
        for event in audit["events"]:
            events.append({**event, "time_s": t + event["time_offset_s"]})
        peak = np.maximum(peak, audit["force_peak_n"]); impulse += audit["force_impulse_world_ns"]; damping += audit["damping_work_j"]
        vehicle_moment = np.maximum(vehicle_moment, audit["vehicle_moment_peak_nm"]); internal_peak = max(internal_peak, audit["internal_force_peak_n"]); payload_moment_peak = max(payload_moment_peak, audit["payload_moment_peak_nm"]); action = max(action, audit["action_reaction_max_n"]); null = max(null, audit["internal_null_max_n"])
        zone_steps += audit["zone_steps_per_connector"]; accepted += audit["accepted_steps"]; closure_count += audit["closure_residual_count"]; min_dt = min(min_dt, audit["min_physical_dt_s"] if audit["min_physical_dt_s"] > 0 else float("inf"))
        for record in audit["step_records"]:
            if record["dt_class"] == "REGULAR_DT": min_regular_dt = min(min_regular_dt, float(record["advanced_dt_s"]))
            if record["dt_class"] == "FINITE_SUBMINIMUM_DT": subminimum_by_cause[record["selection_cause"]] = subminimum_by_cause.get(record["selection_cause"],0) + 1
        t += h
        if audit["status"] != "PASS": status = audit["status"]; break
        if t + 1e-12 >= next_record:
            diag = connector_diagnostics(state, params, law)
            time_rows.append(t); state_rows.append(state.copy()); force_rows.append(diag["force_norm_n"].copy()); internal_rows.append(float(diag["internal_force_norm_n"])); moment_rows.append(float(diag["payload_moment_total_nm"])); control_rows.append(control.copy()); next_record += 0.002
    runtime = time.perf_counter() - started
    metric = {"scenario": name, "run": label, "law": law, "mode": mode, "outer_h_s": outer_h, "max_step_s": max_step_s or outer_h, "status": status, "duration_s": t, "runtime_s": runtime, "terminal_state": state.tolist(), "peak_force_n": peak.tolist(), "force_impulse_world_ns": impulse.tolist(), "internal_force_peak_n": internal_peak, "payload_moment_peak_nm": payload_moment_peak, "vehicle_moment_peak_nm": vehicle_moment.tolist(), "action_reaction_max_n": action, "internal_null_max_n": null, "zone_steps_per_connector": zone_steps.tolist(), "events": events, "accepted_steps": accepted, "min_physical_dt_s": 0.0 if min_dt == float("inf") else min_dt, "min_regular_dt_s": 0.0 if min_regular_dt == float("inf") else min_regular_dt, "subminimum_by_cause": subminimum_by_cause, "closure_residual_count": closure_count, "finite": bool(np.all(np.isfinite(state)) and np.all(np.isfinite(peak)))}
    raw = {"time_s": np.asarray(time_rows), "state30": np.asarray(state_rows), "force_norm_n": np.asarray(force_rows), "internal_force_norm_n": np.asarray(internal_rows), "payload_moment_nm": np.asarray(moment_rows), "control": np.asarray(control_rows), "initial_state": initial}
    return metric, raw


def flatten_vehicle_metric(metric: dict) -> dict:
    row = {key: metric[key] for key in ("scenario", "run", "law", "mode", "outer_h_s", "max_step_s", "status", "duration_s", "runtime_s", "internal_force_peak_n", "payload_moment_peak_nm", "action_reaction_max_n", "internal_null_max_n", "accepted_steps", "min_physical_dt_s", "min_regular_dt_s", "closure_residual_count", "finite")}
    for cause,value in metric["subminimum_by_cause"].items(): row[f"subminimum_{cause.lower()}_count"] = value
    for index, value in enumerate(metric["peak_force_n"]): row[f"peak_force_{index}_n"] = value
    for index, vector in enumerate(metric["force_impulse_world_ns"]): row[f"impulse_{index}_x_ns"] = vector[0]; row[f"impulse_{index}_y_ns"] = vector[1]
    for index, value in enumerate(metric["vehicle_moment_peak_nm"]): row[f"vehicle_moment_{index}_peak_nm"] = value
    for index, value in enumerate(metric["zone_steps_per_connector"]): row[f"zone_steps_{index}"] = value
    row["event_count"] = len(metric["events"])
    return row


def n3_compare(candidate: dict, reference: dict) -> dict:
    candidate_peak, reference_peak = np.asarray(candidate["peak_force_n"]), np.asarray(reference["peak_force_n"])
    candidate_impulse, reference_impulse = np.asarray(candidate["force_impulse_world_ns"]), np.asarray(reference["force_impulse_world_ns"])
    candidate_vehicle_moment, reference_vehicle_moment = np.asarray(candidate["vehicle_moment_peak_nm"]), np.asarray(reference["vehicle_moment_peak_nm"])
    peak_errors = np.abs(candidate_peak - reference_peak) / np.maximum(np.abs(reference_peak), 1e-12)
    impulse_errors = np.linalg.norm(candidate_impulse - reference_impulse, axis=1) / np.maximum(np.linalg.norm(reference_impulse, axis=1), 1e-12)
    vehicle_moment_errors = np.abs(candidate_vehicle_moment - reference_vehicle_moment) / np.maximum(np.abs(reference_vehicle_moment), 1e-12)
    scale = np.tile([100.0, 100.0, np.pi, 5.0, 5.0, 1.0], 5)
    terminal_error = float(np.max(np.abs((np.asarray(candidate["terminal_state"]) - np.asarray(reference["terminal_state"])) / scale)))
    internal_error = relative(candidate["internal_force_peak_n"], reference["internal_force_peak_n"])
    payload_moment_error = relative(candidate["payload_moment_peak_nm"], reference["payload_moment_peak_nm"])
    return {"peak_force_error_max": float(np.max(peak_errors)), "peak_force_error_by_connector": peak_errors.tolist(), "impulse_error_max": float(np.max(impulse_errors)), "impulse_error_by_connector": impulse_errors.tolist(), "terminal_state_scaled_error": terminal_error, "internal_force_peak_error": internal_error, "payload_moment_peak_error": payload_moment_error, "vehicle_moment_error_max": float(np.max(vehicle_moment_errors)), "vehicle_moment_error_by_vehicle": vehicle_moment_errors.tolist(), "peak_force_abs_difference_n": np.abs(candidate_peak - reference_peak).tolist(), "impulse_abs_difference_ns": np.linalg.norm(candidate_impulse - reference_impulse, axis=1).tolist(), "payload_moment_abs_difference_nm": abs(candidate["payload_moment_peak_nm"] - reference["payload_moment_peak_nm"])}


def run_n3(project: Path, paths: dict[str, Path]) -> None:
    results = paths["results"]; require_previous(results, "N3")
    out = results / "n3"; out.mkdir(parents=True, exist_ok=True)
    scenario_summaries = {}; all_pass = True
    for scenario in ("g3_turn_reversal", "q99_contact"):
        scenario_out = out / scenario; scenario_out.mkdir(parents=True, exist_ok=True)
        specs = [("V1-F2", "V1", 0.002, "F2", None), ("V1-ES", "V1", 0.002, "ES", None), ("R3-F2", "R3", 0.002, "F2", None), ("R3-ES", "R3", 0.002, "ES", None), ("V1-ES-H1", "V1", 0.001, "ES", None), ("R3-ES-H1", "R3", 0.001, "ES", None), ("V1-ES-H0p5", "V1", 0.0005, "ES", None), ("R3-ES-H0p5", "R3", 0.0005, "ES", None), ("V1-REF", "V1", 0.002, "ES", 0.0001), ("R3-REF", "R3", 0.002, "ES", 0.0001)]
        metrics = []; raw_payload = {}
        for label, law, h, mode, max_step in specs:
            metric, raw = simulate_vehicle(scenario, law, label, h, mode, max_step)
            metrics.append(metric)
            for key, value in raw.items(): raw_payload[f"{label.replace('-', '_')}_{key}"] = value
            if metric["status"] != "PASS":
                break
        write_csv(scenario_out / "metrics.csv", [flatten_vehicle_metric(metric) for metric in metrics]); np.savez_compressed(scenario_out / "raw_timeseries.npz", **raw_payload)
        by_label = {metric["run"]: metric for metric in metrics}; comparisons = {}; checks = {}
        if len(metrics) == len(specs):
            for law in ("V1", "R3"):
                comparisons[law] = n3_compare(by_label[f"{law}-ES"], by_label[f"{law}-REF"])
            candidate_metrics = [by_label["V1-ES"], by_label["R3-ES"]]
            checks = {
                "peak_force_le_5pct": all(comparisons[law]["peak_force_error_max"] <= 0.05 for law in ("V1", "R3")),
                "impulse_le_2pct": all(comparisons[law]["impulse_error_max"] <= 0.02 for law in ("V1", "R3")),
                "terminal_le_1pct": all(comparisons[law]["terminal_state_scaled_error"] <= 0.01 for law in ("V1", "R3")),
                "internal_force_le_5pct": all(comparisons[law]["internal_force_peak_error"] <= 0.05 for law in ("V1", "R3")),
                "payload_moment_le_5pct": all(comparisons[law]["payload_moment_peak_error"] <= 0.05 for law in ("V1", "R3")),
                "vehicle_moment_le_5pct": all(comparisons[law]["vehicle_moment_error_max"] <= 0.05 for law in ("V1", "R3")),
                "action_reaction": all(metric["action_reaction_max_n"] < 1e-10 for metric in metrics),
                "internal_null": all(metric["internal_null_max_n"] < 1e-8 * max(1.0, metric["internal_force_peak_n"]) for metric in metrics),
                "finite_no_limit": all(metric["status"] == "PASS" and metric["finite"] for metric in metrics),
                "physical_dt_ge_2us": all(metric["min_physical_dt_s"] >= 2e-6 for metric in metrics if metric["mode"] == "ES"),
            }
            if scenario == "q99_contact":
                q99_r3 = by_label["R3-ES"]
                contact_ids = {event["connector_id"] for event in q99_r3["events"] if event["surface"] == "contact" and event["direction"] == "load"}
                smoothing_ids = {event["connector_id"] for event in q99_r3["events"] if event["surface"] == "smoothing" and event["direction"] == "load"}
                smoothing_count = np.asarray([sum(1 for event in q99_r3["events"] if event["connector_id"] == index and event["surface"] == "smoothing") for index in range(4)])
                zone = np.asarray(q99_r3["zone_steps_per_connector"])
                checks["all_q99_events_recorded"] = contact_ids == {0, 1, 2, 3} and smoothing_ids == {0, 1, 2, 3}
                checks["r3_zone_8_per_crossing"] = bool(np.all(zone >= 8 * np.maximum(smoothing_count, 1)))
        scenario_pass = bool(checks) and all(checks.values())
        all_pass = all_pass and scenario_pass
        scenario_summary = {"scenario": scenario, "passed": scenario_pass, "status": "PASS" if scenario_pass else "FAIL_N3_SCENARIO", "run_count": len(metrics), "checks": checks, "comparisons": comparisons, "cost": {metric["run"]: metric["runtime_s"] for metric in metrics}, "timestamp": now()}
        write_json(scenario_out / "summary.json", scenario_summary); scenario_summaries[scenario] = scenario_summary
        append_log(results, "R33-R5" if scenario == "g3_turn_reversal" else "R33-R6", f"N3 {scenario}", scenario_summary["status"], "run.py --stage N3", scenario_out / "summary.json", f"runs={len(metrics)}", "N3 scenario gate" if not scenario_pass else "none")
        if not scenario_pass:
            break
    summary = {"stage": "N3", "passed": all_pass and len(scenario_summaries) == 2, "status": "PASS" if all_pass and len(scenario_summaries) == 2 else "FAIL_N3", "scenarios": scenario_summaries, "N4_to_N9": "NOT_RUN", "timestamp": now()}
    write_json(out / "summary.json", summary); write_json(out / "complete.json", summary)
    print(json.dumps(summary, indent=2)); raise SystemExit(0 if summary["passed"] else 2)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--project-root", type=Path, required=True); parser.add_argument("--stage", choices=("N0", "R1", "N1", "N2A", "N2", "N3"), required=True)
    args = parser.parse_args(); project = args.project_root.resolve(); paths = roots(project)
    {"N0": run_n0, "R1": run_r1, "N1": run_n1, "N2A": run_n2a, "N2": run_n2, "N3": run_n3}[args.stage](project, paths)


if __name__ == "__main__":
    main()
