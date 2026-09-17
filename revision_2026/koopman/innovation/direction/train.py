from __future__ import annotations
import json,time
from pathlib import Path
from typing import Any
import numpy as np
from audit import sha256
from dataset import axial_targets,feature
from magnitude_head import DirectAxialMagnitudeHead,DirectPointHead
from metrics import direction_metrics
from predictors import structured_predictions,add_p5

def fit_thresholds(train:dict[str,Any])->dict[str,np.ndarray|float]:
    target=axial_targets(train);points=target["points"];mag=np.linalg.norm(points,axis=-1)
    point=np.asarray([np.quantile(mag[...,i][mag[...,i]>1e-9],.1) for i in range(4)])
    component=np.asarray([np.quantile(np.abs(points.reshape(len(points),20,8)[...,i])[np.abs(points.reshape(len(points),20,8)[...,i])>1e-9],.1) for i in range(8)])
    n=train["norms"];q=train["truth_f"][...,8:10]*n["force_std"][8:10]+n["force_mean"][8:10];qfloor=np.asarray([np.quantile(np.abs(q[...,i])[np.abs(q[...,i])>1e-9],.1) for i in range(2)])
    active=mag>=point.reshape(1,1,4);dn=target["displacement_norm"];direction_floor=float(max(1e-6,np.quantile(dn[active],.01)))
    scale=np.asarray([np.median(target["magnitude"][...,i][active[...,i]]) for i in range(4)])
    return {"point_floor":point,"component_floor":component,"q_floor":qfloor,"direction_floor":direction_floor,"base_scale":np.maximum(scale,1e-6)}

def _standardize(x:np.ndarray)->tuple[np.ndarray,np.ndarray,np.ndarray]:
    mean=np.mean(x,axis=0);std=np.std(x,axis=0);mean[0]=0.;std[0]=1.;std=np.maximum(std,1e-8);return (x-mean)/std,mean,std

def _ridge(x:np.ndarray,y:np.ndarray,lam:float)->np.ndarray:
    gram=x.T@x;gram.flat[::len(gram)+1]+=lam;return np.linalg.solve(gram,x.T@y)

def _bootstrap_indices(data:dict[str,Any],seed:int)->tuple[np.ndarray,list[int]]:
    ids=np.unique(data["trajectory"]);rng=np.random.default_rng(seed);draw=ids[rng.integers(0,len(ids),size=len(ids))];idx=np.concatenate([np.flatnonzero(data["trajectory"]==i) for i in draw]);return idx,[int(x) for x in draw]

def fit_p4(train:dict[str,Any],validation:dict[str,Any],thresholds:dict[str,Any],seed:int,scale_factor:float,ridges:tuple[float,...])->tuple[DirectAxialMagnitudeHead,dict[str,Any]]:
    idx,draw=_bootstrap_indices(train,seed);target=axial_targets(train)["magnitude"];vtarget=axial_targets(validation)["magnitude"];scale=np.asarray(thresholds["base_scale"])*scale_factor;maxdim=1+46+20*8;coef=np.zeros((20,maxdim,4));means=np.zeros((20,maxdim));stds=np.ones((20,maxdim));dims=[];selected=[]
    for h in range(1,21):
        xb=feature(train,h)[idx];xv=feature(validation,h);xs,m,s=_standardize(xb);d=xs.shape[1];means[h-1,:d]=m;stds[h-1,:d]=s;dims.append(d);ratio=np.maximum(target[idx,h-1]/scale,1e-12);latent=np.where(ratio>40,ratio,np.log(np.expm1(ratio)+1e-12));best=None
        for lam in ridges:
            c=_ridge(xs,latent,lam);vp=scale*np.logaddexp(0.,((xv-m)/s)@c);score=float(np.mean((vp-vtarget[:,h-1])**2))
            if best is None or score<best[0]:best=(score,lam,c)
        coef[h-1,:d]=best[2];selected.append(float(best[1]))
    head=DirectAxialMagnitudeHead(coef,means,stds,np.asarray(dims),scale,np.asarray(thresholds["point_floor"]));return head,{"bootstrap_trajectory_ids":draw,"ridge_by_h":selected,"scale_factor":scale_factor}

