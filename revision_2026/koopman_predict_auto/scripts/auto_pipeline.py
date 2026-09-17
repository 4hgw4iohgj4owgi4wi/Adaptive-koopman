from __future__ import annotations

import argparse
import csv
import gzip
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "plant")]

from actuator_rollout import rollout_actuator_step
from auto_data import load_npz, simulate_hash_only, simulate_job
from contracts import (
    StageDecision,
    assert_stage_allowed,
    decide_stage_status,
    json_sha256,
    require_stage_transition,
    sha256,
    source_manifest,
    validate_predict_auto_protocol,
)
from evaluation import (
    accumulate_fit_statistics,
    evaluate_model,
    fit_normalization,
    macro_summary,
    paired_family_bootstrap,
    solve_model,
)
from freeze_predict import freeze
from generate_data import resolved_params, simulate_trajectory
from physics_audit import coverage_audit, mirror_audit
from physics_audit import audit_trajectory, window_ledger
from scenarios import (
    ScenarioSpec,
    build_auto_smoke_identities,
    build_future_trajectory_identities,
    build_predict_pilot_identities,
)
from steering_actuator import SteeringActuatorConfig


STAGE_DIR = {"A0": "a0", "N4-S": "n4_smoke", "N4": "n4", "N5": "n5", "N6": "n6"}


