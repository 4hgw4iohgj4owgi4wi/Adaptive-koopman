from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main():
    project, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    rev = project / "revision_2026"
    roots = {
        "historical_source_connector_v2": rev / "connector_v2",
        "historical_r1_results_c0_c4": rev / "connector_v2_results",
    }
    files = {}
    for label, root in roots.items():
        selected = []
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = path.relative_to(root).as_posix()
            if label == "historical_r1_results_c0_c4" and not (rel.startswith(("c0/", "c1/", "c2/", "c3/", "c4/", "r2_energy_match/"))):
                continue
            selected.append({"path": str(path), "relative_path": rel, "size": path.stat().st_size, "sha256": sha256(path)})
        files[label] = selected
    result = {
        "status": "read_only_snapshot",
        "roots": {k: str(v) for k, v in roots.items()},
        "files": files,
        "counts": {k: len(v) for k, v in files.items()},
        "development_read": False,
        "confirm_read": False,
        "note": "Hashes file bytes only; no NPZ/JSON scientific contents were opened.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
