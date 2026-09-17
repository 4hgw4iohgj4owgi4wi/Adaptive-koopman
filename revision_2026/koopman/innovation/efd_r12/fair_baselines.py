from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any
import numpy as np

from axial_decoder import decode, reconstruct_q

P_DIM=5
REC_BILINEAR_START=1+46+8+P_DIM


def _manifest(root: Path) -> list[dict[str, Any]]:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))["completed"]


def _static(meta:dict[str,Any])->np.ndarray:
    p=meta["params"]
    return np.asarray([p["payload"]["mass_kg"],p["vehicle"]["mu"],p["connector"]["stiffness_npm"],p["connector"]["damping_nspm"],p["connector"]["free_play_m"]],float)


def fit_norms(root: Path) -> dict[str, np.ndarray]:
    rows=[x for x in _manifest(root) if x["split"]=="train"]; sums={k:None for k in ("x","u","f")};sq={k:None for k in sums};counts={k:0 for k in sums};pvals=[]
    for row in rows:
        with np.load(root/"train"/row["base_file"],allow_pickle=False) as s:
            vals={"x":np.asarray(s["state46"],float),"u":np.asarray(s["control"],float),"f":np.asarray(s["force_payload"],float).reshape(-1,8)};pvals.append(_static(json.loads(str(s["metadata_json"].item()))))
        for k,v in vals.items():
            sums[k]=v.sum(0) if sums[k] is None else sums[k]+v.sum(0);sq[k]=(v*v).sum(0) if sq[k] is None else sq[k]+(v*v).sum(0);counts[k]+=len(v)
    out={}
    for k in sums:
        mean=sums[k]/counts[k];std=np.sqrt(np.maximum(sq[k]/counts[k]-mean*mean,1e-12));out[k+"_mean"]=mean;out[k+"_std"]=std
    pv=np.asarray(pvals);out["p_mean"]=pv.mean(0);out["p_std"]=np.maximum(pv.std(0),1e-12)
    return out


def load_windows(root: Path, split: str, norms: dict[str,np.ndarray]) -> dict[str,Any]:
    rows=[x for x in _manifest(root) if x["split"]==split];parts={k:[] for k in ("x0","u","y","force","current_force","p")};family=[];scenario=[];params=[]
    for fi,row in enumerate(rows):
        with np.load(root/split/row["base_file"],allow_pickle=False) as s:
            x=np.asarray(s["state46"],float);u=np.asarray(s["control"],float);f=np.asarray(s["force_payload"],float);meta=json.loads(str(s["metadata_json"].item()))
        origins=np.arange(0,len(u)-20+1,20);pstatic=_static(meta);parts["x0"].append((x[origins]-norms["x_mean"])/norms["x_std"]);parts["u"].append(np.asarray([(u[o:o+20]-norms["u_mean"])/norms["u_std"] for o in origins]));parts["y"].append(np.asarray([(x[o+1:o+21]-norms["x_mean"])/norms["x_std"] for o in origins]));parts["force"].append(np.asarray([(f[o+1:o+21].reshape(20,8)-norms["f_mean"])/norms["f_std"] for o in origins]));parts["current_force"].append(f[origins]);parts["p"].append(np.repeat(((pstatic-norms["p_mean"])/norms["p_std"])[None],len(origins),axis=0))
        family.extend([fi]*len(origins));scenario.extend([row["scenario"]]*len(origins));p=meta["params"]["connector"];params.extend([[p["stiffness_npm"],p["damping_nspm"],p["free_play_m"]]]*len(origins))
    return {**{k:np.concatenate(v).astype(np.float32) for k,v in parts.items()},"family":np.asarray(family),"scenario":np.asarray(scenario),"params":np.asarray(params,float),"rows":rows}


def direct_feature(data:dict[str,Any],h:int)->np.ndarray:return np.c_[np.ones(len(data["x0"])),data["x0"],data["p"],data["u"][:,:h].reshape(len(data["x0"]),-1)]


def _ridge(x:np.ndarray,y:np.ndarray,lam:float)->np.ndarray:
    g=x.T@x;g.flat[::len(g)+1]+=lam;return np.linalg.solve(g,x.T@y)


def fit_direct(train:dict[str,Any],target:str,lam:float)->list[dict[str,np.ndarray]]:
    y=train[target];out=[]
    for h in range(1,21):
        x=direct_feature(train,h);mean=x.mean(0);std=np.maximum(x.std(0),1e-8);mean[0]=0.;std[0]=1.;xs=(x-mean)/std
        out.append({"coef":_ridge(xs,y[:,h-1],lam),"mean":mean,"std":std})
    return out


