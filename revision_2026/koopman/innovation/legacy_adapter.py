from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import numpy as np


class FrozenK1Adapter:
    def __init__(self, koopman_root: Path):
        self.koopman_root = Path(koopman_root)
        if str(self.koopman_root) not in sys.path: sys.path.insert(0, str(self.koopman_root))
        import compare_pipeline as cp
        import universal_v2_pipeline as uv2
        self.cp, self.uv2 = cp, uv2
        with np.load(self.koopman_root / "universal_v2" / "normalizers.npz", allow_pickle=False) as src:
            self.norms = {key: np.asarray(src[key], dtype=float) for key in src.files}
        _, original = cp.load_rows(cp.DATA)
        old = cp.train_moments(original)
        self.model = uv2.adapt_model_metrics(cp.all_frozen_models()["K1"], old, self.norms)

    def lift(self, x_s3: np.ndarray) -> np.ndarray:
        return self.cp.lift(self.model, np.asarray(x_s3, dtype=float))

    def step(self, z: np.ndarray, u: np.ndarray) -> np.ndarray:
        return self.cp.model_step(self.model, np.asarray(z), np.asarray(u))[0]

    def decode_state(self, z: np.ndarray) -> np.ndarray:
        return self.cp.decode(self.model, np.asarray(z))[2]

    def decode_force(self, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        force = self.cp.decode(self.model, np.asarray(z))[1]
        return force[:8].reshape(4, 2), force[8:10]

    def rollout_normalized(self, x0_s3: np.ndarray, u_future: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        z = self.lift(x0_s3); xs, fs = [], []
        for u in np.asarray(u_future):
            z = self.step(z, u); _, f, x = self.cp.decode(self.model, z); xs.append(x); fs.append(f)
        return np.asarray(xs), np.asarray(fs)

