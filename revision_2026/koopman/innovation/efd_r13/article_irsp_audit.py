from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import numpy as np
import audit

def run(project:Path,reproduction:dict[str,Any])->dict[str,Any]:
    folder=project/"revision_2026"/"03_irsp";old=json.loads((folder/"actual_irsp_audit.json").read_text(encoding="utf-8"));c=old["continuous_domain_audit"]
    sampled=bool(old["projection_info"]["effective_radius_after_max"]<=old["projection_info"]["projection_radius"]+1e-9)
    continuous=bool(c["triangle_upper_bound"]<=c["radius"] and c["continuous_bound_feasible_without_reprojecting_A"])
    source=project/"paper_dcn_tf12_draft"/"dcn_latex_zh_comm_update_r42_2026-05-14"/"source"/"fig_nrkdcc_koopman_irsp_audit.csv"
    sources=[source] if source.exists() else []
    return {"audit_completed":bool(reproduction["passed"]),"scientific_claim_passed":False,"sampled_radius_passed":sampled,"continuous_norm_passed":continuous,"paper_claim_allowed":False,"continuous":c,"projection_info":old["projection_info"],"historical_figure_inputs":[{"path":str(p),"sha256":audit.sha256(p)} for p in sources],"decision":"delete continuous-domain certificate and ISS/UUB support; describe only sampled spectral-radius regularization"}
