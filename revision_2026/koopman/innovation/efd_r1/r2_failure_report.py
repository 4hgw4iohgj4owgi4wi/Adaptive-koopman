from __future__ import annotations
import json, time
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

import audit
from config import EFDR1Config


def main(project: Path) -> None:
    cfg = EFDR1Config(project); stage = cfg.results / "pilot"
    complete = json.loads((stage / "complete.json").read_text(encoding="utf-8"))
    audits = json.loads((stage / "audits.json").read_text(encoding="utf-8"))
    independent = [x for x in audits if x["independent_requested"]]
    seeds = [str(x["seed"]) for x in independent]
    p95 = [x["independent"]["overall"]["normalized_p95_max"] for x in independent]
    maxima = [x["independent"]["overall"]["normalized_max"] for x in independent]
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    pos = np.arange(len(seeds)); width = .38
    ax[0].bar(pos - width / 2, p95, width, label="worst field p95")
    ax[0].bar(pos + width / 2, maxima, width, label="worst field max")
    ax[0].axhline(1e-5, color="red", ls="--", label="frozen 1e-5 gate")
    ax[0].set_yscale("log"); ax[0].set_xticks(pos, seeds, rotation=35); ax[0].set_ylabel("normalized residual")
    ax[0].set_title("Independent mirror rollouts"); ax[0].legend(fontsize=8)
    passed = ["R0 freeze", "R1 contracts", "R2 generation", "R2 mirror gate", "R3 formal data"]
    values = [1, 1, 1, 0, 0]; colors = ["#70ad47", "#70ad47", "#70ad47", "#c00000", "#bfbfbf"]
    ax[1].barh(passed[::-1], values[::-1], color=colors[::-1]); ax[1].set_xlim(0, 1.05); ax[1].set_xlabel("passed / authorized")
    ax[1].set_title("R1 state machine stop")
    fig.suptitle(f"EFD-R1 R2 evidence stop | BASE=201000 | oracle max={complete['oracle_max_N']:.3g} N")
    fig.tight_layout(); figure = stage / "r2_mirror_failure.png"; fig.savefig(figure, dpi=180); plt.close(fig)

    frozen = json.loads((cfg.results / "freeze" / "old_readonly_snapshot.json").read_text(encoding="utf-8"))
    now = {
        "efd_code": audit.hash_tree(cfg.koopman / "innovation" / "efd", {"__pycache__"}),
        "efd_results": audit.hash_tree(cfg.koopman / "innovation_efd_results", {"__pycache__", "postmortem"}),
        "direction_code": audit.hash_tree(cfg.koopman / "innovation" / "direction", {"__pycache__"}),
        "direction_results": audit.hash_tree(cfg.koopman / "innovation_direction_results", {"__pycache__"}),
    }
    changed = {k: sorted(x for x in set(frozen[k]) | set(now[k]) if frozen[k].get(x) != now[k].get(x)) for k in frozen}
    readonly = {"passed": not any(changed.values()), "changed": changed}; (cfg.results / "audits").mkdir(parents=True, exist_ok=True)
    (cfg.results / "audits" / "old_readonly_after_r2.json").write_text(json.dumps(readonly, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failure = {"stage": "R2 independent mirror gate", "passed": False, "blocked": ["R3", "R4", "R5", "R6", "R7", "R8", "R9 model claims", "R10"],
               "base_trajectories": 16, "analytic_mirrors": 16, "independent_rollouts": 8,
               "independent_pass_count": sum(x["independent_passed"] for x in independent),
               "failed_seeds": [{"seed": x["seed"], "p95": x["independent"]["overall"]["normalized_p95_max"],
                                 "max": x["independent"]["overall"]["normalized_max"]} for x in independent if not x["independent_passed"]],
               "oracle_max_N": complete["oracle_max_N"], "finite_ultimate_gate": complete["finite_ultimate_gate"],
               "development_read": False, "confirm_generated": False, "old_readonly": readonly, "figure": str(figure)}
    (cfg.results / "failure.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = f"""# EFD-R1 R2停止报告

## 结论

R0与R1通过；R2完成16条base、16个解析镜像和8次镜像初态/控制独立积分，但独立镜像门仅{failure['independent_pass_count']}/8通过。按冻结任务书停止，未生成R3正式数据，未读取development，未生成confirm。

## 已核实事实

- BASE=201000无碰撞；H2/K1和协议hash匹配。
- 相对特征旋转误差≤1.78e-15；Reynolds交换子=0；轴向本构oracle最大误差={complete['oracle_max_N']:.9g} N。
- 解析镜像数组残差为0；plant首帧微分交换子为0。
- 实际state64/control64开环重放原轨迹，在最终第3103步仍逐元素一致。
- 独立镜像失败seed为{failure['failed_seeds']}；最坏p95={complete['independent_worst_p95']:.9g}，最坏max={complete['independent_worst_max']:.9g}，冻结门为1e-5。
- 失败集中于长程staged_100m，表明极小浮点求和顺序差异被刚性连接长时放大；这不等于物理方程不对称，但当前数值仿真证据不满足预注册门。

## 禁止的处理

不得每步把镜像解投影回base解、不得放宽1e-5门、不得忽略失败seed、不得继续生成R3。

## 恢复方案

1. 新立R1.1，将“局部积分器等变（单步/固定短窗）”和“长时成对轨迹误差”分为两个预注册指标；成本中等，必须使用新pilot seed。
2. 修改plant为顺序无关/对称求和或更高精度积分，更新plant hash并从R0完整重跑；成本高，且方法声明变为包含数值积分器修订。
3. 保持当前plant，承认独立长时镜像门过严并关闭R1；不产生主方法证据。
"""
    (cfg.results / "report.md").write_text(report, encoding="utf-8")
    with (cfg.results / "work_log.md").open("a", encoding="utf-8") as h:
        h.write(f"\n## R10004 R2失败归因与停止\n\n- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n- failure={json.dumps(failure, ensure_ascii=False)}\n- derivative commutator=0；base state64/control64 replay最终逐元素一致\n- 未放宽门限；R3及以后未启动\n- 旧目录只读={readonly['passed']}\n- 回滚：仅删除innovation/efd_r1与innovation_efd_r1_results，不影响旧实验\n")
    with (cfg.results / "solutions.md").open("a", encoding="utf-8") as h:
        h.write(f"\n## R2独立长时镜像仿真未通过\n\n### 事实\n\n- {failure}\n\n### 最可能原因与替代解释\n\n- 最可能：长程刚性连接动力学放大由角点求和顺序引入的浮点舍入差异。\n- 替代解释：仍存在未记录的求解器状态；但原轨迹精确开环重放和首帧微分交换子为0使其可能性较低。\n\n### 修复方案与成本\n\n- R1.1分离局部等变与长时轨迹门（中等，需新seed）；或修改对称/高精度积分器并重冻plant（高）。\n- 禁止每步镜像投影、放宽门或删除失败seed。\n\n### 论文影响与恢复条件\n\n当前不能声称严格镜像仿真通过，不能训练R1主模型。新协议冻结且新pilot通过前停止。\n")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("--project-root", type=Path, required=True); a = p.parse_args(); main(a.project_root.resolve())
