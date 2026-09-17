from __future__ import annotations
import json,sys,time
from pathlib import Path
from typing import Any
import numpy as np

H=20

def _p(meta:dict[str,Any])->np.ndarray:
 p=meta["params"];return np.asarray([p["payload"]["mass_kg"],p["vehicle"]["mu"],p["connector"]["stiffness_npm"],p["connector"]["damping_nspm"],p["connector"]["free_play_m"]],float)

def rows(root:Path,splits:tuple[str,...])->list[dict[str,Any]]:
 manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))["completed"];out=[]
 for row in manifest:
  if row["split"] not in splits:continue
  with np.load(root/row["split"]/row["base_file"],allow_pickle=False) as s:
   x=np.asarray(s["state46"],float);u=np.asarray(s["control"],float);state30=np.asarray(s["state30"],float);force=np.asarray(s["force_payload"],float).reshape(-1,8);q=np.asarray(s["q"],float);meta=json.loads(str(s["metadata_json"].item()))
  rate=np.vstack([np.zeros((1,8)),np.diff(force,axis=0)/.02]);fo=np.c_[force,q,rate]
  meta.update({"split":row["split"],"scenario":row["scenario"],"physical_scene":row["scenario"],"seed":row["seed"],"base_family_id":row["base_family_id"],"p_static":_p(meta).tolist()})
  out.append({"meta":meta,"arrays":{"s3_deform":x,"u1_four":u,"s2_four":state30,"force_output":fo,"force_body":force.reshape(-1,4,2)}})
 return out

def _family_score(result:dict[str,Any])->float:
 groups={}
 for r in result["window_rows"]:groups.setdefault(r["trajectory"],[]).append(r["J_pred"])
 return float(np.mean([np.mean(v) for v in groups.values()]))

def _compact(result:dict[str,Any])->dict[str,Any]:
 groups={};scenes={}
 for r in result["window_rows"]:
  groups.setdefault(r["trajectory"],[]).append(r["J_pred"]);scenes.setdefault(r["trajectory"].split("|")[0],[]).append(r["J_pred"])
 return {"family_macro_J":float(np.mean([np.mean(v) for v in groups.values()])),"scenario_macro_J":float(np.mean([np.mean(v) for v in scenes.values()])),"micro_J":result["micro_J_pred"],"macro_by_label":result["macro_by_label"],"horizon_nrmse":result["horizon_nrmse"],"nonfinite_rate":result["nonfinite_rate"],"divergence_rate":result["divergence_rate"],"families":len(groups),"windows":len(result["window_rows"])}

def _windows(rs:list[dict[str,Any]],norms:dict[str,np.ndarray],pnorm:tuple[np.ndarray,np.ndarray]|None=None)->dict[str,Any]:
 parts={k:[] for k in ("x0","u","p","y")};family=[];scenario=[]
 ptrain=np.asarray([r["meta"]["p_static"] for r in rs]);pm=ptrain.mean(0) if pnorm is None else pnorm[0];ps=np.maximum(ptrain.std(0),1e-12) if pnorm is None else pnorm[1]
 for i,r in enumerate(rs):
  a=r["arrays"];x=(a["s3_deform"]-norms["x_mean"])/norms["x_std"];u=(a["u1_four"]-norms["u_mean"])/norms["u_std"];f=(a["force_output"]-norms["force_mean"])/norms["force_std"];o=np.arange(0,len(u)-H+1,H)
  parts["x0"].append(x[o]);parts["u"].append(np.asarray([u[j:j+H] for j in o]));parts["p"].append(np.repeat(((np.asarray(r["meta"]["p_static"])-pm)/ps)[None],len(o),0));parts["y"].append(np.asarray([np.c_[x[j+1:j+H+1],f[j+1:j+H+1]] for j in o]));family.extend([i]*len(o));scenario.extend([r["meta"]["scenario"]]*len(o))
 return {**{k:np.concatenate(v) for k,v in parts.items()},"family":np.asarray(family),"scenario":np.asarray(scenario),"p_mean":pm,"p_std":ps}

