from __future__ import annotations

import numpy as np


def connector_kinematics(x_s3:np.ndarray,free_play_m:float)->dict[str,np.ndarray]:
    x=np.asarray(x_s3,float); d=x[...,30:38].reshape(*x.shape[:-1],4,2); v=x[...,38:46].reshape(*x.shape[:-1],4,2)
    norm=np.linalg.norm(d,axis=-1); normal=d/np.maximum(norm[...,None],1e-12); p=np.maximum(norm-free_play_m,0.0); vn=np.sum(v*normal,axis=-1)
    effective=np.sum(p*vn,axis=-1)/np.maximum(np.sum(p,axis=-1),1e-12)
    return {"displacement":d,"relative_velocity":v,"penetration":p,"normal_velocity":vn,"p_max":np.max(p,axis=-1),"vn_effective":effective}


def causal_regime_features(history:np.ndarray,aoi:np.ndarray|None=None)->np.ndarray:
    x=np.asarray(history,float); latest=x[...,-1,:] if x.ndim>=3 else x
    previous=x[...,-2,:] if x.ndim>=3 and x.shape[-2]>1 else latest
    feature=np.concatenate([latest[...,24:30],latest[...,30:46],latest[...,30:46]-previous[...,30:46]],axis=-1)
    if aoi is not None: feature=np.concatenate([feature,np.asarray(aoi,float)],axis=-1)
    return feature


def regime_index(x_s3:np.ndarray,free_play_m:float,thresholds:dict[str,float])->np.ndarray:
    kin=connector_kinematics(x_s3,free_play_m); p=kin["p_max"]; v=kin["vn_effective"]
    out=np.full(np.shape(p),2,dtype=np.int8); loaded=p>float(thresholds["eps_p"]); out[~loaded]=0
    out[loaded&(v>float(thresholds["eps_v"]))]=1; out[loaded&(v< -float(thresholds["eps_v"]))]=3
    return out


def regime_weights(features:np.ndarray,thresholds:dict[str,float])->np.ndarray:
    # features must end with [p_max,vn_effective]; this function never accepts
    # a scenario ID or future quantity.
    f=np.asarray(features,float); p=f[...,-2]; v=f[...,-1]; idx=np.full(np.shape(p),2,dtype=int); loaded=p>thresholds["eps_p"]
    idx[~loaded]=0; idx[loaded&(v>thresholds["eps_v"])]=1; idx[loaded&(v< -thresholds["eps_v"])]=3
    return np.eye(4,dtype=float)[idx]


def apply_hysteresis(weights:np.ndarray,previous:np.ndarray,dwell_steps:int)->np.ndarray:
    proposed=np.asarray(weights,float); prior=np.asarray(previous,float)
    if dwell_steps>0 and np.argmax(proposed)!=np.argmax(prior): return prior.copy()
    return proposed.copy()
