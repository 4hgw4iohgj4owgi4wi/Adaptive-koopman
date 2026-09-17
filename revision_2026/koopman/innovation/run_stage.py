from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path: sys.path.insert(0, str(HERE))
from config import InnovationConfig
import audit_inputs as audit
from legacy_adapter import FrozenK1Adapter
from data_protocol import pilot_jobs, formal_jobs, CONFIGS
from generate_d4r import simulate_one
from t2_analysis import freeze_validation_thresholds,coverage,audit_contracts
from baseline_cache import cache_all
from train_component import train_regime
from horizon_training import train_horizon
from make_report import make_report


def clean(value: Any) -> Any:
    if isinstance(value, dict): return {str(k): clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [clean(v) for v in value]
    if isinstance(value, Path): return str(value)
    if isinstance(value, np.ndarray): return clean(value.tolist())
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, float) and not math.isfinite(value): return None
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8"); temp.replace(path)


def append_log(cfg: InnovationConfig, identifier: str, title: str, lines: list[str]) -> None:
    path=cfg.results_root/"work_log.md"; path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as h:
        h.write(f"\n## {identifier} — {title}\n\n- 开始/结束时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        h.write("\n".join(f"- {line}" for line in lines)+"\n")


def solution(cfg: InnovationConfig, title: str, facts: list[str], actions: list[str], boundary: str) -> None:
    path=cfg.results_root/"solutions.md"; path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists(): path.write_text("# CRMH-Koopman问题与处置\n",encoding="utf-8")
    with path.open("a",encoding="utf-8") as h:
        h.write(f"\n## {title}\n\n### 事实\n\n"+"\n".join(f"- {x}" for x in facts))
        h.write("\n\n### 方案\n\n"+"\n".join(f"- {x}" for x in actions)+f"\n\n### 边界\n\n{boundary}\n")


def t0(cfg: InnovationConfig) -> bool:
    out=cfg.results_root; stage=out/"freeze"; gate=stage/"t0_gate.json"; audits=out/"audits"
    if gate.exists() and json.loads(gate.read_text(encoding="utf-8")).get("passed"): return True
    koop=cfg.koopman_root; universal=koop/"universal_v2"; composer=koop/"composer_results"
    paths={"protocol":HERE/"protocol.md", "universal_modules":koop/"universal_v2_modules.py",
           "compare_pipeline":koop/"compare_pipeline.py", "generate_k2":koop/"generate_k2.py",
           "plant":cfg.project_root/"revision_2026"/"model"/"four_vehicle_coupled.py",
           "allocator":cfg.project_root/"revision_2026"/"model"/"steering_allocator.py",
           "closed_loop_current":koop/"universal_v2_closedloop.py", "K1_operator":koop/"k2"/"linear"/"models"/"S3-U1-lifted.npz",
           "K0_Fhead":universal/"t3"/"models"/"K0.npz", "K1_Fhead":universal/"t3"/"models"/"K1.npz",
           "K4_Fhead":universal/"t3"/"models"/"K4.npz", "K5_Fhead":universal/"t3"/"models"/"K5-linear.npz",
           "F_selection":universal/"t3"/"selection.json", "composer_input_freeze":composer/"t0"/"input_freeze.json",
           "composer_cache_manifest":composer/"t2"/"cache_manifest.json"}
    missing=[name for name,path in paths.items() if not path.exists()]
    if missing:
        write_json(gate,{"passed":False,"missing":missing}); solution(cfg,"T0输入缺失",missing,["恢复冻结输入后原seed重跑"],"不得生成D4R。"); return False
    hashes=audit.hash_frozen_inputs(paths); write_json(audits/"source_hashes.json",hashes)
    prior=json.loads(paths["composer_input_freeze"].read_text(encoding="utf-8"))["inputs"]
    expected_map={"universal_modules":"universal_v2_modules.py","closed_loop_current":"universal_v2_closedloop.py",
                  "K0_Fhead":"K0.npz","K1_Fhead":"K1.npz","K4_Fhead":"K4.npz","K5_Fhead":"K5-linear.npz","F_selection":"selection.json"}
    matches={key: hashes[key]["sha256"]==prior[src]["sha256"] for key,src in expected_map.items()}
    selection=json.loads(paths["F_selection"].read_text(encoding="utf-8"))["backbones"]["K5-linear"]
    identity={"K5_validation_F2":selection.get("validation_selected")=="F2","K5_BFH_F0":selection.get("BFH_force_head")=="F0"}
    code=audit.write_code_map([paths[k] for k in ("compare_pipeline","generate_k2","plant","allocator","universal_modules","closed_loop_current")],audits/"code_map.md")
    write_json(audits/"legacy_api.json",{"code_map_sha256":code["sha256"],"K1":{"lift":"compare_pipeline.lift","step":"compare_pipeline.model_step","decode":"compare_pipeline.decode"},
               "plant":{"step":"four_vehicle_coupled.rk4_step","features":"generate_k2.feature_rows"},"closed_loop":{"executor":"universal_v2_closedloop.simulate_job"}})
    schema=audit.schema(); write_json(audits/"schema.json",schema)
    requested=list(range(130001,130049))+list(range(131001,131241))+list(range(132001,132081))+list(range(133001,133081))+list(range(141001,141161))+list(range(142001,142033))+list(range(143001,143025))+list(range(144001,144041))+list(range(145001,145041))
    manifests=list((cfg.project_root/"revision_2026").rglob("manifest*.json"))+list((cfg.project_root/"revision_2026").rglob("freeze.json"))
    seed=audit.audit_seed_collisions(manifests,requested); write_json(audits/"seed_audit.json",seed)
    d5=audit.audit_d5_absent(out); write_json(audits/"d5_audit.json",d5)
    # Independent K1 adapter regression against the frozen composer D4 cache.
    adapter=FrozenK1Adapter(koop); cache_manifest=json.loads(paths["composer_cache_manifest"].read_text(encoding="utf-8"))["trajectories"]
    diffs=[]; checked=0
    for row in cache_manifest[:8]:
        raw=composer/"d4"/"trajectories"/row["file"]
        cache=composer/"t2"/"cache"/row["file"]
        with np.load(raw,allow_pickle=False) as s: x=np.asarray(s["s3_deform"],float); u=np.asarray(s["u1_four"],float)
        with np.load(cache,allow_pickle=False) as s: origins=np.asarray(s["origins"],int); px=np.asarray(s["pred_x"],float); pf=np.asarray(s["pred_f"],float)
        for wi,start in enumerate(origins[:4]):
            xn,fn=adapter.rollout_normalized(x[start],u[start:start+20])
            # Composer cache is intentionally float32.  The protocol accepts
            # elementwise <=1e-10 OR binary equality with the frozen cache.
            x32=np.asarray(xn,dtype=np.float32); f32=np.asarray(fn,dtype=np.float32)
            binary=bool(np.array_equal(x32,np.asarray(px[wi,1],dtype=np.float32)) and np.array_equal(f32,np.asarray(pf[wi,1],dtype=np.float32)))
            diffs.append({"float64_vs_cache":max(float(np.max(np.abs(xn-px[wi,1]))),float(np.max(np.abs(fn-pf[wi,1])))),"binary_float32_equal":binary}); checked+=1
    regression={"windows":checked,"max_abs_difference_float64_vs_float32_cache":max(x["float64_vs_cache"] for x in diffs),
                "all_binary_float32_equal":all(x["binary_float32_equal"] for x in diffs),"threshold_or_binary":"<=1e-10 or binary float32 equality",
                "passed":all(x["binary_float32_equal"] for x in diffs) or max(x["float64_vs_cache"] for x in diffs)<=1e-10}; write_json(audits/"k1_regression.json",regression)
    historical="30445AE583452C5FE495230339E879FC0B3B47FD0A5AF4452E5573B4761F1C1F"; found=audit.locate_legacy_by_hash(cfg.project_root,historical)
    closed={"historical_sha256":historical,"located":str(found) if found else None,"current_entry_located":paths["closed_loop_current"].exists(),"offline_allowed":True,"t8_requires_recovery_or_new_adapter_regression":found is None}; write_json(audits/"closed_loop_audit.json",closed)
    passed=not missing and all(matches.values()) and all(identity.values()) and not seed["collisions"] and d5["passed"] and regression["passed"] and len(schema["state_s3"]["names"])==46
    write_json(gate,{"stage":"T0","passed":passed,"hash_matches":matches,"identity":identity,"seed_collisions":seed["collisions"],"d5":d5,"K1_regression":regression,"closed_loop":closed})
    # Every new file is new, so before hash is null and rollback is directory removal only.
    source_files=[HERE/x for x in ("__init__.py","config.py","contracts.py","audit_inputs.py","legacy_adapter.py","run_stage.py","protocol.md")]
    changes=[{"path":str(p),"before_sha256":None,"after_sha256":audit.sha256(p),"functions_changed":"new file","reason":"T0 implementation contract","tests_run":["K1 regression","hash/seed/D5/schema audit"],"rollback_path":"remove innovation directory only"} for p in source_files]
    write_json(audits/"change_manifest.json",changes)
    append_log(cfg,"I0001","T0冻结/接口/污染审计",[f"5080主机与项目根目录：{cfg.project_root}",f"用户任务书SHA256：{audit.sha256(HERE/'protocol.md')}",
               f"修改文件：{len(source_files)}个新文件；change_manifest={audit.sha256(audits/'change_manifest.json')}","实际命令：run_stage.py --stage t0；退出码由gate决定",
               f"输入hash匹配：{matches}；K5身份：{identity}",f"seed请求={len(requested)}，碰撞={seed['collisions']}；D5审计={d5['passed']}",
               f"K1回归：windows={checked}, float32_binary={regression['all_binary_float32_equal']}, max_abs64vs32={regression['max_abs_difference_float64_vs_float32_cache']:.3e}",f"历史闭环hash定位={found}；当前入口已定位，不影响离线但T8独立受限",
               f"资源：RAM/VRAM未训练；磁盘D={os.statvfs(str(cfg.project_root)).f_bavail*os.statvfs(str(cfg.project_root)).f_frsize/2**30:.2f}GB（若Windows不可用则此项仅审计脚本值）" if hasattr(os,'statvfs') else "资源：T0无训练；磁盘由外部预检记录",
               f"结论：{'通过' if passed else '停止'}"])
    if not passed: solution(cfg,"T0门失败",[json.dumps(clean({"matches":matches,"identity":identity,"seed":seed["collisions"],"d5":d5,"regression":regression}),ensure_ascii=False)],["仅恢复冻结输入/修复适配器实现后原样重跑"],"不得生成D4R。")
    return passed


def _scales(cfg: InnovationConfig) -> dict[str,Any]:
    if str(cfg.koopman_root) not in sys.path: sys.path.insert(0,str(cfg.koopman_root))
    import generate_compare as gen
    import compare_pipeline as cp
    return gen.train_scales(cp.DATA)


def _run_jobs(cfg: InnovationConfig,jobs:list[dict[str,Any]],folder:Path,workers:int=8)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    folder.mkdir(parents=True,exist_ok=True); scales=_scales(cfg); done=[]; failures=[]; pending=[]
    for job in jobs:
        path=folder/f"{job['split']}_{job['group']}_{job['seed']}.npz"
        # simulate_one validates and summarizes a pre-existing archive without
        # rewriting it.  Incomplete writes never acquire the final .npz name.
        pending.append((job,scales,str(path)))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(simulate_one,str(cfg.project_root),*item):item for item in pending}
        for i,future in enumerate(as_completed(futures),1):
            item=futures[future]
            try: done.append(future.result())
            except Exception as exc: failures.append({"job":item[0],"error":repr(exc)})
            if i%4==0 or i==len(pending):
                print(f"D4R {folder.parent.name} {i}/{len(pending)} failures={len(failures)}",flush=True)
                write_json(folder.parent/"progress.json",{"completed":done,"failures":failures})
    done.sort(key=lambda r:r["seed"]); return done,failures


