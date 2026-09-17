from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
def norms(project,rows):
 koop=project/'revision_2026'/'koopman';sys.path.insert(0,str(koop));import compare_pipeline as cp
 shim=[]
 for r in rows:shim.append({'meta':r['meta'],'arrays':{'s3_deform':r['arrays']['state46'],'u1_four':r['arrays']['control'],'s2_four':r['arrays']['state30'],'force_output':np.c_[r['arrays']['force_payload'].reshape(-1,8),r['arrays']['q'],np.zeros((len(r['arrays']['q']),8))]}})
 return cp.train_moments(shim)
def predict(project,model_path,w,norm):
 koop=project/'revision_2026'/'koopman';sys.path.insert(0,str(koop));import compare_pipeline as cp
 m=cp.load_model(model_path);x0=w['x0'];u=w['u'];states=[];forces=[];z=np.asarray([cp.lift(m,q) for q in x0])
 for h in range(20):
  zz=[];ff=[]
  for i in range(len(z)):
   zi,_=cp.model_step(m,z[i],u[i,h]);_,fn,xn=cp.decode(m,zi);zz.append(zi);ff.append(fn)
  z=np.asarray(zz);states.append(z[:,1:47]);forces.append(np.asarray(ff)[...,:8])
 state=np.stack(states,1)*norm['x_std']+norm['x_mean'];force=np.stack(forces,1)*norm['force_std'][:8]+norm['force_mean'][:8]
 return state,force
