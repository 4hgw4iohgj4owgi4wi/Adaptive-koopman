"""Paired blind-confirm statistics for the frozen external A candidates."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "universal_v2"
if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))
import universal_v2_modules as m  # noqa: E402


def per_trajectory(model, rows, norms, basis, prior, seconds):
    baseline, adaptive = {}, {}
    task_ids = sorted({int(row["meta"]["task_id"]) for row in rows})
    biases = {task: m.task_bias(model, rows, norms, task, seconds) for task in task_ids}
    projected = {task: basis @ (basis.T @ bias) / (1.0 + prior) for task, bias in biases.items()}
    first = int(5.0 / m.DT)
    for row in rows:
        a = row["arrays"]; task = int(row["meta"]["task_id"]); pred0=[]; pred1=[]; truth=[]
        for start in range(first, len(a["u1_four"]) - m.H + 1, m.H):
            xn, fn = m.rollout(model, a, start); p0=np.c_[xn,fn]
            tx=(a["s3_deform"][start+1:start+m.H+1]-norms["x_mean"])/norms["x_std"]
            tf=(a["force_output"][start+1:start+m.H+1]-norms["force_mean"])/norms["force_std"]
            pred0.append(p0); pred1.append(p0+projected[task]); truth.append(np.c_[tx,tf])
        key=str(row["meta"]["file"]); target=np.asarray(truth)
        baseline[key]=m.metric_y(np.asarray(pred0),target)["J_pred"]
        adaptive[key]=m.metric_y(np.asarray(pred1),target)["J_pred"]
    return baseline, adaptive


def main():
    target=OUT/"t7"/"external_adaptation_statistics.json"
    if target.exists(): print(target); return
    _,norms,_,models=m.context(); rows=m.load_d2_rows("external")
    adev=json.loads((OUT/"t5"/"adaptation_results.json").read_text(encoding="utf-8"))
    stats={}
    for name in m.amend_g2():
        with np.load(OUT/"t5"/f"A-{name}.npz",allow_pickle=False) as source:
            basis=np.asarray(source["basis"]);prior=float(source["prior"])
        condition=adev[name]["best_adaptive_condition"]
        seconds=float(condition.split("-")[1][:-1]) if condition.startswith("A1-") else 1.0
        base,cand=per_trajectory(models[name],rows,norms,basis,prior,seconds)
        result=m.paired_bootstrap(base,cand); result["condition"]=condition
        stats[name]=result
        print(name,result,flush=True)
    tests=sorted((value["bootstrap_p"],name) for name,value in stats.items());running=0.0;count=len(tests)
    for index,(p,name) in enumerate(tests):
        running=max(running,min(1.0,(count-index)*p));stats[name]["holm_p"]=running
        stats[name]["statistical_gate"]=(stats[name]["mean_improvement"]>=.08 and stats[name]["ci95_low"]>0 and running<.05)
    m.write_json(target,stats)
    gates_path=OUT/"universality_gates.json"; initial=OUT/"universality_gates_initial.json"
    if not initial.exists(): shutil.copy2(gates_path,initial)
    gates=json.loads(gates_path.read_text(encoding="utf-8")); gates["external_adaptation_candidates_mean_only"]=gates.get("external_adaptation_candidates",[])
    gates["external_adaptation_candidates"]=[name for name,value in stats.items() if value["statistical_gate"]]
    gates["external_adaptation_statistics_sha256"]=m.uv2.sha256(target)
    m.write_json(gates_path,gates)
    m.write_json(OUT/"t7"/"complete_reaudited.json",{"status":"complete","external_statistical_candidates":gates["external_adaptation_candidates"],
                 "statistics_sha256":m.uv2.sha256(target),"gates_sha256":m.uv2.sha256(gates_path)})
    m.uv2.append_log("W0072","D2 external A配对统计复核",[
        f"对冻结D2 external按24条轨迹做10000次配对bootstrap并对4骨干Holm校正；通过={gates['external_adaptation_candidates']}。",
        f"统计hash={m.uv2.sha256(target)}；保留初始均值门文件universality_gates_initial.json。",
        "未修改模型、候选、D2数据或超参数；只补齐预注册统计判定。",
    ])

if __name__=="__main__":main()
