from __future__ import annotations

import json,math,time
from pathlib import Path
from typing import Any

import numpy as np

from audit_inputs import sha256
from baseline_cache import _context,H
from data_protocol import formal_jobs
from multihorizon import DirectMultiHorizonHead

RIDGES=(1e-8,1e-6,1e-4,1e-2); SEEDS=(151001,151002,151003,151004,151005); MAXD=1+46+20*8


def _dataset(project:Path,jobs:list[dict[str,Any]],norms:dict[str,np.ndarray])->dict[str,np.ndarray]:
    root=project/"revision_2026"/"koopman"/"innovation_results"/"d4r"/"formal"; xs=[]; us=[]; ys=[]; bx=[]; bf=[]; tids=[]
    for ti,job in enumerate(jobs):
        name=f"{job['split']}_{job['group']}_{job['seed']}.npz"
        with np.load(root/"trajectories"/name,allow_pickle=False) as r: state=np.asarray(r["s3_deform"],float); control=np.asarray(r["u1_four"],float)
        with np.load(root/"baseline_cache"/name,allow_pickle=False) as c:
            origins=np.asarray(c["origins"],int); tx=np.asarray(c["truth_x"],float); tf=np.asarray(c["truth_f"],float); kx=np.asarray(c["K1_x"],float); kf=np.asarray(c["K1_f"],float)
        xs.append((state[origins]-norms["x_mean"])/norms["x_std"]); us.append(np.asarray([(control[o:o+H]-norms["u_mean"])/norms["u_std"] for o in origins])); ys.append(np.concatenate([tx,tf],axis=2)); bx.append(kx); bf.append(kf); tids.extend([ti]*len(origins))
    return {"x0":np.concatenate(xs),"u":np.concatenate(us),"y":np.concatenate(ys),"base_x":np.concatenate(bx),"base_f":np.concatenate(bf),"trajectory":np.asarray(tids,int)}


def _feature(data:dict[str,np.ndarray],h:int)->np.ndarray: return np.c_[np.ones(len(data["x0"])),data["x0"],data["u"][:,:h].reshape(len(data["x0"]),-1)]


def _ridge(x:np.ndarray,y:np.ndarray,value:float)->np.ndarray: return np.linalg.solve(x.T@x+value*np.eye(x.shape[1]),x.T@y)


def _loss(pred:np.ndarray,true:np.ndarray,expected:np.ndarray,norms:dict[str,np.ndarray])->dict[str,float]:
    state=float(np.sqrt(np.mean((pred[:,:30]-true[:,:30])**2))); force=float(np.sqrt(np.mean((pred[:,46:54]-true[:,46:54])**2))); load=float(np.sqrt(np.mean((pred[:,54:56]-true[:,54:56])**2)))
    pp=pred[:,46:56]*norms["force_std"][:10]+norms["force_mean"][:10]; tt=true[:,46:56]*norms["force_std"][:10]+norms["force_mean"][:10]; mask=np.abs(tt)>=norms["force_sign_floor"][:10]
    direction=1.0-float(np.mean(np.sign(pp[mask])==np.sign(tt[mask]))) if np.any(mask) else 0.0; consistency=float(np.sqrt(np.mean((pred[:,:46]-expected)**2)))
    return {"state":state,"force":force,"load":load,"direction_loss":direction,"consistency":consistency,"loss":state+force+load+.1*direction+.05*consistency}


def _k1_expected(ctx:dict[str,Any],previous:np.ndarray,u:np.ndarray)->np.ndarray:
    cp,model=ctx["cp"],ctx["models"]["K1"]; z=cp.fixed_basis(previous); return np.c_[z,u]@model["transition"][:,1:47]


def fit_seed(ctx:dict[str,Any],train:dict[str,np.ndarray],validation:dict[str,np.ndarray],seed:int)->tuple[DirectMultiHorizonHead,dict[str,Any]]:
    rng=np.random.default_rng(seed); trajectories=np.unique(train["trajectory"]); sampled=rng.choice(trajectories,size=len(trajectories),replace=True); indices=np.concatenate([np.where(train["trajectory"]==t)[0] for t in sampled])
    coef=np.zeros((H,MAXD,64)); mean=np.zeros((H,MAXD)); std=np.ones((H,MAXD)); dims=[]; records=[]; previous=validation["x0"]
    for h in range(1,H+1):
        xt=_feature(train,h)[indices]; yt=train["y"][indices,h-1]; xv=_feature(validation,h); d=xt.shape[1]; mu=xt.mean(0); sd=np.where(xt.std(0)<1e-8,1.0,xt.std(0)); xnt=(xt-mu)/sd; xnv=(xv-mu)/sd
        expected=_k1_expected(ctx,previous,validation["u"][:,h-1]); candidates=[]; weights={}
        for ridge in RIDGES:
            w=_ridge(xnt,yt,ridge); pred=xnv@w; metric=_loss(pred,validation["y"][:,h-1],expected,ctx["norms"]); candidates.append({"ridge":ridge,**metric}); weights[ridge]=w
        best=min(candidates,key=lambda x:x["loss"]); prediction=xnv@weights[best["ridge"]]; previous=prediction[:,:46]
        coef[h-1,:d]=weights[best["ridge"]]; mean[h-1,:d]=mu; std[h-1,:d]=sd; dims.append(d); records.append({"h":h,"candidates":candidates,"selected_ridge":best["ridge"],"validation_loss":best})
    return DirectMultiHorizonHead(coef,mean,std,np.asarray(dims)),{"seed":seed,"horizons":records,"bootstrap_trajectories":len(sampled),"consistency_weight":.05,"consistency_grid":[0,.05,.1],"selection":"fixed preregistered total loss"}


