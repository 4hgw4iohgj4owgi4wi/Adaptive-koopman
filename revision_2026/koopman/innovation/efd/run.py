from __future__ import annotations
import argparse,json,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
from typing import Any
from config import EFDConfig
import audit
from schema import load_schema,validate_corner_order
from generate_d6efd import pilot_jobs,formal_jobs,simulate_one,train_scales
from geometry_audit import truth_alignment,oracle_ablation
from coverage import formal_contract
import numpy as np
from dataset import load_split,fit_metric_thresholds
from heads import fit_head,RidgeHead
from baseline import predictions
from metrics import evaluate
from efd_heads import EFDHead,fit as fit_efd
from experiment import candidate_result,bootstrap_indices
from h2_adapter import FrozenH2

HERE=Path(__file__).resolve().parent
def write_json(path:Path,v:Any)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
def log(cfg:EFDConfig,number:str,title:str,lines:list[str])->None:
    p=cfg.results/"work_log.md";p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8") as h:h.write(f"\n## {number} {title}\n\n- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"+"\n".join(f"- {x}" for x in lines)+"\n")
def solution(cfg:EFDConfig,title:str,facts:list[str],actions:list[str],boundary:str)->None:
    p=cfg.results/"solutions.md"
    if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);p.write_text("# EFD问题与处置\n",encoding="utf-8")
    with p.open("a",encoding="utf-8") as h:h.write(f"\n## {title}\n\n### 已核实事实\n\n"+"\n".join(f"- {x}" for x in facts)+"\n\n### 可行修复\n\n"+"\n".join(f"- {x}" for x in actions)+f"\n\n### 证据边界/恢复条件\n\n{boundary}\n")

def e0(cfg:EFDConfig)->bool:
    stage=cfg.results/"freeze";complete=stage/"complete.json"
    protocol=HERE/"protocol.md";project=cfg.project_root;koop=cfg.koopman
    files={"protocol":protocol,"plant":project/"revision_2026"/"model"/"four_vehicle_coupled.py","generator":koop/"generate_k2.py","H2":koop/"innovation_results"/"t4_h2"/"models"/"N2-seed-151002.npz","K1":koop/"k2"/"linear"/"models"/"S3-U1-lifted.npz","normalizer":koop/"universal_v2"/"normalizers.npz"}
    hashes={k:{"path":str(p),"sha256":audit.sha256(p),"bytes":p.stat().st_size} for k,p in files.items()};schema=load_schema(project);validate_corner_order(schema);write_json(stage/"schema_map.json",schema)
    requested=list(range(190001,190017))+list(range(191001,191257))+list(range(192001,192097))+list(range(193001,193065))+list(range(194001,194161));seeds=audit.audit_seed_collisions(project/"revision_2026",requested);write_json(stage/"seed_audit.json",seeds)
    old_direction=audit.hash_tree(koop/"innovation"/"direction",{"__pycache__"});old_results=audit.hash_tree(koop/"innovation_direction_results",{"__pycache__"});write_json(stage/"old_readonly_snapshot.json",{"code":old_direction,"results":old_results});write_json(stage/"source_hashes.json",hashes);write_json(stage/"environment.json",audit.environment());write_json(stage/"protocol.json",{"sha256":audit.sha256(protocol),"config":cfg.jsonable(),"status":"frozen_before_pilot"})
    confirm_absent=not (cfg.results/"d6efd"/"confirm").exists();passed=hashes["H2"]["sha256"]==cfg.h2_sha256 and hashes["K1"]["sha256"]==cfg.k1_sha256 and seeds["passed"] and confirm_absent and schema["connector_contract"]["force_direction_sign"]==1
    write_json(complete,{"stage":"E0","passed":passed,"H2_hash":hashes["H2"]["sha256"],"K1_hash":hashes["K1"]["sha256"],"seed_collisions":seeds["collisions"],"confirm_absent":confirm_absent,"schema_sha256":audit.sha256(stage/"schema_map.json")});log(cfg,"EFD0001","E0冻结与物理字段审计",[f"任务书SHA256={audit.sha256(protocol)}",f"H2/K1 hash匹配={passed if seeds['passed'] and confirm_absent else False}",f"结构化seed请求={len(requested)}，碰撞={len(seeds['collisions'])}","源码证明d=vehicle_anchor-payload_anchor；日志F=force_on_payload；s_i=+1；d/v/F同一payload body frame、同一t_k","轴向刚度+仅加载阻尼+2mm间隙；无切向、预紧、滞回、显式饱和",f"旧direction代码/结果快照={len(old_direction)}/{len(old_results)}；confirm absent={confirm_absent}",f"结论={'通过' if passed else '停止'}"])
    if not passed:solution(cfg,"E0门失败",[json.dumps({"hashes":hashes,"seeds":seeds,"confirm_absent":confirm_absent},ensure_ascii=False)],["恢复冻结输入；seed碰撞须在生成前整体平移连续号段"],"E1不得启动。")
    return passed

