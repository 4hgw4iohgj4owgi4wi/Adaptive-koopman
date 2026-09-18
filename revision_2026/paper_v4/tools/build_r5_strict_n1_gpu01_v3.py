"""Freeze the current GPU01 strict R5-N1 protocol after S4 evidence exists.

The historical v2 protocol is never overwritten.  This builder refuses to
write unless the N0 run, its 35-item audit, its current figure manifest, and
the strict no-op report/figure all pass and agree on protocol identity.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


PAPER = Path(__file__).resolve().parents[1]
OLD_PROTOCOL = PAPER / "protocol/R5_STRICT_N1_GPU_20260918_v2.json"
OLD_PROTOCOL_EXPECTED_SHA = "6180b51112bc3a8ee3d778e875ee5d9febc3deaad954bdb47a2a24b0bf4c39ed"
N0_PROTOCOL = PAPER / "protocol/R5_STRICT_N0_GPU_20260918_v2.json"
N0_RUN = PAPER / "results/20260917_R5_STRICT_N0_GPU01"
NO_OP = PAPER / "analysis/20260918_R5_STRICT_N0_NO_OP_01"
TARGET = PAPER / "protocol/R5_STRICT_N1_GPU_20260918_v3.json"
TARGET_RUN_REL = "results/20260917_R5_STRICT_N1_GPU01"
BUILDER_REL = "tools/build_r5_strict_n1_gpu01_v3.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(PAPER.resolve())).replace("\\", "/")


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError("PARENT_EVIDENCE_MISSING:" + rel(path))
    return json.loads(path.read_text(encoding="utf-8"))


def identity(paths: list[str]) -> list[dict]:
    records: list[dict] = []
    for item in dict.fromkeys(paths):
        path = PAPER / item
        if not path.is_file():
            raise FileNotFoundError("IDENTITY_FILE_MISSING:" + item)
        records.append({"path": item, "sha256": sha(path)})
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=TARGET)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    target = args.out.resolve()
    if target.exists():
        raise FileExistsError("REFUSING_TO_OVERWRITE_PROTOCOL:" + rel(target))
    if (PAPER / TARGET_RUN_REL).exists():
        raise FileExistsError("REFUSING_TO_REUSE_RESULT_OUTPUT:" + TARGET_RUN_REL)
    if sha(OLD_PROTOCOL) != OLD_PROTOCOL_EXPECTED_SHA:
        raise ValueError("OLD_N1_V2_IDENTITY_DRIFT")

    n0_protocol_sha = sha(N0_PROTOCOL)
    n0_metrics_path = N0_RUN / "metrics.json"
    n0_raw_path = N0_RUN / "raw.npz"
    n0_audit_path = N0_RUN / "single_run_audit.json"
    n0_figure_path = N0_RUN / "figures/figure_manifest.json"
    no_op_path = NO_OP / "no_op.json"
    no_op_figure_path = NO_OP / "figure_manifest.json"

    metrics = read_json(n0_metrics_path)
    audit = read_json(n0_audit_path)
    figure = read_json(n0_figure_path)
    no_op = read_json(no_op_path)
    no_op_figure = read_json(no_op_figure_path)
    if metrics.get("status") != "COMPLETED" or metrics.get("iterations") != 2379:
        raise ValueError("PARENT_N0_NOT_COMPLETED_2379")
    if metrics.get("protocol_sha256") != n0_protocol_sha:
        raise ValueError("PARENT_N0_PROTOCOL_IDENTITY_MISMATCH")
    if audit.get("status") != "PASS_SINGLE_RUN_AUDIT" or (
        audit.get("items_passed"), audit.get("items_total")
    ) != (35, 35):
        raise ValueError("PARENT_N0_AUDIT_NOT_35_OF_35_PASS")
    if figure.get("figure_status") != "PASS_VISUAL_QA":
        raise ValueError("PARENT_N0_FIGURE_NOT_PASS")
    if no_op.get("status") != "PASS_R5_STRICT_N0_NO_OP":
        raise ValueError("PARENT_N0_NO_OP_NOT_PASS")
    if no_op.get("protocol_sha256") != n0_protocol_sha:
        raise ValueError("PARENT_N0_NO_OP_PROTOCOL_IDENTITY_MISMATCH")
    if no_op.get("maximum_absolute_difference") != 0.0:
        raise ValueError("PARENT_N0_NO_OP_NOT_EXACT")
    if no_op_figure.get("figure_status") != "PASS_VISUAL_QA":
        raise ValueError("PARENT_N0_NO_OP_FIGURE_NOT_PASS")

    data = copy.deepcopy(read_json(OLD_PROTOCOL))
    data["protocol_id"] = "R5-STRICT-N1-GPU-strict-solver-v3-parent-evidence"
    data["authorization"] = (
        "R5_STRICT_CHAIN_EXECUTION_20260917.md stage S5, released only after "
        "the current GPU01 N0 audit, figure QA, exact no-op gate and no-op figure QA pass."
    )
    data["strict_chain"]["stage"] = "S5"
    data["strict_chain"]["readiness"] = "READY_TO_START_AFTER_READ_ONLY_HOST_PREFLIGHT"
    data["strict_chain"]["n0_parent_evidence"] = {
        "protocol": {"path": rel(N0_PROTOCOL), "sha256": n0_protocol_sha},
        "metrics": {"path": rel(n0_metrics_path), "sha256": sha(n0_metrics_path),
                    "status": metrics["status"], "iterations": metrics["iterations"]},
        "raw": {"path": rel(n0_raw_path), "sha256": sha(n0_raw_path)},
        "audit": {"path": rel(n0_audit_path), "sha256": sha(n0_audit_path),
                  "status": audit["status"], "items": "35/35"},
        "figure_manifest": {"path": rel(n0_figure_path), "sha256": sha(n0_figure_path),
                            "figure_status": figure["figure_status"]},
        "no_op": {"path": rel(no_op_path), "sha256": sha(no_op_path),
                  "status": no_op["status"],
                  "maximum_absolute_difference": no_op["maximum_absolute_difference"]},
        "no_op_figure_manifest": {
            "path": rel(no_op_figure_path), "sha256": sha(no_op_figure_path),
            "figure_status": no_op_figure["figure_status"],
        },
    }
    data["supersedes_protocol"] = {
        "path": rel(OLD_PROTOCOL),
        "sha256": sha(OLD_PROTOCOL),
        "reason": (
            "v2 was frozen before S4 completed and did not pin the N0 audit, current "
            "N0 figure, exact no-op report or no-op figure manifest required by the strict chain."
        ),
    }
    identity_paths = [str(item["path"]) for item in data.get("identity_files", [])]
    identity_paths.extend(
        [
            BUILDER_REL,
            "tools/r5_strict_no_op_gate.py",
            rel(N0_PROTOCOL),
            rel(n0_metrics_path),
            rel(n0_raw_path),
            rel(n0_audit_path),
            rel(n0_figure_path),
            rel(no_op_path),
            rel(no_op_figure_path),
        ]
    )
    data["identity_files"] = identity(identity_paths)

    summary = {
        "protocol": rel(target),
        "run": TARGET_RUN_REL,
        "identity_files": len(data["identity_files"]),
        "parent_n0_audit": audit["status"],
        "parent_n0_no_op": no_op["status"],
        "dry_run": bool(args.dry_run),
    }
    if args.dry_run:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary["protocol_sha256"] = sha(target)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
