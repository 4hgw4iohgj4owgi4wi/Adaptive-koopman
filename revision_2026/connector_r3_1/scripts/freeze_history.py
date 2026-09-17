from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    project = Path(sys.argv[1]).resolve()
    source = Path(sys.argv[2]).resolve()
    output = Path(sys.argv[3]).resolve()
    rev = project / "revision_2026"
    old_source = rev / "connector_r3"
    old_results = rev / "connector_r3_results"
    required = [
        old_source / "protocol.md",
        old_source / "README.md",
        old_source / "src" / "connector_r3.py",
        old_source / "src" / "schema_r3.py",
        old_source / "src" / "single_connector_dynamics_r3.py",
        old_source / "tests" / "test_r1_contract.py",
        old_source / "tests" / "test_r2_single_connector.py",
        old_results / "r0" / "delta_s_freeze.json",
        old_results / "r0" / "input_manifest.json",
        old_results / "r0" / "delta_s_events.csv",
        old_results / "r1" / "contract_results.json",
        old_results / "r2" / "single_connector" / "r2_results.json",
        old_results / "stage_status.json",
        old_results / "work_log.md",
        old_results / "solutions.md",
        source / "protocol.md",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("missing historical inputs: " + json.dumps(missing))

    snapshot = output / "s0" / "historical_snapshot"
    snapshot.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in required:
        if path.is_relative_to(old_source):
            rel = Path("connector_r3") / path.relative_to(old_source)
        elif path.is_relative_to(old_results):
            rel = Path("connector_r3_results") / path.relative_to(old_results)
        else:
            rel = Path("connector_r3_1") / path.relative_to(source)
        target = snapshot / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        if sha256(path) != sha256(target):
            raise SystemExit(f"snapshot hash mismatch: {path}")
        rows.append({
            "source": str(path),
            "snapshot": str(target),
            "relative_path": rel.as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        })

    old_status = json.loads((old_results / "stage_status.json").read_text(encoding="utf-8"))
    if old_status.get("status") != "BLOCKED_AFTER_R2_2MS_GATE":
        raise SystemExit("historical status changed unexpectedly")
    result = {
        "passed": True,
        "status": "R3_HISTORY_FROZEN_FOR_POST_R2_REVISION",
        "historical_status": old_status["status"],
        "files": rows,
        "development_read": False,
        "confirm_read": False,
    }
    manifest = output / "s0" / "historical_manifest.json"
    manifest.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "files": len(rows), "manifest": str(manifest)}))


if __name__ == "__main__":
    main()
