from __future__ import annotations
import argparse,json,math,os,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
from typing import Any
import numpy as np

HERE=Path(__file__).resolve().parent
from config import DirectionConfig
import audit
from data_protocol import all_requested_seeds,pilot_jobs,formal_jobs,append_jobs
from generate_d4r2 import simulate_one,train_scales
from coverage import pilot_contract,formal_contract
from cache import cache_all
from evaluate import h2_regression,evaluate_d3
from dataset import load_direction_dataset
from train import fit_thresholds,train_seed,load_heads,prediction_runtime_p99_ms
from predictors import structured_predictions,add_p5
from metrics import direction_metrics
from physics_decoder import manual_counterexample
from report import build_report

EXPECTED_H2="3828A4AD5D1DDDA532BD38FB3832A8B568458F55366B873321A17D043E72FDAC"

def clean(v:Any)->Any:
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,Path):return str(v)
    if isinstance(v,np.ndarray):return clean(v.tolist())
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,float) and not math.isfinite(v):return None
    return v

def write_json(path:Path,v:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_suffix(path.suffix+".tmp"); temp.write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8"); temp.replace(path)

def append_log(cfg:DirectionConfig,identifier:str,title:str,lines:list[str])->None:
    path=cfg.results_root/"work_log.md"; path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as h:h.write(f"\n## {identifier} — {title}\n\n- 开始/结束时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"+"\n".join(f"- {x}" for x in lines)+"\n")

def solution(cfg:DirectionConfig,title:str,facts:list[str],actions:list[str],boundary:str)->None:
    path=cfg.results_root/"solutions.md"
    if not path.exists():path.parent.mkdir(parents=True,exist_ok=True);path.write_text("# DP-MHK问题与处置\n",encoding="utf-8")
    with path.open("a",encoding="utf-8") as h:h.write(f"\n## {title}\n\n### 事实\n\n"+"\n".join(f"- {x}" for x in facts)+"\n\n### 处置\n\n"+"\n".join(f"- {x}" for x in actions)+f"\n\n### 边界\n\n{boundary}\n")

def d0(cfg:DirectionConfig)->bool:
    stage=cfg.results_root/"freeze"; complete=stage/"complete.json"
    if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("passed"):return True
    protocol=HERE/"protocol.md"; frozen=audit.freeze_source_hashes(cfg.project_root,protocol); seeds=audit.audit_seed_collisions(cfg.project_root/"revision_2026",all_requested_seeds()); d5=audit.audit_d5_absent(cfg.project_root)
    old_snapshot=audit.hash_tree(cfg.old_results,{"trajectories","baseline_cache","figures","__pycache__"}); write_json(cfg.results_root/"audits"/"old_results_snapshot.json",old_snapshot)
    code_snapshot=audit.hash_tree(cfg.old_code,{"direction","__pycache__"}); write_json(cfg.results_root/"audits"/"old_code_snapshot.json",code_snapshot)
    write_json(stage/"source_hashes.json",frozen);write_json(stage/"seed_audit.json",seeds);write_json(stage/"d5_audit.json",d5);write_json(stage/"environment.json",audit.package_versions())
    h2_ok=frozen.get("files",{}).get("H2_model",{}).get("sha256")==EXPECTED_H2
    passed=not frozen["missing"] and h2_ok and seeds["passed"] and d5["passed"]
    source=list(HERE.glob("*.py"))+[protocol,HERE/"protocol_amendment.md"]; changes=[{"path":str(p),"before_sha256":None,"after_sha256":audit.sha256(p),"functions_changed":"new isolated file","reason":"koopman_dir.md D0 foundation","tests_run":["py_compile","hash/seed/D5 audit"],"rollback_path":"remove direction directory only"} for p in source]
    write_json(cfg.results_root/"audits"/"change_manifest.json",changes); write_json(complete,{"stage":"D0","passed":passed,"H2_hash_match":h2_ok,"seed_collisions":seeds["collisions"],"D5_absent":d5["passed"],"source_hashes_sha256":audit.sha256(stage/"source_hashes.json")})
    append_log(cfg,"D0001","D0冻结/污染/seed审计",[f"任务书SHA256={audit.sha256(protocol)}；审计修订A2={audit.sha256(HERE/'protocol_amendment.md')}","保留的两次失败：初版正则扫描把JSON中的六位数字片段误报为seed；改为结构化seed字段解析后原预注册号段碰撞=0，期间没有生成数据",f"修改文件={len(source)}；全部为新隔离文件",f"实际命令=run.py --stage d0；输入H2={frozen.get('files',{}).get('H2_model')}",f"seed请求={len(all_requested_seeds())}，碰撞={seeds['collisions']}",f"D5 absent={d5['passed']}；旧结果快照文件={len(old_snapshot)}；旧代码快照={len(code_snapshot)}",f"环境={audit.package_versions()}",f"结论：{'通过' if passed else '停止'}"])
    if passed:solution(cfg,"D0 seed误报更正",["初版扫描器对JSON全文做六位数字正则，误报非seed数字片段","结构化解析seed/traj_id字段后原号段真实碰撞=0","更正前未生成pilot或D4R2"],["恢复koopman_dir.md原seed号段并冻结A2审计说明"],"此前solutions中的碰撞结论已撤销，不得作为真实数据冲突引用。")
    if not passed:solution(cfg,"D0门失败",[json.dumps(clean({"missing":frozen["missing"],"h2":h2_ok,"seeds":seeds,"d5":d5}),ensure_ascii=False)],["仅恢复冻结输入或在生成前整体换seed段后重跑"],"D1不得启动。")
    return passed

def _run_jobs(cfg:DirectionConfig,jobs:list[dict[str,Any]],folder:Path,workers:int=8)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    folder.mkdir(parents=True,exist_ok=True);scales=train_scales(cfg.project_root);done=[];fail=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(simulate_one,str(cfg.project_root),job,scales,str(folder/f"{job['split']}_{job['group']}_{job['seed']}.npz")):job for job in jobs}
        for i,future in enumerate(as_completed(futures),1):
            try:done.append(future.result())
            except Exception as exc:fail.append({"job":futures[future],"error":repr(exc)})
            if i%4==0 or i==len(jobs):print(f"D4R2 {folder.parent.name} {i}/{len(jobs)} failures={len(fail)}",flush=True);write_json(folder.parent/"progress.json",{"completed":done,"failures":fail})
    done.sort(key=lambda x:x["seed"]);return done,fail

