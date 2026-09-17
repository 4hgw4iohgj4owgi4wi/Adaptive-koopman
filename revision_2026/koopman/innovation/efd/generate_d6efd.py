from __future__ import annotations
import json,sys,time,math
from pathlib import Path
from typing import Any
import numpy as np
from audit import sha256

SCENARIOS=("staged_100m","connector_directional","single_lane_change","hairpin")
def pilot_jobs()->list[dict[str,Any]]:return [{"split":"pilot","scenario":SCENARIOS[i%4],"seed":190001+i,"trajectory_id":190001+i,"regime":f"R{i%4}"} for i in range(16)]

def formal_jobs()->list[dict[str,Any]]:
    jobs=[];scenes=(("E0","E2"),("E1","E6"),("E5","E2"),("E3","E6"))
    for split,start,per in (("train",191001,64),("validation",192001,24),("development",193001,16)):
        for g in range(4):
            for i in range(per):
                seed=start+g*per+i;pair_seed=start+g*per+(i//2)*2;sign=-1. if i%2==0 else 1.;speed=(2.,4.,4.,4.)[g];front=(0.,15.,15.,15.)[g];rear=(0.,-1.,-1.,-1.)[g];mode=("none","diagonal","diagonal","diagonal")[g];profile=("hold","hold","reversal","reversal")[g]
                config={"config_id":6000+g*100+i,"speed":speed,"front_deg":front,"rear_ratio":rear,"mode":mode,"profile":profile,"forced_sign":sign}
                jobs.append({"split":split,"scenario":scenes[g][i%2],"physical_scene":scenes[g][i%2],"seed":seed,"trajectory_id":seed,"traj_id":seed,"regime":f"R{g}","external":False,"parameter_external":False,"network_profile":"clean","network_trace_id":"clean","coverage_tier":"D6-EFD","config":config,"pair_rng_seed":pair_seed,"mirror_pair_id":f"{split}_R{g}_{i//2:03d}","mirror_sign":sign})
    return jobs

def train_scales(project:Path)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman"
    if str(koop) not in sys.path:sys.path.insert(0,str(koop))
    import generate_compare as gen,compare_pipeline as cp
    return gen.train_scales(cp.DATA)

def _simulate_config(job:dict[str,Any],scales:dict[str,Any])->tuple[dict[str,np.ndarray],dict[str,Any]]:
    import generate_compare as compare_gen,universal_pipeline as uv,generate_k2 as base
    config=job["config"];original_physical=compare_gen.physical_command;original_e9=compare_gen.e9_excitation;original_allocate=base.allocate_controls;current={"signal":0.,"sign":config["forced_sign"]}
    def physical(scene:str,t:float,speed:float,phase:float,ignored_sign:float):
        if t>=14.:current["signal"]=0.;return original_physical(scene,t,speed,phase,config["forced_sign"])
        signal=uv.excitation_signal(t,str(config["profile"]));current["signal"]=signal;front=config["forced_sign"]*float(config["front_deg"])*signal;return base.target_speed_accel(speed,float(config["speed"])),front,float(config["rear_ratio"])*front
    def e9(t:float,phase:float,local_scales:dict[str,np.ndarray]):
        if t>=14.:current["signal"]=0.;return original_e9(t,phase,local_scales)
        signal=uv.excitation_signal(t,str(config["profile"]));current["signal"]=signal;front=config["forced_sign"]*float(config["front_deg"])*signal;correction=base.target_speed_accel(0.,float(config["speed"]))-base.target_speed_accel(0.,2.2);return correction,front,float(config["rear_ratio"])*front,np.zeros(4)
    def allocate(state,accel,front,rear,params,cfg):
        controls,allocation=original_allocate(state,accel,front,rear,params,cfg);amplitude=0. if config["mode"]=="none" else 1.2;controls[:,0]=np.clip(controls[:,0]+amplitude*current["signal"]*config["forced_sign"]*uv.MODES[str(config["mode"])],-1.4,1.2);return controls,allocation
    compare_gen.physical_command=physical;compare_gen.e9_excitation=e9;base.allocate_controls=allocate
    try:
        sim_job={**job,"seed":job["pair_rng_seed"],"traj_id":job["pair_rng_seed"]};arrays,meta=compare_gen.simulate(sim_job,scales)
    finally:compare_gen.physical_command=original_physical;compare_gen.e9_excitation=original_e9;base.allocate_controls=original_allocate
    meta.update({"seed":job["seed"],"trajectory_id":job["trajectory_id"],"traj_id":job["trajectory_id"],"simulation_rng_seed":job["pair_rng_seed"],"mirror_pair_id":job["mirror_pair_id"],"mirror_sign":job["mirror_sign"],"regime":job["regime"],"split":job["split"],"coverage_config":config});return arrays,meta

def simulate_one(project_root:str,job:dict[str,Any],target_s:str,scales:dict[str,Any]|None=None)->dict[str,Any]:
    project=Path(project_root);koop=project/"revision_2026"/"koopman";model=project/"revision_2026"/"model"
    for p in (koop,model):
        if str(p) not in sys.path:sys.path.insert(0,str(p))
    import generate_k2 as base
    from four_vehicle_coupled import ModelParams,VehicleParams,PayloadParams,ConnectorParams,connector_diagnostics,rotation
    target=Path(target_s)
    if target.exists():return {**job,"file":target.name,"sha256":sha256(target),"resumed":True}
    arrays,meta=(base.simulate(job["scenario"],job["trajectory_id"],job["seed"],False) if "config" not in job else _simulate_config(job,scales if scales is not None else train_scales(project)));pd=meta["params"];params=ModelParams(vehicle=VehicleParams(**pd["vehicle"]),payload=PayloadParams(**pd["payload"]),connector=ConnectorParams(**pd["connector"]))
    vehicle_force=[];payload_force=[];internal=[]
    for state in np.asarray(arrays["s2_four"],float):
        diag=connector_diagnostics(state,params);rp=rotation(state[26]);vf=np.asarray(diag["force_vehicle_world_n"])@rp;pf=np.asarray(diag["force_payload_body_n"]);vehicle_force.append(vf);payload_force.append(pf);internal.append(vf+pf)
    n=len(arrays["s3_deform"]);vehicles=np.asarray(arrays["s2_four"][:,:24]).reshape(n,4,6);system_yaw=np.arctan2(np.mean(np.sin(vehicles[:,:,2]),axis=1),np.mean(np.cos(vehicles[:,:,2]),axis=1));force=np.asarray(payload_force,float);disp=np.asarray(arrays["displacement_body"],float);gap=np.maximum(np.linalg.norm(disp,axis=-1)-params.connector.free_play_m,0)
    enriched={**arrays,"connector_disp_payload_frame":disp.astype(np.float32),"connector_rel_vel_payload_frame":np.asarray(arrays["relative_velocity_body"],np.float32),"force_on_payload":force.astype(np.float32),"force_on_vehicle":np.asarray(vehicle_force,np.float32),"action_reaction_residual":np.asarray(internal,np.float32),"payload_yaw":np.asarray(arrays["s2_four"][:,26],np.float32),"system_yaw":system_yaw.astype(np.float32),"connector_gap":gap.astype(np.float32),"stiffness":np.full((n,4),params.connector.stiffness_npm,np.float32),"damping":np.full((n,4),params.connector.damping_nspm,np.float32),"saturation_flags":np.zeros((n,4),np.uint8)}
    meta.update({"split":job["split"],"regime":job["regime"],"trajectory_id":job["trajectory_id"],"efd_protocol":"D6-EFD","force_vehicle_source":"direct connector_diagnostics.force_vehicle_world_n transformed to payload frame; not reconstructed from payload log","field_time_alignment":"all state/disp/velocity/force rows at t_k; u[k] held to t_k+1"});target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix(".tmp.npz");np.savez_compressed(tmp,**enriched,metadata_json=np.asarray(json.dumps(meta,ensure_ascii=False)));tmp.replace(target)
    return {**job,"file":target.name,"sha256":sha256(target),"steps":int(n-1),"bytes":target.stat().st_size,"ultimate_steps":meta["ultimate_exceeded_steps"],"finite":meta["finite"],"max_connector_force_n":meta["max_connector_force_n"],"resumed":False}
