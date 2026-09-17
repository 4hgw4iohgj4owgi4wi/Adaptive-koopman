from __future__ import annotations

import json
from pathlib import Path

from connector_r3 import ConnectorR3Params


PARAMETER_UNITS = {
    "stiffness_npm": "N/m",
    "damping_nspm": "N*s/m",
    "free_play_m": "m",
    "smoothing_width_m": "m",
    "rated_force_n": "N",
    "ultimate_force_n": "N",
}


def params_from_delta_freeze(path: Path) -> ConnectorR3Params:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not data.get("passed") or data.get("development_read") or data.get("confirm_read"):
        raise ValueError("R3 parameters require a passed train-only R0 freeze")
    return ConnectorR3Params(smoothing_width_m=float(data["smoothing_width_m"]))
