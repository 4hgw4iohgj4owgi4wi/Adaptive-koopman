from __future__ import annotations
import json,sys,time
from pathlib import Path
from typing import Any
import numpy as np

from audit import sha256

def train_scales(project:Path)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman"
    if str(koop) not in sys.path:sys.path.insert(0,str(koop))
    import generate_compare as gen,compare_pipeline as cp
    return gen.train_scales(cp.DATA)

def _summary(path:Path,job:dict[str,Any],elapsed:float,resumed:bool)->dict[str,Any]:
    with np.load(path,allow_pickle=False) as s:
        meta=json.loads(str(s["metadata_json"].item())); force=np.asarray(s["force_body"],float); disp=np.asarray(s["displacement_body"],float)
    dot=np.sum(force*disp,axis=2); active=np.linalg.norm(force,axis=2)>1e-6; negative=int(np.sum(active&(dot< -1e-7)))
    return {"seed":job["seed"],"split":job["split"],"group":job["group"],"scenario":job["scenario"],"file":path.name,"sha256":sha256(path),"resumed":resumed,
            "steps":meta["steps"],"finite":meta["finite"],"max_connector_force_n":meta["max_connector_force_n"],"rated_force_n":meta["params"]["connector"]["rated_force_n"],
            "ultimate_exceeded_steps":meta["ultimate_exceeded_steps"],"max_tire_utilization":meta["max_tire_utilization"],"axial_negative_samples":negative,"wall_time_s":elapsed,"bytes":path.stat().st_size}

def simulate_one(project_root:str,job:dict[str,Any],scales:dict[str,Any],output:str)->dict[str,Any]:
    project=Path(project_root);koop=project/"revision_2026"/"koopman";path=Path(output)
    if str(koop) not in sys.path:sys.path.insert(0,str(koop))
    if path.exists():return _summary(path,job,0.,True)
    import generate_compare as gen,universal_pipeline as uv
    config=job.get("config"); tic=time.perf_counter(); arrays,meta=(gen.simulate(job,scales) if config is None else uv.simulate_d1(job,scales,config))
    temp=path.with_suffix(".tmp.npz")
    np.savez_compressed(temp,**arrays,metadata_json=np.asarray(json.dumps(meta,ensure_ascii=False)));temp.replace(path)
    return _summary(path,job,time.perf_counter()-tic,False)
