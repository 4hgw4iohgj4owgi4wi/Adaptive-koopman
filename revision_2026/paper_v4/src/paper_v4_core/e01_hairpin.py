"""Registered EXP-R1 true-hairpin open-input plant diagnostic."""
import argparse,time
from pathlib import Path
import numpy as np
from .cli import save,sha
from .e01_100m import DT,LIMIT,RATE,TAU,PARAMS,params
from .plant.four_vehicle_common import initialize_state,split_state,connector_diagnostics,system_derivative
from .plant.event_substep import EventSubstepConfig,advance_outer_step
from .failure_boundary import consume_audit
from .reference_geometry import transition_targets
from .references import build_hairpin

SPEED=2.; PATH=build_hairpin(); DURATION=float(PATH['s_m'][-1]/SPEED)
K_SPEED=.8; MAX_COMMON_ACCEL=1.2; K_HEADING=0.; K_YAW_RATE=0.

def schedule(t):
 s=min(SPEED*float(t),float(PATH['s_m'][-1]));curv=float(np.interp(s,PATH['s_m'],PATH['curvature_1pm']))
 f=np.arctan(curv*5./2.);return SPEED,0.,np.rad2deg(f),-np.rad2deg(f),s,curv

def constrained_target(speed,desired_yaw_rate,beta,p):
 """Scale one shared yaw command if necessary; never clip four wheels independently."""
 candidate=transition_targets(np.array([speed,0.]),desired_yaw_rate,beta,p)
 if np.max(abs(candidate['steering']))<=LIMIT:return candidate,float(desired_yaw_rate),False
 zero=transition_targets(np.array([speed,0.]),0.,beta,p)
 if np.max(abs(zero['steering']))>LIMIT:return zero,0.,True
 lo,hi=0.,1.
 for _ in range(50):
  mid=.5*(lo+hi);trial=transition_targets(np.array([speed,0.]),mid*desired_yaw_rate,beta,p)
  if np.max(abs(trial['steering']))<=LIMIT:lo=mid
  else:hi=mid
 allocated=lo*desired_yaw_rate;return transition_targets(np.array([speed,0.]),allocated,beta,p),float(allocated),True

