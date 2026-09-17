from __future__ import annotations
import math,sys
from pathlib import Path
import numpy as np
from connector_v2 import ConnectorV2Params
from four_vehicle_v2 import ModelParamsV2,initialize_state as init2,rk4_step as step2,split_state as split2,connector_diagnostics as diag2,system_derivative as deriv2
from internal_force import decompose_planar_point_forces,legacy_q_fr_q_lr
DT=.002
def _paths(project):
 for p in (project/'revision_2026'/'model',project/'revision_2026'/'koopman'):
  if str(p) not in sys.path:sys.path.insert(0,str(p))
 import four_vehicle_coupled as v1
 from steering_allocator import allocate_controls
 import generate_k2 as gen
 return v1,allocate_controls,gen
def _system_yaw(state,p):
 veh,pay=state[:24].reshape(4,6),state[24:];m=np.asarray([p.vehicle.mass_kg]*4+[p.payload.mass_kg]);pos=np.vstack([veh[:,:2],pay[:2]]);vel=np.vstack([[(np.cos(x[2])*x[3]-np.sin(x[2])*x[4]),(np.sin(x[2])*x[3]+np.cos(x[2])*x[4])] for x in veh]+[[(np.cos(pay[2])*pay[3]-np.sin(pay[2])*pay[4]),(np.sin(pay[2])*pay[3]+np.cos(pay[2])*pay[4])]]);com=np.sum(m[:,None]*pos,0)/sum(m);vc=np.sum(m[:,None]*vel,0)/sum(m);arms=pos-com;I=np.asarray([p.vehicle.yaw_inertia_kgm2]*4+[p.payload.yaw_inertia_kgm2]);rates=np.r_[veh[:,5],pay[5]];den=np.sum(I+m*np.sum(arms**2,1));num=np.sum(I*rates)+sum(m[i]*(arms[i,0]*(vel[i,1]-vc[1])-arms[i,1]*(vel[i,0]-vc[0])) for i in range(5));return num/den
def _record(state,ctrl,p,version,v1):
 if version=='v1':
  ag=v1.aggregate_diagnostics(state,ctrl,p);c=ag['connectors'];fb=c['force_payload_body_n'];pen=c['penetration_m'];active=pen>0;vn=c['normal_speed_mps'];raw=c['force_norm_n'];energy=.5*p.connector.stiffness_npm*pen**2;damp=p.connector.damping_nspm*np.maximum(vn,0)**2*active;tire=ag['tire_utilization'];sysyaw=ag['system_yaw_rate_radps'];limits=np.zeros(4,bool)
 else:
  c=diag2(state,p);fb=c['force_payload_body_n'];pen=c['penetration_m'];active=c['contact_active'];vn=c['normal_speed_mps'];raw=c['raw_force_norm_n'];energy=c['elastic_energy_j'];damp=c['damping_power_w'];_,aux=deriv2(state,ctrl,p);tire=np.asarray([x['utilization'] for x in aux['tire']]);sysyaw=_system_yaw(state,p);limits=np.logical_or(c['limit_flags']['failure_displacement_exceeded'],c['limit_flags']['ultimate_force_exceeded'])
 dec=decompose_planar_point_forces(fb,p.payload_anchor_body_m);return {'state':state.copy(),'force':fb.copy(),'penetration':pen.copy(),'vn':vn.copy(),'raw':raw.copy(),'active':active.copy(),'energy':energy.copy(),'damping':damp.copy(),'internal':dec['internal_force_vector'].copy(),'internal_norm':dec['internal_force_norm_n'],'motion':dec['motion_force_vector'].copy(),'wrench':dec['generalized_payload_wrench'].copy(),'q':legacy_q_fr_q_lr(fb),'system_yaw':sysyaw,'tire':tire.copy(),'null':float(np.linalg.norm(dec['null_residual'])),'limits':limits}
def _pack(rows,controls,dt=DT):
 out={k:np.asarray([r[k] for r in rows]) for k in rows[0]};out['control']=np.asarray(controls);out['time_s']=np.arange(len(rows))*dt;pay=out['state'][:,24:30];ds=np.linalg.norm(np.diff(pay[:,:2],axis=0),axis=1);out['distance_m']=np.r_[0,np.cumsum(ds)];return out
def _command(scenario,t,distance,speed,sign,turn_start,decel,gen):
 if scenario=='staged_100m':
  if distance<30:return (.35,0.,0.),turn_start,decel
  turn_start=t if turn_start is None else turn_start;tau=t-turn_start
  if tau<5:return (0.,4*sign,-2*sign),turn_start,decel
  if tau<10:return (0.,-4*sign,2*sign),turn_start,decel
  if decel is None:decel=float(np.clip(-speed**2/(2*max(100-distance,.5)),-.45,-.1))
  return (decel,0.,0.),turn_start,decel
 return gen.nominal_command(scenario,t,distance,speed,0.,sign,turn_start),turn_start,decel
def reference(project,scenario,sign):
 v1,allocate,gen=_paths(project);p=v1.ModelParams();speed0={'staged_100m':2.,'single_lane_change':2.,'hairpin':1.}[scenario];s=v1.initialize_state(p,speed0);controls=[];rows=[];turn=None;decel=None;distance=0.;duration={'staged_100m':90.,'single_lane_change':16.,'hairpin':44.}[scenario];steps=int(duration/DT)
 for j in range(steps):
  _,pay=v1.split_state(s);speed=float(np.linalg.norm(pay[3:5]));cmd,turn,decel=_command(scenario,j*DT,distance,speed,sign,turn,decel,gen);u,_=allocate(s,*cmd,p);rows.append(_record(s,u,p,'v1',v1));controls.append(u);sn=v1.rk4_step(s,u,DT,p);_,pn=v1.split_state(sn);distance+=.5*(speed+np.linalg.norm(pn[3:5]))*DT;s=sn
  if scenario=='staged_100m' and distance>=100:break
 return _pack(rows,controls),p
