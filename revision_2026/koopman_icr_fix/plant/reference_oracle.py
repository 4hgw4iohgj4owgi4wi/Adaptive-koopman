from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import minimize_scalar
from connector_adapter import DELTA_S_M,ScalarConnector

@dataclass(frozen=True)
class OracleConfig:
    rtol: float=1e-11
    atol_q: float=1e-13
    atol_v: float=1e-11
    atol_j: float=1e-12

def solve_oracle(law:str,q0:float,v0:float,duration:float,config:OracleConfig=OracleConfig()):
    connector=ScalarConnector(law);mass=300.; t=0.; y=np.array([q0,v0,0.]);segments=[];events=[];last=None;motion_direction=1 if v0>=0 else -1
    def rhs(_,z):
        f=float(connector.evaluate(float(z[0]),float(z[1]))['force_n']);return [z[1],-f/mass,f]
    while t<duration-1e-14:
        q,v=float(y[0]),float(y[1]); direction=(1 if v>0 else -1) if abs(v)>1e-12 else motion_direction
        targets=[]
        if direction>0:
            if q < -1e-12: targets=[(0.,'contact')]
            elif q < DELTA_S_M-1e-12: targets=[(DELTA_S_M,'smoothing')]
        else:
            if q > DELTA_S_M+1e-12: targets=[(DELTA_S_M,'smoothing')]
            elif q > 1e-12: targets=[(0.,'contact')]
        evs=[];meta=[]
        for surface,name in targets:
            def ev(_,z,s=surface):return z[0]-s
            ev.terminal=True;ev.direction=direction;evs.append(ev);meta.append(('surface',name,surface))
        if abs(v)>1e-12 and q>0:
            def turn(_,z):return z[1]
            turn.terminal=True;turn.direction=-direction;evs.append(turn);meta.append(('turn','turn',None))
        sol=solve_ivp(rhs,(t,duration),y,method='DOP853',rtol=config.rtol,atol=np.array([config.atol_q,config.atol_v,config.atol_j]),events=evs,dense_output=True,max_step=np.inf)
        segments.append(sol); y=sol.y[:,-1]; new_t=float(sol.t[-1])
        fired=None
        for i,arr in enumerate(sol.t_events):
            if len(arr) and abs(float(arr[-1])-new_t)<=1e-9:fired=meta[i];break
        if fired is None:t=new_t;break
        if new_t<=t+1e-14: raise RuntimeError('zero-time event loop')
        kind,name,surface=fired;t=new_t
        if kind=='surface':events.append({'time_s':t,'surface':name,'direction':'load' if direction>0 else 'unload','residual_m':abs(float(y[0]-surface))})
        last=fired
        if kind=='turn': motion_direction=-direction
        # The state is continuous. A tiny classification-only offset avoids selecting the same boundary again.
        if kind=='surface': y[0]=surface+direction*2e-12
    peak=0.;peak_t=0.
    for sol in segments:
        a,b=float(sol.t[0]),float(sol.t[-1]);grid=np.linspace(a,b,65);vals=np.array([connector.evaluate(float(sol.sol(x)[0]),float(sol.sol(x)[1]))['force_n'] for x in grid],float);i=int(np.argmax(vals))
        lo=grid[max(0,i-1)];hi=grid[min(len(grid)-1,i+1)]
        if hi>lo:
            opt=minimize_scalar(lambda x:-float(connector.evaluate(float(sol.sol(x)[0]),float(sol.sol(x)[1]))['force_n']),bounds=(lo,hi),method='bounded',options={'xatol':1e-14})
            value=-float(opt.fun);pt=float(opt.x)
        else:value=float(vals[i]);pt=float(grid[i])
        if value>peak:peak,peak_t=value,pt
    residual=max([e['residual_m'] for e in events],default=0.)
    return {'status':'PASS','peak_force_n':peak,'peak_time_s':peak_t,'impulse_ns':float(y[2]),'terminal_penetration_m':float(y[0]),'terminal_speed_mps':float(y[1]),'events':events,'max_event_residual_m':residual,'segments':len(segments),'time_conservation_residual_s':abs(duration-t)}
