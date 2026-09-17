from __future__ import annotations
import importlib.util,sys,time
from pathlib import Path
from typing import Any
import numpy as np

def _load(path:Path):
    spec=importlib.util.spec_from_file_location("efd_r13_irsp_extract",path);mod=importlib.util.module_from_spec(spec);assert spec and spec.loader;sys.modules[spec.name]=mod;spec.loader.exec_module(mod);return mod

def reproduce(project:Path)->dict[str,Any]:
    tic=time.perf_counter();folder=project/"revision_2026"/"03_irsp";extract=_load(folder/"extract_actual_irsp_model.py")
    runner=extract.load_runner();stage5=runner._load_stage5_module();stage1=stage5._load_stage1_module();ns=stage5._bootstrap_env_for_path(stage1,"sine");methods=runner._ablation_method_plans(stage5,stage1,ns);cfg=dict(methods["full_tf14"].updates)
    raw_a,raw_b,fit=ns["fit_koopman_bilinear_matrices"](ns["model_koop_dnn_lin"],ns["xs_train"],ns["us_train"],ridge_lambda=ns["KOOPMAN_CFG"].get("ridge_lambda",1e-5),batch_size=4096)
    pack=ns["get_tf9_model_pack"](cfg);values={"raw_A":np.asarray(raw_a),"raw_B":np.asarray(raw_b),"projected_A":np.asarray(pack["A_bilinear"]),"projected_B":np.asarray(pack["B_bilinear"])}
    residuals={};binary={}
    with np.load(folder/"actual_irsp_matrices.npz",allow_pickle=False) as saved:
        for k,v in values.items():residuals[k]=float(np.max(np.abs(v-np.asarray(saved[k]))));binary[k]=bool(np.array_equal(v,np.asarray(saved[k])))
    return {"residuals":residuals,"binary_equal":binary,"fit_info":fit,"projection_info":dict(pack.get("bilinear_info") or {}),"max_residual":max(residuals.values()),"passed":max(residuals.values())<=1e-10,"wall_time_s":time.perf_counter()-tic}
