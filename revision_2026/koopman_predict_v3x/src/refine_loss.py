"""KC4: refined training objectives (koopman_next.md 7.2).

L_align   = sum_h a_h M_h^{fit,eps} + R
L_fixed   = L_align + (M20_0/55) * sum_j 0.5*[g_j]_+^2
L_adaptive= L_align + (M20_0/55) * sum_j (lambda_j*g_j + 0.5*[g_j]_+^2)

a = (0.10, 0.20, 0.25, 0.45) over h=(1,5,10,20); R = 1e-4||E||^2 + 1e-5||theta||^2
(E appears in both terms by definition).  g_batch keeps gradients; lambda is
detached and updated every 500 formal steps on the FULL fit set as
lambda <- clip(lambda + 0.5*g_fit, 0, 20).  M20_0 is the fold's frozen pure
linear anchor M20.  Training uses smooth RMSE, evaluation exact RMSE.
"""
from __future__ import annotations

import torch

from guard_core import balanced_mean, component_errors, constraints, smooth_rmse

HW = (0.10, 0.20, 0.25, 0.45)
H = (1, 5, 10, 20)


def batch_errors(model, data, ix, smooth=True, dtype=torch.float32):
    """Errors (len(ix), 4, 6) for a batch using the model rollout."""
    pred = model.rollout(data.x[ix].to(dtype), data.u[ix].to(dtype), H)["xhat"]
    pred = pred[:, [h - 1 for h in H]]
    f, inn = data.physical(pred, ix)
    target = data.y[ix][:, [h - 1 for h in H]].to(dtype)
    ft = data.force[ix][:, [h - 1 for h in H]].to(dtype)
    it = data.internal[ix][:, [h - 1 for h in H]].to(dtype)
    errors = component_errors(pred, target, f, inn, ft, it, data.norm, smooth)
    if not torch.isfinite(errors).all():
        raise FloatingPointError("nonfinite batch errors")
    return errors, pred, target


def loss_kc(model, data, ix, method, anchor, lam, anchor_scale_m20):
    """Batch training objective for the KC methods.

    anchor: full-fit pure-linear anchor stats (12,4,6) on the candidate device;
    anchor_scale_m20: scalar M20_0 used to scale the guard penalty.
    """
    errors, _, _ = batch_errors(model, data, ix, smooth=True)
    stats = balanced_mean(errors, data.scenario[ix])
    val = sum(w * stats[:, j, 0].mean() for j, w in enumerate(HW))
    reg = 1e-4 * (model.E**2).sum() + 1e-5 * sum((p**2).sum() for p in model.parameters())
    if method == "aligned":
        return val + reg
    g = constraints(stats, anchor.to(stats))
    scale = float(anchor_scale_m20) / 55.0
    if method == "fixed_guard":
        return val + scale * 0.5 * g.clamp_min(0.0).pow(2).sum() + reg
    if method == "adaptive_guard":
        lam_d = lam.detach().to(stats)
        return val + scale * ((lam_d * g) + 0.5 * g.clamp_min(0.0).pow(2)).sum() + reg
    raise ValueError(method)


def residual_loss(model, data, ix):
    """One-step residual squared-error curriculum objective (KC 7.3):
    ||E phi(x,u) - r||^2_Omega = group-weighted one-step state MSE (identity),
    Omega group totals 0.30/0.20/0.20/0.30 over slices 0:3/3:19/19:31/31:47,
    each uniform within the group.  F/G/c get no one-step data gradient here."""
    from background_core import mse_data_loss
    pred1 = model.rollout(data.x[ix].float(), data.u[ix, :1].float(), (1,))["xhat"][:, 0]
    err = pred1 - data.y[ix][:, 0].float()
    val = mse_data_loss(err, data.scenario[ix])
    reg = 1e-4 * (model.E**2).sum() + 1e-5 * sum((p**2).sum() for p in model.parameters())
    return val + reg


def full_fit_constraints(model, fit, anchor_fit):
    """55 guard values on the full fit set (used for the lambda update and
    monitoring).  Returns (constraint vector, M20)."""
    with torch.no_grad():
        clone = __import__("copy").deepcopy(model).double().eval()
        from guard_core import evaluate

        stats, _ = evaluate(clone, fit)
    g = constraints(stats, anchor_fit.to(stats))
    m20 = float(stats[:, 3, 0].mean())
    return g, m20
