from __future__ import annotations
import numpy as np
def unit(d:np.ndarray,floor:float=1e-6)->tuple[np.ndarray,np.ndarray]:
    n=np.linalg.norm(d,axis=-1);return d/np.maximum(n[...,None],1e-12),n>=floor
def reconstruct_load(p:np.ndarray)->np.ndarray:
    return np.stack([.5*((p[...,0,0]+p[...,1,0])-(p[...,2,0]+p[...,3,0])),.5*((p[...,0,1]+p[...,2,1])-(p[...,1,1]+p[...,3,1]))],axis=-1)
def causal_rate(p:np.ndarray,current:np.ndarray,dt:float=.02)->np.ndarray:
    out=np.empty_like(p);prev=current
    for h in range(p.shape[1]):out[:,h]=(p[:,h]-prev)/dt;prev=p[:,h]
    return out