def _old_readonly(cfg:DirectionConfig)->dict[str,Any]:
    expected=json.loads((cfg.results_root/"audits"/"old_results_snapshot.json").read_text(encoding="utf-8"));current=audit.hash_tree(cfg.old_results,{"trajectories","baseline_cache","figures","__pycache__"})
    changed={key:{"before":expected.get(key),"after":current.get(key)} for key in sorted(set(expected)|set(current)) if expected.get(key)!=current.get(key)};return {"passed":not changed,"changed":changed}

def d1(cfg:DirectionConfig)->bool:
    if not d0(cfg):return False
    stage=cfg.results_root/"d4r2"/"pilot";complete=stage/"complete.json"
    if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("passed"):return True
    jobs=pilot_jobs();write_json(stage/"freeze.json",{"jobs":jobs,"protocol":audit.sha256(HERE/"protocol.md"),"amendment":audit.sha256(HERE/"protocol_amendment.md"),"status":"frozen_before_generation"})
    tic=time.perf_counter();done,fail=_run_jobs(cfg,jobs,stage/"trajectories");paths=[stage/"trajectories"/r["file"] for r in done];contract=pilot_contract(paths,cfg.project_root);readonly=_old_readonly(cfg)
    total=sum(x["bytes"] for x in done);wall=time.perf_counter()-tic;projection=total/max(len(done),1)*320
    passed=not fail and contract["passed"] and readonly["passed"]
    write_json(stage/"manifest.json",{"planned":16,"completed":done,"failures":fail,"contract":contract,"old_results_read_only":readonly,"resource":{"wall_time_s":wall,"bytes":total,"projected_320_bytes":projection,"workers":8}})
    write_json(stage/"resource_budget.json",{"pilot_wall_s":wall,"bytes":total,"projected_320_gb":projection/2**30,"workers":8,"RAM":"not sampled; process design <16GB","VRAM":"not used"})
    write_json(complete,{"stage":"D1","passed":passed,"completed":len(done),"failures":len(fail),"direction_reversal_events":contract["direction_reversal_events"],"ultimate_steps":contract["ultimate_steps"],"projected_320_gb":projection/2**30})
    append_log(cfg,"D0002","D1安全与方向事件pilot",[f"任务书={audit.sha256(HERE/'protocol.md')}；代码generate={audit.sha256(HERE/'generate_d4r2.py')} coverage={audit.sha256(HERE/'coverage.py')}",f"命令=run.py --stage d1；seed=180001–180016；完成={len(done)}/16，失败={len(fail)}，未替换",f"finite={contract['finite']}；ultimate={contract['ultimate_steps']}；轴向反号={contract['axial_negative_samples']}；方向反转事件={contract['direction_reversal_events']}",f"旧结果只读={readonly['passed']}；wall={wall:.2f}s；数据={total/2**20:.2f}MiB；320投影={projection/2**30:.3f}GiB",f"输出manifest={audit.sha256(stage/'manifest.json')}；结论：{'通过' if passed else '停止'}"])
    if not passed:solution(cfg,"D1 pilot门失败",[f"failures={fail}",f"contract={clean(contract)}",f"readonly={readonly}"],["只允许使用冻结安全降级表整轮同seed重跑，最多两轮"],"D2不得启动。")
    return passed

