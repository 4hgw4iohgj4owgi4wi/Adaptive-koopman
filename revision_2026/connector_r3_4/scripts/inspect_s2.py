from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from event_substep import integrate
v=0.054984709782141795
r=integrate('R3',-v*(0.002+0.00075),v,0.02275,'ES',keep_trace=True)
print(json.dumps({'status':r['status'],'events':r['events'],'interesting':[x for x in r['step_records'] if x['selection_cause']=='EVENT_ROOT' or x['dt_class']!='REGULAR_DT']},indent=2))
