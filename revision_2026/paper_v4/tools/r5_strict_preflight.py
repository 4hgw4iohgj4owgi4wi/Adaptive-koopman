"""Non-dynamic negative tests for the strict-chain protocol boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

PAPER = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=PAPER, env=env, text=True, capture_output=True, check=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    baseline_path = args.baseline_protocol.resolve()
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(PAPER / "src")
    tests = []

    def record(name: str, passed: bool, result: subprocess.CompletedProcess | None = None, **detail) -> None:
        tests.append({
            "name": name,
            "pass": bool(passed),
            "returncode": result.returncode if result else None,
            "stdout_tail": (result.stdout[-500:] if result else None),
            "stderr_tail": (result.stderr[-1000:] if result else None),
            **detail,
        })

    with tempfile.TemporaryDirectory(prefix="r5_strict_preflight_") as temp_name:
        temp = Path(temp_name)
        wrong_sha_out = (PAPER / baseline["run"]["output"]).resolve()
        cmd = [sys.executable, "-m", "paper_v4_core.diagnostics.full_route_gpu_runner",
               "--protocol", str(baseline_path), "--protocol-sha", "0" * 64,
               "--backend", "gpu", "--deadline-unix", "9999999999"]
        result = run(cmd, env)
        record("baseline_wrong_sha_rejected_before_output", result.returncode != 0 and not wrong_sha_out.exists(), result,
               checked_output=str(wrong_sha_out))

        malformed = json.loads(json.dumps(baseline))
        malformed["solver_settings"]["eps_abs"] = 0.0
        malformed["run"]["output"] = str((temp / "malformed_output").resolve()).replace("\\", "/")
        malformed_path = temp / "malformed.json"
        malformed_path.write_text(json.dumps(malformed, indent=2), encoding="utf-8")
        result = run([sys.executable, "-m", "paper_v4_core.diagnostics.full_route_gpu_runner",
                      "--protocol", str(malformed_path), "--protocol-sha", sha(malformed_path),
                      "--backend", "gpu", "--deadline-unix", "9999999999"], env)
        record("malformed_solver_settings_rejected_before_output",
               result.returncode != 0 and not Path(malformed["run"]["output"]).exists(), result)

        existing_dir = temp / "existing_output"
        existing_dir.mkdir()
        existing = json.loads(json.dumps(baseline))
        existing["run"]["output"] = str(existing_dir.resolve()).replace("\\", "/")
        existing_path = temp / "existing.json"
        existing_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        result = run([sys.executable, "-m", "paper_v4_core.diagnostics.full_route_gpu_runner",
                      "--protocol", str(existing_path), "--protocol-sha", sha(existing_path),
                      "--backend", "gpu", "--deadline-unix", "9999999999"], env)
        record("existing_output_rejected", result.returncode != 0 and existing_dir.is_dir(), result)

        r5 = {
            "scope": "R5_LEGAL_INFORMATION",
            "run": {"output": str((temp / "r5_output").resolve()).replace("\\", "/"),
                    "noise": "none", "seed": 5105, "backend": "gpu", "parameter_id": "P0",
                    "plant_max_step_ms": 2.0, "controller_step_ms": 20.0, "horizon": 20,
                    "lambda_internal": 2.0, "frozen_dynamics_jacobian": False,
                    "finite_difference_scale": 1.0, "total_ticks": 2379},
            "solver_settings": baseline["solver_settings"],
            "identity_files": [],
        }
        r5_path = temp / "r5_missing_acceptance.json"
        r5_path.write_text(json.dumps(r5, indent=2), encoding="utf-8")
        result = run([sys.executable, "-m", "paper_v4_core.r5_runner",
                      "--out", r5["run"]["output"], "--noise", "none", "--seed", "5105",
                      "--backend", "gpu", "--deadline-unix", "9999999999",
                      "--protocol", str(r5_path), "--protocol-sha", sha(r5_path)], env)
        record("r5_missing_acceptance_rejected_before_output",
               result.returncode != 0 and not Path(r5["run"]["output"]).exists(), result)

        r5["acceptance_tolerances"] = baseline["acceptance_tolerances"]
        r5_path = temp / "r5_missing_deadline.json"
        r5_path.write_text(json.dumps(r5, indent=2), encoding="utf-8")
        result = run([sys.executable, "-m", "paper_v4_core.r5_runner",
                      "--out", r5["run"]["output"], "--noise", "none", "--seed", "5105",
                      "--backend", "gpu", "--protocol", str(r5_path), "--protocol-sha", sha(r5_path)], env)
        record("r5_missing_deadline_rejected_before_output",
               result.returncode != 0 and not Path(r5["run"]["output"]).exists(), result)

    status = "PASS_R5_STRICT_PREFLIGHT" if all(item["pass"] for item in tests) else "FAIL_R5_STRICT_PREFLIGHT"
    output.mkdir(parents=True)
    figures = output / "figures"
    figures.mkdir()
    report = {"status": status, "tests": tests, "baseline_protocol": str(baseline_path),
              "baseline_protocol_sha256": sha(baseline_path),
              "scope": "Non-dynamic protocol and refusal tests; no GPU dynamics or full route was run."}
    (output / "preflight.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    fig, ax = plt.subplots(figsize=(10.0, 4.8))
    colors = ["#2ca02c" if item["pass"] else "#d62728" for item in tests]
    ax.barh(range(len(tests)), [1 if item["pass"] else 0 for item in tests], color=colors)
    ax.set_yticks(range(len(tests)), [item["name"] for item in tests])
    ax.set_xlim(0, 1.05); ax.set_xlabel("pass = 1"); ax.set_title(f"R5 strict-chain non-dynamic preflight — {status}")
    ax.grid(axis="x", alpha=0.25); fig.tight_layout()
    names = []
    for suffix in ("png", "svg"):
        name = f"r5_strict_preflight.{suffix}"
        fig.savefig(figures / name, dpi=300 if suffix == "png" else None)
        names.append(name)
    plt.close(fig)
    manifest = {"science_status": status, "figure_status": "PENDING_VISUAL_QA",
                "figures": [f"figures/{name}" for name in names],
                "generating_script": "tools/r5_strict_preflight.py",
                "generating_script_sha256": sha(Path(__file__)), "caption": report["scope"]}
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (figures / "README.md").write_text(f"# R5严格链非动力学预检\n\n状态：`{status}`。\n\n{report['scope']}\n", encoding="utf-8")
    print(json.dumps({"status": status, "output": str(output), "tests": tests}, ensure_ascii=False))
    if status != "PASS_R5_STRICT_PREFLIGHT":
        raise SystemExit(20)


if __name__ == "__main__":
    main()
