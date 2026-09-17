"""Rebuild a minimal, deterministic latency case without copying data modules."""
from __future__ import annotations

import copy
from pathlib import Path

import torch

from background_core import build_data, digest_arrays, sha


def build_benchmark_case(queue, spec):
    """Return (model, one-sample data view) from immutable checkpoint/fold identity."""
    required = {"checkpoint", "checkpoint_sha", "fold", "gamma", "sample_id", "normalization_sha"}
    missing = sorted(required - set(spec))
    if missing:
        raise ValueError(f"incomplete timing specification: {missing}")
    checkpoint = Path(spec["checkpoint"]).resolve()
    if sha(checkpoint) != spec["checkpoint_sha"]:
        raise ValueError("timing checkpoint identity changed")
    fold = int(spec["fold"])
    queue.contexts.clear()
    ctx = queue.context(fold)
    if digest_arrays(ctx["norm"]) != spec["normalization_sha"]:
        raise ValueError("timing normalization identity changed")
    data = build_data(ctx["outer_e"], ctx["norm"], queue.guard, fold, "outer_evaluate",
                      ctx["resolver"], queue.decoder, "cuda")
    keys = [(m["family"], m["trajectory"], int(m["start"])) for m in data.meta]
    wanted = tuple(spec["sample_id"])
    if wanted not in keys:
        raise ValueError("registered timing sample is absent")
    idx = keys.index(wanted)
    case = copy.copy(data)
    case.x = data.x[idx:idx + 1]
    case.u = data.u[idx:idx + 1]
    case.y = data.y[idx:idx + 1]
    case.force = data.force[idx:idx + 1]
    case.internal = data.internal[idx:idx + 1]
    case.law_constants = data.law_constants[idx:idx + 1]
    case.projectors = data.projectors[idx:idx + 1]
    case.scenario = data.scenario[idx:idx + 1]
    case.meta = [data.meta[idx]]
    model, _ = queue.load_model(checkpoint, ctx, int(spec["seed"]))
    with torch.no_grad():
        model.E.mul_(float(spec["gamma"]))
    return model.cpu(), case
