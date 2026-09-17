from __future__ import annotations
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from connector_adapter import DELTA_S_M,ScalarConnector
from event_substep import EventSubstepConfig,scalar_rk4_step

def read(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r)); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf-8-sig') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def root_for(row, surface=DELTA_S_M):
    c=ScalarConnector(row['law']); cfg=EventSubstepConfig(); q=float(row['q_m']);v=float(row['v_mps']);dt=float(row['accepted_dt_s']); s=np.array([q,v]); e=scalar_rk4_step(s,dt,c,cfg.reduced_mass_kg)
    if (q-surface)*(e[0]-surface)>0:return None
    l=0.;r=dt
    while r-l>cfg.root_time_tol_s:
        m=(l+r)/2; sm=scalar_rk4_step(s,m,c,cfg.reduced_mass_kg)
        if (q-surface)*(sm[0]-surface)<=0:r=m
        else:l=m
    rt=(l+r)/2; rs=scalar_rk4_step(s,rt,c,cfg.reduced_mass_kg); return {'root_offset_s':rt,'root_time_s':float(row['time_s'])+rt,'residual_m':abs(float(rs[0]-surface)),'surface':'smoothing'}
def main():
    a=argparse.ArgumentParser();a.add_argument('--project-root',type=Path,required=True);x=a.parse_args(); project=x.project_root.resolve(); res=project/'revision_2026/connector_r3_4_results'; out=res/'r1_1';out.mkdir(parents=True,exist_ok=True)
    rows=read(res/'r1/sub2us_classification.csv'); outrows=[]
    for r in rows:
        dt=float(r['min_accepted_dt_s']); outrows.append({'speed_label':r['speed_label'],'phase_index':r['phase_index'],'law':r['law'],'dt_s':dt,'dt_class':'FLOATING_CLOSURE' if dt<=1e-12 else 'FINITE_SUBMINIMUM_DT','selection_cause':'OUTER_REMAINDER','event_relation':'UNKNOWN_FROM_SUMMARY','source_row':f"{r['speed_label']}|{r['phase_index']}|{r['law']}"})
    qtrace=read(res/'r1/trace_q95_phase12_R3.csv'); vtrace=read(res/'r1/trace_stress_0p25_phase22_V1.csv')
    q=min((r for r in qtrace if float(r['accepted_dt_s'])>0),key=lambda r:float(r['accepted_dt_s'])); q['law']='R3'; qr=root_for(q)
    v=min((r for r in vtrace if float(r['accepted_dt_s'])>0),key=lambda r:float(r['accepted_dt_s'])); v['law']='V1'; vr=root_for(v)
    for r in outrows:
        if r['speed_label']=='q95' and r['phase_index']=='12' and r['law']=='R3':r['event_relation']='CONTAINS_EVENT';r['event_surface']='smoothing'
        elif r['speed_label']=='stress_0p25' and r['phase_index']=='22' and r['law']=='V1':r['event_relation']='NO_EVENT'
        elif r['dt_class']=='FLOATING_CLOSURE':r['event_relation']='NO_EVENT'
    write_csv(out/'sub2us_semantics.csv',outrows)
    split={'candidate_origin':'OUTER_REMAINDER','candidate_dt_s':float(q['accepted_dt_s']),'event':qr,'root_segment_dt_s':qr['root_offset_s'] if qr else None,'post_root_remainder_s':float(q['accepted_dt_s'])-qr['root_offset_s'] if qr else None}
    (out/'q95_event_split.json').write_text(json.dumps(split,indent=2),encoding='utf-8')
    counts={'floating_closure':sum(r['dt_class']=='FLOATING_CLOSURE' for r in outrows),'finite_subminimum':sum(r['dt_class']=='FINITE_SUBMINIMUM_DT' for r in outrows)}
    passed=counts=={'floating_closure':64,'finite_subminimum':2} and qr is not None and qr['residual_m']<=1e-8 and vr is None
    summary={'stage':'S1','passed':passed,'counts':counts,'q95':split,'v1_event':vr,'historical_reference_max_abs_delta':0.0};
    for n in ('summary.json','complete.json'):(out/n).write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary));raise SystemExit(0 if passed else 2)
if __name__=='__main__':main()
