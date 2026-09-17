import sys
import numpy as np

for path in sys.argv[1:]:
    z = np.load(path, allow_pickle=False)
    print(path)
    for key in z.files:
        a = z[key]
        print(key, a.shape, a.dtype)
        if key == "metadata_json":
            print(str(a.item()))