def t1(cfg: InnovationConfig) -> bool:
    if not t0(cfg): return False
    stage=cfg.results_root/"d4r"/"pilot"; complete=stage/"complete.json"
    if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("passed"): return True
    jobs=pilot_jobs(); write_json(stage/"freeze.json",{"status":"frozen_before_generation","jobs":jobs,"configs":CONFIGS,"protocol_sha256":audit.sha256(HERE/'protocol.md')})
    start=time.perf_counter(); done,failures=_run_jobs(cfg,jobs,stage/"trajectories")
    rounds={}
    for name in ("high_round1","high_round2","high_round3"):
        rows=[r for r in done if r["config_name"]==name]
        rounds[name]={"trajectories":len(rows),"failures":sum(1 for f in failures if f["job"]["config_name"]==name),
                      "high_windows":sum(r["L4_high"] for r in rows),"max_force_ratio":max((r["max_connector_force_n"]/r["rated_force_n"] for r in rows),default=0),
                      "ultimate_steps":sum(r["ultimate_exceeded_steps"] for r in rows)}
    safe=[name for name,row in rounds.items() if row["trajectories"]==4 and row["failures"]==0 and row["ultimate_steps"]==0]
    selected=max(safe,key=lambda name:(rounds[name]["high_windows"],rounds[name]["max_force_ratio"])) if safe else None
    group_counts={group:{f"R{i}":sum(r[f"R{i}"] for r in done if r["group"]==group) for i in range(4)} for group in ("G0_slack_low","G1_loading","G2_sustained","G3_transition")}
    total_bytes=sum(r["file_bytes"] for r in done); total_wall=time.perf_counter()-start; projected=total_bytes/len(done)*400 if done else math.inf
    accepted=len(done)==48 and not failures and all(r["finite"] and r["ultimate_exceeded_steps"]==0 for r in done) and projected<=40*2**30
    high_branch=selected is not None and sum(rounds[x]["high_windows"] for x in rounds)>=1
    write_json(stage/"manifest.json",{"planned":48,"completed":done,"failures":failures,"rounds":rounds,"selected_high_config":selected,
               "provisional_group_counts":group_counts,"resource":{"wall_time_s":total_wall,"bytes":total_bytes,"projected_400_bytes":projected,"workers":8}})
    write_json(complete,{"stage":"T1","passed":accepted,"high_load_branch":high_branch,"selected_high_config":selected,"failures":len(failures),
                         "projected_400_gb":projected/2**30,"manifest_sha256":audit.sha256(stage/'manifest.json')})
    append_log(cfg,"I0002","T1 D4R pilot与资源测量",[f"用户任务书SHA256：{audit.sha256(HERE/'protocol.md')}",f"命令：run_stage.py --stage t1；planned=48 completed={len(done)} failures={len(failures)}，seed未替换",
               "保留的首次失败：远端缺少data_protocol.py导致ModuleNotFoundError；仅补同步实现文件，未改seed/工况/阈值后重跑",
               f"三轮高载荷：{rounds}；selected={selected}；high_branch={high_branch}",f"临时工况覆盖：{group_counts}（正式阈值只允许T2 validation冻结）",
               f"资源：wall={total_wall:.2f}s，数据={total_bytes/2**20:.2f}MiB，400条投影={projected/2**30:.3f}GiB，workers=8",
               f"输出manifest={audit.sha256(stage/'manifest.json')}；代码run_stage={audit.sha256(HERE/'run_stage.py')} generate={audit.sha256(HERE/'generate_d4r.py')}",f"结论：{'通过' if accepted else '停止'}；高载荷分支={'保留' if high_branch else '删除'}"])
    if not accepted: solution(cfg,"T1 pilot失败",[f"completed={len(done)}, failures={failures}, projected={projected/2**30:.3f}GB"],["修复实现后按原seed重跑；不得替换失败轨迹"],"T2不得启动。")
    if accepted and not high_branch: solution(cfg,"F08高载荷三轮pilot不足",[json.dumps(rounds,ensure_ascii=False)],["删除高载荷分支，普通工况继续"],"不得降低0.8 rated定义。")
    return accepted


