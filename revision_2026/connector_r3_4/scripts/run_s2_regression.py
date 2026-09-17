from __future__ import annotations
import csv,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from event_substep import EventSubstepConfig,integrate
SPEEDS={'q95':0.054984709782141795,'stress_0p25':.25}
def rel(a,b):return abs(a-b)/max(abs(b),1e-300)
project=Path(sys.argv[1]);out=project/'revision_2026/connector_r3_4_results/audit_history/s2_regression';out.mkdir(parents=True,exist_ok=True)
with (project/'revision_2026/connector_r3_2_results/n2/single_connector_factorial.csv').open(newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
targets=[r for r in rows if (r['speed_label'],r['phase_index'],r['law']) in {('q95','12','R3'),('stress_0p25','22','V1')} and r['integrator']=='ES']
result=[]
for old in targets:
    speed=SPEEDS[old['speed_label']];q0=-speed*(.002+float(old['phase_s']));started=time.perf_counter();new=integrate(old['law'],q0,speed,float(old['duration_s']),'ES',keep_trace=True);runtime=time.perf_counter()-started
    item={'case':f"{old['speed_label']}|{old['phase_index']}|{old['law']}",'status':new['status'],'runtime_s':runtime,'old_min_dt_s':float(old['min_accepted_dt_s']),'new_min_regular_dt_s':new['min_accepted_dt_s'],'new_min_advanced_dt_s':new['min_advanced_dt_s'],'time_conservation_residual_s':new['time_conservation_residual_s'],'events':new['events'],'step_records':new['step_records']}
    for k in ('peak_force_n','impulse_ns','terminal_penetration_m','terminal_speed_mps'):
        item['old_'+k]=float(old[k]);item['new_'+k]=new[k];item[k+'_abs_change']=abs(new[k]-float(old[k]));item[k+'_rel_change']=rel(new[k],float(old[k]))
    (out/(item['case'].replace('|','_')+'.json')).write_text(json.dumps(item,indent=2),encoding='utf-8');result.append(item)
summary={'passed':all(x['status']=='PASS' and x['time_conservation_residual_s']<=1e-12 for x in result),'cases':[{k:v for k,v in x.items() if k not in {'events','step_records'}} for x in result]}
(out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary));raise SystemExit(0 if summary['passed'] else 2)
