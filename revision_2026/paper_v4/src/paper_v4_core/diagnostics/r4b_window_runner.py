"""EXP-R4-B B2b restored-state serial or 8-process closed-loop window."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import numpy as np

from ..cli import save, sha
from ..controllers import physical_tracking_pilot as controller
from ..controllers.parallel_fd_backend import ParallelFiniteDifferenceBackend, install_parallel_linearization
from ..controllers.physical_tracking_pilot import PilotConfig
from ..diagnostics.qp_fd_trials import array_digest
from ..diagnostics.qp_sensitivity import load_raw, reference_state, row_at, state_and_previous
from ..diagnostics.relative_motion import extract
from ..e01_100m import DT, LIMIT, RATE, TAU, params
from ..failure_boundary import consume_audit
from ..pilot_runner import ROUTE_LENGTH, SPEED, _path_sample, make_preview
from ..plant.event_substep import EventSubstepConfig, advance_outer_step
from ..plant.four_vehicle_common import connector_diagnostics, system_derivative
from ..reference_geometry import transition_targets


def checkpoint(out, rows, columns, subrows, subcolumns, status):
    np.savez_compressed(out/"raw.npz",values=np.asarray(rows,float),columns=np.asarray(columns))
    sub=np.asarray(subrows,float) if subrows else np.empty((0,len(subcolumns)))
    np.savez_compressed(out/"substeps.npz",values=sub,columns=np.asarray(subcolumns))
    save(out,"status.json",status)


def execute(out, source, implementation, start_s, end_s, deadline_unix):
    values,c=load_raw(source); start_row=row_at(values,c,start_s); state_delta,previous_u=state_and_previous(start_row,c)
    state=state_delta[:30].copy();delta=state_delta[30:].copy();model=params("P0")
    distance,beta,_,_=reference_state(start_s,model,previous_u)
    if abs(distance-float(start_row[c["reference_distance_m"]]))>1e-12: raise ValueError("REFERENCE_DISTANCE_RESTORE_MISMATCH")
    rows=[];subrows=[];actual_path=float(start_row[c["actual_payload_path_m"]]);last_payload=state[24:26].copy();max_force=max_internal=max_tire=0.;min_support=float("inf");max_eg=0.;reason=None;status="RUNNING";started=time.perf_counter()
    columns=["time_s","reference_distance_m","actual_payload_path_m","lambda_internal"]+[f"x{i}" for i in range(30)]+[f"request_accel{i}" for i in range(4)]+[f"request_delta{i}" for i in range(4)]+[f"actual_delta{i}" for i in range(4)]+[f"point_force_norm{i}" for i in range(4)]+[f"tire_utilization{i}" for i in range(4)]+[f"support_load{i}" for i in range(4)]+["internal_force_norm_n","tension_x_n","tension_y_n","max_e_g_m","solver_wall_s"]
    subcolumns=["time_s","dt_s"]+[f"force_peak{i}" for i in range(4)]+[f"force_impulse_x{i}" for i in range(4)]+[f"force_impulse_y{i}" for i in range(4)]+[f"tire_utilization{i}" for i in range(4)]+[f"support_load{i}" for i in range(4)]
    start_tick=int(round(start_s/DT)); count=int(round((end_s-start_s)/DT)); solver_path=out/"solver.jsonl"; handle=solver_path.open("w",encoding="utf-8")
    try:
        for local_tick in range(count):
            if time.time()>deadline_unix: status="TIMEOUT_INCOMPLETE";reason="B2_COMBINED_DEADLINE";break
            absolute_tick=start_tick+local_tick;t=start_s+local_tick*DT;u_nom,refs,_=make_preview(distance,beta,model,previous_u,20);config=PilotConfig(horizon=20,lambda_internal=2.,frozen_dynamics_jacobian=False,finite_difference_scale=1.)
            result=controller.solve(np.r_[state,delta],u_nom,refs,model,config)
            problem=result["problem"]; hashes={name:array_digest(np.asarray(problem[name])) for name in ("P","q","A","l","u","u_nom")} if problem is not None else None
            record={key:result[key] for key in ("status","solver_status","iterations","primal_residual","dual_residual","objective","wall_s")};record.update({"tick":absolute_tick,"time_s":t,"validation":result["validation"],"first_control":result["control"][0].tolist(),"last_control":result["control"][-1].tolist(),"problem_hashes":hashes});handle.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+"\n");handle.flush()
            if result["status"]!="PASS":status="FAILED";reason="MPC_"+str(result["solver_status"]);break
            command=np.asarray(result["control"][0]).reshape(4,2);previous_u=result["control"][0].copy();interval_duration=0.
            for _ in range(10):
                delta_before=delta.copy();free=command[:,1]+np.exp(-.002/TAU)*(delta-command[:,1]);delta=np.clip(delta+np.clip(free-delta,-RATE*.002,RATE*.002),-LIMIT,LIMIT)
                state,audit=advance_outer_step(state,np.c_[command[:,0],delta],"R3",model,.002,"ES",EventSubstepConfig(),max_step_s=.002,load_transfer_enabled=True)
                boundary=consume_audit(audit,t+interval_duration,state,delta_before,delta);local=0.
                for seg in boundary["segments"]:
                    local+=float(seg["dt_s"]);fp=np.asarray(seg["force_peak_n"]);imp=np.asarray(seg["force_interval_impulse_world_ns"]);util=np.asarray(seg["tire_raw_utilization"]);support=np.asarray(seg["payload_support_load_n"]);subrows.append(np.r_[t+interval_duration+local,seg["dt_s"],fp,imp[:,0],imp[:,1],util,support]);max_force=max(max_force,float(np.max(fp)));max_tire=max(max_tire,float(np.max(util)));min_support=min(min_support,float(np.min(support)))
                interval_duration+=boundary["accepted_duration_s"]
                if audit["status"]!="PASS":status="FAILED";reason=audit["status"];break
            distance=min(distance+SPEED*interval_duration,ROUTE_LENGTH);beta=beta+(interval_duration/DT)*(np.asarray(refs[0]["beta_star"])-beta)
            diag=connector_diagnostics(state,model,"R3");_,system=system_derivative(state,np.c_[command[:,0],delta],model,"R3",load_transfer_enabled=True);force=np.asarray(diag["force_norm_n"]);tire=np.asarray([item["raw_utilization"] for item in system["tire"]]);support=np.asarray(system["payload_support_load_n"]);qstar=transition_targets(np.asarray([SPEED,0.]),SPEED*_path_sample(distance)[3],beta,model)["centers"];rel=extract(state,model,qstar,beta);eg=float(np.max(np.linalg.norm(rel["e_g_m"],axis=1)));payload=state[24:26];actual_path+=float(np.linalg.norm(payload-last_payload));last_payload=payload.copy();max_force=max(max_force,float(np.max(force)));max_internal=max(max_internal,float(diag["internal_force_norm_n"]));max_tire=max(max_tire,float(np.max(tire)));min_support=min(min_support,float(np.min(support)));max_eg=max(max_eg,eg)
            rows.append(np.r_[t+interval_duration,distance,actual_path,2.,state,command[:,0],command[:,1],delta,force,tire,support,diag["internal_force_norm_n"],diag["tension_x_n"],diag["tension_y_n"],eg,result["wall_s"]])
            if max_force>15000.+1e-6:status="FAILED";reason="STOP_ULTIMATE_FORCE_ENDPOINT"
            elif max_tire>1.+1e-9:status="FAILED";reason="TIRE_CAPABILITY_VIOLATION"
            elif min_support<0.:status="FAILED";reason="SUPPORT_LIFT"
            if status!="RUNNING":break
            if (local_tick+1)%5==0:
                checkpoint(out,rows,columns,subrows,subcolumns,{"status":"RUNNING","implementation":implementation,"completed_ticks":local_tick+1,"total_ticks":count,"time_s":t+interval_duration,"updated_unix":time.time(),"deadline_unix":deadline_unix})
                print(json.dumps({"implementation":implementation,"completed":local_tick+1,"total":count,"last_solver_s":result["wall_s"]}),flush=True)
        if status=="RUNNING": status="COMPLETED" if len(rows)==count else "PAUSED"
    finally: handle.close()
    metrics={"status":status,"reason":reason,"candidate_id":"EXP-R3-unfrozen-v1","implementation_id":"EXP-R4B-serial-v1" if implementation=="serial" else "EXP-R4B-parallel8-v1","start_s":start_s,"end_s":end_s,"iterations":len(rows),"expected_iterations":count,"duration_s":float(rows[-1][0]-start_s) if rows else 0.,"reference_distance_m":distance,"maximum_point_force_n":max_force,"maximum_internal_force_norm_n":max_internal,"maximum_tire_utilization":max_tire,"minimum_support_load_n":min_support,"maximum_configuration_error_m":max_eg,"wall_s":time.perf_counter()-started,"source_sha256":sha(__file__),"controller_sha256":sha(Path(controller.__file__)),"deadline_unix":deadline_unix}
    checkpoint(out,rows,columns,subrows,subcolumns,metrics);save(out,"metrics.json",metrics);print(json.dumps(metrics,ensure_ascii=False),flush=True)
    if status!="COMPLETED": raise SystemExit(20)


def main():
    p=argparse.ArgumentParser();p.add_argument("--source",required=True);p.add_argument("--implementation",choices=("serial","parallel8"),required=True);p.add_argument("--start-s",type=float,default=42.0);p.add_argument("--end-s",type=float,default=44.5);p.add_argument("--deadline-unix",type=float,required=True);p.add_argument("--protocol",required=True);p.add_argument("--protocol-sha",required=True);p.add_argument("--out",required=True);a=p.parse_args()
    protocol=Path(a.protocol).resolve()
    if sha(protocol)!=a.protocol_sha.lower(): raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    out=Path(a.out).resolve()
    if out.exists(): raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    out.mkdir(parents=True)
    if a.implementation=="parallel8":
        values,c=load_raw(Path(a.source).resolve());sample=row_at(values,c,a.start_s);z0,prev=state_and_previous(sample,c);model=params("P0");_,_,u,_=reference_state(a.start_s,model,prev)
        with ParallelFiniteDifferenceBackend(8) as backend:
            warm=backend.warm(z0,u[0],model);save(out,"pool.json",{"workers":8,"warmup_s":warm})
            with install_parallel_linearization(backend): execute(out,Path(a.source).resolve(),a.implementation,a.start_s,a.end_s,a.deadline_unix)
    else: execute(out,Path(a.source).resolve(),a.implementation,a.start_s,a.end_s,a.deadline_unix)


if __name__=="__main__": main()