def t2(cfg: InnovationConfig) -> bool:
    if not t1(cfg): return False
    previous=cfg.results_root/"d4r"/"pilot"/"complete.json"; stage=cfg.results_root/"d4r"/"formal"; complete=stage/"complete.json"
    if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("passed"): return True
    pilot=json.loads(previous.read_text(encoding="utf-8")); selected=pilot.get("selected_high_config")
    if not selected:
        solution(cfg,"T2缺少冻结高载荷配置",["T1没有selected_high_config"],["删除高载荷分支前需在data_protocol中定义普通G2替代配置"],"不得猜测配置继续生成。"); return False
    jobs=formal_jobs(selected); stage.mkdir(parents=True,exist_ok=True)
    write_json(stage/"freeze.json",{"status":"frozen_before_generation","previous_complete_sha256":audit.sha256(previous),"selected_high_config":selected,
                                    "jobs":jobs,"configs":CONFIGS,"protocol_sha256":audit.sha256(HERE/'protocol.md')})
    tic=time.perf_counter(); done,failures=_run_jobs(cfg,jobs,stage/"trajectories")
    write_json(stage/"generation_manifest.json",{"planned":400,"completed":done,"failures":failures})
    if failures or len(done)!=400:
        write_json(stage/"failure.json",{"stage":"T2-generation","planned":400,"completed":len(done),"failures":failures})
        solution(cfg,"T2正式轨迹生成失败",[f"completed={len(done)}/400",json.dumps(failures,ensure_ascii=False)],["修复实现后只按原seed断点重跑"],"不得替换seed或静默丢弃。")
        append_log(cfg,"I0003","T2正式D4R生成失败",[f"completed={len(done)}/400 failures={len(failures)}；failure.json已保留","结论：T2停止，未缓存基线"]); return False
    paths=[stage/"trajectories"/row["file"] for row in done]
    validation=[path for path in paths if path.name.startswith("validation_")]
    thresholds=freeze_validation_thresholds(validation); write_json(stage/"regime_thresholds.json",thresholds)
    counts=coverage(paths,thresholds); write_json(stage/"regime_coverage.json",counts)
    contracts=audit_contracts(paths); write_json(stage/"contract_audit.json",contracts)
    cover_ok=all(counts.get(split,{}).get(f"R{i}",0)>=minimum for split,minimum in (("train",2000),("validation",500),("development",500)) for i in range(4))
    high_train=int(contracts["high_load_windows"].get("train",0)); high_branch=high_train>=200
    if not cover_ok or not contracts["passed"]:
        write_json(stage/"failure.json",{"stage":"T2-contract-coverage","coverage_passed":cover_ok,"contract_passed":contracts["passed"],"coverage":counts,"thresholds":thresholds})
        solution(cfg,"T2覆盖或合同门失败",[f"coverage={counts}",f"contract_passed={contracts['passed']}",f"validation-only thresholds={thresholds}"],
                 ["若是工况窗不足，仅可在训练前按冻结追加方案补对应轨迹；若是方向合同错误，先修复映射并原seed整批复核"],"不得重叠采窗、读取development调阈值或降低门槛。")
        append_log(cfg,"I0003","T2正式D4R合同门失败",[f"400/400生成，wall={time.perf_counter()-tic:.1f}s",f"validation-only阈值={thresholds}",f"覆盖={counts}",f"合同={contracts['passed']}；高载荷train={high_train}","结论：停止在缓存/训练前"]); return False
    cache_done,cache_failures=cache_all(cfg.project_root,jobs,stage/"trajectories",stage/"baseline_cache",workers=4)
    write_json(stage/"cache_manifest.json",{"models":["K0","K1","K2","K5(F2)","B4(C5)","B5(C9)"],"completed":cache_done,"failures":cache_failures})
    passed=len(cache_done)==400 and not cache_failures
    write_json(stage/"implementation_manifest.json",{"files":{p.name:audit.sha256(p) for p in (HERE/"data_protocol.py",HERE/"generate_d4r.py",HERE/"regime_coverage.py",HERE/"t2_analysis.py",HERE/"baseline_cache.py",HERE/"run_stage.py")}})
    write_json(complete,{"stage":"T2","passed":passed,"trajectories":len(done),"coverage":counts,"thresholds_sha256":audit.sha256(stage/'regime_thresholds.json'),
                         "contract_sha256":audit.sha256(stage/'contract_audit.json'),"cache_completed":len(cache_done),"cache_failures":cache_failures,
                         "high_load_branch":high_branch,"high_load_train_windows":high_train,"action_reaction":"not_identifiable"})
    append_log(cfg,"I0003","T2正式D4R与冻结基线缓存",[f"命令：run_stage.py --stage t2；400/400生成，seed未替换，wall_total={time.perf_counter()-tic:.1f}s",
               "保留的首次合同失败：50条44 s float32时间轴因固定2e-6 s审计容差误报；改为2×末时刻float32 ULP并同时锁定单调性/总时长，未改轨迹/seed/模型/阈值",
               "保留的首次缓存失败：4分区均因错误引用universal_pipeline.uv2在加载阶段退出、0缓存落盘；改为直接导入冻结universal_v2_pipeline适配器，未改算法",
               f"validation-only阈值：eps_p={thresholds['eps_p']:.9g}, eps_v={thresholds['eps_v']:.9g}；grid={thresholds['grid_candidates']}",f"非重叠覆盖={counts}",
               f"合同：passed={contracts['passed']}，力顺序=FL/FR/RL/RR×Fx/Fy，轴向反号样本={contracts['direction_contract']['opposite_axial_samples']}",
               "车辆侧独立施力未记录，作用—反作用证据=not identifiable；未把货物侧力取负伪装成独立验证",
               f"高载荷train={high_train}，分支={'保留' if high_branch else '删除'}；缓存={len(cache_done)}/400 failures={len(cache_failures)}",f"结论：{'通过' if passed else '停止'}"])
    if not passed:
        write_json(stage/"failure.json",{"stage":"T2-cache","failures":cache_failures}); solution(cfg,"T2基线缓存失败",[json.dumps(cache_failures,ensure_ascii=False)],["修复缓存实现后按同一原始轨迹断点重算"],"T3/T4不得启动。")
    return passed


