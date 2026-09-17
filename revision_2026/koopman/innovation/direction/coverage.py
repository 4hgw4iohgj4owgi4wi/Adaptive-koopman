from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from typing import Any
import numpy as np

def frozen_force_floor(project:Path)->np.ndarray:
    path=project/"revision_2026"/"koopman"/"universal_v2"/"normalizers.npz"
    with np.load(path,allow_pickle=False) as s:return np.asarray(s["force_sign_floor"][:8],float).reshape(4,2)

def reversal_events(force:np.ndarray,floor:np.ndarray)->int:
    f=np.asarray(force,float); a=f[:-1];b=f[1:]; active=(np.abs(a)>=floor)&(np.abs(b)>=floor); return int(np.sum(active&(np.sign(a)!=np.sign(b))))

def pilot_contract(paths:list[Path],project:Path)->dict[str,Any]:
    floor=frozen_force_floor(project); events=ultimate=negative=0; finite=True; rows=[]
    for path in paths:
        with np.load(path,allow_pickle=False) as s:
            meta=json.loads(str(s["metadata_json"].item())); force=np.asarray(s["force_body"],float);disp=np.asarray(s["displacement_body"],float)
        local=reversal_events(force,floor); dot=np.sum(force*disp,axis=2); active=np.linalg.norm(force,axis=2)>1e-6; bad=int(np.sum(active&(dot< -1e-7)))
        events+=local;negative+=bad;ultimate+=int(meta["ultimate_exceeded_steps"]);finite=finite and bool(meta["finite"])
        rows.append({"file":path.name,"events":local,"axial_negative":bad,"ultimate_steps":meta["ultimate_exceeded_steps"],"finite":meta["finite"]})
    return {"passed":len(paths)==16 and finite and ultimate==0 and negative==0 and events>=40,"trajectories":len(paths),"finite":finite,"ultimate_steps":ultimate,"axial_negative_samples":negative,"direction_reversal_events":events,"force_floor":floor,"rows":rows}

def _regime_labels(displacement:np.ndarray,velocity:np.ndarray,free:float,thresholds:dict[str,float])->np.ndarray:
    d=np.asarray(displacement,float);v=np.asarray(velocity,float);norm=np.linalg.norm(d,axis=2);normal=d/np.maximum(norm[...,None],1e-12);p=np.maximum(norm-free,0.);vn=np.sum(v*normal,axis=2);effective=np.sum(p*vn,axis=1)/np.maximum(np.sum(p,axis=1),1e-12);pmax=np.max(p,axis=1)
    out=np.full(len(p),2,dtype=np.int8);loaded=pmax>thresholds["eps_p"];out[~loaded]=0;out[loaded&(effective>thresholds["eps_v"])]=1;out[loaded&(effective< -thresholds["eps_v"])]=3;return out

def formal_contract(paths:list[Path],project:Path,thresholds:dict[str,float])->dict[str,Any]:
    floor=frozen_force_floor(project);coverage={s:Counter() for s in ("train","validation","development")};events=Counter();high=Counter();failures=[];negative=ultimate=0
    for path in paths:
        with np.load(path,allow_pickle=False) as s:
            meta=json.loads(str(s["metadata_json"].item()));split=meta["split"];n=int(meta["steps"]);force=np.asarray(s["force_body"],float);disp=np.asarray(s["displacement_body"],float);vel=np.asarray(s["relative_velocity_body"],float);time_s=np.asarray(s["time_s"],float)
            expected={"s3_deform":(n+1,46),"u1_four":(n,8),"force_output":(n+1,18),"force_body":(n+1,4,2),"force_rate":(n+1,4,2),"q":(n+1,2),"time_s":(n+1,)};wrong={k:[list(s[k].shape),list(v)] for k,v in expected.items() if k not in s or s[k].shape!=v}
            tol=max(2e-6,2*float(np.spacing(np.float32(np.max(np.abs(time_s))))));time_ok=bool(np.all(np.diff(time_s)>0) and np.allclose(np.diff(time_s),meta["control_dt_s"],rtol=0,atol=tol) and abs(time_s[-1]-meta["duration_s"])<=tol)
            maps=bool(np.array_equal(s["force_output"][:,:8],s["force_body"].reshape(n+1,8)) and np.array_equal(s["force_output"][:,8:10],s["q"]) and np.array_equal(s["force_output"][:,10:18],s["force_rate"].reshape(n+1,8)))
            finite=all(np.all(np.isfinite(s[k])) for k in expected if k in s)
        lab=_regime_labels(disp,vel,float(meta["params"]["connector"]["free_play_m"]),thresholds);rated=float(meta["params"]["connector"]["rated_force_n"])
        for start in range(0,n-20+1,20):coverage[split][f"R{int(np.bincount(lab[start:start+20],minlength=4).argmax())}"]+=1;high[split]+=int(np.max(np.linalg.norm(force[start:start+20],axis=2))>=.8*rated)
        events[split]+=reversal_events(force,floor);dot=np.sum(force*disp,axis=2);active=np.linalg.norm(force,axis=2)>1e-6;negative+=int(np.sum(active&(dot< -1e-7)));ultimate+=int(meta["ultimate_exceeded_steps"])
        if wrong or not(time_ok and maps and finite):failures.append({"file":path.name,"shape":wrong,"time":time_ok,"maps":maps,"finite":finite})
    cov={s:{f"R{i}":coverage[s][f"R{i}"] for i in range(4)} for s in coverage};cover_ok=all(cov[s][f"R{i}"]>=m for s,m in (("train",1500),("validation",400),("development",400)) for i in range(4));event_ok=all(events[s]>=200 for s in events);high_ok=high["train"]>=200
    return {"passed":not failures and negative==0 and ultimate==0 and cover_ok and event_ok and high_ok,"coverage":cov,"direction_events":dict(events),"high_load_windows":dict(high),"coverage_gate":cover_ok,"event_gate":event_ok,"high_gate":high_ok,"axial_negative_samples":negative,"ultimate_steps":ultimate,"failures":failures}
