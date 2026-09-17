"""Centralized full-state physical MPC diagnostic upper bound (EXP-R2 R2)."""
from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np
from scipy import sparse
import osqp

from ..diagnostics.relative_motion import extract, wrap
from ..e01_100m import LIMIT, RATE, TAU
from ..plant.four_vehicle_common import connector_diagnostics, rk4_step, rotation, system_derivative


TS = 0.02
PLANT_DT = 0.002
ACCEL_LIMIT = 2.0  # existing common 1.2 + differential 0.8 envelope
PREDICTED_FORCE_BUDGET_N = 12000.0


@dataclass(frozen=True)
class PilotConfig:
    horizon: int = 20
    lambda_internal: float = 1.0
    max_iter: int = 4000
    eps_abs: float = 2e-4
    eps_rel: float = 2e-4
    frozen_dynamics_jacobian: bool = True
    finite_difference_scale: float = 1.0


def actuator_step(request, actual, dt=PLANT_DT):
    request=np.asarray(request,float);actual=np.asarray(actual,float)
    free=request+np.exp(-dt/TAU)*(actual-request)
    return np.clip(actual+np.clip(free-actual,-RATE*dt,RATE*dt),-LIMIT,LIMIT)


def rollout_step(z, u, model):
    """20 ms physical prediction with ten frozen 2 ms actuator/plant updates."""
    z=np.asarray(z,float);u=np.asarray(u,float).reshape(4,2);state=z[:30].copy();delta=z[30:].copy()
    for _ in range(10):
        delta=actuator_step(u[:,1],delta)
        state=rk4_step(state,np.c_[u[:,0],delta],PLANT_DT,model,"R3",load_transfer_enabled=True)
    return np.r_[state,delta]


def _steps(size, actuator=False, scale=1.0):
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("finite_difference_scale must be finite and positive")
    base=np.empty(size)
    for i in range(size):
        j=i%6 if i<30 else None
        base[i]=1e-6 if actuator or i>=30 or j in (2,5) else 1e-5
    return base*scale


def linearize_step(z, u, model, finite_difference_scale=1.0):
    z=np.asarray(z,float);u=np.asarray(u,float);f0=rollout_step(z,u,model);A=np.empty((34,34));B=np.empty((34,8))
    for j,h in enumerate(_steps(34, scale=finite_difference_scale)):
        zp=z.copy();zm=z.copy();zp[j]+=h;zm[j]-=h;A[:,j]=(rollout_step(zp,u,model)-rollout_step(zm,u,model))/(2*h)
    uh=np.asarray([1e-4 if j%2==0 else 1e-6 for j in range(8)])*finite_difference_scale
    for j,h in enumerate(uh):
        up=u.copy();um=u.copy();up[j]+=h;um[j]-=h;B[:,j]=(rollout_step(z,up,model)-rollout_step(z,um,model))/(2*h)
    return f0,A,B


def tracking_feature(z, ref, model):
    state=np.asarray(z[:30]);payload=state[24:];rp=np.asarray(ref["payload"]);r=rotation(rp[2]);pos=(payload[:2]-rp[:2])@r
    rel=extract(state,model,ref["q_star"],ref["beta_star"])
    return np.r_[pos/0.1,float(wrap(payload[2]-rp[2]))/np.deg2rad(2), (payload[3]-rp[3])/0.5, payload[4]/0.2, (payload[5]-rp[5])/0.2, rel["e_g_m"].ravel()/0.1, rel["e_beta_rad"]/np.deg2rad(2), (rel["relative_velocity_body_mps"]-np.asarray(ref["q_dot_star"])).ravel()/0.1]


def _jacobian(fn, z, finite_difference_scale=1.0):
    y=np.asarray(fn(z),float);J=np.empty((len(y),len(z)))
    for j,h in enumerate(_steps(len(z), scale=finite_difference_scale)):
        zp=z.copy();zm=z.copy();zp[j]+=h;zm[j]-=h;J[:,j]=(fn(zp)-fn(zm))/(2*h)
    return y,J


