"""F2: exact-resume test (E04): continuous training and interrupted+resumed
training must agree to <=1e-6 on model parameters."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch


def _synthetic_cache(trajectories=3, length=90, seed=7):
    """Minimal temp NPZ caches (relative_state47 + control7) for train_phase."""
    rng = np.random.default_rng(seed)
    tmp = Path(tempfile.mkdtemp(prefix="v3r_resume_"))
    entries = []
    state_dim, control_dim = 47, 7
    for trajectory_id in range(trajectories):
        x = rng.normal(size=(length, state_dim)) * 0.3
        u = rng.normal(size=(length - 1, control_dim)) * 0.2
        x[1:] = 0.95 * x[:-1] + u @ (rng.normal(size=(control_dim, state_dim)) * 0.01)
        path = tmp / f"syn_{trajectory_id}.npz"
        window_starts = np.arange(0, length - 20, 20, dtype=int)
        window_classes = np.asarray(["steady"] * len(window_starts))
        np.savez(
            path,
            relative_state47=x,
            actual_steering4=np.zeros((length, 4)),
            control7=u,
            window_start=window_starts,
            window_class=window_classes,
        )
        entries.append(
            {
                "trajectory_id": trajectory_id,
                "base_family_id": f"syn_family_{trajectory_id}",
                "cache_path": str(path),
                "split": "train",
                "scenario": "D0",
                "direction": "none",
                "member": "none",
                "plant": "V1-ES",
                "law": "V1",
                "seed": seed,
            }
        )
    normalization = {
        "relative_state47_mean": np.zeros(47),
        "relative_state47_scale": np.ones(47),
        "actual_steering4_mean": np.zeros(4),
        "actual_steering4_scale": np.ones(4),
        "control7_mean": np.zeros(7),
        "control7_scale": np.ones(7),
        "force_payload_body8_mean": np.zeros(8),
        "force_payload_body8_scale": np.ones(8),
        "internal_force8_mean": np.zeros(8),
        "internal_force8_scale": np.ones(8),
        "source_split": np.asarray("train"),
    }
    return entries, normalization, tmp


def _build_model():
    from lift import TriangularResidualKoopman

    return TriangularResidualKoopman(
        torch.as_tensor(np.eye(47) * 0.95, dtype=torch.float64),
        torch.as_tensor(np.zeros((47, 7)), dtype=torch.float64),
        torch.as_tensor(np.zeros(47), dtype=torch.float64),
        residual_dim=16, branch_output=8, hidden_width=16,
    )


def _run_phase(dataset, protocol, stream, out_dir, steps, resume, seed):
    from train import train_phase

    torch.manual_seed(int(seed))
    model = _build_model()
    return train_phase(
        model, dataset, protocol,
        loss_spec="MH", fold=-1, variant="RESUME", run_id="test", attempt_id="a1",
        stage="F2", identity={"seed": seed}, device=torch.device("cpu"),
        batch_stream=stream, lr=1e-3, steps=steps, grad_clip=1.0,
        monitor_every=1000000, early_stop_patience=1000000,
        closure_scale=None, tail_scale=None, out_dir=out_dir, monitor_fn=None,
        resume=resume,
    )


def test_resume_equals_continuous(protocol):
    entries, normalization, tmp = _synthetic_cache()
    try:
        from data_contract import FrozenSequenceDataset
        from train import build_batch_stream

        dataset = FrozenSequenceDataset(entries, normalization, horizon=20)
        stream = build_batch_stream(dataset, batches=60, batch_windows=64, seed=11)
        out = Path(tmp) / "outs"
        _run_phase(dataset, protocol, stream, out / "continuous", 40, False, 11)
        _run_phase(dataset, protocol, stream, out / "interrupted", 20, False, 11)
        _run_phase(dataset, protocol, stream, out / "interrupted", 40, True, 11)
        continuous = torch.load(out / "continuous" / "last.pt", map_location="cpu")["model_state"]
        resumed = torch.load(out / "interrupted" / "last.pt", map_location="cpu")["model_state"]
        max_diff = 0.0
        for key in continuous:
            max_diff = max(max_diff, float(torch.max(torch.abs(continuous[key] - resumed[key])).item()))
        assert max_diff <= 1e-6, f"resume mismatch {max_diff}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
