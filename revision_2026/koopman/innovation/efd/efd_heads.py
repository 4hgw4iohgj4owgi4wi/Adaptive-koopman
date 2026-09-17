from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from feature_builder import causal_feature
from physics_decoder import unit,reconstruct_load

@dataclass
class EFDHead:
    coef:np.ndarray;mean:np.ndarray;std:np.ndarray;dims:np.ndarray;kind:str;force_scale:np.ndarray;theta_deg:float=0.
    def raw(self,x0:np.ndarray,u:np.ndarray,norms:dict[str,np.ndarray])->np.ndarray:
        out=[]
        for h in range(1,21):
            f=causal_feature(x0,u,h,norms);d=int(self.dims[h-1]);out.append(((f-self.mean[h-1,:d])/self.std[h-1,:d])@self.coef[h-1,:d])
        return np.stack(out,axis=1)
def _standardize(x:np.ndarray):
    m=x.mean(0);s=np.maximum(x.std(0),1e-8);m[0]=0;s[0]=1;return (x-m)/s,m,s
def _solve(x:np.ndarray,y:np.ndarray,lam:float):
    a=x.T@x;a.flat[::len(a)+1]+=lam;return np.linalg.solve(a,x.T@y)
def _geometry(data:dict):
    n=data["norms"];hx=data["h2"][...,:46]*n["x_std"]+n["x_mean"];hd=hx[...,30:38].reshape(len(hx),20,4,2);td=data["truth_x"]*n["x_std"]+n["x_mean"];td=td[...,30:38].reshape(len(td),20,4,2);n0,_=unit(hd);t0=np.stack([-n0[...,1],n0[...,0]],axis=-1);tf=data["truth_points"];tn,_=unit(tf);mag=np.linalg.norm(tf,axis=-1);return hx,hd,td,n0,t0,tn,mag
def targets_g(data:dict,scale:np.ndarray):
    _,hd,td,n0,t0,_,mag=_geometry(data);delta=td-hd;a=np.sum(delta*n0,axis=-1);b=np.sum(delta*t0,axis=-1);ratio=np.maximum(mag/scale,1e-12);m=np.where(ratio>40,ratio,np.log(np.expm1(ratio)+1e-12));return np.concatenate([a,b,m],axis=-1)
def targets_d(data:dict,scale:np.ndarray,theta_deg:float):
    _,_,_,n0,t0,tn,mag=_geometry(data);dot=np.sum(n0*tn,axis=-1);cross=np.sum(t0*tn,axis=-1);delta=np.arctan2(cross,dot);limit=np.radians(theta_deg);z=np.clip(np.tan(np.clip(delta,-limit,limit))/np.tan(limit),-.999,.999);r=np.arctanh(z);ratio=np.maximum(mag/scale,1e-12);m=np.where(ratio>40,ratio,np.log(np.expm1(ratio)+1e-12));return np.concatenate([r,m],axis=-1)
def fit(data:dict,kind:str,lam:float,theta_deg:float=0.,trajectory_indices:np.ndarray|None=None)->EFDHead:
    idx=np.arange(len(data["x0"])) if trajectory_indices is None else trajectory_indices;mag=np.linalg.norm(data["truth_points"],axis=-1);scale=np.asarray([np.median(mag[...,i][mag[...,i]>1e-9]) for i in range(4)]);y=targets_g(data,scale) if kind=="G" else targets_d(data,scale,theta_deg);maxd=1+47+160;outdim=12 if kind=="G" else 8;coef=np.zeros((20,maxd,outdim));means=np.zeros((20,maxd));stds=np.ones((20,maxd));dims=[]
    for h in range(1,21):
        x=causal_feature(data["x0"][idx],data["u"][idx],h,data["norms"]);xs,m,s=_standardize(x);d=x.shape[1];means[h-1,:d]=m;stds[h-1,:d]=s;dims.append(d);coef[h-1,:d]=_solve(xs,y[idx,h-1],lam)
    return EFDHead(coef,means,stds,np.asarray(dims),kind,scale,theta_deg)
def predict(head:EFDHead,data:dict,direction_floor:float)->dict[str,np.ndarray]:
    n=data["norms"];raw=head.raw(data["x0"],data["u"],n);hx=data["h2"][...,:46]*n["x_std"]+n["x_mean"];hd=hx[...,30:38].reshape(len(hx),20,4,2);n0,valid=unit(hd,direction_floor);t0=np.stack([-n0[...,1],n0[...,0]],axis=-1);current=(data["x0"]*n["x_std"]+n["x_mean"])[:,30:38].reshape(len(hx),4,2);cn,_=unit(current);active=None
    if head.kind=="G":a=raw[...,:4];b=raw[...,4:8];m=head.force_scale*np.logaddexp(0,raw[...,8:12]);d=hd+a[...,None]*n0+b[...,None]*t0;direction,dvalid=unit(d,direction_floor);fallback=~dvalid;direction=np.where(fallback[...,None],cn[:,None],direction);hx[...,30:38]=d.reshape(len(hx),20,8);valid=dvalid
    else:r=raw[...,:4];m=head.force_scale*np.logaddexp(0,raw[...,4:8]);beta=np.tan(np.radians(head.theta_deg))*np.tanh(r);direction=(n0+beta[...,None]*t0)/np.sqrt(1+beta**2)[...,None];fallback=~valid;direction=np.where(fallback[...,None],cn[:,None],direction)
    points=m[...,None]*direction;q=reconstruct_load(points);x=(hx-n["x_mean"])/n["x_std"];base_angle=np.degrees(np.arccos(np.clip(np.sum(direction*n0,axis=-1),-1,1)));return {"x":x,"points":points,"q":q,"valid":valid,"fallback":fallback,"correction_angle_deg":base_angle}