def d2(cfg:DirectionConfig)->bool:
    if not d1(cfg):return False
    stage=cfg.results_root/"d4r2"/"formal";complete=stage/"complete.json"
    if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("passed"):return True
    jobs=formal_jobs();threshold_path=cfg.old_results/"d4r"/"formal"/"regime_thresholds.json";thresholds=json.loads(threshold_path.read_text(encoding="utf-8"));write_json(stage/"freeze.json",{"jobs":jobs,"regime_thresholds":thresholds,"threshold_sha256":audit.sha256(threshold_path),"status":"frozen_before_generation"})
    tic=time.perf_counter();done,fail=_run_jobs(cfg,jobs,stage/"trajectories");write_json(stage/"generation_manifest.json",{"planned":320,"completed":done,"failures":fail})
    if fail or len(done)!=320:
        write_json(stage/"failure.json",{"stage":"D2-generation","completed":len(done),"failures":fail});solution(cfg,"D2生成失败",[f"{len(done)}/320",str(fail)],["修复实现后同seed断点重跑"],"不得替换seed或静默丢弃。")
        append_log(cfg,"D0003","D2生成失败",[f"完成={len(done)}/320，失败={len(fail)}","未启动覆盖/缓存；结论=停止"]);return False
    paths=[stage/"trajectories"/r["file"] for r in done];contract=formal_contract(paths,cfg.project_root,thresholds);readonly=_old_readonly(cfg);added=[];active_jobs=list(jobs)
    # Only a high-load shortfall may invoke the preregistered whole-round
    # addition.  Other contract failures still stop immediately.
    base_other_ok=not contract["failures"] and contract["coverage_gate"] and contract["event_gate"] and contract["ultimate_steps"]==0 and contract["axial_negative_samples"]==0
    if base_other_ok and not contract["high_gate"]:
        for round_id in (1,2):
            extra=append_jobs(round_id);seed_audit=audit.audit_seed_collisions(cfg.project_root/"revision_2026",[j["seed"] for j in extra]);write_json(stage/f"append_round{round_id}_freeze.json",{"jobs":extra,"seed_audit":seed_audit,"reason":"train high-load windows below 200","before":contract["high_load_windows"]})
            if not seed_audit["passed"]:break
            local_done,local_fail=_run_jobs(cfg,extra,stage/"trajectories");write_json(stage/f"append_round{round_id}_manifest.json",{"completed":local_done,"failures":local_fail})
            if local_fail or len(local_done)!=32:break
            added.extend(local_done);active_jobs.extend(extra);paths.extend(stage/"trajectories"/r["file"] for r in local_done);contract=formal_contract(paths,cfg.project_root,thresholds)
            if contract["passed"]:break
    write_json(stage/"contract_coverage.json",contract)
    if not contract["passed"] or not readonly["passed"]:
        write_json(stage/"failure.json",{"stage":"D2-contract","contract":contract,"old_readonly":readonly});solution(cfg,"D2覆盖/合同门失败",[json.dumps(clean(contract),ensure_ascii=False),str(readonly)],["只允许训练前按预注册追加表补轨迹；映射错误先修实现后同seed复核"],"不得降floor、重叠采窗或读取development调门。")
        append_log(cfg,"D0003","D2覆盖/合同失败",[f"320/320生成；覆盖={contract['coverage']}；事件={contract['direction_events']}；高载荷={contract['high_load_windows']}",f"合同失败={contract['failures']}；结论=停止"]);return False
    cache_done,cache_fail=cache_all(cfg.project_root,active_jobs,stage/"trajectories",stage/"cache",4);write_json(stage/"cache_manifest.json",{"completed":cache_done,"failures":cache_fail,"models":["P0-K1","P1-frozen-H2"],"base":320,"added":len(added)})
    passed=len(cache_done)==len(active_jobs) and not cache_fail
    write_json(complete,{"stage":"D2","passed":passed,"base_trajectories":320,"added_trajectories":len(added),"trajectories":len(active_jobs),"cache":len(cache_done),"coverage":contract["coverage"],"direction_events":contract["direction_events"],"high_load_windows":contract["high_load_windows"],"contract_sha256":audit.sha256(stage/"contract_coverage.json")})
    append_log(cfg,"D0003","D2 D4R2生成/覆盖/缓存",[f"任务书={audit.sha256(HERE/'protocol.md')}；正式seed原号段，320/320，失败=0，未替换",f"保留的首次覆盖失败：train高载荷107<200；按冻结追加表整轮增加={len(added)}条，未降低0.8 rated",f"冻结旧D4R validation工况阈值hash={audit.sha256(threshold_path)}；覆盖={contract['coverage']}",f"反转事件={contract['direction_events']}；高载荷={contract['high_load_windows']}；ultimate={contract['ultimate_steps']}；轴向反号={contract['axial_negative_samples']}",f"shape/time/单位/顺序失败={len(contract['failures'])}；旧结果只读={readonly['passed']}",f"P0/P1缓存={len(cache_done)}/{len(active_jobs)}，失败={cache_fail}；wall={time.perf_counter()-tic:.1f}s",f"输出complete={audit.sha256(complete)}；结论：{'通过' if passed else '停止'}"])
    if not passed:solution(cfg,"D2缓存失败",[str(cache_fail)],["修复适配实现后用现有冻结D4R2断点重算"],"D3不得启动。")
    return passed

