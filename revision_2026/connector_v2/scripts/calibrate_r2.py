from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
def main(project,out):
 data=project/'revision_2026'/'koopman'/'innovation_efd_r13_results'/'u4_data';rows=json.loads((data/'manifest.json').read_text())['completed'];num=den=0.;active=[];vnall=[]
 for row in rows:
  if row['split']!='train':continue
  with np.load(data/'train'/row['base_file'],allow_pickle=False) as z:
   meta=json.loads(str(z['metadata_json'].item()));c=float(meta['params']['connector']['damping_nspm']);l0=float(meta['params']['connector']['free_play_m']);d=np.asarray(z['connector_disp'],float);v=np.asarray(z['connector_vel'],float)
  length=np.linalg.norm(d,axis=-1);delta=np.maximum(length-l0,0);n=d/np.maximum(length[...,None],1e-12);vn=np.sum(n*v,axis=-1);mask=delta>0;num+=float(np.sum(c*np.maximum(vn,0)**2*mask));den+=float(np.sum(delta**1.5*vn**2*mask));active.append(delta[mask]);vnall.append(vn[mask])
 base=json.loads((project/'revision_2026'/'connector_v2_results'/'c0'/'parameter_freeze.json').read_text());base['hysteresis_damping_CH']=num/den;cal={'revision':'r2_energy_match','formula':'CH=sum(c*[vn]_+^2)/sum(delta^n*vn^2) on V1 train','target_dissipation_sum_without_dt':num,'unit_response_sum_without_dt':den,'CH':base['hysteresis_damping_CH'],'delta_quantiles_m':np.quantile(np.concatenate(active),[.5,.9,.95,.99,.999]).tolist(),'vn_abs_quantiles_mps':np.quantile(np.abs(np.concatenate(vnall)),[.5,.9,.95,.99,.999]).tolist(),'params':base,'development_read':False,'confirm_read':False};out.mkdir(parents=True,exist_ok=True);(out/'calibration.json').write_text(json.dumps(cal,indent=2));(out/'parameter_freeze.json').write_text(json.dumps(base,indent=2));print(json.dumps(cal))
if __name__=='__main__':main(Path(sys.argv[1]),Path(sys.argv[2]))