def predict_dataset(model:DirectMultiHorizonHead,data:dict[str,np.ndarray])->np.ndarray:
    out=np.empty((len(data["x0"]),H,64))
    for h in range(1,H+1):
        x=_feature(data,h); d=int(model.feature_dims[h-1]); out[:,h-1]=((x-model.feature_mean[h-1,:d])/model.feature_std[h-1,:d])@model.coef[h-1,:d]
    return out


def _subset(pred:np.ndarray,true:np.ndarray,norms:dict[str,np.ndarray],sl:slice)->dict[str,float]:
    p=pred[:,sl]; t=true[:,sl]; state=float(np.sqrt(np.mean((p[...,:30]-t[...,:30])**2))); force=float(np.sqrt(np.mean((p[...,46:54]-t[...,46:54])**2))); load=float(np.sqrt(np.mean((p[...,54:56]-t[...,54:56])**2)))
    pp=p[...,46:56]*norms["force_std"][:10]+norms["force_mean"][:10]; tt=t[...,46:56]*norms["force_std"][:10]+norms["force_mean"][:10]; mask=np.abs(tt)>=norms["force_sign_floor"][:10]
    point_mask=mask[...,:8]; load_mask=mask[...,8:10]; point=float(np.mean(np.sign(pp[...,:8][point_mask])==np.sign(tt[...,:8][point_mask]))) if np.any(point_mask) else math.nan; load_dir=float(np.mean(np.sign(pp[...,8:10][load_mask])==np.sign(tt[...,8:10][load_mask]))) if np.any(load_mask) else math.nan
    return {"state":state,"force":force,"load":load,"J_pred":(state+force+load)/3,"point_direction":point,"load_direction":load_dir,"divergence_rate":float(np.mean(np.any(~np.isfinite(p),axis=(1,2))| (np.max(np.abs(p),axis=(1,2))>50)))}


def evaluate(model:DirectMultiHorizonHead,data:dict[str,np.ndarray],norms:dict[str,np.ndarray])->dict[str,Any]:
    pred=predict_dataset(model,data); base=np.concatenate([data["base_x"],data["base_f"]],axis=2); true=data["y"]
    return {"candidate":{"h1_5":_subset(pred,true,norms,slice(0,5)),"h10_20":_subset(pred,true,norms,slice(9,20)),"all":_subset(pred,true,norms,slice(0,20))},
            "baseline":{"h1_5":_subset(base,true,norms,slice(0,5)),"h10_20":_subset(base,true,norms,slice(9,20)),"all":_subset(base,true,norms,slice(0,20))},"prediction":pred}


def _trajectory_values(model:DirectMultiHorizonHead,data:dict[str,np.ndarray],norms:dict[str,np.ndarray])->tuple[np.ndarray,np.ndarray]:
    pred=predict_dataset(model,data); base=np.concatenate([data["base_x"],data["base_f"]],axis=2); values=[]; bases=[]
    for tid in np.unique(data["trajectory"]):
        use=data["trajectory"]==tid; values.append(_subset(pred[use],data["y"][use],norms,slice(9,20))["J_pred"]); bases.append(_subset(base[use],data["y"][use],norms,slice(9,20))["J_pred"])
    return np.asarray(values),np.asarray(bases)


def _runtime(model:DirectMultiHorizonHead,sample:dict[str,np.ndarray])->dict[str,float]:
    x=np.repeat(sample["x0"][:1],9,axis=0); u=np.repeat(sample["u"][:1],9,axis=0); data={"x0":x,"u":u}; times=[]
    for _ in range(1000):
        tick=time.perf_counter_ns()
        for h in range(1,H+1):
            f=_feature(data,h); d=int(model.feature_dims[h-1]); _=((f-model.feature_mean[h-1,:d])/model.feature_std[h-1,:d])@model.coef[h-1,:d]
        times.append((time.perf_counter_ns()-tick)/1e6)
    return {"nine_candidate_20step_p50_ms":float(np.quantile(times,.5)),"nine_candidate_20step_p99_ms":float(np.quantile(times,.99))}


