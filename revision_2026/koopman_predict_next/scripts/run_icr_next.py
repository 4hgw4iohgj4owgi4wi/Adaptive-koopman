from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]


def _json_safe(value: object) -> object:
    """Convert numpy containers/scalars without converting booleans to strings."""

    import numpy as np

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _json_safe(value),
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


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
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _runtime_protocol(protocol: dict) -> dict:
    """Compatibility view for unchanged frozen simulation helpers."""

    runtime = json.loads(json.dumps(protocol))
    runtime["i1"] = {
        "seed": runtime["n2"]["seed"],
        "scenario": runtime["n2"]["scenario"],
        "directions": runtime["n2"]["directions"],
        "plants": runtime["n2"]["plants"],
        "load_mode": runtime["n2"]["load_mode"],
        "load_transfer_enabled": runtime["n2"]["load_transfer_enabled"],
        "actuator_modes": runtime["n2"]["mathematical_mode_order"],
    }
    runtime["resource_limits"]["maximum_i1_hours"] = runtime["resource_limits"]["maximum_n2_hours"]
    return runtime


def validate_protocol(protocol: dict) -> dict:
    modes = list(protocol["n2"]["mathematical_mode_order"])
    execution = list(protocol["n2"]["execution_mode_order"])
    if len(modes) != 4 or len(modes) != len(set(modes)) or set(modes) != {"A0", "A1", "A2", "A3"}:
        raise ValueError("N2 requires unique A0/A1/A2/A3 mathematical modes")
    if set(execution) != set(modes) or len(execution) != len(set(execution)):
        raise ValueError("execution modes must be a unique permutation of mathematical modes")
    pilots = list(protocol["n2"]["pilot_order"])
    if len(pilots) != 2 or [item["actuator_mode"] for item in pilots] != ["A3", "A0"]:
        raise ValueError("pilot order must be A3 then A0")
    blocks = protocol["seed_blocks"]
    overlaps = []
    names = list(blocks)
    for left_index, left in enumerate(names):
        low_left, high_left = map(int, blocks[left])
        if low_left > high_left:
            raise ValueError(f"invalid seed block: {left}")
        for right in names[left_index + 1 :]:
            low_right, high_right = map(int, blocks[right])
            if max(low_left, low_right) <= min(high_left, high_right):
                overlaps.append((left, right))
    if overlaps:
        raise ValueError(f"overlapping seed blocks: {overlaps}")
    if int(protocol["n2"]["seed"]) != int(blocks["N2_DIAGNOSTIC"][0]):
        raise ValueError("N2 seed does not match its frozen diagnostic block")
    tolerance_keys = {
        "icr_mps_abs", "fraction_abs", "rate_radps_abs", "angle_rad_abs",
        "tire_abs", "support_n_abs", "force_n_abs", "impulse_ns_abs",
        "relative_abs", "parent_common_abs",
    }
    tolerances = protocol.get("independent_recompute_tolerances", {})
    if set(tolerances) != tolerance_keys or any(
        not math.isfinite(float(value)) or float(value) <= 0.0
        for value in tolerances.values()
    ):
        raise ValueError("independent recompute tolerances must be complete, finite and positive")
    return {"passed": True, "mode_count": len(modes), "seed_block_count": len(blocks)}


def _source_identity(root: Path) -> tuple[dict, str]:
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from contracts import json_sha256, source_manifest

    manifest = source_manifest(root)
    return manifest, json_sha256(manifest)


def _run_root(results_root: Path, stage: str, run_tag: str) -> Path:
    runs = results_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for revision in range(1, 100):
        candidate = runs / f"{stamp}_{stage}_{run_tag}_R{revision:02d}"
        if not candidate.exists():
            candidate.mkdir()
            return candidate
    raise RuntimeError("cannot allocate unique run directory")


def _append_log(results_root: Path, stage: str, action: str, status: str, details: dict) -> None:
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    path = results_root / "work_log.md"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n## {stamp} — {stage}/{action}\n\n"
            f"- 授权范围：N0→N2（仅在显式执行请求后）。\n"
            f"- 主机/项目根：{platform.node()} / `{PROJECT}`。\n"
            f"- 命令：`{' '.join(sys.argv)}`。\n"
            f"- 关键结果：`{json.dumps(_json_safe(details), ensure_ascii=False, allow_nan=False)}`。\n"
            f"- 状态：{status}。\n"
            f"- 下一允许动作：{'人工查看；N3及以后仍NOT_RUN' if stage == 'N2' else '仅当前任务树的下一阶段'}。\n"
        )


