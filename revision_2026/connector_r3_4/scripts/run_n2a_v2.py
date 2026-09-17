from __future__ import annotations
import argparse,csv,json,math,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from connector_adapter import DELTA_S_M
from event_substep import integrate
from reference_oracle import OracleConfig,solve_oracle
SPEEDS={'q05':0.0002041391858023853,'q50':0.003371584129140294,'q95':0.054984709782141795,'q99':0.2006325726682664,'stress_0p25':.25,'stress_1p0':1.0}
def duration(v):return max(.020,DELTA_S_M/v+.012)
def dump(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def csvout(p,rows):
 f=list(dict.fromkeys(k for r in rows for k in r));p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',newline='',encoding='utf-8-sig') as s:w=csv.DictWriter(s,fieldnames=f);w.writeheader();w.writerows(rows)
def rel(a,b,scale):return abs(a-b)/max(scale,1e-300)
def state_err(a,b,v):return max(abs(a['terminal_penetration_m']-b['terminal_penetration_m'])/max(DELTA_S_M,abs(b['terminal_penetration_m']),v*.002,1e-6),abs(a['terminal_speed_mps']-b['terminal_speed_mps'])/max(v,abs(b['terminal_speed_mps']),1e-4))
def main():
 a=argparse.ArgumentParser();a.add_argument('--project-root',type=Path,required=True);a.add_argument('--pilot-only',action='store_true');x=a.parse_args();project=x.project_root.resolve();out=project/'revision_2026/connector_r3_4_results/n2a';out.mkdir(parents=True,exist_ok=True)
 labels=['q05','q95'] if x.pilot_only else list(SPEEDS);fixed=[];orows=[];checks=[];started=time.perf_counter()
 for label in labels:
  v=SPEEDS[label];dur=duration(v)
  for law in ('V1','R3'):
   main=solve_oracle(law,0.,v,dur,OracleConfig());tight=solve_oracle(law,0.,v,dur,OracleConfig(2.5e-12,2.5e-14,2.5e-12,2.5e-13))
   orows.append({'speed_label':label,'law':law,'tier':'main',**{k:main[k] for k in ('status','peak_force_n','impulse_ns','terminal_penetration_m','terminal_speed_mps','max_event_residual_m','segments','time_conservation_residual_s')}});orows.append({'speed_label':label,'law':law,'tier':'tight',**{k:tight[k] for k in ('status','peak_force_n','impulse_ns','terminal_penetration_m','terminal_speed_mps','max_event_residual_m','segments','time_conservation_residual_s')}})
   runs={}
   for dt in (2e-6,1e-6,.5e-6,.25e-6):
    st=time.perf_counter();r=integrate(law,0.,v,dur,'REF',fixed_step_s=dt,keep_trace=False);r['runtime_s']=time.perf_counter()-st;runs[dt]=r;fixed.append({'speed_label':label,'law':law,'dt_s':dt,**{k:r[k] for k in ('status','peak_force_n','impulse_ns','terminal_penetration_m','terminal_speed_mps','min_accepted_dt_s','min_advanced_dt_s','time_conservation_residual_s','runtime_s')}})
   peak_scale=max(abs(tight['peak_force_n']),50.);jscale=max(abs(tight['impulse_ns']),50*dur)
   oracle_peak=rel(main['peak_force_n'],tight['peak_force_n'],peak_scale);oracle_j=rel(main['impulse_ns'],tight['impulse_ns'],jscale);oracle_state=state_err(main,tight,v)
   ref=runs[.5e-6]; ref_peak=rel(ref['peak_force_n'],tight['peak_force_n'],peak_scale);ref_j=rel(ref['impulse_ns'],tight['impulse_ns'],jscale);ref_state=state_err(ref,tight,v)
   diffs={}
   for metric,scale in [('impulse_ns',jscale),('terminal_penetration_m',max(DELTA_S_M,abs(tight['terminal_penetration_m']),v*.002,1e-6)),('terminal_speed_mps',max(v,abs(tight['terminal_speed_mps']),1e-4))]:
    ds=[abs(runs[h][metric]-runs[h/2][metric])/scale for h in (2e-6,1e-6,.5e-6)];dif=ds[-1];floor=dif<=1e-10;mono=ds[2]<=ds[1]<=ds[0];p=math.log(ds[1]/ds[2],2) if ds[2]>0 and ds[1]>0 else float('inf');diffs[metric]={'d':ds,'floor':floor,'monotonic':mono,'p_obs_last':p,'passed':floor or (mono and p>=.9)}
   passed=oracle_peak<=.0005 and oracle_j<=.0002 and oracle_state<=.0001 and ref_peak<=.005 and ref_j<=.002 and ref_state<=.001 and all(z['passed'] for z in diffs.values()) and max(main['max_event_residual_m'],tight['max_event_residual_m'])<=1e-8 and max(main['time_conservation_residual_s'],tight['time_conservation_residual_s'],ref['time_conservation_residual_s'])<=1e-12
   checks.append({'speed_label':label,'law':law,'oracle_peak':oracle_peak,'oracle_impulse':oracle_j,'oracle_terminal':oracle_state,'ref_0p5_peak':ref_peak,'ref_0p5_impulse':ref_j,'ref_0p5_terminal':ref_state,'convergence':diffs,'passed':passed})
 csvout(out/('fixed_pilot.csv' if x.pilot_only else 'fixed_reference.csv'),fixed);csvout(out/('oracle_pilot.csv' if x.pilot_only else 'oracle.csv'),orows);dump(out/('checks_pilot.json' if x.pilot_only else 'checks.json'),checks)
 complete={'stage':'S4_PILOT' if x.pilot_only else 'S4','passed':all(c['passed'] for c in checks),'pairs':len(checks),'runtime_s':time.perf_counter()-started,'checks':checks};dump(out/('pilot_complete.json' if x.pilot_only else 'complete.json'),complete);print(json.dumps({'stage':complete['stage'],'passed':complete['passed'],'pairs':len(checks),'runtime_s':complete['runtime_s']}));raise SystemExit(0 if complete['passed'] else 2)
if __name__=='__main__':main()
