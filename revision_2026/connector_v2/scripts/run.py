from __future__ import annotations
import argparse,hashlib,json,platform,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def write(p,v):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
def log(res,rid,title,lines):
 p=res/'work_log.md';p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('a',encoding='utf-8') as f:f.write(f'\n## {rid} {title}\n\n- 时间：{datetime.now(timezone.utc).astimezone().isoformat()}\n'+''.join(f'- {x}\n' for x in lines))
def c0(project,res):
 stage=res/'c0';complete=stage/'complete.json'
 if complete.exists():return json.loads(complete.read_text())['passed']
 oldplant=project/'revision_2026'/'model'/'four_vehicle_coupled.py';data=project/'revision_2026'/'koopman'/'innovation_efd_r13_results'/'u4_data';manifest=data/'manifest.json';protocol=ROOT/'protocol.md';missing=[str(p) for p in (oldplant,manifest,protocol) if not p.exists()]
 if missing:write(complete,{'passed':False,'missing':missing});return False
 m=json.loads(manifest.read_text(encoding='utf-8'));rows=m['completed'];active=[];positive_v=[]
 for row in rows:
  if row['split']!='train':continue
  with np.load(data/'train'/row['base_file'],allow_pickle=False) as z:
   meta=json.loads(str(z['metadata_json'].item()));l0=float(meta['params']['connector']['free_play_m']);d=np.asarray(z['connector_disp'],float);v=np.asarray(z['connector_vel'],float)
  r=np.linalg.norm(d,axis=-1);pen=np.maximum(r-l0,0.);n=d/np.maximum(r[...,None],1e-12);vn=np.sum(n*v,axis=-1);active.append(pen[pen>0]);positive_v.append(vn[(pen>0)&(vn>0)])
 active=np.concatenate(active);positive_v=np.concatenate(positive_v);dref=float(np.median(active));nexp=1.5;k1=30000.;c1=3500.;K=k1*dref**(1-nexp);CH=c1/dref**nexp;rated=12000.;ultimate=15000.;dwork=(rated/K)**(1/nexp);dfail=(ultimate/K)**(1/nexp)
 params={'law_version':'plant_v2_hc_smooth','contact_exponent_n':nexp,'contact_stiffness_K':K,'hysteresis_damping_CH':CH,'free_play_m':.002,'maximum_working_displacement_m':dwork,'failure_displacement_m':dfail,'rated_force_n':rated,'ultimate_force_n':ultimate,'force_cap_enabled':True}
 freeze={'passed':True,'protocol_sha256':sha(protocol),'v1_plant':{'name':'plant_v1_linear_gated','path':str(oldplant),'sha256':sha(oldplant)},'v1_data':{'path':str(data),'manifest_sha256':sha(manifest),'completed_rows':len(rows),'boundary':'read-only baseline only'},'mpc_boundary':'all pre-V2 MPC is plant_v1_linear_gated and excluded from V2 claims','physical_assumptions':{'status':'modeling assumptions, not measured facts','type':'2D radial pin-bushing numerical equivalent','preload':False,'tangential_friction':False,'relative_yaw_free':True,'force_components':'planar payload-frame x/y, not gravity z','measured_curve_available':False},'parameter_identification':{'mode':'numerical equivalent; no physical calibration','n_assumption':1.5,'active_penetration_samples':len(active),'delta_ref_median_m':dref,'match':'V1 secant elastic force and local damping coefficient at delta_ref','positive_contact_speed_median':float(np.median(positive_v))},'v2_nominal_params':params,'development_read':False,'confirm_read':False}
 write(stage/'c0_freeze.json',freeze);write(stage/'parameter_freeze.json',params);write(stage/'environment.json',{'python':sys.version,'numpy':np.__version__,'platform':platform.platform()});write(complete,{'stage':'C0','passed':True,'development_read':False,'confirm_read':False});log(res,'CV2-0001','C0冻结与版本隔离',[f'V1 plant hash={sha(oldplant)}',f'V1 rows={len(rows)}',f'delta_ref={dref}',f'K={K}, CH={CH}, n={nexp}','无实测参数，仅数值等效','development/confirm未读']);return True
