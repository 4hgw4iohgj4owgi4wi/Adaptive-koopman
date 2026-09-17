from __future__ import annotations

import os
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if "KOOPMAN_PROJECT_ROOT" in os.environ:
    PROJECT_ROOT = Path(os.environ["KOOPMAN_PROJECT_ROOT"])
else:
    PROJECT_ROOT = next(
        (
            parent
            for parent in SOURCE_ROOT.parents
            if (parent / "revision_2026" / "connector_r3_4" / "src").is_dir()
        ),
        SOURCE_ROOT.parents[1],
    )
CONNECTOR_SRC = PROJECT_ROOT / "revision_2026" / "connector_r3_4" / "src"

sys.path.insert(0, str(SOURCE_ROOT / "src"))
sys.path.insert(0, str(SOURCE_ROOT / "scripts"))
sys.path.insert(0, str(CONNECTOR_SRC))
