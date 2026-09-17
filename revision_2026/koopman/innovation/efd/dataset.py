from __future__ import annotations
import json,sys
from pathlib import Path
from typing import Any
import numpy as np
from h2_adapter import FrozenH2
from physics_decoder import reconstruct_load,causal_rate

def old_norms(project:Path)->dict[str,np.ndarray]:
    with np.load(project/"revision_2026"/"koopman"/"universal_v2"/"normalizers.npz",allow_pickle=False) as s:return {k:np.asarray(s[k],float) for k in s.files}
def load_split(project:Path,split:str,include_k1:bool=False)->dict[str,Any]:
    root=project/"revision_2026"/"koopman"/"innovation_efd_results"/"d6efd";manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))["completed"];rows=[r for r in manifest if r["split"]==split];norm=old_norms(project);h2=FrozenH2(project/"revision_2026"/"koopman"/"innovation_results"/"t4_h2"/"models"/"N2-seed-151002.npz");parts={k:[] for k in ("x0","u","truth_x","truth_f","truth_points","truth_q","current","h2")};trajectory=[];regime=[];seeds=[]
    k1ctx=None
    if include_k1:
        old=project/"revision_2026"/"koopman"/"innovation";koop=project/"revision_2026"/"koopman"
        for p in (old,koop):
            if str(p) not in sys.path:sys.path.insert(0,str(p))
        import baseline_cache as legacy;k1ctx=(legacy,legacy._context(project));parts["k1x"]=[];parts["k1f"]=[]
    for ti,row in enumerate(rows):
        path=root/"trajectories"/row["file"]
        with np.load(path,allow_pickle=False) as s:state=np.asarray(s["s3_deform"],float);control=np.asarray(s["u1_four"],float);points=np.asarray(s["force_on_payload"],float);raw={k:np.asarray(s[k],float) for k in ("s3_deform","force_output","u1_four","network")};meta=json.loads(str(s["metadata_json"].item()))
        origins=np.arange(0,len(control)-20+1,20);x0=(state[origins]-norm["x_mean"])/norm["x_std"];uf=np.asarray([(control[o:o+20]-norm["u_mean"])/norm["u_std"] for o in origins]);tx=np.asarray([(state[o+1:o+21]-norm["x_mean"])/norm["x_std"] for o in origins]);tp=np.asarray([points[o+1:o+21] for o in origins]);tq=reconstruct_load(tp);cur=points[origins];rate=causal_rate(tp,cur);physical=np.concatenate([tp.reshape(len(tp),20,8),tq,rate.reshape(len(tp),20,8)],axis=-1);tf=(physical-norm["force_mean"])/norm["force_std"];hp=h2.predict(x0,uf)
        for k,v in (("x0",x0),("u",uf),("truth_x",tx),("truth_f",tf),("truth_points",tp),("truth_q",tq),("current",cur),("h2",hp)):parts[k].append(v)
        if include_k1:
            legacy,ctx=k1ctx;kx=[];kf=[]
            for o in origins:x,f,_,_=legacy._rollout(ctx,"K1",raw,int(o));kx.append(x);kf.append(f)
            parts["k1x"].append(np.asarray(kx));parts["k1f"].append(np.asarray(kf))
        trajectory.extend([ti]*len(origins));regime.extend([meta["regime"]]*len(origins));seeds.extend([meta["seed"]]*len(origins))
    return {**{k:np.concatenate(v) for k,v in parts.items()},"trajectory":np.asarray(trajectory),"regime":np.asarray(regime),"seed":np.asarray(seeds),"norms":norm,"rows":rows}
def feature(data:dict[str,Any],h:int)->np.ndarray:return np.c_[np.ones(len(data["x0"])),data["x0"],data["u"][:,:h].reshape(len(data["x0"]),-1)]
def fit_metric_thresholds(train:dict[str,Any])->dict[str,np.ndarray]:
    p=train["truth_points"].reshape(len(train["x0"]),20,8);q=train["truth_q"]
    return {"component_floor":np.asarray([np.quantile(np.abs(p[...,i])[np.abs(p[...,i])>1e-9],.1) for i in range(8)]),"point_floor":np.asarray([np.quantile(np.linalg.norm(train["truth_points"],axis=-1)[...,i][np.linalg.norm(train["truth_points"],axis=-1)[...,i]>1e-9],.1) for i in range(4)]),"q_floor":np.asarray([np.quantile(np.abs(q[...,i])[np.abs(q[...,i])>1e-9],.1) for i in range(2)])}
