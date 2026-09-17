"""Binary-IPC CUDA worker.  It must never import SciPy/OSQP or write to stdout."""
from __future__ import annotations

import pickle
import struct
import sys
import time
import traceback
import math

import torch

from .physics_torch import TorchModel, rk4_step_batch, system_derivative_batch
from .rollout_batch import rollout_batch_torch


# Module audit: the worker boundary is only real if nothing outside Torch and the
# standard library is ever imported here.  Unpickling a NumPy ndarray would import
# NumPy inside this process, which loads a second OpenMP runtime alongside the one
# Torch already owns and aborts with OMP Error #15.  This audit turns the
# previously static hypothesis into a per-response measurement.
_FORBIDDEN = ("numpy", "scipy", "osqp", "pandas")
_STARTUP_MODULES = frozenset(sys.modules)
_STARTUP_FORBIDDEN = {name: any(key == name or key.startswith(name + ".") for key in _STARTUP_MODULES) for name in _FORBIDDEN}


def module_audit() -> dict:
    present = {
        name: any(key == name or key.startswith(name + ".") for key in sys.modules)
        for name in _FORBIDDEN
    }
    return {
        "forbidden_present": present,
        "forbidden_present_at_startup": dict(_STARTUP_FORBIDDEN),
        "imported_after_startup": sorted(name for name, value in present.items() if value and not _STARTUP_FORBIDDEN[name]),
        "worker_boundary_clean": not any(present.values()),
        "module_count": len(sys.modules),
    }


def read_exact(size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        chunk = sys.stdin.buffer.read(remaining)
        if not chunk:
            raise EOFError
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def receive():
    length = struct.unpack("<Q", read_exact(8))[0]
    return pickle.loads(read_exact(length))


def _plain(value, path: str = "reply"):
    """Coerce a reply payload to exact built-in primitives before pickling.

    Measured on 2026-09-15: `torch.__version__` is a `torch.torch_version.TorchVersion`
    instance, a *subclass* of str.  Pickling it stores a class reference, so the CPU
    parent's `pickle.loads` imported the whole torch package into the parent process
    (718 modules), which loads torch's OpenMP runtime next to the MKL one the parent
    already owns.  The parent then aborted inside numpy.linalg.svd with OMP Error #15.
    The worker boundary is therefore only real if nothing but exact primitives ever
    crosses it; anything else is rejected loudly instead of being sent.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    if isinstance(value, str):
        # str subclasses (torch.TorchVersion and friends) must be flattened, because
        # str(subclass_instance) can return the subclass instance itself.
        return value if type(value) is str else value.encode("utf-8").decode("utf-8")
    if isinstance(value, dict):
        return {_plain(key, f"{path}.key") if not isinstance(key, str) else key: _plain(item, f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item, f"{path}[{index}]") for index, item in enumerate(value)]
    raise TypeError(f"NON_PRIMITIVE_IN_IPC_REPLY:{path}:{type(value).__name__}")


def send(value) -> None:
    if isinstance(value, dict):
        value = {**value, "worker_module_audit": module_audit()}
    value = _plain(value)
    payload = pickle.dumps(value, protocol=5)
    sys.stdout.buffer.write(struct.pack("<Q", len(payload)))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def tensor(value, device):
    return torch.as_tensor(value, dtype=torch.float64, device=device)


def main() -> None:
    init = receive()
    device = torch.device(init["device"])
    model = TorchModel.from_mapping(init["model"], device=device, dtype=torch.float64)
    torch.cuda.reset_peak_memory_stats(device)
    while True:
        try:
            request = receive()
            operation = request["operation"]
            if operation == "close":
                send({"ok": True})
                return
            if operation == "environment":
                sample = torch.arange(16, dtype=torch.float64, device=device).reshape(4, 4)
                result = float((sample @ sample.T).sum().item())
                send({
                    "ok": True,
                    "torch": torch.__version__,
                    "torch_cuda_build": torch.version.cuda,
                    "cuda_available": torch.cuda.is_available(),
                    "device_name": torch.cuda.get_device_name(device),
                    "device_capability": list(torch.cuda.get_device_capability(device)),
                    "device_total_memory_bytes": torch.cuda.get_device_properties(device).total_memory,
                    "float64_test_result": result,
                    "float64_test_finite": bool(math.isfinite(result)),
                    "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
                })
            elif operation == "rhs":
                value = system_derivative_batch(tensor(request["state"], device), tensor(request["controls"], device), model, strict=True)
                send({"ok": True, "value": value.cpu().tolist()})
            elif operation == "rk4":
                value = rk4_step_batch(tensor(request["state"], device), tensor(request["controls"], device), float(request["dt"]), model, strict=True)
                send({"ok": True, "value": value.cpu().tolist()})
            elif operation == "rollout":
                value = rollout_batch_torch(tensor(request["z"], device), tensor(request["u"], device), model, strict=True)
                send({"ok": True, "value": value.cpu().tolist()})
            elif operation == "linearize":
                z = tensor(request["z"], device)
                u = tensor(request["u"], device)
                state_steps = tensor(request["state_steps"], device)
                control_steps = tensor(request["control_steps"], device)
                Z = z.unsqueeze(0).repeat(85, 1)
                U = u.unsqueeze(0).repeat(85, 1)
                state_index = torch.arange(34, device=device)
                control_index = torch.arange(8, device=device)
                Z[1 + 2 * state_index, state_index] += state_steps
                Z[2 + 2 * state_index, state_index] -= state_steps
                U[69 + 2 * control_index, control_index] += control_steps
                U[70 + 2 * control_index, control_index] -= control_steps
                torch.cuda.synchronize(device); started = time.perf_counter()
                values = rollout_batch_torch(Z, U, model)
                torch.cuda.synchronize(device); kernel_s = time.perf_counter() - started
                transfer_started = time.perf_counter()
                host = values.cpu().tolist()
                transfer_s = time.perf_counter() - transfer_started
                send({"ok": True, "values": host, "kernel_s": kernel_s, "transfer_s": transfer_s, "peak_allocated_bytes": torch.cuda.max_memory_allocated(device)})
            else:
                raise ValueError("UNKNOWN_OPERATION:" + str(operation))
        except EOFError:
            return
        except Exception as error:
            send({"ok": False, "error": f"{type(error).__name__}: {error}", "traceback": traceback.format_exc()})


if __name__ == "__main__":
    main()
