from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
from typing import Any

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):h.update(block)
    return h.hexdigest().upper()

def hash_tree(root:Path,exclude_parts:set[str]|None=None)->dict[str,dict[str,Any]]:
    excluded=exclude_parts or set(); out={}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(part in excluded for part in path.relative_to(root).parts):
            out[str(path.relative_to(root))]={"sha256":sha256(path),"bytes":path.stat().st_size}
    return out

def freeze_source_hashes(project:Path,protocol:Path)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman"; old=koop/"innovation"; results=koop/"innovation_results"
    paths={"protocol":protocol,"protocol_amendment":protocol.parent/"protocol_amendment.md","H2_model":results/"t4_h2"/"models"/"N2-seed-151002.npz","K1_model":koop/"k2"/"linear"/"models"/"S3-U1-lifted.npz",
           "normalizer":koop/"universal_v2"/"normalizers.npz","physics_decoder":koop/"universal_v2_modules.py","generator":koop/"generate_compare.py",
           "old_horizon_training":old/"horizon_training.py","old_multihorizon":old/"multihorizon.py","old_baseline_cache":old/"baseline_cache.py","old_data_protocol":old/"data_protocol.py"}
    missing=[k for k,p in paths.items() if not p.exists()]
    return {"missing":missing,"files":{k:{"path":str(p),"sha256":sha256(p),"bytes":p.stat().st_size} for k,p in paths.items() if p.exists()}}

def audit_seed_collisions(root:Path,requested:list[int])->dict[str,Any]:
    wanted=set(requested); found={}
    def integers(value:Any)->set[int]:
        if isinstance(value,bool):return set()
        if isinstance(value,int):return {value}
        if isinstance(value,list):
            out=set()
            for item in value:out|=integers(item)
            return out
        if isinstance(value,dict):
            out=set()
            for item in value.values():out|=integers(item)
            return out
        return set()
    def seed_values(value:Any)->set[int]:
        out=set()
        if isinstance(value,dict):
            for key,item in value.items():
                lowered=str(key).lower()
                if "seed" in lowered or lowered in ("traj_id","trajectory_id"):out|=integers(item)
                out|=seed_values(item)
        elif isinstance(value,list):
            for item in value:out|=seed_values(item)
        return out
    for path in root.rglob("*.json"):
        if "innovation_direction_results" in path.parts:continue
        try:value=json.loads(path.read_text(encoding="utf-8",errors="ignore"))
        except (OSError,json.JSONDecodeError):continue
        overlap=sorted(seed_values(value)&wanted)
        if overlap:found[str(path)]=overlap
    return {"requested":len(requested),"collisions":found,"passed":not found}

def audit_d5_absent(project:Path)->dict[str,Any]:
    candidates=[project/"revision_2026"/"koopman"/"innovation_results"/"d5",project/"revision_2026"/"koopman"/"innovation_direction_results"/"d5"]
    existing=[str(p) for p in candidates if p.exists() and any(p.rglob("*"))]; return {"paths":[str(p) for p in candidates],"existing_nonempty":existing,"passed":not existing}

def package_versions()->dict[str,str]:
    import numpy,scipy,sklearn,matplotlib
    return {"python":sys.version,"numpy":numpy.__version__,"scipy":scipy.__version__,"sklearn":sklearn.__version__,"matplotlib":matplotlib.__version__}
