from __future__ import annotations
import json,sys,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
from typing import Any
import numpy as np

from audit import sha256
from h2_adapter import FrozenH2StateAdapter

def _context(project:Path)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman";old=koop/"innovation"
    if str(old) not in sys.path:sys.path.insert(0,str(old))
    if str(koop) not in sys.path:sys.path.insert(1,str(koop))
    import baseline_cache as legacy
    ctx=legacy._context(project)
    model=FrozenH2StateAdapter(koop/"innovation_results"/"t4_h2"/"models"/"N2-seed-151002.npz")
    return {"legacy":legacy,"ctx":ctx,"h2":model}

def _one(context:dict[str,Any],raw:Path,target:Path,job:dict[str,Any])->dict[str,Any]:
    if target.exists():return {"seed":job["seed"],"split":job["split"],"file":target.name,"sha256":sha256(target),"resumed":True}
    keys=("s3_deform","force_output","u1_four","network")
    with np.load(raw,allow_pickle=False) as s:arrays={k:np.asarray(s[k],float) for k in keys}
    ctx=context["ctx"];norms=ctx["norms"];origins=np.arange(0,len(arrays["u1_four"])-20+1,20,dtype=int);p0x=[];p0f=[];p1=[];tx=[];tf=[];current=[]
    for origin in origins:
        x,f,_,_=context["legacy"]._rollout(ctx,"K1",arrays,int(origin));p0x.append(x);p0f.append(f)
        x0=(arrays["s3_deform"][origin]-norms["x_mean"])/norms["x_std"];u=(arrays["u1_four"][origin:origin+20]-norms["u_mean"])/norms["u_std"];p1.append(context["h2"].predict_full(x0,u)[0])
        tx.append((arrays["s3_deform"][origin+1:origin+21]-norms["x_mean"])/norms["x_std"]);tf.append((arrays["force_output"][origin+1:origin+21]-norms["force_mean"])/norms["force_std"]);current.append(arrays["force_output"][origin,:8].reshape(4,2))
    temp=target.with_suffix(".tmp.npz");np.savez_compressed(temp,origins=origins,P0_x=np.asarray(p0x,dtype=np.float32),P0_f=np.asarray(p0f,dtype=np.float32),P1=np.asarray(p1,dtype=np.float32),truth_x=np.asarray(tx,dtype=np.float32),truth_f=np.asarray(tf,dtype=np.float32),current_points=np.asarray(current,dtype=np.float32));temp.replace(target)
    return {"seed":job["seed"],"split":job["split"],"file":target.name,"sha256":sha256(target),"resumed":False,"windows":len(origins),"bytes":target.stat().st_size}

def _partition(project_root:str,jobs:list[dict[str,Any]],rawdir:str,cachedir:str)->list[dict[str,Any]]:
    context=_context(Path(project_root));out=[]
    for job in jobs:
        name=f"{job['split']}_{job['group']}_{job['seed']}.npz";out.append(_one(context,Path(rawdir)/name,Path(cachedir)/name,job))
    return out

def cache_all(project:Path,jobs:list[dict[str,Any]],rawdir:Path,cachedir:Path,workers:int=4)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    cachedir.mkdir(parents=True,exist_ok=True);chunks=[jobs[i::workers] for i in range(workers)];done=[];fail=[];tic=time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(_partition,str(project),part,str(rawdir),str(cachedir)):i for i,part in enumerate(chunks)}
        for f in as_completed(futures):
            try:done.extend(f.result())
            except Exception as exc:fail.append({"partition":futures[f],"error":repr(exc)})
            print(f"D4R2 cache {len(done)}/{len(jobs)} failures={len(fail)} elapsed={time.perf_counter()-tic:.1f}s",flush=True)
    done.sort(key=lambda x:x["seed"]);return done,fail
