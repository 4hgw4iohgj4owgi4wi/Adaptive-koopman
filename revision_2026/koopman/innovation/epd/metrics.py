from __future__ import annotations
import numpy as np
from axial_decoder import q_from_force
def scales(train_rows):
 x=np.concatenate([r['arrays']['state46'] for r in train_rows]);f=np.concatenate([r['arrays']['force_payload'].reshape(-1,8) for r in train_rows]);q=np.concatenate([r['arrays']['q'] for r in train_rows]);return {'core':np.maximum(x[:,:30].std(0),1e-9),'d':np.maximum(x[:,30:38].std(0),1e-9),'v':np.maximum(x[:,38:46].std(0),1e-9),'f':np.maximum(f.std(0),1e-9),'q':np.maximum(q.std(0),1e-9)}
def evaluate(core,geom,force,w,s):
 hs=slice(9,20);truth=w['truth'];pd=geom[...,:8];pv=geom[...,8:];tf=w['force'].reshape(*w['force'].shape[:2],8);pf=force.reshape(*force.shape[:2],8);pq=q_from_force(force);tq=w['q'];vals=[]
 for fam in np.unique(w['family']):
  z=w['family']==fam
  def e(a,b,sc):return float(np.sqrt(np.mean(((a[z,hs]-b[z,hs])/sc)**2)))
  ec=e(core,truth[...,:30],s['core']);ed=e(pd,truth[...,30:38],s['d']);ev=e(pv,truth[...,38:46],s['v']);ef=e(pf,tf,s['f']);eq=e(pq,tq,s['q']);vals.append([ec,ed,ev,ef,eq,(ec+ef+eq)/3])
 a=np.mean(vals,0);return {'E_core':a[0],'E_d':a[1],'E_v':a[2],'E_F':a[3],'E_Q':a[4],'J_pred':a[5],'families':len(vals),'finite':bool(np.all(np.isfinite(core)) and np.all(np.isfinite(geom)) and np.all(np.isfinite(force)))}

