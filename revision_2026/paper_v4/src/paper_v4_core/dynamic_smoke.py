"""Short closed plant smoke for the corrected moving reference; not an E01 trajectory count."""
import argparse
from pathlib import Path
import time
import numpy as np
from .cli import save,sha
from .plant.four_vehicle_common import ModelParams,initialize_state,split_state,connector_diagnostics
from .plant.event_substep import EventSubstepConfig,advance_outer_step
from .reference_geometry import transition_targets

def wrap(x): return (x+np.pi)%(2*np.pi)-np.pi

def main(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);p=ModelParams();x=initialize_state(p,2.);beta=np.zeros(4);delta=np.zeros(4)
    dt=.02;plant_dt=.002;tau=.12;rate=1.2;limit=np.deg2rad(15);records=[];started=time.perf_counter()
    max_ar=max_null=max_force=0.;min_support=float('inf');status='PASS';reason=''
    for k in range(501):
        t=k*dt;r=.04*np.sin(np.pi*np.clip((t-1)/2,0,1))**2 if t<5 else -.04*np.sin(np.pi*np.clip((t-5)/2,0,1))**2
        target=transition_targets(np.array([2.,0.]),r,beta,p)
        vehicles,payload=split_state(x);desired=payload[2]+beta
        steer_req=np.clip(target['steering']+2.*wrap(desired-vehicles[:,2]),-limit,limit)
        desired_body=np.array([np.cos(beta[i])*target['velocity_payload_frame'][i,0]+np.sin(beta[i])*target['velocity_payload_frame'][i,1] for i in range(4)])
        corr=.8*(desired_body-vehicles[:,3]);corr-=corr.mean();acc=np.clip(corr,-.8,.8);acc-=acc.mean()
        for _ in range(10):
            free=steer_req+np.exp(-plant_dt/tau)*(delta-steer_req);inc=np.clip(free-delta,-rate*plant_dt,rate*plant_dt);delta=np.clip(delta+inc,-limit,limit)
            u=np.c_[acc,delta]
            x,audit=advance_outer_step(x,u,'R3',p,plant_dt,'ES',EventSubstepConfig(),load_transfer_enabled=True)
            if audit['status']!='PASS': status='FAIL';reason=audit['status'];break
        beta=beta+dt*target['beta_dot']
        d=connector_diagnostics(x,p,'R3');ar=float(np.max(abs(d['action_reaction_residual_n'])));nu=float(np.max(abs(d['internal_null_residual'])));force=float(np.max(d['force_norm_n']))
        max_ar=max(max_ar,ar);max_null=max(max_null,nu);max_force=max(max_force,force)
        _,diag=advance_outer_step(x,np.c_[acc,delta],'R3',p,0.,'ES',EventSubstepConfig(),load_transfer_enabled=True) if False else (None,None)
        records.append(np.r_[t,x,steer_req,delta,acc,d['force_payload_body_n'].ravel(),d['tension_x_n'],d['tension_y_n'],d['payload_moment_total_nm']])
        if status!='PASS' or not np.all(np.isfinite(x)): status='FAIL';reason=reason or 'NONFINITE';break
    raw=np.asarray(records);np.savez_compressed(out/'smoke.npz',values=raw)
    result={'status':status,'reason':reason,'samples':len(raw),'duration_s':float(raw[-1,0]),'wall_s':time.perf_counter()-started,'max_force_n':max_force,'max_action_reaction_n':max_ar,'max_internal_null_residual':max_null,'max_actual_steer_deg':float(np.rad2deg(np.max(abs(raw[:,35:39])))),'scope':'short plant smoke only; convergence and registered E01 NOT_RUN','source_sha':sha(__file__)}
    save(out,'smoke.json',result);print(result)
    if status!='PASS':raise SystemExit(20)

if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('--out',required=True);main(q.parse_args().out)
