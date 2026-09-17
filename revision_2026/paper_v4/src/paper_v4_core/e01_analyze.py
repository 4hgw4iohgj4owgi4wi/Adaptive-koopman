"""Independent convergence recomputation and figures for the E01 100 m subset."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from .cli import save,sha

STEPS=['2ms','1ms','0.5ms']


def audit_failure_boundary(folder):
 """Fail closed when accepted terminal motion is absent or completion is mislabeled."""
 folder=Path(folder)
 with np.load(folder/'raw.npz',allow_pickle=False) as z:
  raw=z['values'];rawcols=[str(x) for x in z['columns']]
 with np.load(folder/'substeps.npz',allow_pickle=False) as z:
  sub=z['values'];subcols=[str(x) for x in z['columns']]
 metrics=json.loads((folder/'metrics.json').read_text(encoding='utf-8'))
 ri={n:k for k,n in enumerate(rawcols)};si={n:k for k,n in enumerate(subcols)}
 missing=sorted({'time_s','accepted_substeps'}-set(ri)) + sorted({'time_s','dt_s'}-set(si))
 if missing or len(raw)==0:
  return {'status':'FAIL','reason':'MISSING_BOUNDARY_EVIDENCE','missing':missing}
 accepted_duration=float(np.sum(sub[:,si['dt_s']])) if len(sub) else 0.
 terminal_time=float(raw[-1,ri['time_s']])
 accepted_count=int(np.sum(raw[:,ri['accepted_substeps']]))
 requested=bool(metrics.get('requested_full_trajectory',metrics.get('complete_registered_trajectory',False)))
 completed=bool(metrics.get('trajectory_completed',False))
 hard_failed=str(metrics.get('status','PASS'))!='PASS'
 checks={
  'duration_matches_terminal':bool(np.isclose(accepted_duration,terminal_time,atol=1e-10,rtol=0.)),
  'duration_matches_metrics':bool(np.isclose(accepted_duration,float(metrics.get('integrated_duration_s',float('nan'))),atol=1e-10,rtol=0.)),
  'accepted_count_matches':bool(accepted_count==len(sub)==int(metrics.get('accepted_substeps',-1))),
  'completion_not_request_alias':bool(not completed or (requested and not hard_failed)),
  'failure_has_event_time':bool(not hard_failed or metrics.get('failure_event_time_s') is not None),
  'endpoint_state_saved':bool('state_at_t_end' in metrics and 'actuator_state_at_t_end' in metrics),
 }
 return {'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'accepted_duration_s':accepted_duration,'terminal_time_s':terminal_time,'accepted_steps':accepted_count,'requested_full_trajectory':requested,'trajectory_completed':completed,'hard_failed':hard_failed}

def load(folder):
 with np.load(folder/'raw.npz',allow_pickle=False) as z:
  a=z['values'];cols=[str(x) for x in z['columns']]
 m=json.loads((folder/'metrics.json').read_text())
 return a,{n:i for i,n in enumerate(cols)},m
def audit_run(folder,a,i,m):
 required={'time_s','interval_start_time_s','payload_support_load_0','vehicle_total_normal_load_0','tire_raw_utilization_0','accepted_substeps'}
 missing=sorted(required-set(i))
 with np.load(folder/'substeps.npz',allow_pickle=False) as z:
  sub=z['values'];subcols=[str(x) for x in z['columns']]
 si={n:k for k,n in enumerate(subcols)}
 subrequired={'time_s','dt_s','payload_support_load_0','vehicle_total_normal_load_0','tire_raw_utilization_0','tension_x_n','signed_gap_0','smoothing_weight_0'}
 submissing=sorted(subrequired-set(si))
 accepted=int(np.sum(a[:,i['accepted_substeps']])) if 'accepted_substeps' in i else -1
 duration=float(np.sum(sub[:,si['dt_s']])) if 'dt_s' in si else float('nan')
 support_cols=[si[f'payload_support_load_{j}'] for j in range(4)] if not submissing else []
 support_raw=[i[f'payload_support_load_{j}'] for j in range(4)] if not missing else []
 util_cols=[si[f'tire_raw_utilization_{j}'] for j in range(4)] if not submissing else []
 util_raw=[i[f'tire_raw_utilization_{j}'] for j in range(4)] if not missing else []
 min_support=float(min(np.min(sub[:,support_cols]),np.min(a[:,support_raw]))) if support_cols and support_raw else float('nan')
 max_util=float(max(np.max(sub[:,util_cols]),np.max(a[:,util_raw]))) if util_cols and util_raw else float('nan')
 xy=a[:,[i['x24'],i['x25']]];actual_path=float(np.sum(np.linalg.norm(np.diff(np.vstack((np.zeros((1,2)),xy)),axis=0),axis=1)))
 point_force=a[:,[i[f'payload_force_body_{j}'] for j in range(8)]].reshape(-1,4,2)
 vehicle_yaw=a[:,[i[f'vehicle_yaw_rate_{j}'] for j in range(4)]];payload_yaw=a[:,i['payload_yaw_rate']]
 checks={'three_files':all((folder/n).is_file() for n in ['raw.npz','substeps.npz','metrics.json']),'raw_columns':not missing,'substep_columns':not submissing,'finite_raw':bool(np.all(np.isfinite(a))),'finite_substeps':bool(np.all(np.isfinite(sub))),'substep_count':len(sub)==int(m['substep_records'])==int(m['accepted_substeps'])==accepted,'duration_closure':abs(duration-float(m['integrated_duration_s']))<=1e-10 and abs(duration-float(a[-1,i['time_s']]))<=1e-10,'support_recompute':abs(min_support-float(m['minimum_payload_support_load_n']))<=1e-9,'utilization_recompute':abs(max_util-float(m['maximum_tire_raw_utilization']))<=1e-12,'trajectory_complete':bool(m['complete_registered_trajectory'])}
 return {'folder':folder.name,'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'missing_raw_columns':missing,'missing_substep_columns':submissing,'raw_samples':len(a),'substep_records':len(sub),'integrated_duration_s':duration,'actual_payload_path_m':actual_path,'terminal_payload_xy_m':xy[-1].tolist(),'maximum_point_force_norm_n':float(np.max(np.linalg.norm(point_force,axis=2))),'maximum_abs_point_fx_n':float(np.max(abs(point_force[:,:,0]))),'maximum_abs_point_fy_n':float(np.max(abs(point_force[:,:,1]))),'maximum_longitudinal_opening_proxy_n':float(np.max(a[:,i['tension_x_n']])),'maximum_lateral_opening_proxy_n':float(np.max(a[:,i['tension_y_n']])),'maximum_abs_payload_yaw_rate_radps':float(np.max(abs(payload_yaw))),'maximum_vehicle_payload_yaw_rate_difference_radps':float(np.max(abs(vehicle_yaw-payload_yaw[:,None]))),'minimum_payload_support_load_n':min_support,'maximum_tire_raw_utilization':max_util}
def main(root):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 root=Path(root);pairs=[];audits=[];gate=True
 for p in ['P0','P1','P2']:
  data={s:load(root/f'{p}_{s}') for s in STEPS}
  for s,(a,i,m) in data.items():audits.append(audit_run(root/f'{p}_{s}',a,i,m))
  for coarse,fine in zip(STEPS[:-1],STEPS[1:]):
   a,ia,ma=data[coarse];b,ib,mb=data[fine]
   assert a.shape==b.shape and list(ia)==list(ib)
   peak_a=np.asarray(ma['force_peak4_n']);peak_b=np.asarray(mb['force_peak4_n'])
   imp_a=np.asarray(ma['force_impulse4x2_ns']);imp_b=np.asarray(mb['force_impulse4x2_ns'])
   peak_rel=float(np.max(abs(peak_a-peak_b)/np.maximum(abs(peak_b),1.)))
   imp_rel=float(np.max(np.linalg.norm(imp_a-imp_b,axis=1)/np.maximum(np.linalg.norm(imp_b,axis=1),1.)))
   pos_a=a[-1,[ia['x24'],ia['x25']]];pos_b=b[-1,[ib['x24'],ib['x25']]]
   pos=float(np.linalg.norm(pos_a-pos_b));yaw=float(np.rad2deg(abs(a[-1,ia['x26']]-b[-1,ib['x26']])))
   row={'parameter':p,'pair':f'{coarse}_to_{fine}','peak_max_relative':peak_rel,'impulse_vector_max_relative':imp_rel,'terminal_payload_position_m':pos,'terminal_payload_yaw_deg':yaw,'fine_pair_gate':None}
   if fine=='0.5ms':
    row['fine_pair_gate']=bool(peak_rel<=.02 and imp_rel<=.02 and pos<=.001 and yaw<=.01);gate &= row['fine_pair_gate']
   pairs.append(row)
 evidence_gate=all(a['status']=='PASS' for a in audits);gate &= evidence_gate
 report={'status':'PASS' if gate else 'FAIL','scope':'100m subset only (9 of E01 27 normal trajectories)','thresholds':{'peak_relative':.02,'impulse_vector_relative':.02,'terminal_position_m':.001,'terminal_yaw_deg':.01},'near_zero_policy':'vector impulse norm uses 1 N*s denominator floor; no claim for components below that resolution','evidence_audits':audits,'pairs':pairs,'source_sha':sha(__file__)}
 save(root,'convergence_100m.json',report)
 # Evidence plot from nominal finest trajectory.
 a,i,m=data = load(root/'P0_0.5ms');t=a[:,i['time_s']]
 fig,ax=plt.subplots(5,1,figsize=(11,12),sharex=True,constrained_layout=True)
 ax[0].plot(t,a[:,i['reference_accel_mps2']],label='Reference acceleration (m/s/s)');ax0=ax[0].twinx();ax0.plot(t,a[:,i['virtual_front_deg']],color='tab:red',label='Virtual front steer');ax0.plot(t,a[:,i['virtual_rear_deg']],color='tab:orange',label='Virtual rear steer');ax[0].set_ylabel('Acceleration (m/s²)');ax0.set_ylabel('Steering (deg)')
 for j in range(4):ax[1].plot(t,a[:,i[f'payload_force_body_{2*j}']],label=f'Point {j+1} Fx');ax[1].plot(t,a[:,i[f'payload_force_body_{2*j+1}']],ls='--',label=f'Point {j+1} Fy')
 ax[1].set_ylabel('Payload point force (N)');ax[1].legend(ncol=4,fontsize=7)
 for j in range(4):ax[2].plot(t,a[:,i[f'payload_support_load_{j}']],label=f'Point {j+1}')
 ax[2].set_ylabel('Vertical support (N)');ax[2].legend(ncol=4,fontsize=7)
 for j in range(4):ax[3].plot(t,a[:,i[f'vehicle_yaw_rate_{j}']],label=f'Vehicle {j+1}')
 ax[3].plot(t,a[:,i['payload_yaw_rate']],lw=2,label='Payload');ax[3].plot(t,a[:,i['intrinsic_inertia_weighted_yaw_rate']],lw=2,ls=':',label='Intrinsic-inertia weighted');ax[3].set_ylabel('Yaw rate (rad/s)');ax[3].legend(ncol=3,fontsize=7)
 ax[4].plot(t,a[:,i['tension_x_n']],label='Longitudinal opening proxy');ax[4].plot(t,a[:,i['tension_y_n']],label='Lateral opening proxy');ax[4].set_ylabel('Tension proxy (N)');ax[4].set_xlabel('Time (s)');ax[4].legend()
 for q in ax:
  for e in [12,17,22]:q.axvline(e,color='0.6',lw=.8,ls=':')
 fig.suptitle('EXP-R1 E01 100 m diagnostic — P0, 0.5 ms maximum substep')
 fig.savefig(root/'figure_100m_P0_0p5ms.png',dpi=180);plt.close(fig)
 anchors=np.asarray([[2.5,1.0],[2.5,-1.0],[-2.5,1.0],[-2.5,-1.0]])
 requested=[6.0,14.5,19.5,24.5];fig,axs=plt.subplots(1,4,figsize=(13,3.5),constrained_layout=True)
 for q,when in zip(axs,requested):
  k=int(np.argmin(abs(t-when)));force=np.asarray([a[k,[i[f'payload_force_body_{2*j}'],i[f'payload_force_body_{2*j+1}']]] for j in range(4)])
  q.scatter(anchors[:,0],anchors[:,1],c=np.arange(4),cmap='tab10',s=35);q.quiver(anchors[:,0],anchors[:,1],force[:,0],force[:,1],angles='xy',scale_units='xy',scale=max(np.max(np.linalg.norm(force,axis=1))/1.5,1.));q.axhline(0,color='.8');q.axvline(0,color='.8');q.set_aspect('equal');q.set_xlim(-3.3,3.3);q.set_ylim(-2,2);q.set_title(f't={t[k]:.2f}s\nTx={a[k,i["tension_x_n"]]:.1f}N, Ty={a[k,i["tension_y_n"]]:.1f}N');q.set_xlabel('payload-body x (m)')
 axs[0].set_ylabel('payload-body y (m)');fig.suptitle('Four connector force directions (arrow lengths normalized per panel)')
 fig.savefig(root/'figure_connector_directions_100m.png',dpi=180);plt.close(fig)
 fig,ax=plt.subplots(1,2,figsize=(9,4),constrained_layout=True)
 for p in ['P0','P1','P2']:
  rows=[r for r in pairs if r['parameter']==p];ax[0].plot([r['pair'] for r in rows],[100*r['peak_max_relative'] for r in rows],marker='o',label=p);ax[1].plot([r['pair'] for r in rows],[100*r['impulse_vector_max_relative'] for r in rows],marker='o',label=p)
 for q,title in zip(ax,['Peak-force convergence','Impulse convergence']):q.axhline(2,color='r',ls='--',label='2% gate');q.set_yscale('log');q.set_ylim(1e-5,4);q.set_ylabel('Maximum relative difference (%) — log scale');q.set_title(title);q.legend()
 fig.savefig(root/'figure_convergence_100m.png',dpi=180);plt.close(fig)
 print(json.dumps({'status':report['status'],'pairs':pairs}))
 if not gate:raise SystemExit(20)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);main(p.parse_args().root)
