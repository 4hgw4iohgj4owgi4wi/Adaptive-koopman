from __future__ import annotations
import argparse, json, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import audit
from config import EFDR11Config, seed_block
import schema

HERE = Path(__file__).resolve().parent


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def log(cfg: EFDR11Config, number: str, title: str, lines: list[str]) -> None:
    path = cfg.results / "work_log.md"; path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists(): path.write_text("# EFD-R1工作记录\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as h:
        h.write(f"\n## {number} {title}\n\n- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n" + "\n".join(f"- {x}" for x in lines) + "\n")


def solution(cfg: EFDR11Config, title: str, facts: list[str], actions: list[str], boundary: str) -> None:
    path = cfg.results / "solutions.md"; path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists(): path.write_text("# EFD-R1问题与处置\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as h:
        h.write(f"\n## {title}\n\n### 已核实事实\n\n" + "\n".join(f"- {x}" for x in facts) +
                "\n\n### 允许的小修与成本\n\n" + "\n".join(f"- {x}" for x in actions) +
                f"\n\n### 论文影响与恢复条件\n\n{boundary}\n")


def r0(cfg: EFDR11Config) -> bool:
    stage = cfg.results / "freeze"; complete = stage / "complete.json"
    protocol = HERE / "protocol.md"
    if audit.sha256(protocol) != cfg.protocol_sha256:
        solution(cfg, "R0协议哈希不符", [f"expected={cfg.protocol_sha256}", f"actual={audit.sha256(protocol)}"],
                 ["同步最新efd_r1.md并新建协议版本；不得覆盖历史complete"], "R0恢复前不得生成pilot。")
        return False
    all_audits = {}
    selected = None
    for base in cfg.base_candidates:
        flat = sum(seed_block(base).values(), [])
        result = audit.seed_collisions(cfg.project_root / "revision_2026", flat)
        all_audits[str(base)] = result
        if result["passed"]: selected = base; break
    write_json(stage / "seed_audit.json", {"candidates": all_audits, "selected_base": selected})
    schema_value = schema.contract(); schema.validate(schema_value); write_json(stage / "schema.json", schema_value)
    old = {
        "efd_code": audit.hash_tree(cfg.koopman / "innovation" / "efd", {"__pycache__"}),
        "efd_results": audit.hash_tree(cfg.koopman / "innovation_efd_results", {"__pycache__", "postmortem"}),
        "direction_code": audit.hash_tree(cfg.koopman / "innovation" / "direction", {"__pycache__"}),
        "direction_results": audit.hash_tree(cfg.koopman / "innovation_direction_results", {"__pycache__"}),
        "efd_r1_code": audit.hash_tree(cfg.koopman / "innovation" / "efd_r1", {"__pycache__"}),
        "efd_r1_results": audit.hash_tree(cfg.koopman / "innovation_efd_r1_results", {"__pycache__"}),
    }
    write_json(stage / "old_readonly_snapshot.json", old); write_json(stage / "environment.json", audit.environment())
    files = {"protocol": protocol,
             "plant": cfg.project_root / "revision_2026" / "model" / "four_vehicle_coupled.py",
             "generator": cfg.koopman / "generate_k2.py",
             "H2": cfg.koopman / "innovation_results" / "t4_h2" / "models" / "N2-seed-151002.npz",
             "K1": cfg.koopman / "k2" / "linear" / "models" / "S3-U1-lifted.npz"}
    hashes = {k: {"path": str(p), "sha256": audit.sha256(p), "bytes": p.stat().st_size} for k, p in files.items()}
    write_json(stage / "source_hashes.json", hashes)
    passed = selected is not None and hashes["H2"]["sha256"] == cfg.h2_sha256 and hashes["K1"]["sha256"] == cfg.k1_sha256
    freeze = {"stage": "R0", "passed": passed, "selected_base": selected, "seed_block": seed_block(selected) if selected else None,
              "protocol_sha256": hashes["protocol"]["sha256"], "source_hashes": hashes,
              "old_tree_counts": {k: len(v) for k, v in old.items()}, "protocol_version": "EFD-R1.1"}
    write_json(complete, freeze)
    log(cfg, "R11001", "S0协议、seed、输入和历史目录冻结", [
        f"协议SHA256={hashes['protocol']['sha256']}", f"候选块审计={all_audits}", f"选定BASE={selected}",
        f"H2/K1 hash匹配={passed}", f"旧目录文件数={freeze['old_tree_counts']}",
        "新增独立efd_r1代码；旧efd/direction代码与结果只读快照已落盘", f"结论={'通过' if passed else '停止'}"])
    return passed


def r1(cfg: EFDR11Config) -> bool:
    if not r0(cfg): return False
    from selftest import run as tests
    stage = cfg.results / "r1_contracts"; result = tests(cfg.project_root)
    write_json(stage / "tests.json", result); passed = bool(result["passed"])
    write_json(stage / "complete.json", {"stage": "R1", "passed": passed, "tests_sha256": audit.sha256(stage / "tests.json")})
    log(cfg, "R11002", "S1相对特征、Q奇偶、镜像投影与轴向解码合同", [
        f"tests={result}", "修正全局旋转合同：world位置/航向变换，车体速度不重复旋转",
        "小修留痕：plant诊断未导出完整相对速度；oracle按已导出的normal_speed*n构造轴向等价速度，未修改plant",
        "Reynolds使用row-regression矩阵约定并以交换子与预测等式双测试冻结",
        f"结论={'通过，允许R2 pilot' if passed else '停止，不生成pilot'}"])
    if not passed:
        solution(cfg, "R1单元合同失败", [json.dumps(result, ensure_ascii=False)],
                 ["只修坐标、矩阵乘法或plant公式实现并重跑同一确定性测试"], "全部R1合同通过前不得生成pilot。")
    return passed


def r2(cfg: EFDR11Config, workers: int) -> bool:
    if not r1(cfg): return False
    from pilot import generate_one
    from pilot_r11 import analytic_oracle, jobs
    from integrator_equivariance import local_audit, long_audit
    freeze = json.loads((cfg.results / "freeze" / "complete.json").read_text(encoding="utf-8")); base = int(freeze["selected_base"])
    stage = cfg.results / "pilot"; existing_complete=stage/"complete.json"
    if existing_complete.exists():
        prior=json.loads(existing_complete.read_text(encoding="utf-8"))
        if prior.get("passed") is True:return True
    traj = stage / "trajectories"; traj.mkdir(parents=True, exist_ok=True)
    planned = jobs(base)
    write_json(stage / "freeze.json", {"jobs": planned, "L0_analytic_max": 1e-12,
               "L1": {"derivative_max":1e-12,"rk4_002_max":1e-11,"rk4_02_max":1e-9,"rk4_04_p95":1e-5,"rk4_04_max":1e-4,"pass_count":11},
               "physical_scales": schema.contract()["physical_scales"], "L2_role":"diagnostic; blocks only nonfinite/event asymmetry/systematic unexplained bias",
               "tolerance_frozen_before_generation": True, "protocol_sha256": cfg.protocol_sha256})
    done = []; failures = []; tic = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(generate_one, str(cfg.project_root), j, str(traj)): j for j in planned}
        for i, future in enumerate(as_completed(futures), 1):
            try: done.append(future.result())
            except Exception as exc: failures.append({"job": futures[future], "error": repr(exc)})
            print(f"S2 base+analytic {i}/24 failures={len(failures)}", flush=True)
    done.sort(key=lambda x: x["seed"]); write_json(stage / "manifest.json", {"completed": done, "failures": failures})
    analytic = []; local = []; long = []
    if not failures and len(done) == 24:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(analytic_oracle, str(cfg.project_root), row, str(traj)): row for row in done}
            for i, future in enumerate(as_completed(futures), 1):
                try: analytic.append(future.result())
                except Exception as exc: failures.append({"job": futures[future], "audit_error": repr(exc)})
                print(f"S2 L0 analytic/oracle {i}/24 failures={len(failures)}", flush=True)
        local_rows=[x for x in done if x["local_mirror"]]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(local_audit,str(cfg.project_root),str(traj/x["base_file"])):x for x in local_rows}
            for i,future in enumerate(as_completed(futures),1):
                try: local.append(future.result())
                except Exception as exc: failures.append({"job":futures[future],"local_error":repr(exc)})
                print(f"S2 L1 local {i}/12 failures={len(failures)}",flush=True)
        long_rows=[x for x in done if x["long_diagnostic"]]; curves=stage/"long_horizon_diagnostic";curves.mkdir(parents=True,exist_ok=True)
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures={pool.submit(long_audit,str(cfg.project_root),str(traj/x["base_file"]),str(curves/f"curve_{x['seed']}.npz")):x for x in long_rows}
            for i,future in enumerate(as_completed(futures),1):
                try: long.append(future.result())
                except Exception as exc: failures.append({"job":futures[future],"long_error":repr(exc)})
                print(f"S2 L2 long {i}/8 failures={len(failures)}",flush=True)
    analytic.sort(key=lambda x:x["seed"]);local.sort(key=lambda x:x["seed"]);long.sort(key=lambda x:x["seed"])
    write_json(stage/"l0_analytic_oracle.json",analytic);write_json(stage/"local_equivariance"/"results.json",local);write_json(stage/"long_horizon_diagnostic"/"results.json",long)
    finite = not failures and len(done) == 24 and all(x["finite"] and x["ultimate_steps"] == 0 for x in done)
    local_pass=sum(x["passed"] for x in local); long_block=any(x["blocking"] for x in long)
    passed = finite and len(analytic)==24 and all(x["passed"] for x in analytic) and len(local)==12 and local_pass>=11 and len(long)==8 and not long_block
    result = {"stage": "S2", "passed": passed, "base_trajectories": len(done), "analytic_mirrors": len(done),
              "local_pass_count":local_pass,"local_total":len(local),"long_diagnostics":len(long),"long_blocking":long_block,"failures": failures,
              "finite_ultimate_gate": finite, "oracle_max_N": max((x["oracle_max_N"] for x in analytic), default=None),
              "local_worst_04_p95":max((x["checkpoints"]["0.4"]["overall"]["p95_max"] for x in local),default=None),
              "local_worst_04_max":max((x["checkpoints"]["0.4"]["overall"]["max"] for x in local),default=None),
              "wall_time_s": time.perf_counter() - tic, "workers": workers, "bytes": sum(x.get("bytes", 0) for x in done)}
    write_json(stage / "complete.json", result)
    log(cfg, "R11003", "S2新pilot、0.4秒局部门与长时诊断", [f"结果={result}",
        "L0/L1为硬门；L2长时仅在非有限/事件不一致/系统性偏置时阻断；解析镜像不增加独立n",
        "工程小修：generate_k2未重导出system_derivative，L1显式绑定经S0冻结的plant RHS；seed/数据/积分/门限未改",
        f"结论={'通过，允许S3' if passed else '停止S3'}"])
    if not passed: solution(cfg, "S2局部物理/pilot门失败", [json.dumps(result, ensure_ascii=False), json.dumps(failures, ensure_ascii=False)],
        ["工程异常只允许同seed断点重跑；若仅1组轻微超门按协议做dt收敛；不放宽冻结容差"], "S2硬门恢复前不得生成正式train。")
    return passed


