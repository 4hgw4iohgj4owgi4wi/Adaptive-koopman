from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor,as_completed
import json,math,pickle,sys,time
from pathlib import Path
from typing import Any

import numpy as np


H=20
EXPERTS=("K0","K1","K4","K5F2")


def _context(project_root:Path)->dict[str,Any]:
    koop=project_root/"revision_2026"/"koopman"
    if str(koop) not in sys.path: sys.path.insert(0,str(koop))
    import compare_pipeline as cp
    import universal_v2_pipeline as uv2
    import universal_v2_modules as uv
    universal=koop/"universal_v2"; composer=koop/"composer_results"
    with np.load(universal/"normalizers.npz",allow_pickle=False) as s: norms={k:np.asarray(s[k],float) for k in s.files}
    _,old_rows=cp.load_rows(cp.DATA); old_norms=cp.train_moments(old_rows); original=cp.all_frozen_models()
    models={name:uv2.adapt_model_metrics(original[source],old_norms,norms) for name,source in
            (("K0","K0"),("K1","K1"),("K2","K2"),("K4","K4"),("K5F2","K5-linear"))}
    with np.load(universal/"t3"/"models"/"K5-linear.npz",allow_pickle=False) as s:
        head={k:np.asarray(s[k]) for k in ("coef","feature_mean","feature_std","clip")}
    selection=json.loads((composer/"t3"/"selection.json").read_text(encoding="utf-8")); seed=int(selection["representative_seed"])
    with (composer/"t3"/f"selector_seed_{seed}.pkl").open("rb") as h: selector=pickle.load(h)
    return {"cp":cp,"uv":uv,"norms":norms,"models":models,"head":head,"selection":selection,"selector":selector}


def _rollout(ctx:dict[str,Any],alias:str,arrays:dict[str,np.ndarray],origin:int)->tuple[np.ndarray,np.ndarray,np.ndarray,np.ndarray]:
    cp,uv,norms=ctx["cp"],ctx["uv"],ctx["norms"]; model=ctx["models"][alias]
    z=cp.lift(model,arrays["s3_deform"][origin]); xs=[]; fs=[]; drift=[]
    for h in range(H):
        z,_=cp.model_step(model,z,arrays["u1_four"][origin+h]); _,fn,xn=cp.decode(model,z)
        xs.append(xn); fs.append(fn)
        physical=xn*norms["x_std"]+norms["x_mean"]; drift.append(float(np.linalg.norm(z-cp.lift(model,physical))/math.sqrt(len(z))))
    xn=np.asarray(xs); fn=np.asarray(fs); previous=arrays["force_output"][origin,:8].reshape(4,2)
    physics=uv.physics_force(xn,norms,previous)
    if alias=="K5F2":
        fp=uv.apply_fhead(ctx["head"],xn,arrays["u1_four"][origin:origin+H],physics,previous,norms)
        fn=(fp-norms["force_mean"])/norms["force_std"]
    contract=np.mean(np.abs(fn[:,:10]-(physics[:,:10]-norms["force_mean"][:10])/norms["force_std"][:10]),axis=1)
    return xn,fn,np.asarray(drift),contract


def _base(arrays:dict[str,np.ndarray],origin:int)->np.ndarray:
    x=arrays["s3_deform"][origin]; u=arrays["u1_four"][origin]; prev=arrays["u1_four"][max(0,origin-1)]
    disp=x[30:38].reshape(4,2); vel=x[38:46].reshape(4,2); network=arrays["network"][min(origin,len(arrays["network"])-1)]
    return np.r_[x[24:30],x[[2,8,14,20]],np.mean(u[0::2]),np.mean(u[1::2]),np.mean(u[1::2]-prev[1::2]),
                 np.linalg.norm(disp,axis=1),np.linalg.norm(vel,axis=1),network[:4]]


def _features(data:dict[str,np.ndarray])->np.ndarray:
    px,pf=data["pred_x"],data["pred_f"]; w=len(px)
    horizon=np.broadcast_to(np.arange(1,H+1)/H,(w,H))[...,None]
    base=np.broadcast_to(data["base_context"][:,None,:],(w,H,data["base_context"].shape[1]))
    sx=np.mean(np.std(px,axis=1),axis=-1)[...,None]; sf=np.mean(np.std(pf[:,:,:,:10],axis=1),axis=-1)[...,None]
    contract=np.transpose(data["contract"],(0,2,1)); drift=np.transpose(data["lift_drift"][:,[1,2]],(0,2,1))
    return np.concatenate([base,horizon,sx,sf,contract,drift],axis=-1)


def _proba(model:Any,x:np.ndarray)->tuple[np.ndarray,np.ndarray]:
    p0=model.predict_proba(x); p=np.zeros((len(x),len(EXPERTS))); p[:,model.classes_.astype(int)]=p0
    return np.argmax(p,axis=1),np.max(p,axis=1)