def c1(project,res):
 if not c0(project,res):return False
 stage=res/'c1';complete=stage/'complete.json'
 if complete.exists():return json.loads(complete.read_text())['passed']
 import subprocess
 params=res/'c0'/'parameter_freeze.json';out=stage/'g1_results.json';cmd=[sys.executable,str(ROOT/'tests'/'test_g1.py'),str(params),str(out)];run=subprocess.run(cmd,capture_output=True,text=True);result=json.loads(out.read_text()) if out.exists() else {'passed':False,'stderr':run.stderr};write(stage/'source_manifest.json',{str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*.py')});write(complete,{'stage':'C1/G1','passed':bool(result['passed']),'returncode':run.returncode,'development_read':False,'confirm_read':False});log(res,'CV2-0002','C1唯一V2实现与G1',[f'command={cmd}',f'result={result}','development/confirm未读']);return bool(result['passed'])
def c2(project,res):
 if not c1(project,res):return False
 stage=res/'c2';complete=stage/'complete.json'
 if complete.exists():
  old=json.loads(complete.read_text())
  if old.get('serialization_fix_version')==1:return old['passed']
  import shutil
  shutil.copy2(complete,stage/'complete_pre_bool_serialization_fix.json')
 import subprocess
 params=res/'c0'/'parameter_freeze.json';out=stage/'dynamics';cmd=[sys.executable,str(ROOT/'tests'/'test_g2.py'),str(params),str(out)];run=subprocess.run(cmd,capture_output=True,text=True);result=json.loads((out/'g2_results.json').read_text()) if (out/'g2_results.json').exists() else {'passed':False,'stderr':run.stderr};write(complete,{'stage':'C2/G2','passed':bool(result['passed']),'returncode':run.returncode,'serialization_fix_version':1,'development_read':False,'confirm_read':False});log(res,'CV2-0003','C2单连接器动力学与G2（序列化修正后）',[f'command={cmd}',f'result={result}','development/confirm未读']);return bool(result['passed'])
def c3(project,res):
 if not c2(project,res):return False
 stage=res/'c3';complete=stage/'complete.json'
 if complete.exists():return json.loads(complete.read_text())['passed']
 import subprocess
 params=res/'c0'/'parameter_freeze.json';out=stage/'convergence';cmd=[sys.executable,str(ROOT/'tests'/'test_g3.py'),str(params),str(out)];run=subprocess.run(cmd,capture_output=True,text=True);result=json.loads((out/'g3_results.json').read_text()) if (out/'g3_results.json').exists() else {'passed':False,'stderr':run.stderr};write(stage/'source_manifest.json',{str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*.py')});write(complete,{'stage':'C3/G3','passed':bool(result['passed']),'returncode':run.returncode,'development_read':False,'confirm_read':False});log(res,'CV2-0004','C3四车V2集成与步长收敛',[f'command={cmd}',f'result={result}','development/confirm未读']);return bool(result['passed'])
def c4(project,res):
 if not c3(project,res):return False
 stage=res/'c4';complete=stage/'complete.json'
 if complete.exists():
  old=json.loads(complete.read_text())
  if old.get('summary_length_fix_version')==1:return old['passed']
  import shutil
  shutil.copy2(complete,stage/'complete_pre_summary_length_fix.json')
 import subprocess
 params=res/'c0'/'parameter_freeze.json';out=stage/'paired';cmd=[sys.executable,str(ROOT/'tests'/'test_c4.py'),str(project),str(params),str(out)];run=subprocess.run(cmd,capture_output=True,text=True);result=json.loads((out/'c4_results.json').read_text()) if (out/'c4_results.json').exists() else {'passed':False,'stderr':run.stderr};write(complete,{'stage':'C4/G4/G5','passed':bool(result['passed']),'returncode':run.returncode,'summary_length_fix_version':1,'development_read':False,'confirm_read':False});log(res,'CV2-0005','C4成对100m/单移线/回头弯（汇总长度修正后）',[f'command={cmd}',f'result={result}','development/confirm未读']);return bool(result['passed'])
def blocked(res,stage,by):write(res/stage.lower()/'complete.json',{'stage':stage,'passed':False,'executed':False,'blocked_by':by,'development_read':False,'confirm_read':False});return False
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--project-root',type=Path,required=True);ap.add_argument('--stage',required=True);a=ap.parse_args();project=a.project_root.resolve();res=project/'revision_2026'/'connector_v2_results';ok=c0(project,res) if a.stage=='C0' else c1(project,res) if a.stage=='C1' else c2(project,res) if a.stage=='C2' else c3(project,res) if a.stage=='C3' else c4(project,res) if a.stage=='C4' else blocked(res,a.stage,'C4/G4/G5 not yet passed');print(json.dumps({'stage':a.stage,'passed':ok,'results':str(res)},ensure_ascii=False));raise SystemExit(0 if ok else 2)
if __name__=='__main__':main()