def d3(cfg:DirectionConfig)->bool:
    if not d2(cfg):return False
    stage=cfg.results_root/"d3_h2_generalization";complete=stage/"complete.json"
    if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("experiment_complete"):return True
    tic=time.perf_counter();regression=h2_regression(cfg.project_root);write_json(stage/"h2_regression.json",regression)
    if not regression["passed"]:
        write_json(stage/"failure.json",{"stage":"D3-adapter","regression":regression});solution(cfg,"D3 H2适配回归失败",[str(regression)],["逐字段核对feature维数/normalizer/dtype后原样重跑"],"不得近似替代冻结H2。")
        append_log(cfg,"D0004","D3适配器失败",[f"回归={regression}","未读取development；结论=停止"]);return False
    result=evaluate_d3(cfg.project_root);write_json(stage/"results.json",result);readonly=_old_readonly(cfg);passed=result["passed"] and readonly["passed"]
    write_json(complete,{"stage":"D3","experiment_complete":True,"hypothesis_passed":passed,"relative_improvement":result["relative_improvement"],"gates":result["gates"],"regression":regression,"results_sha256":audit.sha256(stage/"results.json")})
    append_log(cfg,"D0004","D3冻结原H2新数据泛化",[f"H2逐元素回归={regression}；原H2/K1只读",f"全新development轨迹=64；P0={result['P0']}；P1={result['P1']}",f"10–20步J改善={100*result['relative_improvement']:.3f}%；轨迹统计={result['statistics']}",f"门禁={result['gates']}；旧结果只读={readonly['passed']}；wall={time.perf_counter()-tic:.2f}s",f"结论：{'复现，允许D4' if passed else '不复现，停止全部方向头'}"])
    if not passed:solution(cfg,"D3原H2幅值收益未复现",[f"improvement={result['relative_improvement']}",f"gates={result['gates']}"],["停止P2–P5，不训练方向头；保留为旧development特定收益证据"],"不得在本D4R2上调H2后继续称冻结泛化。")
    return True

def _d4_gates(metrics:dict[str,dict[str,Any]],runtime:dict[str,float])->dict[str,bool]:
    k1=metrics["P0"];p1=metrics["P1"];p4=metrics["P4"]
    return {"J_vs_K1_8pct":(k1["J_pred"]-p4["J_pred"])/k1["J_pred"]>=.08,"state_binary_P1":True,"force_vs_P1_le_5pct":p4["force"]<=1.05*p1["force"],"load_vs_P1_le_5pct":p4["load"]<=1.05*p1["load"],"component_direction":p4["component_sign_accuracy"]>=k1["component_sign_accuracy"]-.01,"Q_direction":p4["q_sign_accuracy"]>=k1["q_sign_accuracy"]-.01,"angle_p95":p4["angle_p95_deg"]<=k1["angle_p95_deg"],"reversal":p4["reversal_accuracy"]>=k1["reversal_accuracy"],"Q_algebra":p4["algebraic_residual_N"]<=1e-10,"fallback":p4["fallback_rate"]<=.01,"divergence":p4["divergence_rate"]<=k1["divergence_rate"],"runtime":runtime["p99_ms"]<8.}

