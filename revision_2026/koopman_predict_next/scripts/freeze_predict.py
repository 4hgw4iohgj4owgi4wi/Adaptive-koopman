from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contracts import json_sha256, sha256, source_manifest, write_json


def environment_manifest(project_root: Path) -> dict:
    import numpy as np

    disk = shutil.disk_usage(project_root)
    result = {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "cwd": str(Path.cwd()),
        "project_root": str(project_root),
        "disk_free_gib": disk.free / 1024**3,
        "thread_environment": {
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
        },
    }
    try:
        import torch

        result.update(
            {
                "torch_version": torch.__version__,
                "cuda_available": bool(torch.cuda.is_available()),
                "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            }
        )
    except Exception as error:  # pragma: no cover - environment evidence path
        result.update({"cuda_available": False, "gpu": None, "torch_probe_error": repr(error)})
    return result


def freeze(
    *,
    project_root: Path,
    source_root: Path,
    protocol_path: Path,
    taskbook_path: Path,
    output: Path,
) -> dict:
    manifest = source_manifest(source_root)
    environment = environment_manifest(project_root)
    result = {
        "source_root": str(source_root),
        "source_manifest": manifest,
        "source_manifest_sha256": json_sha256(manifest),
        "source_file_count": len(manifest),
        "protocol_path": str(protocol_path),
        "protocol_sha256": sha256(protocol_path),
        "taskbook_path": str(taskbook_path),
        "taskbook_sha256": sha256(taskbook_path),
        "environment": environment,
        "excluded_from_source_manifest": ["__pycache__", ".pytest_cache", "non_py_json_md_files"],
    }
    write_json(output / "source_manifest.json", manifest)
    write_json(output / "environment_manifest.json", environment)
    write_json(output / "freeze_manifest.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--source-root", default=str(ROOT))
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--taskbook", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = freeze(
        project_root=Path(args.project_root).resolve(),
        source_root=Path(args.source_root).resolve(),
        protocol_path=Path(args.protocol).resolve(),
        taskbook_path=Path(args.taskbook).resolve(),
        output=Path(args.output).resolve(),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
