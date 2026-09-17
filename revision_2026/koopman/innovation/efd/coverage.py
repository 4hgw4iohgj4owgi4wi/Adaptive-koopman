from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import numpy as np

REQUIRED={"train":{"regime":40,"sign":300,"reversal":800,"high":200},"validation":{"regime":15,"sign":300,"reversal":250,"high":60},"development":{"regime":10,"sign":300,"reversal":160,"high":40}}
def formal_contract(rows:list[dict[str,Any]],root:Path)->dict[str,Any]:
    out={};fail=[]
    for split,req in REQUIRED.items():
        local=[r for r in rows if r["split"]==split];reg={f"R{i}":sum(r["regime"]==f"R{i}" for r in local) for i in range(4)};pos=np.zeros(8,int);neg=np.zeros(8,int);reversal=0;high=0;active_points=np.zeros(4,int);total_windows=0;ultimate=0;nonfinite=0;shape_fail=[];pairs={}
        for r in local:
            p=root/r["file"]
            with np.load(p,allow_pickle=False) as s:
                f=np.asarray(s["force_on_payload"],float).reshape(len(s["force_on_payload"]),8);d=np.asarray(s["connector_disp_payload_frame"],float);meta=json.loads(str(s["metadata_json"].item()));n=len(f);expected={"s3_deform":(n,46),"u1_four":(n-1,8),"force_on_payload":(n,4,2),"force_on_vehicle":(n,4,2),"connector_disp_payload_frame":(n,4,2)}
                wrong={k:[list(s[k].shape),list(v)] for k,v in expected.items() if k not in s or s[k].shape!=v}
                if wrong:shape_fail.append({"file":r["file"],"wrong":wrong});continue
                nonfinite+=int(any(not np.all(np.isfinite(s[k])) for k in expected));ultimate+=int(meta["ultimate_exceeded_steps"]);pairs.setdefault(meta["mirror_pair_id"],set()).add(float(meta["mirror_sign"]));origins=np.arange(0,n-20,20);total_windows+=len(origins)
                for o in origins:
                    w=f[o+1:o+21];pos+=np.any(w>12.,axis=0);neg+=np.any(w< -12.,axis=0);high+=int(np.any(np.linalg.norm(w.reshape(20,4,2),axis=-1)>=.8*12000));active_points+=np.any(np.linalg.norm(w.reshape(20,4,2),axis=-1)>=12.,axis=0)
                a=np.abs(f)>=12.;reversal+=int(np.sum(a[1:]&a[:-1]&(np.sign(f[1:])!=np.sign(f[:-1]))))
        mirror_ok=bool(pairs) and all(v=={-1.,1.} for v in pairs.values());gates={"regimes":all(v>=req["regime"] for v in reg.values()),"component_signs":bool(np.all(pos>=req["sign"]) and np.all(neg>=req["sign"])),"reversal":reversal>=req["reversal"],"high_load":high>=req["high"],"active_points":bool(np.all(active_points>=.2*total_windows)),"mirror_pairs":mirror_ok,"safety_shape":ultimate==0 and nonfinite==0 and not shape_fail};out[split]={"trajectories":len(local),"regime_counts":reg,"positive_windows":pos.tolist(),"negative_windows":neg.tolist(),"reversal_events":reversal,"high_load_windows":high,"active_point_windows":active_points.tolist(),"total_windows":total_windows,"mirror_pairs":len(pairs),"ultimate_steps":ultimate,"nonfinite_trajectories":nonfinite,"shape_failures":shape_fail,"gates":gates,"passed":all(gates.values())}
        if not out[split]["passed"]:fail.append(split)
    return {"splits":out,"failed_splits":fail,"passed":not fail}