def _feature(d:dict[str,Any],h:int)->np.ndarray:return np.c_[np.ones(len(d["x0"])),d["x0"],d["p"],d["u"][:,:h].reshape(len(d["x0"]),-1)]
def _ridge(x:np.ndarray,y:np.ndarray,lam:float)->np.ndarray:
 g=x.T@x;g.flat[::len(g)+1]+=lam;return np.linalg.solve(g,x.T@y)
def _fit_direct(train:dict[str,Any],indices:np.ndarray,ridges:tuple[float,...],val:dict[str,Any])->tuple[list[dict[str,np.ndarray]],float]:
 model=[]
 for h in range(1,H+1):
  xt=_feature(train,h)[indices];yt=train["y"][indices,h-1];mu=xt.mean(0);sd=np.maximum(xt.std(0),1e-8);best=None
  for lam in ridges:
   w=_ridge((xt-mu)/sd,yt,lam);pv=((_feature(val,h)-mu)/sd)@w;e=pv-val["y"][:,h-1];score=float(np.sqrt(np.mean(e[:,:46]**2))+np.sqrt(np.mean(e[:,46:54]**2))+np.sqrt(np.mean(e[:,54:56]**2)))
   if best is None or score<best[0]:best=(score,w,lam)
  model.append({"coef":best[1],"mean":mu,"std":sd,"ridge":best[2]})
 return model,float(np.mean([x["ridge"] for x in model]))
def _predict(model:list[dict[str,np.ndarray]],d:dict[str,Any])->np.ndarray:return np.stack([((_feature(d,h)-model[h-1]["mean"])/model[h-1]["std"])@model[h-1]["coef"] for h in range(1,H+1)],1)
def _fit_force(train:dict[str,Any],val:dict[str,Any],ridges:tuple[float,...])->list[dict[str,np.ndarray]]:
 out=[]
 for h in range(1,H+1):
  xt=_feature(train,h);yt=train["y"][:,h-1,46:];mu=xt.mean(0);sd=np.maximum(xt.std(0),1e-8);best=None
  for lam in ridges:
   w=_ridge((xt-mu)/sd,yt,lam);e=((_feature(val,h)-mu)/sd)@w-val["y"][:,h-1,46:];score=float(np.sqrt(np.mean(e[:,:8]**2))+np.sqrt(np.mean(e[:,8:10]**2)))
   if best is None or score<best[0]:best=(score,w,lam)
  out.append({"coef":best[1],"mean":mu,"std":sd,"ridge":best[2]})
 return out
def _direct_metrics(pred:np.ndarray,d:dict[str,Any])->dict[str,Any]:
 hs=slice(9,20);e=pred[:,hs]-d["y"][:,hs];vals=[];by_scene={}
 for fam in np.unique(d["family"]):
  q=d["family"]==fam;state=np.sqrt(np.mean(e[q,:,:46]**2));force=np.sqrt(np.mean(e[q,:,46:54]**2));load=np.sqrt(np.mean(e[q,:,54:56]**2));j=(state+force+load)/3;vals.append(j);by_scene.setdefault(d["scenario"][np.where(q)[0][0]],[]).append(j)
 return {"family_macro_J":float(np.mean(vals)),"scenario_macro_J":float(np.mean([np.mean(v) for v in by_scene.values()])),"state_core":float(np.sqrt(np.mean(e[:,:,:30]**2))),"state_all":float(np.sqrt(np.mean(e[:,:,:46]**2))),"force":float(np.sqrt(np.mean(e[:,:,46:54]**2))),"load":float(np.sqrt(np.mean(e[:,:,54:56]**2))),"families":len(vals),"finite":bool(np.all(np.isfinite(pred)))}

