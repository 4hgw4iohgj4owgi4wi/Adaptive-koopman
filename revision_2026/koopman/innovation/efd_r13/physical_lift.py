from __future__ import annotations
import time
from pathlib import Path
from typing import Any
import numpy as np
from fair_vehicle_baselines import _ridge,_direct_metrics,_windows,rows

def _extras(d:dict[str,Any],level:int,norms:dict[str,np.ndarray])->np.ndarray:
 x=d["x0"]*norms["x_std"]+norms["x_mean"];v=x[:,:24].reshape(-1,4,6);p=x[:,24:30];out=[];rel_yaw=v[:,:,2]-p[:,None,2]
 if level>=1:out.extend([np.sin(rel_yaw),np.cos(rel_yaw)])
 if level>=2:
  delta=v[:,:,:2]-p[:,None,:2];c=np.cos(p[:,2])[:,None];s=np.sin(p[:,2])[:,None];body=np.stack([delta[:,:,0]*c+delta[:,:,1]*s,-delta[:,:,0]*s+delta[:,:,1]*c],-1);out.extend([body.reshape(len(x),-1),x[:,30:46]])
 if level>=3:
  ds=x[:,30:38].reshape(-1,4,2);vs=x[:,38:46].reshape(-1,4,2);n=ds/np.maximum(np.linalg.norm(ds,axis=-1,keepdims=True),1e-10);speed=np.sum(vs*n,axis=-1);free=d["p"][:,4]*d["p_std"][4]+d["p_mean"][4];penetration=np.maximum(np.linalg.norm(ds,axis=-1)-free[:,None],0.);active=(penetration>0).astype(float);out.extend([penetration, speed, active, (speed>0).astype(float)])
 if level>=4:
  u0=d["u"][:,0]*norms["u_std"]+norms["u_mean"];delta=u0[:,1::2];ax=u0[:,0::2];out.extend([v[:,:,3]*delta,v[:,:,3]*ax,v[:,:,5]*delta,v[:,:,4]*v[:,:,5]]);ds=x[:,30:38].reshape(-1,4,2);vs=x[:,38:46].reshape(-1,4,2);n=ds/np.maximum(np.linalg.norm(ds,axis=-1,keepdims=True),1e-10);speed=np.sum(vs*n,axis=-1);free=d["p"][:,4]*d["p_std"][4]+d["p_mean"][4];pen=np.maximum(np.linalg.norm(ds,axis=-1)-free[:,None],0.);act=(pen>0).astype(float);out.extend([pen*speed,act*speed,np.mean(v[:,:,3],1,keepdims=True)*np.mean(delta,1,keepdims=True),p[:,5:6]*(delta[:,0:1]+delta[:,2:3]-delta[:,1:2]-delta[:,3:4])])
 return np.concatenate([np.asarray(a).reshape(len(x),-1) for a in out],1) if out else np.empty((len(x),0))

def _feature(d:dict[str,Any],h:int,level:int,norms:dict[str,np.ndarray])->np.ndarray:return np.c_[np.ones(len(d["x0"])),d["x0"],d["p"],_extras(d,level,norms),d["u"][:,:h].reshape(len(d["x0"]),-1)]
def _fit(train:dict[str,Any],val:dict[str,Any],indices:np.ndarray,level:int,norms:dict[str,np.ndarray],ridges:tuple[float,...])->list[dict[str,np.ndarray]]:
 out=[]
 for h in range(1,21):
  xt=_feature(train,h,level,norms)[indices];yt=train["y"][indices,h-1];mu=xt.mean(0);sd=np.maximum(xt.std(0),1e-8);best=None;xv=(_feature(val,h,level,norms)-mu)/sd
  for lam in ridges:
   w=_ridge((xt-mu)/sd,yt,lam);e=xv@w-val["y"][:,h-1];score=float(np.sqrt(np.mean(e[:,:46]**2))+np.sqrt(np.mean(e[:,46:54]**2))+np.sqrt(np.mean(e[:,54:56]**2)))
   if best is None or score<best[0]:best=(score,w,lam)
  out.append({"coef":best[1],"mean":mu,"std":sd,"ridge":best[2]})
 return out
def _predict(model:list[dict[str,np.ndarray]],d:dict[str,Any],level:int,norms:dict[str,np.ndarray])->np.ndarray:return np.stack([((_feature(d,h,level,norms)-model[h-1]["mean"])/model[h-1]["std"])@model[h-1]["coef"] for h in range(1,21)],1)

def train(project:Path,data_root:Path,results:Path,ridges:tuple[float,...],seeds:list[int],fl_state_reference:float)->dict[str,Any]:
 import sys;koop=project/"revision_2026"/"koopman";sys.path.insert(0,str(koop));import compare_pipeline as cp
 tic=time.perf_counter();rs=rows(data_root,("train","validation"));norms=cp.train_moments(rs);tw=_windows([r for r in rs if r["meta"]["split"]=="train"],norms);vw=_windows([r for r in rs if r["meta"]["split"]=="validation"],norms,(tw["p_mean"],tw["p_std"]));reports={}
 for level in range(1,5):
  runs=[]
  for seed in seeds:
   rng=np.random.default_rng(seed);f=np.unique(tw["family"]);sample=rng.choice(f,len(f),replace=True);idx=np.concatenate([np.where(tw["family"]==q)[0] for q in sample]);m=_fit(tw,vw,idx,level,norms,ridges);pred=_predict(m,vw,level,norms);met=_direct_metrics(pred,vw);runs.append((met["family_macro_J"],seed,m,met))
  runs.sort(key=lambda x:x[0]);rep=runs[len(runs)//2];reports[f"V-P{level}"]={"representative_seed":rep[1],"metrics":rep[3],"bootstrap":[{"seed":x[1],"metrics":x[3]} for x in runs],"feature_dim_h20":len(rep[2][-1]["mean"]),"H3_passed":False,"reason":"state_core reference uses historical full-state metric and CI not yet positive"};out=results/"models";out.mkdir(parents=True,exist_ok=True);np.savez_compressed(out/f"V-P{level}.npz",**{f"{k}_h{i+1}":v for i,row in enumerate(rep[2]) for k,v in row.items()})
 return {"methods":reports,"all_failed":not any(x["H3_passed"] for x in reports.values()),"fallback_core":"V-FL92-U8","development_read":False,"wall_time_s":time.perf_counter()-tic}
