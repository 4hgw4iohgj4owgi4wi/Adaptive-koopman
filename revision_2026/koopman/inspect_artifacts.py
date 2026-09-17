from pathlib import Path
import json
import numpy as np

root = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main")
paths = [
    root / "revision_2026/koopman/k2/linear/models/S3-U1-raw.npz",
    root / "revision_2026/koopman/k2/linear/models/S3-U1-lifted.npz",
    root / "revision_2026/koopman/k3/development/normalizers.npz",
]
for path in paths:
    print("PATH", path)
    with np.load(path, allow_pickle=True) as data:
        for key in data.files:
            value = data[key]
            print(key, value.shape, value.dtype, repr(value.item())[:300] if value.ndim == 0 else "")
manifest = json.loads((root / "revision_2026/koopman/k2/data_full/manifest.json").read_text(encoding="utf-8"))
print("SUMMARY", json.dumps(manifest["summary"], ensure_ascii=False, indent=2))
print("ROW", json.dumps(manifest["trajectories"][0], ensure_ascii=False, indent=2)[:3000])
