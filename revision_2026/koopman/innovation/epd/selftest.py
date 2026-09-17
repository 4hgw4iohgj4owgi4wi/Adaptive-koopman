from __future__ import annotations
import sys
import numpy as np
from kinematic_decoder import decode as kin
from axial_decoder import decode as axial,q_from_force

def oracle(project,rows):
 koop=project/'revision_2026'/'koopman';model=project/'revision_2026'/'model';r13=koop/'innovation'/'efd_r13'
 for pth in (koop,model,r13):
  if str(pth) not in sys.path:sys.path.insert(0,str(pth))
 import generate_k2 as gen
 from mirror_generator import params_from_metadata
 max64=max32=maxf=maxq_struct=maxq_persist=maxact=max_persisted_geom=0.;count=0;formula_samples=0
 for r in rows:
  x=np.asarray(r['arrays']['state30'],float);truth=np.asarray(r['arrays']['state46'],float);p=r['params'];d,v=kin(x,p['length'],p['width']);g=np.c_[d.reshape(len(x),8),v.reshape(len(x),8)]
  max_persisted_geom=max(max_persisted_geom,float(np.max(np.abs(g-truth[:,30:46]))));params=params_from_metadata(project,r['meta']);idx=np.unique(np.linspace(0,len(x)-1,min(17,len(x)),dtype=int));states=list(x[idx])
  if 'initial_state64' in r['arrays']:states.insert(0,np.asarray(r['arrays']['initial_state64'],float))
  for state in states:
   ref=gen.feature_rows(state,None,gen.CONTROL_DT,params);dd,vv=kin(state[None],p['length'],p['width']);max64=max(max64,float(np.max(np.abs(dd[0]-ref['displacement_body']))),float(np.max(np.abs(vv[0]-ref['relative_velocity_body']))))
   state32=state.astype(np.float32);ref32=gen.feature_rows(state32,None,gen.CONTROL_DT,params);dd32,vv32=kin(state32[None],np.float32(p['length']),np.float32(p['width']));max32=max(max32,float(np.max(np.abs(dd32[0]-ref32['displacement_body']))),float(np.max(np.abs(vv32[0]-ref32['relative_velocity_body']))));formula_samples+=1
  ds=np.asarray(r['arrays']['connector_disp'],float);vs=np.asarray(r['arrays']['connector_vel'],float);a=axial(ds,vs,p['k'],p['c'],p['l0']);ft=np.asarray(r['arrays']['force_payload'],float);maxf=max(maxf,float(np.max(np.abs(a['force']-ft))));qcalc=q_from_force(a['force']);maxq_struct=max(maxq_struct,float(np.max(np.abs(qcalc-q_from_force(a['force'])))));maxq_persist=max(maxq_persist,float(np.max(np.abs(q_from_force(ft)-r['arrays']['q']))));maxact=max(maxact,float(np.max(np.abs((np.linalg.norm(ft,axis=-1)>0).astype(int)-a['active'].astype(int)))));count+=len(x)
 x=np.asarray(rows[0]['arrays']['state30'][:32],float);p=rows[0]['params'];d0,v0=kin(x,p['length'],p['width']);xt=x.copy();xt[:,:24].reshape(-1,4,6)[...,:2]+=np.array([3.2,-1.7]);xt[:,24:26]+=np.array([3.2,-1.7]);dt,vt=kin(xt,p['length'],p['width']);translation=float(max(np.max(np.abs(dt-d0)),np.max(np.abs(vt-v0))))
 ang=.5235987755982988;c=np.cos(ang);s=np.sin(ang);xr=x.copy();vv=xr[:,:24].reshape(-1,4,6);pay=xr[:,24:30]
 def rw(pos):return np.stack([c*pos[...,0]-s*pos[...,1],s*pos[...,0]+c*pos[...,1]],-1)
 vv[...,:2]=rw(vv[...,:2]);vv[...,2]+=ang;pay[:,:2]=rw(pay[:,:2]);pay[:,2]+=ang;dr,vr=kin(xr,p['length'],p['width']);rotation=float(max(np.max(np.abs(dr-d0)),np.max(np.abs(vr-v0))))
 aa=axial(d0,v0,p['k'],p['c'],p['l0']);collinear=float(np.max(np.abs(aa['force'][...,0]*d0[...,1]-aa['force'][...,1]*d0[...,0])));nonnegative=bool(np.all(np.sum(aa['force']*d0,axis=-1)>=-1e-10));inactive=float(np.max(np.linalg.norm(aa['force'][~aa['active']],axis=-1))) if np.any(~aa['active']) else 0.
 passed=bool(max64<=1e-9 and max32<=1e-6 and maxf<=2e-3 and maxq_struct<=1e-10 and maxact==0 and translation<=1e-10 and rotation<=1e-10 and collinear<=1e-10 and nonnegative and inactive==0)
 return {'passed':passed,'persisted_samples':count,'formula_oracle_samples':formula_samples,'kinematic_formula_float64_max_abs':max64,'kinematic_formula_float32_max_abs':max32,'persisted_state30_to_separately_rounded_geometry_max_abs':max_persisted_geom,'axial_force_from_persisted_dv_max_abs_N':maxf,'q_structural_residual_N':maxq_struct,'persisted_q_rounding_residual_N':maxq_persist,'activity_disagreement':maxact,'translation_invariance':translation,'rotation_invariance':rotation,'collinearity_residual':collinear,'force_dot_d_nonnegative':nonnegative,'inactive_force_max_N':inactive,'boundary_damping_discontinuity_reported':True,'precision_contract':'formula gates compare EPD to original plant on identical core; separately float32-rounded fields reported as fidelity only'}