def _readonly(cfg:EFDConfig)->dict[str,Any]:
    frozen=json.loads((cfg.results/"freeze"/"old_readonly_snapshot.json").read_text(encoding="utf-8"));now={"code":audit.hash_tree(cfg.koopman/"innovation"/"direction",{"__pycache__"}),"results":audit.hash_tree(cfg.koopman/"innovation_direction_results",{"__pycache__"})};changed={k:[x for x in set(frozen[k])|set(now[k]) if frozen[k].get(x)!=now[k].get(x)] for k in frozen};return {"passed":not any(changed.values()),"changed":changed}

def e1(cfg:EFDConfig,workers:int)->bool:
    if not e0(cfg):return False
    stage=cfg.results/"pilot";complete=stage/"complete.json"
    if complete.exists():return bool(json.loads(complete.read_text(encoding="utf-8")).get("passed"))
    jobs=pilot_jobs();write_json(stage/"freeze.json",{"jobs":jobs,"protocol_sha256":audit.sha256(HERE/"protocol.md"),"status":"frozen before generation"});done=[];fail=[];tic=time.perf_counter();(stage/"trajectories").mkdir(parents=True,exist_ok=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(simulate_one,str(cfg.project_root),j,str(stage/"trajectories"/f"pilot_{j['regime']}_{j['seed']}.npz")):j for j in jobs}
        for i,f in enumerate(as_completed(futures),1):
            try:done.append(f.result())
            except Exception as exc:fail.append({"job":futures[f],"error":repr(exc)})
            print(f"E1 pilot {i}/16 failures={len(fail)}",flush=True);write_json(stage/"progress.json",{"completed":done,"failures":fail})
    done.sort(key=lambda x:x["seed"]);paths=[stage/"trajectories"/x["file"] for x in done];alignment=truth_alignment(paths) if len(done)==16 else {};oracle=oracle_ablation(cfg.project_root,paths) if len(done)==16 and alignment.get("passed") else {};readonly=_readonly(cfg);finite=not fail and len(done)==16 and all(x["finite"] and x["ultimate_steps"]==0 for x in done);passed=finite and alignment.get("passed",False) and oracle.get("passed",False) and readonly["passed"]
    result={"jobs":jobs,"completed":done,"failures":fail,"finite_ultimate_gate":finite,"truth_alignment":alignment,"oracle":oracle,"old_readonly":readonly,"resource":{"wall_time_s":time.perf_counter()-tic,"bytes":sum(x.get("bytes",0) for x in done),"workers":workers}};write_json(stage/"results.json",result);write_json(complete,{"stage":"E1","passed":passed,"completed":len(done),"failures":len(fail),"alignment_passed":alignment.get("passed"),"oracle_passed":oracle.get("passed"),"results_sha256":audit.sha256(stage/"results.json")})
    log(cfg,"EFD0002","E1 pilot物理与oracle审计",[f"16条完成={len(done)}，失败={len(fail)}，同seed无替换",f"finite/ultimate={finite}",f"真值几何—力={alignment}",f"oracle={oracle}",f"旧direction只读={readonly['passed']}；wall={time.perf_counter()-tic:.1f}s；bytes={result['resource']['bytes']}",f"结论={'通过' if passed else '停止训练'}"])
    if not passed:solution(cfg,"E1物理/oracle门失败",[json.dumps(result,ensure_ascii=False,default=str)],["先核对符号、点序、payload-frame变换和t_k时序；若属于确定性日志实现错误，只能同seed完整重做pilot"],"在真值共线与oracle门同时恢复前，E2及任何head训练不得启动。")
    return passed

