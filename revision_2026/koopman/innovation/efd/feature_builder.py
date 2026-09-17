from __future__ import annotations
import numpy as np
def canonical_state(x0n:np.ndarray,norms:dict[str,np.ndarray])->np.ndarray:
    x=np.asarray(x0n,float)*norms["x_std"]+norms["x_mean"];v=x[:,:24].reshape(len(x),4,6);p=x[:,24:30];yaw=p[:,2];c=np.cos(yaw);s=np.sin(yaw);rel=v[...,:2]-p[:,None,:2];rx=rel[...,0]*c[:,None]+rel[...,1]*s[:,None];ry=-rel[...,0]*s[:,None]+rel[...,1]*c[:,None];dyaw=v[...,2]-yaw[:,None];vehicle=np.stack([rx,ry,np.sin(dyaw),np.cos(dyaw),v[...,3],v[...,4],v[...,5]],axis=-1).reshape(len(x),28);payload=p[:,3:6];return np.c_[vehicle,payload,x[:,30:46]]
def causal_feature(x0n:np.ndarray,u:np.ndarray,h:int,norms:dict[str,np.ndarray])->np.ndarray:return np.c_[np.ones(len(x0n)),canonical_state(x0n,norms),u[:,:h].reshape(len(x0n),-1)]
