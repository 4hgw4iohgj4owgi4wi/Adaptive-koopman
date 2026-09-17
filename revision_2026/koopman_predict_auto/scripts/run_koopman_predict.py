from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from actuator_rollout import rollout_actuator_horizon, rollout_actuator_step
from causal_schema import build_schema_variant
from contracts import (
    build_future_split_ledger,
    json_sha256,
    sha256,
    source_manifest,
    validate_predict_protocol,
    write_json,
)
from dataset import validate_base_family_split_contract
from freeze_predict import freeze
from scenarios import audit_predict_pilot_identities, build_predict_pilot_identities
from steering_actuator import SteeringActuatorConfig


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refuse to write empty CSV: {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _run_root(results_root: Path, run_tag: str) -> Path:
    runs = results_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for revision in range(1, 100):
        candidate = runs / f"{stamp}_N3_{run_tag}_R{revision:02d}"
        if not candidate.exists():
            candidate.mkdir()
            return candidate
    raise RuntimeError("cannot allocate unique N3 run directory")


def _append_work_log(results_root: Path, action: str, status: str, details: dict) -> None:
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with (results_root / "work_log.md").open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n## {stamp} — N3/{action}\n\n"
            "- 授权边界：仅 N3；N4/N5/N6/训练/正式126条数据均未授权。\n"
            f"- 主机：`{platform.node()}`。\n"
            f"- 命令：`{' '.join(sys.argv)}`。\n"
            f"- 状态：`{status}`。\n"
            f"- 证据：`{json.dumps(details, ensure_ascii=False, allow_nan=False, default=str)}`。\n"
            "- 下一步：人工核验；不得自动进入 N4。\n"
        )


def _append_solution(results_root: Path, repair_code: str, evidence: dict) -> None:
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with (results_root / "solutions.md").open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n## {stamp} — {repair_code}\n\n"
            f"- 现有证据：`{json.dumps(evidence, ensure_ascii=False, allow_nan=False, default=str)}`。\n"
            "- 根因候选：源码/父证据身份漂移、测试合同失败、A3端点语义不一致或环境不满足。\n"
            "- 最小诊断：只复查首个失败字段和对应原始轨迹，不放宽 `1e-12 rad` 门槛。\n"
            "- 恢复门槛：同一协议、同一父证据下修复后完整 pytest、一步/20步 A3 身份和父公共物理身份全部通过。\n"
            "- 风险：改阈值、删除不利轨迹或改 A3 参数会破坏归因，禁止据此转为 PASS。\n"
        )


def _find_metadata_by_sha(root: Path, expected_sha: str) -> Path:
    matches = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "raw" in {part.lower() for part in path.parts}:
            continue
        if path.suffix.lower() not in {".json", ".md", ".csv"}:
            continue
        if sha256(path) == expected_sha:
            matches.append(path)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one metadata file with SHA {expected_sha}, found {matches}"
        )
    return matches[0]


def _parent_identity(project: Path, protocol: dict) -> dict:
    parent = protocol["parent"]
    source_root = project / Path(parent["source_root"])
    results_root = project / Path(parent["results_root"])
    n2_root = results_root / "runs" / parent["n2_run_id"] / "n2"
    protocol_path = source_root / "config" / "protocol_icr_next.json"
    manifest = source_manifest(source_root)
    checks = {
        "source_manifest": {
            "path": str(source_root),
            "expected": parent["source_manifest_sha256"],
            "actual": json_sha256(manifest),
        },
        "protocol": {
            "path": str(protocol_path),
            "expected": parent["protocol_sha256"],
            "actual": sha256(protocol_path),
        },
    }
    metadata = {
        "n2_complete": parent["n2_complete_sha256"],
        "n2_report": parent["n2_report_sha256"],
        "n2_data_manifest": parent["n2_data_manifest_sha256"],
        "n2_audit_summary": parent["n2_audit_summary_sha256"],
        "n2_independent_complete": parent["n2_independent_complete_sha256"],
    }
    for label, expected in metadata.items():
        path = _find_metadata_by_sha(n2_root, expected)
        checks[label] = {"path": str(path), "expected": expected, "actual": sha256(path)}
    complete = _read_json(Path(checks["n2_complete"]["path"]))
    semantic_ok = bool(
        complete.get("passed")
        and complete.get("stage_status") == "PASS_DIAGNOSTIC_WITH_COUNTERFACTUAL_OOD"
        and complete.get("human_stop") is True
    )
    return {
        "passed": all(item["expected"] == item["actual"] for item in checks.values())
        and semantic_ok,
        "checks": checks,
        "n2_semantic_status": complete.get("stage_status"),
        "n2_human_stop": complete.get("human_stop"),
        "n2_root": str(n2_root),
    }


