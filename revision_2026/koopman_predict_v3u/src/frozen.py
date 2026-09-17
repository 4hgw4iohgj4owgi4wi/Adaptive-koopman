from __future__ import annotations

"""Read-only bridge to the frozen N6 tree (koopman_predict_auto).

Everything in this module is read-only: it validates the frozen N6 source
manifest SHA, exposes the frozen artifact paths and the frozen parameter
resolver / planar grasp projector.  It never writes into the N6 tree.
"""

import importlib.util
import sys
from pathlib import Path

from contracts_v2 import json_sha256, read_json, sha256


def frozen_source_manifest(root: Path) -> dict[str, str]:
    """Replicate the frozen N6 source-manifest walker (contracts.source_manifest)."""
    result: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or any(
            part in {"__pycache__", ".pytest_cache", "runs", "results", "models", "checkpoints"}
            for part in path.parts
        ):
            continue
        if path.suffix.lower() in {".pyc", ".tmp", ".lock", ".partial"}:
            continue
        if path.suffix.lower() not in {".py", ".json", ".md"}:
            continue
        result[path.relative_to(root).as_posix()] = sha256(path)
    return result


class FrozenN6:
    """Locate and validate the frozen N6 tree, then expose read-only dependencies."""

    def __init__(self, project_root: Path, protocol: dict):
        self.project_root = Path(project_root)
        parent = protocol["parent_n6"]
        self.source_root = self.project_root / Path(parent["source_root"])
        self.results_root = self.project_root / Path(parent["results_root"])
        self.data_root = self.project_root / Path(parent["data_root"])
        self.models_root = self.project_root / Path(parent["models_root"])
        self.run_id = str(parent["run_id"])
        self.run_results_root = self.results_root / "runs" / self.run_id
        self.data_run_root = self.data_root / self.run_id
        self.models_run_root = self.models_root / self.run_id
        if not self.source_root.is_dir():
            raise RuntimeError(f"frozen N6 source missing: {self.source_root}")
        if not self.run_results_root.is_dir():
            raise RuntimeError(f"frozen N6 run missing: {self.run_results_root}")

    # ---- identity -------------------------------------------------------
    def verify_identity(self, protocol: dict) -> dict:
        parent = protocol["parent_n6"]
        manifest = frozen_source_manifest(self.source_root)
        manifest_sha = json_sha256(manifest)
        protocol_path = self.source_root / "config" / "protocol_predict_auto.json"
        taskbook_path = self.source_root / "protocol.md"
        complete_path = self.run_results_root / "n6" / "complete.json"
        checks = {
            "source_manifest_sha256": manifest_sha == parent["source_manifest_sha256"],
            "protocol_sha256": sha256(protocol_path) == parent["protocol_sha256"],
            "taskbook_sha256": sha256(taskbook_path) == parent["taskbook_sha256"],
            "complete_sha256": sha256(complete_path) == parent["complete_sha256"],
            "n6_status": read_json(complete_path).get("stage_status") == parent["status"],
        }
        return {
            "passed": all(checks.values()),
            "checks": checks,
            "source_file_count": len(manifest),
            "source_manifest_sha256": manifest_sha,
            "n6_complete_path": str(complete_path),
        }

    # ---- frozen artifacts ------------------------------------------------
    def n5_manifest_path(self) -> Path:
        return self.run_results_root / "n5" / "data_manifest.csv"

    def n5_normalization_path(self) -> Path:
        return self.run_results_root / "n5" / "normalization_train_only.npz"

    def n5_cache_dir(self) -> Path:
        return self.data_run_root / "n5" / "cache"

    def n6_models_dir(self) -> Path:
        return self.models_run_root / "n6"

    def n6_stage_dir(self) -> Path:
        return self.run_results_root / "n6"

    def n6_development_detailed_path(self) -> Path:
        return self.n6_stage_dir() / "development_detailed.csv.gz"

    # ---- frozen code dependencies (read-only imports) --------------------
    def resolved_params(self, seed: int, protocol: dict):
        """Frozen N6 parameter resolver (generate_data.resolved_params)."""
        module = self._import_frozen_module(
            "frozen_generate_data",
            self.source_root / "scripts" / "generate_data.py",
        )
        return module.resolved_params(int(seed), protocol)

    def build_planar_grasp_matrix(self, anchor_body):
        """Frozen N6 planar grasp projector (internal_force.build_planar_grasp_matrix)."""
        module = self._import_frozen_module(
            "frozen_internal_force",
            self.source_root / "plant" / "internal_force.py",
        )
        return module.build_planar_grasp_matrix(anchor_body)

    def _import_frozen_module(self, name: str, path: Path):
        cached = getattr(self, f"_module_{name}", None)
        if cached is not None:
            return cached
        if not path.is_file():
            raise RuntimeError(f"frozen dependency missing: {path}")
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load frozen dependency: {path}")
        module = importlib.util.module_from_spec(spec)
        # The frozen scripts/plant modules import each other by bare name.
        for extra in ("src", "scripts", "plant"):
            sys.path.insert(0, str(self.source_root / extra))
        try:
            spec.loader.exec_module(module)
        finally:
            for extra in ("src", "scripts", "plant"):
                try:
                    sys.path.remove(str(self.source_root / extra))
                except ValueError:
                    pass
        setattr(self, f"_module_{name}", module)
        return module
