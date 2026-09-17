"""Read-only D2 audit of the stopped RTX 5080 qualification boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    if protocol.get("scope") != "D2_GPU_RUNTIME_BLOCKER_READ_ONLY":
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

    ipc_path = paper / "src/paper_v4_core/gpu_port/ipc_backend.py"
    worker_path = paper / "src/paper_v4_core/gpu_port/gpu_worker.py"
    qualifier_path = paper / "tools/gpu_g0_g2_qualify.py"
    ipc = ipc_path.read_text(encoding="utf-8")
    worker = worker_path.read_text(encoding="utf-8")
    qualifier = qualifier_path.read_text(encoding="utf-8")

    env_root = Path(r"E:\anaconda\envs\pytorch_new")
    libomp = env_root / "Library/bin/libomp.dll"
    libiomp_env = env_root / "Library/bin/libiomp5md.dll"
    libiomp_torch = env_root / "Lib/site-packages/torch/lib/libiomp5md.dll"

    checks = {
        "worker_has_no_explicit_numpy_import": "import numpy" not in worker,
        "initial_model_mapping_uses_lists": "payload_anchors\": np.asarray" in ipc and ".tolist()" in ipc,
        "g1_rhs_request_uses_numpy_array": '"state": np.asarray(state, float)' in ipc,
        "g1_rk4_request_uses_numpy_array": '"controls": np.asarray(controls, float)' in ipc,
        "g1_rollout_request_uses_numpy_array": '"z": np.asarray(z, float)' in ipc,
        "g2_linearize_request_contains_numpy_arrays": '"state_steps": state_steps' in ipc and '"control_steps": control_steps' in ipc,
        "libomp_dll_present": libomp.is_file(),
        "environment_libiomp_dll_present": libiomp_env.is_file(),
        "torch_libiomp_dll_present": libiomp_torch.is_file(),
        "qualifier_uses_invalid_ndarray_square": "error.square()" in qualifier,
    }
    payload_violation = all(
        checks[name]
        for name in (
            "g1_rhs_request_uses_numpy_array",
            "g1_rk4_request_uses_numpy_array",
            "g1_rollout_request_uses_numpy_array",
            "g2_linearize_request_contains_numpy_arrays",
        )
    )
    dual_runtime_present = checks["libomp_dll_present"] and (
        checks["environment_libiomp_dll_present"] or checks["torch_libiomp_dll_present"]
    )
    report = {
        "status": "PASS_READ_ONLY_BLOCKER_LOCALIZED",
        "scope": protocol["scope"],
        "observed_prior_failure": "G0 PASS; G1 NOT_RUN; OMP Error #15 libomp.dll versus libiomp5md.dll",
        "checks": checks,
        "inference": {
            "classification": "LIKELY_ROOT_CAUSE_STATIC_AND_TIMING_NOT_YET_INTERVENTION_PROVEN",
            "candidate": "NumPy ndarray objects remain in outbound pickle requests, so the pure-Torch worker boundary is incomplete and NumPy can be imported during unpickle at the first G1 request.",
            "timing_consistency": "G0 initialization uses list/scalar model data and passes; G1 is the first ndarray-bearing request and is where the prior run stopped.",
            "dual_openmp_files_present": dual_runtime_present,
        },
        "latent_next_error": {
            "present": checks["qualifier_uses_invalid_ndarray_square"],
            "candidate_failure": "error_stats calls ndarray.square(), which is unavailable in the active NumPy 2.0.1 environment.",
        },
        "minimal_candidate_changes_not_applied": [
            "Convert every outbound ndarray in rhs/rk4/rollout/linearize IPC requests to nested Python lists before pickle serialization.",
            "Replace error.square() with np.square(error) in the qualification-only RMSE calculation.",
        ],
        "software_installed": False,
        "gpu_qualification_executed": False,
        "dynamics_or_closed_loop_executed": False,
        "source_modified_by_this_audit": False,
        "decision": "ENGINEERING_FIX_REQUIRED_BUT_REPAIR_BUDGET_NOT_REOPENED; STOP_BEFORE_G1_G2_G3",
    }
    (output / "d2_runtime_blocker_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    labels = ["G0 list init", "G1 list IPC", "single OMP", "RMSE API", "repair auth"]
    values = [1, 0 if payload_violation else 1, 0 if dual_runtime_present else 1, 0 if checks["qualifier_uses_invalid_ndarray_square"] else 1, 0]
    colors = ["#2ca02c" if value else "#d62728" for value in values]
    fig, axis = plt.subplots(figsize=(10.5, 5.4))
    bars = axis.bar(labels, values, color=colors)
    axis.set_ylim(0, 1.25)
    axis.set_ylabel("Qualification prerequisite (1 = satisfied)")
    axis.set_title("D2 RTX 5080 qualification blocker audit — no GPU execution")
    axis.grid(axis="y", alpha=0.2)
    for bar, value in zip(bars, values):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            0.08 if not value else 0.5,
            "PASS" if value else "BLOCKED",
            ha="center",
            color="white" if value else "#8b0000",
            fontweight="bold",
        )
    fig.text(0.02, 0.01, "Static/timing inference only; the candidate cause is not proven until a separately authorized fix and rerun.", fontsize=10)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    figures = []
    for suffix in ("png", "svg"):
        name = f"d2_runtime_blocker_audit.{suffix}"
        fig.savefig(output / name, dpi=220 if suffix == "png" else None)
        figures.append(name)
    plt.close(fig)

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "figures": figures,
        "source_files": [
            {"path": str(paper / item["path"]), "sha256": item["sha256"]}
            for item in protocol["identity_files"]
        ] + [{"path": str(protocol_path), "sha256": sha(protocol_path)}],
        "result_files": [
            {"path": "d2_runtime_blocker_audit.json", "sha256": sha(output / "d2_runtime_blocker_audit.json")}
        ],
        "claim_boundary": "No source fix, GPU qualification, dynamics, or closed loop was executed.",
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "README.md").write_text(
        "# D2 GPU运行库阻断只读审计\n\n"
        "本目录只检查现有源码、旧失败记录与本机DLL存在性。结论是高可信候选根因，不是修复后动态证明；没有安装软件、修改GPU后端、运行G1/G2或启动闭环。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "decision": report["decision"], "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
