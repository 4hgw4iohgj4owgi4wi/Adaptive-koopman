"""Reports only saved legal artifacts, including negative and incomplete outcomes."""
from pathlib import Path
import numpy as np
from background_core import read_json,write_csv,sha,write_json

LABELS={"aligned":"统一预测目标","fixed_guard":"固定强度保护","adaptive_guard":"自适应强度保护",
        "residual_curriculum":"先一步、后多步的分段训练"}


def report(run,exit_info):
    run=Path(run)
    records=[]
    for p in sorted((run/"pilot").rglob("selection.json")):
        u=read_json(p)
        for g in u["grid"]:
            records.append(dict(method=LABELS[u["method"]],seed=u["seed"],step=u["step"],**g,
                                checkpoint=u["checkpoint"],checkpoint_sha=u["checkpoint_sha"]))
    lines=["# 剩余实验运行结果","",f"状态：{exit_info['status']}。{exit_info['message']}","",
           "## 内部比较","","下表来自保存的检查点与完整四时域评价。下降率为正表示20步误差减小；保护通过还需满足短期、逐工况、连接力、内部力和回头弯尾部要求。","",
           "| 方法 | 初始化 | 选中步数 | 修正强度 | 20步误差下降率 | 保护通过 |","|---|---:|---:|---:|---:|---|"]
    for r in records:
        lines.append(f"| {r['method']} | {r['seed']} | {r['step']} | {r['gamma']} | {r['i20']:.4f}% | {'是' if r['protected'] else '否'} |")
    if records:
        write_csv(run/"calibration_table.csv",records)
    lines += ["","## 结论范围","","数据属于反复使用的开发研究池。单折内部比较不能替代五折、三个初始化的正式复验。",
              "旧均方根误差课程不属于本次正确均方误差分支。未运行的正式比较、预测速度或控制实验不计为通过。",
              "","## 查看进度","","progress.json记录当前状态；events.jsonl及work_log.md逐项留痕；exit.json保存真实结束状态和退出码。"]
    (run/"report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    if records:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
        plt.rcParams['axes.unicode_minus']=False
        methods=list(dict.fromkeys(r["method"] for r in records))
        fig,axes=plt.subplots(1,len(methods),figsize=(4*len(methods),4),squeeze=False)
        for ax,method in zip(axes[0],methods):
            for seed in sorted({r['seed'] for r in records}):
                rr=sorted([r for r in records if r['method']==method and r['seed']==seed],key=lambda r:r['gamma'])
                if not rr:continue
                ax.plot([r['gamma'] for r in rr],[r['i20'] for r in rr],'-o',label=str(seed))
                good=[r for r in rr if r['protected']]
                ax.scatter([r['gamma'] for r in good],[r['i20'] for r in good],s=100,facecolors='none',edgecolors='green')
            ax.axhline(5,color='gray',linestyle='--');ax.axhline(0,color='black',linewidth=.7)
            ax.set(title=method,xlabel='残差修正强度',ylabel='20步误差下降率（%）');ax.legend(fontsize=8);ax.grid(alpha=.2)
        fig.suptitle('内部比较：绿圈表示完整保护要求通过，虚线为5%收益要求')
        fig.tight_layout();fig.savefig(run/"calibration.png",dpi=180);fig.savefig(run/"calibration.pdf");plt.close(fig)
        write_json(run/"figure_manifest.json",dict(figure_sha=sha(run/"calibration.png"),
            table_sha=sha(run/"calibration_table.csv"),script_sha=sha(__file__),n_rows=len(records)))
