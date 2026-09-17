from __future__ import annotations

import argparse,json,math,sys,time
from collections import Counter,defaultdict
from pathlib import Path
from typing import Any

import numpy as np

HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path: sys.path.insert(0,str(HERE))
from baseline_cache import _context,H
from data_protocol import formal_jobs
from low_rank_regime import SharedBackboneRegimeResidual,ridge_low_rank
from regime_features import regime_index
from audit_inputs import sha256

RIDGES=(1e-8,1e-6,1e-4,1e-2); RANKS=(1,2,4,8); SEEDS=(151001,151002,151003,151004,151005)


def _load_raw(path:Path)->tuple[dict[str,np.ndarray],dict[str,Any]]:
    with np.load(path,allow_pickle=False) as s:
        arrays={k:np.asarray(s[k],float) for k in ("s3_deform","u1_four","force_output")}; meta=json.loads(str(s["metadata_json"].item()))
    return arrays,meta


def _one_step(ctx:dict[str,Any],arrays:dict[str,np.ndarray])->tuple[np.ndarray,np.ndarray,np.ndarray,np.ndarray]:
    cp,model,norms=ctx["cp"],ctx["models"]["K1"],ctx["norms"]
    xn=(arrays["s3_deform"]-norms["x_mean"])/norms["x_std"]; un=(arrays["u1_four"]-norms["u_mean"])/norms["u_std"]
    z=cp.fixed_basis(xn[:-1]); znext=np.c_[z,un]@model["transition"]; base=znext[:,1:47]
    return xn[:-1],un,base,xn[1:]-base


def _grams(project:Path,jobs:list[dict[str,Any]],ctx:dict[str,Any],thresholds:dict[str,float],seed:int)->tuple[np.ndarray,np.ndarray,np.ndarray]:
    rng=np.random.default_rng(seed); selected=rng.choice(len(jobs),size=len(jobs),replace=True)
    gram=np.zeros((4,55,55)); cross=np.zeros((4,55,46)); samples=np.zeros(4,dtype=int); raw=project/"revision_2026"/"koopman"/"innovation_results"/"d4r"/"formal"/"trajectories"
    for idx in selected:
        job=jobs[int(idx)]; arrays,meta=_load_raw(raw/f"{job['split']}_{job['group']}_{job['seed']}.npz"); xn,un,_,residual=_one_step(ctx,arrays)
        free=float(meta["params"]["connector"]["free_play_m"]); mode=regime_index(arrays["s3_deform"][:-1],free,thresholds); phi=np.c_[np.ones(len(xn)),xn,un]
        for m in range(4):
            use=mode==m
            if np.any(use): p=phi[use]; gram[m]+=p.T@p; cross[m]+=p.T@residual[use]; samples[m]+=int(np.sum(use))
    return gram,cross,samples


def _validation_rows(project:Path,jobs:list[dict[str,Any]],ctx:dict[str,Any],thresholds:dict[str,float])->list[tuple[np.ndarray,np.ndarray,np.ndarray,np.ndarray]]:
    out=[]; raw=project/"revision_2026"/"koopman"/"innovation_results"/"d4r"/"formal"/"trajectories"
    for job in jobs:
        arrays,meta=_load_raw(raw/f"{job['split']}_{job['group']}_{job['seed']}.npz"); xn,un,base,residual=_one_step(ctx,arrays)
        mode=regime_index(arrays["s3_deform"][:-1],float(meta["params"]["connector"]["free_play_m"]),thresholds); out.append((np.c_[np.ones(len(xn)),xn,un],base,residual,mode))
    return out