def r3(cfg: EFDR11Config, workers: int) -> bool:
    if not r2(cfg, workers): return False
    from formal_data import coverage, jobs
    from pilot import generate_one
    freeze0=json.loads((cfg.results/"freeze"/"complete.json").read_text(encoding="utf-8"));base=int(freeze0["selected_base"])
    stage=cfg.results/"data";complete=stage/"complete.json";planned=jobs(base)
    if complete.exists():
        prior=json.loads(complete.read_text(encoding="utf-8"))
        if prior.get("passed") is True:return True
    write_json(stage/"freeze.json",{"jobs":planned,"active_force_floor_N":10.,"high_load_floor_N":500.,
        "coverage":"all scenarios; +/- each Fx/Fy; reversals each component; high load; every parameter range straddles 1",
        "base_family_is_statistical_unit":True,"analytic_mirror_adds_n":False,"protocol_sha256":cfg.protocol_sha256})
    roots={s:stage/s for s in ("train","validation","development")}
    for root in roots.values():root.mkdir(parents=True,exist_ok=True)
    done=[];failures=[];tic=time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(generate_one,str(cfg.project_root),job,str(roots[job["split"]])):job for job in planned}
        for i,future in enumerate(as_completed(futures),1):
            try:done.append(future.result())
            except Exception as exc:failures.append({"job":futures[future],"error":repr(exc)})
            if i%10==0 or i==len(planned):print(f"S3 formal {i}/{len(planned)} failures={len(failures)}",flush=True)
            if i%25==0:write_json(stage/"progress.json",{"completed":done,"failures":failures})
    done.sort(key=lambda x:x["seed"]);write_json(stage/"manifest.json",{"completed":done,"failures":failures})
    finite=not failures and len(done)==len(planned) and all(x["finite"] and x["ultimate_steps"]==0 for x in done)
    cov=coverage(done,roots) if finite else {"passed":False};write_json(stage/"coverage.json",cov)
    passed=finite and cov["passed"]
    result={"stage":"S3","passed":passed,"base_families":len(done),"analytic_mirrors":len(done),"failures":failures,
            "finite_ultimate_gate":finite,"coverage":cov,"wall_time_s":time.perf_counter()-tic,"workers":workers,"bytes":sum(x.get("bytes",0) for x in done),
            "development_model_read":False}
    write_json(complete,result);log(cfg,"R11004","S3正式train/validation/development生成与覆盖",[f"结果={result}",
        "解析镜像与base同split；coverage/CI/bootstrap只计base family；development仅生成未用于模型评价",f"结论={'通过，允许S4' if passed else '停止S4'}"])
    if not passed:solution(cfg,"S3生成或覆盖门失败",[json.dumps(result,ensure_ascii=False)],
        ["工程失败同seed断点续跑；覆盖不足只能按新预注册追加表补充，不移动split或重复计镜像"],"S3恢复前不得训练。")
    return passed