def replay_v2(project,controls,params,speed0):
 v1,_,_=_paths(project);p=ModelParamsV2(connector=params);s=init2(p,speed0);rows=[]
 for u in controls:
  r=_record(s,u,p,'v2',v1);rows.append(r)
  if np.any(r['limits']):break
  s=step2(s,u,DT,p)
 return _pack(rows,controls[:len(rows)]),p
def summary(a):
 f=a['force'].reshape(len(a['force']),8);df=np.linalg.norm(np.diff(a['force'],axis=0),axis=-1);freq=np.fft.rfftfreq(len(f),DT);power=np.abs(np.fft.rfft(f-f.mean(0),axis=0))**2;total=max(float(np.sum(power[1:])),1e-30);hf=float(np.sum(power[freq>20])/total);switch=int(np.sum(a['active'][1:]!=a['active'][:-1]));return {'steps':len(a['force']),'distance_m':float(a['distance_m'][-1]),'finite':bool(all(np.all(np.isfinite(v)) for v in a.values())),'peak_force_n':float(np.max(np.linalg.norm(a['force'],axis=-1))),'rms_force_n':float(np.sqrt(np.mean(a['force']**2))),'impulse_ns':float(np.sum(np.linalg.norm(a['force'],axis=-1))*DT),'max_2ms_force_jump_n':float(np.max(df)),'hf_energy_above_20hz':hf,'switches':switch,'peak_internal_n':float(np.max(a['internal_norm'])),'peak_tire_utilization':float(np.max(a['tire'])),'max_null_residual':float(np.max(a['null'])),'limit_steps':int(np.sum(a['limits']))}
def run_all(project,params,out):
 out.mkdir(parents=True,exist_ok=True);traces={};reports={}
 for scenario in ('staged_100m','single_lane_change','hairpin'):
  signs=(1.,) if scenario=='staged_100m' else (1.,-1.)
  for sign in signs:
   key=f'{scenario}_{"left" if sign>0 else "right"}';a,_=reference(project,scenario,sign);b,_=replay_v2(project,a['control'],params,{'staged_100m':2.,'single_lane_change':2.,'hairpin':1.}[scenario]);traces[(key,'v1')]=a;traces[(key,'v2')]=b;reports[key]={'v1':summary(a),'v2':summary(b)};np.savez_compressed(out/f'{key}_v1.npz',**a);np.savez_compressed(out/f'{key}_v2.npz',**b)
 s=reports['staged_100m_left'];v1s,v2s=s['v1'],s['v2'];jump_gain=(v1s['max_2ms_force_jump_n']-v2s['max_2ms_force_jump_n'])/max(v1s['max_2ms_force_jump_n'],1e-9);checks={'jump_reduction_ge_50pct':jump_gain>=.5,'hf20_not_increased':v2s['hf_energy_above_20hz']<=v1s['hf_energy_above_20hz']+1e-12,'switches_not_gt_10pct':v2s['switches']<=1.1*v1s['switches']+1,'v2_100m':v2s['distance_m']>=99.9,'finite':v2s['finite'],'tire_not_worse_0p02':v2s['peak_tire_utilization']<=v1s['peak_tire_utilization']+.02,'action_internal_null':v2s['max_null_residual']<=1e-8*max(1,v2s['peak_internal_n']),'no_limits':v2s['limit_steps']==0}
 mirror={}
 for scenario in ('single_lane_change','hairpin'):
  l=traces[(f'{scenario}_left','v2')]['force'];r=traces[(f'{scenario}_right','v2')]['force'];n=min(len(l),len(r));expected=l[:n][:,[1,0,3,2]]*np.asarray([1,-1]);mirror[scenario]={'force_mirror_max_n':float(np.max(np.abs(r[:n]-expected))),'lateral_wrench_sign_opposite':bool(np.mean(traces[(f'{scenario}_left','v2')]['wrench'][:,1])*np.mean(traces[(f'{scenario}_right','v2')]['wrench'][:,1])<0),'internal_null_max':float(max(np.max(traces[(f'{scenario}_left','v2')]['null']),np.max(traces[(f'{scenario}_right','v2')]['null']))),'q_miss_samples':int(np.sum((np.linalg.norm(traces[(f'{scenario}_left','v2')]['q'],axis=1)<.1*np.maximum(traces[(f'{scenario}_left','v2')]['internal_norm'],1))&(traces[(f'{scenario}_left','v2')]['internal_norm']>100)))}
 g5=all(x['force_mirror_max_n']<1e-5 and x['lateral_wrench_sign_opposite'] for x in mirror.values());result={'passed':all(checks.values()) and g5,'g4_checks':{k:bool(v) for k,v in checks.items()},'g5_passed':bool(g5),'jump_reduction':jump_gain,'force_amplitude_ratios':{'peak':v2s['peak_force_n']/max(v1s['peak_force_n'],1e-9),'rms':v2s['rms_force_n']/max(v1s['rms_force_n'],1e-9),'impulse':v2s['impulse_ns']/max(v1s['impulse_ns'],1e-9)},'reports':reports,'mirror':mirror};(out/'c4_results.json').write_text(__import__('json').dumps(result,indent=2));return result