def _append_solution(results_root: Path, stage: str, code: str, details: dict) -> None:
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with (results_root / "solutions.md").open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n## {stamp} — {stage}: {code}\n\n"
            "- 根因候选：从首个失败字段、模式身份、时间端点和父身份逐项定位。\n"
            "- 反证：只改变一个诊断变量并使用相同 seed/线程/工况复现。\n"
            "- 允许修复：审计、调度、导入、JSON 类型或确定的端点错误。\n"
            "- 禁止：放宽 0.90、修改 D2、改变 A3 物理或删除失败成员。\n"
            "- 代价：源码改变后 N0 身份失效，必须从 N0 重新进入。\n"
            f"- 现场：`{json.dumps(_json_safe(details), ensure_ascii=False, allow_nan=False)}`。\n"
        )


def _update_status(results_root: Path, stage: str, output: Path, complete: dict) -> None:
    path = results_root / "stage_status.json"
    status = _read_json(path) if path.exists() else {"stages": {}}
    semantic = str(complete.get("stage_status", "PASS" if complete.get("passed") else "BLOCKED"))
    status.setdefault("stages", {})[stage] = {
        "status": semantic,
        "run_dir": str(output),
        "complete": str(output / "complete.json"),
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    for forbidden in complete.get("forbidden_stage_status", {}):
        status["stages"].setdefault(forbidden, {"status": "NOT_RUN"})
    status["human_stop_required"] = stage == "N2"
    _write_json(path, status)


def _require_previous(results_root: Path, stage: str, protocol_path: Path) -> None:
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from contracts import sha256

    required = {"N0": (), "N1": ("N0",), "N2": ("N0", "N1")}[stage]
    if not required:
        return
    status_path = results_root / "stage_status.json"
    if not status_path.exists():
        raise RuntimeError(f"{stage} requires prior stage_status.json")
    status = _read_json(status_path)
    current_source = _source_identity(ROOT)[1]
    current_protocol = sha256(protocol_path)
    for prior in required:
        record = status.get("stages", {}).get(prior, {})
        if record.get("status") != "PASS":
            raise RuntimeError(f"{stage} requires {prior}=PASS, found {record}")
        complete = _read_json(Path(record["complete"]))
        if not complete.get("passed"):
            raise RuntimeError(f"{prior} complete.json is not PASS")
        if complete["source_manifest_sha256"] != current_source:
            raise RuntimeError(f"source changed after {prior}; rerun N0")
        if complete["protocol_sha256"] != current_protocol:
            raise RuntimeError(f"protocol changed after {prior}; rerun N0")


def _parent_f3_evidence(protocol: dict) -> dict:
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from contracts import sha256
    from data_manifest import file_sha256

    parent = protocol["parent_f3"]
    manifest_path = PROJECT / Path(parent["run_root"]) / Path(parent["manifest_relpath"])
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    raw_root = PROJECT / Path(parent["data_root"])
    raw = []
    for row in rows:
        path = raw_root / Path(row["raw_path"]).name
        actual = file_sha256(path) if path.exists() else None
        raw.append(
            {
                "trajectory_id": int(row["trajectory_id"]),
                "path": str(path),
                "expected_sha256": row["raw_file_sha256"],
                "actual_sha256": actual,
                "passed": actual == row["raw_file_sha256"],
            }
        )
    actual_manifest = sha256(manifest_path)
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": actual_manifest,
        "manifest_expected_sha256": parent["manifest_sha256"],
        "trajectory_count": len(rows),
        "raw": raw,
        "passed": actual_manifest == parent["manifest_sha256"]
        and len(rows) == int(parent["expected_trajectory_count"])
        and all(row["passed"] for row in raw),
    }