def _schema_ledgers(output: Path) -> dict:
    schemas = [build_schema_variant(variant) for variant in ("S0", "S1", "S2")]
    rows = []
    for schema in schemas:
        for category in ("inputs", "labels"):
            for item in schema[category]:
                rows.append(
                    {
                        "variant": schema["variant"],
                        "category": category,
                        "name": item["name"],
                        "shape": json.dumps(item["shape"]),
                        "dimension": item["dimension"],
                        "unit": item["unit"],
                        "endpoint": item["endpoint"],
                        "role": item["role"],
                        "source": item["source"],
                        "physical_components": json.dumps(item["physical_components"]),
                    }
                )
    write_json(output / "schema_ledger.json", schemas)
    _write_csv(output / "schema_ledger.csv", rows)
    passed = all(schema["contract_audit"]["passed"] for schema in schemas)
    return {
        "passed": passed,
        "variant_count": len(schemas),
        "field_row_count": len(rows),
        "duplicate_physical_feature_count": sum(
            schema["contract_audit"]["duplicate_physical_feature_count"] for schema in schemas
        ),
        "future_measured_input_count": sum(
            schema["contract_audit"]["future_measured_input_count"] for schema in schemas
        ),
    }


def _dry_run_matrix(protocol: dict, output: Path) -> dict:
    rows = build_predict_pilot_identities(protocol)
    audit = audit_predict_pilot_identities(rows, protocol)
    write_json(output / "dry_run_126_identities.json", rows)
    _write_csv(output / "dry_run_126_identities.csv", rows)
    write_json(output / "dry_run_126_audit.json", audit)
    return audit


def _future_split_contract(protocol: dict, output: Path) -> dict:
    ledger = build_future_split_ledger(protocol)
    rows = ledger["visible_rows"]
    audit = validate_base_family_split_contract(
        np.asarray([row["base_family_id"] for row in rows]),
        np.asarray([row["split"] for row in rows]),
    )
    ledger["audit"].update(audit)
    write_json(output / "future_split_ledger.json", ledger)
    _write_csv(output / "future_visible_base_families.csv", rows)
    return ledger["audit"]


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def _a3_raw_identity(parent: dict, protocol: dict, output: Path) -> dict:
    n2_root = Path(parent["n2_root"])
    manifest_path = Path(parent["checks"]["n2_data_manifest"]["path"])
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as stream:
        rows = [row for row in csv.DictReader(stream) if row["actuator_mode"] == "A3"]
    if len(rows) != 4:
        raise RuntimeError(f"expected four N2 A3 trajectories, found {len(rows)}")
    expected_config = protocol["actuator"]
    per_trajectory = []
    global_one = 0.0
    global_twenty = 0.0
    for row in rows:
        raw_path = Path(row["raw_path"])
        if not raw_path.is_absolute():
            raw_path = n2_root / "raw" / raw_path.name
        arrays = _load_npz(raw_path)
        actual = np.asarray(arrays["actual_steering_rad"], dtype=float)
        request = np.asarray(arrays["requested_control4x2"], dtype=float)[:, :, 1]
        config = SteeringActuatorConfig(
            tau_delta_s=float(np.asarray(arrays["actuator_tau_delta_s"]).reshape(-1)[0]),
            rate_max_radps=float(np.asarray(arrays["actuator_rate_max_radps"]).reshape(-1)[0]),
            angle_max_rad=float(np.asarray(arrays["actuator_angle_max_rad"]).reshape(-1)[0]),
        )
        config_error = max(
            abs(config.tau_delta_s - float(expected_config["tau_delta_s"])),
            abs(config.rate_max_radps - float(expected_config["rate_max_radps"])),
            abs(config.angle_max_rad - np.deg2rad(float(expected_config["angle_max_deg"]))),
        )
        one_error = 0.0
        for start in range(actual.shape[0] - 1):
            prediction = rollout_actuator_step(
                actual[start],
                request[start + 1],
                model_step_s=float(expected_config["model_step_s"]),
                plant_step_s=float(expected_config["plant_step_s"]),
                config=config,
            )["delta_act_k1_rad"]
            one_error = max(one_error, float(np.max(np.abs(prediction - actual[start + 1]))))
        twenty_error = 0.0
        horizon = int(expected_config["horizon_steps"])
        for start in range(actual.shape[0] - horizon):
            prediction = rollout_actuator_horizon(
                actual[start],
                request[start + 1 : start + horizon + 1],
                model_step_s=float(expected_config["model_step_s"]),
                plant_step_s=float(expected_config["plant_step_s"]),
                config=config,
            )["delta_act_endpoints_rad"][-1]
            twenty_error = max(
                twenty_error,
                float(np.max(np.abs(prediction - actual[start + horizon]))),
            )
        global_one = max(global_one, one_error)
        global_twenty = max(global_twenty, twenty_error)
        per_trajectory.append(
            {
                "trajectory_id": int(row["trajectory_id"]),
                "direction": row["direction"],
                "plant": row["plant"],
                "raw_path": str(raw_path),
                "sample_count": int(actual.shape[0]),
                "one_step_max_abs_rad": one_error,
                "twenty_step_max_abs_rad": twenty_error,
                "actuator_config_max_abs": config_error,
            }
        )
    tolerance = float(expected_config["endpoint_atol_rad"])
    result = {
        "passed": global_one <= tolerance
        and global_twenty <= tolerance
        and max(row["actuator_config_max_abs"] for row in per_trajectory) <= tolerance,
        "trajectory_count": len(rows),
        "one_step_max_abs_rad": global_one,
        "twenty_step_max_abs_rad": global_twenty,
        "endpoint_atol_rad": tolerance,
        "per_trajectory": per_trajectory,
    }
    write_json(output / "n2_a3_analytic_identity.json", result)
    _write_csv(output / "n2_a3_analytic_identity.csv", per_trajectory)
    return result