def _candidate_one_step(weights:np.ndarray,rows:list[tuple[np.ndarray,np.ndarray,np.ndarray,np.ndarray]])->dict[str,float]:
    sq=n=0; ratios=[]
    for phi,base,residual,mode in rows:
        corr=np.empty_like(residual)
        for m in range(4):
            use=mode==m
            if np.any(use): corr[use]=phi[use]@weights[m]
        raw_ratio=np.linalg.norm(corr,axis=1)/np.maximum(np.linalg.norm(base,axis=1),1e-12); scale=np.minimum(1.0,.25/np.maximum(raw_ratio,1e-12)); corr*=scale[:,None]
        error=corr-residual; sq+=float(np.sum(error*error)); n+=error.size; ratios.extend(np.minimum(raw_ratio,.25).tolist())
    return {"rmse":math.sqrt(sq/max(n,1)),"residual_ratio_p99":float(np.quantile(ratios,.99)),"samples":int(n/46)}


def _predict_regime(ctx:dict[str,Any],model:SharedBackboneRegimeResidual,raw:dict[str,np.ndarray],origin:int,mode:int)->tuple[np.ndarray,np.ndarray,np.ndarray]:
    cp,k1,norms=ctx["cp"],ctx["models"]["K1"],ctx["norms"]; current=raw["s3_deform"][origin].copy(); xs=[]; fs=[]; ratios=[]; alpha=np.eye(4)[mode]
    for h in range(H):
        xn=(current-norms["x_mean"])/norms["x_std"]; un=(raw["u1_four"][origin+h]-norms["u_mean"])/norms["u_std"]
        z=cp.lift(k1,current); znext,_=cp.model_step(k1,z,raw["u1_four"][origin+h]); _,_,base=cp.decode(k1,znext)
        corrected,ratio=model.step(base,xn,un,alpha); current=corrected*norms["x_std"]+norms["x_mean"]
        _,fn,_=cp.decode(k1,cp.lift(k1,current)); xs.append(corrected); fs.append(fn); ratios.append(ratio)
    return np.asarray(xs),np.asarray(fs),np.asarray(ratios)


def _metrics(predx:np.ndarray,predf:np.ndarray,truex:np.ndarray,truef:np.ndarray,norms:dict[str,np.ndarray])->dict[str,float]:
    state=float(np.sqrt(np.mean((predx[...,:30]-truex[...,:30])**2))); force=float(np.sqrt(np.mean((predf[...,:8]-truef[...,:8])**2))); load=float(np.sqrt(np.mean((predf[...,8:10]-truef[...,8:10])**2)))
    pp=predf[...,:10]*norms["force_std"][:10]+norms["force_mean"][:10]; tt=truef[...,:10]*norms["force_std"][:10]+norms["force_mean"][:10]; floor=norms["force_sign_floor"][:10]
    mask=np.abs(tt)>=floor; direction=float(np.mean(np.sign(pp[mask])==np.sign(tt[mask]))) if np.any(mask) else math.nan
    return {"state":state,"force":force,"load":load,"J_pred":(state+force+load)/3,"direction_accuracy":direction,"diverged":float(not np.all(np.isfinite(predx)) or np.max(np.abs(predx))>50)}


