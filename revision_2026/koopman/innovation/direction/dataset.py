from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import numpy as np

def normalizers(project:Path)->dict[str,np.ndarray]:
    with np.load(project/"revision_2026"/"koopman"/"universal_v2"/"normalizers.npz",allow_pickle=False) as s:return {k:np.asarray(s[k],float) for k in s.files}

def load_direction_dataset(project:Path,split:str)->dict[str,Any]:
    root=project/"revision_2026"/"koopman"/"innovation_direction_results"/"d4r2"/"formal";manifest=json.loads((root/"cache_manifest.json").read_text(encoding="utf-8"));norms=normalizers(project);parts={k:[] for k in ("x0","u","truth_x","truth_f","p0x","p0f","p1","current")};trajectory=[];groups=[];seeds=[]
    rows=[r for r in manifest["completed"] if r["split"]==split]
    for ti,row in enumerate(rows):
        with np.load(root/"trajectories"/row["file"],allow_pickle=False) as raw:state=np.asarray(raw["s3_deform"],float);control=np.asarray(raw["u1_four"],float);meta=json.loads(str(raw["metadata_json"].item()))
        with np.load(root/"cache"/row["file"],allow_pickle=False) as c:
            origins=np.asarray(c["origins"],int);values={"truth_x":np.asarray(c["truth_x"],float),"truth_f":np.asarray(c["truth_f"],float),"p0x":np.asarray(c["P0_x"],float),"p0f":np.asarray(c["P0_f"],float),"p1":np.asarray(c["P1"],float),"current":np.asarray(c["current_points"],float)}
        parts["x0"].append((state[origins]-norms["x_mean"])/norms["x_std"]);parts["u"].append(np.asarray([(control[o:o+20]-norms["u_mean"])/norms["u_std"] for o in origins]))
        for k,v in values.items():parts[k].append(v)
        trajectory.extend([ti]*len(origins));groups.extend([meta["group"]]*len(origins));seeds.extend([row["seed"]]*len(origins))
    return {**{k:np.concatenate(v) for k,v in parts.items()},"trajectory":np.asarray(trajectory,int),"group":np.asarray(groups),"seed":np.asarray(seeds,int),"norms":norms,"trajectory_rows":rows}

def axial_targets(data:dict[str,Any])->dict[str,np.ndarray]:
    norms=data["norms"];state=data["truth_x"]*norms["x_std"]+norms["x_mean"];disp=state[...,30:38].reshape(*state.shape[:-1],4,2);dn=np.linalg.norm(disp,axis=-1);direction=disp/np.maximum(dn[...,None],1e-12);points=data["truth_f"][...,:8]*norms["force_std"][:8]+norms["force_mean"][:8];points=points.reshape(*points.shape[:-1],4,2);magnitude=np.maximum(np.sum(points*direction,axis=-1),0.);return {"direction":direction,"displacement_norm":dn,"points":points,"magnitude":magnitude}

def feature(data:dict[str,Any],h:int)->np.ndarray:return np.c_[np.ones(len(data["x0"])),data["x0"],data["u"][:,:h].reshape(len(data["x0"]),-1)]
