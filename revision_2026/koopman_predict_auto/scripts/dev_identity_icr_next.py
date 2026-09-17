from __future__ import annotations

import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    from run_icr_next import _read_json, _short_parent_identity, validate_protocol

    protocol_path = ROOT / "config" / "protocol_icr_next.json"
    protocol = _read_json(protocol_path)
    validate_protocol(protocol)
    with tempfile.TemporaryDirectory(prefix="koopman_icr_next_identity_") as directory:
        result = _short_parent_identity(protocol_path, protocol, Path(directory))
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()