def run_n0(protocol_path: Path, protocol: dict, run_root: Path) -> dict:
    started = time.perf_counter()
    output = run_root / "n0"
    output.mkdir(parents=True, exist_ok=False)
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
    import numpy as np
    import scipy
    import torch
    import run_icr_fix as legacy
    from contracts import sha256

    processes = legacy._process_snapshot()
    unknown = [row for row in processes if int(row.get("ProcessId", -1)) != os.getpid()]
    disk = shutil.disk_usage(PROJECT)
    environment = {
        "hostname": platform.node(),
        "python_executable": sys.executable,
        "python": sys.version,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "disk_free_gib": disk.free / 1024**3,
        "git_repository": (PROJECT / ".git").exists(),
        "unknown_python_matlab_processes": unknown,
        "thread_environment": {
            key: os.environ.get(key) for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS")
        },
    }
    _write_json(output / "environment.json", environment)
    own_manifest, own_sha = _source_identity(ROOT)
    parent_manifest, parent_sha = _source_identity(PROJECT / Path(protocol["parent_source_root"]))
    source = {
        "source_manifest": own_manifest,
        "source_manifest_sha256": own_sha,
        "parent_source_manifest_sha256": parent_sha,
        "parent_source_expected_sha256": protocol["parent_source_manifest_sha256"],
        "parent_source_passed": parent_sha == protocol["parent_source_manifest_sha256"],
    }
    _write_json(output / "source_identity.json", source)
    parent_files = []
    for name, record in (
        ("parent_i0", protocol["parent_i0"]),
        ("parent_i1_complete", {"complete_path": protocol["parent_i1_failure"]["complete_path"], "complete_sha256": protocol["parent_i1_failure"]["complete_sha256"]}),
        ("parent_i1_diagnostic", {"complete_path": protocol["parent_i1_failure"]["diagnostic_path"], "complete_sha256": protocol["parent_i1_failure"]["diagnostic_sha256"]}),
        ("parent_i1_a0_raw", {"complete_path": protocol["parent_i1_failure"]["a0_raw_path"], "complete_sha256": protocol["parent_i1_failure"]["a0_raw_sha256"]}),
    ):
        path = PROJECT / Path(record["complete_path"])
        actual = sha256(path) if path.exists() else None
        parent_files.append(
            {"name": name, "path": str(path), "expected_sha256": record["complete_sha256"], "actual_sha256": actual, "passed": actual == record["complete_sha256"]}
        )
    f3 = _parent_f3_evidence(protocol)
    _write_json(output / "parent_evidence.json", {"registered_files": parent_files, "parent_f3": f3})
    taskbook_hashes = {
        "taskbook": sha256(ROOT / "protocol.md"),
        "parent_icr_taskbook": sha256(ROOT / "protocol_v1.md"),
        "parent_icr_fix_taskbook": sha256(ROOT / "parent_protocol.md"),
        "parent_koopman_taskbook": sha256(ROOT / "grandparent_protocol.md"),
    }
    for source_path, destination in (
        (ROOT / "protocol.md", output / "protocol_snapshot.md"),
        (ROOT / "protocol_v1.md", output / "parent_icr_protocol_snapshot.md"),
        (ROOT / "parent_protocol.md", output / "parent_icr_fix_protocol_snapshot.md"),
        (ROOT / "grandparent_protocol.md", output / "grandparent_protocol_snapshot.md"),
    ):
        shutil.copy2(source_path, destination)
    runtime = _runtime_protocol(protocol)
    thread_probe = legacy._thread_identity_probe(protocol_path, output, runtime)
    _write_json(output / "thread_identity_probe.json", thread_probe)
    test_env = os.environ.copy()
    test_env["KOOPMAN_PROJECT_ROOT"] = str(PROJECT)
    tests = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
        env=test_env,
    )
    (output / "pytest.txt").write_text(
        tests.stdout + "\n--- STDERR ---\n" + tests.stderr, encoding="utf-8"
    )
    passed = bool(
        environment["hostname"].upper() == protocol["project_host"].upper()
        and environment["cuda_available"]
        and "RTX 5080" in str(environment["gpu"])
        and environment["disk_free_gib"] >= float(protocol["resource_limits"]["minimum_free_gib"])
        and not environment["git_repository"]
        and not unknown
        and environment["thread_environment"]
        == {"OMP_NUM_THREADS": protocol["threads"]["OMP_NUM_THREADS"], "MKL_NUM_THREADS": protocol["threads"]["MKL_NUM_THREADS"]}
        and parent_sha == protocol["parent_source_manifest_sha256"]
        and all(row["passed"] for row in parent_files)
        and f3["passed"]
        and taskbook_hashes["taskbook"] == protocol["taskbook_sha256"]
        and taskbook_hashes["parent_icr_taskbook"] == protocol["parent_icr_taskbook_sha256"]
        and taskbook_hashes["parent_icr_fix_taskbook"] == protocol["parent_icr_fix_taskbook_sha256"]
        and taskbook_hashes["parent_koopman_taskbook"] == protocol["parent_koopman_taskbook_sha256"]
        and thread_probe["passed"]
        and tests.returncode == 0
    )
    complete = {
        "stage": "N0",
        "stage_status": "PASS" if passed else "BLOCKED",
        "passed": passed,
        "protocol_sha256": sha256(protocol_path),
        "source_manifest_sha256": own_sha,
        "parent_source_manifest_sha256": parent_sha,
        "taskbook_hashes": taskbook_hashes,
        "parent_f3_raw_count": len(f3["raw"]),
        "parent_f3_raw_mismatch_count": sum(not row["passed"] for row in f3["raw"]),
        "unknown_process_count": len(unknown),
        "thread_identity_max_abs": thread_probe.get("max_abs"),
        "pytest_returncode": tests.returncode,
        "runtime_s": time.perf_counter() - started,
    }
    if not passed:
        complete["repair_code"] = "N0_IDENTITY_ENVIRONMENT_THREAD_OR_TEST_FAILED"
    _write_json(output / "complete.json", complete)
    return complete


