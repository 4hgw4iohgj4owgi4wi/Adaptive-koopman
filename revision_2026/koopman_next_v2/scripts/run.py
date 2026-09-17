from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from contracts import RunContract, json_sha256, write_json


def append_work_log(path: Path, run_id: str, stage: str, identity: dict, complete: dict, command: list[str]) -> None:
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")
    status = "PASS" if complete.get("passed") else "BLOCKED"
    lines = [
        f"## {run_id} — {timestamp} — {stage} execution",
        "",
        "- 请求/任务编号：`koopman_v2.md / {}`".format(stage),
        "- 授权模式：执行实验",
        f"- 机器与项目根目录：`{os.environ.get('COMPUTERNAME', '')}` / `{complete.get('project_root', '')}`",
        f"- 阶段：`{stage}`",
        f"- 基线身份：source manifest `{identity['source_manifest_sha256']}`；protocol `{identity['protocol_sha256']}`",
        f"- 输入数据/manifest：`{complete.get('input_data', 'upstream freeze inputs')}`",
        f"- 读取：`{complete.get('read_summary', 'see input_manifest.json')}`",
        f"- 修改：`{complete.get('modification_summary', 'isolated koopman_next stage outputs only')}`",
        f"- 命令：`{' '.join(command)}`",
        f"- 退出码：{0 if complete.get('passed') else 2}",
        f"- 原始产物：`{complete.get('run_dir', '')}`",
        f"- 关键结果（单位、样本范围、统计口径）：`{json.dumps(complete.get('key_results', {}), ensure_ascii=False)}`",
        f"- 结论类型：事实",
        f"- 状态：{status}",
        f"- 停止原因：{complete.get('repair_code', '无硬门失败；按任务书阶段边界停止')}",
        f"- 下一允许动作：{complete.get('next_action', '等待下一阶段授权')}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n".join(lines))


