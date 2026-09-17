from __future__ import annotations

import os
import sys
from pathlib import Path

# Anaconda MKL (libiomp5md) + PyTorch (libomp) duplicate OpenMP runtime guard;
# must be set before torch/numpy load their OpenMP runtimes.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

PROJECT_ROOT = Path(
    os.environ.get(
        "KOOPMAN_PROJECT_ROOT",
        r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main",
    )
)


@pytest.fixture(scope="session")
def project_root() -> Path:
    if not PROJECT_ROOT.is_dir():
        pytest.skip(f"project root not available: {PROJECT_ROOT}")
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def protocol(project_root: Path) -> dict:
    from contracts_v2 import read_json

    return read_json(ROOT / "config" / "protocol_v3.json")


@pytest.fixture(scope="session")
def frozen(project_root: Path, protocol: dict) -> object:
    from frozen import FrozenN6

    value = FrozenN6(project_root, protocol)
    identity = value.verify_identity(protocol)
    if not identity["passed"]:
        pytest.skip(f"frozen N6 identity failed: {identity['checks']}")
    return value


@pytest.fixture(scope="session")
def data(frozen) -> object:
    from contracts_v2 import read_json
    from data_contract import FrozenData, load_entries, load_normalization

    protocol = read_json(ROOT / "config" / "protocol_v2.json")
    entries = load_entries(frozen.n5_manifest_path())
    normalization = load_normalization(frozen.n5_normalization_path())
    return FrozenData(entries, normalization)
