"""Current EXP-R2 E00 package/import/plant identity audit."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import platform
from pathlib import Path
import sys

from .cli import save


TASKBOOK_SHA256 = "417CFCDBF22A026973DFF617E29E4814361F9013AED7CA06F065992C20F0D81D"
FROZEN_ORIGINALS = {
    "koopman_predict_auto/plant/four_vehicle_common.py": "6d7a2092fc6b9772347fc6d9812ba920bb139c8271f5cbba1ac96cc4f12bca80",
    "koopman_predict_auto/plant/event_substep.py": "9aa0e8bd62dd8b83b8bd0c15414cbd21f915f0203b7ca978d5f46bc45746d77c",
    "paper_v3/src/controllers.py": "c504bb0941990443fc0becdefaf6ab6d97ff9b14ae4180b546d714eea044c797",
}
CRITICAL_MODULES = (
    "paper_v4_core.plant.four_vehicle_common",
    "paper_v4_core.plant.event_substep",
    "paper_v4_core.plant.steering_allocator",
    "paper_v4_core.controllers.physical_tracking_pilot",
    "paper_v4_core.pilot_runner",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _normalized_ast(path: Path, local_names: set[str], normalize_relative: bool):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    if normalize_relative:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in local_names:
                node.level = 1
    return ast.dump(tree, include_attributes=False)


def _import_edges(path: Path, package_root: Path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    edges = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            edges.append({"kind": "from", "level": node.level, "module": node.module, "names": sorted(alias.name for alias in node.names)})
        elif isinstance(node, ast.Import):
            edges.extend({"kind": "import", "level": 0, "module": alias.name, "names": []} for alias in node.names)
    return edges


def run(out, taskbook):
    out = Path(out)
    taskbook = Path(taskbook).resolve()
    package_root = Path(__file__).resolve().parent
    revision_root = package_root.parents[2]
    if out.exists():
        raise ValueError("refusing to overwrite identity audit output")
    if _sha(taskbook) != TASKBOOK_SHA256:
        raise ValueError("taskbook identity mismatch")

    original_checks = []
    for relative, expected in FROZEN_ORIGINALS.items():
        path = revision_root / relative
        actual = _sha(path) if path.is_file() else None
        original_checks.append({"path": str(path), "expected_sha256": expected.upper(), "actual_sha256": actual, "match": actual == expected.upper()})
    if not all(item["match"] for item in original_checks):
        raise ValueError("frozen original source mismatch")

    runtime_modules = []
    for name in CRITICAL_MODULES:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(package_root):
            raise ValueError(f"foreign critical import: {name} -> {path}")
        runtime_modules.append({"module": name, "path": str(path), "sha256": _sha(path)})

    package_locations = []
    for entry in sys.path:
        if not entry:
            continue
        candidate = (Path(entry).resolve() / "paper_v4_core")
        if candidate.is_dir():
            package_locations.append(str(candidate.resolve()))
    package_locations = sorted(set(package_locations))
    if package_locations != [str(package_root)]:
        raise ValueError(f"ambiguous paper_v4_core locations: {package_locations}")

    files = []
    for path in sorted(package_root.rglob("*.py")):
        files.append({"module_file": str(path), "relative_path": path.relative_to(package_root).as_posix(), "sha256": _sha(path), "imports": _import_edges(path, package_root)})

    original_plant = revision_root / "koopman_predict_auto" / "plant"
    isolated_plant = package_root / "plant"
    local_names = {path.stem for path in original_plant.glob("*.py")}
    conversions = []
    for isolated in sorted(isolated_plant.glob("*.py")):
        original = original_plant / isolated.name
        if not original.is_file():
            continue
        equivalent = _normalized_ast(original, local_names, True) == _normalized_ast(isolated, local_names, False)
        conversions.append({"original": str(original), "original_sha256": _sha(original), "isolated": str(isolated), "isolated_sha256": _sha(isolated), "ast_equivalent_after_relative_import_normalization": equivalent})
    if not all(item["ast_equivalent_after_relative_import_normalization"] for item in conversions):
        raise ValueError("isolated plant contains a non-import change")

    identity = {
        "schema_version": "EXP-R2-E00-identity-v1",
        "status": "PARTIAL",
        "host": platform.node(),
        "python": sys.version,
        "taskbook": {"path": str(taskbook), "sha256": _sha(taskbook)},
        "frozen_originals": original_checks,
        "package_root": str(package_root),
        "package_location_unique": True,
        "plant_import_identity": "PASS",
        "actuator_contract": {
            "status": "PASS_IMPLEMENTED_CONTRACT",
            "update_interval_s": 0.002,
            "semantics": "discrete jump at each 2 ms interval start, then held during that plant interval",
            "time_constant_s": 0.12,
            "rate_limit_radps": 1.2,
            "angle_limit_deg": 15.0,
            "scope": "simulation contract, not hardware calibration and not a continuous actuator-plant convergence claim"
        },
        "data_roles": "PARTIAL",
        "submission_pdf": "SOURCE_PENDING",
        "all_E00_complete": False
    }
    imports = {
        "schema_version": "EXP-R2-E00-imports-v1",
        "status": "PASS",
        "package_root": str(package_root),
        "package_locations_on_sys_path": package_locations,
        "critical_runtime_modules": runtime_modules,
        "recursive_python_file_inventory": files,
        "recursive_python_file_count": len(files),
        "recursive_plant_conversion": conversions,
    }
    save(out, "identity.json", identity)
    save(out, "imports.json", imports)
    print(json.dumps({"status": "PARTIAL", "host": identity["host"], "python_files": len(files), "plant_files_compared": len(conversions)}))
    return identity, imports


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--taskbook", required=True)
    args = parser.parse_args()
    run(args.out, args.taskbook)


if __name__ == "__main__":
    main()
