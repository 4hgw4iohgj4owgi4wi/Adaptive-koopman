"""Read-only review and figures for interrupted P1; never resumes dynamics."""
from pathlib import Path
import json, hashlib, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
run=root/'results/20260915_R4_P1_2MS01'
out=root/'analysis/P1_2200_review_20260915'
out.mkdir(parents=True,exist_ok=True)
def read(name):
    with np.load(run/name,allow_pickle=False) as a:
        return a['values'].copy(),{str(k):i for i,k in enumerate(a['columns'])}
r,c=read('raw.npz');s,d=read('substeps.npz')
sol=[json.loads(l) for l in (run/'solver.jsonl').read_text().splitlines() if l.strip()]
sys.path.insert(0,str(root/'src'))
from paper_v4_core.references import build_hairpin
route=build_hairpin()
reference=np.column_stack([np.interp(r[:,c['reference_distance_m']],route['s_m'],route[k]) for k in ['x_m','y_m','heading_rad']])
err=np.linalg.norm(r[:,[c['x24'],c['x25']]]-reference[:,:2],axis=1)
a=r[:,c['x26']]-reference[:,2];heading=np.rad2deg(np.arctan2(np.sin(a),np.cos(a)))
peaks=np.array([s[:,d[f'force_peak{i}']].max() for i in range(4)])
request=np.rad2deg(r[:,[c[f'request_delta{i}'] for i in range(4)]])
actual=np.rad2deg(r[:,[c[f'actual_delta{i}'] for i in range(4)]])
report={'scope':'Accepted prefix only; no full-route PASS/FAIL; no resume/retry',
 'accepted_ticks':len(r),'expected_ticks':2379,'solver_rows':len(sol),'unclosed_solver_rows':len(sol)-len(r),
 'substep_rows':len(s),'last_time_s':float(r[-1,c['time_s']]),'substep_duration_s':float(s[:,d['dt_s']].sum()),
 'completion_fraction':len(r)/2379,'remaining_ticks':2379-len(r),
 'all_arrays_finite':bool(np.isfinite(r).all() and np.isfinite(s).all()),
 'all_logged_solver_and_nonlinear_pass':all(x.get('status')=='PASS' and x.get('validation',{}).get('status')=='PASS' for x in sol),
 'peak_force_n':float(peaks.max()),'peak_internal_n':float(r[:,c['internal_force_norm_n']].max()),
 'tire_max':float(s[:,[d[f'tire_utilization{i}'] for i in range(4)]].max()),
 'support_min_n':float(s[:,[d[f'support_load{i}'] for i in range(4)]].min()),
 'configuration_max_m':float(r[:,c['max_e_g_m']].max()),
 'request_max_deg':float(abs(request).max()),'actual_max_deg':float(abs(actual).max()),
 'prefix_position_rmse_m':float(np.sqrt(np.mean(err**2))),'prefix_position_max_m':float(err.max()),
 'prefix_heading_rmse_deg':float(np.sqrt(np.mean(heading**2))),
 'all_solver_mean_s':float(np.mean([x['wall_s'] for x in sol])),
 'accepted_solver_mean_s':float(np.mean([x['wall_s'] for x in sol[:len(r)]])),
 'decision':'CANNOT_RELEASE_NEXT_FORMAL_RUN; GPU_PORT_OFFLINE_QUALIFICATION_CAN_BE_PLANNED'}
(out/'analysis.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
fig,ax=plt.subplots(3,2,figsize=(13,12));t=r[:,c['time_s']]
ax[0,0].plot(route['x_m'],route['y_m'],'k--',label='Full frozen reference')
ax[0,0].plot(r[:,c['x24']],r[:,c['x25']],label='Accepted payload prefix')
ax[0,0].set(xlabel='World X (m)',ylabel='World Y (m)',title='2200 / 2379 ticks: INCOMPLETE');ax[0,0].axis('equal')
ax[0,1].plot(t,err,label='Payload position error');ax[0,1].plot(t,r[:,c['max_e_g_m']],label='Configuration error');ax[0,1].set(xlabel='Time (s)',ylabel='Error (m)',title='Prefix errors only')
for i in range(4):
 ax[1,0].plot(s[:,d['time_s']],s[:,d[f'force_peak{i}']],label=f'Connection {i+1}')
 ax[1,1].plot(t,request[:,i],label=f'Request {i+1}')
ax[1,0].set(xlabel='Time (s)',ylabel='Force (N)',title='Accepted substep force peaks')
ax[1,1].set(xlabel='Time (s)',ylabel='Steering (deg)',title='Requested steering');ax[1,1].axhline(15,color='k',ls=':');ax[1,1].axhline(-15,color='k',ls=':')
for i in range(4):ax[2,0].plot(s[:,d['time_s']],s[:,d[f'tire_utilization{i}']],label=f'Vehicle {i+1}')
ax[2,0].set(xlabel='Time (s)',ylabel='Utilization (1)',title='Tire utilization in accepted prefix')
ax[2,1].plot(t,[x['wall_s'] for x in sol[:len(r)]],label='CPU parallel8 solver');ax[2,1].axhline(5,color='r',ls=':',label='Original 5 s budget');ax[2,1].set(xlabel='Time (s)',ylabel='Wall time (s)',title='Accepted prefix solver costs')
for item in ax.flat:item.legend(fontsize=8);item.grid(alpha=.2)
fig.suptitle('P1 / 2 ms: externally interrupted, no full-route verdict')
fig.tight_layout()
for ext in ('png','svg'):fig.savefig(out/f'accepted_prefix.{ext}',dpi=200)
plt.close(fig)
manifest={'science_status':'INCOMPLETE','scope':report['scope'],'source_files':[{'path':str((run/n).relative_to(root)),'sha256':hashlib.sha256((run/n).read_bytes()).hexdigest()} for n in ['raw.npz','substeps.npz','solver.jsonl','status.json']], 'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'figures':['accepted_prefix.png','accepted_prefix.svg'],'figure_status':'GENERATED_PENDING_VISUAL_QA'}
(out/'figure_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