def r4(cfg:EFDR11Config,workers:int)->bool:
    if not r3(cfg,workers):return False
    from fair_baselines import train_and_validate
    stage=cfg.results/"s4_baselines";complete=stage/"complete.json"
    if complete.exists():
        prior=json.loads(complete.read_text(encoding="utf-8"));
        if prior.get("passed") is True:return True
    result=train_and_validate(cfg.results/"data",cfg.ridge_grid);write_json(stage/"results.json",result)
    passed=result["B3_reproduced"] and result["B4_learnable"];write_json(complete,{"stage":"S4","passed":passed,"B3_reproduced":result["B3_reproduced"],"B4_learnable":result["B4_learnable"]})
    log(cfg,"R11005","S4同数据B0-B4公平重训",[f"结果={result}","B0-B4共用新train/validation、46维x0和20步控制；development未读",
        "小修留痕：首跑direct horizon特征遗漏train-only列标准化导致与历史H2合同不公平；补mean/std后同数据/网格重跑，首跑失败结果未删除",f"结论={'通过，允许S5' if passed else '停止S5'}"])
    if not passed:solution(cfg,"S4公平骨干或直接力可学习性失败",[json.dumps(result,ensure_ascii=False)],
        ["只核对窗口、归一化和接口；不得扩大head或读取development"],"B3优势与B4可学习性同时恢复前停止R1.1主模型。")
    return passed


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--stage", choices=("s0", "s1", "s2", "s3", "s4"), required=True); p.add_argument("--workers", type=int, default=8)
    a = p.parse_args(); cfg = EFDR11Config(a.project_root.resolve())
    ok = {"s0": lambda: r0(cfg), "s1": lambda: r1(cfg), "s2": lambda: r2(cfg, a.workers), "s3":lambda:r3(cfg,a.workers),"s4":lambda:r4(cfg,a.workers)}[a.stage]()
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__": main()
