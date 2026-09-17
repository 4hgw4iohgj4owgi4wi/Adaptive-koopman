from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import audit


def _read(path:Path)->dict[str,Any]|None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def run(project:Path)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman";r11=koop/"innovation_efd_r11_results"
    evidence={
        "s2":_read(r11/"pilot"/"complete.json"),
        "s3":_read(r11/"data"/"complete.json"),
        "s4":_read(r11/"s4_baselines"/"complete.json"),
    }
    s2=evidence["s2"];formal=bool(s2 and s2.get("passed") and s2.get("local_pass_count")==12 and not s2.get("failures"))
    paths={
        "r11_code":koop/"innovation"/"efd_r11",
        "r11_results":r11,
        "efd_code":koop/"innovation"/"efd",
        "direction_code":koop/"innovation"/"direction",
        "actual_irsp":project/"revision_2026"/"03_irsp",
        "compare":koop/"compare",
        "innovation":koop/"innovation",
    }
    return {"r11_evidence":evidence,"r11_evidence_role":"formal" if formal else "post_hoc_diagnostic",
            "tree_hashes":{k:audit.hash_tree(v,{"__pycache__"}) for k,v in paths.items()},"passed":formal}
