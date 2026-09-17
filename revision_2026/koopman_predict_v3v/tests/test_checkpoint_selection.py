"""F2: best/last checkpoint selection tests (E01/E02).

A synthetic metric that first decreases then increases must select the model
at the minimum, and best_step must differ from stop_step when early stopping
fires after a plateau.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from checkpoint import EarlyStopState


def test_early_stop_selects_global_minimum():
    state = EarlyStopState(patience=2000)
    metrics = {0: 1.0, 500: 0.6, 1000: 0.4, 1500: 0.35, 2000: 0.36, 2500: 0.38, 3000: 0.40}
    for step, metric in sorted(metrics.items()):
        improved = state.observe(metric, step)
        assert improved == (metric == min(v for k, v in metrics.items() if k <= step))
    assert state.best_step == 1500
    assert state.best_metric == pytest.approx(0.35)
    # patience: no improvement after step 1500 through 3000 -> counter 1500
    assert state.patience_counter == 1500


def test_early_stop_patience_accumulates():
    state = EarlyStopState(patience=1000)
    state.observe(1.0, 0)
    state.observe(0.5, 500)  # improved
    state.observe(0.55, 1000)  # not improved: +500
    assert state.should_stop() is False
    state.observe(0.56, 1500)  # not improved: +500 -> 1000
    assert state.should_stop() is True
    assert state.best_step == 500


def test_early_stop_state_roundtrip():
    state = EarlyStopState(best_metric=0.3, best_step=1000, patience_counter=800, patience=2000, last_check_step=1500)
    restored = EarlyStopState.from_dict(state.to_dict())
    assert restored.to_dict() == state.to_dict()


def test_best_and_stop_step_are_distinct_after_plateau():
    state = EarlyStopState(patience=2000)
    for step in (0, 500, 1000):
        state.observe(1.0 - 0.1 * step / 500, step)
    # metric now increases
    for step in (1500, 2000, 2500, 3000):
        state.observe(0.8, step)
    assert state.best_step == 1000
    assert state.best_step != 3000  # stop step would be 3000
