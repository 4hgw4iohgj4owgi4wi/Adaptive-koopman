from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from event_substep import EventSubstepConfig, integrate


def test_floating_closure_not_counted_as_physical_step():
    config = EventSubstepConfig()
    run = integrate("R3", -0.0002, 0.2, 0.006000000000000001, "ES", config, keep_trace=False)
    assert run["status"] == "PASS"
    assert run["min_accepted_dt_s"] >= config.min_step_s
    assert run["duration_actual_s"] == run["duration_requested_s"]


def test_reference_is_not_subject_to_es_cap():
    run = integrate("R3", 0.0, 0.2, 0.004, "REF", EventSubstepConfig(), fixed_step_s=0.5e-6, keep_trace=False)
    assert run["status"] == "PASS"
    assert run["accepted_steps"] >= 7999

