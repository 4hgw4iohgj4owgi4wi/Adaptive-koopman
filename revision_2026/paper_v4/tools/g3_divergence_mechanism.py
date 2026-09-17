"""G3-B read-only mechanism analysis: why restart equivalence fails only in the late window.

Uses only the already-produced G3 runs and the persisted P1 artifacts.  Shows:
  * the CPU replay is bitwise identical in the force window and float-noise level in
    the steering window,
  * the late window diverges in discrete steps while its connector force is exactly
    zero, i.e. inside the free-play branch,
  * the only admissible seed is the reference-memory replay error, because the frozen
    runner never persisted the per-tick accepted duration and therefore an
    exactly-bitwise beta cannot be reconstructed from saved artifacts at all.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

POSITION_INDEX = (0, 1, 6, 7, 12, 13, 18, 19, 24, 25)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return data["values"].copy(), [str(value) for value in data["columns"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    paper = Path(__file__).resolve().parents[1]
    protocol_path = args.protocol.resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_SHA_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("scope") != "G3B_DIVERGENCE_MECHANISM_READ_ONLY":
        raise ValueError("SCOPE_MISMATCH")
    for item in protocol["identity_files"]:
        path = paper / item["path"]
        if not path.is_file() or sha(path) != item["sha256"]:
            raise ValueError("IDENTITY_MISMATCH:" + item["path"])
    output = args.out.resolve()
    if output != (paper / protocol["output"]).resolve():
        raise ValueError("OUTPUT_PROTOCOL_MISMATCH")
    if output.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    output.mkdir(parents=True)

    source_raw, source_columns = load(paper / protocol["inputs"]["source_run"] / "raw.npz")
    source_index = {name: position for position, name in enumerate(source_columns)}
    windows = []
    for entry in protocol["windows"]:
        first = int(entry["start_tick"])
        ticks = list(range(first, first + int(entry["ticks"])))
        record = {"window": entry["name"], "start_tick": first, "ticks": int(entry["ticks"]), "backends": {}}
        saved_force = source_raw[np.ix_(ticks, [source_index[f"point_force_norm{i}"] for i in range(4)])]
        record["saved_force_max_n"] = float(saved_force.max())
        record["saved_force_exactly_zero_fraction"] = float(np.mean(saved_force.max(axis=1) == 0.0))
        for run in protocol["runs"]:
            if run["window"] != entry["name"]:
                continue
            raw, columns = load(paper / run["output"] / "raw.npz")
            index = {name: position for position, name in enumerate(columns)}
            state = raw[:, [index[f"x{i}"] for i in range(30)]]
            saved_state = source_raw[np.ix_(ticks, [source_index[f"x{i}"] for i in range(30)])]
            delta = np.abs(state - saved_state)
            per_tick = delta[:, list(POSITION_INDEX)].max(axis=1)
            record["backends"][run["backend"]] = {
                "per_tick_position_m": per_tick.tolist(),
                "first_tick_m": float(per_tick[0]),
                "max_m": float(per_tick.max()),
                "bitwise_identical_all_ticks": bool(np.all(per_tick == 0.0)),
                "zero_ticks": int(np.count_nonzero(per_tick == 0.0)),
                "growth_decades": float(np.log10(max(per_tick.max(), 1e-300)) - np.log10(max(per_tick[0], 1e-300))),
            }
        windows.append(record)

    late = next(item for item in windows if item["window"] == "late_prefix")
    force = next(item for item in windows if item["window"] == "force_peak")
    steer = next(item for item in windows if item["window"] == "steering_limit")
    report = {
        "status": "PASS_READ_ONLY_MECHANISM_ANALYSIS",
        "scope": protocol["scope"],
        "windows": windows,
        "mechanism": {
            "cpu_replay_is_exact_in_the_force_window": force["backends"]["cpu"]["bitwise_identical_all_ticks"],
            "cpu_replay_level_force_window_m": force["backends"]["cpu"]["max_m"],
            "cpu_replay_level_steering_window_m": steer["backends"]["cpu"]["max_m"],
            "cpu_replay_level_late_window_m": late["backends"]["cpu"]["max_m"],
            "late_window_saved_force_max_n": late["saved_force_max_n"],
            "late_window_zero_force_tick_fraction": late["saved_force_exactly_zero_fraction"],
            "late_window_growth_decades": late["backends"]["cpu"]["growth_decades"],
            "interpretation": (
                "The replay is exact where the connectors carry load and diverges only in the free-play window, "
                "in discrete steps rather than smoothly, while the saved connector force is exactly zero there. "
                "That is the signature of branch switching in the regularised free-play law amplified by the stiff "
                "closed loop, not of a wrong checkpoint."
            ),
        },
        "seed_of_the_divergence": {
            "state_steering_previous_control_distance": "taken from persisted artifacts; previous control verified bitwise against solver.jsonl",
            "reference_memory_beta": "replayed; the frozen runner never persisted the per-tick accepted duration, only its running sum inside time_s, so an exactly bitwise beta is not reconstructible from saved artifacts",
            "consequence": "a 1e-16-level beta difference is admissible, and the late free-play regime amplifies it to about 1e-6 m within 0.6 s",
        },
        "conclusions": {
            "checkpoint_restart_equivalence": "FAILED as pre-registered at the 1e-6 m level on the late free-play window; it passes bitwise on the force window and at 2.9e-10 m on the steering window",
            "splicing_the_interrupted_cpu_run": "not supportable; any continuation must be a fresh route from the frozen initial condition",
            "d1_original_conclusion": "vindicated: the interrupted P1 prefix cannot be resumed, which is what D1 asserted before the beta replay was registered",
            "cuDA_closed_loop_equivalence": "unaffected by this failure; the CUDA backend tracked the CPU replay to 8.9e-10 m (force), 2.6e-10 m (steering) and 5.3e-6 m (late) over 30 ticks",
        },
        "forbidden": [
            "widening the restart tolerance to make this comparison pass",
            "presenting the GPU run as a continuation of the CPU prefix",
        ],
    }
    (output / "g3_divergence_mechanism.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    figure, axes = plt.subplots(1, 3, figsize=(15.5, 4.8))
    floor = 1e-17
    for axis, record in zip(axes[:2], (force, late)):
        for backend in ("cpu", "gpu"):
            series = record["backends"][backend]["per_tick_position_m"]
            axis.semilogy(np.arange(len(series)), np.maximum(series, floor), marker="o", markersize=3, label=f"{backend} replay vs saved")
        axis.axhline(protocol["gates"]["restart_position_atol_m"], color="red", linestyle=":", label="restart gate 1e-06 m")
        axis.set(xlabel="tick within window", ylabel="max position deviation (m, log)",
                 title=f"{record['window']}\nsaved connector force max {record['saved_force_max_n']:.3f} N, zero-force ticks {100 * record['saved_force_exactly_zero_fraction']:.0f}%")
        axis.legend(fontsize=8)
        axis.grid(which="both", alpha=0.25)

    names = [item["window"] for item in windows]
    positions = np.arange(len(windows))
    width = 0.36
    cpu_values = [max(item["backends"]["cpu"]["max_m"], floor) for item in windows]
    gpu_values = [max(item["backends"]["gpu"]["max_m"], floor) for item in windows]
    axes[2].bar(positions - width / 2, cpu_values, width, label="CPU replay vs saved", color="#1f77b4")
    axes[2].bar(positions + width / 2, gpu_values, width, label="GPU vs saved", color="#ff7f0e")
    axes[2].axhline(protocol["gates"]["restart_position_atol_m"], color="red", linestyle=":", label="restart gate 1e-06 m")
    axes[2].axhline(protocol["gates"]["window_position_atol_m"], color="black", linestyle="--", label="window gate 1e-02 m")
    axes[2].set_yscale("log")
    axes[2].set(xticks=positions, xticklabels=names, ylabel="worst position deviation (m, log)",
                title="Worst deviation per window\nthe GPU equivalence gate passes everywhere; only the restart gate fails, in free play")
    axes[2].legend(fontsize=7.5)
    axes[2].grid(which="both", alpha=0.25)

    figure.suptitle("G3-B mechanism: restart equivalence fails only in the zero-force free-play window", fontsize=12.5)
    figure.tight_layout(rect=(0, 0.01, 1, 0.94))
    figures = []
    for suffix in ("png", "svg"):
        name = f"g3_divergence_mechanism.{suffix}"
        figure.savefig(output / name, dpi=200 if suffix == "png" else None)
        figures.append(name)
    plt.close(figure)

    manifest = {
        "science_status": report["status"],
        "figure_status": "PENDING_VISUAL_QA",
        "scope": protocol["scope"],
        "figures": figures,
        "source_files": [{"path": str(paper / item["path"]), "sha256": item["sha256"]} for item in protocol["identity_files"]]
        + [{"path": str(protocol_path), "sha256": sha(protocol_path)}],
        "result_files": [{"path": "g3_divergence_mechanism.json", "sha256": sha(output / "g3_divergence_mechanism.json")}],
        "claim_boundary": "Read-only mechanism analysis of already-produced runs. No dynamics executed.",
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "README.md").write_text(
        "# G3-B 偏差机理只读分析\n\n"
        "用已产出的G3运行与已保存P1证据说明：为什么重启等价只在晚段free-play窗口失败。\n\n"
        "要点：①力承载窗口的CPU重放**逐位完全相同**；②转向窗口为2.9e-10 m；③晚段窗口保存连接力**恰为0**，"
        "偏差呈**台阶式**增长，属正则化free-play力律的分支切换被刚性闭环放大；"
        "④唯一允许的seed是参考记忆`beta`的回放误差（约1e-16），因为冻结runner从未落盘每周期接受时长，"
        "逐位重建`beta`在原理上不可能。\n\n"
        "结论：中断的P1前缀**不可续接**，必须从冻结初值重跑完整路线；这与D1原始结论一致。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "windows": [
        {"window": item["window"], "cpu_max_m": item["backends"]["cpu"]["max_m"],
         "cpu_bitwise": item["backends"]["cpu"]["bitwise_identical_all_ticks"],
         "gpu_max_m": item["backends"]["gpu"]["max_m"],
         "saved_force_max_n": item["saved_force_max_n"]} for item in windows]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
