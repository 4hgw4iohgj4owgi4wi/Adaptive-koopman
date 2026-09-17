from __future__ import annotations
import json,sys
from pathlib import Path
from typing import Any
import numpy as np
import audit

REGISTRY={
 "A-LIN31-U2":{"chain":"A","state":24,"lift":31,"control":2,"irsp":False,"continuous_cert_allowed":False},
 "A-BIL31-U2":{"chain":"A","state":24,"lift":31,"control":2,"irsp":False,"continuous_cert_allowed":False},
 "A-IRSP31-U2":{"chain":"A","state":24,"lift":31,"control":2,"irsp":True,"continuous_cert_allowed":False},
 "V-ARX46-U8":{"chain":"B","state":46,"lift":46,"control":8,"irsp":False,"source":"K0"},
 "V-FL92-U8":{"chain":"B","state":46,"lift":92,"control":8,"irsp":False,"source":"K1"},
 "V-FB92-U8":{"chain":"B","state":46,"lift":92,"control":8,"irsp":False,"source":"K2"},
 "V-SB92-U8":{"chain":"B","state":46,"lift":92,"control":8,"irsp":False,"source":"K3"},
 "V-H2-64-U8":{"chain":"B","state":46,"output":64,"control":8,"irsp":False},
}

def build(project:Path)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman";sys.path.insert(0,str(koop));import compare_pipeline as cp
    models=cp.all_frozen_models();actual={}
    for mid,spec in REGISTRY.items():
        row=dict(spec)
        if mid.startswith("V-") and "source" in spec:
            m=models[spec["source"]];row.update({"kind":str(m["kind"]),"artifact":m.get("source_path",m.get("artifact_path")),"artifact_sha256":m.get("source_sha256",m.get("artifact_sha256"))})
            if "transition" in m:row["matrix_shapes"]={"transition":list(m["transition"].shape)}
            else:row["matrix_shapes"]={"base_transition":list(m["base_transition"].shape),"bilinear":list(m["bilinear"].shape)}
        actual[mid]=row
    irsp=project/"revision_2026"/"03_irsp"/"actual_irsp_matrices.npz"
    with np.load(irsp,allow_pickle=False) as s:shapes={k:list(s[k].shape) for k in ("raw_A","raw_B","projected_A","projected_B")}
    for mid in ("A-LIN31-U2","A-BIL31-U2","A-IRSP31-U2"):actual[mid].update({"artifact":str(irsp),"artifact_sha256":audit.sha256(irsp),"matrix_shapes":shapes})
    h2=koop/"innovation_results"/"t4_h2"/"models"/"N2-seed-151002.npz"
    with np.load(h2,allow_pickle=False) as s:h2shape={k:list(s[k].shape) for k in ("coef","feature_mean","feature_std","feature_dims")}
    actual["V-H2-64-U8"].update({"artifact":str(h2),"artifact_sha256":audit.sha256(h2),"matrix_shapes":h2shape})
    checks={
      "unique_ids":len(actual)==len(set(actual)),
      "article_irsp_31x2":shapes["projected_A"]==[31,31] and shapes["projected_B"]==[31,62],
      "vehicle_sb_92x8_no_irsp":actual["V-SB92-U8"]["matrix_shapes"]=={"base_transition":[101,93],"bilinear":[460,93]} and not actual["V-SB92-U8"]["irsp"],
      "h2_64_output":h2shape["coef"][-1]==64,
      "no_cross_chain_substitution":actual["A-IRSP31-U2"]["artifact_sha256"]!=actual["V-SB92-U8"]["artifact_sha256"],
    }
    return {"methods":actual,"checks":checks,"passed":all(checks.values())}
