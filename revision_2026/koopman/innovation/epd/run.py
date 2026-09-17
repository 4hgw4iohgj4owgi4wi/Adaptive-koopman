from __future__ import annotations
import argparse,json,os,shutil,sys,time
from pathlib import Path
import numpy as np
from audit import sha,write_json,log,solution
from config import EPDConfig

def seed_collision(project:Path,candidates):
 seen=set()
 for p in (project/'revision_2026').rglob('manifest.json'):
  try:
   obj=json.loads(p.read_text(encoding='utf-8'))
   def walk(v):
    if isinstance(v,dict):
     for k,x in v.items():
      if k=='seed':
       try:seen.add(int(x))
       except:pass
      walk(x)
    elif isinstance(v,list):
     for x in v:walk(x)
   walk(obj)
  except (OSError,json.JSONDecodeError):pass
 audits=[];chosen=None
 for b in candidates:
  block=set(range(b,b+10000));hit=sorted(block&seen);audits.append({'base':b,'collision_count':len(hit),'first_collisions':hit[:20]})
  if chosen is None and not hit:chosen=b
 return chosen,audits,len(seen)

def ep0(c):
 stage=c.results/'ep0';complete=stage/'complete.json';protocol=c.code/'protocol.md'
 if complete.exists():return json.loads(complete.read_text())['passed']
 stage.mkdir(parents=True,exist_ok=True)
 required=[c.data/'freeze.json',c.data/'manifest.json',c.core_model,protocol]
 missing=[str(x) for x in required if not x.exists()]
 if missing:
  result={'passed':False,'missing':missing};write_json(stage/'historical_freeze_audit.json',result);write_json(complete,result);solution(c.results,'EP0身份失败',missing,'工程/身份失败',[],['修正只读路径'],['不得创建模型'],['补齐冻结artifact后重跑EP0']);return False
 chosen,audits,n=seed_collision(c.project,c.base_candidates);write_json(stage/'seed_audit.json',{'chosen_base':chosen,'audits':audits,'historical_seed_count':n})
 from registry import METHODS
 write_json(stage/'method_registry.json',METHODS);write_json(stage/'environment.json',{'python':sys.version,'numpy':np.__version__,'platform':sys.platform})
 hist={'files':{str(p):sha(p) for p in required},'old_tree_read_only':True,'development_read':False};write_json(stage/'historical_freeze_audit.json',hist);(stage/'protocol_sha256.txt').write_text(sha(protocol)+'\n');(stage/'code_map.md').write_text('# EPD code map\n\n新代码仅位于 `innovation/epd`；R1.3代码、模型和数据只读。\n',encoding='utf-8')
 passed=chosen is not None;write_json(complete,{'stage':'EP0','passed':passed,'base':chosen,'protocol_sha256':sha(protocol),'development_read':False});log(c.results,'EPD-0001','EP0冻结与身份审计',[f'协议={sha(protocol)}',f'BASE={chosen}',f'冻结核心={sha(c.core_model)}','development未读'])
 return passed

def ep1(c):
 if not ep0(c):return False
 stage=c.results/'ep1';complete=stage/'complete.json'
 if complete.exists():
  old=json.loads(complete.read_text())
  if old.get('oracle_contract_version')==2:return old['passed']
  if (stage/'selftest.json').exists():shutil.copy2(stage/'selftest.json',stage/'selftest_pre_precision_contract_fix.json')
  shutil.copy2(complete,stage/'complete_pre_precision_contract_fix.json')
 from data_adapter import rows
 from selftest import oracle
 rs=rows(c.data,('train',));result=oracle(c.project,rs);write_json(stage/'selftest.json',result);write_json(complete,{'stage':'EP1','passed':result['passed'],'oracle_contract_version':2,'development_read':False});log(c.results,'EPD-0002','EP1公式与接口oracle（精度合同拆分后）',[f'结果={result}','development未读'])
 if not result['passed']:solution(c.results,'EP1 oracle未通过',[f'{k}={v}' for k,v in result.items()],'公式或接口失败',['坐标、锚点参数或日志定义不一致'],['只修EPD适配器并以相同输入重跑'],['不得训练K2-K4'],['达到任务书全部oracle容差'])
 return result['passed']

def _g(core,w):
 from kinematic_decoder import decode
 d,v=decode(core,w['length'][:,None],w['width'][:,None]);return np.concatenate([d.reshape(len(d),20,8),v.reshape(len(v),20,8)],-1)
