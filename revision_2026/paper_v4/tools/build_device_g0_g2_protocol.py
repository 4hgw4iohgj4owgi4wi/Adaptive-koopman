"""Build a device-specific G0-G2 protocol for the three-host workflow.

This builder never overwrites a protocol.  It reads the registered RTX 5080 v5
protocol only as a gate/input template, replaces the device identity, and
rehashes every current source and fixed input used by the generic qualifier.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import re
from pathlib import Path


PAPER = Path(__file__).resolve().parents[1]
REFERENCE_PROTOCOL = PAPER / "protocol/RTX5080_G0_G2_20260915_v5.json"
BUILDER_REL = "tools/build_device_g0_g2_protocol.py"
QUALIFIER_REL = "tools/gpu_g0_g2_qualify_device.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(PAPER.resolve())).replace("\\", "/")


def normalized_device_name(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


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
    parser.add_argument("--device-tag", choices=("RTX5080", "RTX5060", "RTX3050"), required=True)
    parser.add_argument("--host-tag", required=True)
    parser.add_argument("--phase", choices=("DEV_PRE_V2", "V2_FORMAL"), required=True)
    parser.add_argument("--date", default="20260918")
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--taskbook", required=True,
                        help="paper_v4-relative host taskbook path to pin")
    parser.add_argument("--protocol-out", default=None)
    parser.add_argument("--result-out", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.version < 1:
        raise ValueError("VERSION_MUST_BE_POSITIVE")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.host_tag):
        raise ValueError("HOST_TAG_MALFORMED")

    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA_NOT_AVAILABLE")
    actual_device = torch.cuda.get_device_name(0)
    if args.device_tag not in normalized_device_name(actual_device):
        raise RuntimeError(
            f"DEVICE_FAMILY_MISMATCH: expected {args.device_tag}, got {actual_device}"
        )

    taskbook = PAPER / args.taskbook
    if not taskbook.is_file():
        raise FileNotFoundError("TASKBOOK_MISSING:" + args.taskbook)
    if not REFERENCE_PROTOCOL.is_file():
        raise FileNotFoundError("REFERENCE_PROTOCOL_MISSING")

    protocol_rel = args.protocol_out or (
        f"protocol/{args.device_tag}_G0_G2_{args.date}_{args.phase}_v{args.version}.json"
    )
    result_rel = args.result_out or (
        f"results/{args.date}_{args.host_tag}_G0_G2_{args.phase}_{args.version:02d}"
    )
    protocol_path = PAPER / protocol_rel
    result_path = PAPER / result_rel
    if protocol_path.exists():
        raise FileExistsError("REFUSING_TO_OVERWRITE_PROTOCOL:" + protocol_rel)
    if result_path.exists():
        raise FileExistsError("REFUSING_TO_REUSE_RESULT_OUTPUT:" + result_rel)

    base = json.loads(REFERENCE_PROTOCOL.read_text(encoding="utf-8"))
    data = copy.deepcopy(base)
    data["protocol_id"] = (
        f"{args.device_tag}-G0-G2-{args.phase}-v{args.version}-three-host"
    )
    data["authorization"] = (
        "experiment.md section 61 and the pinned per-host taskbook; fixed-sample "
        "G0-G2 only, with no closed-loop or full-route authorization."
    )
    data["scope"] = "GPU_DEVICE_G0_G2_ONLY_NO_CLOSED_LOOP"
    data["output"] = result_rel
    data["device_label"] = args.device_tag
    data["host_tag"] = args.host_tag
    data["phase"] = args.phase
    data["formal_qualification"] = args.phase == "V2_FORMAL"
    data["status_note"] = (
        "V2_FORMAL_DEVICE_QUALIFICATION"
        if args.phase == "V2_FORMAL"
        else "DEV_PRE_V2 / NOT_A_FORMAL_QUALIFICATION_UNTIL_V2"
    )
    data["claim_boundary"] = (
        "Fixed-sample environment, physics and QP qualification for this exact device. "
        "It does not execute a closed loop or establish a paper control result."
    )
    data["related_reference_qualification"] = {
        "path": rel(REFERENCE_PROTOCOL),
        "sha256": sha(REFERENCE_PROTOCOL),
        "relation": "gate and input template only; not a parent qualification for this device",
    }
    for key in ("supersedes_protocol", "engineering_history", "repair_authorization"):
        data.pop(key, None)

    data["preconditions_verified_at_freeze"] = {
        "host": platform.node(),
        "torch_device_name": actual_device,
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "cuda_available": True,
        "phase": args.phase,
        "result_output_absent": True,
    }
    data["g0"]["required_device_name"] = actual_device
    data["g0"]["required_cuda_available"] = True
    data["g0"]["required_dtype"] = "torch.float64"
    data["g0"]["required_single_process_single_device"] = True
    data["gates"]["performance"]["interpretation"] = (
        "Performance controls scheduling only.  A slow device remains a numerical PASS "
        "when G0-G2 numerical gates pass, and the timing must be reported unchanged."
    )

    identity_paths = []
    for item in base.get("identity_files", []):
        path = str(item["path"])
        if path == "tools/gpu_g0_g2_qualify.py":
            path = QUALIFIER_REL
        identity_paths.append(path)
    identity_paths.extend(
        [
            BUILDER_REL,
            rel(taskbook),
            rel(REFERENCE_PROTOCOL),
        ]
    )
    data["authorization_documents_at_freeze"] = [
        {"path": rel(taskbook), "sha256": sha(taskbook)},
        {"path": "experiment.md", "section": 61,
         "note": "rolling status document; not included in identity_files"},
    ]
    data["identity_files"] = identity(identity_paths)

    summary = {
        "protocol": protocol_rel,
        "result": result_rel,
        "host": platform.node(),
        "device": actual_device,
        "phase": args.phase,
        "identity_files": len(data["identity_files"]),
        "dry_run": bool(args.dry_run),
    }
    if args.dry_run:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    protocol_path.parent.mkdir(parents=True, exist_ok=True)
    protocol_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary["protocol_sha256"] = sha(protocol_path)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