def internal_vector(z, model):
    return np.asarray(connector_diagnostics(z[:30],model,"R3")["internal_force_vector_n"],float)/PREDICTED_FORCE_BUDGET_N


def constraint_values(z, u, model):
    diag=connector_diagnostics(z[:30],model,"R3");_,system=system_derivative(z[:30],np.c_[np.asarray(u).reshape(4,2)[:,0],z[30:]],model,"R3",load_transfer_enabled=True)
    return np.r_[diag["force_norm_n"]/PREDICTED_FORCE_BUDGET_N,np.asarray([v["raw_utilization"] for v in system["tire"]]),-np.asarray(system["payload_support_load_n"])/10000.0]


def _constraint_jacobian(z,u,model,finite_difference_scale=1.0):
    c0=constraint_values(z,u,model);Jz=np.empty((12,34));Ju=np.empty((12,8))
    for j,h in enumerate(_steps(34, scale=finite_difference_scale)):
        zp=z.copy();zm=z.copy();zp[j]+=h;zm[j]-=h;Jz[:,j]=(constraint_values(zp,u,model)-constraint_values(zm,u,model))/(2*h)
    for j,h in enumerate(np.asarray([1e-4 if j%2==0 else 1e-6 for j in range(8)])*finite_difference_scale):
        up=u.copy();um=u.copy();up[j]+=h;um[j]-=h;Ju[:,j]=(constraint_values(z,up,model)-constraint_values(z,um,model))/(2*h)
    return c0,Jz,Ju


def build_problem(z0, u_nom, refs, model, config=PilotConfig()):
    n=config.horizon;u_nom=np.asarray(u_nom,float).reshape(n,8)
    if len(refs)!=n:raise ValueError("reference preview length must equal horizon")
    zbar=[np.asarray(z0,float)];dynamics=[];frozen=None
    for h in range(n):
        if h==0 or not config.frozen_dynamics_jacobian:
            nxt,A,B=linearize_step(zbar[-1],u_nom[h],model,config.finite_difference_scale)
            if h==0:frozen=(A,B)
        else:
            nxt=rollout_step(zbar[-1],u_nom[h],model);A,B=frozen
        dynamics.append((A,B));zbar.append(nxt)
    sensitivities=[];S=np.zeros((34,8*n))
    for h,(A,B) in enumerate(dynamics):
        S=A@S;S[:,8*h:8*h+8]+=B;sensitivities.append(S.copy())
    H=np.eye(8*n)*1e-8;g=np.zeros(8*n);constraint_rows=[];constraint_upper=[]
    for h in range(n):
        e,Je=_jacobian(lambda value:tracking_feature(value,refs[h],model),zbar[h+1],config.finite_difference_scale);M=Je@sensitivities[h];H+=2*M.T@M;g+=2*M.T@e
        fint,Jf=_jacobian(lambda value:internal_vector(value,model),zbar[h+1],config.finite_difference_scale);Mf=Jf@sensitivities[h];H+=2*config.lambda_internal*(Mf.T@Mf);g+=2*config.lambda_internal*Mf.T@fint
        steer=np.arange(8*h+1,8*h+8,2);nom_steer=u_nom[h,1::2];H[np.ix_(steer,steer)]+=2*0.1*np.eye(4)/(np.deg2rad(2)**2);g[steer]+=2*0.1*(nom_steer-np.asarray(refs[h]["steering_nominal"]))/(np.deg2rad(2)**2)
        c0,Jz,Ju=_constraint_jacobian(zbar[h+1],u_nom[h],model,config.finite_difference_scale);Mc=Jz@sensitivities[h];Mc[:,8*h:8*h+8]+=Ju;constraint_rows.append(Mc);constraint_upper.append(np.r_[np.ones(8),np.zeros(4)]-c0)
    D=np.zeros((8*n,8*n));target=np.zeros(8*n)
    prev=np.asarray(refs[0].get("previous_u",u_nom[0]),float)
    for h in range(n):
        D[8*h:8*h+8,8*h:8*h+8]=np.eye(8)
        if h: D[8*h:8*h+8,8*(h-1):8*h]=-np.eye(8);target[8*h:8*h+8]=-(u_nom[h]-u_nom[h-1])
        else: target[:8]=-(u_nom[0]-prev)
    scale=np.tile(np.asarray([0.2,np.deg2rad(2)]*4),n);Ds=D/scale[:,None];ts=target/scale;H+=2*0.05*(Ds.T@Ds);g+=2*0.05*Ds.T@ts
    lower=np.tile(np.asarray([-ACCEL_LIMIT,-LIMIT]*4),n)-u_nom.ravel();upper=np.tile(np.asarray([ACCEL_LIMIT,LIMIT]*4),n)-u_nom.ravel()
    Aall=np.vstack([np.eye(8*n),*constraint_rows]);lall=np.r_[lower,np.full(12*n,-np.inf)];uall=np.r_[upper,*constraint_upper]
    return {"P":0.5*(H+H.T),"q":g,"A":Aall,"l":lall,"u":uall,"u_nom":u_nom,"zbar":zbar,"sensitivities":sensitivities}


