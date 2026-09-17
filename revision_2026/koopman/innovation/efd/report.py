from __future__ import annotations
import csv,json
from pathlib import Path
from typing import Any
import numpy as np
def _load_efd(path:Path):
    from efd_heads import EFDHead
    with np.load(path,allow_pickle=False) as s:return EFDHead(s["coef"],s["mean"],s["std"],s["dims"],str(s["kind"].item()),s["force_scale"],float(s["theta_deg"].item()))
def build(project:Path,output:Path)->dict[str,Any]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from dataset import load_split
    from run import _load_baseline_heads,_load_thresholds
    from baseline import predictions
    from efd_heads import predict
    from metrics import evaluate
    root=project/"revision_2026"/"koopman"/"innovation_efd_results";output.mkdir(parents=True,exist_ok=True);data=load_split(project,"validation",True);thr,floor=_load_thresholds(type("C",(),{"results":root})());mag,point=_load_baseline_heads(root/"e3_baselines"/"models"/"E2_E3_full_train.npz");pred=predictions(data,mag,point,floor);g=_load_efd(root/"e4_g_efd"/"models"/"G_EFD_full_train.npz");d=_load_efd(root/"e5_d_efd"/"models"/"D_EFD_full_train.npz");pred["G-EFD"]=predict(g,data,floor);pred["D-EFD"]=predict(d,data,floor);methods=("E0","E1","E2","E3","G-EFD","D-EFD");horizons=(1,5,10,15,20);curves={m:{k:[] for k in ("state_core","connector_disp","connector_vel","state_all","force","load","angle_p95_deg")} for m in methods}
    for h in horizons:
        for m in methods:
            r=evaluate(pred[m]["x"],pred[m]["points"],pred[m]["q"],data,thr,slice(h-1,h))
            for k in curves[m]:curves[m][k].append(r[k])
    colors=plt.cm.tab10(np.linspace(0,1,len(methods)));fig,axs=plt.subplots(2,2,figsize=(12,8))
    for ax,key,title in zip(axs.flat,("state_core","connector_disp","connector_vel","state_all"),("state core 0:30","connector displacement 30:38","connector velocity 38:46","all state 0:46")):
        for m,c in zip(methods,colors):ax.plot(horizons,curves[m][key],marker="o",label=m,color=c)
        ax.set_title(title);ax.set_xlabel("horizon step (dt=0.02 s)");ax.set_ylabel("normalized RMSE");ax.grid(alpha=.25)
    axs[0,0].legend(ncol=3,fontsize=8);fig.suptitle("Validation, 96 trajectories; frozen models; state errors");fig.tight_layout();fig.savefig(output/"01_horizon_state4groups.png",dpi=180);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4));
    for ax,key,title in zip(axs,("force","load"),("Four-point force","Q payload load proxy")):
        for m,c in zip(methods,colors):ax.plot(horizons,curves[m][key],marker="o",label=m,color=c)
        ax.set_title(title);ax.set_xlabel("horizon step");ax.set_ylabel("normalized RMSE");ax.grid(alpha=.25)
    axs[0].legend(ncol=2,fontsize=8);fig.suptitle("Validation, n=96 trajectories; lower is better");fig.tight_layout();fig.savefig(output/"02_force_load_horizon.png",dpi=180);plt.close(fig)
    final={m:evaluate(pred[m]["x"],pred[m]["points"],pred[m]["q"],data,thr) for m in methods};x=np.arange(len(methods));fig,axs=plt.subplots(1,2,figsize=(12,4.5));axs[0].bar(x,[final[m]["angle_p95_deg"] for m in methods],color=colors);axs[0].axhline(90,color="red",ls="--",label="90 deg gate");axs[0].set_xticks(x,methods,rotation=25);axs[0].set_ylabel("angle p95 (deg)");axs[0].legend();axs[1].bar(x,[final[m]["component_accuracy"] for m in methods],color=colors);axs[1].axhline(final["E0"]["component_accuracy"]-.01,color="black",ls="--",label="K1-1 pp");axs[1].set_xticks(x,methods,rotation=25);axs[1].set_ylabel("component direction accuracy");axs[1].legend();fig.suptitle("Validation direction evidence, 10-20 steps, n=96 trajectories");fig.tight_layout();fig.savefig(output/"03_direction_angle.png",dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4));ax.bar(x,[final[m]["reversal_accuracy"] for m in methods],color=colors);ax.axhline(final["E0"]["reversal_accuracy"]-.01,color="black",ls="--",label="K1-1 pp");ax.set_xticks(x,methods);ax.set_ylim(0,1);ax.set_ylabel("reversal ±0.2 s accuracy");ax.set_title(f"Validation reversal response; events={final['E0']['reversal_events']}");ax.legend();fig.tight_layout();fig.savefig(output/"04_reversal_response.png",dpi=180);plt.close(fig)
    pilot=json.loads((root/"pilot"/"results.json").read_text(encoding="utf-8"));oracle=pilot["oracle"]["metrics"];fig,ax=plt.subplots(figsize=(8,4));names=list(oracle);ax.bar(names,[oracle[k]["p95_deg"] for k in names]);ax.axhline(2,color="red",ls="--",label="truth geometry gate 2 deg");ax.set_ylabel("force-direction angle p95 (deg)");ax.set_title(f"Pilot geometry oracle; windows={pilot['oracle']['windows']}");ax.legend();fig.tight_layout();fig.savefig(output/"05_geometry_alignment.png",dpi=180);plt.close(fig)
    gr=json.loads((root/"e4_g_efd"/"results.json").read_text(encoding="utf-8"))["selected"]["result"]["equivariance"];dr=json.loads((root/"e5_d_efd"/"results.json").read_text(encoding="utf-8"))["selected"]["result"]["equivariance"];labels=("rot30","rot60","mirror");fig,ax=plt.subplots(figsize=(9,4));w=.35;xx=np.arange(3);ax.bar(xx-w/2,[gr["rotation_30_p95"],gr["rotation_60_p95"],gr["mirror_p95"]],w,label="G-EFD");ax.bar(xx+w/2,[dr["rotation_30_p95"],dr["rotation_60_p95"],dr["mirror_p95"]],w,label="D-EFD");ax.axhline(.02,color="red",ls="--",label="2% gate");ax.set_xticks(xx,labels);ax.set_ylabel("equivariance relative error p95");ax.set_title("Unseen transform test, validation subset n=512 windows");ax.legend();fig.tight_layout();fig.savefig(output/"06_equivariance.png",dpi=180);plt.close(fig)
    regimes=("R0","R1","R2","R3");fig,axs=plt.subplots(1,2,figsize=(12,4))
    for m,c in zip(("E0","E1","G-EFD","D-EFD"),colors):
        vals=[];loads=[]
        for reg in regimes:
            idx=np.flatnonzero(data["regime"]==reg);sub={k:(v[idx] if isinstance(v,np.ndarray) and len(v)==len(data["x0"]) else v) for k,v in data.items()};r=evaluate(pred[m]["x"][idx],pred[m]["points"][idx],pred[m]["q"][idx],sub,thr);vals.append(r["force"]);loads.append(r["load"])
        axs[0].plot(regimes,vals,marker="o",label=m);axs[1].plot(regimes,loads,marker="o",label=m)
    axs[0].set_ylabel("force NRMSE");axs[1].set_ylabel("Q load NRMSE");axs[0].legend();fig.suptitle("Validation regime envelope, 24 trajectories per regime");fig.tight_layout();fig.savefig(output/"07_regime_envelope.png",dpi=180);plt.close(fig)
    gc=json.loads((root/"e4_g_efd"/"complete.json").read_text(encoding="utf-8"));dc=json.loads((root/"e5_d_efd"/"complete.json").read_text(encoding="utf-8"));allg=gc["failed_gates"];alld=dc["failed_gates"];labels=sorted(set(allg+alld+["accuracy gates","runtime/algebra"]));fig,ax=plt.subplots(figsize=(10,4));mat=np.asarray([[0 if k in allg else 1 for k in labels],[0 if k in alld else 1 for k in labels]]);ax.imshow(mat,cmap=matplotlib.colors.ListedColormap(["#cc4c4c","#338f5b"]),vmin=0,vmax=1,aspect="auto");ax.set_yticks([0,1],["G-EFD","D-EFD"]);ax.set_xticks(range(len(labels)),labels,rotation=30,ha="right");ax.set_title("Pre-registered gate summary (red=failed)");fig.tight_layout();fig.savefig(output/"08_gate_status.png",dpi=180);plt.close(fig)
    with (output/"validation_metrics.csv").open("w",newline="",encoding="utf-8-sig") as h:keys=sorted(final["E0"]);w=csv.DictWriter(h,fieldnames=["method",*keys]);w.writeheader();w.writerows([{"method":m,**final[m]} for m in methods])
    return {"methods":list(methods),"metrics_10_20":final,"figures":[p.name for p in sorted(output.glob("*.png"))]}