def run(out,pid,max_step,cap=None):
 out=Path(out);out.mkdir(parents=True,exist_ok=False);p=params(pid);x=initialize_state(p,SPEED);beta=np.zeros(4);delta=np.zeros(4);rows=[]
 started=time.perf_counter();max_ar=max_null=closure=0.;accepted=0;status='PASS';reason='';impulse=np.zeros((4,2));peak=np.zeros(4);peak_argmax=[{'time_s':0.,'source':'none','value_n':0.} for _ in range(4)];subrows=[];minimum_support=float('inf');max_tire_util=0.;saturation_count=yaw_allocation_count=common_accel_saturation_count=0;max_target_geometry=max_request_geometry=max_actual_front=max_actual_rear=max_speed_error=max_heading_error=0.;failure_event_time=None;last_interval_start=last_interval_end=0.;last_accepted_duration=0.;actuator_update_times=[]
 requested_duration=DURATION if cap is None else min(cap,DURATION);count=int(np.ceil(requested_duration/DT))
 for k in range(count):
  t=k*DT;speed,base,fdeg,rdeg,s,curv=schedule(t);route_yaw_rate=speed*curv;href=float(np.interp(s,PATH['s_m'],PATH['heading_rad']));vehicles,payload=split_state(x);heading_error=float((payload[2]-href+np.pi)%(2*np.pi)-np.pi);speed_error=float(speed-payload[3]);desired_yaw_rate=route_yaw_rate-K_HEADING*heading_error-K_YAW_RATE*(payload[5]-route_yaw_rate);target,yaw_rate,allocated=constrained_target(speed,desired_yaw_rate,beta,p);yaw_allocation_count+=int(allocated);max_speed_error=max(max_speed_error,abs(speed_error));max_heading_error=max(max_heading_error,abs(heading_error))
  # E01 is an input-only plant diagnostic, not a steering-controller ranking.
  # Feed the rigid-reference target directly; actuator lag and tire slip remain
  # inside the plant.  Adding per-vehicle heading feedback here and clipping it
  # independently would destroy the shared-ICR geometry being tested.
  unconstrained_request=target['steering'];saturation_count+=int(np.count_nonzero(abs(unconstrained_request)>LIMIT));request=np.clip(unconstrained_request,-LIMIT,LIMIT);beta_start=beta.copy()
  tv=target['velocity_vehicle_frame'];tr=target['vehicle_yaw_rates'];target_rear=tv[:,1]-p.vehicle.lr_m*tr;target_front=-np.sin(target['steering'])*tv[:,0]+np.cos(target['steering'])*(tv[:,1]+p.vehicle.lf_m*tr);request_front=-np.sin(request)*tv[:,0]+np.cos(request)*(tv[:,1]+p.vehicle.lf_m*tr);max_target_geometry=max(max_target_geometry,float(np.max(abs(np.r_[target_rear,target_front]))));max_request_geometry=max(max_request_geometry,float(np.max(abs(request_front))))
  desired=np.sum(target['velocity_payload_frame']*np.c_[np.cos(beta),np.sin(beta)],axis=1)
  corr=.8*(desired-vehicles[:,3]);corr-=corr.mean();corr=np.clip(corr,-.8,.8);corr-=corr.mean();unbounded_common=K_SPEED*speed_error;common=float(np.clip(unbounded_common,-MAX_COMMON_ACCEL,MAX_COMMON_ACCEL));common_accel_saturation_count+=int(common!=unbounded_common);acc=common+corr
  interval_imp=np.zeros((4,2));interval_peak=np.zeros(4);interval_closure=0.;interval_steps=0;interval_integrated=0.
  for substep in range(10):
   actuator_update_times.append(float(t+interval_integrated))
   delta_before=delta.copy()
   free=request+np.exp(-.002/TAU)*(delta-request);delta=np.clip(delta+np.clip(free-delta,-RATE*.002,RATE*.002),-LIMIT,LIMIT)
   x,audit=advance_outer_step(x,np.c_[acc,delta],'R3',p,.002,'ES',EventSubstepConfig(),max_step_s=max_step,load_transfer_enabled=True)
   boundary=consume_audit(audit,t+interval_integrated,x,delta_before,delta)
   interval_imp+=audit['force_impulse_world_ns'];interval_peak=np.maximum(interval_peak,boundary['force_peak_n']);interval_closure+=audit['time_conservation_residual_s'];interval_steps+=boundary['accepted_steps'];max_ar=max(max_ar,audit['action_reaction_max_n']);max_null=max(max_null,audit['internal_null_max_n'])
   for connector,item in enumerate(boundary['force_peak_argmax']):
    if item['value_n']>=peak_argmax[connector]['value_n']:peak_argmax[connector]=item
   local=0.;sub_start=interval_integrated
   for seg in boundary['segments']:
    local+=seg['dt_s'];support=np.asarray(seg['payload_support_load_n']);util=np.asarray(seg['tire_raw_utilization']);minimum_support=min(minimum_support,float(np.min(support)));max_tire_util=max(max_tire_util,float(np.max(util)))
    subrows.append(np.r_[t+sub_start+local,seg['dt_s'],np.asarray(seg['force_payload_body_n']).ravel(),np.asarray(seg['force_interval_impulse_world_ns']).ravel(),support,np.asarray(seg['vehicle_total_normal_load_n']),util,seg['tension_x_n'],seg['tension_y_n'],np.asarray(seg['signed_gap_m']),np.asarray(seg['smoothing_weight'])])
   interval_integrated+=local
   last_interval_start=float(boundary['t_start_s']);last_interval_end=float(boundary['t_end_s']);last_accepted_duration=float(boundary['accepted_duration_s'])
   if audit['status']!='PASS':status='FAIL';reason=audit['status'];failure_event_time=boundary['failure_event_time_s'];break
  beta+=interval_integrated*target['beta_dot'];d=connector_diagnostics(x,p,'R3');veh,pay=split_state(x);vi=p.vehicle.yaw_inertia_kgm2;li=p.payload.yaw_inertia_kgm2;sysr=(vi*veh[:,5].sum()+li*pay[5])/(4*vi+li)
  _,endpoint_system=system_derivative(x,np.c_[acc,delta],p,'R3',load_transfer_enabled=True);support=np.asarray(endpoint_system['payload_support_load_n']);total_normal=np.asarray(endpoint_system['vehicle_total_normal_load_n']);tire_util=np.asarray([z['raw_utilization'] for z in endpoint_system['tire']]);minimum_support=min(minimum_support,float(np.min(support)));max_tire_util=max(max_tire_util,float(np.max(tire_util)));actual_rear=veh[:,4]-p.vehicle.lr_m*veh[:,5];actual_front=-np.sin(delta)*veh[:,3]+np.cos(delta)*(veh[:,4]+p.vehicle.lf_m*veh[:,5]);max_actual_front=max(max_actual_front,float(np.max(abs(actual_front))));max_actual_rear=max(max_actual_rear,float(np.max(abs(actual_rear))))
  endpoint_time=t+interval_integrated;end=schedule(endpoint_time);rx=float(np.interp(end[4],PATH['s_m'],PATH['x_m']));ry=float(np.interp(end[4],PATH['s_m'],PATH['y_m']));rh=float(np.interp(end[4],PATH['s_m'],PATH['heading_rad']))
  rows.append(np.r_[endpoint_time,t,end[4],s,speed,base,fdeg,rdeg,rx,ry,rh,curv,route_yaw_rate,desired_yaw_rate,yaw_rate,common,x,target['steering'],beta_start,request,delta,acc,target_rear,target_front,request_front,actual_rear,actual_front,d['force_payload_body_n'].ravel(),d['force_vehicle_body_n'].ravel(),support,total_normal,tire_util,interval_peak,interval_imp.ravel(),veh[:,5],pay[5],sysr,d['tension_x_n'],d['tension_y_n'],d['payload_moment_total_nm'],interval_steps,interval_closure])
  impulse+=interval_imp;peak=np.maximum(peak,interval_peak);accepted+=interval_steps;closure+=interval_closure
  if status!='PASS' or not np.all(np.isfinite(x)):status='FAIL';reason=reason or 'NONFINITE';break
 raw=np.asarray(rows);columns=['time_s','interval_start_time_s','reference_distance_m','interval_reference_distance_start_m','reference_speed_start_mps','reference_accel_mps2','virtual_front_deg','virtual_rear_deg','reference_x_m','reference_y_m','reference_heading_rad','reference_curvature_1pm','route_yaw_rate_radps','desired_yaw_rate_radps','allocated_yaw_rate_radps','common_accel_mps2']+[f'x{i}' for i in range(30)]+[f'target_delta{i}' for i in range(4)]+[f'reference_beta{i}' for i in range(4)]+[f'request_delta{i}' for i in range(4)]+[f'actual_delta{i}' for i in range(4)]+[f'accel{i}' for i in range(4)]+[f'target_rear_residual_{i}' for i in range(4)]+[f'target_front_residual_{i}' for i in range(4)]+[f'request_front_residual_{i}' for i in range(4)]+[f'actual_rear_residual_{i}' for i in range(4)]+[f'actual_front_residual_{i}' for i in range(4)]+[f'payload_force_body_{i}' for i in range(8)]+[f'vehicle_connector_force_body_{i}' for i in range(8)]+[f'payload_support_load_{i}' for i in range(4)]+[f'vehicle_total_normal_load_{i}' for i in range(4)]+[f'tire_raw_utilization_{i}' for i in range(4)]+[f'interval_peak_force_{i}' for i in range(4)]+[f'interval_impulse_world_{i}' for i in range(8)]+[f'vehicle_yaw_rate_{i}' for i in range(4)]+['payload_yaw_rate','intrinsic_inertia_weighted_yaw_rate','tension_x_n','tension_y_n','payload_moment_nm','accepted_substeps','closure_residual_s']
 np.savez_compressed(out/'raw.npz',values=raw,columns=np.asarray(columns));sub=np.asarray(subrows);subcols=['time_s','dt_s']+[f'payload_force_body_{i}' for i in range(8)]+[f'force_impulse_world_{i}' for i in range(8)]+[f'payload_support_load_{i}' for i in range(4)]+[f'vehicle_total_normal_load_{i}' for i in range(4)]+[f'tire_raw_utilization_{i}' for i in range(4)]+['tension_x_n','tension_y_n']+[f'signed_gap_{i}' for i in range(4)]+[f'smoothing_weight_{i}' for i in range(4)];np.savez_compressed(out/'substeps.npz',values=sub,columns=np.asarray(subcols))
 trajectory_completed=bool(status=='PASS' and raw[-1,2]>=PATH['s_m'][-1]-1e-9)
 scale=max(1.,float(np.max(peak)));report={'status':status,'reason':reason,'scenario':'true_hairpin','parameter_id':pid,'parameter_values':PARAMS[pid],'max_step_s':max_step,'samples':len(raw),'substep_records':len(sub),'duration_s':float(raw[-1,0]),'integrated_duration_s':float(np.sum(sub[:,1])),'reference_distance_m':float(raw[-1,2]),'route_length_m':float(PATH['s_m'][-1]),'transition_m':float(PATH['transition_m']),'low_level_tracking':{'k_speed':K_SPEED,'max_common_accel_mps2':MAX_COMMON_ACCEL,'k_heading':K_HEADING,'k_yaw_rate':K_YAW_RATE},'wall_s':time.perf_counter()-started,'force_peak4_n':peak.tolist(),'force_peak_argmax':peak_argmax,'force_impulse4x2_ns':impulse.tolist(),'minimum_payload_support_load_n':minimum_support,'maximum_tire_raw_utilization':max_tire_util,'requested_steering_saturation_count':saturation_count,'yaw_allocation_count':yaw_allocation_count,'common_accel_saturation_count':common_accel_saturation_count,'max_payload_speed_error_mps':max_speed_error,'max_payload_heading_error_rad':max_heading_error,'max_target_geometry_residual_mps':max_target_geometry,'max_request_front_residual_mps':max_request_geometry,'max_actual_rear_slip_mps':max_actual_rear,'max_actual_front_slip_mps':max_actual_front,'max_action_reaction_normalized':max_ar/scale,'max_internal_projection_normalized':max_null/(scale*5),'time_closure_relative':closure/max(float(np.sum(sub[:,1])),1e-12),'accepted_substeps':accepted,'t_start_s':last_interval_start,'t_end_s':last_interval_end,'accepted_duration_s':last_accepted_duration,'state_at_t_end':x.tolist(),'actuator_state_at_t_end':delta.tolist(),'failure_event_time_s':failure_event_time,'stop_reason':reason or None,'actuator_update_semantics':'discrete jump at subinterval start, before plant advance','last_actuator_update_time_s':actuator_update_times[-1] if actuator_update_times else None,'requested_full_trajectory':cap is None,'trajectory_completed':trajectory_completed,'batch_state':'COMPLETED' if trajectory_completed else ('FAILED' if status!='PASS' else 'PAUSED'),'source_sha':sha(__file__),'failure_boundary_sha':sha(Path(__file__).with_name('failure_boundary.py')),'reference_geometry_sha':sha(Path(__file__).with_name('reference_geometry.py')),'route_builder_sha':sha(Path(__file__).with_name('references.py'))}
 save(out,'metrics.json',report);print(report)
 if status!='PASS':raise SystemExit(20)
def main():
 a=argparse.ArgumentParser();a.add_argument('--out',required=True);a.add_argument('--parameter',choices=PARAMS,required=True);a.add_argument('--max-step-ms',type=float,choices=[2.,1.,.5],required=True);a.add_argument('--cap-s',type=float);z=a.parse_args();run(z.out,z.parameter,z.max_step_ms/1000,z.cap_s)
if __name__=='__main__':main()
