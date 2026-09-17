from __future__ import annotations

import importlib.util
import json
import sys
import time
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    rows = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        for name in sorted(value for value in vars(module) if value.startswith("test_")):
            started = time.perf_counter()
            try:
                getattr(module, name)()
                rows.append({"file": path.name, "test": name, "passed": True, "runtime_s": time.perf_counter() - started})
            except Exception:
                rows.append({"file": path.name, "test": name, "passed": False, "runtime_s": time.perf_counter() - started, "traceback": traceback.format_exc()})
    result = {"passed": all(row["passed"] for row in rows), "tests": rows, "runner": "stdlib assertion runner; pytest unavailable in frozen environment"}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()

