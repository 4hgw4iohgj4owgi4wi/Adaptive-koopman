from __future__ import annotations
import argparse, json, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import audit
from config import EFDR1Config, seed_block
import schema

HERE = Path(__file__).resolve().parent


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def log(cfg: EFDR1Config, number: str, title: str, lines: list[str]) -> None:
    path = cfg.results / "work_log.md"; path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists(): path.write_text("# EFD-R1工作记录\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as h:
        h.write(f"\n## {number} {title}\n\n- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n" + "\n".join(f"- {x}" for x in lines) + "\n")


def solution(cfg: EFDR1Config, title: str, facts: list[str], actions: list[str], boundary: str) -> None:
    path = cfg.results / "solutions.md"; path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists(): path.write_text("# EFD-R1问题与处置\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as h:
        h.write(f"\n## {title}\n\n### 已核实事实\n\n" + "\n".join(f"- {x}" for x in facts) +
                "\n\n### 允许的小修与成本\n\n" + "\n".join(f"- {x}" for x in actions) +
                f"\n\n### 论文影响与恢复条件\n\n{boundary}\n")


def r0(cfg: EFDR1Config) -> bool:
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
              "old_tree_counts": {k: len(v) for k, v in old.items()}}
    write_json(complete, freeze)
    log(cfg, "R10001", "R0协议、seed、输入和旧目录冻结", [
        f"协议SHA256={hashes['protocol']['sha256']}", f"候选块审计={all_audits}", f"选定BASE={selected}",
        f"H2/K1 hash匹配={passed}", f"旧目录文件数={freeze['old_tree_counts']}",
        "新增独立efd_r1代码；旧efd/direction代码与结果只读快照已落盘", f"结论={'通过' if passed else '停止'}"])
    return passed


def r1(cfg: EFDR1Config) -> bool:
    if not r0(cfg): return False
    from selftest import run as tests
    stage = cfg.results / "r1_contracts"; result = tests(cfg.project_root)
    write_json(stage / "tests.json", result); passed = bool(result["passed"])
    write_json(stage / "complete.json", {"stage": "R1", "passed": passed, "tests_sha256": audit.sha256(stage / "tests.json")})
    log(cfg, "R10002", "R1相对特征、镜像投影与轴向解码合同", [
        f"tests={result}", "修正全局旋转合同：world位置/航向变换，车体速度不重复旋转",
        "小修留痕：plant诊断未导出完整相对速度；oracle按已导出的normal_speed*n构造轴向等价速度，未修改plant",
        "Reynolds使用row-regression矩阵约定并以交换子与预测等式双测试冻结",
        f"结论={'通过，允许R2 pilot' if passed else '停止，不生成pilot'}"])
    if not passed:
        solution(cfg, "R1单元合同失败", [json.dumps(result, ensure_ascii=False)],
                 ["只修坐标、矩阵乘法或plant公式实现并重跑同一确定性测试"], "全部R1合同通过前不得生成pilot。")
    return passed


def r2(cfg: EFDR1Config, workers: int) -> bool:
    if not r1(cfg): return False
    from pilot import audit_one, generate_one, jobs
    freeze = json.loads((cfg.results / "freeze" / "complete.json").read_text(encoding="utf-8")); base = int(freeze["selected_base"])
    stage = cfg.results / "pilot"; traj = stage / "trajectories"; traj.mkdir(parents=True, exist_ok=True)
    tolerance = 1e-5; planned = jobs(base)
    write_json(stage / "freeze.json", {"jobs": planned, "independent_mirror_normalized_p95_max": tolerance,
               "independent_mirror_normalized_max": tolerance, "analytic_copy_max_abs": 1e-12,
               "tolerance_frozen_before_generation": True, "protocol_sha256": cfg.protocol_sha256})
    done = []; failures = []; tic = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(generate_one, str(cfg.project_root), j, str(traj)): j for j in planned}
        for i, future in enumerate(as_completed(futures), 1):
            try: done.append(future.result())
            except Exception as exc: failures.append({"job": futures[future], "error": repr(exc)})
            print(f"R2 base+analytic {i}/16 failures={len(failures)}", flush=True)
    done.sort(key=lambda x: x["seed"]); write_json(stage / "manifest.json", {"completed": done, "failures": failures})
    audits = []
    if not failures and len(done) == 16:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(audit_one, str(cfg.project_root), row, str(traj), tolerance): row for row in done}
            for i, future in enumerate(as_completed(futures), 1):
                try: audits.append(future.result())
                except Exception as exc: failures.append({"job": futures[future], "audit_error": repr(exc)})
                print(f"R2 mirror/oracle audit {i}/16 failures={len(failures)}", flush=True)
    audits.sort(key=lambda x: x["seed"]); write_json(stage / "audits.json", audits)
    finite = not failures and len(done) == 16 and all(x["finite"] and x["ultimate_steps"] == 0 for x in done)
    passed = finite and len(audits) == 16 and all(x["passed"] for x in audits) and sum(x["independent_requested"] for x in audits) == 8
    result = {"stage": "R2", "passed": passed, "base_trajectories": len(done), "analytic_mirrors": len(done),
              "independent_mirror_rollouts": sum(x.get("independent_requested", False) for x in audits), "failures": failures,
              "finite_ultimate_gate": finite, "oracle_max_N": max((x["oracle_max_N"] for x in audits), default=None),
              "independent_worst_p95": max((x.get("independent", {}).get("overall", {}).get("normalized_p95_max", 0.) for x in audits), default=None),
              "independent_worst_max": max((x.get("independent", {}).get("overall", {}).get("normalized_max", 0.) for x in audits), default=None),
              "wall_time_s": time.perf_counter() - tic, "workers": workers, "bytes": sum(x.get("bytes", 0) for x in done)}
    write_json(stage / "complete.json", result)
    log(cfg, "R10003", "R2 pilot、解析镜像与独立镜像积分", [f"冻结容差={tolerance}（生成前）", f"结果={result}",
        "解析镜像不计独立样本；独立镜像使用镜像初态+镜像控制重新RK4积分",
        "精度小修：首轮float32初态/控制重放导致长时误差；同seed旁路捕获实际送入首次RK4的state64及每周期control64，生成器/RNG/容差未改",
        f"结论={'通过，允许R3' if passed else '停止R3'}"])
    if not passed: solution(cfg, "R2镜像/本构/pilot门失败", [json.dumps(result, ensure_ascii=False), json.dumps(failures, ensure_ascii=False)],
        ["工程异常只允许同seed断点重跑；合同误差定位state/control/d/v/force/q字段；不放宽冻结容差"], "R2全部门恢复前不得生成正式train。")
    return passed


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--project-root", type=Path, required=True)
    p.add_argument("--stage", choices=("r0", "r1", "r2"), required=True); p.add_argument("--workers", type=int, default=8)
    a = p.parse_args(); cfg = EFDR1Config(a.project_root.resolve())
    ok = {"r0": lambda: r0(cfg), "r1": lambda: r1(cfg), "r2": lambda: r2(cfg, a.workers)}[a.stage]()
    raise SystemExit(0 if ok else 2)


if __name__ == "__main__": main()
