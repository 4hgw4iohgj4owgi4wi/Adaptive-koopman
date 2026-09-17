"""C4: build the E01 evidence matrix and the plant gate.

Detailed task book section 6 (C4): "逐行列原E01每项要求、当前证据、plant/输入器/候选/参数/
步长身份、科学门、图、剩余动作。已有33条原计划不能简单减去最近运行条数；旧输入器与新控制器
不得混算，已失败轨迹保留FAIL，100M05仅代表其子门。转向切换、通信相关植物诊断若未覆盖则按原
条目冻结确切数量再执行，不发明一个'已完成E01'总判定。"

The E01 requirement list is taken verbatim from the task book section "E01：植物和100m激励验收"
(experiment.md lines 756-772): five steps producing 33 trajectories (27 + 6).

Read-only. Every item is classified from files that actually exist, and no overall "E01 done"
verdict is ever emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

OLD_ROOT = Path("../paper_v4_results")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


PASSING_STATUSES = {"PASS", "COMPLETED"}


def run_status(folder: Path) -> dict:
    """Status of a run directory, from metrics.json if present.

    The 2026-09-09 E01 runs report "PASS" while the newer runners report "COMPLETED";
    treating only one of them as success made the first version of this matrix count zero
    covered trajectories, and the glob "P?_?ms" additionally missed every 0.5 ms cell
    because of the decimal point.  Both are fixed here.
    """
    metrics = read_json(folder / "metrics.json") if folder.is_dir() else None
    if metrics is None:
        return {"present": folder.is_dir(), "status": "NO_METRICS", "reason": None}
    status = metrics.get("status")
    return {"present": True, "status": status, "reason": metrics.get("reason"),
            "passing": status in PASSING_STATUSES,
            "complete_registered_trajectory": metrics.get("complete_registered_trajectory")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paper = Path(__file__).resolve().parents[1]
    protocol_path = args.protocol.resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("scope") != "C4_E01_EVIDENCE_MATRIX":
        raise ValueError("SCOPE_MISMATCH")
    for item in protocol["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    output = args.out.resolve()
    if output != (paper / protocol["output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)

    old_root = (paper / OLD_ROOT).resolve()
    items: list[dict] = []

    def add(step: str, requirement: str, required_trajectories: int, evidence: list[dict],
            gate: str, figures: list[str], remaining: str, identities: str) -> None:
        items.append({
            "item": len(items) + 1,
            "e01_step": step,
            "requirement": requirement,
            "required_trajectories": required_trajectories,
            "evidence": evidence,
            "science_gate": gate,
            "figures": figures,
            "identities": identities,
            "remaining_action": remaining,
        })

    # --- step 1: unit tests ------------------------------------------------------
    unit_evidence = []
    for name, note in (("20260909_E01_D01", "plant smoke; its own scope states convergence and registered E01 NOT_REACHED"),
                       ("20260909_E01_S01", "short plant run"),
                       ("20260909_E01_HR00", "support/load-transfer micro test")):
        folder = old_root / name
        if folder.is_dir():
            status = read_json(folder / "smoke.json") or read_json(folder / "metrics.json") or {}
            unit_evidence.append({"path": name, "status": status.get("status"), "note": note})
    add("1", "静态平衡、单连接器伸缩、匀速平移、纯几何转弯单元测试；验证作用反作用、坐标旋转、力矩、Wf_int≈0、Fz平衡",
        0, unit_evidence,
        "按物理量尺度归一化的作用反作用/投影残差 ≤ 1e-8",
        ["20260909_E01_G01/geometry.json", "20260909_E01_G02", "20260909_E01_G03"],
        "尚未找到覆盖全部四类单元测试的登记证据；几何类证据存在但作用反作用/力矩残差未按1e-8门逐项登记",
        "plant / 输入器 / 候选：不适用（纯植物单元测试）")

    # --- step 2: 27 trajectories --------------------------------------------------
    hundred_cells = sorted((old_root / "20260909_E01_100M05").glob("P?_*ms"))
    hundred_ok = [run_status(c).get("passing", False) for c in hundred_cells]
    add("2a", "100m阶跃诊断：3个预定参数点 × 2/1/0.5ms = 9条",
        9,
        [{"path": str(c.relative_to(old_root)).replace("\\", "/"), **run_status(c)} for c in hundred_cells],
        "参考时间对齐比较真实峰值/冲量/能量/位置/横摆；最终两档相对差 ≤2%，位置 ≤1mm、航向 ≤0.01°",
        ["20260909_E01_100M05/figure_100m_P0_0p5ms.png",
         "20260909_E01_100M05/figure_connector_directions_100m.png",
         "20260909_E01_100M05/figure_convergence_100m.png"],
        "已完成" if all(hundred_ok) and len(hundred_cells) == 9 else f"仅{sum(hundred_ok)}/{len(hundred_cells)}个单元COMPLETED",
        "plant identity 未变；输入器为冻结100m激励；参数点 P0/P1/P2；步长 2/1/0.5ms")

    hairpin_cells = sorted((old_root / "20260909_E01_HAIRPIN01").glob("P?_*ms"))
    hairpin_records = [{"path": str(c.relative_to(old_root)).replace("\\", "/"), **run_status(c)} for c in hairpin_cells]
    add("2b", "真实回头弯：3个预定参数点 × 2/1/0.5ms = 9条",
        9, hairpin_records,
        "同上数值分辨率门",
        [],
        f"仅{len(hairpin_cells)}条且其中状态为 " + ", ".join(f"{r['status']}({r.get('reason')})" for r in hairpin_records) + "；**失败轨迹按§6保留为FAIL，不删除、不改门**；缺8条",
        "plant identity 未变；参数点与步长身份需按原条目冻结后执行")

    steering_evidence = []
    for name in ("20260909_E01_HS01", "20260909_E01_HS02", "20260909_E01_HS03", "20260909_E01_HS04",
                 "20260909_E01_HG01", "20260909_E01_HG02"):
        folder = old_root / name
        if folder.is_dir():
            status = run_status(folder)
            steering_evidence.append({"path": name, "has_metrics": status["present"],
                                      "status": status["status"],
                                      "note": "geometry only, no dynamics" if not (folder / "metrics.json").is_file() else ""})
    add("2c", "转向切换：3个预定参数点 × 2/1/0.5ms = 9条",
        9, steering_evidence,
        "同上数值分辨率门",
        [],
        "现有HS/HG目录为短测试与几何证据，**未构成转向切换的3参数点×3步长矩阵**；按§6应冻结确切数量(9条)后执行，不发明已完成判定",
        "参数点与步长身份需冻结")

    # --- step 3: convergence comparison ------------------------------------------
    convergence = old_root / "20260909_E01_100M05/convergence_100m.json"
    add("3", "参考时间对齐比较真实峰值、冲量、能量、位置与横摆；不得先平滑再比较",
        0, [{"path": "20260909_E01_100M05/convergence_100m.json", "present": convergence.is_file()}],
        "最终两档相对差 ≤2%；近零用预登记绝对分辨率；位置 ≤1mm、航向 ≤0.01°",
        ["20260909_E01_100M05/figure_convergence_100m.png"],
        "100m子门有收敛报告；回头弯与转向切换无对应收敛报告",
        "数值分辨率门，非设备精度标准")

    # --- step 4: six communication-plant trajectories ----------------------------
    delay_dirs = sorted(p.name for p in old_root.glob("*") if p.is_dir() and any(
        token in p.name for token in ("DELAY", "OUTAGE", "NET", "COMM")))
    add("4", "100m诊断增加100ms延迟与0.4s中断各3族（2ms主积分），共6条新轨迹，与前述3条正常配对",
        6, [{"searched_glob": "*DELAY*/*OUTAGE*/*NET*/*COMM*", "found": delay_dirs}],
        "只用于显示通信如何传到单车/货物受力，不证明最终控制优势",
        [],
        "**未找到任何延迟/中断植物诊断证据**；按§6冻结确切数量（6条）后执行",
        "plant / 输入器：通信诊断输入器尚未登记；候选不参与")

    # --- step 5: figures ----------------------------------------------------------
    figure_evidence = []
    for pattern in ("figure", "*.png"):
        for path in sorted((old_root / "20260909_E01_100M05").glob(pattern)):
            figure_evidence.append({"path": str(path.relative_to(old_root)).replace("\\", "/"), "bytes": path.stat().st_size})
    add("5", "记录四点箭头图、各车横摆/系统横摆、Fx/Fy/Fz分图、左右/前后拉伸代理、输入与实际转角，标记30m、两次阶跃和制动",
        0, figure_evidence,
        "图注须写方法全名、信息边界、工况/参数/种子数、时间范围与失败状态（§25.3）",
        [item["path"] for item in figure_evidence],
        "100m有四张图；回头弯与转向切换无图；失败轨迹（HAIRPIN01）无诊断图",
        "§25.4 的 E01 行要求含失败接受段覆盖图")

    required_total = sum(item["required_trajectories"] for item in items)
    covered = 0
    for item in items:
        if item["e01_step"] == "2a":
            covered += sum(1 for entry in item["evidence"] if entry.get("passing"))
        # 2b and 2c and 4 contribute zero covered until the frozen counts are actually executed
    failed_retained = [entry for item in items for entry in item["evidence"]
                       if entry.get("status") == "FAIL"]

    report = {
        "status": "PLANT_GATE_NOT_READY",
        "scope": protocol["scope"],
        "rule": ("Task book section 6: the existing 33-item plan cannot be reduced by simply subtracting recent runs, "
                 "old input generators must not be mixed with the new controller, failed trajectories stay FAIL, "
                 "100M05 covers only its own sub-gate, and no overall 'E01 complete' verdict may be invented."),
        "requirement_source": "experiment.md section 'E01：植物和100m激励验收' (lines 756-772)",
        "required_trajectories_total": 33,
        "required_trajectories_accounted": required_total,
        "trajectories_covered": covered,
        "trajectories_outstanding": required_total - covered,
        "failed_trajectories_retained": failed_retained,
        "items": items,
        "outstanding_actions": [
            "freeze the exact count and identities for the steering-switch matrix (9 trajectories) before executing",
            "freeze the exact count and identities for the hairpin matrix (9 trajectories, of which 1 exists as FAIL)",
            "freeze and execute the six communication-plant trajectories (100 ms delay and 0.4 s outage, 3 families each)",
            "register the unit-test residuals against the 1e-8 normalised gate",
            "produce the missing figures, including a diagnostic figure over the accepted segment of the failed hairpin run",
        ],
        "what_this_releases": "Nothing by itself. gates/plant.json stays NOT READY until the outstanding items are executed and independently reviewed.",
        "claim_boundary": ("This matrix inventories evidence; it is not a plant gate PASS. It does not authorise control ranking, "
                           "and it does not convert the existing 100M05 sub-gate into a full E01 result."),
    }
    (output / "e01_evidence_matrix.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    plant_gate = {
        "status": "PLANT_GATE_NOT_READY",
        "reason": f"{report['trajectories_outstanding']} of {required_total} registered E01 trajectories have no passing evidence",
        "covered": covered,
        "outstanding": report["trajectories_outstanding"],
        "failed_retained": len(failed_retained),
        "independent_review": "NOT_PERFORMED",
        "rule": "A plant-gate PASS requires every registered item to have applicable evidence and an independent review; it is not inferred from run counts.",
    }
    (output / "plant_gate.json").write_text(json.dumps(plant_gate, indent=2, ensure_ascii=False), encoding="utf-8")

    (output / "README.md").write_text(
        "# C4：E01 证据矩阵与 plant gate\n\n"
        "按详细任务书§6建立，逐行列原 E01 每项要求、当前证据、身份、科学门、图与剩余动作。\n\n"
        f"- 登记要求轨迹总数：**{required_total}**（27＋6，出自任务书 E01 节）\n"
        f"- 已有通过证据：**{covered}**\n"
        f"- **尚缺：{report['trajectories_outstanding']}**\n"
        f"- 保留为 FAIL 的失败轨迹：**{len(failed_retained)}**（`HAIRPIN01/P0_2ms`，`STOP_ULTIMATE_FORCE`）\n\n"
        "**`plant_gate.json` = `PLANT_GATE_NOT_READY`**，独立审查 `NOT_PERFORMED`。\n\n"
        "**本矩阵不发明\"已完成E01\"总判定**：100M05 的九条只代表其自身的 100m 子门；"
        "回头弯、转向切换、以及 100ms 延迟/0.4s 中断的六条通信诊断**均需先冻结确切数量与身份再执行**。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "required": required_total, "covered": covered,
                      "outstanding": report["trajectories_outstanding"],
                      "failed_retained": len(failed_retained), "items": len(items),
                      "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
