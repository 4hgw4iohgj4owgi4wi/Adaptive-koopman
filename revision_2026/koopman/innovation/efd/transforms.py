from __future__ import annotations
import numpy as np
def rotate_global_x0(x0n:np.ndarray,norms:dict[str,np.ndarray],angle_deg:float)->np.ndarray:
    x=x0n*norms["x_std"]+norms["x_mean"];out=x.copy();a=np.radians(angle_deg);c,s=np.cos(a),np.sin(a);r=np.array([[c,-s],[s,c]])
    v=out[:,:24].reshape(len(out),4,6);p=out[:,24:30];v[...,:2]=v[...,:2]@r.T;p[:,:2]=p[:,:2]@r.T;v[...,2]+=a;p[:,2]+=a;out[:,:24]=v.reshape(len(out),24);out[:,24:30]=p;return (out-norms["x_mean"])/norms["x_std"]
def mirror_lr(x0n:np.ndarray,u:np.ndarray,norms:dict[str,np.ndarray])->tuple[np.ndarray,np.ndarray]:
    x=x0n*norms["x_std"]+norms["x_mean"];out=x.copy();perm=[1,0,3,2];v=x[:,:24].reshape(len(x),4,6)[:,perm].copy();v[...,1]*=-1;v[...,2]*=-1;v[...,4]*=-1;v[...,5]*=-1;p=x[:,24:30].copy();p[:,1]*=-1;p[:,2]*=-1;p[:,4]*=-1;p[:,5]*=-1;d=x[:,30:38].reshape(len(x),4,2)[:,perm].copy();d[...,1]*=-1;rv=x[:,38:46].reshape(len(x),4,2)[:,perm].copy();rv[...,1]*=-1;out[:,:24]=v.reshape(len(x),24);out[:,24:30]=p;out[:,30:38]=d.reshape(len(x),8);out[:,38:46]=rv.reshape(len(x),8);un=u*norms["u_std"]+norms["u_mean"];uc=un.reshape(len(u),20,4,2)[:,:,perm].copy();uc[...,1]*=-1;return (out-norms["x_mean"])/norms["x_std"],(uc.reshape(len(u),20,8)-norms["u_mean"])/norms["u_std"]
def mirror_points(p:np.ndarray)->np.ndarray:
    out=p[:,:, [1,0,3,2]].copy();out[...,1]*=-1;return out
