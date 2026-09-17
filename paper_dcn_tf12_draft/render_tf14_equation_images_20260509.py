from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


OUT_DIR = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\equation_images_20260509")
OUT_DIR.mkdir(parents=True, exist_ok=True)


EQUATIONS = [
    (
        "eq_global_kinematics.png",
        r"\dot X_i=v_{x,i}\cos\psi_i-v_{y,i}\sin\psi_i,\quad "
        r"\dot Y_i=v_{x,i}\sin\psi_i+v_{y,i}\cos\psi_i,\quad "
        r"\dot\psi_i=r_i.",
        16,
    ),
    (
        "eq_frenet_s.png",
        r"\dot s_i=\frac{v_{x,i}\cos e_{\psi,i}-v_{y,i}\sin e_{\psi,i}}{1-\kappa(s_i)e_{y,i}}",
        19,
    ),
    (
        "eq_frenet_error.png",
        r"\dot e_{y,i}=v_{x,i}\sin e_{\psi,i}+v_{y,i}\cos e_{\psi,i},\quad "
        r"\dot e_{\psi,i}=r_i-\kappa(s_i)\dot s_i",
        17,
    ),
    (
        "eq_bicycle_vy.png",
        r"\dot v_{y,i}=-\frac{2C_f+2C_r}{m v_{x,i}}v_{y,i}"
        r"+\left(-v_{x,i}-\frac{2C_f l_f-2C_r l_r}{m v_{x,i}}\right)r_i"
        r"+\frac{2C_f}{m}\delta_i",
        15,
    ),
    (
        "eq_bicycle_r.png",
        r"\dot r_i=-\frac{2C_f l_f-2C_r l_r}{I_z v_{x,i}}v_{y,i}"
        r"-\frac{2C_f l_f^2+2C_r l_r^2}{I_z v_{x,i}}r_i"
        r"+\frac{2C_f l_f}{I_z}\delta_i",
        15,
    ),
    (
        "eq_bicycle_vx.png",
        r"\dot v_{x,i}=a_{x,i}+r_i v_{y,i},\quad v_{x,i}\geq 0.5\,\mathrm{m/s}.",
        17,
    ),
    (
        "eq_koopman_bilinear.png",
        r"z_{k+1}=Az_k+Bu_k+\sum_{j=1}^{2}u_{k,j}N_jz_k+\varepsilon_k.",
        18,
    ),
    (
        "eq_fdi_residual.png",
        r"\hat x_{i,k|k-1}=f_i(x_{i,k-1},u^{\mathrm{cmd}}_{i,k-1}),\quad "
        r"r_{i,k}=x_{i,k}-\hat x_{i,k|k-1}",
        17,
    ),
    (
        "eq_fdi_ewma.png",
        r"\rho_{i,k}=\sqrt{\sum_{\ell}\left(r_{i,k,\ell}/\eta_{\ell}\right)^2},\quad "
        r"\mathrm{EWMA}_k=\beta\,\mathrm{EWMA}_{k-1}+(1-\beta)\rho_{i,k}",
        16,
    ),
    (
        "eq_actuator_efficiency.png",
        r"u^{\mathrm{act}}_{i,k}=\Gamma_{i,k}u^{\mathrm{cmd}}_{i,k},\quad "
        r"\Gamma_{i,k}=\mathrm{diag}(\gamma_{\delta,i,k},\gamma_{a,i,k}).",
        17,
    ),
    (
        "eq_ftc_reconfig.png",
        r"u_i^{R}=\Pi_{U}\left(\hat\Gamma_i^{-1}u_i^{\mathrm{MPC}}+\Delta u_i^{\mathrm{redist}}\right),\quad "
        r"\sum_i\Delta u_i^{\mathrm{redist}}\approx u_{\mathrm{miss}}^{\mathrm{team}}.",
        15,
    ),
    (
        "eq_ftc_safe.png",
        r"u_i^{S}=\Pi_{U}\left(\mathrm{diag}(\alpha_{\delta},\alpha_a)u_i^{\mathrm{MPC}}+\Delta u_i^{\mathrm{safe}}\right).",
        17,
    ),
    (
        "eq_phase_role_output.png",
        r"u_i^{\mathrm{out}}=\Pi_{U}\left(u_i^{\mathrm{FTC}}+[\Delta\delta_i^{\mathrm{phase}},\,\Delta a_i^{\mathrm{phase}}]^{\top}\right).",
        17,
    ),
    (
        "eq_switched_error.png",
        r"e_{k+1}=A_{\sigma_k}e_k+B_{\sigma_k}\tilde\Gamma_k u_k+d_k,",
        18,
    ),
    (
        "eq_lyapunov_iss.png",
        r"V_{\sigma_{k+1}}(e_{k+1})\leq(1-\lambda_{\sigma}\Delta t)V_{\sigma_k}(e_k)"
        r"+c_d\Vert d_k\Vert^2+c_g\Vert\Gamma_k-\hat\Gamma_k\Vert^2.",
        15,
    ),
]


def render_equation(filename: str, latex: str, fontsize: int) -> None:
    fig = plt.figure(figsize=(9.0, 0.55), dpi=240)
    fig.patch.set_facecolor("white")
    fig.text(0.5, 0.5, f"${latex}$", ha="center", va="center", fontsize=fontsize, color="#111111")
    out = OUT_DIR / filename
    fig.savefig(out, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    plt.close(fig)


def main() -> None:
    for filename, latex, fontsize in EQUATIONS:
        render_equation(filename, latex, fontsize)
    print(OUT_DIR)


if __name__ == "__main__":
    main()
