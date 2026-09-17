from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from connector_v2 import ConnectorV2Params,connector_force_v2
from internal_force import build_planar_grasp_matrix,decompose_planar_point_forces,legacy_q_fr_q_lr

def run(params):
    checks={};l0=params.free_play_m
    def result(d,v):return connector_force_v2(np.asarray(d,float),np.asarray(v,float),params)
    checks['inside_gap_zero']=bool(result([[.5*l0,0]],[[3,0]]).applied_force_n[0]==0)
    eps=np.logspace(-12,-6,7);f=np.asarray([result([[l0+e,0]],[[2,0]]).applied_force_n[0] for e in eps]);checks['boundary_zero_limit']=bool(f[0]<1e-5 and np.all(np.diff(f)>=0))
    dirs=np.asarray([[1,0],[-1,0],[0,1],[0,-1]],float);rr=result((l0+.01)*dirs,.2*dirs);checks['four_directions']=bool(np.all(np.sum(rr.force_payload_world_n*dirs,axis=1)>0));checks['action_reaction']=bool(np.max(np.abs(rr.force_payload_world_n+rr.force_vehicle_world_n))<=1e-12)
    for deg in (30.,60.):
     a=np.deg2rad(deg);rot=np.asarray([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]]);base=result([[l0+.01,.004]],[[.2,.1]]);turned=result(np.asarray([[l0+.01,.004]])@rot.T,np.asarray([[.2,.1]])@rot.T);checks[f'rotation_{int(deg)}']=bool(np.max(np.abs(turned.force_payload_world_n-base.force_payload_world_n@rot.T))<1e-9)
    d=np.asarray([[.01,.003],[.01,-.003],[-.01,.003],[-.01,-.003]])+np.asarray([[l0,0],[-l0,0],[l0,0],[-l0,0]]);v=np.ones((4,2))*.1;base=result(d,v);perm=[1,0,3,2];dm=d[perm]*[1,-1];vm=v[perm]*[1,-1];mir=result(dm,vm);checks['lr_mirror']=bool(np.max(np.abs(mir.force_payload_world_n-base.force_payload_world_n[perm]*[1,-1]))<1e-9)
    extreme=result([[params.failure_displacement_m+l0+.01,0]],[[10,0]]);checks['force_nonnegative_and_cap']=bool(np.all(extreme.raw_force_n>=0) and np.all(extreme.applied_force_n<=params.ultimate_force_n));checks['energy_nonnegative']=bool(np.all(extreme.elastic_energy_j>=0));checks['dissipation_nonnegative']=bool(np.all(extreme.damping_power_w>=0));checks['limit_flags']=bool(extreme.limit_flags['failure_displacement_exceeded'][0] and extreme.limit_flags['ultimate_force_exceeded'][0])
    anchors=np.asarray([[2.5,1],[2.5,-1],[-2.5,1],[-2.5,-1]],float);force=np.asarray([[100,40],[80,-30],[-70,20],[-40,-10]],float);dec=decompose_planar_point_forces(force,anchors);scale=max(1.,np.linalg.norm(force));checks['internal_null']=bool(np.linalg.norm(dec['null_residual'])<=1e-8*scale);checks['internal_reconstruct']=bool(np.linalg.norm(dec['reconstruction_residual'])<=1e-8*scale)
    manual=np.asarray([.5*((100+80)-(-70-40)),.5*((40+20)-(-30-10))]);checks['legacy_q_exact']=bool(np.array_equal(legacy_q_fr_q_lr(force),manual));checks['grasp_rank']=dec['grasp_rank']==3
    return {'passed':all(checks.values()),'checks':checks,'boundary_forces_N':f.tolist(),'max_action_reaction':float(np.max(np.abs(rr.force_payload_world_n+rr.force_vehicle_world_n))),'internal_null_norm':float(np.linalg.norm(dec['null_residual'])),'internal_reconstruction_norm':float(np.linalg.norm(dec['reconstruction_residual']))}
if __name__=='__main__':
    p=ConnectorV2Params(**json.loads(Path(sys.argv[1]).read_text()));out=run(p);Path(sys.argv[2]).parent.mkdir(parents=True,exist_ok=True);Path(sys.argv[2]).write_text(json.dumps(out,indent=2));print(json.dumps(out));raise SystemExit(0 if out['passed'] else 2)