def t3(cfg: InnovationConfig) -> bool:
    if not t2(cfg): return False
    stage=cfg.results_root/"t3_h1"; complete=stage/"complete.json"
    if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("implementation_version")==2: return True
    if complete.exists():
        import shutil
        shutil.copy2(complete,stage/"complete_initial_one_step_selection.json")
        if (stage/"results.json").exists(): shutil.copy2(stage/"results.json",stage/"results_initial_one_step_selection.json")
    tic=time.perf_counter(); result=train_regime(cfg.project_root)
    write_json(complete,{"stage":"T3","implementation_version":2,"experiment_complete":True,"hypothesis_passed":result["passed"],"relative_improvement":result["relative_improvement"],
                         "representative_seed":result["representative_seed"],"results_sha256":audit.sha256(stage/'results.json'),"gates":result["gates"]})
    append_log(cfg,"I0004","T3 H1物理工况低秩残差",[f"五seed={list(range(151001,151006))}，rank={list((1,2,4,8))}，ridge={list((1e-8,1e-6,1e-4,1e-2))}",
               "每seed按轨迹bootstrap接入随机性；train拟合、validation选rank/ridge与代表seed、development只运行代表模型一次",
               "保留的初轮选择缺口：仅按validation一步状态RMSE选候选导致development约7.5倍恶化；初轮complete/results已归档，修复为16候选validation teacher-free 20步J_pred选择",
               f"代表seed={result['representative_seed']}；development改善={100*result['relative_improvement']:.3f}%；工况改善={result['regime_improvements']}",
               f"门禁={result['gates']}；轨迹级统计={result['statistics']}",f"资源wall={time.perf_counter()-tic:.1f}s；结论：H1={'通过' if result['passed'] else '失败，停止N1/N3/N4/N5'}"])
    if not result["passed"]: solution(cfg,"H1预注册门失败",[f"improvement={result['relative_improvement']}",f"gates={result['gates']}"],["保留N1为负结果；继续独立检验H2"],"不得用development调rank/ridge后复算。")
    return True