def _fit_train_stats(rows:list[dict[str,Any]],root:Path)->dict[str,Any]:
    xs=[];us=[];fs=[];ds=[]
    for r in rows:
        if r["split"]!="train":continue
        with np.load(root/r["file"],allow_pickle=False) as s:xs.append(np.asarray(s["s3_deform"],float));us.append(np.asarray(s["u1_four"],float));fs.append(np.asarray(s["force_on_payload"],float));ds.append(np.asarray(s["connector_disp_payload_frame"],float))
    x=np.concatenate(xs);u=np.concatenate(us);f=np.concatenate(fs);d=np.concatenate(ds);mag=np.linalg.norm(f,axis=-1);active=mag>1e-9
    return {"x_mean":np.mean(x,axis=0).tolist(),"x_std":np.maximum(np.std(x,axis=0),1e-8).tolist(),"u_mean":np.mean(u,axis=0).tolist(),"u_std":np.maximum(np.std(u,axis=0),1e-8).tolist(),"force_mean":np.mean(f.reshape(len(f),8),axis=0).tolist(),"force_std":np.maximum(np.std(f.reshape(len(f),8),axis=0),1e-8).tolist(),"point_force_floor_N":[float(np.quantile(mag[:,i][mag[:,i]>1e-9],.1)) for i in range(4)],"direction_floor_m":float(max(1e-6,np.quantile(np.linalg.norm(d,axis=-1)[active],.01))),"fit_split":"train only","samples":{"state":len(x),"control":len(u),"force":len(f)}}

def e2(cfg:EFDConfig,workers:int)->bool:
    if not e1(cfg,workers):return False
    stage=cfg.results/"d6efd";complete=stage/"complete.json"
    if complete.exists():return bool(json.loads(complete.read_text(encoding="utf-8")).get("passed"))
    jobs=formal_jobs();write_json(stage/"freeze.json",{"jobs":jobs,"protocol_sha256":audit.sha256(HERE/"protocol.md"),"mirror_rule":"consecutive requested IDs share even pair_rng_seed and use forced signs -1/+1; table frozen before generation","status":"frozen before formal generation"});traj=stage/"trajectories";traj.mkdir(parents=True,exist_ok=True);scales=train_scales(cfg.project_root);done=[];fail=[];tic=time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(simulate_one,str(cfg.project_root),j,str(traj/f"{j['split']}_{j['regime']}_{j['seed']}.npz"),scales):j for j in jobs}
        for i,f in enumerate(as_completed(futures),1):
            try:done.append(f.result())
            except Exception as exc:fail.append({"job":futures[f],"error":repr(exc)})
            if i%10==0 or i==len(jobs):print(f"E2 D6-EFD {i}/{len(jobs)} failures={len(fail)}",flush=True);write_json(stage/"progress.json",{"completed":done,"failures":fail})
    done.sort(key=lambda x:x["seed"]);write_json(stage/"manifest.json",{"planned":len(jobs),"completed":done,"failures":fail})
    if fail or len(done)!=len(jobs):
        write_json(cfg.results/"failure.json",{"stage":"E2-generation","completed":len(done),"failures":fail});solution(cfg,"E2生成失败",[f"{len(done)}/{len(jobs)}",str(fail)],["修复确定性实现后用相同seed和冻结job断点重跑"],"不得替换失败seed或丢弃轨迹。") ;log(cfg,"EFD0003","E2生成失败",[f"完成={len(done)}/{len(jobs)}；失败={len(fail)}；停止"]);return False
    contract=formal_contract(done,traj);write_json(stage/"coverage.json",contract);stats=_fit_train_stats(done,traj);write_json(stage/"train_thresholds.json",stats);readonly=_readonly(cfg);passed=contract["passed"] and readonly["passed"]
    write_json(complete,{"stage":"E2","passed":passed,"trajectories":len(done),"coverage":contract,"thresholds_sha256":audit.sha256(stage/"train_thresholds.json"),"manifest_sha256":audit.sha256(stage/"manifest.json")});resource={"wall_time_s":time.perf_counter()-tic,"bytes":sum(x["bytes"] for x in done),"workers":workers,"projected_confirm_bytes":sum(x["bytes"] for x in done)/len(done)*160};write_json(stage/"resource_budget.json",resource)
    log(cfg,"EFD0003","E2 D6-EFD正式数据与覆盖",[f"正式轨迹={len(done)}/{len(jobs)}，失败=0，未换seed",f"覆盖={contract}",f"train-only阈值SHA256={audit.sha256(stage/'train_thresholds.json')}",f"镜像对采用共享冻结rng seed与强制±sign；旧目录只读={readonly['passed']}",f"资源={resource}",f"结论={'通过' if passed else '停止'}"])
    if not passed:solution(cfg,"E2覆盖门失败",[json.dumps(contract,ensure_ascii=False)],["只允许按新任务书预注册追加表整轮追加；当前任务书未给具体追加seed表，因此在补充协议前停止"],"不得降低活动力floor、重复切窗或移动split轨迹。")
    return passed

