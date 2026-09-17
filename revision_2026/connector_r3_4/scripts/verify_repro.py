from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def latest_passed_with(root: Path, relative: str) -> Path:
    candidates = sorted(
        (path for path in root.iterdir() if path.is_dir() and (path / relative).exists()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        complete = path / "complete.json"
        if complete.exists() and read_json(complete).get("passed") is True:
            return path
    raise FileNotFoundError(relative)


def file_role(relative: Path) -> str:
    value = relative.as_posix()
    if value.startswith("figures/") and relative.suffix == ".png":
        return "figure_png"
    if value.startswith("figures/") and relative.suffix == ".pdf":
        return "figure_pdf"
    if value.startswith("figure_data/") and relative.suffix == ".csv":
        return "figure_data"
    if value.startswith("figure_data/") and value.endswith(".meta.json"):
        return "figure_metadata"
    if value.startswith("repro_logs/"):
        return "reproduction_log"
    if relative.suffix == ".md":
        return "report_or_response"
    if relative.suffix == ".json":
        return "machine_readable_contract"
    if relative.suffix == ".txt":
        return "execution_log"
    return ""


def source_manifest() -> dict[str, str]:
    paths = []
    for folder in (ROOT / "src", ROOT / "scripts", ROOT / "tests"):
        paths.extend(path for path in folder.rglob("*.py") if "__pycache__" not in path.parts)
    paths.extend([ROOT / "protocol_flow.md", ROOT / "review_comments.txt"])
    return {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in sorted(set(paths))
        if path.exists()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    project = args.project_root.resolve()
    run_output = args.output_dir.resolve()
    final = run_output / "final"
    if final.exists() and any(final.iterdir()):
        raise SystemExit(f"reproduction final directory must be empty: {final}")
    final.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    definitions = [
        ("plot_finish", "plot_finish.py"),
        ("build_finish_report", "build_finish_report.py"),
        ("build_review_matrix", "build_review_matrix.py"),
    ]
    executions = []
    for name, script in definitions:
        command = [
            sys.executable,
            "-B",
            str(ROOT / "scripts" / script),
            "--project-root",
            str(project),
            "--output-dir",
            str(final),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, env=env)
        logs = final / "repro_logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / f"{name}.stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (logs / f"{name}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
        executions.append(
            {
                "name": name,
                "command": command,
                "returncode": completed.returncode,
                "stdout": str(logs / f"{name}.stdout.txt"),
                "stderr": str(logs / f"{name}.stderr.txt"),
            }
        )
        if completed.returncode != 0:
            failed = {
                "passed": False,
                "failed_step": name,
                "executions": executions,
                "runtime_s": time.perf_counter() - started,
            }
            write_json(final / "reproduce.json", failed)
            write_json(
                run_output / "complete.json",
                {
                    "stage": "FINAL",
                    "passed": False,
                    "repair_code": "REPRODUCTION_STEP_FAILED",
                    "next_action": f"Inspect final/repro_logs/{name}.stderr.txt and rerun only {name}.",
                    "final_dir": str(final),
                },
            )
            raise SystemExit(completed.returncode)

    plot = read_json(final / "plot_finish.json")
    report = read_json(final / "report_verification.json")
    review = read_json(final / "review_response_matrix.json")
    readiness = read_json(final / "READY_FOR_KOOPMAN_TRAINING.json")
    flow_runs = project / "revision_2026" / "connector_r3_4_results" / "flow_runs"
    training_dir = latest_passed_with(flow_runs, "training_metrics.json")
    training = read_json(training_dir / "complete.json")
    data_dir = Path(readiness["confirmation_data"]["data_dir"])
    with (data_dir / "trajectory_manifest.csv").open("r", newline="", encoding="utf-8-sig") as stream:
        trajectories = list(csv.DictReader(stream))
    split_counts = Counter((row["plant"], row["split"]) for row in trajectories)
    models = []
    for model in training["models"]:
        path = Path(model["path"])
        models.append(
            {
                "plant": model["plant"],
                "model": model["model"],
                "path": str(path),
                "sha256": sha256(path),
                "state_dimension": model["state_dimension"],
                "control_dimension": model["control_dimension"],
                "ridge": model["ridge"],
            }
        )
    source_files = source_manifest()
    source_digest = hashlib.sha256(
        json.dumps(source_files, sort_keys=True).encode("utf-8")
    ).hexdigest()
    reproduce = {
        "passed": bool(plot["passed"] and report["passed"] and review["passed"]),
        "empty_output_rebuild": True,
        "executions": executions,
        "differences": {
            "acceptance_metric_mismatch_count": sum(
                not item["passed"] for item in report["metric_checks"]
            ),
            "figure_stem_set_mismatch": not plot["passed"],
            "review_comment_anchor_missing_count": sum(
                not item["anchor_found"] for item in review["items"]
            ),
        },
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
        },
        "runtime_s": time.perf_counter() - started,
    }
    write_json(final / "reproduce.json", reproduce)

    artifacts = []
    unexplained = []
    for path in sorted(path for path in final.rglob("*") if path.is_file() and path.name != "manifest.json"):
        relative = path.relative_to(final)
        role = file_role(relative)
        if not role:
            unexplained.append(relative.as_posix())
        artifacts.append(
            {
                "artifact_id": relative.as_posix(),
                "role": role,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    artifact_ids = [item["artifact_id"] for item in artifacts]
    manifest = {
        "manifest_version": 1,
        "passed": False,
        "self_hash_excluded": True,
        "protocol_flow": {
            "path": str(ROOT / "protocol_flow.md"),
            "sha256": sha256(ROOT / "protocol_flow.md"),
        },
        "source": {
            "root": str(ROOT),
            "manifest_sha256": source_digest,
            "files": source_files,
        },
        "plant": {
            "selected": readiness["selected_plants"],
            "branch": readiness["selection_branch"],
            "schema_dimensions": {"S1_team": 12, "S2_four": 30, "S3_deform": 46, "S4_force_in": 64},
        },
        "data": {
            "path": str(data_dir),
            "trajectory_manifest_sha256": sha256(data_dir / "trajectory_manifest.csv"),
            "physical_trajectory_count": len(trajectories),
            "split_counts": {
                f"{plant}:{split}": count
                for (plant, split), count in sorted(split_counts.items())
            },
        },
        "models": models,
        "figures": {
            "png_count": plot["png_count"],
            "pdf_count": plot["pdf_count"],
            "csv_count": plot["csv_count"],
            "meta_count": plot["meta_count"],
            "stems": plot["common_stems"],
        },
        "review_matrix": {
            "source_sha256": review["source_sha256"],
            "comment_count": review["comment_count"],
            "status_counts": review["status_counts"],
        },
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "duplicate_artifact_ids": sorted(
            key for key, count in Counter(artifact_ids).items() if count > 1
        ),
        "unexplained_files": unexplained,
    }
    manifest["passed"] = bool(
        reproduce["passed"]
        and not manifest["duplicate_artifact_ids"]
        and not unexplained
        and len(artifacts) == len(set(artifact_ids))
    )
    write_json(final / "manifest.json", manifest)
    current_files = {
        path.relative_to(final).as_posix()
        for path in final.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    registered_files = set(artifact_ids)
    manifest_contract_passed = manifest["passed"] and current_files == registered_files
    complete = {
        "stage": "FINAL",
        "passed": manifest_contract_passed,
        "final_dir": str(final),
        "manifest_path": str(final / "manifest.json"),
        "reproduce_path": str(final / "reproduce.json"),
        "report_path": str(final / "report.md"),
        "review_matrix_path": str(final / "review_response_matrix.md"),
        "readiness_path": str(final / "READY_FOR_KOOPMAN_TRAINING.json"),
        "figure_count_png": plot["png_count"],
        "figure_count_pdf": plot["pdf_count"],
        "review_comment_count": review["comment_count"],
        "metric_recalculation_count": report["metric_check_count"],
        "manifest_contract_passed": manifest_contract_passed,
        "runtime_s": time.perf_counter() - started,
    }
    if not manifest_contract_passed:
        complete["repair_code"] = "FINAL_MANIFEST_CONTRACT_FAILED"
        complete["next_action"] = "Inspect final/manifest.json for unregistered, unexplained or duplicate artifacts."
    write_json(run_output / "complete.json", complete)
    print(json.dumps(complete, ensure_ascii=False))
    raise SystemExit(0 if manifest_contract_passed else 2)


if __name__ == "__main__":
    main()
