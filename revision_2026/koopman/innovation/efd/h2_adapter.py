from __future__ import annotations
from pathlib import Path
import hashlib,numpy as np

EXPECTED="3828A4AD5D1DDDA532BD38FB3832A8B568458F55366B873321A17D043E72FDAC"
def _hash(p:Path)->str:
    h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest().upper()
class FrozenH2:
    def __init__(self,path:Path):
        if _hash(path)!=EXPECTED:raise ValueError("H2 hash mismatch")
        with np.load(path,allow_pickle=False) as s:self.coef=s["coef"].astype(float);self.mean=s["feature_mean"].astype(float);self.std=s["feature_std"].astype(float);self.dims=s["feature_dims"].astype(int)
    def predict(self,x0:np.ndarray,u:np.ndarray)->np.ndarray:
        x0=np.asarray(x0,float);u=np.asarray(u,float);single=x0.ndim==1
        if single:x0=x0[None];u=u[None]
        out=[]
        for h in range(1,21):
            f=np.c_[np.ones(len(x0)),x0,u[:,:h].reshape(len(x0),-1)];d=int(self.dims[h-1]);out.append(((f-self.mean[h-1,:d])/self.std[h-1,:d])@self.coef[h-1,:d])
        y=np.stack(out,axis=1);return y[0] if single else y
