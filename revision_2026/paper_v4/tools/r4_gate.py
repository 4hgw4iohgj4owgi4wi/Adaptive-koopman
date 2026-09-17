"""R4 C1 gate: link the six cells and the four decisive comparisons into one verdict.

Task-book section 4: "每参数点r4_parameter_pair.json；最后r4_gate.json逐一链接六条与两组
比较。总PASS要求全齐，不能只以6个COMPLETED计数。"

The gate therefore does not count completions: it checks, per cell, that the audit file
exists and passes, that metrics report COMPLETED, that the run's protocol still matches a
frozen file, and that the run's figures are delivered and QA-passed; and per parameter
point, that both step comparisons exist and pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CELLS = [
    {"parameter": "P1", "step_ms": 2.0, "run": "results/20260915_R4_P1_2MS_GPU01"},
    {"parameter": "P1", "step_ms": 1.0, "run": "results/20260915_R4_P1_1MS_GPU01"},
    {"parameter": "P1", "step_ms": 0.5, "run": "results/20260915_R4_P1_0P5MS_GPU01"},
    {"parameter": "P2", "step_ms": 2.0, "run": "results/20260915_R4_P2_2MS_GPU01"},
    {"parameter": "P2", "step_ms": 1.0, "run": "results/20260915_R4_P2_1MS_GPU02"},
    {"parameter": "P2", "step_ms": 0.5, "run": "results/20260915_R4_P2_0P5MS_GPU01"},
]

PAIR_STEPS = [(2.0, 1.0), (1.0, 0.5)]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_pairs(paper: Path) -> dict:
    found = {}
    for path in sorted((paper / "analysis").glob("*/r4_convergence_*ms_to_*ms.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        found[(report.get("parameter_id"), float(report["coarse_step_ms"]), float(report["fine_step_ms"]))] = path
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paper = Path(__file__).resolve().parents[1]
    protocol_path = args.protocol.resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("scope") != "R4_C1_GATE":
        raise ValueError("SCOPE_MISMATCH")
    for item in protocol["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    output = args.out.resolve()
    if output != (paper / protocol["output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)

    frozen_hashes = {}
    for path in sorted((paper / "protocol").glob("*.json")):
        frozen_hashes.setdefault(sha(path), str(path.relative_to(paper)).replace("\\", "/"))
    pairs = discover_pairs(paper)

    cell_records = []
    for cell in CELLS:
        run = paper / cell["run"]
        audit_path = run / "single_run_audit.json"
        metrics_path = run / "metrics.json"
        figure_path = run / "figures" / "figure_manifest.json"
        record = dict(cell)
        record["audit_present"] = audit_path.is_file()
        record["audit_status"] = json.loads(audit_path.read_text(encoding="utf-8"))["status"] if record["audit_present"] else None
        record["audit_items"] = f"{json.loads(audit_path.read_text(encoding='utf-8'))['items_passed']}/{json.loads(audit_path.read_text(encoding='utf-8'))['items_total']}" if record["audit_present"] else None
        record["audit_sha256"] = sha(audit_path) if record["audit_present"] else None
        metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else None
        record["execution_status"] = metrics["status"] if metrics else None
        record["ticks"] = f"{metrics['iterations']}/{metrics['expected_iterations']}" if metrics else None
        record["route_complete"] = bool(metrics and metrics["reference_distance_m"] >= metrics["route_length_m"] - 1e-9)
        record["hard_gates_hold"] = bool(metrics and metrics["maximum_point_force_n"] <= 15000.0 + 1e-6
                                         and metrics["maximum_tire_utilization"] <= 1.0 + 1e-9
                                         and metrics["minimum_support_load_n"] >= 0.0)
        record["protocol_file"] = frozen_hashes.get(metrics.get("protocol_sha256")) if metrics else None
        record["figure_status"] = json.loads(figure_path.read_text(encoding="utf-8"))["figure_status"] if figure_path.is_file() else None
        record["pass"] = bool(
            record["audit_status"] == "PASS_SINGLE_RUN_AUDIT"
            and record["execution_status"] == "COMPLETED"
            and record["route_complete"]
            and record["hard_gates_hold"]
            and record["protocol_file"]
            and record["figure_status"] == "PASS_VISUAL_QA"
        )
        cell_records.append(record)

    pair_records = []
    for parameter in ("P1", "P2"):
        pair_file = {
            "parameter_id": parameter,
            "cells": [{key: value for key, value in record.items() if key in ("step_ms", "run", "pass", "audit_items", "ticks")}
                      for record in cell_records if record["parameter"] == parameter],
            "comparisons": [],
        }
        for from_ms, to_ms in PAIR_STEPS:
            path = pairs.get((parameter, from_ms, to_ms))
            entry = {"from_ms": from_ms, "to_ms": to_ms}
            if path is None:
                entry.update({"status": "MISSING", "pass": False})
            else:
                report = json.loads(path.read_text(encoding="utf-8"))
                entry.update({
                    "status": report["status"],
                    "pass": all(report["verdicts"].values()),
                    "report": str(path.relative_to(paper)).replace("\\", "/"),
                    "sha256": sha(path),
                    "measurements": report["measurements"],
                })
            pair_file["comparisons"].append(entry)
        pair_file["pass"] = bool(all(entry["pass"] for entry in pair_file["comparisons"])
                                 and all(cell["pass"] for cell in pair_file["cells"]))
        target = output / f"r4_parameter_pair_{parameter}.json"
        target.write_text(json.dumps(pair_file, indent=2, ensure_ascii=False), encoding="utf-8")
        pair_records.append({"parameter_id": parameter, "pass": pair_file["pass"],
                             "file": target.name, "sha256": sha(target)})

    all_cells = all(record["pass"] for record in cell_records)
    all_pairs = all(record["pass"] for record in pair_records)
    gate = {
        "status": "PASS_C1_R4_TOTAL" if (all_cells and all_pairs) else "FAIL_C1_R4_TOTAL",
        "scope": protocol["scope"],
        "rule": "Task-book section 4: the total PASS requires every listed product; six COMPLETED cells alone are not sufficient and are not counted as a PASS.",
        "cells_checked": len(cell_records),
        "cells_passed": sum(1 for record in cell_records if record["pass"]),
        "cells": cell_records,
        "parameter_points": pair_records,
        "required_products": {
            "per_cell": ["raw.npz", "substeps.npz", "solver.jsonl", "metrics.json", "single_run_audit.json", "figures/figure_manifest.json with figure_status PASS"],
            "per_parameter_point": ["r4_parameter_pair_{P1,P2}.json linking the 2-to-1 ms and 1-to-0.5 ms comparisons"],
            "total": ["r4_gate.json linking the six cells and both parameter points"],
        },
        "not_counted_as_pass": [
            "a cell that merely reports COMPLETED",
            "a comparison that exists but has a failing verdict",
            "a cell whose figures are missing or not QA-passed",
            "a cell whose protocol no longer matches a frozen protocol file",
        ],
        "what_this_releases": "With the total PASS, R5 (the legal-information interface batch, where P0 first runs) and the nine actuator segments have their registered prerequisites satisfied; this gate does not itself release review-level claims.",
        "claim_boundary": "R4 is a numerical and physical coverage diagnostic on the centralised full-state upper bound. Passing it does not validate P0/P0N/K0/K0N/K1/K1N as methods, does not establish distributed or communication-robust behaviour, and does not make the P1 late tracking deviation acceptable.",
        "protocol_sha256": sha(protocol_path),
    }
    (output / "r4_gate.json").write_text(json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "README.md").write_text(
        "# R4 / C1 总门\n\n"
        "按详细任务书§4「总PASS要求全齐，**不能只以6个COMPLETED计数**」实现：\n\n"
        "- **逐条**：`single_run_audit.json` 必须存在且为 `PASS_SINGLE_RUN_AUDIT`（21项）、metrics 必须 `COMPLETED`、"
        "必须跑满全长、原硬门必须通过、该run的协议必须仍能匹配到冻结协议文件、`figures/figure_manifest.json` 的 "
        "`figure_status` 必须为 `PASS_VISUAL_QA`；\n"
        "- **每参数点**：`r4_parameter_pair_{P1,P2}.json` 链接 2→1 ms 与 1→0.5 ms 两组比较，两组都须PASS；\n"
        "- **总门**：`r4_gate.json` 逐一链接六条与两个参数点。\n\n"
        "**释放范围**：总PASS使 R5（合法信息接口，P0 首次登场）与执行器九短片段具备登记前置；"
        "本门**不**验证 P0/P0N/K0/K0N/K1/K1N 作为方法、不建立分布式或通信鲁棒结论，"
        "也**不**使 P1 的晚段跟踪偏离变得可接受。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": gate["status"], "cells_passed": gate["cells_passed"], "cells_checked": gate["cells_checked"],
                      "parameter_points": pair_records, "output": str(output)}, ensure_ascii=False))
    if gate["status"] != "PASS_C1_R4_TOTAL":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
