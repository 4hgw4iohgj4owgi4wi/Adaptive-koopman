from __future__ import annotations
from dataclasses import replace
import hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from connector_v2 import ConnectorV2Params,connector_force_v2
from single_connector_dynamics import simulate

def digest(run):
 h=hashlib.sha256()
 for k in ('time_s','delta_m','normal_speed_mps','raw_force_n','applied_force_n','elastic_energy_j','damping_power_w','contact_active','switching_event','impulse_ns'):h.update(np.ascontiguousarray(run[k]).view(np.uint8))
 return h.hexdigest()
def run(params,outdir):
 outdir.mkdir(parents=True,exist_ok=True);checks={};cases={}
 conservative=simulate(replace(params,hysteresis_damping_CH=0.,force_cap_enabled=False,failure_displacement_m=1.,ultimate_force_n=1e12),.012,0.,.12,5e-5,300.,stop_on_limit=False);e=conservative['total_mechanical_energy_j'];drift=float(np.max(np.abs(e-e[0]))/max(e[0],1e-12));checks['conservative_energy_drift_lt_0p5pct']=drift<.005;cases['conservative']=conservative
 damped=simulate(replace(params,force_cap_enabled=False,failure_displacement_m=1.,ultimate_force_n=1e12),.012,0.,.12,5e-5,300.,stop_on_limit=False);de=np.diff(damped['total_mechanical_energy_j']);checks['damped_no_sustained_growth']=float(np.quantile(de,.999))<1e-6;cases['damped']=damped
 contact=[]
 for speed in (.05,.25,1.):
  q=simulate(replace(params,failure_displacement_m=1.,ultimate_force_n=1e12,force_cap_enabled=False),-2e-4,speed,.03,2e-5,300.,stop_on_limit=False);contact.append(q);cases[f'contact_v{speed}']=q
 eps=np.asarray([1e-12,1e-10,1e-8,1e-6]);limits=[]
 for speed in (.05,.25,1.):limits.append([float(connector_force_v2([[params.free_play_m+x,0]],[[speed,0]],params).raw_force_n[0]) for x in eps])
 checks['zero_contact_force_limit']=max(row[0] for row in limits)<1e-5
 directions=[]
 for d in ((1,0),(-1,0),(0,1),(0,-1)):directions.append(simulate(params,-1e-4,.2,.02,2e-5,300.,d,False)['applied_force_n'])
 checks['four_direction_dynamic_symmetry']=max(float(np.max(np.abs(x-directions[0]))) for x in directions)<1e-9
 stiffness={}
 for fac in (.75,1.,1.25):stiffness[str(fac)]=simulate(replace(params,contact_stiffness_K=params.contact_stiffness_K*fac,hysteresis_damping_CH=params.hysteresis_damping_CH*fac),.005,.1,.04,2e-5,300.,stop_on_limit=False)
 cases.update({f'K_{k}':v for k,v in stiffness.items()});checks['stiffness_peak_order']=max(stiffness['0.75']['applied_force_n'])<max(stiffness['1.0']['applied_force_n'])<max(stiffness['1.25']['applied_force_n'])
 near_delta=(.98*params.rated_force_n/params.contact_stiffness_K)**(1/params.contact_exponent_n);near=connector_force_v2([[(params.free_play_m+near_delta),0]],[[0,0]],params);checks['near_rated_not_exceeded']=bool(near.raw_force_n[0]<params.rated_force_n and near.raw_force_n[0]>.9*params.rated_force_n)
 over=simulate(params,params.failure_displacement_m*1.01,0.,.01,1e-4,300.);checks['over_limit_stops']=bool(over['failed'] and len(over['time_s'])==1);cases['over_limit']=over
 repeated=simulate(params,-2e-4,.25,.03,2e-5,300.,stop_on_limit=False);checks['repeat_hash_equal']=digest(repeated)==digest(contact[1]);checks['finite']=all(all(np.all(np.isfinite(v)) for v in q.values() if isinstance(v,np.ndarray)) for q in cases.values());checks['no_negative_force']=all(np.min(q['applied_force_n'])>=0 for q in cases.values())
 for name,q in cases.items():np.savez_compressed(outdir/f'{name}.npz',**q)
 checks={k:bool(v) for k,v in checks.items()};summary={'passed':all(checks.values()),'checks':checks,'conservative_energy_relative_drift':drift,'damped_max_positive_step':float(np.max(de)),'boundary_force_limits_N':limits,'case_hashes':{k:digest(v) for k,v in cases.items()},'sampling_hz':50000,'note':'high-rate reference saved; 500 Hz views may be derived without changing dynamics'};(outdir/'g2_results.json').write_text(json.dumps(summary,indent=2));return summary
if __name__=='__main__':
 p=ConnectorV2Params(**json.loads(Path(sys.argv[1]).read_text()));out=run(p,Path(sys.argv[2]));print(json.dumps(out));raise SystemExit(0 if out['passed'] else 2)
