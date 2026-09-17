import sys
sys.path.insert(0, r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman")
import compare_pipeline as cp

for name, model in cp.all_frozen_models().items():
    print(name, sorted(model))
