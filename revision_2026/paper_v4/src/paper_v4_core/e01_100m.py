"""Registered EXP-R1 100 m open-input diagnostic and convergence evidence."""
import argparse,json,time,traceback
from dataclasses import replace
from pathlib import Path
import numpy as np
from .cli import save,sha
from .plant.four_vehicle_common import ModelParams,initialize_state,split_state,connector_diagnostics,system_derivative
from .plant.event_substep import EventSubstepConfig,advance_outer_step
from .plant.load_transfer import config_from_model,solve_payload_support_loads
from .reference_geometry import transition_targets

DT=.02; LIMIT=np.deg2rad(15.); RATE=1.2; TAU=.12; T1=12.;T2=17.;T3=22.;DECEL=.2585; T4=T3+(4.-.7)/DECEL
PARAMS={
 'P0':dict(payload=1.,connector=1.,mu=.9),
 'P1':dict(payload=.9,connector=.95,mu=.95),
 'P2':dict(payload=1.1,connector=1.05,mu=.8),
}
def params(pid):
 p=ModelParams();q=PARAMS[pid]
 return replace(p,vehicle=replace(p.vehicle,mu=q['mu']),payload=replace(p.payload,mass_kg=p.payload.mass_kg*q['payload']),connector=replace(p.connector,stiffness_npm=p.connector.stiffness_npm*q['connector'],damping_nspm=p.connector.damping_nspm*q['connector'],free_play_m=p.connector.free_play_m*q['connector']))
def schedule(t):
 if t<T1:return 1+.25*t, .25,0.,0.,1*t+.125*t*t
 if t<T2:return 4.,0.,5.,-2.5,30+4*(t-T1)
 if t<T3:return 4.,0.,-5.,2.5,50+4*(t-T2)
 z=min(t-T3,T4-T3);v=max(.7,4-DECEL*z);s=70+4*z-.5*DECEL*z*z
 return v,-DECEL if t<T4 else 0.,0.,0.,min(s,100.)
