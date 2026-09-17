"""EXP-R4-C integer-tick time identity audit with frozen negative tests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


EPS = np.finfo(np.float64).eps
FACTOR = 32.0
RAW_DT = 0.02
SUB_DT = 0.002
RAW_TICKS = np.arange(2101, 2226, dtype=np.int64)
SUB_TICKS = np.arange(21001, 22251, dtype=np.int64)
SOLVER_TICKS = np.arange(2100, 2225, dtype=np.int64)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(path: Path) -> tuple[np.ndarray, list[str]]:
    with np.load(path, allow_pickle=False) as data:
        return np.asarray(data["values"], dtype=np.float64), [str(x) for x in data["columns"]]


def records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def time_identity(times: np.ndarray, dt: float, expected_ticks: np.ndarray) -> dict:
    times = np.asarray(times, dtype=np.float64)
    finite = bool(np.all(np.isfinite(times)))
    ticks = np.rint(times / dt).astype(np.int64) if finite else np.zeros(len(times), dtype=np.int64)
    nominal = ticks.astype(np.float64) * dt
    error = np.abs(times - nominal)
    bound = FACTOR * EPS * np.maximum.reduce((np.ones_like(times), np.abs(times), np.abs(nominal)))
    checks = {
        "finite": finite,
        "strictly_monotone": bool(len(times) > 0 and np.all(np.diff(times) > 0.0)),
        "tick_count": bool(len(ticks) == len(expected_ticks)),
        "ticks_exact": bool(np.array_equal(ticks, expected_ticks)),
        "no_duplicate_ticks": bool(len(np.unique(ticks)) == len(ticks)),
        "time_error_within_registered_bound": bool(np.all(error <= bound)),
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "ticks": ticks,
        "error": error,
        "bound": bound,
        "maximum_error_s": float(np.max(error)) if len(error) else None,
        "minimum_bound_s": float(np.min(bound)) if len(bound) else None,
        "maximum_bound_s": float(np.max(bound)) if len(bound) else None,
    }


def select_by_ticks(values: np.ndarray, time_index: int, dt: float, expected: np.ndarray) -> tuple[np.ndarray, dict]:
    mapped = np.rint(values[:, time_index] / dt).astype(np.int64)
    positions = []
    counts = {}
    for tick in expected:
        found = np.flatnonzero(mapped == tick)
        counts[str(int(tick))] = int(len(found))
        if len(found) == 1:
            positions.append(int(found[0]))
    unique = len(positions) == len(expected)
    return values[positions] if unique else np.empty((0, values.shape[1])), {
        "all_expected_ticks_have_one_row": unique,
        "bad_tick_counts": {k: v for k, v in counts.items() if v != 1},
    }


def negative_tests() -> dict[str, bool]:
    raw = RAW_TICKS.astype(np.float64) * RAW_DT
    base = time_identity(raw, RAW_DT, RAW_TICKS)["status"] == "PASS"
    missing = time_identity(np.delete(raw, 17), RAW_DT, RAW_TICKS)["status"] == "FAIL"
    duplicate = time_identity(np.insert(raw, 17, raw[17]), RAW_DT, RAW_TICKS)["status"] == "FAIL"
    shifted = time_identity(raw + RAW_DT, RAW_DT, RAW_TICKS)["status"] == "FAIL"
    perturbed = raw.copy()
    bound = FACTOR * EPS * max(1.0, abs(float(perturbed[50])), abs(float(RAW_TICKS[50] * RAW_DT)))
    perturbed[50] += 2.0 * bound
    over_bound = time_identity(perturbed, RAW_DT, RAW_TICKS)["status"] == "FAIL"
    equivalent = np.nextafter(raw, np.full_like(raw, np.inf))
    legal_equivalent = time_identity(equivalent, RAW_DT, RAW_TICKS)["status"] == "PASS"
    sub = SUB_TICKS.astype(np.float64) * SUB_DT
    missing_substep = time_identity(np.delete(sub, 99), SUB_DT, SUB_TICKS)["status"] == "FAIL"
    baseline_dt = np.full(len(sub), SUB_DT, dtype=np.float64)
    changed_dt = baseline_dt.copy(); changed_dt[99] = np.nextafter(SUB_DT, np.inf)
    actual_dt_change = not np.array_equal(baseline_dt, changed_dt)
    baseline_physical = np.zeros((len(raw), 2), dtype=np.float64)
    changed_physical = baseline_physical.copy(); changed_physical[1, 1] = np.nextafter(0.0, 1.0)
    physical_change = not np.array_equal(baseline_physical, changed_physical)
    return {
        "registered_positive_control_passes": base,
        "missing_raw_tick_rejected": missing,
        "duplicate_raw_tick_rejected": duplicate,
        "one_control_tick_shift_rejected": shifted,
        "time_perturbation_over_bound_rejected": over_bound,
        "equivalent_legal_time_generation_passes": legal_equivalent,
        "missing_substep_rejected": missing_substep,
        "actual_dt_change_rejected_by_exact_gate": actual_dt_change,
        "physical_value_change_rejected_by_exact_gate": physical_change,
    }


def compact(identity: dict) -> dict:
    return {k: v for k, v in identity.items() if k not in ("ticks", "error", "bound")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--parallel", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    protocol_path = Path(args.protocol).resolve()
    if sha(protocol_path) != args.protocol_sha.lower():
        raise ValueError("PROTOCOL_IDENTITY_MISMATCH")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    out = Path(args.out).resolve()
    if out.exists():
        raise ValueError("REFUSING_TO_OVERWRITE_OUTPUT")
    out.mkdir(parents=True)

    folders = {
        "serial": Path(args.serial).resolve(),
        "parallel": Path(args.parallel).resolve(),
        "source": Path(args.source).resolve(),
    }
    for item in protocol["inputs"]:
        path = protocol_path.parent.parent / item["path"]
        if sha(path.resolve()) != item["sha256"]:
            raise ValueError("INPUT_IDENTITY_MISMATCH:" + item["path"])

    raw = {name: archive(folder / "raw.npz") for name, folder in folders.items()}
    sub = {name: archive(folder / "substeps.npz") for name, folder in folders.items()}
    solver = {name: records(folder / "solver.jsonl") for name, folder in folders.items()}
    columns = raw["serial"][1]
    subcolumns = sub["serial"][1]
    column_identity = all(raw[name][1] == columns for name in folders)
    subcolumn_identity = all(sub[name][1] == subcolumns for name in folders)
    if not column_identity or not subcolumn_identity:
        raise ValueError("COLUMN_IDENTITY_MISMATCH")
    time_index = columns.index("time_s")
    subtime_index = subcolumns.index("time_s")

    aligned_raw = {}
    aligned_sub = {}
    selection = {}
    for name in folders:
        aligned_raw[name], selection[name + "_raw"] = select_by_ticks(raw[name][0], time_index, RAW_DT, RAW_TICKS)
        aligned_sub[name], selection[name + "_substeps"] = select_by_ticks(sub[name][0], subtime_index, SUB_DT, SUB_TICKS)

    raw_time = {name: time_identity(aligned_raw[name][:, time_index], RAW_DT, RAW_TICKS) for name in folders}
    sub_time = {name: time_identity(aligned_sub[name][:, subtime_index], SUB_DT, SUB_TICKS) for name in folders}
    solver_window = {}
    solver_time = {}
    for name in folders:
        indexed = {int(item["tick"]): item for item in solver[name] if int(item["tick"]) in set(SOLVER_TICKS.tolist())}
        solver_window[name] = [indexed[k] for k in SOLVER_TICKS if k in indexed]
        times = np.asarray([item["time_s"] for item in solver_window[name]], dtype=np.float64)
        solver_time[name] = time_identity(times, RAW_DT, SOLVER_TICKS)

    raw_exact_indices = [i for i, name in enumerate(columns) if name not in ("time_s", "solver_wall_s")]
    sub_exact_indices = [i for i, name in enumerate(subcolumns) if name != "time_s"]
    source_problem_hashes_available = all("problem_hashes" in item for item in solver_window["source"])
    exact = {
        "serial_parallel_raw_non_time_non_wall_exact": bool(np.array_equal(aligned_raw["serial"][:, raw_exact_indices], aligned_raw["parallel"][:, raw_exact_indices], equal_nan=True)),
        "serial_source_raw_non_time_non_wall_exact": bool(np.array_equal(aligned_raw["serial"][:, raw_exact_indices], aligned_raw["source"][:, raw_exact_indices], equal_nan=True)),
        "serial_parallel_substep_non_time_exact": bool(np.array_equal(aligned_sub["serial"][:, sub_exact_indices], aligned_sub["parallel"][:, sub_exact_indices], equal_nan=True)),
        "serial_source_substep_non_time_exact": bool(np.array_equal(aligned_sub["serial"][:, sub_exact_indices], aligned_sub["source"][:, sub_exact_indices], equal_nan=True)),
        "serial_parallel_problem_hashes_exact": bool(len(solver_window["serial"]) == len(solver_window["parallel"]) == 125 and all(a["problem_hashes"] == b["problem_hashes"] for a, b in zip(solver_window["serial"], solver_window["parallel"]))),
        "serial_parallel_first_controls_exact": bool(len(solver_window["serial"]) == len(solver_window["parallel"]) == 125 and all(a["first_control"] == b["first_control"] for a, b in zip(solver_window["serial"], solver_window["parallel"]))),
        "serial_source_first_controls_exact": bool(len(solver_window["serial"]) == len(solver_window["source"]) == 125 and all(a["first_control"] == b["first_control"] for a, b in zip(solver_window["serial"], solver_window["source"]))),
    }
    identities_pass = all(x["status"] == "PASS" for x in [*raw_time.values(), *sub_time.values(), *solver_time.values()])
    selections_pass = all(item["all_expected_ticks_have_one_row"] for item in selection.values())
    negatives = negative_tests()
    checks = {
        "protocol_identity": True,
        "input_identities": True,
        "column_identity": column_identity,
        "subcolumn_identity": subcolumn_identity,
        "registered_time_identities": identities_pass,
        "unique_tick_selection": selections_pass,
        "all_non_time_and_solver_exact_gates": all(exact.values()),
        "all_negative_tests": all(negatives.values()),
    }
    status = "PASS_NEW_TIME_IDENTITY_CONTRACT" if all(checks.values()) else "FAIL"
    report = {
        "schema_version": "EXP-R4C-time-identity-v1",
        "status": status,
        "old_formal_report_status": "FAIL_UNCHANGED",
        "scope": "Time representation identity only; no physical tolerance and no dynamics rerun.",
        "protocol": str(protocol_path),
        "protocol_sha256": args.protocol_sha.lower(),
        "checks": checks,
        "selection": selection,
        "raw_time_identity": {k: compact(v) for k, v in raw_time.items()},
        "substep_time_identity": {k: compact(v) for k, v in sub_time.items()},
        "solver_time_identity": {k: compact(v) for k, v in solver_time.items()},
        "exact_gates": exact,
        "evidence_availability": {
            "source_problem_hashes_available": source_problem_hashes_available,
            "source_problem_hashes_requirement": "NOT_APPLICABLE_HISTORICAL_SOURCE_DID_NOT_RECORD_FIELD",
            "serial_parallel_problem_hashes_still_required": True,
        },
        "negative_tests": negatives,
        "decision": "RELEASE_FORCE_BEARING_WINDOW_REGISTRATION" if status.startswith("PASS") else "STOP_DEPENDENCIES",
    }
    (out / "time_identity_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    for name, color in (("serial", "#315a9c"), ("parallel", "#e18437"), ("source", "#438a5e")):
        axes[0].plot(RAW_TICKS, raw_time[name]["error"] * 1e15, label=name, color=color)
        axes[1].plot(SUB_TICKS, sub_time[name]["error"] * 1e15, label=name, color=color)
    axes[0].plot(RAW_TICKS, raw_time["source"]["bound"] * 1e15, "k:", label="registered bound")
    axes[1].plot(SUB_TICKS, sub_time["source"]["bound"] * 1e15, "k:", label="registered bound")
    axes[0].set(title="20 ms timestamp identity", xlabel="Control interval end tick", ylabel="Absolute representation error (fs)")
    axes[1].set(title="2 ms substep timestamp identity", xlabel="Substep end tick", ylabel="Absolute representation error (fs)")
    labels = list(negatives)
    axes[2].barh(np.arange(len(labels)), [1 if negatives[k] else 0 for k in labels], color=["#438a5e" if negatives[k] else "#b33a3a" for k in labels])
    axes[2].set_yticks(np.arange(len(labels)), [x.replace("_", " ") for x in labels], fontsize=7)
    axes[2].set_xlim(0, 1.05); axes[2].set(title="Frozen positive / negative tests", xlabel="Pass = 1")
    for ax in axes: ax.grid(alpha=0.2)
    axes[0].legend(fontsize=8); axes[1].legend(fontsize=8)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(out / f"time_identity_audit.{ext}", dpi=300)
    plt.close(fig)

    script_path = Path(__file__).resolve()
    manifest = {
        "science_status": status,
        "figure_status": "GENERATED_PENDING_VISUAL_QA",
        "protocol_sha256": args.protocol_sha.lower(),
        "generator": str(script_path),
        "generator_sha256": sha(script_path),
        "figures": [{
            "name": "time_identity_audit",
            "files": ["time_identity_audit.png", "time_identity_audit.svg"],
            "question": "Can each stored timestamp be uniquely assigned to the frozen integer tick while all physical arrays remain bitwise exact?",
            "caption": "EXP-R4-C independent time-identity audit. Timestamp representation error is checked against the preregistered 32-epsilon bound; physical arrays retain exact comparison. Old EXP-R4-B FAIL is unchanged.",
        }],
    }
    (out / "figure_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "README.md").write_text(
        "# EXP-R4-C 时间身份独立重审\n\n"
        "旧EXP-R4-B正式FAIL保持不变。本目录仅按冻结的新合同验证整数tick与浮点时间表示，并保持所有物理量逐位比较。\n\n"
        "- `time_identity_report.json`：正例、负例、时间界和精确物理门。\n"
        "- `time_identity_audit.png/.svg`：时间误差、登记界和负例覆盖图。\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "out": str(out), "checks": checks}, ensure_ascii=False))
    if not status.startswith("PASS"):
        raise SystemExit(20)


if __name__ == "__main__":
    main()
