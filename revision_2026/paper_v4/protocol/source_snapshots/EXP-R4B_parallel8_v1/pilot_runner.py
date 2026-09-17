"""EXP-R2 R2b/R2c runner for the centralized full-state physical MPC pilot."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from .cli import save,sha
from .controllers.physical_tracking_pilot import PilotConfig,solve
from .diagnostics.relative_motion import extract
from .e01_100m import DT,LIMIT,RATE,TAU,params
from .failure_boundary import consume_audit
from .plant.event_substep import EventSubstepConfig,advance_outer_step
from .plant.four_vehicle_common import connector_diagnostics,initialize_state,rotation,split_state,system_derivative
from .reference_geometry import transition_targets
from .references import build_hairpin


SPEED=2.0;PATH=build_hairpin();ROUTE_LENGTH=float(PATH["s_m"][-1])


def _path_sample(distance):
    s=min(max(float(distance),0.0),ROUTE_LENGTH)
    return np.asarray([np.interp(s,PATH["s_m"],PATH[name]) for name in ("x_m","y_m","heading_rad","curvature_1pm")])


def make_preview(distance,beta,model,previous_u,horizon=20):
    refs=[];controls=[];b=np.asarray(beta,float).copy()
    for h in range(horizon):
        s=min(distance+(h+1)*SPEED*DT,ROUTE_LENGTH);x,y,heading,curvature=_path_sample(s);yaw=SPEED*curvature
        target=transition_targets(np.asarray([SPEED,0.]),yaw,b,model);b=b+DT*target["beta_dot"];target_end=transition_targets(np.asarray([SPEED,0.]),yaw,b,model)
        u=np.empty(8);u[0::2]=0.;u[1::2]=target_end["steering"];controls.append(u)
        refs.append({"payload":np.asarray([x,y,heading,SPEED,0.,yaw]),"q_star":target_end["centers"],"beta_star":b.copy(),"q_dot_star":target_end["center_rates"],"steering_nominal":target_end["steering"],"previous_u":np.asarray(previous_u,float)})
    return np.asarray(controls),refs,b


def _checkpoint(out,rows,columns,subrows,subcolumns,status):
    np.savez_compressed(out/"raw.npz",values=np.asarray(rows,float),columns=np.asarray(columns))
    sub=np.asarray(subrows,float) if subrows else np.empty((0,len(subcolumns)))
    np.savez_compressed(out/"substeps.npz",values=sub,columns=np.asarray(subcolumns))
    save(out,"status.json",status)


def run(out,parameter_id="P0",max_step_s=.002,lambda_internal=1.,segment_s=18.,frozen_dynamics_jacobian=True,finite_difference_scale=1.0):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);model=params(parameter_id);state=initialize_state(model,SPEED);delta=np.zeros(4);beta=np.zeros(4);previous_u=np.zeros(8);distance=0.;rows=[];subrows=[];solver_path=out/"solver.jsonl";started=time.perf_counter();status="RUNNING";reason=None;actual_path=0.;last_payload=state[24:26].copy();max_force=max_internal=max_tire=0.;min_support=float("inf");max_eg=0.;iterations=0
    columns=["time_s","reference_distance_m","actual_payload_path_m","lambda_internal"]+[f"x{i}" for i in range(30)]+[f"request_accel{i}" for i in range(4)]+[f"request_delta{i}" for i in range(4)]+[f"actual_delta{i}" for i in range(4)]+[f"point_force_norm{i}" for i in range(4)]+[f"tire_utilization{i}" for i in range(4)]+[f"support_load{i}" for i in range(4)]+["internal_force_norm_n","tension_x_n","tension_y_n","max_e_g_m","solver_wall_s"]
    subcolumns=["time_s","dt_s"]+[f"force_peak{i}" for i in range(4)]+[f"force_impulse_x{i}" for i in range(4)]+[f"force_impulse_y{i}" for i in range(4)]+[f"tire_utilization{i}" for i in range(4)]+[f"support_load{i}" for i in range(4)]
    count=int(np.ceil(float(segment_s)/DT));solver_handle=solver_path.open("w",encoding="utf-8")
    try:
        for k in range(count):
            t=k*DT;u_nom,refs,beta_preview=make_preview(distance,beta,model,previous_u,20);config=PilotConfig(horizon=20,lambda_internal=float(lambda_internal),frozen_dynamics_jacobian=bool(frozen_dynamics_jacobian),finite_difference_scale=float(finite_difference_scale));result=solve(np.r_[state,delta],u_nom,refs,model,config)
            solver_record={key:result[key] for key in ("status","solver_status","iterations","primal_residual","dual_residual","objective","wall_s")};solver_record.update({"tick":k,"time_s":t,"validation":result["validation"],"first_control":result["control"][0].tolist(),"last_control":result["control"][-1].tolist()});solver_handle.write(json.dumps(solver_record,ensure_ascii=False,allow_nan=False)+"\n");solver_handle.flush()
            if result["status"]!="PASS":status="FAILED";reason="MPC_"+str(result["solver_status"]);break
            command=np.asarray(result["control"][0]).reshape(4,2);previous_u=result["control"][0].copy();interval_duration=0.;interval_segments=[]
            for _ in range(10):
                delta_before=delta.copy();free=command[:,1]+np.exp(-.002/TAU)*(delta-command[:,1]);delta=np.clip(delta+np.clip(free-delta,-RATE*.002,RATE*.002),-LIMIT,LIMIT)
                try: state,audit=advance_outer_step(state,np.c_[command[:,0],delta],"R3",model,.002,"ES",EventSubstepConfig(),max_step_s=max_step_s,load_transfer_enabled=True)
                except Exception as error: status="FAILED";reason=f"PLANT_{type(error).__name__}";break
                boundary=consume_audit(audit,t+interval_duration,state,delta_before,delta);interval_segments.extend(boundary["segments"]);local=0.
                for seg in boundary["segments"]:
                    local+=float(seg["dt_s"]);fp=np.asarray(seg["force_peak_n"]);imp=np.asarray(seg["force_interval_impulse_world_ns"]);util=np.asarray(seg["tire_raw_utilization"]);support=np.asarray(seg["payload_support_load_n"]);subrows.append(np.r_[t+interval_duration+local,seg["dt_s"],fp,imp[:,0],imp[:,1],util,support]);max_force=max(max_force,float(np.max(fp)));max_tire=max(max_tire,float(np.max(util)));min_support=min(min_support,float(np.min(support)))
                interval_duration+=boundary["accepted_duration_s"]
                if audit["status"]!="PASS":status="FAILED";reason=audit["status"];break
            distance=min(distance+SPEED*interval_duration,ROUTE_LENGTH);beta=beta+(interval_duration/DT)*(np.asarray(refs[0]["beta_star"])-beta)
            diag=connector_diagnostics(state,model,"R3");_,system=system_derivative(state,np.c_[command[:,0],delta],model,"R3",load_transfer_enabled=True);force=np.asarray(diag["force_norm_n"]);tire=np.asarray([item["raw_utilization"] for item in system["tire"]]);support=np.asarray(system["payload_support_load_n"]);qstar=transition_targets(np.asarray([SPEED,0.]),SPEED*_path_sample(distance)[3],beta,model)["centers"];rel=extract(state,model,qstar,beta);eg=float(np.max(np.linalg.norm(rel["e_g_m"],axis=1)));payload=state[24:26];actual_path+=float(np.linalg.norm(payload-last_payload));last_payload=payload.copy();max_force=max(max_force,float(np.max(force)));max_internal=max(max_internal,float(diag["internal_force_norm_n"]));max_tire=max(max_tire,float(np.max(tire)));min_support=min(min_support,float(np.min(support)));max_eg=max(max_eg,eg)
            rows.append(np.r_[t+interval_duration,distance,actual_path,lambda_internal,state,command[:,0],command[:,1],delta,force,tire,support,diag["internal_force_norm_n"],diag["tension_x_n"],diag["tension_y_n"],eg,result["wall_s"]]);iterations=k+1
            if max_force>15000.+1e-6:status="FAILED";reason="STOP_ULTIMATE_FORCE_ENDPOINT"
            elif max_tire>1.+1e-9:status="FAILED";reason="TIRE_CAPABILITY_VIOLATION"
            elif min_support<0.:status="FAILED";reason="SUPPORT_LIFT"
            if status=="FAILED":break
            if (k+1)%25==0:_checkpoint(out,rows,columns,subrows,subcolumns,{"status":"RUNNING","tick":k+1,"time_s":t+interval_duration,"reference_distance_m":distance,"updated_unix":time.time()})
        if status=="RUNNING":status="COMPLETED" if iterations==count else "PAUSED"
    finally:
        solver_handle.close()
    metrics={"status":status,"reason":reason,"role":"DEV","identity":"Centralized Full-State Physical Model Predictive Control diagnostic upper bound","candidate_id":"EXP-R3-unfrozen-v1" if not frozen_dynamics_jacobian else "EXP-R2-frozen-v1","parameter_id":parameter_id,"lambda_internal":lambda_internal,"horizon":20,"controller_step_s":DT,"plant_step_s":.002,"maximum_plant_step_s":max_step_s,"requested_segment_s":segment_s,"iterations":iterations,"duration_s":float(rows[-1][0]) if rows else 0.,"reference_distance_m":distance,"route_length_m":ROUTE_LENGTH,"actual_payload_path_m":actual_path,"maximum_point_force_n":max_force,"maximum_internal_force_norm_n":max_internal,"maximum_tire_utilization":max_tire,"minimum_support_load_n":min_support,"maximum_configuration_error_m":max_eg,"trajectory_completed":bool(status=="COMPLETED" and (segment_s<ROUTE_LENGTH/SPEED or distance>=ROUTE_LENGTH-1e-9)),"predicted_force_budget_n":12000.,"ultimate_stop_n":15000.,"solver_calls":iterations+(1 if status=="FAILED" and reason and reason.startswith("MPC_") else 0),"frozen_dynamics_jacobian":bool(frozen_dynamics_jacobian),"finite_difference_scale":float(finite_difference_scale),"wall_s":time.perf_counter()-started,"source_sha256":sha(__file__)}
    _checkpoint(out,rows,columns,subrows,subcolumns,metrics);save(out,"metrics.json",metrics);print(json.dumps(metrics,ensure_ascii=False));
    if status!="COMPLETED":raise SystemExit(20)


def main():
    p=argparse.ArgumentParser();p.add_argument("--out",required=True);p.add_argument("--parameter",choices=["P0","P1","P2"],default="P0");p.add_argument("--max-step-ms",type=float,choices=[2.,1.,.5],default=2.);p.add_argument("--lambda-internal",type=float,choices=[1.,2.],required=True);p.add_argument("--segment-s",type=float,default=18.);p.add_argument("--dynamics-jacobian",choices=["frozen","unfrozen"],default="frozen");p.add_argument("--finite-difference-scale",type=float,default=1.0);a=p.parse_args();run(a.out,a.parameter,a.max_step_ms/1000.,a.lambda_internal,a.segment_s,a.dynamics_jacobian=="frozen",a.finite_difference_scale)
if __name__=="__main__":main()
