from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import numpy as np

LAW_VERSION='plant_v2_hc_smooth'

@dataclass(frozen=True)
class ConnectorV2Params:
    law_version:str=LAW_VERSION
    contact_exponent_n:float=1.5
    contact_stiffness_K:float=1.0
    hysteresis_damping_CH:float=0.0
    free_play_m:float=0.002
    maximum_working_displacement_m:float=0.05
    failure_displacement_m:float=0.06
    rated_force_n:float=12000.0
    ultimate_force_n:float=15000.0
    force_cap_enabled:bool=True

@dataclass(frozen=True)
class ConnectorResult:
    distance_m:np.ndarray
    penetration_m:np.ndarray
    normal_world:np.ndarray
    normal_speed_mps:np.ndarray
    constitutive_trial_force_n:np.ndarray
    raw_force_n:np.ndarray
    applied_force_n:np.ndarray
    force_payload_world_n:np.ndarray
    force_vehicle_world_n:np.ndarray
    elastic_energy_j:np.ndarray
    damping_power_w:np.ndarray
    contact_active:np.ndarray
    limit_flags:dict[str,np.ndarray]

def connector_force_v2(displacement_world:np.ndarray,relative_velocity_world:np.ndarray,params:ConnectorV2Params)->ConnectorResult:
    d=np.asarray(displacement_world,float);v=np.asarray(relative_velocity_world,float)
    if d.shape!=v.shape or d.shape[-1]!=2:raise ValueError('displacement and velocity must share [...,2] shape')
    if params.contact_exponent_n<=1.:raise ValueError('V2 requires n>1 for zero boundary tangent')
    if min(params.contact_stiffness_K,params.hysteresis_damping_CH,params.free_play_m,params.rated_force_n,params.ultimate_force_n)<0:raise ValueError('nonnegative connector parameters required')
    r=np.linalg.norm(d,axis=-1);nvec=d/np.maximum(r[...,None],1e-12);delta=np.maximum(r-params.free_play_m,0.);vn=np.sum(v*nvec,axis=-1);dn=np.power(delta,params.contact_exponent_n)
    trial=dn*(params.contact_stiffness_K+params.hysteresis_damping_CH*vn);raw=np.maximum(trial,0.);applied=np.minimum(raw,params.ultimate_force_n) if params.force_cap_enabled else raw
    fp=applied[...,None]*nvec;active=delta>0.;diss=np.where(active & (trial>0.),params.hysteresis_damping_CH*dn*vn*vn,0.);energy=params.contact_stiffness_K/(params.contact_exponent_n+1.)*np.power(delta,params.contact_exponent_n+1.)
    flags={'working_displacement_exceeded':delta>params.maximum_working_displacement_m,'failure_displacement_exceeded':delta>=params.failure_displacement_m,'rated_force_exceeded':raw>=params.rated_force_n,'ultimate_force_exceeded':raw>=params.ultimate_force_n}
    return ConnectorResult(r,delta,nvec,vn,trial,raw,applied,fp,-fp,energy,diss,active,flags)

def params_from_dict(value:dict[str,Any])->ConnectorV2Params:return ConnectorV2Params(**{k:value[k] for k in ConnectorV2Params.__dataclass_fields__ if k in value})

