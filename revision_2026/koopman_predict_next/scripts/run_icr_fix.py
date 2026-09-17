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
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: object) -> None:
    def scalar_default(item: object) -> object:
        if hasattr(item, "item"):
            return item.item()
        raise TypeError(f"Object of type {item.__class__.__name__} is not JSON serializable")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
            default=scalar_default,
        ),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refuse to write empty CSV: {path}")
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _append_log(results_root: Path, stage: str, message: str, status: str, artifacts: list[str]) -> None:
    path = results_root / "work_log.md"
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n## {stamp} — {stage} — {status}\n\n"
            f"- 操作：{message}\n"
            f"- 产物：{'; '.join(artifacts) if artifacts else '无'}\n"
            f"- 结论类型：实测事实（仅限本阶段与冻结配置）。\n"
        )


def _append_solution(results_root: Path, stage: str, code: str, details: dict) -> None:
    path = results_root / "solutions.md"
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n## {stamp} — {stage}: {code}\n\n"
            "- 根因候选：见下方保存的首个确定失败现场；当前不得将候选当作已证实根因。\n"
            "- 反证要求：使用同一协议、seed、线程、调用路径复现，并只改变一个诊断变量。\n"
            "- 最小诊断：定位首个不同字段/首个失败门，检查端点、dt、模式和配置 SHA。\n"
            "- 允许处理：只修隔离导入、诊断、模式开关或确定的实现错误；禁止改 D2 命令、物理门槛或删回放。\n"
            "- 代价：修复后 I0 身份失效，必须重新 I0，再重新进入 I1。\n"
            "- 重新进入门槛：新 I0 PASS，且本失败对应的最小复现 PASS。\n"
            f"- 现场：`{json.dumps(details, ensure_ascii=False, default=str)}`\n"
        )


def _source_identity(root: Path) -> tuple[dict, str]:
    sys.path.insert(0, str(ROOT / "src"))
    from contracts import json_sha256, source_manifest

    manifest = source_manifest(root)
    return manifest, json_sha256(manifest)


def _process_snapshot() -> list[dict]:
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object {$_.Name -match '^(python|matlab)(.exe)?$'} | "
        "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Depth 3"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    if not completed.stdout.strip():
        return []
    value = json.loads(completed.stdout)
    return value if isinstance(value, list) else [value]


def _load_npz(path: Path) -> dict:
    import numpy as np

    with np.load(path, allow_pickle=False) as source:
        return {key: source[key].copy() for key in source.files}


