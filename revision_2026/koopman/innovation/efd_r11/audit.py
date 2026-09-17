from __future__ import annotations
import hashlib, json, platform, sys
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def hash_tree(root: Path, exclude: set[str] | None = None) -> dict[str, str]:
    exclude = exclude or set()
    if not root.exists(): return {}
    return {str(p.relative_to(root)): sha256(p) for p in sorted(root.rglob("*"))
            if p.is_file() and not any(x in p.parts for x in exclude)}


def _structured_values(path: Path) -> set[int]:
    out: set[int] = set()
    try:
        if path.suffix.lower() == ".json":
            obj = json.loads(path.read_text(encoding="utf-8"))
            def walk(x: Any, key: str = "") -> None:
                if isinstance(x, dict):
                    for k, v in x.items(): walk(v, str(k).lower())
                elif isinstance(x, list):
                    for v in x: walk(v, key)
                elif any(q in key for q in ("seed", "traj_id", "trajectory_id")) and isinstance(x, (int, float)) and float(x).is_integer():
                    out.add(int(x))
            walk(obj)
        elif path.suffix.lower() == ".npz":
            import numpy as np
            with np.load(path, allow_pickle=False) as s:
                for k in s.files:
                    if any(q in k.lower() for q in ("seed", "traj_id", "trajectory_id")) and s[k].size < 10000:
                        for value in s[k].reshape(-1):
                            try: out.add(int(value))
                            except (TypeError, ValueError): pass
    except Exception:
        pass
    return out


def seed_collisions(root: Path, requested: list[int]) -> dict[str, Any]:
    wanted = set(requested); found: dict[str, list[int]] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in (".json", ".npz"): continue
        if "innovation_efd_r11_results" in path.parts: continue
        hit = _structured_values(path) & wanted
        if hit: found[str(path)] = sorted(hit)
    return {"requested_count": len(requested), "range": [min(requested), max(requested)],
            "collisions": found, "passed": not found,
            "parser": "structured seed/traj_id/trajectory_id fields only"}


def environment() -> dict[str, Any]:
    import numpy, scipy
    return {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "numpy": numpy.__version__, "scipy": scipy.__version__}
