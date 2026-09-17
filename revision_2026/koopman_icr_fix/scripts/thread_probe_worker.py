from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root / "src"), str(root / "plant"), str(root / "scripts")]

    import numpy as np

    from generate_data import resolved_params, simulate_trajectory
    from scenarios import ScenarioSpec

    protocol = json.loads(Path(args.protocol).read_text(encoding="utf-8"))
    seed = int(protocol["i1"]["seed"])
    params = resolved_params(seed, protocol)
    spec = ScenarioSpec("D0", "none", 0.04, None, False)
    summary, arrays = simulate_trajectory(
        spec,
        "V1",
        seed,
        params,
        protocol,
        actuator_mode="A3",
        load_transfer_enabled=True,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, **arrays)
    output.with_suffix(".json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
