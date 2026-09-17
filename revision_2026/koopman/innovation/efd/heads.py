from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from dataset import feature

@dataclass
class RidgeHead:
    coef:np.ndarray;mean:np.ndarray;std:np.ndarray;dims:np.ndarray;kind:str;scale:np.ndarray|None=None
    def latent(self,x0:np.ndarray,u:np.ndarray)->np.ndarray:
        out=[]
        for h in range(1,21):
            f=np.c_[np.ones(len(x0)),x0,u[:,:h].reshape(len(x0),-1)];d=int(self.dims[h-1]);out.append(((f-self.mean[h-1,:d])/self.std[h-1,:d])@self.coef[h-1,:d])
        return np.stack(out,axis=1)
    def predict(self,x0:np.ndarray,u:np.ndarray)->np.ndarray:
        z=self.latent(x0,u);return self.scale*np.logaddexp(0,z) if self.kind=="magnitude" else z.reshape(len(x0),20,4,2)

def _std(x:np.ndarray):
    m=np.mean(x,axis=0);s=np.maximum(np.std(x,axis=0),1e-8);m[0]=0;s[0]=1;return (x-m)/s,m,s
def _ridge(x:np.ndarray,y:np.ndarray,lam:float):
    a=x.T@x;a.flat[::len(a)+1]+=lam;return np.linalg.solve(a,x.T@y)
def fit_head(train:dict,validation:dict,kind:str,ridges:tuple[float,...])->tuple[RidgeHead,dict]:
    maxd=207;outdim=4 if kind=="magnitude" else 8;coef=np.zeros((20,maxd,outdim));means=np.zeros((20,maxd));stds=np.ones((20,maxd));dims=[];selected=[]
    if kind=="magnitude":
        td=train["truth_x"]*train["norms"]["x_std"]+train["norms"]["x_mean"];direction=td[...,30:38].reshape(len(td),20,4,2);direction/=np.maximum(np.linalg.norm(direction,axis=-1)[...,None],1e-12);target=np.maximum(np.sum(train["truth_points"]*direction,axis=-1),0);vd=validation["truth_x"]*validation["norms"]["x_std"]+validation["norms"]["x_mean"];vdir=vd[...,30:38].reshape(len(vd),20,4,2);vdir/=np.maximum(np.linalg.norm(vdir,axis=-1)[...,None],1e-12);vtarget=np.maximum(np.sum(validation["truth_points"]*vdir,axis=-1),0);scale=np.asarray([np.median(target[...,i][target[...,i]>1e-9]) for i in range(4)]);y=np.where(target/scale>40,target/scale,np.log(np.expm1(np.maximum(target/scale,1e-12))+1e-12))
    else:target=train["truth_points"].reshape(len(train["x0"]),20,8);vtarget=validation["truth_points"].reshape(len(validation["x0"]),20,8);y=target;scale=None
    for h in range(1,21):
        x=feature(train,h);xv=feature(validation,h);xs,m,s=_std(x);d=x.shape[1];means[h-1,:d]=m;stds[h-1,:d]=s;dims.append(d);best=None
        for lam in ridges:
            c=_ridge(xs,y[:,h-1],lam);raw=((xv-m)/s)@c;pred=scale*np.logaddexp(0,raw) if kind=="magnitude" else raw;score=float(np.mean((pred-vtarget[:,h-1])**2))
            if best is None or score<best[0] or (score==best[0] and lam>best[1]):best=(score,lam,c)
        coef[h-1,:d]=best[2];selected.append(best[1])
    return RidgeHead(coef,means,stds,np.asarray(dims),kind,scale),{"ridge_by_h":selected,"kind":kind,"fit":"full train deterministic; validation finite ridge selection"}
