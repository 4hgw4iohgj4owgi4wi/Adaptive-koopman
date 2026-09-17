from __future__ import annotations
import hashlib,json,platform,sys
from pathlib import Path
from typing import Any

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(8*1024*1024),b""):h.update(block)
    return h.hexdigest().upper()

def hash_tree(root:Path,exclude:set[str]|None=None)->dict[str,str]:
    exclude=exclude or set();return {str(p.relative_to(root)):sha256(p) for p in sorted(root.rglob("*")) if p.is_file() and not any(x in p.parts for x in exclude)} if root.exists() else {}

def _structured_seeds(path:Path)->set[int]:
    out=set()
    try:
        if path.suffix.lower()==".json":
            obj=json.loads(path.read_text(encoding="utf-8"))
            def walk(x:Any,key:str=""):
                if isinstance(x,dict):
                    for k,v in x.items():walk(v,str(k).lower())
                elif isinstance(x,list):
                    for v in x:walk(v,key)
                elif any(q in key for q in ("seed","traj_id","trajectory_id")) and isinstance(x,(int,float)) and float(x).is_integer():out.add(int(x))
            walk(obj)
        elif path.suffix.lower()==".npz":
            import numpy as np
            with np.load(path,allow_pickle=False) as s:
                for k in s.files:
                    if any(q in k.lower() for q in ("seed","traj_id","trajectory_id")):
                        a=s[k]
                        if a.size<10000:
                            for v in a.reshape(-1):
                                try:out.add(int(v))
                                except Exception:pass
    except Exception:pass
    return out

def audit_seed_collisions(root:Path,requested:list[int])->dict[str,Any]:
    found={};wanted=set(requested)
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".json",".npz") and "innovation_efd_results" not in p.parts:
            hit=_structured_seeds(p)&wanted
            if hit:found[str(p)]=sorted(hit)
    return {"requested_count":len(requested),"range":[min(requested),max(requested)],"collisions":found,"passed":not found,"parser":"structured seed/traj_id/trajectory_id fields only"}

def environment()->dict[str,Any]:
    import numpy,scipy
    return {"python":sys.version,"executable":sys.executable,"platform":platform.platform(),"numpy":numpy.__version__,"scipy":scipy.__version__}
