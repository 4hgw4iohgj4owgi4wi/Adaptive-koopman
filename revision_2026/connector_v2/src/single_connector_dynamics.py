from __future__ import annotations
from dataclasses import replace
import numpy as np
from connector_v2 import ConnectorV2Params,connector_force_v2

def simulate(params:ConnectorV2Params,delta0:float,v0:float,duration:float=.15,dt:float=1e-4,reduced_mass_kg:float=300.,direction=(1.,0.),stop_on_limit=True):
    direction=np.asarray(direction,float);direction/=np.linalg.norm(direction);steps=int(round(duration/dt))+1;t=np.arange(steps)*dt;y=np.asarray([delta0,v0],float);rows=[];failed=False
    def rhs(q):
        delta,v=q;d=(params.free_play_m+delta)*direction;res=connector_force_v2(d,v*direction,params);return np.asarray([v,-float(res.applied_force_n)/reduced_mass_kg]),res
    for i in range(steps):
        dy,res=rhs(y);rows.append((t[i],y[0],y[1],float(res.raw_force_n),float(res.applied_force_n),float(res.elastic_energy_j),float(res.damping_power_w),bool(res.contact_active)))
        if stop_on_limit and (bool(res.limit_flags['failure_displacement_exceeded']) or bool(res.limit_flags['ultimate_force_exceeded'])):failed=True;rows[-1]=(*rows[-1],);break
        if i==steps-1:break
        k1,_=rhs(y);k2,_=rhs(y+.5*dt*k1);k3,_=rhs(y+.5*dt*k2);k4,_=rhs(y+dt*k3);y=y+dt*(k1+2*k2+2*k3+k4)/6
    a=np.asarray(rows,float);kin=.5*reduced_mass_kg*a[:,2]**2;total=kin+a[:,5];active=a[:,7]>0.5;switch=np.r_[False,active[1:]!=active[:-1]];impulse=np.cumsum(a[:,4])*dt
    return {'time_s':a[:,0],'delta_m':a[:,1],'normal_speed_mps':a[:,2],'raw_force_n':a[:,3],'applied_force_n':a[:,4],'elastic_energy_j':a[:,5],'damping_power_w':a[:,6],'contact_active':active,'switching_event':switch,'impulse_ns':impulse,'kinetic_energy_j':kin,'total_mechanical_energy_j':total,'failed':failed,'dt':dt}

