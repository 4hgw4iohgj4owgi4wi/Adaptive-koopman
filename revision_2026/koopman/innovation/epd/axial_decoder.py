from __future__ import annotations
import numpy as np
def q_from_force(f):
 a=np.asarray(f);return np.stack([.5*((a[...,0,0]+a[...,1,0])-(a[...,2,0]+a[...,3,0])),.5*((a[...,0,1]+a[...,2,1])-(a[...,1,1]+a[...,3,1]))],-1)
def decode(d,v,k,c,l0,eps=1e-12):
 d=np.asarray(d,float);v=np.asarray(v,float);lead=d.shape[:-2]
 k=np.broadcast_to(np.asarray(k,float),lead)[...,None];c=np.broadcast_to(np.asarray(c,float),lead)[...,None];l0=np.broadcast_to(np.asarray(l0,float),lead)[...,None]
 length=np.linalg.norm(d,axis=-1);n=d/np.maximum(length[...,None],eps);pen=np.maximum(length-l0,0.);active=pen>0
 vn=np.sum(n*v,axis=-1);vlog=np.where(active,vn,0.);mag=active*(k*pen+c*np.maximum(vn,0.));f=mag[...,None]*n
 return {'force':f,'q':q_from_force(f),'penetration':pen,'normal_speed':vn,'plant_normal_speed':vlog,'active':active,'magnitude':mag,'direction_valid':length>=eps}

