from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_finish", ROOT / "scripts" / "run_finish.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_finish_dispatcher_registers_the_flow_tree():
    assert MODULE.STAGES == (
        "FLOW_C1",
        "N2_PILOT",
        "N2_FULL",
        "PHYSICS_STATIC",
        "N3_PILOT",
        "N3_FULL",
        "N4_PILOT",
        "N4_FULL",
        "SELECT_PLANT",
        "DATA_PILOT",
        "DATA_FULL",
        "TRAIN_SMOKE",
        "MPC_INTERFACE",
        "FINAL",
    )
    assert set(MODULE.SCRIPT_ENTRY) == set(MODULE.STAGES) - {"FLOW_C1"}
