from __future__ import annotations
import numpy as np

def unit_from_displacement(state_physical:np.ndarray,direction_floor:float)->tuple[np.ndarray,np.ndarray]:
    d=np.asarray(state_physical,float)[...,30:38].reshape(*state_physical.shape[:-1],4,2);norm=np.linalg.norm(d,axis=-1);return d/np.maximum(norm[...,None],1e-12),norm>=direction_floor

def reconstruct_points(magnitude:np.ndarray,direction:np.ndarray)->np.ndarray:return np.asarray(magnitude,float)[...,None]*np.asarray(direction,float)

def reconstruct_load(points:np.ndarray)->np.ndarray:
    p=np.asarray(points,float);qfr=.5*((p[...,0,0]+p[...,1,0])-(p[...,2,0]+p[...,3,0]));qlr=.5*((p[...,0,1]+p[...,2,1])-(p[...,1,1]+p[...,3,1]));return np.stack([qfr,qlr],axis=-1)

def causal_force_rate(points:np.ndarray,current_points:np.ndarray,dt:float=.02)->np.ndarray:
    p=np.asarray(points,float);current=np.asarray(current_points,float);out=np.empty_like(p);previous=current.copy()
    for h in range(p.shape[1]):out[:,h]=(p[:,h]-previous)/dt;previous=p[:,h]
    return out

def nominal_physics_decoder(state_normalized:np.ndarray,current_points:np.ndarray,norms:dict[str,np.ndarray])->tuple[np.ndarray,np.ndarray,np.ndarray]:
    x=np.asarray(state_normalized,float)*norms["x_std"]+norms["x_mean"];disp=x[...,30:38].reshape(*x.shape[:-1],4,2);vel=x[...,38:46].reshape(*x.shape[:-1],4,2);distance=np.linalg.norm(disp,axis=-1);normal=disp/np.maximum(distance[...,None],1e-12);penetration=np.maximum(distance-.002,0.);loading=np.maximum(np.sum(vel*normal,axis=-1),0.);points=(30000*penetration+3500*loading)[...,None]*normal;return points,reconstruct_load(points),causal_force_rate(points,current_points)

def manual_counterexample()->dict[str,float|bool]:
    points=np.asarray([[[[1.,0.],[-1.,0.],[-1.,0.],[1.,0.]]]])
    # A separate y-pattern has zero resultant but non-zero Q_LR.
    points[0,0,:,1]=[1.,-1.,1.,-1.];resultant=np.sum(points,axis=-2);q=reconstruct_load(points)
    return {"resultant_norm":float(np.linalg.norm(resultant)),"q_norm":float(np.linalg.norm(q)),"passed":bool(np.linalg.norm(resultant)<1e-12 and np.linalg.norm(q)>0)}
