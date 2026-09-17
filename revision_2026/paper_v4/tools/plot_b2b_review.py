"""Read-only B2b review and reproducible figures; does not change gate verdicts."""
from pathlib import Path
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results'
OUT = ROOT / 'analysis' / 'b2b_latest_review_20260913'
OUT.mkdir(parents=True, exist_ok=True)
paths = {k: RESULTS / v for k, v in {
    'serial': '20260913_R4B_B2B_SERIAL02',
    'parallel': '20260913_R4B_B2B_PARALLEL01',
    'source': '20260911_R3_UNFROZEN_FULL01/2ms',
}.items()}

def read(folder, name):
    with np.load(folder / name, allow_pickle=False) as a:
        return a['values'].copy(), [str(x) for x in a['columns']]

raw = {k: read(p, 'raw.npz') for k, p in paths.items()}
sub = {k: read(p, 'substeps.npz') for k, p in paths.items()}
s, cols = raw['serial']; p, pc = raw['parallel']; origin, oc = raw['source']
assert cols == pc == oc
c = {v: i for i, v in enumerate(cols)}
# Map known fixed 20ms interval end coordinates to integer ticks, no interpolation.
ticks = np.rint(origin[:, c['time_s']] / .02).astype(int)
mask = (ticks > 2100) & (ticks <= 2225)
aligned = origin[mask]
assert np.array_equal(ticks[mask], np.arange(2101, 2226))
physical = [i for i, name in enumerate(cols) if name not in ('time_s', 'solver_wall_s')]
ss, sc = sub['serial']; ps, psc = sub['parallel']; os, osc = sub['source']
assert sc == psc == osc
st = np.rint(os[:, 0] / .002).astype(int)
sa = os[(st > 21000) & (st <= 22250)]
assert np.array_equal(st[(st > 21000) & (st <= 22250)], np.arange(21001, 22251))
metrics = {k: json.loads((paths[k] / 'metrics.json').read_text()) for k in ('serial','parallel')}
report = {
    'scope': 'Independent local review; original formal FAIL unchanged; not full R3',
    'raw_rows': len(s), 'substep_rows': len(ss),
    'serial_parallel_physical_exact': bool(np.array_equal(s[:,physical],p[:,physical])),
    'serial_parallel_substeps_exact': bool(np.array_equal(ss,ps)),
    'aligned_source_physical_exact': bool(np.array_equal(s[:,physical],aligned[:,physical])),
    'aligned_source_substep_non_time_exact': bool(np.array_equal(ss[:,1:],sa[:,1:])),
    'source_raw_time_max_difference_s': float(np.max(np.abs(s[:,0]-aligned[:,0]))),
    'source_substep_time_max_difference_s': float(np.max(np.abs(ss[:,0]-sa[:,0]))),
    'serial_wall_s': metrics['serial']['wall_s'],
    'parallel_wall_s': metrics['parallel']['wall_s'],
    'speedup': metrics['serial']['wall_s']/metrics['parallel']['wall_s'],
    'parallel_observed_wall_per_tick_s': metrics['parallel']['wall_s']/125,
    'full_route_extrapolation_hours_not_guarantee': metrics['parallel']['wall_s']/125*2379/3600,
    'maximum_substep_force_n': float(ss[:,[sc.index(f'force_peak{i}') for i in range(4)]].max()),
}
manifest = {'scope': report['scope'], 'source_files': [], 'figures': []}
for folder in paths.values():
    for name in ('raw.npz','substeps.npz'):
        file = folder / name
        manifest['source_files'].append({'path': str(file.relative_to(ROOT)), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})

def save(fig, name, caption):
    fig.tight_layout()
    for ext in ('png','svg'):
        fig.savefig(OUT / f'{name}.{ext}', dpi=180)
    manifest['figures'].append({'name':name,'caption':caption,'files':[f'{name}.png',f'{name}.svg']})
    plt.close(fig)

t = np.arange(2101,2226)*.02
fig, axes = plt.subplots(1,3,figsize=(13,3.7))
axes[0].plot(t,np.max(np.abs(s[:,physical]-p[:,physical]),axis=1))
axes[0].set(title='Serial / parallel: physical difference',xlabel='Interval end time (s)',ylabel='Max absolute difference (native units)')
axes[1].plot(t,(s[:,0]-aligned[:,0])*1e15)
axes[1].set(title='Aligned source timestamp difference',xlabel='Interval end time (s)',ylabel='Timestamp difference (fs)')
axes[2].bar(['Serial','Parallel (8)'],[report['serial_wall_s']/60,report['parallel_wall_s']/60],color=['#315a9c','#e18437'])
axes[2].set(title=f"Window speedup: {report['speedup']:.3f}x",ylabel='Total wall time (min)')
for ax in axes: ax.grid(alpha=.2)
save(fig,'01_equivalence_and_cost','Physical equality is limited to this window; source timestamps differ. Original formal verdict remains FAIL.')

fig,axes=plt.subplots(2,2,figsize=(11,7))
for label,data,style in [('Serial',s,'-'),('Parallel (8)',p,'--')]:
    axes[0,0].plot(data[:,c['x24']],data[:,c['x25']],style,label=label)
    axes[0,1].plot(t,data[:,c['max_e_g_m']]*1000,style,label=label)
    axes[1,1].plot(t,data[:,c['solver_wall_s']],style,label=label)
for i in range(4): axes[1,0].plot(t,s[:,c[f'point_force_norm{i}']],label=f'Connection {i+1}')
axes[0,0].set(title='Payload path: short window only',xlabel='World X (m)',ylabel='World Y (m)')
axes[0,1].set(title='Maximum configuration error',xlabel='Time (s)',ylabel='Error (mm)')
axes[1,0].set(title='Connection forces: zero in this window',xlabel='Time (s)',ylabel='Force norm (N)')
axes[1,1].axhline(5,color='r',ls=':',label='Original 5 s budget')
axes[1,1].set(title='Recorded solver wall time',xlabel='Time (s)',ylabel='Wall time (s)')
for ax in axes.flat: ax.legend(fontsize=8); ax.grid(alpha=.2)
save(fig,'02_window_physics','Overlapping serial and parallel trajectories. Zero forces are observed window data, not evidence of loaded-domain equivalence.')

fig,axes=plt.subplots(1,3,figsize=(13,3.8))
for i in range(4):
    axes[0].plot(t,np.rad2deg(s[:,c[f'request_delta{i}']]),label=f'Vehicle {i+1}')
    axes[1].plot(t,s[:,c[f'tire_utilization{i}']],label=f'Vehicle {i+1}')
    axes[2].plot(t,s[:,c[f'support_load{i}']],label=f'Vehicle {i+1}')
axes[0].set(title='Requested steering',ylabel='Angle (deg)')
axes[1].set(title='Tire utilization',ylabel='Utilization (1)')
axes[2].set(title='Support loads',ylabel='Load (N)')
for ax in axes: ax.set_xlabel('Time (s)'); ax.legend(fontsize=8); ax.grid(alpha=.2)
save(fig,'03_window_controls','Serial data shown; parallel physical/control arrays were independently checked identical. Simulation data only.')
(OUT/'analysis.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(OUT/'figure_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
