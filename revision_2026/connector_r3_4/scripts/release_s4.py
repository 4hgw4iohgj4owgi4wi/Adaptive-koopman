from __future__ import annotations
import argparse,csv,hashlib,json,platform,subprocess,sys
from datetime import datetime
from pathlib import Path

def sha(p):
 h=hashlib.sha256();h.update(p.read_bytes());return h.hexdigest()
def dump(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def main():
 a=argparse.ArgumentParser();a.add_argument('--project-root',type=Path,required=True);x=a.parse_args();project=x.project_root.resolve();src=project/'revision_2026/connector_r3_4';res=project/'revision_2026/connector_r3_4_results';out=res/'s4_review';post=res/'r0_post_s4';out.mkdir(parents=True,exist_ok=True);post.mkdir(parents=True,exist_ok=True)
 frozen=json.loads((res/'r0/source_manifest_s2.json').read_text(encoding='utf-8')); actual={k:sha(src/k) if (src/k).exists() else None for k in frozen};drift=[{'path':k,'expected':v,'actual':actual[k]} for k,v in frozen.items() if actual[k]!=v]
 with (res/'n2a/oracle.csv').open(newline='',encoding='utf-8-sig') as f:oracle=list(csv.DictReader(f))
 with (res/'n2a/fixed_reference.csv').open(newline='',encoding='utf-8-sig') as f:fixed=list(csv.DictReader(f))
 checks=json.loads((res/'n2a/checks.json').read_text(encoding='utf-8'));complete=json.loads((res/'n2a/complete.json').read_text(encoding='utf-8'))
 recompute={'pairs':len(checks),'passed_pairs':sum(bool(r['passed']) for r in checks),'oracle_rows':len(oracle),'fixed_rows':len(fixed),'worst':{k:max(float(r[k]) for r in checks) for k in ('oracle_peak','oracle_impulse','oracle_terminal','ref_0p5_peak','ref_0p5_impulse','ref_0p5_terminal')},'max_event_residual_m':max(float(r['max_event_residual_m']) for r in oracle),'max_oracle_time_residual_s':max(float(r['time_conservation_residual_s']) for r in oracle),'max_fixed_time_residual_s':max(float(r['time_conservation_residual_s']) for r in fixed)}
 thresholds={'oracle_peak':0.0005,'oracle_impulse':0.0002,'oracle_terminal':0.0001,'ref_0p5_peak':0.005,'ref_0p5_impulse':0.002,'ref_0p5_terminal':0.001,'event_residual_m':1e-8,'time_residual_s':1e-12}
 data_ok=complete.get('passed') is True and recompute['pairs']==12 and recompute['passed_pairs']==12 and recompute['oracle_rows']==24 and recompute['fixed_rows']==48 and all(recompute['worst'][k]<=thresholds[k] for k in recompute['worst']) and recompute['max_event_residual_m']<=thresholds['event_residual_m'] and max(recompute['max_oracle_time_residual_s'],recompute['max_fixed_time_residual_s'])<=thresholds['time_residual_s']
 env=dict(PYTHONDONTWRITEBYTECODE='1');env.update({k:v for k,v in __import__('os').environ.items() if k!='PYTEST_ADDOPTS'});tests=subprocess.run([sys.executable,'-m','pytest',str(src/'tests'),'-q','-p','no:cacheprovider'],capture_output=True,text=True,env=env)
 test_ok=tests.returncode==0 and '18 passed' in tests.stdout
 source= (src/'scripts/run_n2a_v2.py').read_text(encoding='utf-8');threshold_ok=all(token in source for token in ("oracle_peak<=.0005","oracle_j<=.0002","oracle_state<=.0001","ref_peak<=.005","ref_j<=.002","ref_state<=.001"))
 provenance={'timestamp':datetime.now().astimezone().isoformat(),'host':platform.node(),'historical_protocol':{'path':str(src/'protocol.md'),'sha256':sha(src/'protocol.md')},'finish_protocol':{'path':str(src/'protocol_finish.md'),'sha256':sha(src/'protocol_finish.md')},'frozen_manifest_sha256':sha(res/'r0/source_manifest_s2.json'),'source_drift':drift,'s4_recompute':recompute,'thresholds':thresholds,'tests':{'returncode':tests.returncode,'stdout':tests.stdout,'stderr':tests.stderr}}
 dump(post/'provenance.json',provenance)
 approved=not drift and data_ok and test_ok and threshold_ok
 release={'stage':'C0','approved':approved,'passed':approved,'historical_evidence_not_retroactively_relabelled':True,'source_identity_passed':not drift,'s4_data_passed':data_ok,'tests_18_passed':test_ok,'threshold_source_passed':threshold_ok,'source_drift':drift,'recompute':recompute,'timestamp':datetime.now().astimezone().isoformat()};dump(out/'release.json',release);dump(out/'complete.json',release);print(json.dumps({'stage':'C0','approved':approved,'source_drift_count':len(drift),'s4_data_passed':data_ok,'tests_18_passed':test_ok,'threshold_source_passed':threshold_ok}));raise SystemExit(0 if approved else 2)
if __name__=='__main__':main()