def _compose(ctx:dict[str,Any],data:dict[str,np.ndarray])->tuple[np.ndarray,np.ndarray,np.ndarray,np.ndarray]:
    px,pf=data["pred_x"],data["pred_f"]; sel=ctx["selector"]; thresholds=ctx["selection"]["thresholds"]; w=len(px)
    weights=np.asarray([ctx["selection"]["global_weights"][x] for x in EXPERTS])
    b4x=np.einsum("e,wehd->whd",weights,px); b4f=np.einsum("e,wehd->whd",weights,pf)
    feat=_features(data); flat=feat.reshape(-1,feat.shape[-1]); ix,cx=_proba(sel["state"],flat); iff,cf=_proba(sel["force"],flat)
    ix=ix.reshape(w,H); iff=iff.reshape(w,H); confidence=np.minimum(cx,cf).reshape(w,H); rows=np.arange(w)[:,None]; hs=np.arange(H)[None,:]
    b5x=px[rows,ix,hs]; b5f=pf[rows,iff,hs]
    reject=((confidence<thresholds["confidence"])|(np.mean(np.std(px,axis=1),axis=-1)>thresholds["state_disagreement_p95"])|
            (np.mean(np.std(pf[:,:,:,:10],axis=1),axis=-1)>thresholds["force_disagreement_p95"])|
            (data["contract"][rows,iff,hs]>thresholds["contract_p95"]))
    b5x=np.where(reject[...,None],px[:,1],b5x); b5f=np.where(reject[...,None],pf[:,1],b5f)
    return b4x,b4f,b5x,b5f


def _partition(project_root:str,jobs:list[dict[str,Any]],raw_folder:str,cache_folder:str)->list[dict[str,Any]]:
    from audit_inputs import sha256
    ctx=_context(Path(project_root)); norms=ctx["norms"]; out=[]
    keys=("s3_deform","force_output","u1_four","network")
    for job in jobs:
        raw=Path(raw_folder)/f"{job['split']}_{job['group']}_{job['seed']}.npz"; target=Path(cache_folder)/raw.name
        if target.exists(): out.append({"seed":job["seed"],"split":job["split"],"file":target.name,"sha256":sha256(target),"resumed":True}); continue
        with np.load(raw,allow_pickle=False) as s: arrays={k:np.asarray(s[k],float) for k in keys}
        origins=np.arange(0,len(arrays["u1_four"])-H+1,H,dtype=int); expert_x=[]; expert_f=[]; k2x=[]; k2f=[]; drift=[]; contract=[]; base=[]; truth_x=[]; truth_f=[]
        for origin in origins:
            ex=[]; ef=[]; ed=[]; ec=[]
            for alias in EXPERTS:
                x,f,d,c=_rollout(ctx,alias,arrays,int(origin)); ex.append(x); ef.append(f); ed.append(d); ec.append(c)
            x2,f2,_,_=_rollout(ctx,"K2",arrays,int(origin)); expert_x.append(ex); expert_f.append(ef); k2x.append(x2); k2f.append(f2); drift.append(ed); contract.append(ec); base.append(_base(arrays,int(origin)))
            truth_x.append((arrays["s3_deform"][origin+1:origin+H+1]-norms["x_mean"])/norms["x_std"])
            truth_f.append((arrays["force_output"][origin+1:origin+H+1]-norms["force_mean"])/norms["force_std"])
        data={"pred_x":np.asarray(expert_x),"pred_f":np.asarray(expert_f),"lift_drift":np.asarray(drift),"contract":np.asarray(contract),"base_context":np.asarray(base)}
        b4x,b4f,b5x,b5f=_compose(ctx,data); temporary=target.with_suffix(".tmp.npz")
        np.savez_compressed(temporary,origins=origins,truth_x=np.asarray(truth_x,dtype=np.float32),truth_f=np.asarray(truth_f,dtype=np.float32),
                            K0_x=data["pred_x"][:,0].astype(np.float32),K0_f=data["pred_f"][:,0].astype(np.float32),
                            K1_x=data["pred_x"][:,1].astype(np.float32),K1_f=data["pred_f"][:,1].astype(np.float32),
                            K2_x=np.asarray(k2x,dtype=np.float32),K2_f=np.asarray(k2f,dtype=np.float32),
                            K5_x=data["pred_x"][:,3].astype(np.float32),K5_f=data["pred_f"][:,3].astype(np.float32),
                            B4_x=b4x.astype(np.float32),B4_f=b4f.astype(np.float32),B5_x=b5x.astype(np.float32),B5_f=b5f.astype(np.float32),
                            base_context=data["base_context"].astype(np.float32))
        temporary.replace(target); out.append({"seed":job["seed"],"split":job["split"],"file":target.name,"sha256":sha256(target),"resumed":False})
    return out


def cache_all(project_root:Path,jobs:list[dict[str,Any]],raw_folder:Path,cache_folder:Path,workers:int=4)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    cache_folder.mkdir(parents=True,exist_ok=True); chunks=[jobs[i::workers] for i in range(workers)]; done=[]; failures=[]; tic=time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(_partition,str(project_root),part,str(raw_folder),str(cache_folder)):i for i,part in enumerate(chunks)}
        for future in as_completed(futures):
            try: done.extend(future.result())
            except Exception as exc: failures.append({"partition":futures[future],"error":repr(exc)})
            print(f"baseline cache partitions {len(done)}/{len(jobs)} failures={len(failures)} elapsed={time.perf_counter()-tic:.1f}s",flush=True)
    done.sort(key=lambda x:x["seed"]); return done,failures
