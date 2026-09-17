from __future__ import annotations
import time
from typing import Any
import numpy as np
from efd_heads import EFDHead,fit,predict
from h2_adapter import FrozenH2
from metrics import evaluate
from transforms import rotate_global_x0,mirror_lr,mirror_points

def subset(data:dict[str,Any],idx:np.ndarray)->dict[str,Any]:return {k:(v[idx] if isinstance(v,np.ndarray) and len(v)==len(data["x0"]) else v) for k,v in data.items()}
def ci95(values:np.ndarray,seed:int=196999)->list[float]:
    v=np.asarray(values,float);rng=np.random.default_rng(seed);means=np.mean(v[rng.integers(0,len(v),size=(10000,len(v)))],axis=1);return [float(np.quantile(means,.025)),float(np.quantile(means,.975))]
def trajectory_comparison(candidate:dict[str,np.ndarray],base0:dict[str,np.ndarray],base1:dict[str,np.ndarray],data:dict[str,Any],thr:dict[str,np.ndarray])->dict[str,Any]:
    rows=[]
    for tid in np.unique(data["trajectory"]):
        idx=np.flatnonzero(data["trajectory"]==tid);d=subset(data,idx);cm=evaluate(candidate["x"][idx],candidate["points"][idx],candidate["q"][idx],d,thr);m0=evaluate(base0["x"][idx],base0["points"][idx],base0["q"][idx],d,thr);m1=evaluate(base1["x"][idx],base1["points"][idx],base1["q"][idx],d,thr);rows.append({"J_imp_K1":(m0["J"]-cm["J"])/(m0["J"]+1e-12),"disp_imp_H2":(m1["connector_disp"]-cm["connector_disp"])/(m1["connector_disp"]+1e-12),"component_delta_K1":cm["component_accuracy"]-m0["component_accuracy"],"Q_delta_K1":cm["Q_accuracy"]-m0["Q_accuracy"],"reversal_delta_K1":cm["reversal_accuracy"]-m0["reversal_accuracy"]})
    return {k:{"mean":float(np.nanmean([r[k] for r in rows])),"ci95":ci95(np.asarray([r[k] for r in rows]))} for k in rows[0]}
def equivariance(head:EFDHead,data:dict[str,Any],direction_floor:float,model:FrozenH2,limit:int=512)->dict[str,float]:
    idx=np.arange(min(limit,len(data["x0"])));d=subset(data,idx);base=predict(head,d,direction_floor)["points"];values={}
    for angle in (30.,60.):
        x=rotate_global_x0(d["x0"],d["norms"],angle);td={**d,"x0":x,"h2":model.predict(x,d["u"])};p=predict(head,td,direction_floor)["points"];err=np.linalg.norm(p-base,axis=-1)/np.maximum(np.linalg.norm(base,axis=-1),1e-9);values[f"rotation_{int(angle)}_p95"]=float(np.quantile(err,.95))
    x,u=mirror_lr(d["x0"],d["u"],d["norms"]);td={**d,"x0":x,"u":u,"h2":model.predict(x,u)};p=predict(head,td,direction_floor)["points"];expected=mirror_points(base);err=np.linalg.norm(p-expected,axis=-1)/np.maximum(np.linalg.norm(expected,axis=-1),1e-9);values["mirror_p95"]=float(np.quantile(err,.95));values["max_p95"]=max(values.values());return values
def runtime(head:EFDHead,data:dict[str,Any],floor:float,model:FrozenH2)->dict[str,float]:
    d=subset(data,np.arange(9));times=[]
    for _ in range(200):
        t=time.perf_counter();h=model.predict(d["x0"],d["u"]);predict(head,{**d,"h2":h},floor);times.append((time.perf_counter()-t)*1000)
    return {"p50_ms":float(np.quantile(times,.5)),"p95_ms":float(np.quantile(times,.95)),"p99_ms":float(np.quantile(times,.99)),"max_ms":float(np.max(times))}
def candidate_result(head:EFDHead,data:dict[str,Any],bases:dict[str,dict[str,np.ndarray]],thr:dict[str,np.ndarray],floor:float,model:FrozenH2)->dict[str,Any]:
    pred=predict(head,data,floor);m=evaluate(pred["x"],pred["points"],pred["q"],data,thr);stats=trajectory_comparison(pred,bases["E0"],bases["E1"],data,thr);eq=equivariance(head,data,floor,model);rt=runtime(head,data,floor,model);corr=pred["correction_angle_deg"];m.update({"fallback_rate":float(np.mean(pred["fallback"])),"correction_angle_median_deg":float(np.median(corr)),"correction_angle_p95_deg":float(np.quantile(corr,.95))});k1=evaluate(bases["E0"]["x"],bases["E0"]["points"],bases["E0"]["q"],data,thr);h2=evaluate(bases["E1"]["x"],bases["E1"]["points"],bases["E1"]["q"],data,thr);sig=sum(stats[k]["ci95"][0]>0 for k in ("component_delta_K1","Q_delta_K1","reversal_delta_K1"));gates={"J_K1_8pct_CI":(k1["J"]-m["J"])/k1["J"]>=.08 and stats["J_imp_K1"]["ci95"][0]>0,"state_core_H2":m["state_core"]<=1.01*h2["state_core"],"connector_disp":True if head.kind=="D" else ((h2["connector_disp"]-m["connector_disp"])/h2["connector_disp"]>=.10 and stats["disp_imp_H2"]["ci95"][0]>0),"force_load_H2":m["force"]<=1.05*h2["force"] and m["load"]<=1.05*h2["load"] and (m["force"]<=.9*h2["force"] or m["load"]<=.9*h2["load"]),"directions_K1":m["component_accuracy"]>=k1["component_accuracy"]-.01 and m["Q_accuracy"]>=k1["Q_accuracy"]-.01 and m["reversal_accuracy"]>=k1["reversal_accuracy"]-.01 and sig>=2,"angle":m["angle_p95_deg"]<k1["angle_p95_deg"] and m["angle_p95_deg"]<=90,"correction_angle":True if head.kind=="G" else (m["correction_angle_median_deg"]<=15 and m["correction_angle_p95_deg"]<=45),"equivariance":eq["max_p95"]<=.02,"algebra":m["Q_residual_N"]<=1e-10,"fallback":m["fallback_rate"]<=.01,"divergence":m["divergence_rate"]<=h2["divergence_rate"],"runtime":rt["p99_ms"]<=2 and rt["max_ms"]<20};return {"metrics":m,"trajectory_statistics":stats,"equivariance":eq,"runtime":rt,"significant_direction_metrics":sig,"gates":gates,"passed":all(gates.values())}
def bootstrap_indices(data:dict[str,Any],seed:int)->np.ndarray:
    ids=np.unique(data["trajectory"]);rng=np.random.default_rng(seed);draw=ids[rng.integers(0,len(ids),len(ids))];return np.concatenate([np.flatnonzero(data["trajectory"]==i) for i in draw])