def run(out,pid,max_step,cap=None):
 out=Path(out);out.mkdir(parents=True,exist_ok=False);p=params(pid);x=initialize_state(p,1.);beta=np.zeros(4);delta=np.zeros(4);rows=[]
 started=time.perf_counter();max_ar=max_null=closure=0.;accepted=0;status='PASS';reason='';impulse=np.zeros((4,2));peak=np.zeros(4);subrows=[];minimum_support=float('inf');max_tire_util=0.
 requested_duration=T4 if cap is None else min(cap,T4)
 count=int(np.ceil(requested_duration/DT))
 for k in range(count):
  t=k*DT;speed,base,fdeg,rdeg,s=schedule(t);f=np.deg2rad(fdeg);rr=np.deg2rad(rdeg);den=np.tan(f)-np.tan(rr)
  yaw_rate=speed*den/p.payload.length_m
  xicr=0. if abs(den)<1e-12 else .5*p.payload.length_m-p.payload.length_m/den*np.tan(f)
  target=transition_targets(np.array([speed,-yaw_rate*xicr]),yaw_rate,beta,p)
  vehicles,payload=split_state(x);err=(payload[2]+beta-vehicles[:,2]+np.pi)%(2*np.pi)-np.pi
  request=np.clip(target['steering']+2*err,-LIMIT,LIMIT)
  desired=np.sum(target['velocity_payload_frame']*np.c_[np.cos(beta),np.sin(beta)],axis=1)
  corr=.8*(desired-vehicles[:,3]);corr-=corr.mean();corr=np.clip(corr,-.8,.8);corr-=corr.mean();acc=base+corr
  interval_imp=np.zeros((4,2));interval_peak=np.zeros(4);interval_closure=0.;interval_steps=0
  for sub in range(10):
   free=request+np.exp(-.002/TAU)*(delta-request);delta=np.clip(delta+np.clip(free-delta,-RATE*.002,RATE*.002),-LIMIT,LIMIT)
   control=np.c_[acc,delta]
   x,audit=advance_outer_step(x,control,'R3',p,.002,'ES',EventSubstepConfig(),max_step_s=max_step,load_transfer_enabled=True)
   if audit['status']!='PASS':status='FAIL';reason=audit['status'];break
   interval_imp+=audit['force_impulse_world_ns'];interval_peak=np.maximum(interval_peak,audit['force_peak_n']);interval_closure+=audit['time_conservation_residual_s'];interval_steps+=audit['accepted_steps']
   max_ar=max(max_ar,audit['action_reaction_max_n']);max_null=max(max_null,audit['internal_null_max_n'])
   local=0.
   for seg in audit['interval_segments']:
    local+=seg['dt_s'];support=np.asarray(seg['payload_support_load_n']);util=np.asarray(seg['tire_raw_utilization']);minimum_support=min(minimum_support,float(np.min(support)));max_tire_util=max(max_tire_util,float(np.max(util)))
    subrows.append(np.r_[t+sub*.002+local,seg['dt_s'],np.asarray(seg['force_payload_body_n']).ravel(),np.asarray(seg['force_interval_impulse_world_ns']).ravel(),support,np.asarray(seg['vehicle_total_normal_load_n']),util,seg['tension_x_n'],seg['tension_y_n'],np.asarray(seg['signed_gap_m']),np.asarray(seg['smoothing_weight'])])
  beta+=DT*target['beta_dot'];d=connector_diagnostics(x,p,'R3');veh,pay=split_state(x);vi=p.vehicle.yaw_inertia_kgm2;li=p.payload.yaw_inertia_kgm2;sysr=(vi*veh[:,5].sum()+li*pay[5])/(4*vi+li)
  _,endpoint_system=system_derivative(x,np.c_[acc,delta],p,'R3',load_transfer_enabled=True)
  support=np.asarray(endpoint_system['payload_support_load_n']);total_normal=np.asarray(endpoint_system['vehicle_total_normal_load_n']);tire_util=np.asarray([z['raw_utilization'] for z in endpoint_system['tire']]);minimum_support=min(minimum_support,float(np.min(support)));max_tire_util=max(max_tire_util,float(np.max(tire_util)))
  endpoint_time=t+DT;endpoint_distance=schedule(endpoint_time)[4]
  rows.append(np.r_[endpoint_time,t,endpoint_distance,s,speed,base,fdeg,rdeg,x,request,delta,acc,d['force_payload_body_n'].ravel(),d['force_vehicle_body_n'].ravel(),support,total_normal,tire_util,interval_peak,interval_imp.ravel(),veh[:,5],pay[5],sysr,d['tension_x_n'],d['tension_y_n'],d['payload_moment_total_nm'],interval_steps,interval_closure])
  impulse+=interval_imp;peak=np.maximum(peak,interval_peak);accepted+=interval_steps;closure+=interval_closure
  if status!='PASS' or not np.all(np.isfinite(x)):status='FAIL';reason=reason or 'NONFINITE';break
 raw=np.asarray(rows);columns=['time_s','interval_start_time_s','reference_distance_m','interval_reference_distance_start_m','reference_speed_start_mps','reference_accel_mps2','virtual_front_deg','virtual_rear_deg']+[f'x{i}' for i in range(30)]+[f'request_delta{i}' for i in range(4)]+[f'actual_delta{i}' for i in range(4)]+[f'accel{i}' for i in range(4)]+[f'payload_force_body_{i}' for i in range(8)]+[f'vehicle_connector_force_body_{i}' for i in range(8)]+[f'payload_support_load_{i}' for i in range(4)]+[f'vehicle_total_normal_load_{i}' for i in range(4)]+[f'tire_raw_utilization_{i}' for i in range(4)]+[f'interval_peak_force_{i}' for i in range(4)]+[f'interval_impulse_world_{i}' for i in range(8)]+[f'vehicle_yaw_rate_{i}' for i in range(4)]+['payload_yaw_rate','intrinsic_inertia_weighted_yaw_rate','tension_x_n','tension_y_n','payload_moment_nm','accepted_substeps','closure_residual_s']
 np.savez_compressed(out/'raw.npz',values=raw,columns=np.asarray(columns))
 sub=np.asarray(subrows);subcols=['time_s','dt_s']+[f'payload_force_body_{i}' for i in range(8)]+[f'force_impulse_world_{i}' for i in range(8)]+[f'payload_support_load_{i}' for i in range(4)]+[f'vehicle_total_normal_load_{i}' for i in range(4)]+[f'tire_raw_utilization_{i}' for i in range(4)]+['tension_x_n','tension_y_n']+[f'signed_gap_{i}' for i in range(4)]+[f'smoothing_weight_{i}' for i in range(4)]
 np.savez_compressed(out/'substeps.npz',values=sub,columns=np.asarray(subcols))
 scale=max(1.,float(np.max(peak)));report={'status':status,'reason':reason,'scenario':'100m_diagnostic','parameter_id':pid,'parameter_values':PARAMS[pid],'max_step_s':max_step,'samples':len(raw),'substep_records':len(sub),'duration_s':float(raw[-1,0]),'integrated_duration_s':float(np.sum(sub[:,1])),'reference_distance_m':float(raw[-1,2]),'wall_s':time.perf_counter()-started,'force_peak4_n':peak.tolist(),'force_impulse4x2_ns':impulse.tolist(),'minimum_payload_support_load_n':minimum_support,'maximum_tire_raw_utilization':max_tire_util,'max_action_reaction_normalized':max_ar/scale,'max_internal_projection_normalized':max_null/(scale*5),'time_closure_relative':closure/max(DT*len(raw),1e-12),'accepted_substeps':accepted,'source_sha':sha(__file__),'reference_sha':sha(Path(__file__).with_name('reference_geometry.py')),'complete_registered_trajectory':cap is None}
 save(out,'metrics.json',report);print(report)
 if status!='PASS':raise SystemExit(20)
def main():
 a=argparse.ArgumentParser();a.add_argument('--out',required=True);a.add_argument('--parameter',choices=PARAMS,required=True);a.add_argument('--max-step-ms',type=float,choices=[2.,1.,.5],required=True);a.add_argument('--cap-s',type=float);z=a.parse_args();run(z.out,z.parameter,z.max_step_ms/1000,z.cap_s)
if __name__=='__main__':main()
