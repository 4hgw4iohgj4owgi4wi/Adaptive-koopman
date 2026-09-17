from __future__ import annotations
import json,sys,time
from pathlib import Path
from typing import Any
import numpy as np
from axial_decoder import decode,reconstruct_q
from equivariant_features import feature,mirror_matrix,symmetric_normalizer
from fair_vehicle_baselines import _ridge,_windows,rows
from reynolds import commutator,project_linear_map
from transforms import mirror_control,mirror_state,output_transform

def _dataset(rs:list[dict[str,Any]],norms:dict[str,np.ndarray],pnorm=None):
 d=_windows(rs,norms,pnorm);d["x_phys"]=d["x0"]*norms["x_std"]+norms["x_mean"];d["u_phys"]=d["u"]*norms["u_std"]+norms["u_mean"];return d
def _phi(d,h):return feature(d["x_phys"],d["u_phys"],h)
def _target(d,norms):return d["y"][:,:,30:46]*norms["x_std"][30:46]+norms["x_mean"][30:46]
def _fit(t,v,idx,h,augment,project):
 x=_phi(t,h)[idx];y=_target(t,NORMS)[idx,h-1];rp=mirror_matrix(h);ry=output_transform(True)
 if augment:
  xm=feature(mirror_state(t["x_phys"][idx]),mirror_control(t["u_phys"][idx]),h);ym=(y@ry.T);x=np.r_[x,xm];y=np.r_[y,ym]
 mu=x.mean(0);sd=np.maximum(x.std(0),1e-9);ymu=y.mean(0);ysd=np.maximum(y.std(0),1e-9)
 if augment or project:
  mu,sd=symmetric_normalizer(mu,sd,rp)
  # Outputs have no constant first component.  Do not apply the input-only
  # clamp that forces component 0 to mean=0 and std=1.
  ymu=.5*(ymu+ry@ymu);ysd=np.maximum(.5*(ysd+np.abs(ry)@ysd),1e-9)
 w=_ridge((x-mu)/sd,(y-ymu)/ysd,1e-6)
 if project:w=project_linear_map(w,rp,ry)
 return {"coef":w,"mean":mu,"std":sd,"ymean":ymu,"ystd":ysd,"commutator":commutator(w,rp,ry)}
def _pred(model,d):return np.stack([(((_phi(d,h)-model[h-1]["mean"])/model[h-1]["std"])@model[h-1]["coef"])*model[h-1]["ystd"]+model[h-1]["ymean"] for h in range(1,21)],1)
def _fl(project,model_path,d,norms):
 import compare_pipeline as cp;m=cp.load_model(model_path);x=[];f=[]
 for h in range(20):
  if h==0:z=np.asarray([cp.lift(m,q) for q in d["x_phys"]])
  z2=[];fn=[]
  for i in range(len(z)):
   zz,_=cp.model_step(m,z[i],d["u_phys"][i,h]);_,ff,_=cp.decode(m,zz);z2.append(zz);fn.append(ff)
  z=np.asarray(z2);x.append(z[:,1:47]);f.append(fn)
 xn=np.stack(x,1);return xn*norms["x_std"]+norms["x_mean"],np.stack(f,1)
def _metrics(g,d,norms,base_x,base_f):
 truth_x=d["y"][:,:,:46]*norms["x_std"]+norms["x_mean"];truth_f=d["y"][:,:,46:54]*norms["force_std"][:8]+norms["force_mean"][:8];hs=slice(9,20);params=d["p"]*d["p_std"]+d["p_mean"];predf=[]
 for i in range(len(g)):
  q=decode(g[i,:,:8].reshape(20,4,2),g[i,:,8:16].reshape(20,4,2),params[i,2],params[i,3],params[i,4]);predf.append(q["force_payload"].reshape(20,8))
 predf=np.asarray(predf);bf=base_f[:,:,:8]*norms["force_std"][:8]+norms["force_mean"][:8];geom_truth=truth_x[:,:,30:46];scale=norms["x_std"][30:46];fscale=norms["force_std"][:8];qscale=norms["force_std"][8:10]
 def vals(geom,force):
  de=np.sqrt(np.mean(((geom[:,hs,:8]-geom_truth[:,hs,:8])/scale[:8])**2));dv=np.sqrt(np.mean(((geom[:,hs,8:]-geom_truth[:,hs,8:])/scale[8:])**2));fe=np.sqrt(np.mean(((force[:,hs]-truth_f[:,hs])/fscale)**2));pq=reconstruct_q(force.reshape(*force.shape[:-1],4,2));tq=reconstruct_q(truth_f.reshape(*truth_f.shape[:-1],4,2));le=np.sqrt(np.mean(((pq[:,hs]-tq[:,hs])/qscale)**2));return de,dv,fe,le
 cand=vals(g,predf);base=vals(base_x[:,:,30:46],bf);gain=[(base[i]-cand[i])/base[i] for i in range(4)];return {"candidate":{"geometry":cand[0],"velocity":cand[1],"force":cand[2],"load":cand[3]},"baseline":{"geometry":base[0],"velocity":base[1],"force":base[2],"load":base[3]},"gains":gain,"finite":bool(np.all(np.isfinite(g)) and np.all(np.isfinite(predf)))}
NORMS={}
def run(project:Path,data_root:Path,u5:Path,results:Path,seeds:list[int])->dict[str,Any]:
 global NORMS;tic=time.perf_counter();koop=project/"revision_2026"/"koopman";sys.path.insert(0,str(koop));import compare_pipeline as cp
 rs=rows(data_root,("train","validation"));NORMS=cp.train_moments(rs);t=_dataset([r for r in rs if r["meta"]["split"]=="train"],NORMS);v=_dataset([r for r in rs if r["meta"]["split"]=="validation"],NORMS,(t["p_mean"],t["p_std"]));base_x,base_f=_fl(project,u5/"models"/"V-FL92-U8.npz",v,NORMS);reports={}
 for name,aug,proj in (("V-G0",False,False),("V-G1",True,False),("V-G2",True,True)):
  runs=[]
  for seed in seeds:
   rng=np.random.default_rng(seed);f=np.unique(t["family"]);sample=rng.choice(f,len(f),replace=True);idx=np.concatenate([np.where(t["family"]==q)[0] for q in sample]);m=[_fit(t,v,idx,h,aug,proj) for h in range(1,21)];g=_pred(m,v);met=_metrics(g,v,NORMS,base_x,base_f);runs.append((met["candidate"]["geometry"],seed,m,met))
  runs.sort(key=lambda x:x[0]);rep=runs[len(runs)//2];reports[name]={"representative_seed":rep[1],"metrics":rep[3],"bootstrap":[{"seed":x[1],"metrics":x[3]} for x in runs],"commutator_max":max(x["commutator"] for x in rep[2])};out=results/"models";out.mkdir(parents=True,exist_ok=True);np.savez_compressed(out/f"{name}.npz",**{f"{k}_h{i+1}":vv for i,row in enumerate(rep[2]) for k,vv in row.items()})
 reports["V-M"]=reports["V-G2"];g=reports["V-M"]["metrics"]["gains"];passed=bool(reports["V-G2"]["commutator_max"]<=1e-10 and g[0]>=.30 and g[1]>=.10 and g[2]>=.10 and g[3]>=.10 and all(x["metrics"]["finite"] for x in reports["V-G2"]["bootstrap"]))
 return {"methods":reports,"M_point_gate_passed":passed,"M_full_gate_passed":False,"full_gate_missing":["family paired CI","direction/reversal","unseen rotations","runtime"],"development_read":False,"wall_time_s":time.perf_counter()-tic}
