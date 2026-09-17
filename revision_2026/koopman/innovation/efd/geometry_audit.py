from __future__ import annotations
from pathlib import Path
from typing import Any
import numpy as np
from h2_adapter import FrozenH2

def _angles(d:np.ndarray,f:np.ndarray)->np.ndarray:
    dn=np.linalg.norm(d,axis=-1);fn=np.linalg.norm(f,axis=-1);cos=np.sum(d*f,axis=-1)/np.maximum(dn*fn,1e-12);return np.degrees(np.arccos(np.clip(cos,-1,1)))
def truth_alignment(paths:list[Path],force_floor:float=12.)->dict[str,Any]:
    ds=[];fs=[];vfs=[];offset={-1:[] ,0:[],1:[]};residual=[]
    for p in paths:
        with np.load(p,allow_pickle=False) as s:d=np.asarray(s["connector_disp_payload_frame"],float);f=np.asarray(s["force_on_payload"],float);vf=np.asarray(s["force_on_vehicle"],float);r=np.asarray(s["action_reaction_residual"],float)
        ds.append(d);fs.append(f);vfs.append(vf);residual.append(r)
        for shift in (-1,0,1):
            if shift<0:dd,ff=d[1:],f[:-1]
            elif shift>0:dd,ff=d[:-1],f[1:]
            else:dd,ff=d,f
            a=_angles(dd,ff);mask=np.linalg.norm(ff,axis=-1)>=force_floor;offset[shift].append(a[mask])
    d=np.concatenate(ds);f=np.concatenate(fs);ang=_angles(d,f);active=np.linalg.norm(f,axis=-1)>=force_floor;t=np.stack([-d[...,1],d[...,0]],axis=-1)/np.maximum(np.linalg.norm(d,axis=-1)[...,None],1e-12);tan=np.abs(np.sum(t*f,axis=-1))/np.maximum(np.linalg.norm(f,axis=-1),1e-12)
    points=[]
    for i in range(4):
        a=ang[...,i][active[...,i]];q=tan[...,i][active[...,i]];points.append({"corner":i,"active":int(len(a)),"angle_median_deg":float(np.median(a)),"angle_p95_deg":float(np.quantile(a,.95)),"tangential_ratio_p95":float(np.quantile(q,.95))})
    timing={str(k):{"median_deg":float(np.median(np.concatenate(v))),"p95_deg":float(np.quantile(np.concatenate(v),.95))} for k,v in offset.items()};max_ar=float(np.max(np.abs(np.concatenate(residual))));gates={"angle":all(x["angle_median_deg"]<=.5 and x["angle_p95_deg"]<=2 for x in points),"tangential":all(x["tangential_ratio_p95"]<=.02 for x in points),"aligned_timing":timing["0"]["p95_deg"]<=2 and timing["0"]["p95_deg"]<=timing["-1"]["p95_deg"] and timing["0"]["p95_deg"]<=timing["1"]["p95_deg"],"action_reaction":max_ar<=1e-8}
    return {"force_floor_N":force_floor,"points":points,"timestamp_offsets":timing,"max_action_reaction_residual_N":max_ar,"gates":gates,"passed":all(gates.values())}

def _p5_predict(model_path:Path,x0:np.ndarray,u:np.ndarray)->np.ndarray:
    with np.load(model_path,allow_pickle=False) as s:coef=s["p5_coef"];mean=s["p5_mean"];std=s["p5_std"];dims=s["p5_dims"]
    out=[]
    for h in range(1,21):
        f=np.r_[1.,x0,u[:h].reshape(-1)];d=int(dims[h-1]);out.append(((f-mean[h-1,:d])/std[h-1,:d])@coef[h-1,:d])
    return np.asarray(out).reshape(20,4,2)

def oracle_ablation(project:Path,paths:list[Path],force_floor:float=12.)->dict[str,Any]:
    koop=project/"revision_2026"/"koopman";norm=np.load(koop/"universal_v2"/"normalizers.npz");h2=FrozenH2(koop/"innovation_results"/"t4_h2"/"models"/"N2-seed-151002.npz");p5path=koop/"innovation_direction_results"/"d4_validation"/"models"/"direction_seed_181004.npz";angles={"H2_displacement":[],"truth_displacement":[],"legacy_P5":[]};windows=0
    for path in paths:
        with np.load(path,allow_pickle=False) as s:state=np.asarray(s["s3_deform"],float);u=np.asarray(s["u1_four"],float);truth_f=np.asarray(s["force_on_payload"],float)
        origins=np.arange(0,len(u)-20+1,20)
        for o in origins:
            x0=(state[o]-norm["x_mean"])/norm["x_std"];un=(u[o:o+20]-norm["u_mean"])/norm["u_std"];hx=h2.predict(x0,un)[...,:46]*norm["x_std"]+norm["x_mean"];hd=hx[...,30:38].reshape(20,4,2);td=state[o+1:o+21,30:38].reshape(20,4,2);tf=truth_f[o+1:o+21];p5=_p5_predict(p5path,x0,un);mask=np.linalg.norm(tf,axis=-1)>=force_floor
            for k,pred in (("H2_displacement",hd),("truth_displacement",td),("legacy_P5",p5)):angles[k].append(_angles(pred,tf)[mask])
            windows+=1
    summary={k:{"samples":int(sum(len(x) for x in v)),"mae_deg":float(np.mean(np.concatenate(v))),"p95_deg":float(np.quantile(np.concatenate(v),.95))} for k,v in angles.items()};gates={"truth_geometry":summary["truth_displacement"]["p95_deg"]<=2,"H2_geometry_fails":summary["H2_displacement"]["p95_deg"]>2}
    return {"windows":windows,"direction_source":"true force magnitude fixed for displacement oracles; legacy P5 is direction-only historical diagnostic","metrics":summary,"gates":gates,"passed":all(gates.values())}
