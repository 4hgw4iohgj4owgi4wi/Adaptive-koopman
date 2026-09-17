"""Process-parallel central differences with deterministic serial reconstruction."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import time

import numpy as np

from . import physical_tracking_pilot as controller


def _rollout_job(job):
    state, control, model = job
    return controller.rollout_step(state, control, model)


class ParallelFiniteDifferenceBackend:
    """Keep one worker pool alive while preserving central-difference ordering."""

    def __init__(self, workers: int = 8):
        if workers != 8:
            raise ValueError("EXP_R4B_REQUIRES_EXACTLY_8_WORKERS")
        self.workers = workers
        self.executor = None
        self.warmup_s = None

    def __enter__(self):
        self.executor = ProcessPoolExecutor(max_workers=self.workers)
        return self

    def warm(self, state, control, model):
        started = time.perf_counter()
        list(self.executor.map(_rollout_job, [(state, control, model)] * self.workers, chunksize=1))
        self.warmup_s = time.perf_counter() - started
        return self.warmup_s

    def linearize(self, state, control, model, finite_difference_scale=1.0):
        state = np.asarray(state, float)
        control = np.asarray(control, float)
        nominal = controller.rollout_step(state, control, model)
        state_steps = controller._steps(34, scale=finite_difference_scale)
        control_steps = np.asarray([1e-4 if j % 2 == 0 else 1e-6 for j in range(8)]) * finite_difference_scale
        jobs = []
        for index, step in enumerate(state_steps):
            plus = state.copy(); minus = state.copy()
            plus[index] += step; minus[index] -= step
            jobs.extend(((plus, control, model), (minus, control, model)))
        for index, step in enumerate(control_steps):
            plus = control.copy(); minus = control.copy()
            plus[index] += step; minus[index] -= step
            jobs.extend(((state, plus, model), (state, minus, model)))
        values = list(self.executor.map(_rollout_job, jobs, chunksize=1))
        A = np.empty((34, 34)); B = np.empty((34, 8)); offset = 0
        for index, step in enumerate(state_steps):
            A[:, index] = (values[offset] - values[offset + 1]) / (2.0 * step); offset += 2
        for index, step in enumerate(control_steps):
            B[:, index] = (values[offset] - values[offset + 1]) / (2.0 * step); offset += 2
        return nominal, A, B

    def __exit__(self, exc_type, exc, traceback):
        if self.executor is not None:
            self.executor.shutdown(wait=True, cancel_futures=True)
        self.executor = None


class install_parallel_linearization:
    def __init__(self, backend: ParallelFiniteDifferenceBackend):
        self.backend = backend
        self.original = None

    def __enter__(self):
        self.original = controller.linearize_step
        controller.linearize_step = self.backend.linearize
        return self.backend

    def __exit__(self, exc_type, exc, traceback):
        controller.linearize_step = self.original
