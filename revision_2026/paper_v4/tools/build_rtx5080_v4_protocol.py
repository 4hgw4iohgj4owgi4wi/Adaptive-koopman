"""Build the RTX 5080 G0-G2 v4 protocol file from verified on-disk identities.

Hand-transcribed SHA-256 values have already blocked this project twice (v1/v2 of
the force-window protocol were rejected by the identity gate before any
computation).  This builder reads the current hashes from disk, refuses to emit a
protocol if any listed file is missing, and writes the frozen JSON.

Usage:  python tools/build_rtx5080_v4_protocol.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]

# Enforced identities: immutable inputs only.  Documents that this same work
# revises (experiment.md, the migration task description) are recorded separately
# and are deliberately NOT enforced; gating them is what made v3 unusable.
IDENTITY_PATHS = [
    "src/paper_v4_core/gpu_port/__init__.py",
    "src/paper_v4_core/gpu_port/physics_torch.py",
    "src/paper_v4_core/gpu_port/rollout_batch.py",
    "src/paper_v4_core/gpu_port/gpu_worker.py",
    "src/paper_v4_core/gpu_port/ipc_backend.py",
    "tools/gpu_g0_g2_qualify.py",
    "src/paper_v4_core/controllers/physical_tracking_pilot.py",
    "src/paper_v4_core/controllers/parallel_fd_backend.py",
    "src/paper_v4_core/plant/four_vehicle_common.py",
    "src/paper_v4_core/plant/connector_adapter.py",
    "src/paper_v4_core/plant/connector_r3.py",
    "src/paper_v4_core/plant/internal_force.py",
    "src/paper_v4_core/plant/load_transfer.py",
    "src/paper_v4_core/e01_100m.py",
    "src/paper_v4_core/diagnostics/post_r3_r4_runner.py",
    "src/paper_v4_core/reference_geometry.py",
    "src/paper_v4_core/references.py",
    "results/20260915_R4_P1_2MS01/raw.npz",
    "results/20260915_R4_P1_2MS01/substeps.npz",
    "results/20260915_R4_P1_2MS01/solver.jsonl",
    "results/20260915_R4_P1_2MS01/status.json",
]

AUTHORIZATION_DOCUMENTS = [
    "experiment.md",
    "protocol/P1中断数据分析与RTX5080迁移任务说明_20260915.md",
]

FORBIDDEN_SOURCE_MARKERS = {
    "KMP_DUPLICATE_LIB_OK": "runtime-library workaround is forbidden",
    "float32": "dtype change is forbidden",
    "autograd": "autodiff is forbidden in this candidate",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    missing = [path for path in IDENTITY_PATHS + AUTHORIZATION_DOCUMENTS if not (PAPER / path).is_file()]
    if missing:
        raise SystemExit("MISSING_IDENTITY_INPUT:" + ",".join(missing))

    ipc_source = (PAPER / "src/paper_v4_core/gpu_port/ipc_backend.py").read_text(encoding="utf-8")
    worker_source = (PAPER / "src/paper_v4_core/gpu_port/gpu_worker.py").read_text(encoding="utf-8")
    qualifier_source = (PAPER / "tools/gpu_g0_g2_qualify.py").read_text(encoding="utf-8")

    # Static preconditions of the fix itself, checked before the protocol is frozen.
    preconditions = {
        "ipc_backend_converts_outbound_arrays": ipc_source.count("_nested_lists(") >= 6,
        "ipc_backend_has_no_raw_request_arrays": '"state": np.asarray' not in ipc_source
        and '"controls": np.asarray' not in ipc_source
        and '"z": np.asarray' not in ipc_source
        and '"state_steps": state_steps' not in ipc_source,
        "worker_has_module_audit": "def module_audit()" in worker_source and "worker_module_audit" in worker_source,
        "worker_has_no_explicit_numpy_import": "import numpy" not in worker_source,
        "qualifier_uses_np_square": "np.square(error)" in qualifier_source,
        "qualifier_has_no_ndarray_square": "error.square()" not in qualifier_source,
        "no_forbidden_runtime_workaround": not any(
            marker in ipc_source or marker in worker_source or marker in qualifier_source
            for marker in ("KMP_DUPLICATE_LIB_OK",)
        ),
        # v5: the measured root cause is a reply-path contamination, not the request path.
        "worker_sanitizes_reply_to_primitives": "def _plain(" in worker_source and "value = _plain(value)" in worker_source,
        "worker_rejects_non_primitive_replies": "NON_PRIMITIVE_IN_IPC_REPLY" in worker_source,
        "parent_guards_against_torch_contamination": "_assert_parent_free_of_torch" in ipc_source
        and "CUDA_PARENT_TORCH_CONTAMINATION" in ipc_source,
    }
    failed = [name for name, ok in preconditions.items() if not ok]
    if failed:
        raise SystemExit("PRECONDITION_FAILED:" + ",".join(failed))

    protocol = {
        "protocol_id": "RTX5080-G0-G2-v5-primitive-reply-boundary",
        "authorization": "User instruction 2026-09-15: continue with P1, reopen the engineering repair round, freeze the protocol, launch the qualification and report every 30 minutes.",
        "scope": "RTX5080_G0_G2_ONLY_NO_CLOSED_LOOP",
        "output": "results/20260915_RTX5080_G0_G2_05",
        "supersedes_protocol": {
            "path": "protocol/RTX5080_G0_G2_20260915_v4.json",
            "sha256": sha(PAPER / "protocol/RTX5080_G0_G2_20260915_v4.json"),
            "status": "FAILED_AND_SUPERSEDED",
            "failed_output": "results/20260915_RTX5080_G0_G2_04",
            "measured_failure": "G0 PASS and its figure written; the parent then aborted with OMP Error #15 (exit 3) on the first parent-side system_derivative call, i.e. before any G1 sample was completed.",
            "falsified_hypothesis": "The D2 audit's candidate root cause - NumPy ndarrays travelling from the parent to the worker in pickle requests - is falsified by measurement: the worker's own module audit reported numpy present at worker startup with an empty imported_after_startup list, so NumPy never entered via unpickling of requests.",
            "true_root_cause_measured": "torch.__version__ is a torch.torch_version.TorchVersion instance, a str subclass. Pickling it in the worker's environment reply stored a class reference, so the parent's pickle.loads imported the entire torch package into the CPU parent (718 modules), loading torch's OpenMP runtime beside the MKL runtime the parent already owns; the parent then aborted inside numpy.linalg.svd via internal_force._pinv -> connector_diagnostics -> system_derivative. faulthandler located the abort, and an __import__ trap located torch.torch_version as the entry point.",
            "previous_versions": {
                "v1": "in-process CUDA stopped by the dual OpenMP runtime before G1",
                "v2": "isolated worker reached G0 but the same conflict stopped the run before G1",
                "v3": "pure-Torch worker with list-return IPC; same conflict; protocol later invalidated by stale document identities",
            },
        },
        "engineering_history": {
            "v4": "array-free request path (nested lists) plus worker module audit plus np.square RMSE; measured insufficient, and it produced the evidence that falsified the registered root cause",
            "v5": "primitive-only reply boundary: the worker coerces every reply value to exact built-in primitives before pickling and rejects anything else, so no torch class reference can cross the boundary; the parent additionally asserts after every unpickle that no torch module appeared and raises CUDA_PARENT_TORCH_CONTAMINATION if one did",
        },
        "repair_authorization": {
            "round": 4,
            "granted_by": "user instruction on 2026-09-15 to continue and launch the experiment; round 4 was opened only after the round-3 change was measured to be insufficient and the true root cause was located by measurement",
            "changes_permitted": [
                "worker reply sanitizer to exact built-in primitives, with a hard rejection of anything else",
                "parent-side torch-contamination assertion after every unpickle",
                "the round-3 changes retained: array-free requests, worker module audit, np.square RMSE",
            ],
            "changes_forbidden": [
                "KMP_DUPLICATE_LIB_OK or any runtime-library bypass",
                "float32, AMP, autodiff, frozen Jacobian",
                "gate, threshold, tolerance, dtype, solver or controller modification",
                "closed loop, P1 resume or prefix splicing",
            ],
        },
        "candidate": {
            "name": "POST-R3-R4-CUDA-batched-FD-primitive-reply-boundary-v5",
            "dtype": "float64",
            "horizon": 20,
            "controller_step_s": 0.02,
            "predictor_step_s": 0.002,
            "batch_size": 85,
            "jacobian": "central finite difference at every horizon step",
            "runtime": "one CPU SciPy/OSQP parent plus one persistent NumPy-free Torch CUDA worker",
            "cpu_retained": ["event-substep true plant", "QP assembly", "OSQP", "nonlinear validation"],
            "forbidden": ["closed loop", "P1 resume", "float32", "AMP", "autodiff", "frozen Jacobian", "KMP_DUPLICATE_LIB_OK"],
        },
        "preconditions_verified_at_freeze": preconditions,
        "inputs": {
            "parameter_id": "P1",
            "partial_run": "results/20260915_R4_P1_2MS01",
            "g1_samples": ["straight", "curve_entry", "force_peak", "steering_limit", "near_gap_boundary", "late_prefix"],
            "g2_fixed_qp": ["initial", "force_bearing_vehicle1_x_plus_0.03m"],
        },
        "g0": {
            "required_device_name": "NVIDIA GeForce RTX 5080",
            "required_cuda_available": True,
            "required_dtype": "torch.float64",
            "required_single_process_single_device": True,
        },
        "gates": {
            "error_definition": "abs_error/(atol+rtol*abs(CPU_reference)); max normalized error <= 1",
            "g1_rhs": {"atol": 2e-9, "rtol": 2e-10, "maximum_normalized_error": 1.0},
            "g1_rk4": {"atol": 2e-11, "rtol": 2e-10, "maximum_normalized_error": 1.0},
            "g1_rollout": {"atol": 2e-10, "rtol": 2e-9, "maximum_normalized_error": 1.0},
            "g2_f0": {"atol": 2e-10, "rtol": 2e-9, "maximum_normalized_error": 1.0},
            "g2_jacobian": {"atol": 2e-7, "rtol": 2e-6, "maximum_normalized_error": 1.0},
            "g2_qp_matrix": {"atol": 1e-5, "rtol": 2e-5, "maximum_normalized_error": 1.0},
            "g2_qp_bounds": {"atol": 1e-7, "rtol": 1e-6, "maximum_normalized_error": 1.0},
            "first_control": {"acceleration_atol_mps2": 0.0001, "steering_atol_rad": 0.00001},
            "performance": {"baseline": "CPU parallel8 fixed-QP end-to-end", "must_be_faster_for_promotion": True, "original_budget_s": 5.0},
        },
        "stop_rules": {
            "engineering_repairs_used": 4,
            "further_engineering_failure": "stop and report; do not open a fifth round without explicit authorization",
            "g1_or_g2_numerical_failure": "stop without widening gates",
            "no_performance_benefit": "stop before G3/G4",
            "closed_loop_authorized": False,
        },
        "monitoring": {
            "cadence_minutes": 30,
            "report_fields": ["process alive", "elapsed", "last stdout line", "stderr content", "which G-stage is reached", "whether qualification.json exists"],
            "note": "G1/G2 are fixed-sample checks; the expected wall clock is minutes, not hours, so a missing output after the first interval is itself a finding.",
        },
        "identity_rule": "Only immutable inputs are enforced. Documents revised by the same work are recorded under authorization_documents_at_freeze and are not enforced, because enforcing them is exactly what invalidated v3.",
        "authorization_documents_at_freeze": [
            {"path": path, "sha256": sha(PAPER / path)} for path in AUTHORIZATION_DOCUMENTS
        ],
        "identity_files": [
            {"path": path, "sha256": sha(PAPER / path)} for path in IDENTITY_PATHS
        ],
        "deliverables": ["G0/G1/G2 JSON", "G0/G1/G2 PNG and SVG", "figure_manifest.json", "README.md", "Chinese execution record"],
    }

    target = PAPER / "protocol/RTX5080_G0_G2_20260915_v5.json"
    if target.exists():
        raise SystemExit("REFUSING_TO_OVERWRITE_PROTOCOL")
    target.write_text(json.dumps(protocol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "protocol": str(target.relative_to(PAPER)).replace("\\", "/"),
        "sha256": sha(target),
        "identity_files": len(protocol["identity_files"]),
        "preconditions": preconditions,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
