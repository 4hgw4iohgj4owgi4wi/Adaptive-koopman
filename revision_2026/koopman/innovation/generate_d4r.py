from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np

from data_protocol import CONFIGS
from regime_coverage import window_counts, continuous_summary


def _summarize(path: Path, job: dict[str,Any], elapsed: float, resumed: bool) -> dict[str,Any]:
    from audit_inputs import sha256
    with np.load(path,allow_pickle=False) as saved:
        arrays={name:np.asarray(saved[name]) for name in ("displacement_body","relative_velocity_body","force_body")}
        meta=json.loads(str(saved["metadata_json"].item()))
    connector=meta["params"]["connector"]
    counts=window_counts(arrays["displacement_body"],arrays["relative_velocity_body"],arrays["force_body"],
                         float(connector["free_play_m"]),float(connector["rated_force_n"]))
    summary=continuous_summary(arrays["displacement_body"],arrays["relative_velocity_body"],float(connector["free_play_m"]))
    return {**{k:job[k] for k in ("seed","split","group","scenario","config_name")},"file":path.name,"sha256":sha256(path),"steps":meta["steps"],
            "max_connector_force_n":meta["max_connector_force_n"],"rated_force_n":connector["rated_force_n"],
            "ultimate_force_n":connector["ultimate_force_n"],"ultimate_exceeded_steps":meta["ultimate_exceeded_steps"],"finite":meta["finite"],
            "max_tire_utilization":meta["max_tire_utilization"],"wall_time_s":elapsed,"file_bytes":path.stat().st_size,"resumed":resumed,**counts,**summary}


def simulate_one(project_root: str, job: dict[str,Any], scales: dict[str,Any], output: str) -> dict[str,Any]:
    project=Path(project_root); koop=project/"revision_2026"/"koopman"; path=Path(output)
    if str(Path(__file__).resolve().parent) not in sys.path: sys.path.insert(0,str(Path(__file__).resolve().parent))
    if str(koop) not in sys.path: sys.path.insert(0,str(koop))
    if path.exists():
        return _summarize(path,job,0.0,True)
    import generate_compare as gen
    import universal_pipeline as uv1
    tic=time.perf_counter(); config=CONFIGS[job["config_name"]]
    arrays,meta=(gen.simulate(job,scales) if config is None else uv1.simulate_d1(job,scales,config))
    temporary=path.with_suffix(path.suffix+".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle,**arrays,metadata_json=np.asarray(json.dumps(meta,ensure_ascii=False)))
    temporary.replace(path)
    return _summarize(path,job,time.perf_counter()-tic,False)