def predict_direct(model:list[dict[str,np.ndarray]],data:dict[str,Any])->np.ndarray:return np.stack([((direct_feature(data,h)-model[h-1]["mean"])/model[h-1]["std"])@model[h-1]["coef"] for h in range(1,21)],axis=1)


def recursive_feature(x:np.ndarray,u:np.ndarray,p:np.ndarray,bilinear:bool)->np.ndarray:
    base=[np.ones((len(x),1)),x,u,p]
    if bilinear:base.append(np.einsum("ni,nj->nij",u,x).reshape(len(x),-1))
    return np.concatenate(base,axis=1)


def fit_recursive(train:dict[str,Any],lam:float,bilinear:bool)->np.ndarray:
    dim=REC_BILINEAR_START+(8*46 if bilinear else 0);g=np.zeros((dim,dim));c=np.zeros((dim,46))
    for start in range(0,len(train["x0"]),400):
        sl=slice(start,min(start+400,len(train["x0"])));prev=np.concatenate([train["x0"][sl,None],train["y"][sl,:-1]],axis=1).reshape(-1,46);u=train["u"][sl].reshape(-1,8);p=np.repeat(train["p"][sl],20,axis=0);target=train["y"][sl].reshape(-1,46);phi=recursive_feature(prev,u,p,bilinear);g+=phi.T@phi;c+=phi.T@target
    g.flat[::len(g)+1]+=lam;return np.linalg.solve(g,c)


def predict_recursive(w:np.ndarray,data:dict[str,Any],bilinear:bool,zero_n:bool=False,permute_u:bool=False)->np.ndarray:
    x=data["x0"].astype(float).copy();out=[];u=data["u"][:,::-1] if permute_u else data["u"]
    for h in range(20):
        phi=recursive_feature(x,u[:,h],data["p"],bilinear)
        if zero_n and bilinear:phi[:,REC_BILINEAR_START:]=0
        x=phi@w;out.append(x.copy())
    return np.stack(out,axis=1)


def project_irsp(w:np.ndarray,train:dict[str,Any],radius:float=.998)->tuple[np.ndarray,dict[str,Any]]:
    out=w.copy();a=out[1:47];norm=float(np.linalg.norm(a,2));gamma_a=min(1.,radius/max(norm,1e-12));out[1:47]*=gamma_a
    blocks=out[REC_BILINEAR_START:].reshape(8,46,46);uabs=np.max(np.abs(train["u"]),axis=(0,1));budget=sum(uabs[j]*np.linalg.norm(blocks[j],2) for j in range(8));remaining=max(radius-np.linalg.norm(out[1:47],2),0.);gamma_n=min(1.,remaining/max(budget,1e-12));out[REC_BILINEAR_START:]*=gamma_n
    bound=float(np.linalg.norm(out[1:47],2)+gamma_n*budget);return out,{"radius":radius,"A_norm_before":norm,"gamma_A":gamma_a,"bilinear_budget_before":float(budget),"gamma_N":gamma_n,"continuous_triangle_bound":bound,"certificate":bound<=radius+1e-10}


def metrics(pred_x:np.ndarray,pred_f:np.ndarray,data:dict[str,Any])->dict[str,float]:
    hs=slice(9,20);err=pred_x[:,hs]-data["y"][:,hs]
    state_core=float(np.sqrt(np.mean(err[...,:30]**2)));connector_disp=float(np.sqrt(np.mean(err[...,30:38]**2)));connector_vel=float(np.sqrt(np.mean(err[...,38:46]**2)));state=float(np.sqrt(np.mean(err**2)));force=float(np.sqrt(np.mean((pred_f[:,hs]-data["force"][:,hs])**2)))
    pf=pred_f*GLOBAL_NORMS["f_std"]+GLOBAL_NORMS["f_mean"];tf=data["force"]*GLOBAL_NORMS["f_std"]+GLOBAL_NORMS["f_mean"]
    q=reconstruct_q(pf.reshape(*pf.shape[:-1],4,2));tq=reconstruct_q(tf.reshape(*tf.shape[:-1],4,2));scale=np.maximum(np.std(tq[:,hs],axis=(0,1)),1e-8);load=float(np.sqrt(np.mean(((q[:,hs]-tq[:,hs])/scale)**2)))
    return {"state_core":state_core,"connector_disp":connector_disp,"connector_vel":connector_vel,"state_all":state,"force":force,"load":load,"J":(state_core+force+load)/3,"finite":bool(np.all(np.isfinite(pred_x)) and np.all(np.isfinite(pred_f)))}


