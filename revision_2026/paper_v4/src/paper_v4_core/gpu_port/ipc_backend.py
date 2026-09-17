"""CPU-side persistent IPC client for one isolated CUDA worker process."""
from __future__ import annotations

import os
import pickle
import struct
import subprocess
import sys
import time

import numpy as np

from ..controllers import physical_tracking_pilot as controller


def model_mapping(model) -> dict:
    return {
        "vehicle_mass": float(model.vehicle.mass_kg),
        "vehicle_inertia": float(model.vehicle.yaw_inertia_kgm2),
        "lf": float(model.vehicle.lf_m),
        "lr": float(model.vehicle.lr_m),
        "cf": float(model.vehicle.cf_nprad),
        "cr": float(model.vehicle.cr_nprad),
        "mu": float(model.vehicle.mu),
        "vehicle_gravity": float(model.vehicle.gravity_mps2),
        "payload_mass": float(model.payload.mass_kg),
        "payload_inertia": float(model.payload.yaw_inertia_kgm2),
        "payload_cog_height": float(model.payload.cog_height_m),
        "payload_gravity": float(model.payload.gravity_mps2),
        "connector_stiffness": float(model.connector.stiffness_npm),
        "connector_damping": float(model.connector.damping_nspm),
        "connector_free_play": float(model.connector.free_play_m),
        "connector_smoothing_width": float(model.connector.smoothing_width_m),
        "payload_anchors": _nested_lists(model.payload_anchor_body_m),
        "vehicle_anchors": _nested_lists(model.vehicle_anchor_body_m),
    }


def _nested_lists(value) -> list:
    """Convert an array-like to nested Python lists for the CUDA worker boundary.

    The worker process must stay free of NumPy: unpickling a NumPy ndarray imports
    NumPy inside the worker, which loads a second OpenMP runtime next to the one
    Torch already owns and aborts with OMP Error #15.  Every outbound array is
    therefore converted here, before pickle serialization.
    """
    return np.asarray(value, dtype=float).tolist()


class CudaIpcFiniteDifferenceBackend:
    def __init__(self, model, device: str = "cuda:0"):
        self.source_model = model
        self.device = device
        self._parent_torch_modules = {name for name in sys.modules if name == "torch" or name.startswith("torch.")}
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        environment = os.environ.copy()
        source_root = str(__import__("pathlib").Path(__file__).resolve().parents[2])
        environment["PYTHONPATH"] = source_root + os.pathsep + environment.get("PYTHONPATH", "")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "paper_v4_core.gpu_port.gpu_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            creationflags=creationflags,
        )
        self.calls: list[dict] = []
        self.worker_purity: dict = {}
        self._send({"device": device, "model": model_mapping(model)})

    def _read_exact(self, size: int) -> bytes:
        chunks = []
        remaining = size
        while remaining:
            chunk = self.process.stdout.read(remaining)
            if not chunk:
                stderr = self.process.stderr.read().decode("utf-8", errors="replace")
                raise RuntimeError("CUDA_WORKER_TERMINATED:" + stderr)
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _send(self, value) -> None:
        payload = pickle.dumps(value, protocol=5)
        self.process.stdin.write(struct.pack("<Q", len(payload)))
        self.process.stdin.write(payload)
        self.process.stdin.flush()

    def _request(self, value):
        self._send(value)
        length = struct.unpack("<Q", self._read_exact(8))[0]
        response = pickle.loads(self._read_exact(length))
        self._assert_parent_free_of_torch()
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "CUDA_WORKER_ERROR") + "\n" + response.get("traceback", ""))
        return response

    def _assert_parent_free_of_torch(self) -> None:
        """Fail loudly if a worker reply contaminated the CPU parent with torch.

        Unpickling a reply that references any torch class imports the torch package
        into this process, which brings a second OpenMP runtime next to the MKL one
        and aborts the parent inside numpy.linalg.svd with OMP Error #15.  Detecting
        it here names the cause at the moment it happens instead of much later.
        """
        current = {name for name in sys.modules if name == "torch" or name.startswith("torch.")}
        leaked = current - self._parent_torch_modules
        if leaked:
            raise RuntimeError("CUDA_PARENT_TORCH_CONTAMINATION:" + ",".join(sorted(leaked)[:5]))

    def environment(self) -> dict:
        return self._request({"operation": "environment"})

    def rhs(self, state, controls):
        return np.asarray(self._request({"operation": "rhs", "state": _nested_lists(state), "controls": _nested_lists(controls)})["value"], float)

    def rk4(self, state, controls, dt=0.002):
        return np.asarray(self._request({"operation": "rk4", "state": _nested_lists(state), "controls": _nested_lists(controls), "dt": float(dt)})["value"], float)

    def rollout(self, z, u):
        return np.asarray(self._request({"operation": "rollout", "z": _nested_lists(z), "u": _nested_lists(u)})["value"], float)

    def warm(self, state, control) -> float:
        started = time.perf_counter()
        self.linearize(state, control, self.source_model, 1.0)
        return time.perf_counter() - started

    def linearize(self, state, control, model, finite_difference_scale=1.0):
        if model is not self.source_model:
            raise ValueError("CUDA_BACKEND_MODEL_IDENTITY_MISMATCH")
        z = np.asarray(state, float).reshape(34)
        u = np.asarray(control, float).reshape(8)
        state_steps = controller._steps(34, scale=finite_difference_scale)
        control_steps = np.asarray([1e-4 if j % 2 == 0 else 1e-6 for j in range(8)]) * finite_difference_scale
        response = self._request({
            "operation": "linearize",
            "z": _nested_lists(z),
            "u": _nested_lists(u),
            "state_steps": _nested_lists(state_steps),
            "control_steps": _nested_lists(control_steps),
        })
        values = np.asarray(response["values"], float)
        A = ((values[1:69:2] - values[2:69:2]) / (2.0 * state_steps[:, None])).T
        B = ((values[69:85:2] - values[70:85:2]) / (2.0 * control_steps[:, None])).T
        self.calls.append({"kernel_s": response["kernel_s"], "device_to_host_and_reconstruct_s": response["transfer_s"], "peak_allocated_bytes": response["peak_allocated_bytes"]})
        self.worker_purity = response.get("worker_module_audit", {})
        return values[0], A, B

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self._request({"operation": "close"})
            finally:
                self.process.wait(timeout=10)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


class install_cuda_linearization:
    def __init__(self, backend: CudaIpcFiniteDifferenceBackend):
        self.backend = backend
        self.original = None

    def __enter__(self):
        self.original = controller.linearize_step
        controller.linearize_step = self.backend.linearize
        return self.backend

    def __exit__(self, exc_type, exc, traceback):
        controller.linearize_step = self.original