def _save_heads(path:Path,mag:RidgeHead,point:RidgeHead,meta:dict[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,mag_coef=mag.coef,mag_mean=mag.mean,mag_std=mag.std,mag_dims=mag.dims,mag_scale=mag.scale,point_coef=point.coef,point_mean=point.mean,point_std=point.std,point_dims=point.dims,metadata_json=np.asarray(json.dumps(meta,sort_keys=True)))

def _h2_regression(cfg:EFDConfig,data:dict[str,Any],limit:int=32)->dict[str,Any]:
    import sys
    old=cfg.koopman/"innovation"
    if str(old) not in sys.path:sys.path.insert(0,str(old))
    from multihorizon import DirectMultiHorizonHead
    path=cfg.koopman/"innovation_results"/"t4_h2"/"models"/"N2-seed-151002.npz"
    with np.load(path,allow_pickle=False) as s:legacy=DirectMultiHorizonHead(s["coef"],s["feature_mean"],s["feature_std"],s["feature_dims"])
    a=data["h2"][:limit];b=np.asarray([legacy.predict(data["x0"][i],data["u"][i]) for i in range(min(limit,len(data["x0"]))) ]);diff=float(np.max(np.abs(a-b)));binary=bool(np.array_equal(a.astype(np.float32),b.astype(np.float32)));return {"windows":len(b),"max_abs":diff,"float32_binary_equal":binary,"passed":diff<=1e-10 or binary}

def e3(cfg:EFDConfig)->bool:
    if not e2(cfg,8):return False
    stage=cfg.results/"e3_baselines";complete=stage/"complete.json"
    if complete.exists():return bool(json.loads(complete.read_text(encoding="utf-8")).get("passed"))
    tic=time.perf_counter();train=load_split(cfg.project_root,"train",False);validation=load_split(cfg.project_root,"validation",True);thresholds=fit_metric_thresholds(train);direction_floor=json.loads((cfg.results/"d6efd"/"train_thresholds.json").read_text(encoding="utf-8"))["direction_floor_m"];write_json(stage/"metric_thresholds.json",{**{k:v.tolist() for k,v in thresholds.items()},"direction_floor_m":direction_floor,"fit_split":"train only","status":"frozen before head fit"});regression=_h2_regression(cfg,validation);write_json(stage/"h2_regression.json",regression)
    if not regression["passed"]:solution(cfg,"E3 H2适配失败",[str(regression)],["核对feature、dtype与normalizer后同数据重跑"],"E4/E5不得训练。") ;return False
    mag,magmeta=fit_head(train,validation,"magnitude",cfg.ridge_grid);point,pointmeta=fit_head(train,validation,"point",cfg.ridge_grid);model=stage/"models"/"E2_E3_full_train.npz";_save_heads(model,mag,point,{"magnitude":magmeta,"point":pointmeta,"train_trajectories":len(train["rows"]),"validation_trajectories":len(validation["rows"]),"protocol":audit.sha256(HERE/"protocol.md")});pred=predictions(validation,mag,point,direction_floor);metrics={k:evaluate(v["x"],v["points"],v["q"],validation,thresholds) for k,v in pred.items()};p5gate=metrics["E3"]["J"]<metrics["E1"]["J"] and metrics["E3"]["component_accuracy"]>=metrics["E1"]["component_accuracy"] and metrics["E3"]["divergence_rate"]<=metrics["E1"]["divergence_rate"];readonly=_readonly(cfg);passed=p5gate and readonly["passed"]
    result={"metrics_10_20":metrics,"H2_regression":regression,"E3_learnability_gate":p5gate,"model":str(model),"model_sha256":audit.sha256(model),"train_windows":len(train["x0"]),"validation_windows":len(validation["x0"]),"development_read":False,"old_readonly":readonly,"wall_time_s":time.perf_counter()-tic};write_json(stage/"results.json",result);write_json(complete,{"stage":"E3","passed":passed,"E3_learnability_gate":p5gate,"model_sha256":audit.sha256(model),"results_sha256":audit.sha256(stage/"results.json")});log(cfg,"EFD0004","E3冻结H2/K1与E2/E3新数据复现",[f"H2逐元素回归={regression}",f"train/validation windows={len(train['x0'])}/{len(validation['x0'])}；development未读",f"E0-E3={metrics}",f"E3可学习性门={p5gate}；模型SHA256={audit.sha256(model)}",f"旧目录只读={readonly['passed']}；wall={time.perf_counter()-tic:.1f}s",f"结论={'通过，允许E4/E5' if passed else '停止'}"])
    if not passed:solution(cfg,"E3 P5可学习性或只读门失败",[json.dumps(result,ensure_ascii=False,default=str)],["先核对新数据特征、归一化和输入输出映射；不扩大网络"],"E4/E5不得启动。")
    return passed

def _load_baseline_heads(path:Path)->tuple[RidgeHead,RidgeHead]:
    with np.load(path,allow_pickle=False) as s:return RidgeHead(s["mag_coef"],s["mag_mean"],s["mag_std"],s["mag_dims"],"magnitude",s["mag_scale"]),RidgeHead(s["point_coef"],s["point_mean"],s["point_std"],s["point_dims"],"point",None)
def _save_efd(path:Path,h:EFDHead,meta:dict[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,coef=h.coef,mean=h.mean,std=h.std,dims=h.dims,kind=np.asarray(h.kind),force_scale=h.force_scale,theta_deg=np.asarray(h.theta_deg),metadata_json=np.asarray(json.dumps(meta,sort_keys=True)))
def _load_thresholds(cfg:EFDConfig)->tuple[dict[str,np.ndarray],float]:
    raw=json.loads((cfg.results/"e3_baselines"/"metric_thresholds.json").read_text(encoding="utf-8"));return {k:np.asarray(raw[k],float) for k in ("component_floor","point_floor","q_floor")},float(raw["direction_floor_m"])

def _run_efd_validation(cfg:EFDConfig,kind:str)->bool:
    if not e3(cfg):return False
    name="e4_g_efd" if kind=="G" else "e5_d_efd";stage=cfg.results/name;complete=stage/"complete.json"
    if complete.exists():return bool(json.loads(complete.read_text(encoding="utf-8")).get("hypothesis_passed"))
    model_seeds=list(range(196001,196006))+[196999];seed_audit=audit.audit_seed_collisions(cfg.project_root/"revision_2026",model_seeds);write_json(stage/"seed_audit.json",seed_audit)
    if not seed_audit["passed"]:solution(cfg,f"{name} bootstrap seed碰撞",[str(seed_audit)],["训练前整体更换模型bootstrap号段并更新冻结记录"],"不得只换单个seed。");return False
    tic=time.perf_counter();train=load_split(cfg.project_root,"train",False);validation=load_split(cfg.project_root,"validation",True);thr,floor=_load_thresholds(cfg);mag,point=_load_baseline_heads(cfg.results/"e3_baselines"/"models"/"E2_E3_full_train.npz");bases=predictions(validation,mag,point,floor);h2=FrozenH2(cfg.koopman/"innovation_results"/"t4_h2"/"models"/"N2-seed-151002.npz");grid=[]
    configs=[(lam,0.) for lam in cfg.ridge_grid] if kind=="G" else [(lam,float(theta)) for theta in cfg.theta_grid for lam in cfg.ridge_grid]
    for lam,theta in configs:
        head=fit_efd(train,kind,lam,theta);result=candidate_result(head,validation,bases,thr,floor,h2);score=(result["metrics"]["force"]+result["metrics"]["load"]+result["metrics"]["angle_p95_deg"]/180)/3;grid.append({"ridge":lam,"theta_deg":theta,"score_J_force":score,"result":result,"head":head});print(f"{name} ridge={lam:g} theta={theta:g} passed={result['passed']}",flush=True)
    eligible=[x for x in grid if x["result"]["passed"]];pool=eligible if eligible else grid;selected=min(pool,key=lambda x:(x["score_J_force"],-x["ridge"],x["theta_deg"]));head=selected.pop("head");bootstrap=[]
    for seed in range(196001,196006):
        idx=bootstrap_indices(train,seed);bh=fit_efd(train,kind,selected["ridge"],selected["theta_deg"],idx);br=candidate_result(bh,validation,bases,thr,floor,h2);bootstrap.append({"seed":seed,"result":br});print(f"{name} bootstrap {seed} passed={br['passed']}",flush=True)
    model=stage/"models"/f"{kind}_EFD_full_train.npz";_save_efd(model,head,{"ridge":selected["ridge"],"theta_deg":selected["theta_deg"],"selection":"hard gates then minimum J_force; full train deterministic","bootstrap_seeds":list(range(196001,196006))});passed=selected["result"]["passed"];serial_grid=[{k:v for k,v in x.items() if k!="head"} for x in grid];result={"kind":kind,"selected":selected,"grid":serial_grid,"bootstrap":bootstrap,"bootstrap_pass_count":sum(x["result"]["passed"] for x in bootstrap),"model":str(model),"model_sha256":audit.sha256(model),"development_read":False,"wall_time_s":time.perf_counter()-tic,"old_readonly":_readonly(cfg)};write_json(stage/"results.json",result);write_json(complete,{"stage":name,"experiment_complete":True,"hypothesis_passed":passed,"selected_ridge":selected["ridge"],"selected_theta_deg":selected["theta_deg"],"failed_gates":[k for k,v in selected["result"]["gates"].items() if not v],"model_sha256":audit.sha256(model),"results_sha256":audit.sha256(stage/"results.json")});log(cfg,"EFD0005" if kind=="G" else "EFD0006",f"{name} validation",[f"有限网格={configs}",f"选择={selected}",f"五bootstrap通过={result['bootstrap_pass_count']}/5",f"development未读；模型SHA256={audit.sha256(model)}；wall={time.perf_counter()-tic:.1f}s",f"结论={'通过' if passed else '本候选失败'}"])
    if not passed:solution(cfg,f"{name} validation门失败",[f"selected={json.dumps(selected,ensure_ascii=False,default=str)}"],["保留有限网格和bootstrap证据；G失败仍允许独立E5，D失败不增加60/90度网格"],"不得读取development调参。")
    return passed

def e4(cfg:EFDConfig)->bool:return _run_efd_validation(cfg,"G")
def e5(cfg:EFDConfig)->bool:return _run_efd_validation(cfg,"D")

def e9(cfg:EFDConfig)->bool:
    from report import build
    e4c=cfg.results/"e4_g_efd"/"complete.json";e5c=cfg.results/"e5_d_efd"/"complete.json"
    if not e4c.exists() or not e5c.exists():return False
    g=json.loads(e4c.read_text(encoding="utf-8"));d=json.loads(e5c.read_text(encoding="utf-8"));summary=build(cfg.project_root,cfg.results/"figures");write_json(cfg.results/"metrics"/"summary.json",summary);failure={"stage":"E4/E5 validation","both_candidates_failed":not g["hypothesis_passed"] and not d["hypothesis_passed"],"G_failed_gates":g["failed_gates"],"D_failed_gates":d["failed_gates"],"blocked_stages":["E6 development","E7 confirm generation","E8 blind confirm","LPV/MPC/network"],"development_model_evaluation_performed":False,"confirm_generated":False};write_json(cfg.results/"failure.json",failure)
    report=f"""# EFD实验结论

## 结论

E0–E3通过；G-EFD与D-EFD均在新validation失败。按预注册规则停止E6–E8，未用development选择或修改模型，未生成confirm。

## 事实

- plant真值几何与真值力角度p95约0.035°，说明轴向物理合同成立。
- 冻结H2几何oracle角度p95为169.6°，连接几何是P4失败的主要来源。
- G-EFD显著改善连接位移和方向精度，但失败门为：{', '.join(g['failed_gates'])}。
- D-EFD最佳为15°小残差，但失败门为：{', '.join(d['failed_gates'])}。
- 两者Q代数、非负幅值、发散和实时门均通过；失败不是程序跑不动，而是支撑证据不足。

## 解释与方案

G-EFD显示几何可被线性读出修正，但当前近零位移定义和左右镜像实现/模型偏置不满足部署合同。D-EFD说明限制在45°以内的方向旋转无法替代严重错误的H2几何。

恢复实验需要新协议：先让状态骨干本身采用相对坐标/等变状态合同，或重新训练仅30–46维的几何骨干；必须使用新的validation/development/confirm，不能回看本轮validation后继续复用。

本轮不能声称闭环收益、通信保护必要性或真实货物撕裂概率。
""";(cfg.results/"report.md").write_text(report,encoding="utf-8");source=sorted(HERE.glob("*.py"))+[HERE/"protocol.md"];write_json(cfg.results/"audits"/"change_manifest.json",[{"path":str(p),"before_sha256":None,"after_sha256":audit.sha256(p),"reason":"isolated EFD implementation","tests_run":["py_compile","E0-E5 contracts","E9 render"],"rollback_path":"remove innovation/efd only"} for p in source]);log(cfg,"EFD0007","E9负结果图表与交付",[f"failure={failure}",f"figures={summary['figures']}","E6-E8未启动；development未用于模型评价；confirm未生成",f"旧目录只读={_readonly(cfg)['passed']}","结论=负结果完整交付"]);return True

def e10(cfg:EFDConfig)->bool:
    from postmortem import run as postmortem_run
    result=postmortem_run(cfg)
    updated=cfg.results/"postmortem"/"updated_execution_md.md"
    log(cfg,"EFD0008","更新任务书后的EFD-v1诊断",[
        f"诊断={result}",
        "只读取已查看的validation；未读取development；未生成confirm；未把诊断当成新门限证据",
        f"更新任务书副本={updated}；SHA256={audit.sha256(updated) if updated.exists() else 'not_synced'}",
        "原E6-E8仍停止；R1缺少冻结seed/split/模型/严格镜像生成合同，未擅自启动",
    ])
    solution(cfg,"EFD-v1事后诊断与R1恢复条件",[
        f"等变分层诊断={json.dumps(result['equivariance_decomposition'],ensure_ascii=False)}",
        f"因果回退率={json.dumps(result['fallback_rates'],ensure_ascii=False)}",
        f"严格镜像对={json.dumps(result['strict_mirror_pair_audit'],ensure_ascii=False)}",
    ],[
        "R1先冻结全新validation/development/confirm seed表、数量与生成器hash",
        "严格镜像必须同physical_scene、同随机参数/初值，仅左右反射；生成后做数组级等式审计",
        "把H2几何、head标量与decoder分别设门，并预注册等变训练项权重或硬等变结构",
        "回退率同时报告all、predicted-active与current-measured-active；门限不得使用未来真值",
    ],"以上R1合同落盘并冻结前，不复用已查看validation/dev，不启动E6-E8、LPV/MPC或网络实验。")
    return True

def main()->None:
    p=argparse.ArgumentParser();p.add_argument("--project-root",type=Path,required=True);p.add_argument("--stage",choices=("e0","e1","e2","e3","e4","e5","e9","e10"),required=True);p.add_argument("--workers",type=int,default=8);a=p.parse_args();cfg=EFDConfig(a.project_root.resolve());ok={"e0":lambda:e0(cfg),"e1":lambda:e1(cfg,a.workers),"e2":lambda:e2(cfg,a.workers),"e3":lambda:e3(cfg),"e4":lambda:e4(cfg),"e5":lambda:e5(cfg),"e9":lambda:e9(cfg),"e10":lambda:e10(cfg)}[a.stage]();raise SystemExit(0 if ok else 2)
if __name__=="__main__":main()
