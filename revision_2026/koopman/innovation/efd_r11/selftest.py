from __future__ import annotations
import inspect, sys, tempfile
from pathlib import Path
import numpy as np

from access_guard import assert_can_read
from axial_decoder import decode, reconstruct_q
from equivariant_features import feature, mirror_matrix
from fallback import causal_direction
from reynolds import commutator, project_linear_map
from transforms import mirror_control, mirror_state, mirror_vector4, output_transform, rotate_global


def _random_state(rng: np.random.Generator, n: int = 16) -> tuple[np.ndarray, np.ndarray]:
    x = rng.normal(size=(n, 46)); x[:, 30:38] *= .02; x[:, 38:46] *= .2
    u = rng.normal(size=(n, 20, 8)); return x, u


def run(project: Path) -> dict:
    rng = np.random.default_rng(201999); checks = {}
    x, u = _random_state(rng)
    for deg in (30., 60., 90.):
        error = float(np.max(np.abs(feature(rotate_global(x, np.radians(deg)), u, 20) - feature(x, u, 20))))
        checks[f"rotation_feature_{int(deg)}"] = {"value": error, "limit": 1e-12, "passed": error <= 1e-12}
    twice_x = float(np.max(np.abs(mirror_state(mirror_state(x)) - x)))
    twice_u = float(np.max(np.abs(mirror_control(mirror_control(u)) - u)))
    checks["mirror_involution"] = {"state": twice_x, "control": twice_u, "passed": max(twice_x, twice_u) == 0.}
    phi = feature(x, u, 20); phim = feature(mirror_state(x), mirror_control(u), 20); rphi = mirror_matrix(20)
    ferr = float(np.max(np.abs(phim - phi @ rphi.T)))
    checks["mirror_feature_contract"] = {"value": ferr, "limit": 1e-12, "passed": ferr <= 1e-12}
    ry = output_transform(True); w = rng.normal(size=(phi.shape[1], 16)); weq = project_linear_map(w, rphi, ry)
    cerr = commutator(weq, rphi, ry)
    checks["reynolds_commutator"] = {"value": cerr, "limit": 1e-12, "passed": cerr <= 1e-12}
    yerr = float(np.max(np.abs((phi @ weq)[..., :] @ ry.T - phim @ weq)))
    checks["reynolds_prediction"] = {"value": yerr, "limit": 1e-10, "passed": yerr <= 1e-10}

    model = project / "revision_2026" / "model"
    if str(model) not in sys.path: sys.path.insert(0, str(model))
    from four_vehicle_coupled import ModelParams, connector_diagnostics, initialize_state
    params = ModelParams(); oracle = []
    for _ in range(32):
        state = initialize_state(params, speed_mps=float(rng.uniform(.5, 4.)))
        state[:24] += rng.normal(0., 2e-3, 24)
        diag = connector_diagnostics(state, params)
        rp_yaw = state[26]; c, s = np.cos(rp_yaw), np.sin(rp_yaw); rp = np.asarray([[c, -s], [s, c]])
        d = np.asarray(diag["displacement_world_m"]) @ rp
        # The plant exposes normal_speed, not the full relative-velocity vector.
        # Axial force depends only on v dot n, so this is an exactly equivalent
        # oracle input for validating the duplicated constitutive formula.
        norm = np.linalg.norm(d, axis=-1)
        normal = d / np.maximum(norm[..., None], 1e-12)
        v = np.asarray(diag["normal_speed_mps"])[..., None] * normal
        pred = decode(d, v, params.connector.stiffness_npm, params.connector.damping_nspm, params.connector.free_play_m)
        oracle.append(np.max(np.abs(pred["force_payload"] - diag["force_payload_body_n"])))
    oerr = float(max(oracle)); checks["axial_decoder_truth_oracle"] = {"value_N": oerr, "limit_N": 1e-10, "passed": oerr <= 1e-10}
    dm = mirror_vector4(d); vm = mirror_vector4(v); fm = decode(dm, vm, 30000., 3500., .002)["force_payload"]
    merr = float(np.max(np.abs(fm - mirror_vector4(decode(d, v, 30000., 3500., .002)["force_payload"]))))
    checks["decoder_mirror"] = {"value": merr, "limit": 1e-10, "passed": merr <= 1e-10}
    q = reconstruct_q(pred["force_payload"]); checks["q_finite"] = {"passed": bool(np.all(np.isfinite(q)))}
    manual = np.asarray([[[11., 2.], [7., -3.], [-5., 13.], [17., -19.]]])
    q0 = reconstruct_q(manual); qm = reconstruct_q(mirror_vector4(manual))
    qerr = float(np.max(np.abs(q0 - qm)))
    checks["q_mirror_parity_manual_counterexample"] = {"q": q0.tolist(), "mirrored_q": qm.tolist(), "value": qerr, "passed": qerr == 0.}
    sig = inspect.signature(causal_direction); leak = any("truth" in name for name in sig.parameters)
    checks["fallback_has_no_future_truth"] = {"signature": str(sig), "passed": not leak}
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); dev_block = confirm_block = False
        try: assert_can_read("development", root)
        except PermissionError: dev_block = True
        try: assert_can_read("confirm", root)
        except PermissionError: confirm_block = True
        checks["development_confirm_access_guard"] = {"development_blocked": dev_block, "confirm_blocked": confirm_block, "passed": dev_block and confirm_block}
    fsig = inspect.signature(feature)
    checks["geometry_no_future_or_h2_geometry"] = {"signature": str(fsig), "passed": set(fsig.parameters) == {"x", "u", "horizon"}}
    return {"checks": checks, "passed": all(v["passed"] for v in checks.values())}