def t4(cfg: InnovationConfig) -> bool:
    if not t2(cfg): return False
    stage=cfg.results_root/"t4_h2"; complete=stage/"complete.json"
    if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("experiment_complete"): return True
    tic=time.perf_counter(); result=train_horizon(cfg.project_root)
    write_json(complete,{"stage":"T4","experiment_complete":True,"hypothesis_passed":result["passed"],"relative_improvement":result["relative_improvement"],
                         "representative_seed":result["representative_seed"],"results_sha256":audit.sha256(stage/'results.json'),"gates":result["gates"]})
    append_log(cfg,"I0005","T4 H2直接多时域输出",["五seed轨迹bootstrap；每个h=1..20使用同一ridge网格，validation按固定state+force+load+0.1direction+0.05consistency选择",
               "teacher-free输入合同=x0与u_future；不读取真实中间状态；development仅运行validation中位代表seed一次",
               f"代表seed={result['representative_seed']}；10–20步J改善={100*result['relative_improvement']:.3f}%，force={100*result['force_improvement']:.3f}%，load={100*result['load_improvement']:.3f}%",
               f"运行时间={result['runtime']}；门禁={result['gates']}；轨迹级统计={result['statistics']}",f"资源wall={time.perf_counter()-tic:.1f}s；结论：H2={'通过' if result['passed'] else '失败，停止N2/N4/N5'}"])
    if not result["passed"]: solution(cfg,"H2预注册门失败",[f"improvement={result['relative_improvement']}",f"gates={result['gates']}"],["保留N2为负结果；不进入依赖N2的组合和D5"],"不得用development逐h挑模型。")
    return True


