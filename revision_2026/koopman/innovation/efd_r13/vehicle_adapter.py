from __future__ import annotations
import csv,json,sys,time
from pathlib import Path
from typing import Any
import numpy as np

def _cache_reproduction(project:Path)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman";innovation=koop/"innovation"
    for p in (koop,innovation):
        if str(p) not in sys.path:sys.path.insert(0,str(p))
    import baseline_cache as bc
    root=koop/"innovation_results"/"d4r"/"formal";cache=sorted((root/"baseline_cache").glob("development_*.npz"))[0];raw=root/"trajectories"/cache.name
    with np.load(raw,allow_pickle=False) as s:arrays={k:np.asarray(s[k],float) for k in ("s3_deform","force_output","u1_four","network")}
    with np.load(cache,allow_pickle=False) as s:saved={k:np.asarray(s[k]) for k in s.files}
    ctx=bc._context(project);mapping={"V-ARX46-U8":"K0","V-FL92-U8":"K1","V-FB92-U8":"K2"};results={}
    for mid,alias in mapping.items():
        px=[];pf=[]
        for origin in saved["origins"]:
            x,f,_,_=bc._rollout(ctx,alias,arrays,int(origin));px.append(x);pf.append(f)
        px=np.asarray(px,dtype=np.float32);pf=np.asarray(pf,dtype=np.float32);key=alias
        rx=float(np.max(np.abs(px-saved[f"{key}_x"])));rf=float(np.max(np.abs(pf-saved[f"{key}_f"])))
        results[mid]={"cache":str(cache),"windows":len(px),"state_max_abs":rx,"force_max_abs":rf,"passed":max(rx,rf)<=1e-10}
    return results

def _structured_csv(project:Path)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman";sys.path.insert(0,str(koop));import compare_pipeline as cp
    csv_path=koop/"compare"/"t2"/"K3_development_windows.csv"
    with csv_path.open(encoding="utf-8-sig",newline="") as h:ref=list(csv.DictReader(h))
    target=ref[0]["trajectory"];_,rows=cp.load_rows(cp.DATA);chosen=[r for r in rows if r["meta"]["split"]=="test" and f"{r['meta']['scenario']}|{r['meta'].get('physical_scene',r['meta']['scenario'])}|{r['meta']['seed']}"==target]
    norms=cp.train_moments(rows);labels=json.loads((koop/"compare"/"labels.json").read_text(encoding="utf-8"));model=cp.all_frozen_models()["K3"];out=cp.evaluate(model,chosen,"development-test",norms,labels)["window_rows"]
    lookup={(r["trajectory"],int(r["start"])):r for r in ref};fields=("state","force","load","deformation","force_rate","J_pred");maximum=0.
    for row in out:
        old=lookup[(row["trajectory"],int(row["start"]))]
        maximum=max(maximum,max(abs(float(row[k])-float(old[k])) for k in fields))
    return {"csv":str(csv_path),"trajectory":target,"windows":len(out),"max_abs":maximum,"passed":maximum<=1e-10}

def _h2(project:Path)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman";innovation=koop/"innovation"
    for p in (koop,innovation):
        if str(p) not in sys.path:sys.path.insert(0,str(p))
    import horizon_training as ht
    selected=json.loads((koop/"innovation_results"/"d4r"/"pilot"/"complete.json").read_text(encoding="utf-8"))["selected_high_config"]
    jobs=ht.formal_jobs(selected);ctx=ht._context(project);val=ht._dataset(project,[j for j in jobs if j["split"]=="validation"],ctx["norms"])
    model_path=koop/"innovation_results"/"t4_h2"/"models"/"N2-seed-151002.npz"
    with np.load(model_path,allow_pickle=False) as s:model=ht.DirectMultiHorizonHead(s["coef"],s["feature_mean"],s["feature_std"],s["feature_dims"])
    pred=ht.predict_dataset(model,val);manual=model.predict(val["x0"][0],val["u"][0]);output_residual=float(np.max(np.abs(pred[0]-manual)))
    evaluated=ht.evaluate(model,val,ctx["norms"]);record=json.loads((koop/"innovation_results"/"t4_h2"/"seed_151002.json").read_text(encoding="utf-8"));maximum=0.
    for band in ("h1_5","h10_20","all"):
        for side in ("candidate","baseline"):
            old=record["validation"][side][band];new=evaluated[side][band]
            for key in ("state","force","load","J_pred","point_direction","load_direction","divergence_rate"):maximum=max(maximum,abs(float(old[key])-float(new[key])))
    files=sorted((koop/"innovation_results"/"t4_h2"/"models").glob("N2-seed-*.npz"))
    return {"model":str(model_path),"bootstrap_models":len(files),"validation_windows":len(val["x0"]),"manual_64d_max_abs":output_residual,"metric_max_abs":maximum,"passed":len(files)==5 and max(output_residual,maximum)<=1e-10}

def run(project:Path)->dict[str,Any]:
    tic=time.perf_counter();cache=_cache_reproduction(project);structured=_structured_csv(project);h2=_h2(project);checks={**cache,"V-SB92-U8":structured,"V-H2-64-U8":h2};return {"checks":checks,"passed":all(x["passed"] for x in checks.values()),"wall_time_s":time.perf_counter()-tic}