def train(project:Path,data_root:Path,results:Path,ridges:tuple[float,...],bootstrap_seeds:list[int])->dict[str,Any]:
 tic=time.perf_counter();koop=project/"revision_2026"/"koopman";sys.path.insert(0,str(koop));import compare_pipeline as cp
 rs=rows(data_root,("train","validation"));norms=cp.train_moments(rs);labels=cp.derive_labels(rs);models={};reports={}
 specs=(("V-ARX46-U8","raw"),("V-FL92-U8","linear"))
 for mid,kind in specs:
  cand=[]
  for lam in ridges:
   m=cp.fit_simple(rs,norms,kind,lam,mid);ev=cp.evaluate(m,rs,"validation",norms,labels);cand.append((_family_score(ev),m,ev,lam))
  b=min(cand,key=lambda x:x[0]);models[mid]=b[1];reports[mid]={"ridge":b[3],"metrics":_compact(b[2]),"p_static":"recorded but unsupported by frozen historical transition interface; explicit input disadvantage"}
 hist=cp.all_frozen_models();rank=int(hist["K3"]["rank"])
 for mid,fit in (("V-FB92-U8",lambda lam:cp.fit_full_fixed(rs,norms,lam,mid)),("V-SB92-U8",lambda lam:cp.fit_struct_fixed(rs,norms,lam,rank,mid))):
  cand=[]
  for lam in ridges:
   m=fit(lam);ev=cp.evaluate(m,rs,"validation",norms,labels);cand.append((_family_score(ev),m,ev,lam))
  b=min(cand,key=lambda x:x[0]);models[mid]=b[1];reports[mid]={"ridge":b[3],"rank":b[1].get("rank"),"metrics":_compact(b[2]),"p_static":"recorded but unsupported by frozen historical transition interface; explicit input disadvantage"}
  reports[mid]["zero_N"]=_compact(cp.evaluate(b[1],rs,"validation",norms,labels,ablation="zero"));reports[mid]["control_permutation"]=_compact(cp.evaluate(b[1],rs,"validation",norms,labels,ablation="permute"))
 out=results/"models";out.mkdir(parents=True,exist_ok=True)
 for mid,m in models.items():cp.save_model(out/f"{mid}.npz",m)
 trainw=_windows([r for r in rs if r["meta"]["split"]=="train"],norms);valw=_windows([r for r in rs if r["meta"]["split"]=="validation"],norms,(trainw["p_mean"],trainw["p_std"]));direct=[]
 for seed in bootstrap_seeds:
  rng=np.random.default_rng(seed);fams=np.unique(trainw["family"]);sample=rng.choice(fams,len(fams),replace=True);idx=np.concatenate([np.where(trainw["family"]==f)[0] for f in sample]);m,_=_fit_direct(trainw,idx,ridges,valw);pred=_predict(m,valw);met=_direct_metrics(pred,valw);direct.append((met["family_macro_J"],seed,m,met))
 direct.sort(key=lambda x:x[0]);rep=direct[len(direct)//2];reports["V-H2-64-U8"]={"representative_seed":rep[1],"metrics":rep[3],"bootstrap":[{"seed":x[1],"metrics":x[3]} for x in direct],"outputs":64};np.savez_compressed(out/"V-H2-64-U8.npz",**{f"{k}_h{i+1}":v for i,row in enumerate(rep[2]) for k,v in row.items()})
 fm=_fit_force(trainw,valw,ridges);fp=_predict(fm,valw);fe=fp[:,9:]-valw["y"][:,9:,46:];reports["V-F5-U8"]={"force":float(np.sqrt(np.mean(fe[:,:,:8]**2))),"load":float(np.sqrt(np.mean(fe[:,:,8:10]**2))),"finite":bool(np.all(np.isfinite(fp))),"role":"direct force upper bound"};np.savez_compressed(out/"V-F5-U8.npz",**{f"{k}_h{i+1}":v for i,row in enumerate(fm) for k,v in row.items()})
 f1=reports["V-FL92-U8"]["metrics"]["family_macro_J"];gates={}
 for mid in ("V-FB92-U8","V-SB92-U8"):
  m=reports[mid];gain=(f1-m["metrics"]["family_macro_J"])/f1;zero=(m["zero_N"]["family_macro_J"]-m["metrics"]["family_macro_J"])/m["metrics"]["family_macro_J"];gates[mid]={"J_gain_vs_FL":gain,"zero_N_degradation":zero,"passed":False,"reason":"family CI and 4/5 bootstrap not yet established"}
 return {"methods":reports,"bilinear_gates":gates,"audit_completed":True,"development_read":False,"train_families":256,"validation_families":96,"wall_time_s":time.perf_counter()-tic}