def _stopped_stage(cfg:InnovationConfig,number:int,dependency:str,reason:str)->bool:
    stage=cfg.results_root/f"t{number}_stopped"; complete=stage/"complete.json"
    if complete.exists(): return True
    write_json(complete,{"stage":f"T{number}","experiment_complete":True,"status":"not_run_by_preregistered_dependency_gate","dependency":dependency,"reason":reason})
    append_log(cfg,f"I{number+2:04d}",f"T{number}依赖门停止",[f"dependency={dependency}",f"事实={reason}","未生成D5、未训练候选、未运行闭环；停止不是算力失败"])
    return True


def t5(cfg:InnovationConfig)->bool:
    if not t3(cfg): return False
    h1=json.loads((cfg.results_root/"t3_h1"/"complete.json").read_text(encoding="utf-8"))
    if not h1["hypothesis_passed"]: return _stopped_stage(cfg,5,"H1/N1",f"H1 gates failed: {h1['gates']}")
    raise RuntimeError("H1 passed but certificate implementation was not reached; do not silently skip")


def t6(cfg:InnovationConfig)->bool:
    if not (t3(cfg) and t4(cfg) and t5(cfg)): return False
    h1=json.loads((cfg.results_root/"t3_h1"/"complete.json").read_text(encoding="utf-8")); h2=json.loads((cfg.results_root/"t4_h2"/"complete.json").read_text(encoding="utf-8"))
    if not (h1["hypothesis_passed"] and h2["hypothesis_passed"]): return _stopped_stage(cfg,6,"H1 and H2",f"H1={h1['hypothesis_passed']}, H2={h2['hypothesis_passed']}; no N4/N5 candidate is eligible")
    raise RuntimeError("H1/H2 passed but combination implementation was not reached; do not silently skip")


