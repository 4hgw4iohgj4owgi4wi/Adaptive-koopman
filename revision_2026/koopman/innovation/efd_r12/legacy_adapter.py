from __future__ import annotations
import json,re
from pathlib import Path
from typing import Any
import numpy as np
import audit


def _source_extract(path:Path,patterns:list[str])->dict[str,list[str]]:
    text=path.read_text(encoding="utf-8",errors="replace").splitlines()
    return {p:[f"{i+1}:{line.strip()}" for i,line in enumerate(text) if re.search(p,line)][:20] for p in patterns}


def audit_method_identity(project:Path)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman";cp=koop/"compare_pipeline.py";extractor=project/"revision_2026"/"03_irsp"/"extract_actual_irsp_model.py"
    irsp_json=project/"revision_2026"/"03_irsp"/"actual_irsp_audit.json";irsp_npz=project/"revision_2026"/"03_irsp"/"actual_irsp_matrices.npz"
    compare=_source_extract(cp,[r'def fit_struct_fixed',r'"K3"\s*:\s*fit_struct_fixed',r'K3.*five|K3.*物理模态',r'def all_frozen_models'])
    extract=_source_extract(extractor,[r'full_tf14',r'fit_koopman_bilinear_matrices',r'get_tf9_model_pack'])
    with np.load(koop/"compare"/"models"/"K3.npz",allow_pickle=False) as s:k3_shapes={k:list(s[k].shape) for k in s.files if k in ("base_transition","bilinear")}
    with np.load(irsp_npz,allow_pickle=False) as s:irsp_shapes={k:list(s[k].shape) for k in ("raw_A","raw_B","projected_A","projected_B")}
    actual=json.loads(irsp_json.read_text(encoding="utf-8"))
    mismatch={
        "protocol_claim":"C2 = historical frozen K3 bilinear+IRSP",
        "actual_compare_K3":"structured low-rank fixed-lift bilinear fitted by fit_struct_fixed; no IRSP projection",
        "actual_IRSP":"separate TF14 artifact, 31-state lift and 2 inputs",
        "four_vehicle_interface":"compare K3 uses 92 nonconstant lifted states and 8 controls",
        "transferable":False,
    }
    return {"compare_source":str(cp),"compare_sha256":audit.sha256(cp),"compare_evidence":compare,
            "irsp_extractor":str(extractor),"irsp_extractor_sha256":audit.sha256(extractor),"irsp_evidence":extract,
            "compare_k3_shapes":k3_shapes,"actual_irsp_shapes":irsp_shapes,"actual_irsp_audit":actual,
            "identity_mismatch":mismatch,"passed":False,
            "reason":"No frozen four-vehicle K3+IRSP artifact exists: compare K3 and actual IRSP are different models, lifts, and input dimensions."}


def run(project:Path)->dict[str,Any]:
    identity=audit_method_identity(project)
    return {"method_identity":identity,"C0_cache_reproduction":{"status":"not_run_after_identity_hard_failure"},
            "C1_cache_reproduction":{"status":"not_run_after_identity_hard_failure"},
            "C2_irsp_reproduction":{"status":"failed_method_identity"},
            "C3_h2_reproduction":{"status":"not_run_after_identity_hard_failure"},"passed":False}
