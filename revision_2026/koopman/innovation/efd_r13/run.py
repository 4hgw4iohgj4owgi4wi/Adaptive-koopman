from __future__ import annotations
import argparse,json,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
from typing import Any
import audit
from config import EFDR13Config,seed_block
HERE=Path(__file__).resolve().parent

def write_json(path:Path,value:Any)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
def log(cfg:EFDR13Config,n:str,title:str,rows:list[str])->None:
 p=cfg.results/"work_log.md";p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():p.write_text("# EFD-R1.3工作记录\n",encoding="utf-8")
 with p.open("a",encoding="utf-8") as h:h.write(f"\n## {n} {title}\n\n- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"+"\n".join(f"- {x}" for x in rows)+"\n")
def solution(cfg:EFDR13Config,title:str,facts:list[str],actions:list[str],impact:str,recovery:str)->None:
 p=cfg.results/"solutions.md";p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():p.write_text("# EFD-R1.3问题与处置\n",encoding="utf-8")
 with p.open("a",encoding="utf-8") as h:h.write(f"\n## {title}\n\n### 已核实事实\n\n"+"\n".join(f"- {x}" for x in facts)+"\n\n### 允许修复与成本\n\n"+"\n".join(f"- {x}" for x in actions)+f"\n\n### 论文影响\n\n{impact}\n\n### 恢复条件\n\n{recovery}\n")

def u0(cfg:EFDR13Config)->bool:
 stage=cfg.results/"u0_freeze";protocol=HERE/"protocol.md";actual=audit.sha256(protocol)
 if actual!=cfg.protocol_sha256:write_json(stage/"complete.json",{"stage":"U0","passed":False,"expected":cfg.protocol_sha256,"actual":actual});return False
 from method_registry import build
 registry=build(cfg.project_root);write_json(stage/"method_registry.json",registry)
 audits={};selected=None
 for base in cfg.base_candidates:
  x=audit.seed_collisions(cfg.project_root/"revision_2026",sum(seed_block(base).values(),[]));audits[str(base)]=x
  if x["passed"]:selected=base;break
 write_json(stage/"seed_audit.json",{"candidates":audits,"selected_base":selected})
 roots={"efd_r1":cfg.koopman/"innovation"/"efd_r1","efd_r11":cfg.koopman/"innovation"/"efd_r11","efd_r12":cfg.koopman/"innovation"/"efd_r12","compare":cfg.koopman/"compare","irsp":cfg.project_root/"revision_2026"/"03_irsp"}
 write_json(stage/"history_hashes.json",{k:audit.hash_tree(v,{"__pycache__"}) for k,v in roots.items()});write_json(stage/"environment.json",audit.environment())
 passed=bool(registry["passed"] and selected is not None);result={"stage":"U0","passed":passed,"selected_base":selected,"protocol_sha256":actual,"registry_checks":registry["checks"]};write_json(stage/"complete.json",result);log(cfg,"R13001","U0协议、seed、历史树与唯一方法注册表冻结",[f"结果={result}",f"seed审计={audits}","链A/B artifact与shape分离，V-SB92-U8明确is_irsp=false"]);return passed

def u1(cfg:EFDR13Config)->bool:
 if not u0(cfg):return False
 stage=cfg.results/"u1_article_irsp";complete=stage/"complete.json"
 if complete.exists():return bool(json.loads(complete.read_text(encoding="utf-8"))["audit_completed"])
 from article_irsp_adapter import reproduce
 from article_irsp_audit import run as assess
 rep_path=stage/"reproduction.json";rep=json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else reproduce(cfg.project_root)
 if not rep_path.exists():write_json(rep_path,rep)
 result=assess(cfg.project_root,rep);write_json(stage/"audit.json",result);write_json(complete,{"stage":"U1",**result})
 log(cfg,"R13002","U1原论文31维/2输入bilinear与IRSP只读复现",[f"复现={rep}",f"分层审计={result}","scientific_claim_passed=false不阻断链B"])
 if result["audit_completed"] and not result["scientific_claim_passed"]:solution(cfg,"U1原IRSP连续证书科学门失败",[f"sampled_radius_passed={result['sampled_radius_passed']}",f"continuous_norm_passed={result['continuous_norm_passed']}",f"continuous={result['continuous']}","历史artifact已逐元素复现，故这是科学结论失败而非工程失败"],["不在R1.3重选半径或gamma；保留冻结负结果，论文删除连续域证书和对完整ISS/UUB的直接支撑"],"IRSP只能表述为采样控制集上的谱半径正则化；后续根据noIRSP收益决定是否从标题、摘要和贡献删除。","链A audit_completed=true即可继续U2；若要恢复连续证书必须另立新协议。")
 return bool(result["audit_completed"])

