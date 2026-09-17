from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    project = Path(sys.argv[1]).resolve()
    source = project / "revision_2026" / "connector_r3_3"
    manifest_path = project / "revision_2026" / "connector_r3_3_results" / "n0" / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    drift = {}
    for rel, expected in manifest.items():
        path = source / rel
        actual = sha256(path) if path.is_file() else None
        if actual != expected:
            drift[rel] = {"expected": expected, "actual": actual}
    packages = {}
    errors = {}
    for name in ("numpy", "scipy", "torch"):
        try:
            module = __import__(name)
            packages[name] = getattr(module, "__version__", "unknown")
        except Exception as exc:
            errors[name] = repr(exc)
    usage = shutil.disk_usage("D:\\")
    tasklist = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, errors="replace")
    active = []
    for line in tasklist.stdout.splitlines():
        if "python" not in line.lower() and "matlab" not in line.lower():
            continue
        fields = [part.strip().strip('"') for part in line.split(",")]
        pid = int(fields[1]) if len(fields) > 1 and fields[1].isdigit() else None
        if pid != os.getpid():
            active.append(line)
    result = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "packages": packages,
        "package_errors": errors,
        "project_root": str(project),
        "r33_source": str(source),
        "r33_manifest": str(manifest_path),
        "r33_manifest_sha256": sha256(manifest_path),
        "r33_manifest_entries": len(manifest),
        "r33_drift": drift,
        "r34_exists": (project / "revision_2026" / "connector_r3_4").exists(),
        "disk_d_total_bytes": usage.total,
        "disk_d_free_bytes": usage.free,
        "disk_d_free_gib": usage.free / 2**30,
        "active_python_matlab_processes": active,
        "checks": {
            "host_expected": socket.gethostname().upper() == "DESKTOP-9IUUGEO",
            "project_exists": project.is_dir(),
            "r33_hashes_match": not drift,
            "r34_absent": not (project / "revision_2026" / "connector_r3_4").exists(),
            "disk_free_ge_50gib": usage.free >= 50 * 2**30,
            "numpy_available": "numpy" in packages,
            "scipy_available": "scipy" in packages,
            "dop853_available": False,
            "no_conflicting_processes": not active,
        },
    }
    if "scipy" in packages:
        try:
            from scipy.integrate import DOP853  # noqa: F401
            result["checks"]["dop853_available"] = True
        except Exception as exc:
            result["dop853_error"] = repr(exc)
    result["passed"] = all(result["checks"].values())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