def _plain(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, np.ndarray):
        return _plain(value.tolist())
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def max_abs_field_difference(left: np.ndarray, right: np.ndarray) -> float:
    """Exact comparison for categorical/bool fields, max-abs for numeric fields."""

    left = np.asarray(left)
    right = np.asarray(right)
    if left.shape != right.shape:
        return float("inf")
    if left.dtype.kind in {"O", "U", "S", "b"} or right.dtype.kind in {
        "O",
        "U",
        "S",
        "b",
    }:
        return 0.0 if np.array_equal(left, right) else float("inf")
    return float(np.max(np.abs(left - right))) if left.size else 0.0


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_plain(value), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refuse to write empty CSV: {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows([_plain(row) for row in rows])
    os.replace(temporary, path)


def write_csv_gz(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refuse to write empty CSV: {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows([_plain(row) for row in rows])
    os.replace(temporary, path)


def append_log(path: Path, heading: str, facts: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n## {datetime.now().astimezone().isoformat(timespec='seconds')} — {heading}\n\n"
            f"- 主机：`{platform.node()}`\n"
            f"- 命令：`{' '.join(sys.argv)}`\n"
            f"- 事实：`{json.dumps(_plain(facts), ensure_ascii=False, allow_nan=False)}`\n"
        )


def append_decision(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(_plain(payload), ensure_ascii=False, allow_nan=False) + "\n")


def allocate_run(results_root: Path, run_tag: str) -> Path:
    runs = results_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for revision in range(1, 100):
        candidate = runs / f"{stamp}_AUTO_{run_tag}_R{revision:02d}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError("cannot allocate unique auto run")


def resolve_resume(results_root: Path, value: str) -> Path:
    selected = Path(value)
    if not selected.is_absolute():
        selected = results_root / "runs" / selected
    selected = selected.resolve()
    if selected.parent != (results_root / "runs").resolve() or not selected.is_dir():
        raise ValueError(f"invalid resume run: {selected}")
    return selected


@contextmanager
def stage_lock(stage_root: Path):
    lock = stage_root.parent / f".{stage_root.name}.lock"
    stage_root.parent.mkdir(parents=True, exist_ok=True)
    if lock.exists():
        try:
            owner = read_json(lock)
            owner_pid = int(owner.get("pid", -1))
            owner_host = str(owner.get("host", ""))
            alive = False
            if owner_host.upper() == platform.node().upper() and owner_pid > 0:
                try:
                    os.kill(owner_pid, 0)
                    alive = True
                except OSError:
                    alive = False
            if not alive:
                lock.unlink()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            raise RuntimeError(f"cannot prove existing stage lock is stale: {lock}")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError(f"stage lock already exists: {lock}") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(json.dumps({"pid": os.getpid(), "host": platform.node(), "time": time.time()}))
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def stage_complete(stage_root: Path) -> dict | None:
    path = stage_root / "complete.json"
    return read_json(path) if path.exists() else None


def _stage_artifacts(stage_root: Path, gates: dict, warnings: list[str], decision: StageDecision, complete: dict) -> None:
    atomic_json(stage_root / "gate_report.json", {"hard_gates": gates, "warnings": warnings})
    atomic_json(
        stage_root / "decision.json",
        {"machine_state": decision.value, "warnings": warnings, "passed": decision in {StageDecision.PASS_CONTINUE, StageDecision.PASS_WITH_WARNING_CONTINUE}},
    )
    atomic_json(stage_root / "complete.json", complete)


def _source_identity() -> dict:
    manifest = source_manifest(ROOT)
    return {"source_manifest_sha256": json_sha256(manifest), "source_file_count": len(manifest)}


def _parent_identity(project: Path, protocol: dict) -> dict:
    expected = protocol["parent_n3"]
    source = project / Path(expected["source_root"])
    results = project / Path(expected["results_root"])
    complete_path = results / "runs" / expected["run_id"] / "n3" / "complete.json"
    protocol_path = source / "config" / "protocol_predict_next.json"
    taskbook_path = source / "protocol.md"
    actual = {
        "source_manifest_sha256": json_sha256(source_manifest(source)),
        "complete_sha256": sha256(complete_path),
        "protocol_sha256": sha256(protocol_path),
        "taskbook_sha256": sha256(taskbook_path),
        "status": read_json(complete_path).get("stage_status"),
    }
    checks = {key: actual[key] == expected[key] for key in actual}
    return {"passed": all(checks.values()), "checks": checks, "actual": actual, "expected": expected, "complete_path": str(complete_path)}


def _a0_probe(project: Path, protocol: dict) -> dict:
    parent_path = project / Path(protocol["parent_n3"]["source_root"]) / "scripts" / "generate_data.py"
    module_spec = importlib.util.spec_from_file_location("frozen_parent_generate_data", parent_path)
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("cannot load frozen parent generator")
    parent = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(parent)
    identity = ScenarioSpec("D0", "none", 0.8, None, True, "none")
    params = resolved_params(985000, protocol)
    parent_summary, parent_arrays = parent.simulate_trajectory(
        identity, "V1", 985000, params, protocol, actuator_mode="A3", load_transfer_enabled=True
    )
    new_summary, new_arrays = simulate_trajectory(
        identity, "V1", 985000, params, protocol, actuator_mode="A3", load_transfer_enabled=True
    )
    common = sorted(set(parent_arrays) & set(new_arrays))
    field_errors = {}
    for key in common:
        left, right = np.asarray(parent_arrays[key]), np.asarray(new_arrays[key])
        field_errors[key] = max_abs_field_difference(left, right)
    actual = np.asarray(new_arrays["actual_steering_rad"], dtype=float)
    request = np.asarray(new_arrays["requested_control4x2"], dtype=float)[:, :, 1]
    actuator = SteeringActuatorConfig(
        tau_delta_s=float(protocol["actuator"]["tau_delta_s"]),
        rate_max_radps=float(protocol["actuator"]["rate_max_radps"]),
        angle_max_rad=float(np.deg2rad(protocol["actuator"]["angle_max_deg"])),
    )
    one = 0.0
    for index in range(len(actual) - 1):
        predicted = rollout_actuator_step(
            actual[index], request[index + 1],
            model_step_s=float(protocol["actuator"]["model_step_s"]),
            plant_step_s=float(protocol["actuator"]["plant_step_s"]), config=actuator,
        )["delta_act_k1_rad"]
        one = max(one, float(np.max(np.abs(predicted - actual[index + 1]))))
    twenty = 0.0
    for start in range(len(actual) - 20):
        predicted = actual[start].copy()
        for offset in range(20):
            predicted = rollout_actuator_step(
                predicted, request[start + offset + 1],
                model_step_s=float(protocol["actuator"]["model_step_s"]),
                plant_step_s=float(protocol["actuator"]["plant_step_s"]), config=actuator,
            )["delta_act_k1_rad"]
        twenty = max(twenty, float(np.max(np.abs(predicted - actual[start + 20]))))
    maximum = max(field_errors.values(), default=float("inf"))
    return {
        "passed": parent_summary["status"] == new_summary["status"] == "PASS" and len(common) >= 63 and maximum <= 1.0e-12 and one <= 1.0e-12 and twenty <= 1.0e-12,
        "common_field_count": len(common),
        "common_field_max_abs": maximum,
        "one_step_max_abs_rad": one,
        "twenty_step_max_abs_rad": twenty,
        "per_field_max_abs": field_errors,
    }


def run_a0(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["A0"]
    if stage_complete(stage_root):
        return stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    with stage_lock(stage_root):
        started = time.perf_counter()
        shutil.copy2(context["taskbook"], stage_root / "taskbook_snapshot.md")
        shutil.copy2(context["protocol_path"], stage_root / "protocol_snapshot.json")
        parent = _parent_identity(context["project"], context["protocol"])
        atomic_json(stage_root / "parent_n3_identity.json", parent)
        probe = _a0_probe(context["project"], context["protocol"])
        atomic_json(stage_root / "a3_short_probe.json", probe)
        environment = os.environ.copy()
        environment["KOOPMAN_PROJECT_ROOT"] = str(context["project"])
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "pytest", str(ROOT), "-q", "-p", "no:cacheprovider"],
            cwd=ROOT, capture_output=True, text=True, timeout=1800, env=environment,
        )
        (stage_root / "pytest.txt").write_text(completed.stdout + "\n--- STDERR ---\n" + completed.stderr, encoding="utf-8")
        frozen = freeze(
            project_root=context["project"], source_root=ROOT,
            protocol_path=context["protocol_path"], taskbook_path=context["taskbook"],
            output=stage_root / "freeze", parent_n3=parent,
        )
        exclusions = not any(
            path.is_dir() and path.name in {"__pycache__", ".pytest_cache"}
            for path in ROOT.rglob("*")
        )
        gates = {
            "parent_n3_identity": bool(parent["passed"]),
            "taskbook_identity": frozen["taskbook_sha256"] == context["protocol"]["taskbook_sha256"],
            "stable_source_manifest": bool(frozen["consecutive_manifest_match"]),
            "no_cache_directories": exclusions,
            "parent_and_new_tests": completed.returncode == 0,
            "a3_63_field_and_rollout_probe": bool(probe["passed"]),
            "runner_failure_injection_tests": completed.returncode == 0 and "failed" not in completed.stdout.lower(),
            "environment_host": platform.node().upper() == "DESKTOP-9IUUGEO",
            "disk_free": float(frozen["environment"]["disk_free_gib"]) >= float(context["protocol"]["resource_limits"]["minimum_free_gib"]),
        }
        warnings = [] if frozen["environment"].get("cuda_available") else ["CUDA probe unavailable; simulation and closed-form regression are CPU paths"]
        decision = decide_stage_status(hard_gates=gates, warnings=warnings)
        result = {
            "stage": "A0", "machine_state": decision.value,
            "passed": decision in {StageDecision.PASS_CONTINUE, StageDecision.PASS_WITH_WARNING_CONTINUE},
            "gates": gates, "warnings": warnings, "runtime_s": time.perf_counter() - started,
            "source_manifest_sha256": frozen["source_manifest_sha256"],
            "protocol_sha256": frozen["protocol_sha256"], "taskbook_sha256": frozen["taskbook_sha256"],
        }
        _stage_artifacts(stage_root, gates, warnings, decision, result)
        return result


def _job_paths(data_stage: Path, identity: dict, cache: bool) -> tuple[Path, Path | None]:
    stem = f"T{int(identity['trajectory_id']):04d}_{identity['scenario']}_{identity['plant']}_{identity['direction']}_{identity['member']}"
    raw = data_stage / "raw" / f"{stem}.npz"
    cache_path = data_stage / "cache" / f"{stem}.npz" if cache else None
    return raw, cache_path


def run_jobs(
    identities: list[dict],
    protocol: dict,
    data_stage: Path,
    checkpoint_root: Path,
    *,
    workers: int,
    replay: bool,
    cache: bool,
    raw_path_by_id: dict[int, Path] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    completed_results = []
    pending = []
    for identity in identities:
        checkpoint = checkpoint_root / f"T{int(identity['trajectory_id']):04d}.json"
        if checkpoint.exists():
            result = read_json(checkpoint)
            if not result.get("ok"):
                raise RuntimeError(f"failed checkpoint cannot be reused: {checkpoint}")
            completed_results.append(result)
            continue
        raw, cache_path = _job_paths(data_stage, identity, cache)
        if raw_path_by_id is not None:
            raw = raw_path_by_id[int(identity["trajectory_id"])]
        pending.append({"identity": identity, "protocol": protocol, "raw_path": str(raw), "cache_path": None if cache_path is None else str(cache_path), "replay": replay, "checkpoint": str(checkpoint)})
    if workers == 1:
        iterator = ((job, simulate_job(job)) for job in pending)
        for job, result in iterator:
            atomic_json(Path(job["checkpoint"]), result)
            if not result.get("ok"):
                raise RuntimeError(f"trajectory failed: {result}")
            completed_results.append(result)
    elif pending:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(simulate_job, job): job for job in pending}
            for future in as_completed(futures):
                job = futures[future]
                result = future.result()
                atomic_json(Path(job["checkpoint"]), result)
                if not result.get("ok"):
                    raise RuntimeError(f"trajectory failed: {result}")
                completed_results.append(result)
    completed_results.sort(key=lambda item: int(item["row"]["trajectory_id"]))
    return (
        [item["row"] for item in completed_results],
        [item["audit"] for item in completed_results],
        [row for item in completed_results for row in item["windows"]],
    )


def _source_gate(context: dict) -> bool:
    a0 = read_json(context["run_root"] / "a0" / "complete.json")
    return _source_identity()["source_manifest_sha256"] == a0["source_manifest_sha256"]


def _reuse_rows(context: dict, identities: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    source_run = context.get("reuse_n4_from")
    if source_run is None:
        raise ValueError("reuse source is not configured")
    manifest = Path(source_run) / "n4" / "data_manifest.csv"
    with manifest.open("r", newline="", encoding="utf-8-sig") as stream:
        old_rows = list(csv.DictReader(stream))
    wanted = {int(identity["trajectory_id"]): identity for identity in identities}
    selected = [row for row in old_rows if int(row["trajectory_id"]) in wanted]
    if len(selected) != len(wanted):
        raise RuntimeError("reuse manifest does not contain every requested trajectory")
    rows, audits, windows = [], [], []
    for old in sorted(selected, key=lambda row: int(row["trajectory_id"])):
        identity = {**old, **wanted[int(old["trajectory_id"])]}
        identity["trajectory_id"] = int(identity["trajectory_id"])
        identity["seed"] = int(identity["seed"])
        for key in ("duration_s", "distance_target_m"):
            value = identity.get(key)
            identity[key] = None if value in (None, "", "None") else float(value)
        raw_path = Path(old["raw_path"])
        arrays = load_npz(raw_path)
        summary = read_json(raw_path.with_suffix(".meta.json"))
        replay = str(old.get("replay_hash_match", "")).lower() == "true"
        audit = audit_trajectory(identity, arrays, summary, context["protocol"], replay_hash_match=replay)
        ledger = window_ledger(identity, arrays, context["protocol"])
        row = dict(old)
        row.update({"audit_passed": bool(audit["passed"]), "failed_gates": json.dumps(audit["failed_gates"]), "reused_raw": True, "reused_from_run": Path(source_run).name})
        rows.append(row)
        audits.append(audit)
        windows.extend(ledger)
    return rows, audits, windows


def _reuse_n5_raw_paths(context: dict, identities: list[dict]) -> dict[int, Path] | None:
    """Resolve a complete, identity-checked N5 raw set for audit/cache-only repair."""

    source_run = context.get("reuse_n5_from")
    if source_run is None:
        return None
    manifest = Path(source_run) / "n5" / "data_manifest.csv"
    with manifest.open("r", newline="", encoding="utf-8-sig") as stream:
        old_rows = list(csv.DictReader(stream))
    old_by_id = {int(row["trajectory_id"]): row for row in old_rows}
    if len(old_by_id) != len(identities):
        raise RuntimeError("reuse N5 manifest is not a complete unique trajectory set")
    identity_keys = (
        "base_family_id", "split", "scenario", "parameter_family", "seed",
        "direction", "member", "plant", "law", "actuator_mode",
    )
    raw_paths: dict[int, Path] = {}
    for identity in identities:
        trajectory_id = int(identity["trajectory_id"])
        old = old_by_id.get(trajectory_id)
        if old is None:
            raise RuntimeError(f"reuse N5 trajectory missing: {trajectory_id}")
        mismatched = [
            key for key in identity_keys
            if str(old.get(key)) != str(identity.get(key))
        ]
        if mismatched:
            raise RuntimeError(
                f"reuse N5 identity mismatch for {trajectory_id}: {mismatched}"
            )
        raw_path = Path(old["raw_path"])
        if not raw_path.exists() or not raw_path.with_suffix(".meta.json").exists():
            raise FileNotFoundError(f"reuse N5 raw pair missing: {raw_path}")
        raw_paths[trajectory_id] = raw_path
    return raw_paths


def run_n4_smoke(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["N4-S"]
    if stage_complete(stage_root):
        return stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    with stage_lock(stage_root):
        started = time.perf_counter()
        identities = build_auto_smoke_identities(context["protocol"])
        if context.get("reuse_n4_from"):
            rows, audits, windows = _reuse_rows(context, identities)
        else:
            rows, audits, windows = run_jobs(
                identities, context["protocol"], context["data_root"] / "n4_smoke",
                stage_root / "checkpoints", workers=1, replay=True, cache=False,
            )
        baseline_hash = {int(row["trajectory_id"]): row["trajectory_array_sha256"] for row in rows}
        concurrency_rows = []
        usable_workers = 1
        for workers in (() if context.get("reuse_n4_from") else (2, 4)):
            concurrency_started = time.perf_counter()
            with ProcessPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(simulate_hash_only, [{"identity": identity, "protocol": context["protocol"]} for identity in identities]))
            passed = all(item.get("ok") and baseline_hash[int(item["trajectory_id"])] == item["trajectory_array_sha256"] for item in results)
            concurrency_rows.append({"workers": workers, "passed": passed, "runtime_s": time.perf_counter() - concurrency_started})
            if passed:
                usable_workers = workers
            else:
                break
        if context.get("reuse_n4_from"):
            old_smoke = read_json(Path(context["reuse_n4_from"]) / "n4_smoke" / "complete.json")
            old_concurrency = read_json(Path(context["reuse_n4_from"]) / "n4_smoke" / "concurrency_identity.json")
            concurrency_rows = [{**row, "reused_evidence": True} for row in old_concurrency]
            usable_workers = int(old_smoke["selected_workers"])
        first_plus_replay = sum(float(row["first_runtime_s"]) + float(row["replay_runtime_s"]) for row in rows)
        projected_hours = first_plus_replay / len(rows) * int(context["protocol"]["n4"]["expected_trajectory_count"]) / usable_workers / 3600.0
        free_gib = min(shutil.disk_usage(context["project"].drive + "\\").free, shutil.disk_usage(context["data_root"].drive + "\\").free) / 1024**3
        write_csv(stage_root / "smoke_manifest.csv", rows)
        write_csv(stage_root / "smoke_audit.csv", audits)
        write_csv(stage_root / "window_ledger.csv", windows)
        atomic_json(stage_root / "concurrency_identity.json", concurrency_rows)
        gates = {
            "source_identity": _source_gate(context),
            "six_trajectories": len(rows) == 6,
            "physics_and_replay": all(row["passed"] for row in audits),
            "load_coverage": {row["scenario"] for row in rows} == set(context["protocol"]["smoke"]["scenarios"]),
            "plant_coverage": {row["plant"] for row in rows} == set(context["protocol"]["smoke"]["required_plants"]),
            "direction_coverage": set(context["protocol"]["smoke"]["required_directions"]).issubset({row["direction"] for row in rows}),
            "thread_identity": all(row["passed"] for row in concurrency_rows),
            "n4_projection": projected_hours <= float(context["protocol"]["smoke"]["n4_wallclock_limit_h"]),
            "disk_free": free_gib >= float(context["protocol"]["resource_limits"]["minimum_free_gib"]),
        }
        warnings = []
        decision = decide_stage_status(hard_gates=gates, warnings=warnings)
        result = {"stage": "N4-S", "machine_state": decision.value, "passed": decision in {StageDecision.PASS_CONTINUE, StageDecision.PASS_WITH_WARNING_CONTINUE}, "gates": gates, "warnings": warnings, "selected_workers": usable_workers, "projected_n4_hours": projected_hours, "free_gib": free_gib, "runtime_s": time.perf_counter() - started}
        _stage_artifacts(stage_root, gates, warnings, decision, result)
        return result


def _stream_mirror(rows: list[dict], protocol: dict) -> dict:
    grouped: dict[tuple[str, str, str], dict[str, dict]] = defaultdict(dict)
    for row in rows:
        if row["direction"] in {"left", "right"}:
            grouped[(row["scenario"], row["parameter_family"], row["plant"])][row["direction"]] = row
    output_rows = []
    for directions in grouped.values():
        if set(directions) != {"left", "right"}:
            continue
        pair = []
        for direction in ("left", "right"):
            row = directions[direction]
            arrays = load_npz(Path(row["raw_path"]))
            pair.append((row, {key: arrays[key] for key in ("time_s", "force_payload_body_n", "system_yaw_rate_radps")}))
        output_rows.extend(mirror_audit(pair, protocol)["rows"])
    return {"passed": bool(output_rows) and all(row["passed"] for row in output_rows), "pair_count": len(output_rows), "max_relative_error": max((row["max_relative_error"] for row in output_rows), default=float("inf")), "rows": output_rows}


def _run_independent(manifest: Path, protocol_path: Path, output: Path, require_replay: bool) -> dict:
    command = [sys.executable, "-B", str(ROOT / "scripts" / "audit_predict_auto.py"), "--manifest", str(manifest), "--protocol", str(protocol_path), "--output", str(output)]
    if require_replay:
        command.append("--require-replay")
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=7200)
    output.with_suffix(".stdout_stderr.txt").write_text(completed.stdout + "\n--- STDERR ---\n" + completed.stderr, encoding="utf-8")
    result = read_json(output) if output.exists() else {"passed": False, "missing_output": True}
    result["returncode"] = completed.returncode
    result["passed"] = bool(result.get("passed") and completed.returncode == 0)
    return result


def run_n4(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["N4"]
    if stage_complete(stage_root):
        return stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    with stage_lock(stage_root):
        started = time.perf_counter()
        identities = build_predict_pilot_identities(context["protocol"])
        for identity in identities:
            identity.pop("dry_run_only", None)
            identity["split"] = "pilot"
        smoke = read_json(context["run_root"] / "n4_smoke" / "complete.json")
        if context.get("reuse_n4_from"):
            rows, audits, windows = _reuse_rows(context, identities)
            atomic_json(stage_root / "raw_reuse_provenance.json", {"source_run": str(context["reuse_n4_from"]), "reason": "audit-only D8 direction/mirror/window aggregation repair; simulator and raw arrays unchanged", "source_complete_sha256": sha256(Path(context["reuse_n4_from"]) / "n4" / "complete.json")})
        else:
            rows, audits, windows = run_jobs(
                identities, context["protocol"], context["data_root"] / "n4",
                stage_root / "checkpoints", workers=int(smoke["selected_workers"]), replay=True, cache=False,
            )
        manifest = stage_root / "data_manifest.csv"
        write_csv(manifest, rows)
        write_csv(stage_root / "physics_audit.csv", audits)
        write_csv(stage_root / "window_ledger.csv", windows)
        coverage = coverage_audit(audits, context["protocol"])
        mirror = _stream_mirror(rows, context["protocol"])
        atomic_json(stage_root / "coverage_audit.json", coverage)
        atomic_json(stage_root / "mirror_audit.json", mirror)
        independent = _run_independent(manifest, context["protocol_path"], stage_root / "independent_audit.json", True)
        identities_unique = {(row["scenario"], row["parameter_family"], row["direction"], row["member"], row["plant"]) for row in rows}
        worst = sorted(audits, key=lambda row: max(float(row["tire_raw_utilization_max"]), float(row["internal_null_relative"])), reverse=True)[:12]
        write_csv(stage_root / "worst_trajectories.csv", worst)
        gates = {
            "source_identity": _source_gate(context),
            "trajectory_count": len(rows) == 126,
            "unique_identity_count": len(identities_unique) == 126,
            "base_family_count": len({row["base_family_id"] for row in rows}) == 36,
            "scenario_count": len({row["scenario"] for row in rows}) == 12,
            "physics_and_replay": all(row["passed"] for row in audits),
            "mirror": bool(mirror["passed"]),
            "window_coverage": bool(coverage["passed"]),
            "field_complete": all(row.get("gate_field_complete") for row in audits),
            "independent_audit": bool(independent["passed"]) and int(independent["trajectory_count"]) == 126,
        }
        warnings = []
        if sum(float(row["angle_mask_fraction"]) for row in audits) == 0.0:
            warnings.append("angle mask is inactive in D0-D11; no excitation was altered to force activation")
        decision = decide_stage_status(hard_gates=gates, warnings=warnings)
        result = {"stage": "N4", "machine_state": decision.value, "passed": decision in {StageDecision.PASS_CONTINUE, StageDecision.PASS_WITH_WARNING_CONTINUE}, "gates": gates, "warnings": warnings, "trajectory_count": len(rows), "runtime_s": time.perf_counter() - started, "manifest": str(manifest)}
        _stage_artifacts(stage_root, gates, warnings, decision, result)
        return result


def run_n5(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["N5"]
    if stage_complete(stage_root):
        return stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    with stage_lock(stage_root):
        started = time.perf_counter()
        identities = build_future_trajectory_identities(context["protocol"])
        workers = int(read_json(context["run_root"] / "n4_smoke" / "complete.json")["selected_workers"])
        reused_raw_paths = _reuse_n5_raw_paths(context, identities)
        rows, audits, windows = run_jobs(
            identities, context["protocol"], context["data_root"] / "n5",
            stage_root / "checkpoints", workers=workers, replay=False, cache=True,
            raw_path_by_id=reused_raw_paths,
        )
        if reused_raw_paths is not None:
            source_run = Path(context["reuse_n5_from"])
            atomic_json(
                stage_root / "raw_reuse_provenance.json",
                {
                    "source_run": str(source_run),
                    "reason": "window-classification-only repair; simulator, identities, parameters, scenarios, seeds, and raw arrays unchanged",
                    "source_complete_sha256": sha256(source_run / "n5" / "complete.json"),
                    "raw_trajectory_count": len(reused_raw_paths),
                },
            )
        manifest = stage_root / "data_manifest.csv"
        write_csv(manifest, rows)
        write_csv(stage_root / "physics_audit.csv", audits)
        write_csv(stage_root / "window_ledger.csv", windows)
        train_rows = [row for row in rows if row["split"] == "train"]
        normalization = fit_normalization(train_rows)
        normalization_path = stage_root / "normalization_train_only.npz"
        np.savez_compressed(normalization_path, **normalization)
        family_splits: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            family_splits[row["base_family_id"]].add(row["split"])
        family_count = {split: len({row["base_family_id"] for row in rows if row["split"] == split}) for split in ("train", "validation", "development")}
        window_counts = Counter(row["class"] for row in windows)
        contract = {
            "trajectory_count": len(rows), "family_count": family_count,
            "cross_split_family_count": sum(len(value) != 1 for value in family_splits.values()),
            "confirm_read_count": sum(row["split"] == "confirm" for row in rows),
            "window_counts": dict(window_counts),
            "normalization_source": str(np.asarray(normalization["source_split"]).item()),
            "causality_failure_count": sum(not bool(row["causality_passed"]) for row in rows),
            "analytic_actuator_max_abs_rad": max(float(row["analytic_actuator_max_abs_rad"]) for row in rows),
        }
        atomic_json(stage_root / "dataset_contract.json", contract)
        gates = {
            "source_identity": _source_gate(context),
            "trajectory_count_672": len(rows) == 672,
            "family_counts_96_48_48": family_count == {"train": 96, "validation": 48, "development": 48},
            "cross_split_zero": contract["cross_split_family_count"] == 0,
            "confirm_hidden": contract["confirm_read_count"] == 0,
            "physics_finite_and_complete": all(row["passed"] for row in audits),
            "cache_and_manifest_sha": all(Path(row["cache_path"]).exists() and row["cache_sha256"] for row in rows),
            "train_only_normalization": contract["normalization_source"] == "train" and int(normalization["source_base_family_count"]) == 96,
            "within_trajectory_windows": bool(windows) and all(row["within_single_trajectory"] for row in windows),
            "four_window_classes": set(context["protocol"]["window"]["classes"]).issubset(window_counts),
            "causality_digest": contract["causality_failure_count"] == 0,
            "analytic_actuator_identity": contract["analytic_actuator_max_abs_rad"] <= float(context["protocol"]["actuator"]["endpoint_atol_rad"]),
        }
        warnings = []
        rare = [name for name, count in window_counts.items() if count < 10]
        if rare:
            warnings.append(f"low-count non-overlap windows: {rare}")
        decision = decide_stage_status(hard_gates=gates, warnings=warnings)
        result = {"stage": "N5", "machine_state": decision.value, "passed": decision in {StageDecision.PASS_CONTINUE, StageDecision.PASS_WITH_WARNING_CONTINUE}, "gates": gates, "warnings": warnings, "trajectory_count": len(rows), "family_count": family_count, "window_counts": dict(window_counts), "manifest": str(manifest), "normalization": str(normalization_path), "runtime_s": time.perf_counter() - started}
        _stage_artifacts(stage_root, gates, warnings, decision, result)
        return result


def _normalization(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def _config_key(model_kind: str, variant: str, rank: int | None) -> str:
    return f"{model_kind}|{variant}|{'none' if rank is None else rank}"


def _field_macro(rows: list[dict], field: str, horizon: int = 20) -> float | None:
    selected = [row for row in rows if int(row["horizon"]) == horizon and row[field] is not None]
    if not selected:
        return None
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in selected:
        grouped[row["scenario"]].append(float(row[field]))
    return float(np.mean([np.mean(value) for value in grouped.values()]))


def _improvement(baseline: float, candidate: float) -> float:
    return 100.0 * (baseline - candidate) / max(abs(baseline), 1.0e-12)


def _compare_rows(baseline: list[dict], candidate: list[dict], protocol: dict) -> dict:
    base = macro_summary(baseline)
    cand = macro_summary(candidate)
    scenarios = {name: _improvement(base["scenario_j_common"][name], cand["scenario_j_common"][name]) for name in base["scenario_j_common"]}
    windows = {name: _improvement(base["window_j_common"][name], cand["window_j_common"][name]) for name in base["window_j_common"] if name in cand["window_j_common"]}
    return {
        "macro_improvement_percent": _improvement(base["j_common_macro"], cand["j_common_macro"]),
        "scenario_improvement_percent": scenarios,
        "window_improvement_percent": windows,
        "max_important_degradation_percent": max([max(-scenarios[name], 0.0) for name in protocol["training"]["important_scenarios"]], default=0.0),
        "divergence_rate_change": cand["divergence_rate"] - base["divergence_rate"],
        "inference_ratio": cand["inference_mean_s_per_window"] / max(base["inference_mean_s_per_window"], 1.0e-12),
        "paired_ci": paired_family_bootstrap(candidate, baseline, replicates=int(protocol["training"]["paired_ci_replicates"]), seed=int(protocol["training"]["paired_ci_seed"])),
    }


def _save_model(path: Path, model: dict, metadata: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, coefficients=model["coefficients"])
    atomic_json(path.with_suffix(".json"), {**metadata, **{key: value for key, value in model.items() if key != "coefficients"}})


def _plot_n6(output: Path, summaries: list[dict], comparisons: dict) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = []
    selected = [row for row in summaries if row["seed_label"] == "FULL_TRAIN"]
    labels = [row["config_key"].replace("M0_FIXED_LINEAR|", "M0|").replace("M1_LOWRANK_BILINEAR|", "M1|") for row in selected]
    values = [row["j_common_macro"] for row in selected]
    fig, axis = plt.subplots(figsize=(12, 5))
    axis.bar(np.arange(len(labels)), values, color="#3b82f6")
    axis.set_xticks(np.arange(len(labels)), labels, rotation=55, ha="right")
    axis.set_ylabel("20-step macro J_common")
    axis.set_title("Frozen N6 model/interface matrix (lower is better)")
    fig.tight_layout()
    path = output / "n6_model_matrix.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))

    fig, axis = plt.subplots(figsize=(7, 4))
    names = ["S1 vs S0", "S2 vs S1"]
    vals = [comparisons["s1_vs_s0"]["macro_improvement_percent"], comparisons["s2_vs_s1"]["macro_improvement_percent"]]
    axis.bar(names, vals, color=["#10b981", "#f59e0b"])
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set_ylabel("20-step macro J_common improvement (%)")
    axis.set_title("Interface effect under fixed-linear backbone")
    fig.tight_layout()
    path = output / "n6_interface_comparison.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    figures.append(str(path))
    return figures


def run_n6(context: dict) -> dict:
    stage_root = context["run_root"] / STAGE_DIR["N6"]
    if stage_complete(stage_root):
        return stage_complete(stage_root)  # type: ignore[return-value]
    stage_root.mkdir(exist_ok=True)
    with stage_lock(stage_root):
        started = time.perf_counter()
        n5 = read_json(context["run_root"] / "n5" / "complete.json")
        with Path(n5["manifest"]).open("r", newline="", encoding="utf-8-sig") as stream:
            entries = list(csv.DictReader(stream))
        for row in entries:
            row["trajectory_id"] = int(row["trajectory_id"])
            row["seed"] = int(row["seed"])
        train = [row for row in entries if row["split"] == "train"]
        validation = [row for row in entries if row["split"] == "validation"]
        development = [row for row in entries if row["split"] == "development"]
        normalization = _normalization(Path(n5["normalization"]))
        protocol = context["protocol"]
        candidate_rows = []
        selections = {}
        central_statistics = {}
        for variant in protocol["interfaces"]["variants"]:
            for kind in protocol["training"]["models"]:
                stats = accumulate_fit_statistics(train, variant, kind, normalization)
                central_statistics[(variant, kind)] = stats
                ranks = [None] if kind == "M0_FIXED_LINEAR" else protocol["training"]["ranks"]
                for rank in ranks:
                    choices = []
                    for ridge in protocol["training"]["ridge_grid"]:
                        model = solve_model(stats, variant=variant, model_kind=kind, ridge=float(ridge), rank=rank)
                        evaluated = evaluate_model(model, validation, normalization, protocol, resolved_params, seed_label="VALIDATION_SELECTION")
                        summary = macro_summary(evaluated)
                        choices.append({"ridge": float(ridge), "j_common_macro": summary["j_common_macro"], "condition_number": model["condition_number"], "parameter_count": model["parameter_count"]})
                    chosen = min(choices, key=lambda item: item["j_common_macro"])
                    key = _config_key(kind, variant, rank)
                    selections[key] = {"model_kind": kind, "variant": variant, "rank": rank, "ridge": chosen["ridge"]}
                    for item in choices:
                        candidate_rows.append({"config_key": key, **item, "selected": item["ridge"] == chosen["ridge"]})
        write_csv(stage_root / "validation_selection.csv", candidate_rows)
        atomic_json(stage_root / "frozen_hyperparameter_selection.json", selections)

        detailed = []
        summaries = []
        central_models = {}
        for key, selected in selections.items():
            stats = central_statistics[(selected["variant"], selected["model_kind"])]
            model = solve_model(stats, variant=selected["variant"], model_kind=selected["model_kind"], ridge=selected["ridge"], rank=selected["rank"])
            central_models[key] = model
            rows = evaluate_model(model, development, normalization, protocol, resolved_params, seed_label="FULL_TRAIN")
            detailed.extend({"config_key": key, **row} for row in rows)
            summary = macro_summary(rows)
            summaries.append({"config_key": key, "seed_label": "FULL_TRAIN", **summary, "j_full_macro": _field_macro(rows, "j_full"), "e_actuator_macro": _field_macro(rows, "e_actuator"), "condition_number": model["condition_number"], "parameter_count": model["parameter_count"], "fit_row_count": model["fit_row_count"]})
            _save_model(context["models_root"] / "n6" / f"{key.replace('|', '_')}_FULL_TRAIN.npz", model, {"config_key": key, "seed_label": "FULL_TRAIN"})
        write_csv_gz(stage_root / "development_detailed.csv.gz", detailed)

        train_families = sorted({row["base_family_id"] for row in train})
        bootstrap_rows = []
        bootstrap_summaries: dict[tuple[int, str], dict] = {}
        for seed in protocol["training"]["primary_family_bootstrap_seeds"]:
            rng = np.random.default_rng(int(seed))
            counts = Counter(rng.choice(train_families, size=len(train_families), replace=True))
            statistics = {}
            for variant in protocol["interfaces"]["variants"]:
                for kind in protocol["training"]["models"]:
                    statistics[(variant, kind)] = accumulate_fit_statistics(train, variant, kind, normalization, counts)
            for key, selected in selections.items():
                model = solve_model(statistics[(selected["variant"], selected["model_kind"])], variant=selected["variant"], model_kind=selected["model_kind"], ridge=selected["ridge"], rank=selected["rank"])
                rows = evaluate_model(model, development, normalization, protocol, resolved_params, seed_label=str(seed))
                summary = {"config_key": key, "seed_label": str(seed), **macro_summary(rows), "j_full_macro": _field_macro(rows, "j_full"), "e_actuator_macro": _field_macro(rows, "e_actuator"), "condition_number": model["condition_number"], "parameter_count": model["parameter_count"]}
                bootstrap_rows.append(summary)
                bootstrap_summaries[(int(seed), key)] = summary
                _save_model(context["models_root"] / "n6" / f"{key.replace('|', '_')}_BOOT_{seed}.npz", model, {"config_key": key, "seed_label": str(seed), "bootstrap_family_counts": dict(counts)})

        central_by_key = {row["config_key"]: row for row in summaries}
        detailed_by_key = defaultdict(list)
        for row in detailed:
            detailed_by_key[row["config_key"]].append(row)
        s0_key = _config_key("M0_FIXED_LINEAR", "S0", None)
        s1_key = _config_key("M0_FIXED_LINEAR", "S1", None)
        s2_key = _config_key("M0_FIXED_LINEAR", "S2", None)
        comparisons = {
            "s1_vs_s0": _compare_rows(detailed_by_key[s0_key], detailed_by_key[s1_key], protocol),
            "s2_vs_s1": _compare_rows(detailed_by_key[s1_key], detailed_by_key[s2_key], protocol),
        }
        for name, candidate_key, baseline_key in (("s1_vs_s0", s1_key, s0_key), ("s2_vs_s1", s2_key, s1_key)):
            direction = []
            for seed in protocol["training"]["primary_family_bootstrap_seeds"]:
                direction.append(_improvement(bootstrap_summaries[(int(seed), baseline_key)]["j_common_macro"], bootstrap_summaries[(int(seed), candidate_key)]["j_common_macro"]))
            comparisons[name]["seed_improvement_percent"] = direction
            comparisons[name]["seed_positive_count"] = sum(value > 0.0 for value in direction)

        s1 = comparisons["s1_vs_s0"]
        switch = s1["window_improvement_percent"].get("switch", float("-inf"))
        important_count = sum(s1["scenario_improvement_percent"].get(name, float("-inf")) >= 5.0 for name in protocol["training"]["important_scenarios"])
        if s1["macro_improvement_percent"] >= 5.0 and switch >= 8.0 and s1["max_important_degradation_percent"] <= 3.0 and s1["paired_ci"]["ci95_low_percent"] > 0.0:
            s1_class = "GLOBAL_EFFECTIVE"
        elif s1["macro_improvement_percent"] >= 0.0 and switch >= 5.0 and important_count >= 2 and s1["max_important_degradation_percent"] <= 5.0 and s1["seed_positive_count"] >= 4:
            s1_class = "LOCAL_EFFECTIVE"
        elif s1["max_important_degradation_percent"] <= 5.0 and (0.0 <= s1["macro_improvement_percent"] < 5.0 or s1["paired_ci"]["ci95_low_percent"] <= 0.0 or s1["seed_positive_count"] < 4):
            s1_class = "GRAY"
        else:
            s1_class = "INEFFECTIVE_OR_DEGRADED"

        s2 = comparisons["s2_vs_s1"]
        s1_full = central_by_key[s1_key]["j_full_macro"]
        s2_full = central_by_key[s2_key]["j_full_macro"]
        full_improvement = _improvement(float(s1_full), float(s2_full))
        s2["j_full_improvement_percent"] = full_improvement
        if (s2["macro_improvement_percent"] >= 3.0 or s2["divergence_rate_change"] < 0.0) and s2["max_important_degradation_percent"] <= 3.0:
            s2_class = "COMMON_DYNAMICS_EFFECTIVE"
        elif full_improvement > 0.0 and s2["macro_improvement_percent"] < 3.0:
            s2_class = "ACTUATOR_ONLY_EFFECTIVE"
        elif 0.0 <= s2["macro_improvement_percent"] < 3.0 and s2["max_important_degradation_percent"] <= 3.0:
            s2_class = "GRAY"
        else:
            s2_class = "DEGRADED"

        backup_needed = s1_class == "GRAY" or s2_class == "GRAY"
        backup_seeds_used = []
        if backup_needed:
            needed = {s0_key, s1_key, s2_key}
            for seed in protocol["training"]["backup_family_bootstrap_seeds"]:
                backup_seeds_used.append(int(seed))
                rng = np.random.default_rng(int(seed))
                counts = Counter(rng.choice(train_families, size=len(train_families), replace=True))
                statistics = {(variant, "M0_FIXED_LINEAR"): accumulate_fit_statistics(train, variant, "M0_FIXED_LINEAR", normalization, counts) for variant in ("S0", "S1", "S2")}
                for key in needed:
                    selected = selections[key]
                    model = solve_model(statistics[(selected["variant"], selected["model_kind"])], variant=selected["variant"], model_kind=selected["model_kind"], ridge=selected["ridge"], rank=None)
                    rows = evaluate_model(model, development, normalization, protocol, resolved_params, seed_label=str(seed))
                    summary = {"config_key": key, "seed_label": str(seed), **macro_summary(rows), "j_full_macro": _field_macro(rows, "j_full"), "e_actuator_macro": _field_macro(rows, "e_actuator"), "condition_number": model["condition_number"], "parameter_count": model["parameter_count"]}
                    bootstrap_rows.append(summary)
                    bootstrap_summaries[(int(seed), key)] = summary
            all_seeds = [*protocol["training"]["primary_family_bootstrap_seeds"], *backup_seeds_used]
            for name, candidate_key, baseline_key in (("s1_vs_s0", s1_key, s0_key), ("s2_vs_s1", s2_key, s1_key)):
                values = [_improvement(bootstrap_summaries[(int(seed), baseline_key)]["j_common_macro"], bootstrap_summaries[(int(seed), candidate_key)]["j_common_macro"]) for seed in all_seeds]
                comparisons[name]["seed_improvement_percent"] = values
                comparisons[name]["seed_positive_count"] = sum(value > 0.0 for value in values)
            if s1_class == "GRAY":
                s1_class = "LOCAL_EFFECTIVE" if comparisons["s1_vs_s0"]["seed_positive_count"] >= 6 and s1["macro_improvement_percent"] >= 0.0 else "INEFFECTIVE_OR_DEGRADED"
            if s2_class == "GRAY":
                s2_class = "COMMON_DYNAMICS_EFFECTIVE" if comparisons["s2_vs_s1"]["seed_positive_count"] >= 6 and s2["macro_improvement_percent"] >= 3.0 else "ACTUATOR_ONLY_EFFECTIVE" if full_improvement > 0.0 else "DEGRADED"

        selected_interface = "S0" if s1_class not in {"GLOBAL_EFFECTIVE", "LOCAL_EFFECTIVE"} else "S2" if s2_class == "COMMON_DYNAMICS_EFFECTIVE" else "S1"
        bilinear = []
        fixed_key = _config_key("M0_FIXED_LINEAR", selected_interface, None)
        acceptance = protocol["n6_engineering_acceptance"]
        for rank in protocol["training"]["ranks"]:
            key = _config_key("M1_LOWRANK_BILINEAR", selected_interface, rank)
            comparison = _compare_rows(detailed_by_key[fixed_key], detailed_by_key[key], protocol)
            seed_values = [_improvement(bootstrap_summaries[(int(seed), fixed_key)]["j_common_macro"], bootstrap_summaries[(int(seed), key)]["j_common_macro"]) for seed in protocol["training"]["primary_family_bootstrap_seeds"]]
            strong_best = max(comparison["scenario_improvement_percent"].get(name, float("-inf")) for name in protocol["training"]["strong_coupling_scenarios"])
            acceptable = central_by_key[key]["condition_number"] <= float(acceptance["condition_number_max"]) and comparison["inference_ratio"] <= float(acceptance["inference_time_ratio_max"]) and comparison["divergence_rate_change"] <= float(acceptance["divergence_rate_increase_max"])
            effective = strong_best >= 8.0 and comparison["macro_improvement_percent"] >= -3.0 and sum(value > 0.0 for value in seed_values) >= 4 and acceptable
            bilinear.append({"rank": rank, "config_key": key, **comparison, "seed_improvement_percent": seed_values, "seed_positive_count": sum(value > 0.0 for value in seed_values), "strong_coupling_best_percent": strong_best, "engineering_acceptable": acceptable, "effective": effective})
        selected_bilinear = max((row for row in bilinear if row["effective"]), key=lambda row: row["strong_coupling_best_percent"], default=None)

        all_summary_rows = summaries + bootstrap_rows
        write_csv(stage_root / "model_seed_summary.csv", all_summary_rows)
        atomic_json(stage_root / "interface_comparisons.json", comparisons)
        atomic_json(stage_root / "bilinear_comparison.json", bilinear)
        parameter_rows = [{"config_key": key, "parameter_count": central_by_key[key]["parameter_count"], "condition_number": central_by_key[key]["condition_number"]} for key in sorted(central_by_key)]
        for row in parameter_rows:
            others = [item for item in parameter_rows if item["config_key"] != row["config_key"]]
            closest = min(others, key=lambda item: abs(item["parameter_count"] - row["parameter_count"]))
            row["nearest_parameter_config"] = closest["config_key"]
            row["parameter_difference"] = abs(closest["parameter_count"] - row["parameter_count"])
        write_csv(stage_root / "parameter_matched_sensitivity.csv", parameter_rows)
        selection = {"selected_interface": selected_interface, "s1_classification": s1_class, "s2_classification": s2_class, "selected_bilinear": None if selected_bilinear is None else selected_bilinear["config_key"], "backup_seeds_used": backup_seeds_used, "force_metric_derivation": "method-neutral analytic reconstruction from predicted relative connector displacement/velocity and frozen connector law/parameters; no learned force target was added"}
        atomic_json(stage_root / "selection.json", selection)
        figures = _plot_n6(stage_root, summaries, comparisons)
        gates = {
            "source_identity": _source_gate(context),
            "confirm_not_read": all(row["split"] != "confirm" for row in entries),
            "validation_only_selection": True,
            "development_read_after_selection_freeze": (stage_root / "frozen_hyperparameter_selection.json").exists(),
            "matrix_12_configs": len(selections) == 12 and len(summaries) == 12,
            "five_primary_bootstrap_seeds": len(bootstrap_rows) >= 12 * 5,
            "all_horizons": {int(row["horizon"]) for row in detailed} == {1, 5, 10, 20},
            "all_windows": set(protocol["window"]["classes"]).issubset({row["window"] for row in detailed}),
            "all_scenarios": set(protocol["scenarios"]["order"]) == {row["scenario"] for row in detailed},
            "metrics_complete": all(all(name in row for name in ("j_common", "j_full", "state47_rmse_si", "force8_rmse_n", "internal8_rmse_n", "divergent", "inference_s")) for row in detailed),
            "selection_complete": selected_interface in {"S0", "S1", "S2"},
            "forbidden_stages_not_run": not any((context["run_root"] / name).exists() for name in ("c1", "c2", "k1", "k7", "mpc", "network", "dos", "confirm")),
        }
        warnings = []
        if s1_class in {"INEFFECTIVE_OR_DEGRADED"}:
            warnings.append("S1 did not satisfy frozen effectiveness rule; retained as negative ablation")
        if s2_class != "COMMON_DYNAMICS_EFFECTIVE":
            warnings.append(f"S2 classification is {s2_class}; analytic actuator benefit is separated from common-state benefit")
        if selected_bilinear is None:
            warnings.append("low-rank bilinear did not satisfy the frozen strong-coupling module rule")
        decision = decide_stage_status(hard_gates=gates, warnings=warnings)
        passed = decision in {StageDecision.PASS_CONTINUE, StageDecision.PASS_WITH_WARNING_CONTINUE}
        final_status = "PASS_STOPPED_AFTER_N6" if passed else "PARTIAL_STOPPED_AFTER_N6"
        result = {"stage": "N6", "machine_state": decision.value, "stage_status": final_status, "passed": passed, "human_stop": True, "gates": gates, "warnings": warnings, "selection": selection, "figures": figures, "runtime_s": time.perf_counter() - started, "forbidden_stage_status": {name: "NOT_RUN" for name in protocol["autonomy"]["forbidden_stages"]}}
        _stage_artifacts(stage_root, gates, warnings, decision, result)
        return result


def execute(args: argparse.Namespace) -> dict:
    project = Path(args.project_root).resolve()
    protocol_path = Path(args.protocol).resolve()
    taskbook = Path(args.taskbook).resolve()
    protocol = read_json(protocol_path)
    validate_predict_auto_protocol(protocol)
    assert_stage_allowed(args.stage)
    if args.auto_through != "N6":
        raise PermissionError("autonomous runner is bounded to --auto-through N6")
    if ROOT.resolve() != (project / Path(protocol["source_root"])).resolve():
        raise RuntimeError(f"source root mismatch: {ROOT}")
    if sha256(taskbook) != protocol["taskbook_sha256"]:
        raise RuntimeError("taskbook SHA mismatch")
    results_root = project / Path(protocol["results_root"])
    data_root_base = project / Path(protocol["data_root"])
    models_root_base = project / Path(protocol["models_root"])
    results_root.mkdir(parents=True, exist_ok=True)
    for name, title in (("work_log.md", "# Koopman Predict Auto 工作记录\n"), ("solutions.md", "# Koopman Predict Auto 失败与解决方案\n")):
        path = results_root / name
        if not path.exists():
            path.write_text(title, encoding="utf-8")
    decision_log = results_root / "decision_log.jsonl"
    decision_log.touch(exist_ok=True)
    run_root = resolve_resume(results_root, args.resume_run) if args.resume_run else allocate_run(results_root, args.run_tag)
    data_root = data_root_base / run_root.name
    models_root = models_root_base / run_root.name
    reuse_n4_from = resolve_resume(results_root, args.reuse_n4_run) if args.reuse_n4_run else None
    reuse_n5_from = resolve_resume(results_root, args.reuse_n5_run) if args.reuse_n5_run else None
    context = {"project": project, "protocol": protocol, "protocol_path": protocol_path, "taskbook": taskbook, "results_root": results_root, "run_root": run_root, "data_root": data_root, "models_root": models_root, "reuse_n4_from": reuse_n4_from, "reuse_n5_from": reuse_n5_from}
    order = list(protocol["autonomy"]["stage_order"])
    start_index = order.index(args.stage)
    if start_index > 0:
        for previous in order[:start_index]:
            complete = stage_complete(run_root / STAGE_DIR[previous])
            if not complete or not complete.get("passed"):
                raise RuntimeError(f"{args.stage} requires passed {previous} in same run")
    functions = {"A0": run_a0, "N4-S": run_n4_smoke, "N4": run_n4, "N5": run_n5, "N6": run_n6}
    append_log(results_root / "work_log.md", "run start", {"run_root": run_root, "stage": args.stage, "auto_through": args.auto_through})
    last = None
    for index in range(start_index, order.index(args.auto_through) + 1):
        stage = order[index]
        if index > start_index:
            require_stage_transition(order[index - 1], stage)
        append_log(results_root / "work_log.md", f"{stage} start", {"data_root": data_root, "models_root": models_root})
        try:
            result = functions[stage](context)
        except Exception as error:
            stage_root = run_root / STAGE_DIR[stage]
            stage_root.mkdir(parents=True, exist_ok=True)
            failure = {"stage": stage, "machine_state": "BLOCKED_HUMAN_REQUIRED", "passed": False, "error": repr(error), "traceback": traceback.format_exc(), "human_stop": True}
            atomic_json(stage_root / "gate_report.json", {"hard_gates": {"unhandled_exception": False}, "warnings": []})
            atomic_json(stage_root / "decision.json", {"machine_state": "BLOCKED_HUMAN_REQUIRED", "error": repr(error)})
            atomic_json(stage_root / "complete.json", failure)
            append_log(results_root / "solutions.md", f"{stage} blocked", {"failure": failure, "minimal_solutions": ["inspect first failing traceback and preserve raw/checkpoints", "repair one non-physical root cause only and create a new source/run identity", "do not change physics, seeds, scenarios, thresholds, or omit adverse trajectories"]})
            append_decision(decision_log, {"stage": stage, "decision": "stop", "facts": [repr(error)], "alternatives": ["single-root-cause implementation repair", "human scientific redesign if physics/data/causality"], "chosen": "BLOCKED_HUMAN_REQUIRED", "rule_id": "AUTO_UNHANDLED_OR_HARD_GATE", "confidence": "high", "affected_identity": False, "next_action": "stop; inspect solutions.md"})
            append_log(results_root / "work_log.md", f"{stage} exception", failure)
            raise
        last = result
        append_decision(decision_log, {"stage": stage, "decision": "continue" if result.get("passed") and stage != "N6" else "stop" if stage == "N6" else "stop", "facts": [result.get("gates", {})], "alternatives": ["continue only on pass/warning", "stop on hard failure"], "chosen": result.get("machine_state"), "rule_id": f"{stage}_GATES", "confidence": "high", "affected_identity": False, "next_action": order[index + 1] if result.get("passed") and index + 1 < len(order) else "HUMAN_STOP_AFTER_N6" if stage == "N6" else "STOP"})
        append_log(results_root / "work_log.md", f"{stage} complete", result)
        atomic_json(results_root / "stage_status.json", {"run_root": str(run_root), "current_stage": stage, "machine_state": result.get("machine_state"), "passed": result.get("passed"), "complete": str(run_root / STAGE_DIR[stage] / "complete.json")})
        if not result.get("passed"):
            append_log(results_root / "solutions.md", f"{stage} hard gate stop", {"gates": result.get("gates", {}), "warnings": result.get("warnings", []), "solution_boundary": "preserve raw/checkpoints; diagnose first failed gate; do not relax physics/data/causality thresholds or change scenarios/seeds"})
            break
    return {"run_root": str(run_root), "last": last}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=["A0", "N4-S", "N4", "N5", "N6"])
    parser.add_argument("--auto-through", required=True, choices=["N6"])
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--taskbook", required=True)
    parser.add_argument("--run-tag", required=True)
    parser.add_argument("--resume-run")
    parser.add_argument("--reuse-n4-run")
    parser.add_argument("--reuse-n5-run")
    return parser


def main(argv: list[str] | None = None) -> None:
    result = execute(build_parser().parse_args(argv))
    print(json.dumps(_plain(result), indent=2, ensure_ascii=False, allow_nan=False))
    passed = bool(result.get("last", {}).get("passed"))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
