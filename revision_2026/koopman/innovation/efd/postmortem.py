from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

import audit
from config import EFDConfig
from dataset import load_split
from efd_heads import EFDHead, predict
from h2_adapter import FrozenH2
from physics_decoder import unit
from transforms import mirror_lr, mirror_points, rotate_global_x0


PERM = [1, 0, 3, 2]


def _load_head(path: Path) -> EFDHead:
    with np.load(path, allow_pickle=False) as s:
        return EFDHead(
            np.asarray(s["coef"], float), np.asarray(s["mean"], float),
            np.asarray(s["std"], float), np.asarray(s["dims"], int),
            str(s["kind"].item()), np.asarray(s["force_scale"], float),
            float(s["theta_deg"].item()),
        )


def _rel_p95(actual: np.ndarray, expected: np.ndarray) -> float:
    """Per-vector relative p95 with a data-scale floor, avoiding zero-vector blow-up."""
    a = np.asarray(actual, float).reshape(*actual.shape[:-1], -1)
    e = np.asarray(expected, float).reshape(*expected.shape[:-1], -1)
    scale = max(float(np.median(np.linalg.norm(e, axis=-1))), 1e-9)
    rel = np.linalg.norm(a - e, axis=-1) / np.maximum(np.linalg.norm(e, axis=-1), 1e-3 * scale)
    return float(np.quantile(rel, .95))


def _mirror_vec(v: np.ndarray) -> np.ndarray:
    out = v[:, :, PERM].copy()
    out[..., 1] *= -1
    return out


def _corrected_disp(pred_x: np.ndarray, norms: dict[str, np.ndarray]) -> np.ndarray:
    physical = pred_x[..., :46] * norms["x_std"] + norms["x_mean"]
    return physical[..., 30:38].reshape(len(pred_x), 20, 4, 2)


def _raw_mirror_g(raw: np.ndarray) -> np.ndarray:
    out = raw.copy()
    out[..., :4] = raw[..., :4][..., PERM]
    # t=J n reverses handedness under reflection, hence b is odd.
    out[..., 4:8] = -raw[..., 4:8][..., PERM]
    out[..., 8:12] = raw[..., 8:12][..., PERM]
    return out


def _strict_pair_audit(cfg: EFDConfig) -> dict[str, Any]:
    manifest = json.loads((cfg.results / "d6efd" / "manifest.json").read_text(encoding="utf-8"))["completed"]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in manifest:
        groups.setdefault(row["mirror_pair_id"], []).append(row)
    counts = {"pairs": len(groups), "two_members": 0, "same_physical_scene": 0,
              "same_pair_rng_seed": 0, "opposite_sign": 0, "strict_metadata_pairs": 0}
    examples = []
    for pair_id, pair in sorted(groups.items()):
        if len(pair) != 2:
            continue
        counts["two_members"] += 1
        a, b = sorted(pair, key=lambda z: z["mirror_sign"])
        same_scene = a["physical_scene"] == b["physical_scene"]
        same_rng = a["pair_rng_seed"] == b["pair_rng_seed"]
        opposite = a["mirror_sign"] == -b["mirror_sign"]
        counts["same_physical_scene"] += int(same_scene)
        counts["same_pair_rng_seed"] += int(same_rng)
        counts["opposite_sign"] += int(opposite)
        strict = same_scene and same_rng and opposite
        counts["strict_metadata_pairs"] += int(strict)
        if len(examples) < 8 and not strict:
            examples.append({"pair_id": pair_id, "scenes": [a["physical_scene"], b["physical_scene"]],
                             "rng": [a["pair_rng_seed"], b["pair_rng_seed"]],
                             "sign": [a["mirror_sign"], b["mirror_sign"]]})
    return {**counts, "strict_pair_fraction": counts["strict_metadata_pairs"] / max(counts["pairs"], 1),
            "examples": examples,
            "conclusion": "metadata already disproves strict mirroring; array-level mirror equality is therefore not claimed"}


def _plot(stage: Path, result: dict[str, Any], model_hash: str) -> str:
    import matplotlib.pyplot as plt
    eq = result["equivariance_decomposition"]
    labels = ["rot30", "rot60", "mirror"]
    layers = [("H2 geometry", "H2_geometry_relative_p95"),
              ("EFD raw head", "head_raw_relative_p95"),
              ("combined disp", "combined_displacement_relative_p95"),
              ("decoded force", "decoded_force_relative_p95")]
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.5))
    x = np.arange(3); width = .19
    for j, (name, key) in enumerate(layers):
        ax[0].bar(x + (j - 1.5) * width, [100 * eq[k][key] for k in ("rotation_30", "rotation_60", "mirror")], width, label=name)
    ax[0].axhline(2, color="red", ls="--", lw=1, label="2% gate")
    ax[0].set_xticks(x, labels); ax[0].set_yscale("symlog", linthresh=1e-6)
    ax[0].set_ylabel("relative p95 (%)"); ax[0].set_title("Layerwise equivariance diagnostic")
    ax[0].legend(fontsize=7)
    fb = result["fallback_rates"]
    vals = [fb["all_points"], fb["predicted_active_causal"], fb["current_measured_active_causal"]]
    ax[1].bar(["all", "pred-active", "current-active"], 100 * np.asarray(vals), color=["#777777", "#4472c4", "#70ad47"])
    ax[1].axhline(1, color="red", ls="--", lw=1, label="1% gate"); ax[1].set_ylabel("fallback rate (%)")
    ax[1].set_title("Full-validation causal fallback"); ax[1].tick_params(axis="x", rotation=15); ax[1].legend(fontsize=8)
    mp = result["strict_mirror_pair_audit"]
    ax[2].bar(["paired IDs", "same scene", "strict mirror"], [mp["pairs"], mp["same_physical_scene"], mp["strict_metadata_pairs"]], color=["#4472c4", "#ed7d31", "#c00000"])
    ax[2].set_ylabel("pair count"); ax[2].set_title("Mirror-pair contract audit"); ax[2].tick_params(axis="x", rotation=15)
    fig.suptitle(f"EFD-v1 postmortem | validation windows={result['fallback_validation_windows']} | model {model_hash[:12]}")
    fig.tight_layout(); path = stage / "09_postmortem_diagnostics.png"; fig.savefig(path, dpi=180); plt.close(fig)
    return str(path)