def evaluate_regime(project:Path,jobs:list[dict[str,Any]],ctx:dict[str,Any],weights:np.ndarray,rank:int,thresholds:dict[str,float])->dict[str,Any]:
    root=project/"revision_2026"/"koopman"/"innovation_results"/"d4r"/"formal"; rawdir=root/"trajectories"; cachedir=root/"baseline_cache"; norms=ctx["norms"]
    candidate=SharedBackboneRegimeResidual(weights,rank); per={}; baseper={}; by=defaultdict(lambda:[[],[]]); ratios=[]; occupancy=Counter(); switches=steps=0
    for job in jobs:
        name=f"{job['split']}_{job['group']}_{job['seed']}.npz"; raw,meta=_load_raw(rawdir/name); free=float(meta["params"]["connector"]["free_play_m"])
        modes=regime_index(raw["s3_deform"],free,thresholds); stable=[]; current=int(modes[0]); last=0
        for k,proposed in enumerate(modes):
            if int(proposed)!=current and k-last>=50: current=int(proposed); last=k; switches+=1
            stable.append(current); occupancy[current]+=1; steps+=1
        with np.load(cachedir/name,allow_pickle=False) as c:
            origins=np.asarray(c["origins"],int); tx=np.asarray(c["truth_x"],float); tf=np.asarray(c["truth_f"],float); bx=np.asarray(c["K1_x"],float); bf=np.asarray(c["K1_f"],float)
        px=[]; pf=[]
        for wi,origin in enumerate(origins):
            x,f,r=_predict_regime(ctx,candidate,raw,int(origin),stable[int(origin)]); px.append(x); pf.append(f); ratios.extend(r.tolist())
            tag=f"R{stable[int(origin)]}"; by[tag][0].append(_metrics(x,f,tx[wi],tf[wi],norms)["J_pred"]); by[tag][1].append(_metrics(bx[wi],bf[wi],tx[wi],tf[wi],norms)["J_pred"])
        per[str(job["seed"])]=_metrics(np.asarray(px),np.asarray(pf),tx,tf,norms); baseper[str(job["seed"])]=_metrics(bx,bf,tx,tf,norms)
    def aggregate(rows:dict[str,dict[str,float]])->dict[str,float]: return {k:float(np.mean([v[k] for v in rows.values()])) for k in ("state","force","load","J_pred","direction_accuracy","diverged")}
    return {"candidate":aggregate(per),"baseline":aggregate(baseper),"per_trajectory":per,"baseline_per_trajectory":baseper,
            "by_regime":{k:{"candidate_J":float(np.mean(v[0])),"baseline_J":float(np.mean(v[1]))} for k,v in by.items()},
            "residual_ratio_p99":float(np.quantile(ratios,.99)),"occupancy":{f"R{k}":v/steps for k,v in occupancy.items()},"switch_rate_hz":switches/(steps*.02),"minimum_dwell_s":1.0}


def _paired_statistics(result:dict[str,Any],seed:int=151999)->dict[str,Any]:
    keys=sorted(result["per_trajectory"]); delta=np.asarray([result["baseline_per_trajectory"][k]["J_pred"]-result["per_trajectory"][k]["J_pred"] for k in keys]); rng=np.random.default_rng(seed)
    boot=np.mean(delta[rng.integers(0,len(delta),size=(10000,len(delta)))],axis=1); signs=rng.choice((-1,1),size=(10000,len(delta))); p=float((1+np.sum(np.abs(np.mean(delta*signs,axis=1))>=abs(float(np.mean(delta)))))/(10001))
    return {"trajectories":len(keys),"mean_improvement_absolute":float(np.mean(delta)),"ci95":[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],"paired_permutation_p":p,"holm_p":p,
            "effect_size_dz":float(np.mean(delta)/(np.std(delta,ddof=1)+1e-12))}


