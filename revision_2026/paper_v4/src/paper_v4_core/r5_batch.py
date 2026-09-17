"""Gate-locked EXP-R2 R5 legal-information interface batch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .cli import save, sha
from .r2c_analyze import load
from .r5_analyze import _r5_audit
from .r5_information_tests import run as run_information_tests
from .r5_runner import run


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _noiseless_difference(baseline: Path, candidate: Path) -> float:
    baseline_raw, baseline_columns, *_ = load(baseline)
    candidate_raw, candidate_columns, *_ = load(candidate)
    shared = [name for name in baseline_columns if name in candidate_columns]
    a = baseline_raw[:, [baseline_columns[name] for name in shared]]
    b = candidate_raw[:, [candidate_columns[name] for name in shared]]
    if a.shape != b.shape:
        return float("inf")
    return float(np.max(np.abs(a - b)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--r4-report", required=True)
    parser.add_argument("--baseline-r2c", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    selection_path = Path(args.selection)
    r4_path = Path(args.r4_report)
    baseline_path = Path(args.baseline_r2c)
    selection = _load_json(selection_path)
    r4 = _load_json(r4_path)
    if selection.get("status") != "PASS" or selection.get("selected_for_r3") != "lambda2":
        raise SystemExit("The valid lambda2 R2c selection is required")
    if r4.get("status") != "PASS" or r4.get("scope") != "P1/P2 full-route parameter and numerical pairing for the R2c-selected controller":
        raise SystemExit("A passing R4 parameter/resolution report is required")
    if float(r4.get("lambda_internal")) != 2.0:
        raise SystemExit("R4 and selected controller identities differ")
    out.mkdir(parents=True, exist_ok=False)
    registration = {
        "status": "RUNNING",
        "stage": "EXP-R2/R5",
        "role": "DEV interface transfer; not a method ranking",
        "run_order": ["contract_tests", "no_noise", "basic_noise"],
        "stop_rule": "contract/no-noise failure stops the batch; basic-noise hard failure ends R5 without changing the method",
        "selection_sha256": sha(selection_path),
        "r4_report_sha256": sha(r4_path),
        "baseline_r2c_sha256": sha(baseline_path / "metrics.json"),
        "runner_sha256": sha(Path(__file__).with_name("r5_runner.py")),
        "information_interface_sha256": sha(Path(__file__).with_name("information") / "legal_information.py"),
        "batch_sha256": sha(__file__),
        "runs": [],
    }
    save(out, "registration.json", registration)
    save(out, "status.json", registration)

    tests = run_information_tests(out / "contract_tests")
    registration["runs"].append({"name": "contract_tests", "status": tests["status"]})
    save(out, "status.json", registration)

    for noise_name in ("none", "basic"):
        run_name = "no_noise" if noise_name == "none" else "basic_noise"
        run_dir = out / run_name
        try:
            run(run_dir, noise_name=noise_name, seed=5105)
        except (SystemExit, Exception) as error:
            metrics_path = run_dir / "metrics.json"
            metrics = _load_json(metrics_path) if metrics_path.is_file() else {"status": "FAILED", "reason": f"{type(error).__name__}: {error}"}
            registration["runs"].append({"name": run_name, "metrics": metrics})
            registration["status"] = "FAILED"
            registration["reason"] = f"{run_name} did not complete"
            save(out, "status.json", registration)
            raise
        post_audit, _, _ = _r5_audit(run_name, run_dir)
        if noise_name == "none":
            difference = _noiseless_difference(baseline_path, run_dir)
            post_audit["checks"]["noiseless_wrapper_reproduces_full_state_baseline"] = difference <= 1e-12
            post_audit["maximum_abs_difference_from_r2c_baseline"] = difference
            post_audit["status"] = "PASS" if all(post_audit["checks"].values()) else "FAIL"
        registration["runs"].append({"name": run_name, "metrics": _load_json(run_dir / "metrics.json"), "post_audit": post_audit})
        if post_audit["status"] != "PASS":
            registration["status"] = "FAILED"
            registration["reason"] = f"{run_name} failed the independent post-run evidence/hard gate"
            save(out, "status.json", registration)
            raise SystemExit(20)
        save(out, "status.json", registration)

    registration["status"] = "COMPLETED"
    registration["reason"] = None
    save(out, "status.json", registration)
    print(json.dumps({"status": "COMPLETED", "runs": [item["name"] for item in registration["runs"]]}))


if __name__ == "__main__":
    main()
