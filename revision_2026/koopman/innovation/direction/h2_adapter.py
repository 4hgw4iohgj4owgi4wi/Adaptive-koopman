from __future__ import annotations
from pathlib import Path
import numpy as np
from audit import sha256

EXPECTED="3828A4AD5D1DDDA532BD38FB3832A8B568458F55366B873321A17D043E72FDAC"

class FrozenH2StateAdapter:
    def __init__(self,model_path:Path,expected_sha256:str=EXPECTED):
        actual=sha256(model_path)
        if actual!=expected_sha256:raise ValueError(f"H2 hash {actual} != {expected_sha256}")
        with np.load(model_path,allow_pickle=False) as s:
            self.coef=np.asarray(s["coef"],float);self.mean=np.asarray(s["feature_mean"],float);self.std=np.asarray(s["feature_std"],float);self.dims=np.asarray(s["feature_dims"],int)
    def predict_full(self,x0:np.ndarray,u_future:np.ndarray)->np.ndarray:
        x=np.atleast_2d(np.asarray(x0,float));u=np.asarray(u_future,float)
        if u.ndim==2:u=u[None]
        out=[]
        for h in range(1,21):
            feature=np.c_[np.ones(len(x)),x,u[:,:h].reshape(len(x),-1)];d=int(self.dims[h-1]);out.append(((feature-self.mean[h-1,:d])/self.std[h-1,:d])@self.coef[h-1,:d])
        return np.stack(out,axis=1)
    def predict_s3(self,x0:np.ndarray,u_future:np.ndarray)->np.ndarray:return self.predict_full(x0,u_future)[...,:46]
