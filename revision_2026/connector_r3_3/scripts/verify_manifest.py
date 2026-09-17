from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--results", type=Path, required=True); args = parser.parse_args(); root = args.results.resolve()
    manifest_path = root / "artifact_manifest.json"; manifest = json.loads(manifest_path.read_text(encoding="utf-8")); mismatches = []
    for relative, metadata in manifest["files"].items():
        path = root / relative; actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        if actual != metadata["sha256"] or (path.exists() and path.stat().st_size != metadata["bytes"]): mismatches.append(relative)
    sidecar = (root / "artifact_manifest.sha256").read_text(encoding="ascii").split()[0]
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    result = {"passed": not mismatches and sidecar == manifest_hash, "files": len(manifest["files"]), "mismatches": mismatches, "manifest_sha256": manifest_hash, "sidecar_matches": sidecar == manifest_hash}
    print(json.dumps(result, indent=2)); raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__": main()