def run(cfg: EFDConfig, limit: int = 512) -> dict[str, Any]:
    stage = cfg.results / "postmortem"
    stage.mkdir(parents=True, exist_ok=True)
    data = load_split(cfg.project_root, "validation", False)
    n = min(limit, len(data["x0"]))
    d = {k: (v[:n] if isinstance(v, np.ndarray) and len(v) == len(data["x0"]) else v) for k, v in data.items()}
    head = _load_head(cfg.results / "e4_g_efd" / "models" / "G_EFD_full_train.npz")
    h2 = FrozenH2(cfg.koopman / "innovation_results" / "t4_h2" / "models" / "N2-seed-151002.npz")
    floor = float(json.loads((cfg.results / "e3_baselines" / "metric_thresholds.json").read_text(encoding="utf-8"))["direction_floor_m"])
    norms = d["norms"]

    base_h2 = d["h2"]
    base_raw = head.raw(d["x0"], d["u"], norms)
    base = predict(head, d, floor)
    base_disp = _corrected_disp(base["x"], norms)

    transformed = {}
    for label, x, u in (
        ("rotation_30", rotate_global_x0(d["x0"], norms, 30.), d["u"]),
        ("rotation_60", rotate_global_x0(d["x0"], norms, 60.), d["u"]),
        ("mirror", *mirror_lr(d["x0"], d["u"], norms)),
    ):
        td = {**d, "x0": x, "u": u, "h2": h2.predict(x, u)}
        th2 = td["h2"]
        traw = head.raw(x, u, norms)
        final = predict(head, td, floor)
        h2_disp = _corrected_disp(th2, norms)
        final_disp = _corrected_disp(final["x"], norms)
        base_h2_disp = _corrected_disp(base_h2, norms)
        if label == "mirror":
            exp_h2 = _mirror_vec(base_h2_disp)
            exp_raw = _raw_mirror_g(base_raw)
            exp_disp = _mirror_vec(base_disp)
            exp_points = mirror_points(base["points"])
        else:
            # All connector quantities are expressed in the co-rotating payload frame.
            exp_h2, exp_raw, exp_disp, exp_points = base_h2_disp, base_raw, base_disp, base["points"]
        transformed[label] = {
            "H2_geometry_relative_p95": _rel_p95(h2_disp, exp_h2),
            "head_raw_relative_p95": _rel_p95(traw, exp_raw),
            "combined_displacement_relative_p95": _rel_p95(final_disp, exp_disp),
            "decoded_force_relative_p95": _rel_p95(final["points"], exp_points),
        }

    # Equivariance follows the frozen 512-window budget, but fallback is a
    # validation-set rate and must use every validation window.
    full = predict(head, data, floor)
    mag = np.linalg.norm(full["points"], axis=-1)
    predicted_active = mag >= np.asarray(json.loads((cfg.results / "e3_baselines" / "metric_thresholds.json").read_text(encoding="utf-8"))["point_floor"])[None, None, :]
    current_mag = np.linalg.norm(data["current"], axis=-1)
    current_active = current_mag >= np.asarray(json.loads((cfg.results / "e3_baselines" / "metric_thresholds.json").read_text(encoding="utf-8"))["point_floor"])[None, :]
    current_active = np.broadcast_to(current_active[:, None, :], full["fallback"].shape)
    fallback = full["fallback"]
    fallback_rates = {
        "all_points": float(np.mean(fallback)),
        "predicted_active_causal": float(np.sum(fallback & predicted_active) / max(np.sum(predicted_active), 1)),
        "current_measured_active_causal": float(np.sum(fallback & current_active) / max(np.sum(current_active), 1)),
        "future_truth_used": False,
        "point_floor_source": "train-only frozen metric_thresholds.json",
    }
    result = {
        "status": "diagnostic_only_no_gate_recovery",
        "validation_windows": n,
        "fallback_validation_windows": len(data["x0"]),
        "development_read": False,
        "confirm_generated": False,
        "equivariance_decomposition": transformed,
        "fallback_rates": fallback_rates,
        "strict_mirror_pair_audit": _strict_pair_audit(cfg),
    }
    model_path = cfg.results / "e4_g_efd" / "models" / "G_EFD_full_train.npz"
    result["figure"] = _plot(stage, result, audit.sha256(model_path))
    (stage / "diagnostics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["diagnostics_sha256"] = audit.sha256(stage / "diagnostics.json")
    return result
