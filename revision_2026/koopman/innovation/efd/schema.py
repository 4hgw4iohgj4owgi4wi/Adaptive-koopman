from __future__ import annotations
from dataclasses import dataclass,asdict
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class StateField:
    index:int;name:str;unit:str;frame:str;sample_time:str;source_path:str;source_line:int

def load_schema(project:Path)->dict[str,Any]:
    gen=project/"revision_2026"/"koopman"/"generate_k2.py";plant=project/"revision_2026"/"model"/"four_vehicle_coupled.py";fields=[];names=("FL","FR","RL","RR")
    base=("x","y","yaw","vx","vy","yaw_rate");units=("m","m","rad","m/s","m/s","rad/s")
    for corner in names:
        for name,unit in zip(base,units):fields.append(StateField(len(fields),f"vehicle_{corner}_{name}",unit,"world position/yaw; vehicle body velocity", "t_k",str(plant),98))
    for name,unit in zip(base,units):fields.append(StateField(len(fields),f"payload_{name}",unit,"world position/yaw; payload body velocity","t_k",str(plant),98))
    for corner in names:
        for component in ("x","y"):fields.append(StateField(len(fields),f"connector_disp_{corner}_{component}","m","payload body; vehicle anchor minus payload anchor","t_k",str(gen),201))
    for corner in names:
        for component in ("x","y"):fields.append(StateField(len(fields),f"connector_rel_vel_{corner}_{component}","m/s","payload body; vehicle anchor velocity minus payload anchor velocity","t_k",str(gen),206))
    controls=[]
    for corner in names:
        controls.extend([{"index":len(controls),"name":f"{corner}_acceleration","unit":"m/s2","frame":"vehicle body","sample_time":"held over [t_k,t_k+1)"},{"index":len(controls),"name":f"{corner}_steering","unit":"rad","frame":"vehicle body","sample_time":"held over [t_k,t_k+1)"}])
    forces=[]
    for corner in names:
        for component in ("Fx","Fy"):forces.append({"index":len(forces),"name":f"payload_{corner}_{component}","unit":"N","frame":"payload body","sample_time":"t_k"})
    forces += [{"index":8,"name":"Q_FR","unit":"N","frame":"payload body","sample_time":"t_k"},{"index":9,"name":"Q_LR","unit":"N","frame":"payload body","sample_time":"t_k"}]
    for corner in names:
        for component in ("dFx_dt","dFy_dt"):forces.append({"index":len(forces),"name":f"payload_{corner}_{component}","unit":"N/s","frame":"payload body","sample_time":"causal (F_k-F_k-1)/0.02"})
    return {"state_dim":46,"control_dim":8,"output_dim":64,"force_output_dim":18,"corner_order":list(names),"component_order":["x","y"],"state_fields":[asdict(x) for x in fields],"control_fields":controls,"force_fields":forces,"connector_contract":{"displacement_definition":"vehicle_anchor - payload_anchor","force_logged":"force_on_payload","force_direction_sign":1,"same_frame":"payload body","axial_only":True,"free_play_m":.002,"stiffness_npm":30000.,"damping_nspm":3500.,"damping_rule":"loading only max(v_dot_n,0)","preload":False,"hysteresis":False,"tangential_force":False,"explicit_saturation":False,"corner_source":"payload anchors lines 63-66 => FL,FR,RL,RR"},"evidence":[{"path":str(plant),"lines":"38-43","claim":"connector constants"},{"path":str(plant),"lines":"51-66","claim":"corner anchors/order"},{"path":str(plant),"lines":"105-146","claim":"displacement, relative velocity, axial law, payload/vehicle forces"},{"path":str(gen),"lines":"201-251","claim":"payload-frame synchronous log and S3/force mapping"}]}

def validate_corner_order(schema:dict[str,Any])->None:
    assert schema["corner_order"]==["FL","FR","RL","RR"]
    assert len(schema["state_fields"])==46 and len(schema["control_fields"])==8 and len(schema["force_fields"])==18
    assert [x["index"] for x in schema["state_fields"]]==list(range(46))
