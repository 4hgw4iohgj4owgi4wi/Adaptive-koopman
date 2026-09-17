"""Single-process RTX 5080 batch finite-difference backend."""
from __future__ import annotations

import time

import numpy as np
import torch

from ..controllers import physical_tracking_pilot as controller
from .physics_torch import TorchModel
from .rollout_batch import rollout_batch_torch


class CudaFiniteDifferenceBackend:
    def __init__(self, model, device: str = "cuda:0"):
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA_NOT_AVAILABLE")
        self.device = torch.device(device)
        self.dtype = torch.float64
        self.source_model = model
        self.model = TorchModel.from_model(model, device=self.device, dtype=self.dtype)
        self.calls: list[dict] = []

    def synchronize(self) -> None:
        torch.cuda.synchronize(self.device)

    def warm(self, state, control) -> float:
        z = torch.as_tensor(np.asarray(state, float).reshape(1, 34), dtype=self.dtype, device=self.device)
        u = torch.as_tensor(np.asarray(control, float).reshape(1, 8), dtype=self.dtype, device=self.device)
        self.synchronize(); started = time.perf_counter()
        rollout_batch_torch(z.repeat(85, 1), u.repeat(85, 1), self.model)
        self.synchronize()
        return time.perf_counter() - started

    def linearize(self, state, control, model, finite_difference_scale=1.0):
        if model is not self.source_model:
            raise ValueError("CUDA_BACKEND_MODEL_IDENTITY_MISMATCH")
        z_cpu = np.asarray(state, float).reshape(34)
        u_cpu = np.asarray(control, float).reshape(8)
        state_steps_cpu = controller._steps(34, scale=finite_difference_scale)
        control_steps_cpu = np.asarray([1e-4 if j % 2 == 0 else 1e-6 for j in range(8)]) * finite_difference_scale
        z = torch.as_tensor(z_cpu, dtype=self.dtype, device=self.device)
        u = torch.as_tensor(u_cpu, dtype=self.dtype, device=self.device)
        state_steps = torch.as_tensor(state_steps_cpu, dtype=self.dtype, device=self.device)
        control_steps = torch.as_tensor(control_steps_cpu, dtype=self.dtype, device=self.device)
        Z = z.unsqueeze(0).repeat(85, 1)
        U = u.unsqueeze(0).repeat(85, 1)
        state_index = torch.arange(34, device=self.device)
        Z[1 + 2 * state_index, state_index] += state_steps
        Z[2 + 2 * state_index, state_index] -= state_steps
        control_index = torch.arange(8, device=self.device)
        U[69 + 2 * control_index, control_index] += control_steps
        U[70 + 2 * control_index, control_index] -= control_steps
        self.synchronize(); started = time.perf_counter()
        Y = rollout_batch_torch(Z, U, self.model)
        self.synchronize(); kernel_s = time.perf_counter() - started
        transfer_started = time.perf_counter()
        values = Y.detach().cpu().numpy()
        transfer_s = time.perf_counter() - transfer_started
        A = ((values[1:69:2] - values[2:69:2]) / (2.0 * state_steps_cpu[:, None])).T
        B = ((values[69:85:2] - values[70:85:2]) / (2.0 * control_steps_cpu[:, None])).T
        self.calls.append({"kernel_s": kernel_s, "device_to_host_and_reconstruct_s": transfer_s})
        return values[0], A, B


class install_cuda_linearization:
    def __init__(self, backend: CudaFiniteDifferenceBackend):
        self.backend = backend
        self.original = None

    def __enter__(self):
        self.original = controller.linearize_step
        controller.linearize_step = self.backend.linearize
        return self.backend

    def __exit__(self, exc_type, exc, traceback):
        controller.linearize_step = self.original