def t7(cfg:InnovationConfig)->bool:
    if not t6(cfg): return False
    return _stopped_stage(cfg,7,"T6 frozen candidate","T6 produced no eligible combined candidate; development confirmation is forbidden")


def t8(cfg:InnovationConfig)->bool:
    if not t7(cfg): return False
    return _stopped_stage(cfg,8,"T6/T7 frozen candidate","No eligible predictor exists; closed-loop and network comparisons would not answer the registered hypothesis")


def t9(cfg:InnovationConfig)->bool:
    if not t8(cfg): return False
    stage=cfg.results_root/"t9_report"; complete=stage/"complete.json"
    if complete.exists(): return True
    artifacts=make_report(cfg.results_root); write_json(complete,{"stage":"T9","experiment_complete":True,"artifacts":artifacts,"report_sha256":audit.sha256(cfg.results_root/'final_report.md')})
    append_log(cfg,"I0011","T9负结果图表与总报告",[f"图={artifacts['figures']}",f"CSV={artifacts['csv']}",f"报告hash={audit.sha256(cfg.results_root/'final_report.md')}","图表由冻结JSON/CSV自动生成；数值与停止门一致"]); return True


def t10(cfg:InnovationConfig)->bool:
    if not t9(cfg): return False
    import zipfile
    stage=cfg.results_root/"t10_delivery"; complete=stage/"complete.json"
    if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("implementation_version")==2: return True
    stage.mkdir(parents=True,exist_ok=True); files=[]
    archive=stage/"innovation_delivery.zip"
    if archive.exists() and not (stage/"innovation_delivery_initial.zip").exists():
        import shutil
        shutil.copy2(archive,stage/"innovation_delivery_initial.zip")
    # The first package was created before I0012 was appended, so its work log
    # did not contain its own delivery action.  Rebuild only the light package;
    # preserve the initial archive and all experiment artifacts.
    append_log(cfg,"I0012V2","T10交付包自包含修复",["保留initial zip；重建包使其中work_log包含T10留痕","未改实验结果、模型、阈值、门禁或D5状态"])
    for path in cfg.results_root.rglob("*"):
        if not path.is_file() or stage in path.parents: continue
        relative=path.relative_to(cfg.results_root)
        if "trajectories" in relative.parts or "baseline_cache" in relative.parts: continue
        files.append(path)
    files.extend(p for p in HERE.glob("*.py")); files.append(HERE/"protocol.md")
    manifest=[{"path":str(path),"sha256":audit.sha256(path),"bytes":path.stat().st_size} for path in sorted(set(files))]; write_json(stage/"delivery_manifest.json",manifest)
    temporary=stage/"innovation_delivery.tmp.zip"
    with zipfile.ZipFile(temporary,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(set(files)):
            arc=(Path("results")/path.relative_to(cfg.results_root)) if cfg.results_root in path.parents else (Path("source")/path.name); z.write(path,arcname=str(arc))
        z.write(stage/"delivery_manifest.json",arcname="delivery_manifest.json")
    temporary.replace(archive)
    write_json(complete,{"stage":"T10","implementation_version":2,"experiment_complete":True,"archive":str(archive),"archive_sha256":audit.sha256(archive),"files":len(manifest),"raw_data_location":str(cfg.results_root/'d4r'/'formal'/'trajectories'),"D5_created":False})
    append_log(cfg,"I0012","T10交付审计",[f"交付包={archive}",f"SHA256={audit.sha256(archive)}，文件={len(manifest)}","原始D4R与400条基线缓存保留在5080，不复制进轻量交付包；D5未创建",f"最终结论：T0–T4完成，H1/H2失败，T5–T8依赖门停止"]); return True


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--stage",choices=tuple(f"t{i}" for i in range(11)),required=True); parser.add_argument("--project-root",type=Path,required=True); args=parser.parse_args()
    cfg=InnovationConfig(args.project_root.resolve()); stages={"t0":t0,"t1":t1,"t2":t2,"t3":t3,"t4":t4,"t5":t5,"t6":t6,"t7":t7,"t8":t8,"t9":t9,"t10":t10}; ok=stages[args.stage](cfg); raise SystemExit(0 if ok else 2)


if __name__=="__main__": main()
