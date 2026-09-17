from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]


def main() -> None:
    env = os.environ.copy()
    env["KOOPMAN_PROJECT_ROOT"] = str(PROJECT)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=ROOT,
        env=env,
        timeout=1800,
    )
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