def u2(cfg:EFDR13Config)->bool:
 if not u1(cfg):return False
 stage=cfg.results/"u2_vehicle_adapter";complete=stage/"complete.json"
 if complete.exists():return bool(json.loads(complete.read_text(encoding="utf-8"))["passed"])
 from vehicle_adapter import run as regress
 result=regress(cfg.project_root);write_json(stage/"tests.json",result);write_json(complete,{"stage":"U2","passed":result["passed"],"tests_sha256":audit.sha256(stage/"tests.json")});log(cfg,"R13003","U2四车历史ARX/FL/FB/SB/H2真实回归",[f"结果={result}",f"结论={'通过，允许U3' if result['passed'] else '停止，不生成pilot'}"])
 if not result["passed"]:solution(cfg,"U2历史四车方法回归失败",[json.dumps(result,ensure_ascii=False)],["只允许修dtype、normalizer、cache路径和历史调用接口；不允许重训或用代理模型替换"],"U2通过前不能将链B方法用于论文公平比较。","全部五个ID在冻结历史结果上误差<=1e-10。")
 return bool(result["passed"])

def u3(cfg:EFDR13Config,workers:int)->bool:
 if not u2(cfg):return False
 from pilot import generate_one
 from pilot_r11 import analytic_oracle,jobs
 from integrator_equivariance import local_audit,long_audit
 import schema
 base=int(json.loads((cfg.results/"u0_freeze"/"complete.json").read_text(encoding="utf-8"))["selected_base"]);stage=cfg.results/"u3_pilot";complete=stage/"complete.json"
 if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("passed"):return True
 traj=stage/"trajectories";traj.mkdir(parents=True,exist_ok=True);planned=jobs(base);write_json(stage/"freeze.json",{"jobs":planned,"analytic_max":1e-12,"local":{"04_p95":1e-5,"04_max":1e-4,"pass_count":11},"oracle_N":2e-3,"physical_scales":schema.contract()["physical_scales"],"protocol_sha256":cfg.protocol_sha256})
 done=[];failures=[];tic=time.perf_counter()
 with ProcessPoolExecutor(max_workers=workers) as pool:
  fs={pool.submit(generate_one,str(cfg.project_root),j,str(traj)):j for j in planned}
  for i,f in enumerate(as_completed(fs),1):
   try:done.append(f.result())
   except Exception as e:failures.append({"job":fs[f],"error":repr(e)})
   print(f"U3 generate {i}/24 failures={len(failures)}",flush=True)
 done.sort(key=lambda x:x["seed"]);write_json(stage/"manifest.json",{"completed":done,"failures":failures});analytic=[];local=[];long=[]
 if len(done)==24 and not failures:
  with ProcessPoolExecutor(max_workers=workers) as pool:
   fs={pool.submit(analytic_oracle,str(cfg.project_root),x,str(traj)):x for x in done}
   for f in as_completed(fs):
    try:analytic.append(f.result())
    except Exception as e:failures.append({"job":fs[f],"analytic_error":repr(e)})
  with ProcessPoolExecutor(max_workers=workers) as pool:
   fs={pool.submit(local_audit,str(cfg.project_root),str(traj/x["base_file"])):x for x in done if x["local_mirror"]}
   for f in as_completed(fs):
    try:local.append(f.result())
    except Exception as e:failures.append({"job":fs[f],"local_error":repr(e)})
  curves=stage/"long_horizon_diagnostic";curves.mkdir(parents=True,exist_ok=True)
  with ProcessPoolExecutor(max_workers=workers) as pool:
   fs={pool.submit(long_audit,str(cfg.project_root),str(traj/x["base_file"]),str(curves/f"curve_{x['seed']}.npz")):x for x in done if x["long_diagnostic"]}
   for f in as_completed(fs):
    try:long.append(f.result())
    except Exception as e:failures.append({"job":fs[f],"long_error":repr(e)})
 analytic.sort(key=lambda x:x["seed"]);local.sort(key=lambda x:x["seed"]);long.sort(key=lambda x:x["seed"]);write_json(stage/"analytic_oracle.json",analytic);write_json(stage/"local_equivariance.json",local);write_json(stage/"long_diagnostic.json",long)
 finite=not failures and len(done)==24 and all(x["finite"] and x["ultimate_steps"]==0 for x in done);lp=sum(x["passed"] for x in local);lb=any(x["blocking"] for x in long);passed=finite and len(analytic)==24 and all(x["passed"] for x in analytic) and len(local)==12 and lp>=11 and len(long)==8 and not lb
 result={"stage":"U3","passed":passed,"base_trajectories":len(done),"analytic_mirrors":len(done),"local_pass_count":lp,"local_total":len(local),"long_diagnostics":len(long),"long_blocking":lb,"failures":failures,"finite_ultimate_gate":finite,"oracle_max_N":max((x["oracle_max_N"] for x in analytic),default=None),"local_worst_04_p95":max((x["checkpoints"]["0.4"]["overall"]["p95_max"] for x in local),default=None),"local_worst_04_max":max((x["checkpoints"]["0.4"]["overall"]["max"] for x in local),default=None),"wall_time_s":time.perf_counter()-tic,"workers":workers,"bytes":sum(x.get("bytes",0) for x in done)};write_json(complete,result);log(cfg,"R13004","U3新pilot与局部物理合同",[f"结果={result}",f"结论={'通过，允许U4' if passed else '停止U4'}"])
 if not passed:solution(cfg,"U3 pilot/局部物理门失败",[json.dumps(result,ensure_ascii=False)],["只允许同seed断点、接口或worker工程修复；不放宽物理门"],"链B正式数据不得生成。","24/24有限、解析/oracle通过、局部至少11/12且长时无阻断。")
 return passed

