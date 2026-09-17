from __future__ import annotations

from collections import Counter,defaultdict
import json
from pathlib import Path
from typing import Any

import numpy as np

from regime_coverage import point_kinematics


H=20


def _meta(source: Any) -> dict[str,Any]:
    return json.loads(str(source["metadata_json"].item()))


def _step_coordinates(path: Path) -> tuple[np.ndarray,np.ndarray]:
    with np.load(path,allow_pickle=False) as source:
        meta=_meta(source); free=float(meta["params"]["connector"]["free_play_m"])
        p,vn=point_kinematics(source["displacement_body"],source["relative_velocity_body"],free)
    pmax=np.max(p,axis=1)
    ve=np.sum(p*vn,axis=1)/np.maximum(np.sum(p,axis=1),1e-12)
    return pmax,ve


def _count_coordinates(records:list[tuple[np.ndarray,np.ndarray]],eps_p:float,eps_v:float)->dict[str,int]:
    count=Counter()
    for p,ve in records:
        lab=np.full(len(p),2,dtype=np.int8); loaded=p>eps_p; lab[~loaded]=0
        lab[loaded&(ve>eps_v)]=1; lab[loaded&(ve< -eps_v)]=3
        for start in range(0,len(lab)-H+1,H):
            count[f"R{int(np.bincount(lab[start:start+H],minlength=4).argmax())}"]+=1
    return {f"R{i}":count[f"R{i}"] for i in range(4)}


def freeze_validation_thresholds(paths:list[Path])->dict[str,Any]:
    records=[_step_coordinates(path) for path in paths]
    p=np.concatenate([x[0] for x in records]); ve=np.concatenate([x[1] for x in records])
    p_grid=np.unique(np.quantile(p,np.linspace(.10,.45,15)))
    active=np.abs(ve[p>float(np.quantile(p,.10))]); active=active[active>1e-10]
    v_grid=np.unique(np.r_[0.0,np.quantile(active,np.linspace(.10,.70,19))]) if len(active) else np.asarray([0.0])
    candidates=[]
    for ep in p_grid:
        for ev in v_grid:
            counts=_count_coordinates(records,float(ep),float(ev)); values=np.asarray(list(counts.values()),float)
            candidates.append({"eps_p":float(ep),"eps_v":float(ev),"counts":counts,
                               "minimum":int(values.min()),"imbalance":float(values.std())})
    best=max(candidates,key=lambda x:(x["minimum"],-x["imbalance"]))
    return {**best,"selection_split":"validation only","grid_candidates":len(candidates),
            "definition":{"R0":"p_max <= eps_p","R1":"loaded and penetration-weighted vn > eps_v",
                          "R2":"loaded and |penetration-weighted vn| <= eps_v","R3":"loaded and penetration-weighted vn < -eps_v"}}


def coverage(paths:list[Path],thresholds:dict[str,Any])->dict[str,dict[str,int]]:
    by=defaultdict(list)
    for path in paths:
        with np.load(path,allow_pickle=False) as source: split=str(_meta(source)["split"])
        by[split].append(_step_coordinates(path))
    return {split:_count_coordinates(rows,float(thresholds["eps_p"]),float(thresholds["eps_v"])) for split,rows in by.items()}


def audit_contracts(paths:list[Path])->dict[str,Any]:
    failures=[]; high=Counter(); total_windows=Counter(); direction_active=direction_bad=0
    for path in paths:
        try:
            with np.load(path,allow_pickle=False) as s:
                m=_meta(s); split=str(m["split"]); n=int(m["steps"])
                expected={"s3_deform":(n+1,46),"s2_four":(n+1,30),"force_output":(n+1,18),
                          "force_body":(n+1,4,2),"force_rate":(n+1,4,2),"q":(n+1,2),
                          "displacement_body":(n+1,4,2),"relative_velocity_body":(n+1,4,2),
                          "u1_four":(n,8),"network":(n,4),"time_s":(n+1,)}
                wrong={key:{"got":list(s[key].shape),"expected":list(shape)} for key,shape in expected.items() if key not in s or s[key].shape!=shape}
                finite=all(np.all(np.isfinite(s[key])) for key in expected if key in s)
                # time_s is frozen float32.  At 44 s its ULP is ~3.8e-6 s,
                # so differencing adjacent samples can exceed a fixed 2e-6
                # tolerance although steps, duration and metadata are exact.
                time_tol=max(2e-6,2.0*float(np.spacing(np.float32(np.max(np.abs(s["time_s"]))))))
                time_ok=bool(np.all(np.diff(s["time_s"])>0) and
                             np.allclose(np.diff(s["time_s"]),float(m["control_dt_s"]),rtol=0,atol=time_tol) and
                             abs(float(s["time_s"][-1])-float(m["duration_s"]))<=time_tol)
                map_force=bool(np.array_equal(s["force_output"][:,:8],s["force_body"].reshape(n+1,8)))
                map_load=bool(np.array_equal(s["force_output"][:,8:10],s["q"]))
                map_rate=bool(np.array_equal(s["force_output"][:,10:18],s["force_rate"].reshape(n+1,8)))
                dot=np.sum(np.asarray(s["force_body"],float)*np.asarray(s["displacement_body"],float),axis=2)
                active=np.linalg.norm(s["force_body"],axis=2)>1e-6; direction_active+=int(np.sum(active)); direction_bad+=int(np.sum(active&(dot< -1e-7)))
                rated=float(m["params"]["connector"]["rated_force_n"])
                for start in range(0,n-H+1,H):
                    total_windows[split]+=1
                    high[split]+=int(np.max(np.linalg.norm(s["force_body"][start:start+H],axis=2))>=.8*rated)
                if wrong or not (finite and time_ok and map_force and map_load and map_rate):
                    failures.append({"file":path.name,"shape":wrong,"finite":finite,"time":time_ok,"force_map":map_force,"load_map":map_load,"rate_map":map_rate})
        except Exception as exc: failures.append({"file":path.name,"error":repr(exc)})
    return {"passed":not failures and direction_bad==0,"failures":failures,"trajectories":len(paths),
            "shape_contract":{"S3":46,"state_main":30,"control":8,"force_order":"FL/FR/RL/RR, each Fx/Fy","force_output":"8 point force + 2 payload load + 8 force rate"},
            "direction_contract":{"active_samples":direction_active,"opposite_axial_samples":direction_bad,"passed":direction_bad==0},
            "action_reaction":{"vehicle_side_force_independently_logged":False,"status":"not_identifiable"},
            "windows":dict(total_windows),"high_load_windows":dict(high)}
