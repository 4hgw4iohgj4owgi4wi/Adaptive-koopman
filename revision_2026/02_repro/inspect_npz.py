import sys
from pathlib import Path

import numpy as np


for raw in sys.argv[1:]:
    path = Path(raw)
    print(f"FILE={path}")
    if not path.exists():
        print("NOT_FOUND")
        continue
    with np.load(path, allow_pickle=True) as data:
        for key in data.files:
            value = data[key]
            print(f"{key}|shape={value.shape}|dtype={value.dtype}")