def _run_tests(project: Path, protocol: dict, output: Path) -> dict:
    env = os.environ.copy()
    env["KOOPMAN_PROJECT_ROOT"] = str(project)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=int(protocol["n3"]["pytest_timeout_s"]),
        env=env,
    )
    (output / "pytest.txt").write_text(
        completed.stdout + "\n--- STDERR ---\n" + completed.stderr,
        encoding="utf-8",
    )
    return {"passed": completed.returncode == 0, "returncode": completed.returncode}


def _parent_common_identity(protocol: dict, output: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "dev_identity_icr_next.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=int(protocol["n3"]["parent_identity_timeout_s"]),
        env=env,
    )
    (output / "parent_a3_common_identity_stdout_stderr.txt").write_text(
        completed.stdout + "\n--- STDERR ---\n" + completed.stderr,
        encoding="utf-8",
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"passed": False, "parse_error": True, "stdout": completed.stdout}
    payload["subprocess_returncode"] = completed.returncode
    payload["passed"] = bool(payload.get("passed") and completed.returncode == 0)
    write_json(output / "parent_a3_common_identity.json", payload)
    return payload


def run_n3(project: Path, protocol_path: Path, taskbook: Path, protocol: dict, run_root: Path) -> dict:
    started = time.perf_counter()
    output = run_root / "n3"
    output.mkdir()
    shutil.copy2(taskbook, output / "taskbook_snapshot.md")
    shutil.copy2(protocol_path, output / "protocol_snapshot.json")
    parent = _parent_identity(project, protocol)
    write_json(output / "parent_n2_identity.json", parent)
    schema = _schema_ledgers(output)
    dry_run = _dry_run_matrix(protocol, output)
    splits = _future_split_contract(protocol, output)
    analytic = _a3_raw_identity(parent, protocol, output) if parent["passed"] else {"passed": False}
    tests = _run_tests(project, protocol, output)
    common = _parent_common_identity(protocol, output)
    frozen = freeze(
        project_root=project,
        source_root=ROOT,
        protocol_path=protocol_path,
        taskbook_path=taskbook,
        output=output / "freeze",
    )
    environment = frozen["environment"]
    environment_passed = bool(
        environment["hostname"].upper() == "DESKTOP-9IUUGEO"
        and environment["cuda_available"]
        and "RTX 5080" in str(environment["gpu"])
        and float(environment["disk_free_gib"])
        >= float(protocol["resource_limits"]["minimum_free_gib"])
    )
    gates = {
        "parent_n2_identity": parent["passed"],
        "taskbook_identity": frozen["taskbook_sha256"] == protocol["taskbook_sha256"],
        "schema_contract": schema["passed"],
        "dry_run_126": dry_run["passed"],
        "split_contract": splits["passed"] and splits["confirm_visible_row_count"] == 0,
        "n2_a3_one_and_twenty_step_identity": analytic["passed"],
        "full_pytest": tests["passed"],
        "parent_a3_common_physics_identity": common["passed"],
        "environment_5080": environment_passed,
        "no_formal_raw_written": dry_run["raw_files_written"] == 0
        and not (output / "raw").exists(),
    }
    passed = all(gates.values())
    result = {
        "stage": "N3",
        "stage_status": "PASS_STOPPED_AFTER_N3" if passed else "BLOCKED_N3_HARD_GATE",
        "passed": passed,
        "human_stop": True,
        "protocol_sha256": frozen["protocol_sha256"],
        "taskbook_sha256": frozen["taskbook_sha256"],
        "source_manifest_sha256": frozen["source_manifest_sha256"],
        "source_file_count": frozen["source_file_count"],
        "gates": gates,
        "schema_audit": schema,
        "dry_run_audit": dry_run,
        "split_audit": splits,
        "a3_analytic_identity": analytic,
        "pytest": tests,
        "parent_a3_common_identity_passed": common["passed"],
        "runtime_s": time.perf_counter() - started,
        "next_stage": "N4_NOT_RUN_REQUIRES_SEPARATE_AUTHORIZATION",
        "forbidden_stage_status": {
            stage: "NOT_RUN" for stage in protocol["forbidden_without_later_authorization"]
        },
    }
    if not passed:
        result["repair_code"] = "N3_IDENTITY_SCHEMA_SPLIT_A3_TEST_OR_ENVIRONMENT_FAILED"
    write_json(output / "complete.json", result)
    return result