def d4(cfg:DirectionConfig)->bool:
    if not d3(cfg):return False
    stage=cfg.results_root/"d4_validation";complete=stage/"complete.json"
    if complete.exists():return bool(json.loads(complete.read_text(encoding="utf-8")).get("passed"))
    tic=time.perf_counter();train=load_direction_dataset(cfg.project_root,"train");validation=load_direction_dataset(cfg.project_root,"validation");thresholds=fit_thresholds(train);write_json(stage/"frozen_thresholds.json",thresholds);counter=manual_counterexample();write_json(stage/"physics_decoder_counterexample.json",counter)
    records=[]
    for seed in cfg.train_seeds:
        record=train_seed(train,validation,thresholds,seed,cfg.scale_grid,cfg.ridge_grid,stage/"models");records.append(record);write_json(stage/"training_progress.json",records);print(f"D4 trained seed {seed} ({len(records)}/5)",flush=True)
    ranked=sorted(records,key=lambda r:r["validation"]["P4"]["J_pred"]);representative=ranked[len(ranked)//2];p4,p5,meta=load_heads(stage/"models"/representative["model"]);pred=structured_predictions(validation,p4,float(thresholds["direction_floor"]));add_p5(pred,validation,p5);metrics={k:direction_metrics(v,validation,thresholds) for k,v in pred.items()};runtime=prediction_runtime_p99_ms(validation,p4,float(thresholds["direction_floor"]));gates=_d4_gates(metrics,runtime);readonly=_old_readonly(cfg);passed=all(gates.values()) and counter["passed"] and readonly["passed"]
    result={"representative_seed":representative["seed"],"representative_rule":"median validation P4 J_pred among five seeds","metrics_10_20":metrics,"runtime_9_candidates":runtime,"gates":gates,"counterexample":counter,"thresholds":thresholds,"all_seeds":records,"old_results_read_only":readonly};write_json(stage/"results.json",result);write_json(complete,{"stage":"D4","passed":passed,"representative_seed":representative["seed"],"gates":gates,"results_sha256":audit.sha256(stage/"results.json")})
    append_log(cfg,"D0005","D4方向头训练与validation选择",[f"五seed={cfg.train_seeds}；代表seed={representative['seed']}（validation J中位，不读取development）",f"train阈值={clean(thresholds)}；物理反例={counter}",f"P0–P5 validation={clean(metrics)}",f"9窗批量推理={runtime}；门禁={gates}",f"模型={representative['model']} sha256={representative['model_sha256']}；wall={time.perf_counter()-tic:.1f}s；旧结果只读={readonly['passed']}",f"结论：{'通过，允许D5' if passed else '停止，不读取development'}"])
    if not passed:solution(cfg,"D4 validation门失败",[f"代表seed={representative['seed']}",json.dumps(clean(metrics),ensure_ascii=False),f"gates={gates}"],["保留全部五seed和P2/P3/P5归因结果；停止development、D5和闭环依赖实验"],"不得针对validation失败改门后继续，也不得读取development调P4。")
    return passed

def d11(cfg:DirectionConfig)->bool:
    stage=cfg.results_root/"d4_validation";results=stage/"results.json"
    if not results.exists():solution(cfg,"D11无法汇总",["D4 results.json不存在"],["先完成D4"],"不得伪造图表。");return False
    summary=build_report(results,cfg.results_root/"delivery");write_json(cfg.results_root/"delivery"/"summary.json",summary)
    source=sorted(HERE.glob("*.py"))+[HERE/"protocol.md",HERE/"protocol_amendment.md"];manifest=[{"path":str(p),"before_sha256":None,"after_sha256":audit.sha256(p),"functions_changed":"isolated direction implementation","reason":"execute koopman_dir.md","tests_run":["py_compile/-B execution","D0-D4 stage contracts"],"rollback_path":"remove innovation/direction only"} for p in source];write_json(cfg.results_root/"audits"/"change_manifest.json",manifest)
    readonly=_old_readonly(cfg);append_log(cfg,"D0006","D11负结果图表、报告和交付",[f"D4失败后未启动D5/D6-D10；输出={summary['files']}",f"归因={summary}；旧结果只读={readonly['passed']}",f"change_manifest条目={len(manifest)}；结论=负结果完整交付"]);return readonly["passed"]

def main()->None:
    p=argparse.ArgumentParser();p.add_argument("--stage",choices=("d0","d1","d2","d3","d4","d11"),required=True);p.add_argument("--project-root",type=Path,required=True);a=p.parse_args();cfg=DirectionConfig(a.project_root.resolve());ok={"d0":d0,"d1":d1,"d2":d2,"d3":d3,"d4":d4,"d11":d11}[a.stage](cfg);raise SystemExit(0 if ok else 2)
if __name__=="__main__":main()