def solve(z0,u_nom,refs,model,config=PilotConfig()):
    started=time.perf_counter()
    try:
        problem=build_problem(z0,u_nom,refs,model,config)
    except Exception as error:
        return {"status":"FAIL","solver_status":"MODEL_DOMAIN_ERROR","iterations":0,"primal_residual":float("inf"),"dual_residual":float("inf"),"objective":float("inf"),"wall_s":time.perf_counter()-started,"control":np.asarray(u_nom,float).reshape(config.horizon,8),"validation":{"status":"FAIL","reason":f"{type(error).__name__}: {error}"},"problem":None}
    solver=osqp.OSQP();solver.setup(P=sparse.csc_matrix(problem["P"]),q=problem["q"],A=sparse.csc_matrix(problem["A"]),l=problem["l"],u=problem["u"],verbose=False,eps_abs=config.eps_abs,eps_rel=config.eps_rel,max_iter=config.max_iter,polishing=True);result=solver.solve();ok=result.info.status in ("solved","solved inaccurate")
    candidate=problem["u_nom"].ravel()+result.x if ok and result.x is not None else problem["u_nom"].ravel();validation=validate(z0,candidate.reshape(config.horizon,8),model)
    accepted=bool(ok and validation["status"]=="PASS")
    return {"status":"PASS" if accepted else "FAIL","solver_status":result.info.status,"iterations":int(result.info.iter),"primal_residual":float(result.info.prim_res),"dual_residual":float(result.info.dual_res),"objective":float(result.info.obj_val),"wall_s":time.perf_counter()-started,"control":candidate.reshape(config.horizon,8),"validation":validation,"problem":problem}


def validate(z0,controls,model):
    z=np.asarray(z0,float).copy();max_force=max_tire=0.;min_support=float("inf")
    for h,u in enumerate(np.asarray(controls).reshape(-1,8)):
        z=rollout_step(z,u,model);values=constraint_values(z,u,model);max_force=max(max_force,float(np.max(values[:4])*PREDICTED_FORCE_BUDGET_N));max_tire=max(max_tire,float(np.max(values[4:8])));min_support=min(min_support,float(-np.max(values[8:])*10000.))
        if max_force>PREDICTED_FORCE_BUDGET_N+1e-6 or max_tire>1.+1e-9 or min_support<0.:
            return {"status":"FAIL","failure_step":h+1,"max_point_force_n":max_force,"max_tire_utilization":max_tire,"minimum_support_n":min_support}
    return {"status":"PASS","failure_step":None,"max_point_force_n":max_force,"max_tire_utilization":max_tire,"minimum_support_n":min_support,"terminal_state":z.tolist()}