def fit_p5(train:dict[str,Any],validation:dict[str,Any],seed:int,ridges:tuple[float,...])->tuple[DirectPointHead,dict[str,Any]]:
    idx,draw=_bootstrap_indices(train,seed);target=axial_targets(train)["points"].reshape(len(train["x0"]),20,8);vtarget=axial_targets(validation)["points"].reshape(len(validation["x0"]),20,8);maxdim=207;coef=np.zeros((20,maxdim,8));means=np.zeros((20,maxdim));stds=np.ones((20,maxdim));dims=[];selected=[]
    for h in range(1,21):
        xb=feature(train,h)[idx];xv=feature(validation,h);xs,m,s=_standardize(xb);d=xs.shape[1];means[h-1,:d]=m;stds[h-1,:d]=s;dims.append(d);best=None
        for lam in ridges:
            c=_ridge(xs,target[idx,h-1],lam);vp=((xv-m)/s)@c;score=float(np.mean((vp-vtarget[:,h-1])**2))
            if best is None or score<best[0]:best=(score,lam,c)
        coef[h-1,:d]=best[2];selected.append(float(best[1]))
    return DirectPointHead(coef,means,stds,np.asarray(dims)),{"bootstrap_trajectory_ids":draw,"ridge_by_h":selected}

def save_heads(path:Path,p4:DirectAxialMagnitudeHead,p5:DirectPointHead,meta:dict[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,p4_coef=p4.coef,p4_mean=p4.feature_mean,p4_std=p4.feature_std,p4_dims=p4.feature_dims,p4_scale=p4.force_scale,p4_floor=p4.force_floor,p5_coef=p5.coef,p5_mean=p5.feature_mean,p5_std=p5.feature_std,p5_dims=p5.feature_dims,metadata_json=np.asarray(json.dumps(meta,sort_keys=True)))

def load_heads(path:Path)->tuple[DirectAxialMagnitudeHead,DirectPointHead,dict[str,Any]]:
    with np.load(path,allow_pickle=False) as s:return DirectAxialMagnitudeHead(s["p4_coef"],s["p4_mean"],s["p4_std"],s["p4_dims"],s["p4_scale"],s["p4_floor"]),DirectPointHead(s["p5_coef"],s["p5_mean"],s["p5_std"],s["p5_dims"]),json.loads(str(s["metadata_json"].item()))

def _rank(metrics:dict[str,Any])->tuple[float,...]:
    return (metrics["divergence_rate"],-metrics["component_sign_accuracy"],-metrics["q_sign_accuracy"],metrics["force"],metrics["load"],metrics["state"],metrics["J_pred"])

def train_seed(train:dict[str,Any],validation:dict[str,Any],thresholds:dict[str,Any],seed:int,scale_grid:tuple[float,...],ridge_grid:tuple[float,...],model_dir:Path)->dict[str,Any]:
    tic=time.perf_counter();candidates=[]
    for scale in scale_grid:
        head,record=fit_p4(train,validation,thresholds,seed,scale,ridge_grid);pred=structured_predictions(validation,head,float(thresholds["direction_floor"]));m=direction_metrics(pred["P4"],validation,thresholds);candidates.append((head,record,m))
    p4,p4record,p4metrics=min(candidates,key=lambda x:_rank(x[2]));p5,p5record=fit_p5(train,validation,seed,ridge_grid);pred=structured_predictions(validation,p4,float(thresholds["direction_floor"]));add_p5(pred,validation,p5);metrics={k:direction_metrics(v,validation,thresholds) for k,v in pred.items()};meta={"seed":seed,"P4":p4record,"P5":p5record,"scale_candidates":[{"scale_factor":r[1]["scale_factor"],"metrics":r[2]} for r in candidates]};path=model_dir/f"direction_seed_{seed}.npz";save_heads(path,p4,p5,meta)
    return {"seed":seed,"model":path.name,"model_sha256":sha256(path),"wall_time_s":time.perf_counter()-tic,"selection":meta,"validation":metrics}

def prediction_runtime_p99_ms(data:dict[str,Any],head:DirectAxialMagnitudeHead,direction_floor:float,repeats:int=200)->dict[str,float]:
    n=min(9,len(data["x0"]));small={k:(v[:n] if isinstance(v,np.ndarray) and len(v)==len(data["x0"]) else v) for k,v in data.items()};times=[]
    for _ in range(repeats):
        tic=time.perf_counter();structured_predictions(small,head,direction_floor);times.append((time.perf_counter()-tic)*1000)
    return {"p50_ms":float(np.quantile(times,.5)),"p95_ms":float(np.quantile(times,.95)),"p99_ms":float(np.quantile(times,.99)),"batch":n,"repeats":repeats}