def _forces(geom,w):
 from axial_decoder import decode
 d=geom[...,:8].reshape(len(geom),20,4,2);v=geom[...,8:].reshape(len(geom),20,4,2);return decode(d,v,w['k'][:,None],w['c'][:,None],w['l0'][:,None])['force']

def ep2(c):
 if not ep1(c):return False
 stage=c.results/'ep2';complete=stage/'complete.json'
 if complete.exists():
  old=json.loads(complete.read_text())
  if old.get('adapter_contract_version')==2:return old['passed']
  if (stage/'diagnostic.json').exists():shutil.copy2(stage/'diagnostic.json',stage/'diagnostic_pre_double_normalization_fix.json')
  shutil.copy2(complete,stage/'complete_pre_double_normalization_fix.json')
 from data_adapter import rows,windows
 from core_adapter import norms,predict
 from metrics import scales,evaluate
 train=rows(c.data,('train',));val=rows(c.data,('validation',));norm=norms(c.project,train);w=windows(val);core46,k0f=predict(c.project,c.core_model,w,norm);core=core46[...,:30];k0g=core46[...,30:46];k1g=_g(core,w);k1f=_forces(k1g,w);s=scales(train);m0=evaluate(core,k0g,k0f.reshape(len(w['x0']),20,4,2),w,s);m1=evaluate(core,k1g,k1f,w,s);gains={k:(m0[k]-m1[k])/m0[k] for k in ('E_d','E_v','E_F','E_Q','J_pred')}
 # Read-only diagnosis of the old independent heads. It does not select EPD parameters.
 old=c.results.parent/'innovation_efd_r13_results'/'u7_geometry'/'models';diag={}
 for name in ('V-G1.npz','V-G2.npz'):
  p=old/name
  if p.exists():
   with np.load(p) as z:
    mats=[np.asarray(z[k]) for k in z.files if k.startswith('coef_h')];ranks=[int(np.linalg.matrix_rank(x)) for x in mats];conds=[float(np.linalg.cond(x)) for x in mats];diag[name]={'coefficient_ranks':ranks,'coefficient_condition_numbers':conds,'note':'coefficient spectrum only; old per-head design matrices were not persisted'}
 result={'K0':m0,'K1':m1,'gains_K1_vs_K0':gains,'old_head_read_only_diagnostic':diag,'validation_role':'post-hoc diagnostic only','development_read':False}
 signal=max(gains[k] for k in ('E_d','E_v','E_F','E_Q'))>=.10 and min(gains[k] for k in ('E_d','E_v','E_F','E_Q'))>=-.20
 result['necessary_signal_passed']=bool(signal);write_json(stage/'diagnostic.json',result);write_json(complete,{'stage':'EP2','passed':bool(signal),'adapter_contract_version':2,'development_read':False});log(c.results,'EPD-0003','EP2历史只读诊断与K1信号门（冻结输入合同修正后）',[f'K0={m0}',f'K1={m1}',f'gains={gains}',f'继续EP3={signal}','development未读'])
 if not signal:solution(c.results,'EP2 K1必要信号未通过',[f'K0={m0}',f'K1={m1}',f'gains={gains}'],'科学路线必要条件失败',['核心误差经物理几何传播后可能主导','活动切换可能放大微小几何误差'],['不得用validation调参；只能另立新协议'],['EPD训练不得启动'],['用新证据协议改变核心或路线，成本为重新冻结数据与验证集'])
 return bool(signal)

def blocked(c,stage):
 parent_ok=ep2(c);p=c.results/stage.lower();p.mkdir(parents=True,exist_ok=True);write_json(p/'complete.json',{'stage':stage,'passed':False,'executed':False,'blocked_by':None if parent_ok else 'EP2 necessary signal gate','development_read':False});return False
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',required=True,choices=[f'EP{i}' for i in range(10)]);ap.add_argument('--project-root',type=Path,default=Path(r'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'));a=ap.parse_args();c=EPDConfig(a.project_root.resolve());ok=ep0(c) if a.stage=='EP0' else ep1(c) if a.stage=='EP1' else ep2(c) if a.stage=='EP2' else blocked(c,a.stage);print(json.dumps({'stage':a.stage,'passed':ok,'results':str(c.results)},ensure_ascii=False));raise SystemExit(0 if ok else 2)
if __name__=='__main__':main()