def state_to_force(pred_x:np.ndarray,data:dict[str,Any],norms:dict[str,np.ndarray])->np.ndarray:
    physical=pred_x*norms["x_std"]+norms["x_mean"];d=physical[...,30:38].reshape(*physical.shape[:-1],4,2);v=physical[...,38:46].reshape(*physical.shape[:-1],4,2);out=[]
    for i in range(len(d)):
        k,c,g=data["params"][i];out.append(decode(d[i],v[i],k,c,g)["force_payload"].reshape(20,8))
    f=np.asarray(out);return (f-norms["f_mean"])/norms["f_std"]


GLOBAL_NORMS:dict[str,np.ndarray]={}


def train_and_validate(root:Path,ridge_grid:tuple[float,...])->dict[str,Any]:
    global GLOBAL_NORMS
    tic=time.perf_counter();norms=fit_norms(root);GLOBAL_NORMS=norms;train=load_windows(root,"train",norms);val=load_windows(root,"validation",norms);models={};results={}
    for name,bilinear in (("B0",False),("B1",True)):
        cand=[]
        for lam in ridge_grid:
            w=fit_recursive(train,lam,bilinear);px=predict_recursive(w,val,bilinear);pf=state_to_force(px,val,norms);cand.append((metrics(px,pf,val)["J"],lam,w,metrics(px,pf,val)))
        best=min(cand,key=lambda x:x[0]);models[name]=best[2];results[name]={"ridge":best[1],"metrics":best[3]}
    b2,cert=project_irsp(models["B1"],train);px=predict_recursive(b2,val,True);pf=state_to_force(px,val,norms);models["B2"]=b2;results["B2"]={"metrics":metrics(px,pf,val),"certificate":cert}
    for name,target in (("B3","y"),("B4","force")):
        cand=[]
        for lam in ridge_grid:
            m=fit_direct(train,target,lam);pred=predict_direct(m,val)
            if name=="B3":px=pred;pf=state_to_force(px,val,norms)
            else:px=predict_direct(models["B3"],val) if "B3" in models else val["y"]*0;pf=pred
            score=metrics(px,pf,val);cand.append((score["state_core"] if name=="B3" else (score["force"]+score["load"])/2,lam,m,score))
        best=min(cand,key=lambda x:x[0]);models[name]=best[2];results[name]={"ridge":best[1],"metrics":best[3]}
        if name=="B3":
            # Recompute B4 loop later with the selected B3 state; placeholder is now valid.
            pass
    # Correct B4's state component to selected B3 for its final reported J.
    b3x=predict_direct(models["B3"],val);b4f=predict_direct(models["B4"],val);results["B4"]["metrics"]=metrics(b3x,b4f,val)
    results["B1"]["zero_N_metrics"]=metrics(predict_recursive(models["B1"],val,True,True),state_to_force(predict_recursive(models["B1"],val,True,True),val,norms),val)
    results["B1"]["permuted_u_metrics"]=metrics(predict_recursive(models["B1"],val,True,False,True),state_to_force(predict_recursive(models["B1"],val,True,False,True),val,norms),val)
    outdir=root.parent/"models"/"fair_baselines";outdir.mkdir(parents=True,exist_ok=True);np.savez_compressed(outdir/"norms.npz",**norms)
    for name,m in models.items():
        if isinstance(m,np.ndarray):np.savez_compressed(outdir/f"{name}.npz",coef=m)
        else:np.savez_compressed(outdir/f"{name}.npz",**{f"{key}_h{i+1}":v for i,row in enumerate(m) for key,v in row.items()})
    b3gain=(results["B0"]["metrics"]["state_core"]-results["B3"]["metrics"]["state_core"])/results["B0"]["metrics"]["state_core"]
    b4gain=(results["B3"]["metrics"]["force"]-results["B4"]["metrics"]["force"])/results["B3"]["metrics"]["force"]
    return {"results":results,"train_windows":len(train["x0"]),"validation_windows":len(val["x0"]),"B3_core_state_gain_vs_B0":b3gain,"B4_force_gain_vs_B3":b4gain,
            "B3_reproduced":b3gain>=.08 and results["B3"]["metrics"]["finite"],"B4_learnable":b4gain>=.10 and results["B4"]["metrics"]["finite"],"development_read":False,"wall_time_s":time.perf_counter()-tic}
