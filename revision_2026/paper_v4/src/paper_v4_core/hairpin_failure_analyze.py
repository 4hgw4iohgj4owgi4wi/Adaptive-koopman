"""Compare preserved EXP-R1 hairpin hard-stop trajectories."""
import argparse,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .cli import save,sha

def load(path):
 with np.load(path/'raw.npz',allow_pickle=False) as z:a=z['values'];cols=[str(x) for x in z['columns']]
 return a,{n:k for k,n in enumerate(cols)},json.loads((path/'metrics.json').read_text())
def main(out,baseline,repair1,repair2):
 out=Path(out);out.mkdir(parents=True,exist_ok=False);runs=[('Feedforward, no common speed',Path(baseline)),('Speed + yaw feedback',Path(repair1)),('Common speed only',Path(repair2))];loaded=[];rows=[]
 for label,path in runs:
  a,i,m=load(path);t=a[:,i['time_s']];force=a[:,[i[f'payload_force_body_{j}'] for j in range(8)]].reshape(-1,4,2);norm=np.linalg.norm(force,axis=2);speed=a[:,i['x27']];href=a[:,i['reference_heading_rad']];yawerr=(a[:,i['x26']]-href+np.pi)%(2*np.pi)-np.pi
  loaded.append((label,a,i,t,norm,speed,yawerr));rows.append({'label':label,'source':str(path),'status':m['status'],'reason':m['reason'],'actual_integrated_duration_s':m['integrated_duration_s'],'reference_distance_m':m['reference_distance_m'],'maximum_point_force_n':float(norm.max()),'maximum_lateral_opening_proxy_n':float(a[:,i['tension_y_n']].max()),'maximum_payload_speed_error_mps':float(np.max(abs(2-speed))),'maximum_payload_heading_error_deg':float(np.rad2deg(np.max(abs(yawerr)))),'requested_steering_saturation_count':m.get('requested_steering_saturation_count'),'maximum_tire_raw_utilization':m['maximum_tire_raw_utilization'],'raw_terminal_time_matches_integrated':abs(float(t[-1])-float(m['integrated_duration_s']))<=1e-10})
 fig,axs=plt.subplots(4,3,figsize=(15,11),sharex='col',constrained_layout=True)
 for col,(label,a,i,t,norm,speed,yawerr) in enumerate(loaded):
  for j in range(4):axs[0,col].plot(t,norm[:,j],label=f'Point {j+1}')
  axs[0,col].axhline(15000,color='r',ls='--',label='15 kN stop');axs[0,col].set_title(label);axs[0,col].set_ylabel('Force norm (N)');axs[0,col].legend(fontsize=7,ncol=2)
  axs[1,col].plot(t,speed,label='Payload body vx');axs[1,col].axhline(2,color='k',ls=':',label='Reference');axs[1,col].set_ylabel('Speed (m/s)');axs[1,col].legend(fontsize=7)
  axs[2,col].plot(t,np.rad2deg(yawerr));axs[2,col].set_ylabel('Payload heading error (deg)')
  axs[3,col].plot(t,a[:,i['tension_x_n']],label='Longitudinal');axs[3,col].plot(t,a[:,i['tension_y_n']],label='Lateral');axs[3,col].set_ylabel('Opening proxy (N)');axs[3,col].set_xlabel('Time (s)');axs[3,col].legend(fontsize=7)
 fig.suptitle('EXP-R1 E01 true-hairpin hard stops — preserved failures')
 fig.savefig(out/'hairpin_failures.png',dpi=180);plt.close(fig)
 save(out,'failure_comparison.json',{'status':'FAIL','gate':'E01 true hairpin','claim':'All three input wrappers hit the unchanged 15 kN ultimate-force stop; no numerical or controller ranking claim.','runs':rows,'source_sha':sha(__file__)})
 print(json.dumps(rows))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--baseline',required=True);p.add_argument('--repair1',required=True);p.add_argument('--repair2',required=True);z=p.parse_args();main(z.out,z.baseline,z.repair1,z.repair2)