def _thread_identity_probe(protocol_path: Path, output: Path, protocol: dict) -> dict:
    import numpy as np

    worker = ROOT / "scripts" / "thread_probe_worker.py"
    default_path = output / "thread_probe_default.npz"
    single_path = output / "thread_probe_single.npz"
    base_env = os.environ.copy()
    for key in protocol["threads"]:
        if key in {"OMP_NUM_THREADS", "MKL_NUM_THREADS"}:
            base_env.pop(key, None)
    single_env = base_env.copy()
    single_env.update(
        {
            "OMP_NUM_THREADS": protocol["threads"]["OMP_NUM_THREADS"],
            "MKL_NUM_THREADS": protocol["threads"]["MKL_NUM_THREADS"],
        }
    )
    commands = []
    for label, path, env in (
        ("default", default_path, base_env),
        ("single", single_path, single_env),
    ):
        command = [
            sys.executable,
            str(worker),
            "--protocol",
            str(protocol_path),
            "--output",
            str(path),
        ]
        completed = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=600
        )
        commands.append(
            {
                "label": label,
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
        if completed.returncode != 0:
            return {"passed": False, "commands": commands, "reason": f"{label}_worker_failed"}
    default = _load_npz(default_path)
    single = _load_npz(single_path)
    first = None
    maximum = 0.0
    for key in sorted(set(default) | set(single)):
        if key not in default or key not in single:
            first = {"field": key, "reason": "key_set"}
            maximum = float("1e300")
            break
        left, right = np.asarray(default[key]), np.asarray(single[key])
        if left.shape != right.shape:
            first = {"field": key, "reason": "shape"}
            maximum = float("1e300")
            break
        if left.dtype.kind in {"U", "S", "O"}:
            error = 0.0 if np.array_equal(left.astype(str), right.astype(str)) else float("1e300")
        else:
            error = float(np.max(np.abs(left.astype(float) - right.astype(float)))) if left.size else 0.0
        maximum = max(maximum, error)
        if error > 0.0 and first is None:
            first = {"field": key, "max_abs": error}
    return {
        "passed": maximum <= float(protocol["threads"]["identity_max_abs"]),
        "max_abs": maximum,
        "first_different": first,
        "commands": commands,
        "frozen_environment": {
            "OMP_NUM_THREADS": single_env["OMP_NUM_THREADS"],
            "MKL_NUM_THREADS": single_env["MKL_NUM_THREADS"],
        },
    }


def run_i0(protocol_path: Path, protocol: dict, run_root: Path, results_root: Path) -> dict:
    started = time.perf_counter()
    output = run_root / "i0"
    output.mkdir(parents=True, exist_ok=False)
    sys.path[:0] = [str(ROOT / "src")]
    import numpy as np
    import scipy
    import torch
    from contracts import sha256
    from data_manifest import file_sha256

    processes = _process_snapshot()
    unknown = [row for row in processes if int(row.get("ProcessId", -1)) != os.getpid()]
    disk = shutil.disk_usage(PROJECT)
    environment = {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "python_executable": sys.executable,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "cuda_runtime": torch.version.cuda,
        "disk_free_gib": disk.free / 1024**3,
        "git_repository": (PROJECT / ".git").exists(),
        "python_matlab_processes": processes,
        "unknown_python_matlab_processes": unknown,
        "thread_environment": {
            key: os.environ.get(key) for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS")
        },
    }
    _write_json(output / "environment.json", environment)

    parent_root = PROJECT / Path(protocol["parent_source_root"])
    parent_manifest, parent_source_sha = _source_identity(parent_root)
    own_manifest, own_source_sha = _source_identity(ROOT)
    source_identity = {
        "parent_source_manifest_sha256": parent_source_sha,
        "parent_source_expected_sha256": protocol["parent_source_manifest_sha256"],
        "parent_source_passed": parent_source_sha == protocol["parent_source_manifest_sha256"],
        "icr_source_manifest": own_manifest,
        "icr_source_manifest_sha256": own_source_sha,
    }
    _write_json(output / "source_identity.json", source_identity)

    parent = protocol["parent_f3"]
    parent_run = PROJECT / Path(parent["run_root"])
    parent_manifest_path = parent_run / Path(parent["manifest_relpath"])
    with parent_manifest_path.open("r", newline="", encoding="utf-8-sig") as stream:
        manifest_rows = list(csv.DictReader(stream))
    raw_root = PROJECT / Path(parent["data_root"])
    raw_checks = []
    for row in manifest_rows:
        path = raw_root / Path(row["raw_path"]).name
        actual = file_sha256(path) if path.exists() else None
        raw_checks.append(
            {
                "trajectory_id": int(row["trajectory_id"]),
                "path": str(path),
                "expected_sha256": row["raw_file_sha256"],
                "actual_sha256": actual,
                "passed": actual == row["raw_file_sha256"],
            }
        )
    parent_evidence = {
        "manifest_path": str(parent_manifest_path),
        "manifest_expected_sha256": parent["manifest_sha256"],
        "manifest_actual_sha256": sha256(parent_manifest_path),
        "manifest_count": len(manifest_rows),
        "raw_checks": raw_checks,
        "passed": sha256(parent_manifest_path) == parent["manifest_sha256"]
        and len(manifest_rows) == int(parent["expected_trajectory_count"])
        and all(item["passed"] for item in raw_checks),
    }
    _write_json(output / "parent_f3_identity.json", parent_evidence)

    taskbook_sha = sha256(ROOT / "protocol.md")
    parent_taskbook_sha = sha256(ROOT / "parent_protocol.md")
    shutil.copy2(ROOT / "protocol.md", output / "protocol_snapshot.md")
    shutil.copy2(ROOT / "parent_protocol.md", output / "parent_protocol_snapshot.md")
    thread_probe = _thread_identity_probe(protocol_path, output, protocol)
    _write_json(output / "thread_identity_probe.json", thread_probe)

    test_env = os.environ.copy()
    test_env["KOOPMAN_PROJECT_ROOT"] = str(PROJECT)
    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
        env=test_env,
    )
    (output / "pytest.txt").write_text(
        test.stdout + "\n--- STDERR ---\n" + test.stderr, encoding="utf-8"
    )
    passed = bool(
        environment["hostname"].upper() == protocol["project_host"].upper()
        and environment["cuda_available"]
        and "RTX 5080" in str(environment["gpu"])
        and environment["disk_free_gib"] >= float(protocol["resource_limits"]["minimum_free_gib"])
        and not unknown
        and not environment["git_repository"]
        and environment["thread_environment"]
        == {
            "OMP_NUM_THREADS": protocol["threads"]["OMP_NUM_THREADS"],
            "MKL_NUM_THREADS": protocol["threads"]["MKL_NUM_THREADS"],
        }
        and parent_evidence["passed"]
        and source_identity["parent_source_passed"]
        and taskbook_sha == protocol["taskbook_sha256"]
        and parent_taskbook_sha == protocol["parent_taskbook_sha256"]
        and thread_probe["passed"]
        and test.returncode == 0
    )
    complete = {
        "stage": "I0",
        "passed": passed,
        "protocol_sha256": sha256(protocol_path),
        "source_manifest_sha256": own_source_sha,
        "taskbook_sha256": taskbook_sha,
        "parent_taskbook_sha256": parent_taskbook_sha,
        "parent_source_manifest_sha256": parent_source_sha,
        "parent_f3_manifest_sha256": parent_evidence["manifest_actual_sha256"],
        "parent_f3_raw_count": len(raw_checks),
        "parent_f3_raw_mismatch_count": sum(not item["passed"] for item in raw_checks),
        "unknown_process_count": len(unknown),
        "thread_identity_max_abs": thread_probe.get("max_abs"),
        "pytest_returncode": test.returncode,
        "runtime_s": time.perf_counter() - started,
        "next_stage": "I1" if passed else "NOT_RUN",
    }
    if not passed:
        complete.update(
            {
                "repair_code": "I0_IDENTITY_ENVIRONMENT_THREAD_OR_TEST_FAILED",
                "next_action": "Inspect I0 artifacts; I1 and all later stages remain NOT_RUN.",
            }
        )
    _write_json(output / "complete.json", complete)
    return complete


def _residual_metrics(values, phases, protocol: dict) -> dict:
    import numpy as np
    from audit_icr_fix import recovery_times
    from icr_metrics import summarize_residual

    threshold = float(protocol["f3"]["diagnostic_icr_threshold_mps"])
    stats = summarize_residual(np.asarray(values, dtype=float), threshold)
    return {
        "peak_mps": stats["peak_mps"],
        "p95_mps": stats["p95_mps"],
        "rms_mps": stats["rms_mps"],
        "fraction_gt_0p5": stats["fraction_above_threshold"],
        "recovery_s": json.dumps(
            recovery_times(values, phases, float(protocol["k2"]["model_step_s"]), threshold)
        ),
    }


def _offline_request_attribution(protocol: dict, output: Path) -> dict:
    import numpy as np
    from generate_data import resolved_params
    from icr_metrics import icr_steering_residual
    from steering_allocator import request_variants

    parent = protocol["parent_f3"]
    manifest_path = PROJECT / Path(parent["run_root"]) / Path(parent["manifest_relpath"])
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as stream:
        manifest = list(csv.DictReader(stream))
    raw_root = PROJECT / Path(parent["data_root"])
    rows: list[dict] = []
    switching_rows: list[dict] = []
    g0_max = 0.0
    g2_max_diff = 0.0
    example = None
    dt = float(protocol["k2"]["model_step_s"])
    window_count = int(round(float(protocol["f3"]["switching_window_s"]) / dt))
    for manifest_row in manifest:
        raw_path = raw_root / Path(manifest_row["raw_path"]).name
        arrays = _load_npz(raw_path)
        params = resolved_params(int(manifest_row["seed"]), protocol)
        wheelbase = float(params.vehicle.lf_m + params.vehicle.lr_m)
        layer_values = {layer: [] for layer in ("G0", "G1", "G2")}
        maximum_request_difference = 0.0
        for index in range(len(arrays["time_s"])):
            state = arrays["initial_state30"] if index == 0 else arrays["state30"][index - 1]
            variants = request_variants(
                state,
                float(arrays["virtual_front_deg"][index]),
                float(arrays["virtual_rear_deg"][index]),
                params,
            )
            for layer, key in (("G0", "g0"), ("G1", "g1"), ("G2", "g2")):
                residual = icr_steering_residual(
                    variants["speed_mps"],
                    float(variants["yaw_rate_radps"]),
                    wheelbase,
                    variants[f"{key}_steering_rad"],
                )
                layer_values[layer].append(float(residual["max_abs_mps"]))
            maximum_request_difference = max(
                maximum_request_difference,
                float(
                    np.max(
                        np.abs(
                            variants["g2_steering_rad"]
                            - arrays["requested_control4x2"][index, :, 1]
                        )
                    )
                ),
            )
        layer_values = {key: np.asarray(value) for key, value in layer_values.items()}
        metrics = {
            layer: _residual_metrics(values, arrays["command_phase"], protocol)
            for layer, values in layer_values.items()
        }
        identity = {
            key: manifest_row[key]
            for key in (
                "trajectory_id", "base_family_id", "split", "seed", "direction", "plant", "law", "load_mode"
            )
        }
        for layer in ("G0", "G1", "G2"):
            row = {**identity, "layer": layer, **metrics[layer]}
            for metric in ("peak_mps", "p95_mps", "rms_mps", "fraction_gt_0p5"):
                row[f"delta_feedback_{metric}"] = (
                    metrics["G1"][metric] - metrics["G0"][metric]
                )
                row[f"delta_clip_{metric}"] = metrics["G2"][metric] - metrics["G1"][metric]
            row["g2_parent_request_max_abs_rad"] = maximum_request_difference
            rows.append(row)
        phase = np.asarray(arrays["command_phase"]).astype(str)
        starts = [
            index
            for index in range(1, len(phase))
            if phase[index] != phase[index - 1]
            and phase[index] in {"STEP_PRIMARY", "STEP_REVERSE", "DECEL"}
        ]
        for switch_number, start in enumerate(starts, start=1):
            stop = min(start + window_count, len(phase))
            switch_metrics = {
                layer: _residual_metrics(values[start:stop], phase[start:stop], protocol)
                for layer, values in layer_values.items()
            }
            for layer in ("G0", "G1", "G2"):
                threshold = float(protocol["f3"]["diagnostic_icr_threshold_mps"])
                found = next(
                    (
                        index
                        for index in range(start, len(layer_values[layer]))
                        if abs(layer_values[layer][index]) <= threshold
                    ),
                    None,
                )
                item = {
                    **identity,
                    "switch_number": switch_number,
                    "phase": phase[start],
                    "start_time_s": float(arrays["time_s"][start]),
                    "window_s": float(protocol["f3"]["switching_window_s"]),
                    "layer": layer,
                    "recovery_s_from_switch": None
                    if found is None
                    else float((found - start) * dt),
                    **switch_metrics[layer],
                }
                for metric in ("peak_mps", "p95_mps", "rms_mps", "fraction_gt_0p5"):
                    item[f"delta_feedback_{metric}"] = switch_metrics["G1"][metric] - switch_metrics["G0"][metric]
                    item[f"delta_clip_{metric}"] = switch_metrics["G2"][metric] - switch_metrics["G1"][metric]
                switching_rows.append(item)
        g0_max = max(g0_max, float(np.max(layer_values["G0"])))
        g2_max_diff = max(g2_max_diff, maximum_request_difference)
        if (
            manifest_row["seed"] == str(protocol["i1"]["seed"])
            and manifest_row["direction"] == "left"
            and manifest_row["plant"] == "V1-ES"
            and manifest_row["load_mode"] == "L1"
        ):
            example = {
                "time_s": arrays["time_s"],
                "g0": layer_values["G0"],
                "g1": layer_values["G1"],
                "g2": layer_values["G2"],
            }
    _write_csv(output / "request_attribution.csv", rows)
    _write_csv(output / "request_switching_attribution.csv", switching_rows)
    passed = bool(
        len(manifest) == int(parent["expected_trajectory_count"])
        and g0_max <= float(protocol["f3"]["geometry_residual_atol_mps"])
        and g2_max_diff <= float(protocol["f3"]["g2_parent_request_atol_rad"])
        and example is not None
    )
    result = {
        "passed": passed,
        "parent_trajectory_count": len(manifest),
        "attribution_row_count": len(rows),
        "switching_row_count": len(switching_rows),
        "g0_peak_max_mps": g0_max,
        "g2_parent_request_max_abs_rad": g2_max_diff,
        "example": example,
    }
    serializable = {key: value for key, value in result.items() if key != "example"}
    _write_json(output / "request_attribution_summary.json", serializable)
    return result


def _simulate_job(job: dict) -> dict:
    started = time.perf_counter()
    try:
        root = Path(job["root"])
        sys.path[:0] = [str(root / "src"), str(root / "plant"), str(root / "scripts")]
        from data_manifest import array_sha256
        from generate_data import resolved_params, simulate_trajectory
        from scenarios import ScenarioSpec

        protocol = job["protocol"]
        identity = job["identity"]
        seed = int(identity["seed"])
        params = resolved_params(seed, protocol)
        spec = ScenarioSpec("D2", identity["direction"], None, 100.0, True)
        summary, arrays = simulate_trajectory(
            spec,
            identity["law"],
            seed,
            params,
            protocol,
            actuator_mode=identity["actuator_mode"],
            load_transfer_enabled=True,
        )
        replay_summary, replay_arrays = simulate_trajectory(
            spec,
            identity["law"],
            seed,
            params,
            protocol,
            actuator_mode=identity["actuator_mode"],
            load_transfer_enabled=True,
        )
        replay_hash = array_sha256(replay_arrays)
        return {
            "ok": True,
            "summary": summary,
            "arrays": arrays,
            "replay_summary": replay_summary,
            "replay_hash": replay_hash,
            "runtime_s": time.perf_counter() - started,
        }
    except Exception:
        return {"ok": False, "traceback": traceback.format_exc(), "runtime_s": time.perf_counter() - started}


def _jobs(protocol: dict) -> list[dict]:
    result = []
    trajectory_id = 0
    for direction in protocol["i1"]["directions"]:
        for plant in protocol["i1"]["plants"]:
            for mode in protocol["i1"]["actuator_modes"]:
                identity = {
                    "trajectory_id": trajectory_id,
                    "base_family_id": f"I1_D2_{protocol['i1']['seed']}",
                    "seed": int(protocol["i1"]["seed"]),
                    "scenario": "D2",
                    "direction": direction,
                    "plant": plant["name"],
                    "law": plant["law"],
                    "load_mode": "L1",
                    "load_transfer_enabled": True,
                    "actuator_mode": mode,
                }
                result.append({"root": str(ROOT), "protocol": protocol, "identity": identity})
                trajectory_id += 1
    # The frozen pilot measures an ideal and full actuator on the same plant/direction.
    pilots = [job for job in result if job["identity"]["direction"] == "left" and job["identity"]["plant"] == "V1-ES" and job["identity"]["actuator_mode"] in {"A0", "A3"}]
    remaining = [job for job in result if job not in pilots]
    return pilots + remaining


def _parent_seed_arrays(protocol: dict) -> dict[tuple[str, str], dict]:
    parent = protocol["parent_f3"]
    manifest_path = PROJECT / Path(parent["run_root"]) / Path(parent["manifest_relpath"])
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    raw_root = PROJECT / Path(parent["data_root"])
    output = {}
    for row in rows:
        if int(row["seed"]) == int(protocol["i1"]["seed"]) and row["load_mode"] == "L1":
            output[(row["direction"], row["plant"])] = _load_npz(raw_root / Path(row["raw_path"]).name)
    if len(output) != 4:
        raise RuntimeError(f"expected four parent A3 L1 trajectories, found {sorted(output)}")
    return output


def _save_simulation_result(
    job: dict,
    result: dict,
    output: Path,
    trajectories: list,
    manifest_rows: list[dict],
) -> Path:
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
    from data_manifest import file_sha256, params_sha256
    from generate_data import resolved_params, save_raw

    identity = dict(job["identity"])
    summary = result["summary"]
    replay_equal = bool(
        summary["trajectory_array_sha256"]
        == result["replay_summary"]["trajectory_array_sha256"]
        == result["replay_hash"]
    )
    identity["replay_hash_match"] = replay_equal
    stem = (
        f"trajectory_{identity['trajectory_id']:04d}_D2_{identity['direction']}_"
        f"{identity['plant']}_{identity['actuator_mode']}_L1"
    )
    raw_path = output / "raw" / f"{stem}.npz"
    params = resolved_params(int(identity["seed"]), job["protocol"])
    save_raw(raw_path, result["arrays"], summary, params)
    manifest_rows.append(
        {
            **identity,
            "params_sha256": params_sha256(params),
            "trajectory_array_sha256": summary["trajectory_array_sha256"],
            "raw_file_sha256": file_sha256(raw_path),
            "raw_path": str(raw_path),
            "sample_count": summary["sample_count"],
            "duration_s": summary["duration_s"],
            "distance_m": summary["distance_m"],
            "status": summary["status"],
            "first_runtime_s": summary["runtime_s"],
            "first_plus_replay_runtime_s": result["runtime_s"],
        }
    )
    trajectories.append((identity, result["arrays"], summary))
    return raw_path


def _write_i1_report(output: Path, audit: dict, request: dict, mode_rows: list[dict], runtime_s: float) -> None:
    import numpy as np

    lines = [
        "# I1 根因归因报告",
        "",
        "> 结论边界：以下是冻结 D2、L1、seed 910021 及父 F3 24 条请求层轨迹内的因果对照；不是控制器优越性或硬件标定结论。",
        "",
        "## 硬门结果",
        "",
        f"- I1：{'PASS' if audit['passed'] and request['passed'] else 'FAIL'}。",
        f"- G0 最大 ICR 残差：{request['g0_peak_max_mps']:.12g} m/s。",
        f"- G2 对父 F3 请求最大逐点差：{request['g2_parent_request_max_abs_rad']:.12g} rad。",
        f"- A3 对父 F3 公共字段最大逐点差：{audit['a3_parent_common_max_abs']:.12g}。",
        f"- 16 条首次运行 + 16 条回放总墙钟：{runtime_s:.3f} s（含离线归因/审计/绘图）。",
        "",
        "## A0–A3 汇总（四个方向/植物配对的均值）",
        "",
        "| 模式 | P95 实际 ICR (m/s) | 峰值跟踪误差 (rad) | 速率饱和占比 | 角度饱和占比 | 峰值连接力 (N) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mode in ("A0", "A1", "A2", "A3"):
        selected = [row for row in mode_rows if row["actuator_mode"] == mode]
        mean = lambda key: float(np.mean([float(row[key]) for row in selected]))
        lines.append(
            f"| {mode} | {mean('actual_icr_p95_mps'):.6g} | {mean('tracking_peak_rad'):.6g} | "
            f"{mean('rate_mask_fraction'):.6g} | {mean('angle_mask_fraction'):.6g} | {mean('connector_force_peak_n'):.6g} |"
        )
    lines += [
        "",
        "## 独立判断",
        "",
        "- 事实：请求层 G0/G1/G2 和执行器 A0–A3 已按逐层增量保存，正负增量均保留。",
        "- 推断：只能依据 `actuator_contributions.csv` 判断滞后、速率和角度约束在本工况中的相对贡献；不能把相关峰值直接解释为硬件因果。",
        "- 风险：执行器参数仍是可追溯仿真假设，不是 5080 或实车标定值。",
        "- 停止点：I2/C1/C2、F4 和 Koopman 训练保持 NOT_RUN，等待人工查看本报告后单独授权。",
    ]
    (output / "i1_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_i1(protocol_path: Path, protocol: dict, run_root: Path, results_root: Path) -> dict:
    started = time.perf_counter()
    output = run_root / "i1"
    output.mkdir(parents=True, exist_ok=False)
    (output / "raw").mkdir()
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "plant"), str(ROOT / "scripts")]
    from audit_icr_fix import audit_run, audit_trajectory
    from contracts import sha256

    request = _offline_request_attribution(protocol, output)
    if not request["passed"]:
        complete = {
            "stage": "I1",
            "passed": False,
            "repair_code": "I1_REQUEST_LAYER_HARD_GATE_FAILED",
            "request_summary": {key: value for key, value in request.items() if key != "example"},
            "runtime_s": time.perf_counter() - started,
            "human_stop": True,
        }
        _write_json(output / "complete.json", complete)
        return complete

    jobs = _jobs(protocol)
    pilot_count = int(protocol["resource_limits"]["pilot_trajectory_count"])
    if pilot_count != 2 or len(jobs) != 16:
        raise ValueError("frozen I1 matrix requires exactly 2 pilots and 16 trajectories")
    parents = _parent_seed_arrays(protocol)
    trajectories = []
    manifest_rows: list[dict] = []
    raw_paths: list[Path] = []
    pilot_runtimes = []
    for count, job in enumerate(jobs[:pilot_count], start=1):
        print(f"I1 pilot {count}/{pilot_count}: {job['identity']}", flush=True)
        result = _simulate_job(job)
        if not result["ok"]:
            _write_json(output / f"pilot_{count:02d}_failure.json", result)
            return {
                "stage": "I1", "passed": False, "repair_code": "I1_PILOT_EXCEPTION",
                "failure": result["traceback"], "runtime_s": time.perf_counter() - started, "human_stop": True,
            }
        raw_paths.append(_save_simulation_result(job, result, output, trajectories, manifest_rows))
        pilot_runtimes.append(float(result["runtime_s"]))
        identity, arrays, summary = trajectories[-1]
        comparison = None
        if identity["actuator_mode"] == "A3":
            from audit_icr_fix import compare_common_fields
            comparison = compare_common_fields(arrays, parents[(identity["direction"], identity["plant"])])
        pilot_audit = audit_trajectory(identity, arrays, summary, protocol, comparison)
        _write_json(output / f"pilot_{count:02d}_audit.json", pilot_audit)
        if not pilot_audit["passed"]:
            _write_csv(output / "data_manifest_partial.csv", manifest_rows)
            complete = {
                "stage": "I1", "passed": False, "repair_code": "I1_PILOT_HARD_GATE_FAILED",
                "failed_identity": identity, "pilot_audit": pilot_audit,
                "runtime_s": time.perf_counter() - started, "human_stop": True,
            }
            _write_json(output / "complete.json", complete)
            return complete

    workers = int(protocol["resource_limits"]["parallel_workers"])
    remaining_count = len(jobs) - pilot_count
    projected_s = sum(pilot_runtimes) + ((remaining_count + workers - 1) // workers) * max(pilot_runtimes)
    budget_s = 3600.0 * float(protocol["resource_limits"]["maximum_i1_hours"])
    timing = {
        "pilot_runtime_s": pilot_runtimes,
        "remaining_trajectory_count": remaining_count,
        "workers": workers,
        "projected_total_simulation_s": projected_s,
        "budget_s": budget_s,
        "passed": projected_s <= budget_s,
    }
    _write_json(output / "pilot_timing.json", timing)
    if not timing["passed"]:
        _write_csv(output / "data_manifest_partial.csv", manifest_rows)
        complete = {
            "stage": "I1", "passed": False, "repair_code": "I1_PROJECTED_TIME_BUDGET_EXCEEDED",
            "timing": timing, "runtime_s": time.perf_counter() - started, "human_stop": True,
        }
        _write_json(output / "complete.json", complete)
        return complete

    print(f"I1 submitted {remaining_count} first/replay jobs to {workers} workers", flush=True)
    failures = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = executor.map(_simulate_job, jobs[pilot_count:], chunksize=1)
        for offset, (job, result) in enumerate(zip(jobs[pilot_count:], results), start=1):
            if not result["ok"]:
                failure = {"identity": job["identity"], **result}
                failures.append(failure)
                _write_json(output / f"trajectory_failure_{job['identity']['trajectory_id']:04d}.json", failure)
                break
            raw_paths.append(_save_simulation_result(job, result, output, trajectories, manifest_rows))
            print(f"I1 completed {offset}/{remaining_count}: {job['identity']}", flush=True)
    if failures:
        _write_csv(output / "data_manifest_partial.csv", manifest_rows)
        complete = {
            "stage": "I1", "passed": False, "repair_code": "I1_TRAJECTORY_EXCEPTION",
            "completed_trajectory_count": len(trajectories), "failure": failures[0],
            "runtime_s": time.perf_counter() - started, "human_stop": True,
        }
        _write_json(output / "complete.json", complete)
        return complete
    if len(trajectories) != 16:
        raise RuntimeError(f"I1 matrix incomplete: {len(trajectories)} != 16")

    manifest_rows.sort(key=lambda row: int(row["trajectory_id"]))
    trajectories.sort(key=lambda item: int(item[0]["trajectory_id"]))
    _write_csv(output / "data_manifest.csv", manifest_rows)
    audit = audit_run(trajectories, protocol, parents, output)
    with (output / "actuator_attribution.csv").open("r", newline="", encoding="utf-8-sig") as stream:
        mode_rows = list(csv.DictReader(stream))
    from plot_icr_fix import plot_i1

    source_paths = raw_paths + [
        output / "request_attribution.csv",
        output / "request_switching_attribution.csv",
        output / "actuator_attribution.csv",
        output / "actuator_contributions.csv",
    ]
    figures = plot_i1(
        trajectories, request["example"], mode_rows, output, source_paths, protocol_path
    )
    runtime_s = time.perf_counter() - started
    replay_mismatch = sum(not bool(row["replay_hash_match"]) for row in manifest_rows)
    budget_passed = runtime_s <= budget_s
    passed = bool(audit["passed"] and request["passed"] and replay_mismatch == 0 and budget_passed)
    _write_i1_report(output, audit, request, mode_rows, runtime_s)
    complete = {
        "stage": "I1",
        "passed": passed,
        "protocol_sha256": sha256(protocol_path),
        "source_manifest_sha256": _source_identity(ROOT)[1],
        "trajectory_count": len(trajectories),
        "simulation_count": 2 * len(trajectories),
        "replay_mismatch_count": replay_mismatch,
        "request_attribution_passed": request["passed"],
        "g0_peak_max_mps": request["g0_peak_max_mps"],
        "g2_parent_request_max_abs_rad": request["g2_parent_request_max_abs_rad"],
        "a3_parent_common_max_abs": audit["a3_parent_common_max_abs"],
        "failed_gates": audit["failed_gates"],
        "runtime_s": runtime_s,
        "time_budget_passed": budget_passed,
        "pilot_timing": timing,
        "figures": figures,
        "human_stop": True,
        "next_stage": "I2_NOT_RUN_REQUIRES_SEPARATE_AUTHORIZATION",
        "forbidden_stage_status": {stage: "NOT_RUN" for stage in protocol["forbidden_before_next_authorization"]},
    }
    if not passed:
        complete.update(
            {
                "repair_code": "I1_" + ("_".join(audit["failed_gates"]).upper() if audit["failed_gates"] else "TIME_OR_REPLAY_FAILED"),
                "next_action": "Stop at I1; inspect first failed hard gate. I2 and all learning stages remain NOT_RUN.",
            }
        )
    _write_json(output / "complete.json", complete)
    return complete


def _next_run_root(results_root: Path, stage: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    runs = results_root / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    for revision in range(1, 100):
        path = runs / f"{stamp}_{stage}_R{revision:02d}"
        if not path.exists():
            path.mkdir()
            return path
    raise RuntimeError("cannot allocate unique run directory")


def _require_i0(protocol_path: Path, results_root: Path) -> dict:
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from contracts import sha256

    status_path = results_root / "stage_status.json"
    if not status_path.exists():
        raise RuntimeError("I1 requires I0 PASS; stage_status.json is missing")
    status = _json(status_path)
    prior = status.get("stages", {}).get("I0", {})
    if prior.get("status") != "PASS":
        raise RuntimeError(f"I1 requires I0 PASS, found {prior}")
    complete_path = Path(prior["run_dir"]) / "complete.json"
    complete = _json(complete_path)
    if not complete.get("passed"):
        raise RuntimeError("I0 complete.json does not pass")
    current_source_sha = _source_identity(ROOT)[1]
    if complete["source_manifest_sha256"] != current_source_sha:
        raise RuntimeError("source identity changed after I0; rerun I0")
    if complete["protocol_sha256"] != sha256(protocol_path):
        raise RuntimeError("protocol identity changed after I0; rerun I0")
    return complete


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True)
    parser.add_argument("--protocol", required=True)
    args = parser.parse_args()
    stage = args.stage.upper()
    protocol_path = Path(args.protocol).resolve()
    protocol = _json(protocol_path)
    if stage not in protocol["authorized_stages"] or stage not in {"I0", "I1"}:
        raise ValueError(f"stage is outside current authorization: {stage}")
    for key, value in protocol["threads"].items():
        if key in {"OMP_NUM_THREADS", "MKL_NUM_THREADS"}:
            os.environ[key] = str(value)
    results_root = PROJECT / Path(protocol["results_root"])
    results_root.mkdir(parents=True, exist_ok=True)
    (results_root / "solutions.md").touch(exist_ok=True)
    (results_root / "work_log.md").touch(exist_ok=True)
    if stage == "I1":
        _require_i0(protocol_path, results_root)
    run_root = _next_run_root(results_root, stage)
    result = None
    try:
        result = run_i0(protocol_path, protocol, run_root, results_root) if stage == "I0" else run_i1(protocol_path, protocol, run_root, results_root)
        output = run_root / stage.lower()
        if not (output / "complete.json").exists():
            _write_json(output / "complete.json", result)
        status = "PASS" if result.get("passed") else "BLOCKED"
        stage_status_path = results_root / "stage_status.json"
        current = _json(stage_status_path) if stage_status_path.exists() else {"stages": {}}
        current.setdefault("stages", {})[stage] = {
            "status": status,
            "run_dir": str(output),
            "complete": str(output / "complete.json"),
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        for forbidden in protocol["forbidden_before_next_authorization"]:
            current["stages"].setdefault(forbidden, {"status": "NOT_RUN"})
        current["human_stop_required"] = stage == "I1"
        _write_json(stage_status_path, current)
        _append_log(
            results_root,
            stage,
            "完成阶段调度、身份/门禁检查并落盘全部已生成证据。",
            status,
            [str(output / "complete.json"), str(stage_status_path)],
        )
        if not result.get("passed"):
            _append_solution(results_root, stage, result.get("repair_code", "UNKNOWN_FAILURE"), result)
        print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
        raise SystemExit(0 if result.get("passed") else 2)
    except Exception:
        failure = {
            "stage": stage,
            "passed": False,
            "repair_code": f"{stage}_UNHANDLED_EXCEPTION",
            "traceback": traceback.format_exc(),
            "human_stop": True,
        }
        output = run_root / stage.lower()
        output.mkdir(parents=True, exist_ok=True)
        _write_json(output / "failure.json", failure)
        _write_json(output / "complete.json", failure)
        _append_log(results_root, stage, "发生未处理异常并按硬门停止。", "BLOCKED", [str(output / "failure.json")])
        _append_solution(results_root, stage, failure["repair_code"], failure)
        print(json.dumps(failure, ensure_ascii=False), flush=True)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
