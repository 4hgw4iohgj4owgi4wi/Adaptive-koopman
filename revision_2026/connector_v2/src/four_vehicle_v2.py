from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from connector_v2 import ConnectorV2Params,connector_force_v2
from internal_force import decompose_planar_point_forces,legacy_q_fr_q_lr,diagonal_tension_modes
@dataclass(frozen=True)
class VehicleParams:mass_kg:float=1200.;yaw_inertia_kgm2:float=1800.;lf_m:float=1.2;lr_m:float=1.3;cf_nprad:float=55000.;cr_nprad:float=60000.;mu:float=.9;gravity_mps2:float=9.81
@dataclass(frozen=True)
class PayloadParams:
 mass_kg:float=2000.;length_m:float=5.;width_m:float=2.;cog_height_m:float=1.2;gravity_mps2:float=9.81
 @property
 def yaw_inertia_kgm2(self):return self.mass_kg*(self.length_m**2+self.width_m**2)/12
@dataclass(frozen=True)
class ModelParamsV2:
 vehicle:VehicleParams=VehicleParams();payload:PayloadParams=PayloadParams();connector:ConnectorV2Params=ConnectorV2Params();vehicle_anchor_body_m:tuple=((-0.4,-.25),(-.4,.25),(.4,-.25),(.4,.25))
 @property
 def payload_anchor_body_m(self):return np.asarray([[.5*self.payload.length_m,.5*self.payload.width_m],[.5*self.payload.length_m,-.5*self.payload.width_m],[-.5*self.payload.length_m,.5*self.payload.width_m],[-.5*self.payload.length_m,-.5*self.payload.width_m]])
def rotation(y):c,s=np.cos(y),np.sin(y);return np.asarray([[c,-s],[s,c]])
def cross_z(r,v):return r*np.asarray([-v[1],v[0]])
def cross2(a,b):return float(a[0]*b[1]-a[1]*b[0])
def split_state(s):
 s=np.asarray(s,float)
 if s.shape!=(30,):raise ValueError('state shape must be 30')
 return s[:24].reshape(4,6),s[24:]
def initialize_state(p,speed_mps=2.):
 pay=np.asarray([0,0,0,speed_mps,0,0.],float);veh=np.zeros((4,6))
 for i in range(4):veh[i,:2]=p.payload_anchor_body_m[i]-np.asarray(p.vehicle_anchor_body_m[i]);veh[i,3]=speed_mps
 return np.r_[veh.ravel(),pay]
def connector_diagnostics(state,p):
 veh,pay=split_state(state);rp=rotation(pay[2]);pa=np.empty((4,2));pv=np.empty((4,2));va=np.empty((4,2));vv=np.empty((4,2));pcv=rp@pay[3:5]
 for i in range(4):
  al=rp@p.payload_anchor_body_m[i];pa[i]=pay[:2]+al;pv[i]=pcv+cross_z(pay[5],al);rv=rotation(veh[i,2]);av=rv@np.asarray(p.vehicle_anchor_body_m[i]);va[i]=veh[i,:2]+av;vv[i]=rv@veh[i,3:5]+cross_z(veh[i,5],av)
 d=va-pa;rel=vv-pv;res=connector_force_v2(d,rel,p.connector);fb=res.force_payload_world_n@rp;fvb=np.vstack([res.force_vehicle_world_n[i]@rotation(veh[i,2]) for i in range(4)]);pm=np.asarray([cross2(rp@p.payload_anchor_body_m[i],res.force_payload_world_n[i]) for i in range(4)]);vm=np.asarray([cross2(rotation(veh[i,2])@np.asarray(p.vehicle_anchor_body_m[i]),res.force_vehicle_world_n[i]) for i in range(4)]);dec=decompose_planar_point_forces(fb,p.payload_anchor_body_m)
 return {'displacement_world_m':d,'relative_velocity_world_mps':rel,'penetration_m':res.penetration_m,'normal_speed_mps':res.normal_speed_mps,'raw_force_norm_n':res.raw_force_n,'applied_force_norm_n':res.applied_force_n,'force_payload_world_n':res.force_payload_world_n,'force_payload_body_n':fb,'force_vehicle_world_n':res.force_vehicle_world_n,'force_vehicle_body_n':fvb,'force_norm_n':res.applied_force_n,'payload_moment_nm':pm,'vehicle_moment_nm':vm,'elastic_energy_j':res.elastic_energy_j,'damping_power_w':res.damping_power_w,'contact_active':res.contact_active,'limit_flags':res.limit_flags,'internal_force_vector_n':dec['internal_force_vector'],'internal_force_norm_n':dec['internal_force_norm_n'],'motion_force_vector_n':dec['motion_force_vector'],'generalized_payload_wrench':dec['generalized_payload_wrench'],'grasp_rank':dec['grasp_rank'],'grasp_condition':dec['grasp_condition'],'q':legacy_q_fr_q_lr(fb),'diagonal_tension_modes_n':diagonal_tension_modes(fb),'internal_null_residual':dec['null_residual']}
def tire_force(state,a,steer,support,p):
 _,_,_,vx,vy,r=state;speed=max(abs(vx),.5);af=steer-np.arctan2(vy+p.lf_m*r,speed);ar=-np.arctan2(vy-p.lr_m*r,speed);fyf=p.cf_nprad*af;fyr=p.cr_nprad*ar;fx=(p.mass_kg+support/p.gravity_mps2)*a;fy=fyf+fyr;mz=p.lf_m*fyf-p.lr_m*fyr;cap=p.mu*(p.mass_kg*p.gravity_mps2+max(support,0));raw=np.hypot(fx,fy)/max(cap,1e-12);sc=min(1.,1/max(raw,1e-12));return {'force_body_n':np.asarray([fx*sc,fy*sc]),'yaw_moment_nm':mz*sc,'utilization':raw*sc}
def system_derivative(state,controls,p):
 veh,pay=split_state(state);controls=np.asarray(controls).reshape(4,2);conn=connector_diagnostics(state,p);support=p.payload.mass_kg*p.payload.gravity_mps2/4;dv=np.empty_like(veh);tires=[]
 for i in range(4):
  td=tire_force(veh[i],controls[i,0],controls[i,1],support,p.vehicle);tires.append(td);force=td['force_body_n']+conn['force_vehicle_body_n'][i];x,y,yaw,vx,vy,r=veh[i];wv=rotation(yaw)@np.asarray([vx,vy]);dv[i]=[wv[0],wv[1],r,force[0]/p.vehicle.mass_kg+r*vy,force[1]/p.vehicle.mass_kg-r*vx,(td['yaw_moment_nm']+conn['vehicle_moment_nm'][i])/p.vehicle.yaw_inertia_kgm2]
 rp=rotation(pay[2]);fw=np.sum(conn['force_payload_world_n'],0);ab=rp.T@(fw/p.payload.mass_kg);vx,vy,r=pay[3:6];wv=rp@pay[3:5];dp=np.asarray([wv[0],wv[1],r,ab[0]+r*vy,ab[1]-r*vx,np.sum(conn['payload_moment_nm'])/p.payload.yaw_inertia_kgm2]);return np.r_[dv.ravel(),dp],{'connectors':conn,'tire':tires,'payload_accel_body_mps2':ab}
def rk4_step(state,controls,dt,p):
 def f(x):return system_derivative(x,controls,p)[0]
 k1=f(state);k2=f(state+.5*dt*k1);k3=f(state+.5*dt*k2);k4=f(state+dt*k3);out=state+dt*(k1+2*k2+2*k3+k4)/6
 if not np.all(np.isfinite(out)):raise FloatingPointError('nonfinite V2 state')
 return out