def train_horizon(project:Path)->dict[str,Any]:
    root=project/"revision_2026"/"koopman"/"innovation_results"; selected=json.loads((root/"d4r"/"pilot"/"complete.json").read_text(encoding="utf-8"))["selected_high_config"]; jobs=formal_jobs(selected); ctx=_context(project); norms=ctx["norms"]
    train=_dataset(project,[j for j in jobs if j["split"]=="train"],norms); val=_dataset(project,[j for j in jobs if j["split"]=="validation"],norms); dev=_dataset(project,[j for j in jobs if j["split"]=="development"],norms)
    stage=root/"t4_h2"; models=stage/"models"; models.mkdir(parents=True,exist_ok=True); records=[]
    for seed in SEEDS:
        tic=time.perf_counter(); model,record=fit_seed(ctx,train,val,seed); validation=evaluate(model,val,norms); path=models/f"N2-seed-{seed}.npz"; np.savez_compressed(path,coef=model.coef,feature_mean=model.feature_mean,feature_std=model.feature_std,feature_dims=model.feature_dims,seed=seed)
        record.update({"validation":{"candidate":validation["candidate"],"baseline":validation["baseline"]},"model":str(path),"model_sha256":sha256(path),"wall_time_s":time.perf_counter()-tic}); records.append(record); (stage/f"seed_{seed}.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
        print(f"H2 seed={seed} val-long={validation['candidate']['h10_20']['J_pred']:.6g} base={validation['baseline']['h10_20']['J_pred']:.6g}",flush=True)
    order=sorted(records,key=lambda x:x["validation"]["candidate"]["h10_20"]["J_pred"]); representative=order[len(order)//2]
    with np.load(representative["model"],allow_pickle=False) as s: model=DirectMultiHorizonHead(s["coef"],s["feature_mean"],s["feature_std"],s["feature_dims"])
    evaluation=evaluate(model,dev,norms); cand=evaluation["candidate"]; base=evaluation["baseline"]; runtime=_runtime(model,dev); cv,bv=_trajectory_values(model,dev,norms); delta=bv-cv; rng=np.random.default_rng(152999); boot=np.mean(delta[rng.integers(0,len(delta),size=(10000,len(delta)))],axis=1); signs=rng.choice((-1,1),size=(10000,len(delta))); p=float((1+np.sum(np.abs(np.mean(delta*signs,axis=1))>=abs(float(np.mean(delta)))))/10001)
    imp=(base["h10_20"]["J_pred"]-cand["h10_20"]["J_pred"])/base["h10_20"]["J_pred"]; fi=(base["h10_20"]["force"]-cand["h10_20"]["force"])/base["h10_20"]["force"]; li=(base["h10_20"]["load"]-cand["h10_20"]["load"])/base["h10_20"]["load"]
    gates={"long_J_8pct":imp>=.08,"force_load":(fi>=.10 and li>=-.03) or (li>=.10 and fi>=-.03),"short_state":cand["h1_5"]["state"]<=1.03*base["h1_5"]["state"],"long_state":cand["h10_20"]["state"]<=1.03*base["h10_20"]["state"],
           "point_direction":cand["all"]["point_direction"]>=base["all"]["point_direction"]-.01,"load_direction":cand["all"]["load_direction"]>=base["all"]["load_direction"]-.01,"teacher_free":True,"runtime":runtime["nine_candidate_20step_p99_ms"]<8,
           "ci_holm":float(np.quantile(boot,.025))>0 and p<.05}
    result={"component":"H2","representative_seed":representative["seed"],"five_seed_validation":[{"seed":r["seed"],"J":r["validation"]["candidate"]["h10_20"]["J_pred"],"hash":r["model_sha256"]} for r in records],"development":{"candidate":cand,"baseline":base},"relative_improvement":imp,"force_improvement":fi,"load_improvement":li,
            "statistics":{"trajectories":len(delta),"ci95":[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],"paired_permutation_p":p,"holm_p":p,"effect_size_dz":float(np.mean(delta)/(np.std(delta,ddof=1)+1e-12))},"runtime":runtime,"teacher_free_audit":{"uses_truth_intermediate":False,"inputs":"x0 and u_future only"},"gates":gates,"passed":all(gates.values()),"model":representative["model"],"model_sha256":representative["model_sha256"]}
    (stage/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); return result