def u4(cfg:EFDR13Config,workers:int)->bool:
 if not u3(cfg,workers):return False
 from formal_data import coverage,jobs
 from pilot import generate_one
 base=int(json.loads((cfg.results/"u0_freeze"/"complete.json").read_text(encoding="utf-8"))["selected_base"]);stage=cfg.results/"u4_data";complete=stage/"complete.json";planned=jobs(base)
 if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("passed"):return True
 write_json(stage/"freeze.json",{"jobs":planned,"base_family_is_statistical_unit":True,"analytic_mirror_adds_n":False,"development_locked":True,"protocol_sha256":cfg.protocol_sha256,"active_force_floor_N":10.,"high_load_floor_N":500.})
 roots={s:stage/s for s in ("train","validation","development")}
 for p in roots.values():p.mkdir(parents=True,exist_ok=True)
 done=[];failures=[];tic=time.perf_counter()
 with ProcessPoolExecutor(max_workers=workers) as pool:
  fs={pool.submit(generate_one,str(cfg.project_root),j,str(roots[j["split"]])):j for j in planned}
  for f in as_completed(fs):
   try:done.append(f.result())
   except Exception as e:failures.append({"job":fs[f],"error":repr(e)})
   if (len(done)+len(failures))%25==0:write_json(stage/"progress.json",{"completed":len(done),"failures":failures});print(f"U4 data {len(done)}/416 failures={len(failures)}",flush=True)
 done.sort(key=lambda x:x["seed"]);write_json(stage/"manifest.json",{"completed":done,"failures":failures});finite=not failures and len(done)==416 and all(x["finite"] and x["ultimate_steps"]==0 for x in done);cov=coverage(done,roots) if finite else {"passed":False};write_json(stage/"coverage.json",cov);passed=finite and bool(cov["passed"])
 result={"stage":"U4","passed":passed,"base_families":len(done),"analytic_mirrors":len(done),"failures":failures,"finite_ultimate_gate":finite,"coverage":cov,"wall_time_s":time.perf_counter()-tic,"workers":workers,"bytes":sum(x.get("bytes",0) for x in done),"development_generated":True,"development_model_read":False,"development_locked":True};write_json(complete,result);log(cfg,"R13005","U4正式train/validation/development生成与锁定",[f"结果={result}",f"结论={'通过，允许U5' if passed else '停止U5'}"])
 if not passed:solution(cfg,"U4数据或覆盖门失败",[json.dumps(result,ensure_ascii=False)],["只允许同seed断点、降worker或预注册覆盖补表；不替换失败轨迹"],"U5不得训练。","416个base有限且全部覆盖门通过。")
 return passed

