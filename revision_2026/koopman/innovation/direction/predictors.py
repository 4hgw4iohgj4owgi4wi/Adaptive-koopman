from __future__ import annotations
from typing import Any
import numpy as np
from contracts import DirectionPrediction,validate_direction_prediction
from physics_decoder import unit_from_displacement,reconstruct_points,reconstruct_load,causal_force_rate,nominal_physics_decoder

def _physical_state(x:np.ndarray,n:dict[str,np.ndarray])->np.ndarray:return np.asarray(x,float)*n["x_std"]+n["x_mean"]
def _physical_force(f:np.ndarray,n:dict[str,np.ndarray])->np.ndarray:return np.asarray(f,float)*n["force_std"]+n["force_mean"]

def cached_predictions(data:dict[str,Any])->dict[str,dict[str,np.ndarray]]:
    n=data["norms"];out={}
    for name,x,f in (("P0",data["p0x"],data["p0f"]),("P1",data["p1"][...,:46],data["p1"][...,46:64])):
        physical=_physical_force(f,n);points=physical[...,:8].reshape(len(f),20,4,2);out[name]={"state":np.asarray(x,float),"points":points,"q":physical[...,8:10],"rate":causal_force_rate(points,data["current"]),"valid":np.ones(points.shape[:-1],bool),"fallback":np.zeros(points.shape[:-1],bool)}
    return out

def structured_predictions(data:dict[str,Any],magnitude_head:Any,direction_floor:float)->dict[str,dict[str,np.ndarray]]:
    n=data["norms"];cached=cached_predictions(data);p0_state=_physical_state(data["p0x"],n);p1_state=_physical_state(data["p1"][...,:46],n);d0,_=unit_from_displacement(p0_state,direction_floor);d1,valid=unit_from_displacement(p1_state,direction_floor);p1mag=np.linalg.norm(cached["P1"]["points"],axis=-1)
    def make(name:str,mag:np.ndarray,direction:np.ndarray,valid_mask:np.ndarray|None=None,fallback:np.ndarray|None=None)->None:
        points=reconstruct_points(np.maximum(mag,0),direction);q=reconstruct_load(points);rate=causal_force_rate(points,data["current"]);v=np.ones(mag.shape,bool) if valid_mask is None else valid_mask;fb=np.zeros(mag.shape,bool) if fallback is None else fallback;obj=DirectionPrediction(data["p1"][...,:46],np.maximum(mag,0),points,q,rate,v,fb);validate_direction_prediction(obj);out[name]={"state":obj.state_s3,"points":obj.point_force,"q":obj.payload_load,"rate":obj.force_rate,"valid":obj.direction_valid,"fallback":obj.fallback_mask}
    out={};make("P2",p1mag,d0)
    p3points,p3q,p3rate=nominal_physics_decoder(data["p1"][...,:46],data["current"],n);out["P3"]={"state":data["p1"][...,:46],"points":p3points,"q":p3q,"rate":p3rate,"valid":np.ones(p3points.shape[:-1],bool),"fallback":np.zeros(p3points.shape[:-1],bool)}
    mag=magnitude_head.predict_magnitude(data["x0"],data["u"]);active=mag>=np.asarray(magnitude_head.force_floor).reshape(1,1,4);fallback=(~valid)&active;direction=np.where(fallback[...,None],d0,d1);mag=np.where((~valid)&(~active),0,mag);make("P4",mag,direction,valid,fallback)
    return {**cached,**out}

def add_p5(predictions:dict[str,dict[str,np.ndarray]],data:dict[str,Any],head:Any)->None:
    points=head.predict(data["x0"],data["u"]);predictions["P5"]={"state":data["p1"][...,:46],"points":points,"q":reconstruct_load(points),"rate":causal_force_rate(points,data["current"]),"valid":np.ones(points.shape[:-1],bool),"fallback":np.zeros(points.shape[:-1],bool)}
