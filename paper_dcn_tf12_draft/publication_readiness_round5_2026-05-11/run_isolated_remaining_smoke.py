from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_STAGE = ROOT / "tf14_remaining_experiments_20260509"
DEFAULT_COPY = ROOT / "tf14_remaining_smoke_round6_20260511"
PYTHON = Path(r"E:\anaconda\envs\pytorch_new\python.exe")


def ignore_stage_outputs(_dir: str, names: list[str]) -> set[str]:
    ignored = {"data", "figures", "logs", "__pycache__"}
    return {name for name in names if name in ignored or name.endswith(".pyc")}


def prepare_copy(dest: Path) -> None:
    if dest.exists():
        raise SystemExit(f"Destination already exists; refusing to overwrite: {dest}")
    shutil.copytree(SOURCE_STAGE, dest, ignore=ignore_stage_outputs)
    for sub in ("data", "figures", "logs"):
        (dest / sub).mkdir(parents=True, exist_ok=True)


def run_command(dest: Path, command_args: list[str]) -> int:
    script = dest / "run_tf14_remaining_experiments.py"
    if not script.exists():
        raise SystemExit(f"Missing copied runner: {script}")
    cmd = [str(PYTHON), str(script), *command_args]
    print(" ".join(cmd))
    completed = subprocess.run(cmd, cwd=str(ROOT), text=True)
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and run TF14 remaining experiments in an isolated copy.")
    parser.add_argument("--dest", type=Path, default=DEFAULT_COPY)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--run-help", action="store_true")
    parser.add_argument("--run-min-e3", action="store_true", help="Run the smallest useful E3 one-seed smoke in the isolated copy.")
    args = parser.parse_args()

    if not args.dest.exists():
        prepare_copy(args.dest)
        print(f"prepared: {args.dest}")
    else:
        print(f"using existing isolated copy: {args.dest}")

    if args.prepare_only:
        return 0
    if args.run_help:
        return run_command(args.dest, ["--help"])
    if args.run_min_e3:
        return run_command(args.dest, ["--experiments", "E3", "--seeds", "2026", "--scenarios", "sine_mixed_fault_noise"])

    print("No run mode selected. Use --run-help or --run-min-e3.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
