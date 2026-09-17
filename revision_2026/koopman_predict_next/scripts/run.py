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


AUTHORIZED = ("F0", "F1", "F2", "F3")
ALL_STAGES = AUTHORIZED + ("F4", "K0", "K1", "K2", "K3", "K4", "K5", "K6", "K7", "C0")


def append_work_log(
    path: Path,
    run_id: str,
    stage: str,
    identity: dict,
    complete: dict,
    command: list[str],
) -> None:
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")
    status = "PASS" if complete.get("passed") else "BLOCKED"
    lines = [
        f"## {run_id} — {timestamp} — {stage}",
        "",
        f"- 请求/任务编号：`koopman_run.md / {stage}`",
        "- 授权模式：执行实验（本轮仅 F0→F3）",
        f"- 机器与项目根目录：`{os.environ.get('COMPUTERNAME', '')}` / `{complete.get('project_root', '')}`",
        f"- 基线身份：source `{identity['source_manifest_sha256']}`；protocol `{identity['protocol_sha256']}`",
        f"- 输入：`{complete.get('input_data', '')}`",
        f"- 读取：`{complete.get('read_summary', '')}`",
        f"- 修改：`{complete.get('modification_summary', '')}`",
        f"- 命令：`{' '.join(command)}`",
        f"- 退出码：{0 if complete.get('passed') else 2}",
        f"- 原始产物：`{complete.get('run_dir', '')}`",
        f"- 关键结果：`{json.dumps(complete.get('key_results', {}), ensure_ascii=False)}`",
        "- 结论类型：事实（由本阶段落盘证据支持）",
        f"- 状态：{status}",
        f"- 停止原因：{complete.get('repair_code', '本阶段通过；服从任务书阶段边界')}",
        f"- 下一允许动作：{complete.get('next_action', '')}",
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
    current_index = ALL_STAGES.index(stage)
    for later in ALL_STAGES[current_index + 1 :]:
        if not passed or later not in payload["stages"]:
            payload["stages"][later] = {
                "status": "NOT_RUN",
                "run_id": None,
                "run_dir": None,
                "stop_reason": (
                    f"{stage}_BLOCKED" if not passed else f"{stage}_AWAITING_GATE_OR_AUTHORIZATION"
                ),
            }
    write_json(path, payload)


def append_failure_solution(path: Path, stage: str, run_id: str, complete: dict) -> None:
    existed = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        if not existed:
            stream.write("# Koopman-focus 阻塞问题与解决方案\n\n")
        stream.write(f"## {stage} 硬门失败 — {run_id}\n\n")
        stream.write(f"- 状态：BLOCKED\n- repair_code：`{complete.get('repair_code', 'UNKNOWN')}`\n")
        stream.write("- 已停止：当前阶段之后的全部阶段。\n")
        stream.write(f"- 现有证据：`{complete.get('run_dir', '')}`\n")
        stream.write(f"- 最小诊断：{complete.get('next_action', '检查失败证据。')}\n")
        stream.write("- 重入条件：在同一冻结输入上修复并通过当前硬门；禁止绕过。\n\n")


def stage_runner(stage: str):
    if stage == "F0":
        import freeze_focus

        return freeze_focus.run
    if stage == "F1":
        import run_f1_focus

        return run_f1_focus.run
    if stage == "F2":
        import run_f2_focus

        return run_f2_focus.run
    import run_f3_focus

    return run_f3_focus.run


def key_results(stage: str, complete: dict) -> dict:
    keys = {
        "F0": (
            "free_gib",
            "unknown_process_count",
            "seed_collision_count",
            "parent_raw_hash_mismatch_count",
        ),
        "F1": (
            "pytest_returncode",
            "trajectory_count",
            "geometry_residual_max_mps",
            "requested_recompute_error_max_mps",
            "actual_recompute_error_max_mps",
            "mirror_error_max_mps",
            "future_actual_fz_causal_digest_unchanged",
        ),
        "F2": (
            "support_contract_passed",
            "direction_contract_passed",
            "lift_detection_passed",
            "replay_relative_error_max",
        ),
        "F3": (
            "trajectory_count",
            "replay_count",
            "runtime_s",
            "time_budget_passed",
            "failed_gates",
            "tradeoff_review_count",
        ),
    }[stage]
    return {name: complete.get(name) for name in keys}


def default_next_action(stage: str, passed: bool) -> str:
    if not passed:
        return f"修复 {stage} 硬门后重跑；不得进入后续阶段。"
    if stage == "F0":
        return "执行 F1 三层 ICR、镜像与因果口径合同。"
    if stage == "F1":
        return "执行 F2 支承载荷解析验证与 L0 最小回放。"
    if stage == "F2":
        return "执行 F3 固定 24 轨迹、48 次确定性仿真。"
    return "在 F3 停止；独立审计后等待用户另行授权 F4。"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--stage", choices=AUTHORIZED, required=True)
    parser.add_argument("--run-tag", default="R01")
    parser.add_argument("--resume")
    args = parser.parse_args()

    project = args.project_root.resolve()
    protocol_path = args.protocol.resolve()
    results = project / "revision_2026" / "koopman_focus_results"
    runs = results / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    contract = RunContract(project, ROOT, results, protocol_path)
    protocol = contract.protocol
    if args.stage not in protocol["authorized_stages"]:
        raise SystemExit(f"stage outside protocol authorization: {args.stage}")
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
                "taskbook_sha256": protocol["taskbook_sha256"],
                "parent_taskbook_sha256": protocol["parent_taskbook_sha256"],
                "input_manifest_sha256": json_sha256({"stage": args.stage, "identity": identity}),
            },
        )

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            stage_complete = stage_runner(args.stage)(project, protocol, run_dir)
    except Exception as error:
        failure = run_dir / "failure"
        failure.mkdir(parents=True, exist_ok=True)
        (failure / "exception.txt").write_text(traceback.format_exc(), encoding="utf-8")
        stage_complete = {
            "stage": args.stage,
            "passed": False,
            "repair_code": "UNHANDLED_STAGE_EXCEPTION",
            "next_action": f"检查 {failure / 'exception.txt'}；不得运行后续阶段。",
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
            "input_data": "冻结的 parent-P2 24 条轨迹、冻结 connector_r3_4 与 focus 候选实现",
            "read_summary": "koopman_run.md、koopman_v2.md、parent-P2 evidence 与冻结物理源",
            "modification_summary": "仅写 koopman_focus/data/models/results；历史目录只读",
        }
    )
    complete["key_results"] = key_results(args.stage, complete)
    complete.setdefault("next_action", default_next_action(args.stage, bool(complete.get("passed"))))
    write_json(run_dir / "complete.json", complete)
    update_stage_status(results / "stage_status.json", run_id, args.stage, bool(complete.get("passed")), run_dir)
    command = [
        sys.executable,
        "-B",
        str(Path(__file__)),
        "--project-root",
        str(project),
        "--protocol",
        str(protocol_path),
        "--stage",
        args.stage,
        "--run-tag",
        args.run_tag,
    ]
    append_work_log(results / "work_log.md", run_id, args.stage, identity, complete, command)
    if not complete.get("passed"):
        append_failure_solution(results / "solutions.md", args.stage, run_id, complete)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "stage": args.stage,
                "passed": bool(complete.get("passed")),
                "run_dir": str(run_dir),
                "next_action": complete.get("next_action"),
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if complete.get("passed") else 2)


if __name__ == "__main__":
    main()
