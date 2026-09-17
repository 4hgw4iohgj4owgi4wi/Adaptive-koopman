from __future__ import annotations

from collections import Counter
import numpy as np


def point_kinematics(displacement: np.ndarray, relative_velocity: np.ndarray, free_play_m: float) -> tuple[np.ndarray,np.ndarray]:
    d=np.asarray(displacement,float); v=np.asarray(relative_velocity,float); norm=np.linalg.norm(d,axis=-1)
    normal=d/np.maximum(norm[...,None],1e-12); penetration=np.maximum(norm-free_play_m,0.0); vn=np.sum(v*normal,axis=-1)
    return penetration,vn


def labels(displacement: np.ndarray, relative_velocity: np.ndarray, free_play_m: float,
           eps_p: float=1e-5, eps_v: float=2e-3) -> np.ndarray:
    p,vn=point_kinematics(displacement,relative_velocity,free_play_m); loaded=np.max(p,axis=1)>eps_p
    # A single connector can open while its opposite closes in a bend.  Using
    # any-point extrema would label almost every loaded bend as a transition.
    # The penetration-weighted normal speed is the causal array-level loading
    # coordinate: positive=net loading, negative=net unloading.
    vn_effective=np.sum(p*vn,axis=1)/np.maximum(np.sum(p,axis=1),1e-12)
    out=np.full(len(p),2,dtype=np.int8); out[~loaded]=0
    out[loaded&(vn_effective>eps_v)]=1; out[loaded&(vn_effective< -eps_v)]=3
    return out


def window_counts(displacement: np.ndarray, relative_velocity: np.ndarray, force_body: np.ndarray,
                  free_play_m: float, rated_force_n: float, eps_p: float=1e-5, eps_v: float=2e-3) -> dict[str,int]:
    lab=labels(displacement,relative_velocity,free_play_m,eps_p,eps_v); counts=Counter(); high=0
    for start in range(0,len(lab)-20+1,20):
        local=lab[start:start+20]; mode=int(np.bincount(local,minlength=4).argmax()); counts[f"R{mode}"]+=1
        peak=np.max(np.linalg.norm(force_body[start:start+20],axis=-1)); high+=int(peak>=0.8*rated_force_n)
    return {**{f"R{i}":counts[f"R{i}"] for i in range(4)},"L4_high":high,"windows":sum(counts.values())}


def continuous_summary(displacement: np.ndarray, relative_velocity: np.ndarray, free_play_m: float) -> dict[str,float]:
    p,vn=point_kinematics(displacement,relative_velocity,free_play_m)
    return {"penetration_p50":float(np.quantile(np.max(p,axis=1),.5)),"penetration_p95":float(np.quantile(np.max(p,axis=1),.95)),
            "abs_vn_p50":float(np.quantile(np.max(np.abs(vn),axis=1),.5)),"abs_vn_p95":float(np.quantile(np.max(np.abs(vn),axis=1),.95))}
