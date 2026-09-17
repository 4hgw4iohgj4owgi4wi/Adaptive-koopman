from __future__ import annotations
import json,sys
from pathlib import Path
from typing import Any
import numpy as np

from h2_adapter import FrozenH2StateAdapter
from metrics import nrmse_groups,paired_statistics

def h2_regression(project:Path,limit:int=32)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman";old=koop/"innovation"
    if str(old) not in sys.path:sys.path.insert(0,str(old))
    from multihorizon import DirectMultiHorizonHead
    path=koop/"innovation_results"/"t4_h2"/"models"/"N2-seed-151002.npz";adapter=FrozenH2StateAdapter(path)
    with np.load(path,allow_pickle=False) as s:legacy=DirectMultiHorizonHead(s["coef"],s["feature_mean"],s["feature_std"],s["feature_dims"])
    with np.load(koop/"universal_v2"/"normalizers.npz",allow_pickle=False) as s:norms={k:np.asarray(s[k],float) for k in s.files}
    rawdir=koop/"innovation_direction_results"/"d4r2"/"formal"/"trajectories";diff=[];binary=[];count=0
    for raw in sorted(rawdir.glob("validation_*.npz")):
        with np.load(raw,allow_pickle=False) as s:state=np.asarray(s["s3_deform"],float);control=np.asarray(s["u1_four"],float)
        for origin in range(0,len(control)-20+1,20):
            x=(state[origin]-norms["x_mean"])/norms["x_std"];u=(control[origin:origin+20]-norms["u_mean"])/norms["u_std"];a=adapter.predict_full(x,u)[0];b=legacy.predict(x,u)
            diff.append(float(np.max(np.abs(a-b))));binary.append(bool(np.array_equal(a.astype(np.float32),b.astype(np.float32))));count+=1
            if count>=limit:break
        if count>=limit:break
    return {"windows":count,"max_abs":max(diff),"float32_binary_equal":all(binary),"passed":max(diff)<=1e-10 or all(binary)}

def evaluate_d3(project:Path)->dict[str,Any]:
    root=project/"revision_2026"/"koopman"/"innovation_direction_results"/"d4r2"/"formal";manifest=json.loads((root/"cache_manifest.json").read_text(encoding="utf-8"));rows=[x for x in manifest["completed"] if x["split"]=="development"]
    aggregate={k:[] for k in ("p0x","p0f","p1x","p1f","tx","tf")};per=[]
    for row in rows:
        with np.load(root/"cache"/row["file"],allow_pickle=False) as s:
            p0x=np.asarray(s["P0_x"],float);p0f=np.asarray(s["P0_f"],float);p1=np.asarray(s["P1"],float);tx=np.asarray(s["truth_x"],float);tf=np.asarray(s["truth_f"],float)
        base=nrmse_groups(p0x,p0f,tx,tf);candidate=nrmse_groups(p1[...,:46],p1[...,46:64],tx,tf);per.append({"seed":row["seed"],"P0":base,"P1":candidate})
        for key,value in (("p0x",p0x),("p0f",p0f),("p1x",p1[...,:46]),("p1f",p1[...,46:64]),("tx",tx),("tf",tf)):aggregate[key].append(value)
    base=nrmse_groups(np.concatenate(aggregate["p0x"]),np.concatenate(aggregate["p0f"]),np.concatenate(aggregate["tx"]),np.concatenate(aggregate["tf"]));candidate=nrmse_groups(np.concatenate(aggregate["p1x"]),np.concatenate(aggregate["p1f"]),np.concatenate(aggregate["tx"]),np.concatenate(aggregate["tf"]));imp=(base["J_pred"]-candidate["J_pred"])/base["J_pred"]
    stats=paired_statistics(np.asarray([x["P1"]["J_pred"] for x in per]),np.asarray([x["P0"]["J_pred"] for x in per]));gates={"J_8pct":imp>=.08,"components":all(candidate[k]<=1.03*base[k] for k in ("state","force","load")),"divergence":candidate["divergence_rate"]<=base["divergence_rate"],"ci_holm":stats["ci95"][0]>0 and stats["holm_p"]<.05}
    return {"P0":base,"P1":candidate,"relative_improvement":imp,"statistics":stats,"per_trajectory":per,"gates":gates,"passed":all(gates.values())}