def _short_parent_identity(protocol_path: Path, protocol: dict, output: Path) -> dict:
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
    import run_icr_fix as legacy
    from audit_icr_fix import compare_common_fields

    parent_root = PROJECT / Path(protocol["parent_source_root"])
    jobs = (
        ("parent", parent_root / "scripts" / "thread_probe_worker.py", parent_root / "config" / "protocol_icr_fix.json"),
        ("candidate", ROOT / "scripts" / "thread_probe_worker.py", protocol_path),
    )
    files = {}
    commands = []
    env = os.environ.copy()
    for label, worker, selected_protocol in jobs:
        target = output / f"a3_short_{label}.npz"
        command = [sys.executable, str(worker), "--protocol", str(selected_protocol), "--output", str(target)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=600, env=env)
        commands.append({"label": label, "command": command, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
        if completed.returncode != 0:
            return {"passed": False, "commands": commands, "max_abs": 1.0e300}
        files[label] = legacy._load_npz(target)
    comparison = compare_common_fields(files["candidate"], files["parent"])
    return {
        "passed": comparison["max_abs"] <= float(protocol["threads"]["identity_max_abs"]),
        "commands": commands,
        **comparison,
    }


def run_n1(protocol_path: Path, protocol: dict, run_root: Path) -> dict:
    started = time.perf_counter()
    output = run_root / "n1"
    output.mkdir(parents=True, exist_ok=False)
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
    from contracts import sha256

    identity = _short_parent_identity(protocol_path, protocol, output)
    _write_json(output / "a3_parent_short_identity.json", identity)
    test_env = os.environ.copy()
    test_env["KOOPMAN_PROJECT_ROOT"] = str(PROJECT)
    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_icr_next_gates.py",
            "tests/test_icr_allocator.py",
            "tests/test_focus_schema.py",
            "tests/test_steering_actuator.py",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
        env=test_env,
    )
    (output / "semantic_tests.txt").write_text(
        tests.stdout + "\n--- STDERR ---\n" + tests.stderr, encoding="utf-8"
    )
    passed = bool(identity["passed"] and tests.returncode == 0)
    complete = {
        "stage": "N1",
        "stage_status": "PASS" if passed else "BLOCKED",
        "passed": passed,
        "protocol_sha256": sha256(protocol_path),
        "source_manifest_sha256": _source_identity(ROOT)[1],
        "a3_parent_common_max_abs": identity["max_abs"],
        "pytest_returncode": tests.returncode,
        "runtime_s": time.perf_counter() - started,
    }
    if not passed:
        complete["repair_code"] = "N1_SEMANTIC_TEST_OR_A3_IDENTITY_FAILED"
    _write_json(output / "complete.json", complete)
    return complete


def _n2_jobs(protocol: dict) -> tuple[list[dict], list[list[dict]]]:
    runtime = _runtime_protocol(protocol)
    canonical: dict[tuple[str, str, str], dict] = {}
    trajectory_id = 0
    for direction in protocol["n2"]["directions"]:
        for plant in protocol["n2"]["plants"]:
            for mode in protocol["n2"]["mathematical_mode_order"]:
                identity = {
                    "trajectory_id": trajectory_id,
                    "base_family_id": f"N2_D2_{protocol['n2']['seed']}",
                    "seed": int(protocol["n2"]["seed"]),
                    "scenario": "D2",
                    "direction": direction,
                    "plant": plant["name"],
                    "law": plant["law"],
                    "load_mode": "L1",
                    "load_transfer_enabled": True,
                    "actuator_mode": mode,
                }
                canonical[(direction, plant["name"], mode)] = {
                    "root": str(ROOT), "protocol": runtime, "identity": identity
                }
                trajectory_id += 1
    pilots = [
        canonical[(item["direction"], item["plant"], item["actuator_mode"])]
        for item in protocol["n2"]["pilot_order"]
    ]
    pilot_keys = {
        (job["identity"]["direction"], job["identity"]["plant"], job["identity"]["actuator_mode"])
        for job in pilots
    }
    batches = []
    for mode in protocol["n2"]["execution_mode_order"]:
        batch = [
            job
            for key, job in canonical.items()
            if key[2] == mode and key not in pilot_keys
        ]
        if batch:
            batches.append(batch)
    return pilots, batches


def _save_partial(output: Path, rows: list[dict]) -> None:
    if rows:
        _write_csv(output / "data_manifest_partial.csv", sorted(rows, key=lambda row: int(row["trajectory_id"])))


def _audit_one(identity, arrays, summary, protocol, parents):
    from audit_icr_fix import compare_common_fields
    from audit_icr_next import audit_trajectory

    comparison = None
    if identity["actuator_mode"] == "A3":
        comparison = compare_common_fields(arrays, parents[(identity["direction"], identity["plant"])])
    return audit_trajectory(identity, arrays, summary, protocol, comparison)


def _write_n2_report(output: Path, audit: dict, request: dict, mode_rows: list[dict]) -> None:
    lines = [
        "# N2 请求层与执行器归因报告",
        "",
        "> 结论边界：本报告只适用于冻结的 D2、L1、seed 910021、双方向、双植物和 A0–A3；A0/A1 是反事实，不代表可部署执行器。",
        "",
        "## 状态",
        "",
        f"- 阶段语义状态：`{audit['stage_status']}`。",
        f"- 16 条身份完整：`{audit['trajectory_count'] == audit['expected_trajectory_count']}`。",
        f"- 诊断完整性失败：`{audit['diagnostic_failure_count']}` 条。",
        f"- A2/A3 部署门失败：`{audit['deployment_failure_count']}` 条。",
        f"- A0/A1 反事实越域：`{audit['counterfactual_ood_trajectory_count']}` 条轨迹、`{audit['counterfactual_domain_event_count']}` 个首事件。",
        f"- G0 最大 ICR 残差：`{request['g0_peak_max_mps']:.12g} m/s`。",
        f"- G2 对父 F3 请求最大逐点差：`{request['g2_parent_request_max_abs_rad']:.12g} rad`。",
        f"- A3 对父 F3 公共字段最大逐点差：`{audit['a3_parent_common_max_abs']:.12g}`。",
        "",
        "## A0–A3 配对指标",
        "",
        "| 方向 | 植物 | 模式 | 部署适用 | P95 实际 ICR (m/s) | 峰值跟踪误差 (rad) | 轮胎峰值 | 连接力峰值 (N) |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in mode_rows:
        mode = str(row["actuator_mode"])
        lines.append(
            "| {direction} | {plant} | {mode} | {applicable} | {icr:.6g} | {tracking:.6g} | {tire:.6g} | {force:.6g} |".format(
                direction=row["direction"],
                plant=row["plant"],
                mode=mode,
                applicable="否（反事实）" if mode in {"A0", "A1"} else "是",
                icr=float(row["actual_icr_p95_mps"]),
                tracking=float(row["tracking_peak_rad"]),
                tire=float(row["tire_raw_utilization_max"]),
                force=float(row["connector_force_peak_n"]),
            )
        )
    lines += [
        "",
        "## 受力坐标说明",
        "",
        "- `force_payload_body_n[...,0]` 是货物车体坐标系纵向 Fx。",
        "- `force_payload_body_n[...,1]` 是货物车体坐标系横向 Fy；它不是重力方向的竖直力。",
        "- 真正的竖直支承作用由 `payload_support_load4_n` 单独报告。",
        "- 前后/左右拉伸采用明确的 `tension_proxy_n`，切换后 1 s 绝对冲量见 `stretch_switching_impulse.csv`。",
        "",
        "## 停止边界",
        "",
        "N2 交付后人工停止；N3、F4、训练、C1/C2 和 K0–K7 均保持 `NOT_RUN`。",
        "",
    ]
    (output / "n2_report.md").write_text("\n".join(lines), encoding="utf-8")


def run_n2(protocol_path: Path, protocol: dict, run_root: Path) -> dict:
    started = time.perf_counter()
    output = run_root / "n2"
    output.mkdir(parents=True, exist_ok=False)
    (output / "raw").mkdir()
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "plant"), str(ROOT / "scripts")]
    import run_icr_fix as legacy
    from audit_icr_next import audit_run
    from contracts import sha256

    runtime = _runtime_protocol(protocol)
    request = legacy._offline_request_attribution(runtime, output)
    if not request["passed"]:
        complete = {
            "stage": "N2", "stage_status": "BLOCKED_DIAGNOSTIC_INTEGRITY", "passed": False,
            "repair_code": "N2_REQUEST_ATTRIBUTION_FAILED", "human_stop": True,
            "runtime_s": time.perf_counter() - started,
        }
        _write_json(output / "complete.json", complete)
        return complete
    for csv_name, json_name in (
        ("request_attribution.csv", "request_attribution.json"),
        ("request_switching_attribution.csv", "request_switching_attribution.json"),
    ):
        with (output / csv_name).open("r", newline="", encoding="utf-8-sig") as stream:
            _write_json(output / json_name, list(csv.DictReader(stream)))

    parents = legacy._parent_seed_arrays(runtime)
    pilots, batches = _n2_jobs(protocol)
    trajectories = []
    manifest_rows: list[dict] = []
    raw_paths: list[Path] = []
    pilot_runtimes = []
    for count, job in enumerate(pilots, start=1):
        print(f"N2 pilot {count}/2: {job['identity']}", flush=True)
        result = legacy._simulate_job(job)
        if not result["ok"]:
            _write_json(output / f"pilot_{count:02d}_failure.json", result)
            complete = {"stage": "N2", "stage_status": "BLOCKED_DIAGNOSTIC_INTEGRITY", "passed": False, "repair_code": "N2_PILOT_EXCEPTION", "human_stop": True, "failure": result}
            _write_json(output / "complete.json", complete)
            return complete
        raw_paths.append(legacy._save_simulation_result(job, result, output, trajectories, manifest_rows))
        pilot_runtimes.append(float(result["runtime_s"]))
        identity, arrays, summary = trajectories[-1]
        row = _audit_one(identity, arrays, summary, runtime, parents)
        _write_json(output / f"pilot_{count:02d}_audit.json", row)
        if row["stage_blocking"]:
            _save_partial(output, manifest_rows)
            complete = {"stage": "N2", "stage_status": row["semantic_status"], "passed": False, "repair_code": "N2_PILOT_HARD_GATE_FAILED", "failed_identity": identity, "pilot_audit": row, "human_stop": True, "runtime_s": time.perf_counter() - started}
            _write_json(output / "complete.json", complete)
            return complete

    workers = int(protocol["resource_limits"]["parallel_workers"])
    remaining = sum(len(batch) for batch in batches)
    projected_s = sum(pilot_runtimes) + math.ceil(remaining / workers) * max(pilot_runtimes)
    budget_s = 3600.0 * float(protocol["resource_limits"]["maximum_n2_hours"])
    timing = {"pilot_runtime_s": pilot_runtimes, "remaining_trajectory_count": remaining, "workers": workers, "projected_total_simulation_s": projected_s, "budget_s": budget_s, "passed": projected_s <= budget_s}
    _write_json(output / "pilot_timing.json", timing)
    if not timing["passed"]:
        _save_partial(output, manifest_rows)
        complete = {"stage": "N2", "stage_status": "BLOCKED", "passed": False, "repair_code": "N2_PROJECTED_TIME_BUDGET_EXCEEDED", "timing": timing, "human_stop": True, "runtime_s": time.perf_counter() - started}
        _write_json(output / "complete.json", complete)
        return complete

    for batch in batches:
        mode = batch[0]["identity"]["actuator_mode"]
        print(f"N2 submitted {len(batch)} {mode} jobs to {workers} workers", flush=True)
        with ProcessPoolExecutor(max_workers=min(workers, len(batch))) as executor:
            results = list(executor.map(legacy._simulate_job, batch, chunksize=1))
        batch_rows = []
        for job, result in zip(batch, results):
            if not result["ok"]:
                _write_json(output / f"trajectory_failure_{job['identity']['trajectory_id']:04d}.json", {"identity": job["identity"], **result})
                _save_partial(output, manifest_rows)
                complete = {"stage": "N2", "stage_status": "BLOCKED_DIAGNOSTIC_INTEGRITY", "passed": False, "repair_code": "N2_TRAJECTORY_EXCEPTION", "failure": {"identity": job["identity"], **result}, "human_stop": True, "runtime_s": time.perf_counter() - started}
                _write_json(output / "complete.json", complete)
                return complete
            raw_paths.append(legacy._save_simulation_result(job, result, output, trajectories, manifest_rows))
            identity, arrays, summary = trajectories[-1]
            row = _audit_one(identity, arrays, summary, runtime, parents)
            batch_rows.append(row)
            _write_json(output / f"trajectory_{identity['trajectory_id']:04d}_audit.json", row)
        blockers = [row for row in batch_rows if row["stage_blocking"]]
        if blockers:
            _save_partial(output, manifest_rows)
            complete = {"stage": "N2", "stage_status": blockers[0]["semantic_status"], "passed": False, "repair_code": "N2_BATCH_HARD_GATE_FAILED", "failed_rows": blockers, "human_stop": True, "runtime_s": time.perf_counter() - started}
            _write_json(output / "complete.json", complete)
            return complete

    manifest_rows.sort(key=lambda row: int(row["trajectory_id"]))
    trajectories.sort(key=lambda item: int(item[0]["trajectory_id"]))
    _write_csv(output / "data_manifest.csv", manifest_rows)
    audit = audit_run(trajectories, runtime, parents, output)
    for csv_name, json_name in (
        ("actuator_attribution.csv", "actuator_attribution.json"),
        ("actuator_contributions.csv", "actuator_contributions.json"),
        ("counterfactual_domain_events.csv", "counterfactual_domain_events.json"),
        ("stretch_switching_impulse.csv", "stretch_switching_impulse.json"),
    ):
        with (output / csv_name).open("r", newline="", encoding="utf-8-sig") as stream:
            _write_json(output / json_name, list(csv.DictReader(stream)))
    with (output / "actuator_attribution.csv").open("r", newline="", encoding="utf-8-sig") as stream:
        mode_rows = list(csv.DictReader(stream))
    _write_n2_report(output, audit, request, mode_rows)

    independent_output = output / "independent_recompute"
    recompute_command = [
        sys.executable,
        str(ROOT / "scripts" / "recompute_icr_next.py"),
        "--protocol",
        str(protocol_path),
        "--data-manifest",
        str(output / "data_manifest.csv"),
        "--output",
        str(independent_output),
    ]
    recompute = subprocess.run(
        recompute_command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
        env=os.environ.copy(),
    )
    (output / "independent_recompute_stdout_stderr.txt").write_text(
        recompute.stdout + "\n--- STDERR ---\n" + recompute.stderr,
        encoding="utf-8",
    )
    if recompute.returncode != 0:
        complete = {
            "stage": "N2",
            "stage_status": "BLOCKED_DIAGNOSTIC_INTEGRITY",
            "passed": False,
            "repair_code": "N2_INDEPENDENT_RECOMPUTE_FAILED",
            "human_stop": True,
            "runtime_s": time.perf_counter() - started,
        }
        _write_json(output / "complete.json", complete)
        return complete
    independent = _read_json(independent_output / "complete.json")
    independent_match = bool(
        independent.get("passed")
        and independent.get("status") == "PASS"
        and independent.get("comparison", {}).get("passed")
        and int(independent.get("trajectory_count", -1)) == len(trajectories)
    )
    from plot_icr_next import plot_n2

    figures = plot_n2(
        trajectories,
        request["example"],
        mode_rows,
        output,
        raw_paths + [output / "request_attribution.csv", output / "actuator_attribution.csv", output / "counterfactual_domain_events.csv", output / "stretch_switching_impulse.csv"],
        protocol_path,
    )
    runtime_s = time.perf_counter() - started
    replay_mismatch = sum(not bool(row["replay_hash_match"]) for row in manifest_rows)
    passed = bool(
        audit["stage_passed"]
        and replay_mismatch == 0
        and independent_match
        and runtime_s <= budget_s
    )
    complete = {
        "stage": "N2",
        "stage_status": audit["stage_status"] if passed else "BLOCKED",
        "passed": passed,
        "protocol_sha256": sha256(protocol_path),
        "source_manifest_sha256": _source_identity(ROOT)[1],
        "trajectory_count": len(trajectories),
        "simulation_count": 2 * len(trajectories),
        "replay_mismatch_count": replay_mismatch,
        "g0_peak_max_mps": request["g0_peak_max_mps"],
        "g2_parent_request_max_abs_rad": request["g2_parent_request_max_abs_rad"],
        "audit": audit,
        "independent_recompute_match": independent_match,
        "independent_recompute_script_sha256": sha256(
            ROOT / "scripts" / "recompute_icr_next.py"
        ),
        "independent_recompute_complete_sha256": sha256(
            independent_output / "complete.json"
        ),
        "runtime_s": runtime_s,
        "time_budget_passed": runtime_s <= budget_s,
        "figures": figures,
        "human_stop": True,
        "next_stage": "N3_NOT_RUN_REQUIRES_SEPARATE_AUTHORIZATION",
        "forbidden_stage_status": {stage: "NOT_RUN" for stage in protocol["forbidden_before_later_authorization"]},
    }
    if not passed:
        complete["repair_code"] = "N2_FINAL_AUDIT_RECOMPUTE_TIME_OR_REPLAY_FAILED"
    _write_json(output / "complete.json", complete)
    return complete


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=["N0", "N1", "N2"])
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--run-tag", required=True)
    args = parser.parse_args()
    global PROJECT
    PROJECT = Path(args.project_root).resolve()
    protocol_path = Path(args.protocol).resolve()
    protocol = _read_json(protocol_path)
    validate_protocol(protocol)
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[key] = str(protocol["threads"][key])
    expected_root = PROJECT / Path(protocol["source_root"])
    if ROOT.resolve() != expected_root.resolve():
        raise RuntimeError(f"source root mismatch: {ROOT} != {expected_root}")
    results_root = PROJECT / Path(protocol["results_root"])
    if args.stage == "N0" and not results_root.exists():
        results_root.mkdir(parents=True)
        (results_root / "work_log.md").write_text("# Koopman ICR Next 工作记录\n", encoding="utf-8")
        (results_root / "solutions.md").write_text("# Koopman ICR Next 失败与解决方案\n", encoding="utf-8")
    if not results_root.exists():
        raise RuntimeError(f"results root missing before {args.stage}: {results_root}")
    _require_previous(results_root, args.stage, protocol_path)
    run_root = _run_root(results_root, args.stage, args.run_tag)
    output = run_root / args.stage.lower()
    try:
        result = {
            "N0": run_n0,
            "N1": run_n1,
            "N2": run_n2,
        }[args.stage](protocol_path, protocol, run_root)
        result.setdefault(
            "forbidden_stage_status",
            {
                stage: "NOT_RUN"
                for stage in protocol["forbidden_before_later_authorization"]
            },
        )
        _write_json(output / "complete.json", result)
        _update_status(results_root, args.stage, output, result)
        _append_log(results_root, args.stage, "stage_complete", str(result["stage_status"]), result)
        if not result.get("passed"):
            _append_solution(results_root, args.stage, str(result.get("repair_code", "UNKNOWN")), result)
        print(json.dumps(_json_safe(result), ensure_ascii=False, allow_nan=False), flush=True)
        raise SystemExit(0 if result.get("passed") else 2)
    except Exception:
        output.mkdir(parents=True, exist_ok=True)
        failure = {
            "stage": args.stage,
            "stage_status": "BLOCKED",
            "passed": False,
            "repair_code": f"{args.stage}_UNHANDLED_EXCEPTION",
            "traceback": traceback.format_exc(),
            "human_stop": True,
            "forbidden_stage_status": {
                stage: "NOT_RUN"
                for stage in protocol["forbidden_before_later_authorization"]
            },
        }
        _write_json(output / "failure.json", failure)
        _write_json(output / "complete.json", failure)
        _update_status(results_root, args.stage, output, failure)
        _append_log(results_root, args.stage, "unhandled_exception", "BLOCKED", failure)
        _append_solution(results_root, args.stage, failure["repair_code"], failure)
        print(json.dumps(_json_safe(failure), ensure_ascii=False, allow_nan=False), flush=True)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
