from __future__ import annotations
import math
from typing import Any
import numpy as np

from physics_decoder import reconstruct_load

def nrmse_groups(pred_x:np.ndarray,pred_f:np.ndarray,true_x:np.ndarray,true_f:np.ndarray,sl:slice=slice(9,20))->dict[str,float]:
    px=np.asarray(pred_x,float)[:,sl];pf=np.asarray(pred_f,float)[:,sl];tx=np.asarray(true_x,float)[:,sl];tf=np.asarray(true_f,float)[:,sl]
    state=float(np.sqrt(np.mean((px[...,:30]-tx[...,:30])**2)));force=float(np.sqrt(np.mean((pf[...,:8]-tf[...,:8])**2)));load=float(np.sqrt(np.mean((pf[...,8:10]-tf[...,8:10])**2)))
    diverged=float(np.mean(np.any(~np.isfinite(np.c_[px.reshape(len(px),-1),pf.reshape(len(pf),-1)]),axis=1)|(np.max(np.abs(px),axis=(1,2))>50)|(np.max(np.abs(pf),axis=(1,2))>50)))
    return {"state":state,"force":force,"load":load,"J_pred":(state+force+load)/3,"divergence_rate":diverged}

def paired_statistics(candidate:np.ndarray,baseline:np.ndarray,seed:int=182999)->dict[str,Any]:
    delta=np.asarray(baseline,float)-np.asarray(candidate,float);rng=np.random.default_rng(seed);boot=np.mean(delta[rng.integers(0,len(delta),size=(10000,len(delta)))],axis=1);signs=rng.choice((-1,1),size=(10000,len(delta)));observed=abs(float(np.mean(delta)));p=float((1+np.sum(np.abs(np.mean(delta*signs,axis=1))>=observed))/10001)
    return {"trajectories":len(delta),"mean_absolute_improvement":float(np.mean(delta)),"ci95":[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],"paired_permutation_p":p,"holm_p":p,"effect_size_dz":float(np.mean(delta)/(np.std(delta,ddof=1)+1e-12))}

def component_sign_accuracy(pred:np.ndarray,truth:np.ndarray,floor:np.ndarray)->float:
    p=np.asarray(pred,float).reshape(*pred.shape[:-2],8);t=np.asarray(truth,float).reshape(*truth.shape[:-2],8);f=np.asarray(floor,float).reshape(1,1,8);mask=np.abs(t)>=f
    return float(np.mean(np.sign(p[mask])==np.sign(t[mask]))) if np.any(mask) else float("nan")

def vector_angle_error_deg(pred:np.ndarray,truth:np.ndarray,floor:np.ndarray)->dict[str,float]:
    p=np.asarray(pred,float);t=np.asarray(truth,float);mask=np.linalg.norm(t,axis=-1)>=np.asarray(floor,float).reshape(1,1,4);pn=np.linalg.norm(p,axis=-1);mask&=pn>1e-12
    cos=np.sum(p*t,axis=-1)/np.maximum(pn*np.linalg.norm(t,axis=-1),1e-12);a=np.degrees(np.arccos(np.clip(cos,-1,1)))[mask]
    return {"mae":float(np.mean(a)) if len(a) else float("nan"),"p95":float(np.quantile(a,.95)) if len(a) else float("nan"),"count":int(len(a))}

def q_sign_accuracy(pred:np.ndarray,truth:np.ndarray,floor:np.ndarray)->float:
    p=np.asarray(pred,float);t=np.asarray(truth,float);mask=np.abs(t)>=np.asarray(floor,float).reshape(1,1,2)
    return float(np.mean(np.sign(p[mask])==np.sign(t[mask]))) if np.any(mask) else float("nan")

def reversal_event_metrics(pred:np.ndarray,truth:np.ndarray,floor:np.ndarray,radius_steps:int=10)->dict[str,float|int]:
    p=np.asarray(pred,float).reshape(len(pred),20,8);t=np.asarray(truth,float).reshape(len(truth),20,8);f=np.asarray(floor,float).reshape(1,1,8);active=np.abs(t)>=f;events=active[:,1:]&active[:,:-1]&(np.sign(t[:,1:])!=np.sign(t[:,:-1]));mask=np.zeros_like(active)
    for b,h,c in np.argwhere(events):mask[b,max(0,h+1-radius_steps):min(20,h+2+radius_steps),c]=True
    mask&=active;return {"accuracy":float(np.mean(np.sign(p[mask])==np.sign(t[mask]))) if np.any(mask) else float("nan"),"events":int(np.sum(events)),"samples":int(np.sum(mask))}

def algebraic_residual(points:np.ndarray,q:np.ndarray)->float:return float(np.max(np.abs(reconstruct_load(points)-np.asarray(q,float))))

def direction_metrics(pred:dict[str,np.ndarray],data:dict[str,Any],thresholds:dict[str,np.ndarray],sl:slice=slice(9,20))->dict[str,Any]:
    n=data["norms"];truth_points=(data["truth_f"][...,:8]*n["force_std"][:8]+n["force_mean"][:8]).reshape(len(data["truth_f"]),20,4,2);truth_q=data["truth_f"][...,8:10]*n["force_std"][8:10]+n["force_mean"][8:10]
    px=pred["state"];pf=np.concatenate([(pred["points"].reshape(len(px),20,8)-n["force_mean"][:8])/n["force_std"][:8],(pred["q"]-n["force_mean"][8:10])/n["force_std"][8:10]],axis=-1)
    base=nrmse_groups(px,pf,data["truth_x"],data["truth_f"],sl);angles=vector_angle_error_deg(pred["points"][:,sl],truth_points[:,sl],thresholds["point_floor"])
    rev=reversal_event_metrics(pred["points"],truth_points,thresholds["component_floor"])
    return {**base,"component_sign_accuracy":component_sign_accuracy(pred["points"][:,sl],truth_points[:,sl],thresholds["component_floor"]),"angle_mae_deg":angles["mae"],"angle_p95_deg":angles["p95"],"angle_count":angles["count"],"q_sign_accuracy":q_sign_accuracy(pred["q"][:,sl],truth_q[:,sl],thresholds["q_floor"]),"reversal_accuracy":rev["accuracy"],"reversal_events":rev["events"],"algebraic_residual_N":algebraic_residual(pred["points"],pred["q"]),"fallback_rate":float(np.mean(pred.get("fallback",np.zeros(pred["points"].shape[:-1],bool)))),"direction_invalid_rate":float(np.mean(~pred.get("valid",np.ones(pred["points"].shape[:-1],bool))))}
