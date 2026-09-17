from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass
class DirectionPrediction:
    state_s3:np.ndarray;axial_magnitude:np.ndarray;point_force:np.ndarray;payload_load:np.ndarray;force_rate:np.ndarray;direction_valid:np.ndarray;fallback_mask:np.ndarray

def validate_direction_prediction(p:DirectionPrediction)->None:
    b=len(p.state_s3);expected={"state_s3":(b,20,46),"axial_magnitude":(b,20,4),"point_force":(b,20,4,2),"payload_load":(b,20,2),"force_rate":(b,20,4,2),"direction_valid":(b,20,4),"fallback_mask":(b,20,4)}
    for key,shape in expected.items():
        value=np.asarray(getattr(p,key))
        if value.shape!=shape:raise ValueError(f"{key} {value.shape}!={shape}")
        if key not in ("direction_valid","fallback_mask") and not np.all(np.isfinite(value)):raise ValueError(f"{key} nonfinite")
    if np.min(p.axial_magnitude)<-1e-12:raise ValueError("negative axial magnitude")
    q=reconstruct_load_check(p.point_force)
    if not np.allclose(q,p.payload_load,rtol=0,atol=1e-10):raise ValueError("Q algebraic mismatch")

def reconstruct_load_check(points:np.ndarray)->np.ndarray:
    qfr=.5*((points[...,0,0]+points[...,1,0])-(points[...,2,0]+points[...,3,0]));qlr=.5*((points[...,0,1]+points[...,2,1])-(points[...,1,1]+points[...,3,1]));return np.stack([qfr,qlr],axis=-1)