def u5(cfg:EFDR13Config)->bool:
 if not u4(cfg,8):return False
 stage=cfg.results/"u5_vehicle_fair";complete=stage/"complete.json"
 if complete.exists():return bool(json.loads(complete.read_text(encoding="utf-8"))["audit_completed"])
 from fair_vehicle_baselines import train
 base=int(json.loads((cfg.results/"u0_freeze"/"complete.json").read_text(encoding="utf-8"))["selected_base"]);result=train(cfg.project_root,cfg.results/"u4_data",stage,cfg.ridge_grid,seed_block(base)["bootstrap"]);write_json(stage/"results.json",result);write_json(complete,{"stage":"U5","audit_completed":result["audit_completed"],"scientific_claim_passed":any(x["passed"] for x in result["bilinear_gates"].values()),"development_read":False});log(cfg,"R13006","U5链B公平重训与bilinear机制",[f"结果={result}","bilinear失败只删除相应主张，不阻断U6"]);return bool(result["audit_completed"])

def u6(cfg:EFDR13Config)->bool:
 if not u5(cfg):return False
 stage=cfg.results/"u6_physical_lift";complete=stage/"complete.json"
 if complete.exists():return bool(json.loads(complete.read_text(encoding="utf-8"))["audit_completed"])
 from physical_lift import train
 base=int(json.loads((cfg.results/"u0_freeze"/"complete.json").read_text(encoding="utf-8"))["selected_base"]);result=train(cfg.project_root,cfg.results/"u4_data",stage,cfg.ridge_grid,seed_block(base)["bootstrap"],0.);write_json(stage/"results.json",result);write_json(complete,{"stage":"U6","audit_completed":True,"scientific_claim_passed":not result["all_failed"],"fallback_core":result["fallback_core"],"development_read":False});log(cfg,"R13007","U6 P0-P4物理lift",[f"结果={result}",f"核心={'回退'+result['fallback_core'] if result['all_failed'] else '选择最小通过P组'}"]);return True

def u7(cfg:EFDR13Config)->bool:
 if not u6(cfg):return False
 stage=cfg.results/"u7_geometry";complete=stage/"complete.json"
 if complete.exists():
  prior=json.loads(complete.read_text(encoding="utf-8"))
  if prior.get("output_normalizer_fix") is True:return bool(prior["M_full_gate_passed"])
  # Preserve invalid pre-fix evidence instead of silently replacing it.
  import shutil
  if (stage/"results.json").exists():shutil.copy2(stage/"results.json",stage/"results_pre_output_normalizer_fix.json")
  shutil.copy2(complete,stage/"complete_pre_output_normalizer_fix.json")
 from geometry_validation import run
 base=int(json.loads((cfg.results/"u0_freeze"/"complete.json").read_text(encoding="utf-8"))["selected_base"]);result=run(cfg.project_root,cfg.results/"u4_data",cfg.results/"u5_vehicle_fair",stage,seed_block(base)["bootstrap"]);write_json(stage/"results.json",result);write_json(complete,{"stage":"U7","audit_completed":True,"M_point_gate_passed":result["M_point_gate_passed"],"M_full_gate_passed":result["M_full_gate_passed"],"development_read":False,"output_normalizer_fix":True});log(cfg,"R13008","U7 G0/G1/G2/M validation（输出归一化修正后重跑）",[f"结果={result}",f"结论={'允许U8' if result['M_full_gate_passed'] else '停止development'}"])
 if not result["M_full_gate_passed"]:solution(cfg,"U7 V-M未通过完整validation门",[json.dumps(result,ensure_ascii=False,default=str)],["只允许修确定性指标/接口错误；不得读取development后回调validation"],"V-M不能作为论文主候选，停止U8，不生成confirm。","另立新协议解决已明确的几何/速度/force或统计缺口。")
 return bool(result["M_full_gate_passed"])

def blocked(cfg:EFDR13Config,stage:str)->bool:
 if not u7(cfg):write_json(cfg.results/stage/"complete.json",{"stage":stage.upper(),"passed":False,"blocked_by":"U7 M validation gate","executed":False});return False
 raise NotImplementedError(f"{stage} implementation pending after U1")
def main()->None:
 p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--stage",choices=tuple(f"u{i}" for i in range(11)),required=True);p.add_argument("--workers",type=int,default=8);a=p.parse_args();cfg=EFDR13Config(a.project_root.resolve());ok=u0(cfg) if a.stage=="u0" else u1(cfg) if a.stage=="u1" else u2(cfg) if a.stage=="u2" else u3(cfg,a.workers) if a.stage=="u3" else u4(cfg,a.workers) if a.stage=="u4" else u5(cfg) if a.stage=="u5" else u6(cfg) if a.stage=="u6" else u7(cfg) if a.stage=="u7" else blocked(cfg,a.stage);print(json.dumps({"stage":a.stage,"passed":ok,"results":str(cfg.results)},ensure_ascii=False),flush=True);raise SystemExit(0 if ok else 2)
if __name__=="__main__":main()
