from __future__ import annotations

import csv,json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _read(path:Path)->dict[str,Any]: return json.loads(path.read_text(encoding="utf-8"))


def make_report(results:Path)->dict[str,Any]:
    figures=results/"figures"; figures.mkdir(parents=True,exist_ok=True)
    pilot=_read(results/"d4r"/"pilot"/"manifest.json"); formal=_read(results/"d4r"/"formal"/"complete.json"); h1=_read(results/"t3_h1"/"results.json"); h2=_read(results/"t4_h2"/"results.json")
    coverage=formal["coverage"]; splits=("train","validation","development"); regimes=("R0","R1","R2","R3")
    fig,ax=plt.subplots(figsize=(8.2,4.8)); x=np.arange(4); width=.24
    for j,split in enumerate(splits): ax.bar(x+(j-1)*width,[coverage[split][r] for r in regimes],width,label=split)
    ax.set_xticks(x,regimes); ax.set_ylabel("Non-overlapping 20-step windows"); ax.set_title("D4R physical-regime coverage"); ax.legend(); ax.grid(axis="y",alpha=.25); fig.tight_layout(); fig.savefig(figures/"regime_coverage.png",dpi=180); plt.close(fig)
    rounds=pilot["rounds"]; names=list(rounds); ratio=[rounds[n]["max_force_ratio"] for n in names]; windows=[rounds[n]["high_windows"] for n in names]
    fig,ax=plt.subplots(figsize=(8.2,4.8)); bars=ax.bar(names,ratio,color=["#4c78a8","#f58518","#54a24b"]); ax.axhline(.8,color="black",ls="--",label="0.8 rated")
    for bar,w in zip(bars,windows): ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+.015,f"{w} windows",ha="center")
    ax.set_ylim(0,1.08); ax.set_ylabel("Peak force / rated force"); ax.set_title("Safe high-load pilot rounds (ultimate steps = 0)"); ax.legend(); fig.tight_layout(); fig.savefig(figures/"highload_pilot.png",dpi=180); plt.close(fig)
    h1c=h1["development"]["candidate"]["J_pred"]; h1b=h1["development"]["baseline"]["J_pred"]; h2c=h2["development"]["candidate"]["h10_20"]["J_pred"]; h2b=h2["development"]["baseline"]["h10_20"]["J_pred"]
    fig,ax=plt.subplots(figsize=(7.8,4.8)); pos=np.arange(2); width=.34; ax.bar(pos-width/2,[h1b,h2b],width,label="K1 baseline"); ax.bar(pos+width/2,[h1c,h2c],width,label="candidate")
    ax.set_xticks(pos,["H1 N1 (all horizons)","H2 N2 (h=10–20)"]); ax.set_ylabel("J_pred (lower is better)"); ax.set_title("Development prediction result under preregistered gates"); ax.legend(); ax.grid(axis="y",alpha=.25); fig.tight_layout(); fig.savefig(figures/"h1_h2_accuracy.png",dpi=180); plt.close(fig)
    c=h2["development"]["candidate"]["all"]; b=h2["development"]["baseline"]["all"]; labels=["State NRMSE","Force NRMSE","Load NRMSE","Point direction error","Load direction error"]
    bv=[b["state"],b["force"],b["load"],1-b["point_direction"],1-b["load_direction"]]; cv=[c["state"],c["force"],c["load"],1-c["point_direction"],1-c["load_direction"]]
    fig,ax=plt.subplots(figsize=(9,4.8)); pos=np.arange(len(labels)); ax.bar(pos-width/2,bv,width,label="K1 baseline"); ax.bar(pos+width/2,cv,width,label="N2 direct head"); ax.set_xticks(pos,labels,rotation=15,ha="right"); ax.set_title("H2 accuracy gain conflicts with direction preservation"); ax.legend(); ax.grid(axis="y",alpha=.25); fig.tight_layout(); fig.savefig(figures/"h2_tradeoff.png",dpi=180); plt.close(fig)
    rows=[{"component":"H1","baseline_J":h1b,"candidate_J":h1c,"relative_improvement":h1["relative_improvement"],"passed":h1["passed"]},
          {"component":"H2","baseline_J":h2b,"candidate_J":h2c,"relative_improvement":h2["relative_improvement"],"passed":h2["passed"]}]
    with (results/"component_summary.csv").open("w",newline="",encoding="utf-8-sig") as handle: writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    report=f"""# CRMH-Koopman预注册实验报告

## 结论

本轮完成T0–T4；T0冻结/污染审计、T1 pilot和T2正式D4R均通过。H1和H2未同时满足预注册门，因此按任务树停止H3、组合、D5和闭环，不形成“CRMH-Koopman优于K1”的论文主张。

## 已核实事实

- D4R正式集400/400成功；四工况非重叠窗口：train `{coverage['train']}`、validation `{coverage['validation']}`、development `{coverage['development']}`。
- 高载荷train窗口=`{formal['high_load_train_windows']}`；pilot三轮均无ultimate触发，选中`{pilot['selected_high_config']}`。
- 四点力顺序为FL/FR/RL/RR，每点Fx/Fy；轴向反号样本为0。车辆侧独立施力没有单独日志，因此作用—反作用只能写`not identifiable`。
- H1代表seed=`{h1['representative_seed']}`，development相对K1变化=`{100*h1['relative_improvement']:.3f}%`，门禁=`{h1['gates']}`。
- H2代表seed=`{h2['representative_seed']}`，10–20步J改善=`{100*h2['relative_improvement']:.3f}%`，force/load改善=`{100*h2['force_improvement']:.3f}%/{100*h2['load_improvement']:.3f}%`，但方向门失败；门禁=`{h2['gates']}`。
- H2九候选20步p99=`{h2['runtime']['nine_candidate_20step_p99_ms']:.6f} ms`，teacher-free审计通过。

## 独立判断

H2说明直接多时域映射能显著降低幅值误差和发散，但它把四点力符号/载荷符号平均化，不能在受力安全任务中仅凭J_pred提升通过。development结果查看后再增加符号投影会构成事后调参，所以本轮没有这样做。若未来另立协议，可把“方向保持的物理force head”作为新方法，并必须使用全新的development/confirm数据。

## 证据边界

没有材料、截面和连接区破坏参数，仍只能报告货物受拉趋势/内力代理，不能判断真实撕裂或开裂。由于H1/H2停止门，未生成D5、未做闭环、网络扰动或DoS对比；本轮不能据此声称通信保护有效。
"""
    (results/"final_report.md").write_text(report,encoding="utf-8")
    return {"figures":[str(p) for p in sorted(figures.glob("*.png"))],"report":str(results/"final_report.md"),"csv":str(results/"component_summary.csv")}
