"""Idempotent SHKC stage executor.

Frozen K0/K1/K4/K5-linear operators and the accepted coupled plant are read
only.  New data and all derived artifacts are isolated under composer_results.
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import sys
import time
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
KOOPMAN = HERE.parent
if str(KOOPMAN) not in sys.path:
    sys.path.insert(0, str(KOOPMAN))

from config import resolved
import compare_pipeline as cp
import generate_compare as gen
import universal_v2_modules as uv

CFG = resolved(HERE)
OUT = CFG.result_root
D4 = OUT / "d4"
D5 = OUT / "d5"
EXPECTED_CLOSED_LOOP_SHA256 = "30445AE583452C5FE495230339E879FC0B3B47FD0A5AF4452E5573B4761F1C1F"


def clean(value: Any) -> Any:
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, Path): return str(value)
    if isinstance(value, np.ndarray): return clean(value.tolist())
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, float) and not math.isfinite(value): return None
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def append_log(identifier: str, title: str, lines: list[str]) -> None:
    path = OUT / "work_log.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    block = ["", f"## {identifier} — {title}", "", f"- 时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"]
    block += [f"- {line}" for line in lines]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(block) + "\n")


def append_solution(title: str, facts: list[str], causes: list[str], actions: list[str], boundary: str) -> None:
    path = OUT / "solutions.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# SHKC实验问题与处置\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {title}\n\n### 已确认事实\n\n" + "\n".join(f"- {x}" for x in facts))
        handle.write("\n\n### 最可能原因与替代解释\n\n" + "\n".join(f"- {x}" for x in causes))
        handle.write("\n\n### 已采取/可采取方案\n\n" + "\n".join(f"- {x}" for x in actions))
        handle.write(f"\n\n### 结论边界\n\n{boundary}\n")


def _api(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        "functions": [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
        "classes": [n.name for n in tree.body if isinstance(n, ast.ClassDef)],
    }


def _artifact(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as source:
        return {"path": str(path), "sha256": sha256(path),
                "arrays": {key: list(source[key].shape) for key in source.files}}


def t0_freeze() -> bool:
    stage = OUT / "t0"
    complete = stage / "complete.json"
    if complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("accepted"):
        return True
    protocol = HERE / "protocol.md"
    module = KOOPMAN / "universal_v2_modules.py"
    closed_loop = KOOPMAN / "universal_v2_closedloop.py"
    model_dir = CFG.universal_root / "t3" / "models"
    selection = CFG.universal_root / "t3" / "selection.json"
    recovery_freeze = CFG.universal_root / "d3_recovery" / "freeze.json"
    required = [protocol, module, closed_loop, selection, recovery_freeze]
    required += [model_dir / f"{name}.npz" for name in ("K0", "K1", "K4", "K5-linear")]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        write_json(stage / "failed.json", {"status": "failed", "missing": missing})
        append_solution("T0输入缺失", missing, ["项目同步或路径不完整"], ["恢复原冻结工件后重跑T0"], "冻结输入未齐全，不能进入D4。")
        return False
    artifacts = {name: _artifact(model_dir / f"{src}.npz") for name, src in
                 (("K0", "K0"), ("K1", "K1"), ("K4", "K4"), ("K5F2", "K5-linear"))}
    select = json.loads(selection.read_text(encoding="utf-8"))
    k5 = select["backbones"]["K5-linear"]
    closed_hash = sha256(closed_loop)
    checks = {
        "closed_loop_hash": closed_hash == EXPECTED_CLOSED_LOOP_SHA256,
        "k5_validation_variant_is_f2": k5.get("validation_selected") == "F2",
        "k5_bfh_is_recorded_f0": k5.get("BFH_force_head") == "F0",
        "artifact_shapes": all(v["arrays"].get("coef") == [63, 8] for v in artifacts.values()),
    }
    protocol_hash = sha256(protocol)
    resolved_config = {**asdict(CFG), "koopman_root": str(CFG.koopman_root),
                       "rated_force_n": float(gen.base.ConnectorParams().rated_force_n),
                       "ultimate_force_n": float(gen.base.ConnectorParams().ultimate_force_n),
                       "plant_dt_s": float(gen.base.PLANT_DT), "protocol_sha256": protocol_hash}
    write_json(OUT / "resolved_config.json", resolved_config)
    write_json(stage / "legacy_api.json", {"universal_v2_modules": _api(module), "closed_loop": _api(closed_loop)})
    write_json(stage / "expert_artifacts.json", {
        "experts": artifacts,
        "K5F2_variant_boundary": "validation-selected F2 diagnostic head; BFH remained F0",
        "selection_sha256": sha256(selection),
    })
    inputs = {p.name: {"path": str(p), "sha256": sha256(p)} for p in required}
    write_json(stage / "input_freeze.json", {"status": "frozen", "checks": checks, "inputs": inputs,
               "python": sys.executable, "platform": platform.platform(), "protocol_sha256": protocol_hash})
    # The protocol explicitly allows T1--T6 to continue when the historical
    # closed-loop source hash cannot be located; only T7 is blocked by it.
    accepted = all(value for key, value in checks.items() if key != "closed_loop_hash")
    if complete.exists() and not json.loads(complete.read_text(encoding="utf-8")).get("accepted"):
        initial = stage / "complete_initial_failed.json"
        if not initial.exists():
            shutil.copy2(complete, initial)
    write_json(complete, {"stage": "T0", "accepted": accepted, "checks": checks,
                          "offline_t1_t6_allowed": accepted,
                          "t7_closed_loop_allowed": bool(checks["closed_loop_hash"]),
                          "input_freeze_sha256": sha256(stage / "input_freeze.json")})
    append_log("C001", "T0冻结与接口审计", [f"accepted={accepted}；checks={checks}。",
               "K5F2显式标注为validation-selected diagnostic F2；未改写BFH=F0事实。",
               f"protocol={protocol_hash}；input_freeze={sha256(stage/'input_freeze.json')}。"])
    if not checks["closed_loop_hash"]:
        append_solution("R03/T7冻结闭环源hash未找到",
                        [f"预注册hash={EXPECTED_CLOSED_LOOP_SHA256}", f"当前同名脚本hash={closed_hash}",
                         "revision_2026下递归检索未找到预注册hash"],
                        ["同名脚本在T8后增加了参数扩展逻辑，或原冻结版本未归档；不能仅凭文件名认定同一版本"],
                        ["按协议继续离线T1--T6", "T7前只允许恢复精确hash或用已冻结plant接口新建适配器并做逐元素回归"],
                        "不影响离线组合验证；在精确源或等价回归证据补齐前，T7标记blocked_missing_frozen_closed_loop_source。")
    return accepted


SCENES = ("E0", "E1", "E2", "E3", "E4", "E5", "E6", "E9")
SPLITS = (("train", 20), ("validation", 8), ("development-test", 8))


def d4_jobs() -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for scene_index, scene in enumerate(SCENES):
        offset = 0
        for split, count in SPLITS:
            for local in range(count):
                seed = 1100000 + scene_index * 1000 + offset + local
                jobs.append({"scenario": scene, "physical_scene": scene, "traj_id": seed, "seed": seed,
                             "split": split, "external": False, "parameter_external": False,
                             "network_profile": "clean", "network_trace_id": "clean"})
            offset += 100
    return jobs


def _generate_one(job: dict[str, Any], scales: dict[str, Any], output: str) -> dict[str, Any]:
    arrays, metadata = gen.simulate(job, scales)
    path = Path(output)
    np.savez_compressed(path, **arrays, metadata_json=np.asarray(json.dumps(metadata, ensure_ascii=False)))
    return {**job, "file": path.name, "sha256": sha256(path), "steps": int(metadata["steps"]),
            "max_connector_force_n": float(metadata["max_connector_force_n"]),
            "rated_exceeded_steps": int(metadata["rated_exceeded_steps"]),
            "ultimate_exceeded_steps": int(metadata["ultimate_exceeded_steps"]), "finite": bool(metadata["finite"])}


def _source_seed_set() -> set[int]:
    seeds: set[int] = set()
    for path in (CFG.universal_root / "d3_recovery" / "freeze.json", CFG.universal_root / "t8" / "job_manifest.json"):
        if not path.exists(): continue
        data = json.loads(path.read_text(encoding="utf-8"))
        def walk(x: Any) -> None:
            if isinstance(x, dict):
                if "seed" in x:
                    try: seeds.add(int(x["seed"]))
                    except (TypeError, ValueError): pass
                for v in x.values(): walk(v)
            elif isinstance(x, list):
                for v in x: walk(v)
        walk(data)
    return seeds


def t1_generate() -> bool:
    if not t0_freeze(): return False
    complete = D4 / "complete.json"
    if complete.exists():
        return bool(json.loads(complete.read_text(encoding="utf-8")).get("accepted"))
    trajectories = D4 / "trajectories"
    trajectories.mkdir(parents=True, exist_ok=True)
    jobs = d4_jobs()
    collisions = sorted({j["seed"] for j in jobs} & _source_seed_set())
    if collisions:
        write_json(D4 / "failed.json", {"status": "seed_collision", "seeds": collisions})
        return False
    scales = gen.train_scales(cp.DATA)
    freeze = {"status": "frozen_before_generation", "jobs": jobs, "scales": scales,
              "generator_sha256": sha256(KOOPMAN / "generate_compare.py"),
              "base_generator_sha256": sha256(KOOPMAN / "generate_k2.py")}
    write_json(D4 / "freeze.json", freeze)
    pending = []
    completed: list[dict[str, Any]] = []
    for job in jobs:
        path = trajectories / f"{job['split']}_{job['scenario']}_{job['seed']}.npz"
        if path.exists():
            with np.load(path, allow_pickle=False) as source:
                meta = json.loads(str(source["metadata_json"].item()))
            completed.append({**job, "file": path.name, "sha256": sha256(path), "steps": int(meta["steps"]),
                              "max_connector_force_n": float(meta["max_connector_force_n"]),
                              "rated_exceeded_steps": int(meta["rated_exceeded_steps"]),
                              "ultimate_exceeded_steps": int(meta["ultimate_exceeded_steps"]), "finite": bool(meta["finite"])})
        else:
            pending.append((job, scales, str(path)))
    failures: list[dict[str, Any]] = []
    workers = min(8, max(1, (os.cpu_count() or 4) // 2))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_generate_one, *item): item for item in pending}
        for index, future in enumerate(as_completed(futures), 1):
            item = futures[future]
            try: completed.append(future.result())
            except Exception as exc: failures.append({"job": item[0], "error": repr(exc)})
            if index % 8 == 0 or index == len(pending):
                print(f"D4 internal {len(completed)}/{len(jobs)} failures={len(failures)}", flush=True)
                write_json(D4 / "progress.json", {"completed": completed, "failures": failures})
    completed.sort(key=lambda r: (r["split"], r["scenario"], r["seed"]))
    rated = float(gen.base.ConnectorParams().rated_force_n)
    high = sum(int(r["max_connector_force_n"] >= 0.8 * rated) for r in completed)
    accepted = len(completed) == len(jobs) and not failures and all(r["finite"] and r["ultimate_exceeded_steps"] == 0 for r in completed)
    write_json(D4 / "manifest.json", {"accepted": accepted, "planned": len(jobs), "trajectories": completed, "failures": failures})
    write_json(D4 / "coverage.json", {"trajectories": len(completed), "high_load_trajectory_count": high,
               "high_load_definition": ">=0.8 rated", "high_load_gate_trainable": False,
               "note": "L4 non-overlap windows are counted after T2 cache; no high-load claim is made here."})
    write_json(complete, {"stage": "T1-internal", "accepted": accepted, "completed": len(completed),
                          "failed": len(failures), "manifest_sha256": sha256(D4 / "manifest.json")})
    append_log("C002", "T1 D4内部数据生成", [f"planned={len(jobs)} completed={len(completed)} failures={len(failures)} accepted={accepted}。",
               f"0.8 rated以上轨迹={high}；L4窗需T2按不重叠20步重新核算。",
               f"manifest={sha256(D4/'manifest.json')}；未替换失败seed。"])
    if failures:
        append_solution("T1轨迹生成失败", [f"失败{len(failures)}条，完整记录于d4/manifest.json"],
                        ["plant安全门、数值异常或进程执行错误"], ["只修实现问题并按原seed重跑"],
                        "T1未完整通过，不进入selector训练。")
    return accepted


def t2_cache() -> bool:
    import offline
    return offline.t2_cache(sys.modules[__name__])


def t3_selector() -> bool:
    import offline
    return offline.t3_selector(sys.modules[__name__])


def t4_development() -> bool:
    import offline
    return offline.t4_development(sys.modules[__name__])


def t9_report() -> bool:
    import report
    return report.run(sys.modules[__name__])


STAGES = {
    "t0-freeze": t0_freeze,
    "t1-d4-generate": t1_generate,
    "t2-cache": t2_cache,
    "t3-selector": t3_selector,
    "t4-offline-development": t4_development,
    "t9-report": t9_report,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=tuple(STAGES), required=True)
    args = parser.parse_args()
    ok = STAGES[args.stage]()
    if not ok: raise SystemExit(2)


if __name__ == "__main__":
    main()