def update_stage_status(path: Path, run_id: str, stage: str, passed: bool, run_dir: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {"stages": {}}
    payload.setdefault("stages", {})[stage] = {
        "status": "PASS" if passed else "BLOCKED",
        "run_id": run_id,
        "run_dir": str(run_dir),
        "updated_at": datetime.now().astimezone().isoformat(),
    }
    ordered = ["P0", "P1", "P2", "P2S", "P3", "D0", "D1"] + [
        f"M{index}" for index in range(10)
    ]
    current_index = ordered.index(stage)
    for later in ordered[current_index + 1 :]:
        if not passed or later not in payload["stages"]:
            payload["stages"][later] = {
                "status": "NOT_RUN",
                "run_id": None,
                "run_dir": None,
                "stop_reason": f"{stage}_{'BLOCKED' if not passed else 'AWAITING_GATE_OR_AUTHORIZATION'}",
            }
    write_json(path, payload)


def append_failure_solution(path: Path, stage: str, run_id: str, complete: dict) -> None:
    existed = path.exists()
    with path.open("a", encoding="utf-8") as stream:
        if not existed:
            stream.write("# Koopman v2阻塞问题解决方案\n\n")
        stream.write(f"## {stage} hard-gate failure — {run_id}\n\n")
        stream.write(f"- 状态：BLOCKED\n- repair_code：`{complete.get('repair_code', 'UNKNOWN')}`\n")
        stream.write("- 已停止：任务树中当前阶段之后的全部阶段。\n")
        stream.write(f"- 现有证据：`{complete.get('run_dir', '')}`\n")
        stream.write(f"- 最小诊断：{complete.get('next_action', 'Inspect failure artifacts.')}\n")
        stream.write("- 重新进入门槛：修正当前硬门并用相同冻结输入完成最小复验；不得绕过。\n\n")


def write_deferred_limitations(path: Path, limitations_path: Path, run_id: str) -> None:
    limitations = json.loads(limitations_path.read_text(encoding="utf-8"))
    lines = [
        f"## K1后当前无法由代码合同直接修正的问题 — {run_id}",
        "",
        "K0/K1没有硬门失败。以下问题不是继续调K1代码能够解决的，而是需要新数据或后续独立实验；在解决前禁止启动复杂模型训练。",
        "",
    ]
    for entry in limitations["items"]:
        lines.extend(
            [
                f"### {entry['code']}",
                "",
                f"- 已确认事实：{entry['fact']}",
                f"- 我认为的原因：{entry['cause']}",
                f"- 功能影响：{entry['impact']}",
                f"- 最低成本解决方案：{entry['minimum_resolution']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 当前推荐决定",
            "",
            "保持F23只作为接口证据；下一次若授权，先执行K2数据pilot和不重叠事件窗覆盖审计。K2通过前，不训练lift、门控、双线性、物理解码残差或稳定证书模块。",
            "",
        ]
    )
    existed = path.exists()
    with path.open("a", encoding="utf-8") as stream:
        if not existed:
            stream.write("# Koopman-next problems and solutions\n\n")
        stream.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--stage", choices=("P0", "P1", "P2"), required=True)
    parser.add_argument("--run-tag", default="R01")
    parser.add_argument("--resume")
    args = parser.parse_args()
    project = args.project_root.resolve()
    protocol_path = args.protocol.resolve()
    results = project / "revision_2026" / "koopman_next_v2_results"
    runs = results / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    contract = RunContract(project, ROOT, results, protocol_path)
    protocol = contract.protocol
    contract.require_previous(args.stage)
    identity = contract.input_identity()
    if args.resume:
        run_id = args.resume
        run_dir = runs / run_id
        stored = json.loads((run_dir / "input_manifest.json").read_text(encoding="utf-8"))
        if stored["stage"] != args.stage or stored["identity"] != identity:
            raise SystemExit("resume identity mismatch")
    else:
        timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        run_id = f"{timestamp}_{args.stage}_{args.run_tag}"
        run_dir = runs / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        write_json(run_dir / "resolved_config.json", protocol)
        write_json(
            run_dir / "input_manifest.json",
            {
                "stage": args.stage,
                "identity": identity,
                "expected_upstream_sha256": protocol["expected_upstream_sha256"],
                "input_manifest_sha256": json_sha256(
                    {"stage": args.stage, "identity": identity, "upstream": protocol["expected_upstream_sha256"]}
                ),
            },
        )
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            if args.stage == "P0":
                import freeze_v2

                stage_complete = freeze_v2.run(project, protocol, run_dir)
            elif args.stage == "P1":
                import run_p1

                stage_complete = run_p1.run(project, protocol, run_dir)
            else:
                import run_p2

                stage_complete = run_p2.run(project, protocol, run_dir)
    except Exception as error:  # preserve complete failure evidence
        failure = run_dir / "failure"
        failure.mkdir(parents=True, exist_ok=True)
        (failure / "exception.txt").write_text(traceback.format_exc(), encoding="utf-8")
        stage_complete = {
            "stage": args.stage,
            "passed": False,
            "repair_code": "UNHANDLED_STAGE_EXCEPTION",
            "next_action": f"Inspect {failure / 'exception.txt'}; do not run later stages.",
            "exception": repr(error),
        }
    (run_dir / "stdout.txt").write_text(stdout_buffer.getvalue(), encoding="utf-8")
    (run_dir / "stderr.txt").write_text(stderr_buffer.getvalue(), encoding="utf-8")
    complete = dict(stage_complete)
    complete.update(
        {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "project_root": str(project),
            "stage": args.stage,
            "protocol_sha256": identity["protocol_sha256"],
            "source_manifest_sha256": identity["source_manifest_sha256"],
            "input_data": (
                "synthetic actuator and causal-schema contracts"
                if args.stage == "P1"
                else (
                    "fixed 12-family D2 A0/A1 paired isolation"
                    if args.stage == "P2"
                    else "frozen source, evidence, environment, parameters and seeds"
                )
            ),
            "read_summary": "historical K2-R06 evidence, frozen connector_r3_4, and isolated koopman_next_v2 source",
            "modification_summary": "new isolated v2 stage outputs; historical koopman_next and connector_r3_4 remain read-only",
        }
    )
    if args.stage == "P0":
        complete["key_results"] = {
            "hash_mismatches": complete.get("upstream_hash_mismatch_count"),
            "unknown_processes": complete.get("unknown_process_count"),
            "seed_collisions": complete.get("seed_collision_count"),
            "free_gib": complete.get("free_gib"),
        }
        complete.setdefault(
            "next_action",
            "Run P1 actuator and v4 causal contracts only." if complete.get("passed") else "Repair P0 before P1.",
        )
    elif args.stage == "P1":
        complete["key_results"] = {
            "pytest_returncode": complete.get("pytest_returncode"),
            "angle_violation_rad": complete.get("angle_violation_rad"),
            "rate_violation_radps": complete.get("rate_violation_radps"),
            "mirror_error_rad": complete.get("mirror_error_rad"),
            "schema_v4_passed": complete.get("schema_v4_passed"),
        }
        complete.setdefault(
            "next_action",
            "Run the authorized fixed 12-case P2 A0/A1 isolation only; P2S and training remain forbidden."
            if complete.get("passed")
            else "Repair P1 before P2.",
        )
    else:
        complete["key_results"] = {
            "trajectory_count": complete.get("trajectory_count"),
            "candidate_failed_trajectory_count": complete.get("candidate_failed_trajectory_count"),
            "candidate_tire_failed_trajectory_count": complete.get("candidate_tire_failed_trajectory_count"),
            "candidate_tire_raw_utilization_min": complete.get("candidate_tire_raw_utilization_min"),
            "candidate_tire_raw_utilization_max": complete.get("candidate_tire_raw_utilization_max"),
            "replay_mismatch_count": complete.get("replay_mismatch_count"),
            "candidate_max_actual_rate_radps": complete.get("candidate_max_actual_rate_radps"),
            "candidate_requested_icr_residual_max_mps": complete.get("candidate_requested_icr_residual_max_mps"),
        }
        complete.setdefault(
            "next_action",
            "Stop after P2; independently review raw evidence before separately authorizing P2S."
            if complete.get("passed")
            else "Stop at P2 and write the prescribed secondary physical diagnosis; P2S and training remain forbidden.",
        )
    write_json(run_dir / "complete.json", complete)
    update_stage_status(results / "stage_status.json", run_id, args.stage, bool(complete.get("passed")), run_dir)
    command = [sys.executable, "-B", str(Path(__file__)), "--project-root", str(project), "--protocol", str(protocol_path), "--stage", args.stage, "--run-tag", args.run_tag]
    append_work_log(results / "work_log.md", run_id, args.stage, identity, complete, command)
    if not complete.get("passed"):
        append_failure_solution(results / "solutions.md", args.stage, run_id, complete)
    print(json.dumps({"run_id": run_id, "stage": args.stage, "passed": bool(complete.get("passed")), "run_dir": str(run_dir), "next_action": complete.get("next_action")}, ensure_ascii=False))
    raise SystemExit(0 if complete.get("passed") else 2)


if __name__ == "__main__":
    main()