def main() -> None:
    if "--auto-through" in sys.argv or "--resume-run" in sys.argv or "--stage" in sys.argv and any(
        value in sys.argv for value in ("A0", "N4-S")
    ):
        from auto_pipeline import main as auto_main

        auto_main()
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=["N3", "N4", "N5", "N6"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--taskbook", required=True)
    parser.add_argument("--run-tag", required=True)
    args = parser.parse_args()
    if args.stage != "N3":
        raise PermissionError(f"{args.stage} is not authorized; stop after N3")
    if not args.dry_run:
        raise PermissionError("N3 requires --dry-run and cannot write formal raw trajectories")
    project = Path(args.project_root).resolve()
    protocol_path = Path(args.protocol).resolve()
    taskbook = Path(args.taskbook).resolve()
    protocol = _read_json(protocol_path)
    validate_predict_protocol(protocol)
    if ROOT.resolve() != (project / Path(protocol["source_root"])).resolve():
        raise RuntimeError(
            f"source root mismatch: actual={ROOT}, expected={project / Path(protocol['source_root'])}"
        )
    if sha256(taskbook) != protocol["taskbook_sha256"]:
        raise RuntimeError("taskbook SHA does not match the frozen N3 protocol")
    results_root = project / Path(protocol["results_root"])
    results_root.mkdir(parents=True, exist_ok=True)
    if not (results_root / "work_log.md").exists():
        (results_root / "work_log.md").write_text("# Koopman Predict Next 工作记录\n", encoding="utf-8")
    if not (results_root / "solutions.md").exists():
        (results_root / "solutions.md").write_text("# Koopman Predict Next 失败与解决方案\n", encoding="utf-8")
    run_root = _run_root(results_root, args.run_tag)
    output = run_root / "n3"
    _append_work_log(results_root, "start", "RUNNING", {"run_root": str(run_root)})
    try:
        result = run_n3(project, protocol_path, taskbook, protocol, run_root)
    except Exception as error:
        output.mkdir(parents=True, exist_ok=True)
        failure = {
            "stage": "N3",
            "stage_status": "BLOCKED_N3_EXCEPTION",
            "passed": False,
            "human_stop": True,
            "repair_code": "N3_UNHANDLED_EXCEPTION",
            "error": repr(error),
            "traceback": traceback.format_exc(),
            "next_stage": "NOT_RUN",
            "forbidden_stage_status": {
                stage: "NOT_RUN" for stage in protocol["forbidden_without_later_authorization"]
            },
        }
        write_json(output / "complete.json", failure)
        _append_solution(results_root, failure["repair_code"], failure)
        _append_work_log(results_root, "exception", failure["stage_status"], failure)
        raise
    status = {
        "current_stage": "N3",
        "stage_status": result["stage_status"],
        "passed": result["passed"],
        "human_stop": True,
        "run_dir": str(run_root),
        "complete": str(output / "complete.json"),
        "forbidden_stage_status": result["forbidden_stage_status"],
    }
    write_json(results_root / "stage_status.json", status)
    if not result["passed"]:
        _append_solution(results_root, result["repair_code"], result["gates"])
    _append_work_log(results_root, "complete", result["stage_status"], status)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
