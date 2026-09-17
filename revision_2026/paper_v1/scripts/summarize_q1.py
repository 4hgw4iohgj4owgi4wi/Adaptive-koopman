from __future__ import annotations

import argparse, csv, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path, rows):
    if not rows:
        raise ValueError("refuse empty table")
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--run",required=True);args=ap.parse_args()
    run=Path(args.run).resolve(); verdict=read(run/"formal_verdict.json")
    folds=verdict["folds"]; pooled=verdict["pooled"]; pressure=verdict["pressure40"]
    if len(folds)!=90 or len(pooled)!=18 or len(pressure)!=90:
        raise ValueError(f"incomplete verdict {len(folds)}/{len(pooled)}/{len(pressure)}")
    quality=list((run/"outer").rglob("quality.json"));pred=list((run/"outer").rglob("predictions.npz"))
    if len(quality)!=90 or len(pred)!=90:
        raise ValueError("raw candidate matrix incomplete")
    selected=verdict["nomination"]
    key=(selected["method"],bool(selected["calibrated"]))
    sf=[r for r in folds if (r["method"],bool(r["calibrated"]))==key]
    sp=[r for r in pooled if (r["method"],bool(r["calibrated"]))==key]
    spr=[r for r in pressure if (r["method"],bool(r["calibrated"]))==key]
    if len(sf)!=15 or len(sp)!=3 or len(spr)!=15: raise ValueError("selected matrix incomplete")
    guard_names={7:"D1 加速—匀速—制动，1步综合J",11:"D2 100米正反转向，1步综合J"}
    failure_rows=[];counts=Counter()
    for r in sf:
        bad=[g["name"] for g in r["rows"] if not g["passed"]]
        for name in bad:
            idx=int(name.rsplit("_",1)[1]) if name.startswith("training_guard_") else -1
            counts[guard_names.get(idx,name)]+=1
        failure_rows.append({"repeat":r["repeat"],"fold":r["fold"],"i20_percent":r["i20"],
            "quality_pass":r["passed"],"failed_gate_count":len(bad),"failed_gates":";".join(bad)})
    summary_rows=[]
    for r in pooled:
        matching=[x for x in folds if x["method"]==r["method"] and bool(x["calibrated"])==bool(r["calibrated"]) and x["repeat"]==r["repeat"]]
        summary_rows.append({"method":r["method"],"calibrated":bool(r["calibrated"]),"repeat":r["repeat"],
            "pooled_i20_percent":r["i20"],"positive_folds":r["positive_folds"],"pooled_quality_pass":r["passed"],
            "fold_quality_pass_count":sum(bool(x["passed"]) for x in matching),
            "fold_i20_min_percent":min(x["i20"] for x in matching),
            "fold_i20_max_percent":max(x["i20"] for x in matching)})
    gate_rows=[{"gate":k,"failed_selected_fold_units":v,"denominator":15} for k,v in counts.most_common()]
    # Independent critical-number recomputation from saved arrays, not verdict summary fields.
    max_i20_diff=0.0
    for r in folds:
        folder=run/f"outer/fold{r['fold']}/repeat{r['repeat']}/{r['method']}/{int(bool(r['calibrated']))}"
        with np.load(run/f"outer/fold{r['fold']}/pure11.npz",allow_pickle=False) as b, np.load(folder/"predictions.npz",allow_pickle=False) as c:
            base=float(b["stats"][:,3,0].mean()); cand=float(c["stats"][:,3,0].mean())
        value=100*(base-cand)/max(base,1e-12)
        max_i20_diff=max(max_i20_diff,abs(value-float(r["i20"])))
    fail_unit=next(r for r in sf if not r["passed"])
    fail_folder=run/f"outer/fold{fail_unit['fold']}/repeat{fail_unit['repeat']}/{fail_unit['method']}/{int(bool(fail_unit['calibrated']))}"
    with np.load(run/f"outer/fold{fail_unit['fold']}/pure11.npz",allow_pickle=False) as b, np.load(fail_folder/"predictions.npz",allow_pickle=False) as c:
        bstats=b["stats"];cstats=c["stats"]
        critical=[]
        for scenario,label in ((1,guard_names[7]),(2,guard_names[11])):
            bv=float(bstats[scenario,0,0]);cv=float(cstats[scenario,0,0]);deg=100*(cv-bv)/max(bv,.02)
            critical.append({"metric":label,"baseline_J":bv,"candidate_J":cv,"degradation_percent":deg,"limit_percent":3.0,"excess_percentage_points":deg-3.0})
    ci=verdict["paired_family_ci95"]
    machine={"passed":False,"status":"NEGATIVE_RESULT","evidence_complete":True,
      "candidate_states":90,"quality_files":len(quality),"prediction_files":len(pred),"pressure_units":len(pressure),
      "selected":selected,"selected_fold_quality_pass_count":sum(bool(r["passed"]) for r in sf),
      "selected_pooled_quality_pass_count":sum(bool(r["passed"]) for r in sp),
      "selected_pooled_i20_percent":[r["i20"] for r in sp],
      "selected_positive_folds":[r["positive_folds"] for r in sp],
      "paired_family_ci95_percent":ci,"new_40step_divergence_count":sum(bool(r["new_divergence"]) for r in spr),
      "raw_recompute_max_abs_i20_difference":max_i20_diff,"critical_failed_metrics":critical,
      "latency_status":"NOT_RUN_BY_PROTOCOL_AFTER_SCIENCE_FAIL",
      "downstream":"K2/K3/C0/C1/B0/N0/A0/E0 NOT_RUN"}
    write_json(run/"q1_summary.json",machine);write_csv(run/"candidate_summary.csv",summary_rows)
    write_csv(run/"selected_fold_failures.csv",failure_rows);write_csv(run/"selected_gate_failure_counts.csv",gate_rows)
    try:
        import matplotlib;matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["font.sans-serif"]=["Microsoft YaHei","SimHei","DejaVu Sans"]
        fig,axes=plt.subplots(1,2,figsize=(12,4.8))
        methods=["aligned","fixed_guard","adaptive_guard"]
        xpos=np.arange(len(methods));width=.36
        for j,cal in enumerate((False,True)):
            vals=[];lo=[];hi=[]
            for m in methods:
                rr=[x["pooled_i20_percent"] for x in summary_rows if x["method"]==m and x["calibrated"]==cal]
                vals.append(float(np.mean(rr)));lo.append(float(np.min(rr)));hi.append(float(np.max(rr)))
            axes[0].bar(xpos+(j-.5)*width,vals,width,label="校准" if cal else "原始")
            axes[0].errorbar(xpos+(j-.5)*width,vals,yerr=[np.array(vals)-lo,np.array(hi)-vals],fmt="none",color="black",capsize=3)
        axes[0].axhline(5,color="red",ls="--",label="5%收益门");axes[0].set_xticks(xpos,methods)
        axes[0].set_ylabel("20步综合误差改善（%）");axes[0].set_title("三方法三初始化合并结果");axes[0].legend();axes[0].grid(axis="y",alpha=.2)
        top=gate_rows[:10];axes[1].barh([x["gate"] for x in top][::-1],[x["failed_selected_fold_units"] for x in top][::-1])
        axes[1].set_xlabel("失败单元数 / 15");axes[1].set_title("提名方法未通过的主要保护门");axes[1].grid(axis="x",alpha=.2)
        fig.tight_layout();fig.savefig(run/"q1_diagnosis.png",dpi=180);fig.savefig(run/"q1_diagnosis.pdf");plt.close(fig)
    except Exception as exc:
        (run/"figure_error.txt").write_text(repr(exc),encoding="utf-8")
    lines=["# Q1冻结预测实验结论","", "## 结论","",
      "Q1证据完整，但科学门未通过，状态为 **NEGATIVE_RESULT**。不得进入Q2预测部署、MPC或网络主实验。","",
      "## 可核实事实","",
      f"- 90/90候选状态均有quality与predictions；40步压力记录90项。",
      f"- 提名：`{key[0]}`，calibrated=`{key[1]}`。15个fold×repeat单元中完整质量门通过 {machine['selected_fold_quality_pass_count']}/15。",
      f"- 三个repeat合并20步改善：{', '.join(f'{x:.6f}%' for x in machine['selected_pooled_i20_percent'])}；对应正改善fold数：{machine['selected_positive_folds']}。",
      f"- 按family配对bootstrap 95%CI：[{ci[0]:.6f}%, {ci[1]:.6f}%]，说明平均20步收益为正；但它不能覆盖短期、逐工况、力/内力和回头弯尾部保护失败。",
      f"- 唯一失败单元是repeat 1/fold 0：D1一步J退化{critical[0]['degradation_percent']:.6f}%（上限3%），D2一步J退化{critical[1]['degradation_percent']:.6f}%（上限3%）。",
      f"- 从90份原始NPZ独立复算20步改善，与verdict最大绝对差{max_i20_diff:.3e}个百分点。",
      f"- 新增40步数值发散：{machine['new_40step_divergence_count']}/15（提名状态）。",
      "- 按协议，科学门失败后没有执行latency；这不是实时性通过或失败证据。","",
      "## 独立判断","",
      "平均20步误差确有改善，但当前候选不是可部署的全域改进：它没有同时满足预注册的短期、逐工况、受力和困难回头弯保护。不能用正CI替代完整K1门，也不能只挑改善工况进入控制实验。","",
      "## 后续","",
      "保持K2/K3/C0/C1/B0/N0/A0/E0为NOT_RUN。允许独立完成T0旧公式反例、W0来源审计或撰写负结果归因；若要继续改学习器，须另立任务书版本、开发数据与新确认集，不得把本outer重新称为盲测。","",
      "详细表：`candidate_summary.csv`、`selected_fold_failures.csv`、`selected_gate_failure_counts.csv`。"]
    (run/"q1_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    sol=["# Q1阻塞问题解决方案","","## 阻塞点","",
      "- 任务编号：K1/Q1。","- 失败状态：NEGATIVE_RESULT，退出码20。","- 已停止：K2、K3以及全部控制和网络部署链。","",
      "## 已确认事实","",f"- 证据矩阵完整：90/90；提名状态质量门通过{machine['selected_fold_quality_pass_count']}/15。",
      f"- 20步配对CI为[{ci[0]:.6f}%, {ci[1]:.6f}%]，但完整保护门失败。","- 40步没有新增数值发散。","",
      "## 根因候选与最小诊断","",
      "| 候选 | 支持证据 | 反对证据 | 最小诊断 |","|---|---|---|---|",
      "| 多步平均目标牺牲局部保护 | 平均20步明显改善而多个完整门失败 | 尚未按失败门分解梯度/样本 | 用已保存预测按门、工况、时域做误差贡献分解，不训练 |",
      "| 全局gamma无法兼顾各fold/工况 | 每单元固定gamma且保护结果分散 | 不能据此自动引入门控 | 比较原始/校准同checkpoint的成对失败迁移 |",
      "| 状态误差改善未转化为力/内力改善 | 保护门包含力、内力和尾部 | 需按具体失败项确认 | 对失败单元关联状态分组误差与力读出雅可比 |","",
      "## 可选方案","",
      "| 方案 | 修改范围 | 预期收益 | 风险 | 进入条件 |","|---|---|---|---|---|",
      "| A：接受负结果并精简论文 | 不再训练 | 避免继续投入无证据方法 | Koopman贡献缩小 | 当前即可；推荐 |",
      "| B：新版本做受约束多目标学习 | 新任务书、新开发集、新确认集 | 可能改善受力/尾部保护 | 成本高且可能仍失败 | 先完成只读失败归因并预注册，不读取旧outer调后仍称盲测 |",
      "| C：仅在预登记局部工况报告 | 不改模型，只重述范围 | 保留局部有效发现 | 不能支撑全域/控制部署 | 必须证明该局部范围不是看结果后挑选 |","",
      "## 推荐方案","","先执行A，并完成只读失败归因。除非用户明确接受新一轮数据与训练成本，否则不进入B。不得放宽3%/5%门、删工况或直接把该模型送入MPC。"]
    (run/"solutions_detailed.md").write_text("\n".join(sol)+"\n",encoding="utf-8")
    print(json.dumps(machine,ensure_ascii=False,indent=2))


if __name__=="__main__": main()
