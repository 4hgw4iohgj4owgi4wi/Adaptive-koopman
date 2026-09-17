from __future__ import annotations
import csv,json
from pathlib import Path
from typing import Any
import numpy as np

def build_report(results_path:Path,output:Path)->dict[str,Any]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    result=json.loads(results_path.read_text(encoding="utf-8"));metrics=result["metrics_10_20"];output.mkdir(parents=True,exist_ok=True);methods=list(metrics)
    with (output/"validation_metrics.csv").open("w",newline="",encoding="utf-8-sig") as h:
        keys=sorted({k for m in metrics.values() for k,v in m.items() if isinstance(v,(int,float))});w=csv.DictWriter(h,fieldnames=["method",*keys]);w.writeheader();w.writerows([{"method":m,**metrics[m]} for m in methods])
    fig,ax=plt.subplots(figsize=(10,5));x=np.arange(len(methods));width=.2
    for i,key in enumerate(("state","force","load","J_pred")):ax.bar(x+(i-1.5)*width,[metrics[m][key] for m in methods],width,label=key)
    ax.set_xticks(x,methods);ax.set_ylabel("Normalized RMSE (steps 10-20)");ax.set_title("D4 validation: prediction errors");ax.grid(axis="y",alpha=.25);ax.legend(ncol=4);fig.tight_layout();fig.savefig(output/"01_prediction_errors.png",dpi=180);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4.5));acc=("component_sign_accuracy","q_sign_accuracy","reversal_accuracy")
    for i,key in enumerate(acc):axs[0].bar(x+(i-1)*.25,[metrics[m][key] for m in methods],.25,label=key.replace("_accuracy",""))
    axs[0].set_xticks(x,methods);axs[0].set_ylim(0,1);axs[0].set_ylabel("Accuracy");axs[0].grid(axis="y",alpha=.25);axs[0].legend(fontsize=8)
    axs[1].bar(x,[metrics[m]["angle_p95_deg"] for m in methods]);axs[1].set_xticks(x,methods);axs[1].set_ylabel("Vector angle p95 (deg, lower is better)");axs[1].grid(axis="y",alpha=.25);fig.suptitle("D4 validation: direction evidence");fig.tight_layout();fig.savefig(output/"02_direction_metrics.png",dpi=180);plt.close(fig)
    gates=result["gates"];names=list(gates);colors=["#2e8b57" if gates[k] else "#c94c4c" for k in names];fig,ax=plt.subplots(figsize=(10,6));ax.barh(np.arange(len(names)),[1]*len(names),color=colors);ax.set_yticks(np.arange(len(names)),names);ax.set_xticks([]);ax.invert_yaxis();ax.set_title("D4 preregistered gates (green=pass, red=fail)");fig.tight_layout();fig.savefig(output/"03_gate_status.png",dpi=180);plt.close(fig)
    seeds=result["all_seeds"];fig,axs=plt.subplots(1,2,figsize=(10,4));sid=[str(r["seed"]) for r in seeds];axs[0].bar(sid,[r["validation"]["P4"]["J_pred"] for r in seeds]);axs[0].set_title("P4 J by bootstrap seed");axs[0].tick_params(axis="x",rotation=30);axs[1].bar(sid,[r["validation"]["P4"]["angle_p95_deg"] for r in seeds]);axs[1].axhline(metrics["P0"]["angle_p95_deg"],color="black",ls="--",label="K1 limit");axs[1].set_title("P4 angle p95 by seed");axs[1].tick_params(axis="x",rotation=30);axs[1].legend();fig.tight_layout();fig.savefig(output/"04_five_seed_stability.png",dpi=180);plt.close(fig)
    p0,p1,p4,p5=metrics["P0"],metrics["P1"],metrics["P4"],metrics["P5"];jimp=100*(p0["J_pred"]-p4["J_pred"])/p0["J_pred"];forcechange=100*(p4["force"]-p1["force"])/p1["force"];loadchange=100*(p4["load"]-p1["load"])/p1["load"]
    failed=[k for k,v in gates.items() if not v];report=f"""# DP-MHK方向实验执行结论

## 结论

D0–D3通过，D4正式validation失败，因此按`koopman_dir.md`停止D5 development、D5盲确认、闭环和网络实验。未读取D4R2 development进行P4调参。

## 已核实事实

- 代表seed：{result['representative_seed']}，按五seed validation J中位选择。
- P4相对K1的10–20步总J改善：{jimp:.3f}%。
- P4相对P1的force NRMSE变化：{forcechange:+.3f}%；load NRMSE变化：{loadchange:+.3f}%。
- P4/K1四点分量方向准确率：{p4['component_sign_accuracy']:.6f}/{p0['component_sign_accuracy']:.6f}。
- P4/K1 Q方向准确率：{p4['q_sign_accuracy']:.6f}/{p0['q_sign_accuracy']:.6f}。
- P4/K1向量角度p95：{p4['angle_p95_deg']:.3f}/{p0['angle_p95_deg']:.3f} deg。
- P4/K1反转准确率：{p4['reversal_accuracy']:.6f}/{p0['reversal_accuracy']:.6f}。
- P4 Q代数残差为{p4['algebraic_residual_N']:.3e} N，回退率{100*p4['fallback_rate']:.3f}%，9窗批量p99={result['runtime_9_candidates']['p99_ms']:.3f} ms。
- 失败门：{', '.join(failed)}。
- 无约束P5在相同x0/u输入下的J={p5['J_pred']:.6f}、角度p95={p5['angle_p95_deg']:.3f} deg；这只用于归因，不能替代P4通过物理方法门。

## 解释边界

事实支持“冻结H2位移几何方向不足以达到K1方向基线，且代数Q重构放大了方向/点力组合误差”。P5结果提示数据中的方向可由直接head学习，但把P5升级为主方法会改变方法定义，当前任务书不允许据此继续D5。

不能从本轮声称闭环改善、网络保护必要性或真实货物撕裂概率；这些分支均未获准运行，且材料/连接区破坏参数仍不可识别。

## 下一轮可选解决方案（需新协议，不能复用本轮development作调参）

1. 保留非负轴向幅值，增加受限方向残差head，并投影回单位圆/轴向锥。
2. 把四点分量符号、向量角度和Q方向加入训练选择的硬约束，而不是仅依赖H2位移几何。
3. 重新设计连接位移状态或加入可观测几何量；用新的validation/development seed整批确认。
4. 将P5保持为归因上界，不包装成DP-MHK物理贡献。
""";(output/"negative_result.md").write_text(report,encoding="utf-8")
    return {"failed_gates":failed,"j_improvement_pct":jimp,"force_change_vs_p1_pct":forcechange,"load_change_vs_p1_pct":loadchange,"files":[p.name for p in sorted(output.iterdir())]}