def train_regime(project:Path)->dict[str,Any]:
    root=project/"revision_2026"/"koopman"/"innovation_results"; formal=root/"d4r"/"formal"; selected=json.loads((root/"d4r"/"pilot"/"complete.json").read_text(encoding="utf-8"))["selected_high_config"]
    jobs=formal_jobs(selected); train=[x for x in jobs if x["split"]=="train"]; val=[x for x in jobs if x["split"]=="validation"]; dev=[x for x in jobs if x["split"]=="development"]
    thresholds=json.loads((formal/"regime_thresholds.json").read_text(encoding="utf-8")); ctx=_context(project); val_rows=_validation_rows(project,val,ctx,thresholds); stage=root/"t3_h1"; models=stage/"models"; models.mkdir(parents=True,exist_ok=True); records=[]
    for seed in SEEDS:
        tic=time.perf_counter(); gram,cross,samples=_grams(project,train,ctx,thresholds,seed); candidates=[]; artifacts={}
        for ridge in RIDGES:
            for rank in RANKS:
                weights=[]; diagnostics=[]
                for m in range(4): w,d=ridge_low_rank(gram[m],cross[m],ridge,rank); weights.append(w); diagnostics.append(d)
                weights=np.asarray(weights); metric=_candidate_one_step(weights,val_rows)
                full=evaluate_regime(project,val,ctx,weights,rank,thresholds)
                row={"ridge":ridge,"rank":rank,"validation_one_step":metric,"validation_20step":full,
                     "mode_diagnostics":diagnostics}; candidates.append(row); artifacts[(ridge,rank)]=weights
        eligible=[x for x in candidates if x["validation_one_step"]["residual_ratio_p99"]<=.25+1e-12 and x["validation_20step"]["residual_ratio_p99"]<=.25+1e-12]
        best=min(eligible,key=lambda x:x["validation_20step"]["candidate"]["J_pred"])
        weights=artifacts[(best["ridge"],best["rank"])]; path=models/f"N1-seed-{seed}.npz"; np.savez_compressed(path,weights=weights,thresholds_json=np.asarray(json.dumps(thresholds)),seed=seed,rank=best["rank"],ridge=best["ridge"])
        validation=best["validation_20step"]; record={"seed":seed,"bootstrap_trajectory_count":len(train),"samples_by_mode":samples,"candidates":candidates,"selected":{"ridge":best["ridge"],"rank":best["rank"],"validation_one_step":best["validation_one_step"]},"validation":validation,"model":str(path),"model_sha256":sha256(path),"wall_time_s":time.perf_counter()-tic}; records.append(record)
        (stage/f"seed_{seed}.json").write_text(json.dumps(record,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else x,indent=2)+"\n",encoding="utf-8")
        print(f"H1 seed={seed} valJ={validation['candidate']['J_pred']:.6g} base={validation['baseline']['J_pred']:.6g}",flush=True)
    order=sorted(records,key=lambda x:x["validation"]["candidate"]["J_pred"]); representative=order[len(order)//2]; with_npz=np.load(representative["model"],allow_pickle=False); weights=np.asarray(with_npz["weights"],float); with_npz.close()
    development=evaluate_regime(project,dev,ctx,weights,int(representative["selected"]["rank"]),thresholds); stats=_paired_statistics(development)
    c,b=development["candidate"],development["baseline"]; improvement=(b["J_pred"]-c["J_pred"])/b["J_pred"]; groups={k:(v["baseline_J"]-v["candidate_J"])/v["baseline_J"] for k,v in development["by_regime"].items()}
    component_guard=all(c[k]<=1.03*b[k]+1e-12 for k in ("state","force","load")); affected=groups.get("R1",-math.inf)>=.12 and groups.get("R3",-math.inf)>=-.03 or groups.get("R3",-math.inf)>=.12 and groups.get("R1",-math.inf)>=-.03
    gates={"overall_8pct":improvement>=.08,"R1_R3":affected,"component_3pct":component_guard,"direction_1pp":c["direction_accuracy"]>=b["direction_accuracy"]-.01,
           "divergence":c["diverged"]<=b["diverged"],"occupancy":max(development["occupancy"].values())<=.90 and len([v for v in development["occupancy"].values() if v>0])>=3,
           "switch_rate":development["switch_rate_hz"]<=.5,"residual_ratio":development["residual_ratio_p99"]<=.25,"ci_holm":stats["ci95"][0]>0 and stats["holm_p"]<.05}
    result={"component":"H1","representative_seed":representative["seed"],"selection_basis":"validation median","five_seed_validation":[{"seed":r["seed"],"J":r["validation"]["candidate"]["J_pred"],"hash":r["model_sha256"]} for r in records],
            "development":development,"statistics":stats,"relative_improvement":improvement,"regime_improvements":groups,"gates":gates,"passed":all(gates.values()),"model":representative["model"],"model_sha256":representative["model_sha256"]}
    (stage/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); return result


def main()->None:
    p=argparse.ArgumentParser(); p.add_argument("--component",choices=("regime","horizon"),required=True); p.add_argument("--project-root",type=Path,required=True); args=p.parse_args()
    if args.component=="regime": result=train_regime(args.project_root.resolve())
    else:
        from horizon_training import train_horizon
        result=train_horizon(args.project_root.resolve())
    print(json.dumps({"component":result["component"],"passed":result["passed"],"improvement":result["relative_improvement"]}),flush=True)


if __name__=="__main__": main()
