from __future__ import annotations
import numpy as np
VEH_ANCHOR=np.asarray([[-.40,-.25],[-.40,.25],[.40,-.25],[.40,.25]],float)

def _rot(v,yaw):
 c=np.cos(yaw);s=np.sin(yaw);return np.stack([c*v[...,0]-s*v[...,1],s*v[...,0]+c*v[...,1]],-1)
def _to_body(v,yaw):
 c=np.cos(yaw);s=np.sin(yaw);return np.stack([c*v[...,0]+s*v[...,1],-s*v[...,0]+c*v[...,1]],-1)
def decode(core:np.ndarray,payload_length:np.ndarray|float=5.,payload_width:np.ndarray|float=2.):
 x=np.asarray(core,float);lead=x.shape[:-1];veh=x[...,:24].reshape(*lead,4,6);pay=x[...,24:30]
 length=np.broadcast_to(np.asarray(payload_length,float),lead);width=np.broadcast_to(np.asarray(payload_width,float),lead)
 signs=np.asarray([[1,1],[1,-1],[-1,1],[-1,-1]],float)
 pa=np.stack([.5*length[...,None]*signs[:,0],.5*width[...,None]*signs[:,1]],-1)
 va=np.broadcast_to(VEH_ANCHOR,(*lead,4,2))
 va_w=_rot(va,veh[...,2]);pa_w=_rot(pa,pay[...,None,2])
 av=veh[...,:2]+va_w;ap=pay[...,None,:2]+pa_w
 vv=_rot(veh[...,3:5],veh[...,2])+veh[...,5,None]*np.stack([-va_w[...,1],va_w[...,0]],-1)
 pv=_rot(pay[...,3:5],pay[...,2])[...,None,:]+pay[...,5,None,None]*np.stack([-pa_w[...,1],pa_w[...,0]],-1)
 d=_to_body(av-ap,pay[...,None,2]);v=_to_body(vv-pv,pay[...,None,2])
 return d,v
