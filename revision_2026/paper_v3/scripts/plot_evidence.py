"""Render six evidence groups directly from registered raw outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import hashlib
import json
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as h: return list(csv.DictReader(h))


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({k for r in rows for k in r}) if rows else ["status"]
    with path.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields); w.writeheader(); w.writerows(rows)


def save(fig, out: Path, rows: list[dict], name: str) -> None:
    fig.tight_layout(); fig.savefig(out / f"{name}.png", dpi=180); fig.savefig(out / f"{name}.pdf")
    write_csv(out / f"{name}.csv", rows); plt.close(fig)


def metric(rows, method, key):
    values = [float(r[key]) for r in rows if r.get("method") == method and r.get(key) not in (None, "")]
    return float(np.mean(values)) if values else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--run", type=Path, required=True); ap.add_argument("--delay", type=Path, required=True); ap.add_argument("--common", type=Path, required=True); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); out = a.out; out.mkdir(parents=True, exist_ok=True)
    core = read_csv(a.run / "metrics.csv"); delay = read_csv(a.delay / "metrics.csv"); common = read_csv(a.common / "metrics.csv")
    methods = ["P0", "P1", "K0", "K0N", "K1", "K1N"]
    colors = {"P0":"#6c757d","P1":"#495057","K0":"#4dabf7","K0N":"#1864ab","K1":"#69db7c","K1N":"#2b8a3e"}
    # 1. 3x2 factor evidence.
    fig, axes = plt.subplots(1, 3, figsize=(12, 4)); x=np.arange(len(methods));
    for ax, key, title in zip(axes, ["lateral_rmse_m","connector_p99_n","completed"], ["Lateral tracking RMSE (m)","Connector force proxy P99 (N)","Completed trials / 810"]):
        vals=[]
        for m in methods:
            if key == "completed": vals.append(sum(r.get("method")==m and r.get("completed")=="True" for r in core))
            else: vals.append(metric(core,m,key))
        ax.bar(x, vals, color=[colors[m] for m in methods]); ax.set_xticks(x, methods, rotation=35); ax.set_title(title); ax.grid(axis="y", alpha=.25)
    save(fig,out,[{"method":m,"lateral_rmse_m":metric(core,m,"lateral_rmse_m"),"connector_p99_n":metric(core,m,"connector_p99_n"),"completed":sum(r.get("method")==m and r.get("completed")=="True" for r in core)} for m in methods],"fig1_ablation_3x2")
    # Representative raw trajectory/force.
    first = next(r for r in core if r.get("scenario")=="100m_accel_turn" and r.get("profile")=="CLEAN" and r.get("family")=="0")
    cid=first["case_id"]; raw=a.run/"raw_ticks"/cid
    fig, axes=plt.subplots(2,1,figsize=(10,6),sharex=True)
    for m in ["P0","P1","K0","K0N","K1","K1N"]:
        f=raw/f"{m}.npz"
        if not f.exists(): continue
        z=np.load(f,allow_pickle=False); states=z["states"]; forces=z["forces"]; t_state=np.arange(len(states))*0.02; t_force=np.arange(len(forces))*0.02
        axes[0].plot(t_state,states[:,24],label=m,color=colors[m]); axes[1].plot(t_force,np.linalg.norm(forces,axis=2).max(axis=1),label=m,color=colors[m])
    axes[0].set_ylabel("Cargo X (m)"); axes[1].set_ylabel("Peak connector force (N)"); axes[1].set_xlabel("Time (s)"); axes[0].legend(ncol=3); axes[0].grid(alpha=.25); axes[1].grid(alpha=.25)
    save(fig,out,[{"case_id":cid,"source":"raw_ticks","status":"available","attack_window":"registered k_s:k_e"}],"fig2_event_force_recovery")
    # 3. Four-point directional forces.
    z=np.load(raw/"K1N.npz",allow_pickle=False); forces=z["forces"]; t=np.arange(len(forces))*0.02
    fig, ax=plt.subplots(figsize=(10,4))
    for i,name in enumerate(["FL","FR","RL","RR"]): ax.plot(t,np.linalg.norm(forces[:,i,:],axis=1),label=name)
    ax.set_xlabel("Time (s)"); ax.set_ylabel("Connector force norm (N)"); ax.set_title("K1N four-point force proxy"); ax.legend(ncol=4); ax.grid(alpha=.25)
    save(fig,out,[{"case_id":cid,"method":"K1N","connector":"FL/FR/RL/RR","status":"available"}],"fig3_directional_force")
    # 4. Delay mechanism.
    fig, axes=plt.subplots(1,2,figsize=(10,4)); prof=["CLEAN","DELAY60","DELAY100","DELAY180","JITTER100"]
    for m,ls in [("K1N","-"),("ND","--")]:
        q=[metric([r for r in delay if r.get("profile")==p],m,"mean_estimate_rmse") for p in prof]
        axes[0].plot(prof,q,marker="o",linestyle=ls,label=m)
        q=[metric([r for r in delay if r.get("profile")==p],m,"lateral_rmse_m") for p in prof]
        axes[1].plot(prof,q,marker="o",linestyle=ls,label=m)
    axes[0].set_title("Neighbor-state estimate RMSE"); axes[1].set_title("Lateral tracking RMSE");
    for ax in axes: ax.grid(alpha=.25); ax.legend(); ax.tick_params(axis="x",rotation=30)
    save(fig,out,[{"profile":p,"K1N_estimate_rmse":metric([r for r in delay if r.get("profile")==p],"K1N","mean_estimate_rmse"),"ND_estimate_rmse":metric([r for r in delay if r.get("profile")==p],"ND","mean_estimate_rmse"),"K1N_lateral_rmse":metric([r for r in delay if r.get("profile")==p],"K1N","lateral_rmse_m"),"ND_lateral_rmse":metric([r for r in delay if r.get("profile")==p],"ND","lateral_rmse_m")} for p in prof],"fig4_delay_five_levels")
    # 5. External baselines: explicit missing evidence.
    fig, ax=plt.subplots(figsize=(8,4)); ax.text(.5,.5,"TUBE / AOF / NET / AKE\nSOURCE_OR_ADAPTATION_BLOCKED\nNot executed; no internal heuristic substituted",ha="center",va="center",fontsize=15); ax.axis("off")
    save(fig,out,[{"baseline":m,"status":"NOT_RUN","reason":"source qualification/adaptation not complete"} for m in ["TUBE","AOF","NET","AKE"]],"fig5_external_baselines_not_run")
    # 6. Failure/completion by profile and method.
    fig, ax=plt.subplots(figsize=(12,5)); profiles=sorted(set(r.get("profile") for r in core)); xx=np.arange(len(profiles)); width=.12
    for j,m in enumerate(methods):
        vals=[sum(r.get("method")==m and r.get("profile")==p and r.get("completed")=="True" for r in core)/max(1,sum(r.get("method")==m and r.get("profile")==p for r in core)) for p in profiles]
        ax.bar(xx+(j-2.5)*width,vals,width,label=m,color=colors[m])
    ax.set_xticks(xx,profiles,rotation=30); ax.set_ylim(0,1.05); ax.set_ylabel("Completion rate"); ax.set_title("Completion rate by network profile"); ax.legend(ncol=3); ax.grid(axis="y",alpha=.25)
    save(fig,out,[{"profile":p,"method":m,"completion_rate":sum(r.get("method")==m and r.get("profile")==p and r.get("completed")=="True" for r in core)/max(1,sum(r.get("method")==m and r.get("profile")==p for r in core))} for p in profiles for m in methods],"fig6_failure_completion")
    figure_names = sorted(p.name for p in out.glob("fig*.png"))
    manifest = {"script":str(Path(__file__).resolve()),"script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper(),"figures":figure_names}
    (out/"figure_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    write_csv(out/"figure_manifest.csv", [{"figure": name, "png": name, "pdf": name[:-4]+".pdf", "data": name[:-4]+".csv", "status":"RENDERED"} for name in figure_names])
    write_csv(out/"figure_manifest.csv", [{"figure": name, "png": name, "pdf": name[:-4]+".pdf", "data": name[:-4]+".csv", "status":"RENDERED"} for name in figure_names])
    print(json.dumps({"out":str(out),"figures":len(list(out.glob("fig*.png")))},ensure_ascii=False))


if __name__ == "__main__": main()
