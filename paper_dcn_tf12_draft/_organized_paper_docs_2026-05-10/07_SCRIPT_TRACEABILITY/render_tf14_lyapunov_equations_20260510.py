from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main")
OUT = ROOT / "paper_dcn_tf12_draft" / "equation_images_lyapunov_tf14_20260510"
OUT.mkdir(parents=True, exist_ok=True)


EQUATIONS = [
    ("lyap_01_error.png", r"e_k=x_{T,k}-x_{T,k}^{\mathrm{ref}}", 18),
    ("lyap_02_team_state.png", r"x_{T,k}=[s_k,\ e_{y,k},\ e_{\psi,k},\ v_{x,k},\ v_{y,k},\ r_k]^\top", 17),
    ("lyap_03_modes.png", r"\sigma_k\in \mathcal{M}=\{N,\ R,\ S\}", 18),
    ("lyap_04_switched_system.png", r"e_{k+1}=A_{\sigma_k}e_k+B_{\sigma_k}\tilde{\Gamma}_k u_k+d_k", 18),
    ("lyap_05_spectral_projection.png", r"\rho(A_K)\leq \rho_s<1", 18),
    ("lyap_06_projection_nonexpansive.png", r"\|\Pi_U(a)-\Pi_U(b)\|\leq \|a-b\|", 18),
    ("lyap_07_disturbance_bounds.png", r"\|d_k\|\leq \bar d,\qquad 1-q_k\leq \bar q", 18),
    ("lyap_08_identification_bound.png", r"\|\tilde{\Gamma}_k\|\leq \bar\eta", 18),
    ("lyap_09_lyapunov_function.png", r"V_\sigma(e_k)=e_k^\top P_\sigma e_k,\qquad P_\sigma\succ 0", 18),
    ("lyap_10_quadratic_bounds.png", r"p_{\min}\|e_k\|^2\leq V_\sigma(e_k)\leq p_{\max}\|e_k\|^2", 18),
    ("lyap_11_lmi.png", r"A_\sigma^\top P_\sigma A_\sigma-P_\sigma\leq -\lambda_\sigma\Delta t\,P_\sigma", 17),
    ("lyap_12_p_nominal.png", r"P_N=\mathrm{diag}(0.8,\ 3.5,\ 2.8,\ 0.9,\ 0.8,\ 1.4)", 16),
    ("lyap_13_p_reconfigured.png", r"P_R=\mathrm{diag}(1.0,\ 4.5,\ 3.8,\ 1.0,\ 0.9,\ 1.7)", 16),
    ("lyap_14_p_safe.png", r"P_S=\mathrm{diag}(1.4,\ 5.5,\ 4.8,\ 1.2,\ 1.1,\ 2.0)", 16),
    ("lyap_15_lambda_values.png", r"\lambda_N=0.08,\qquad \lambda_R=0.06,\qquad \lambda_S=0.04", 17),
    ("lyap_16_nominal_contraction.png", r"V_\sigma(e_{k+1})\leq (1-\lambda_\sigma\Delta t)V_\sigma(e_k)", 18),
    ("lyap_17_w_def.png", r"w_k=B_\sigma\tilde{\Gamma}_k u_k+d_k", 18),
    ("lyap_18_w_bound.png", r"\|w_k\|\leq c_\Gamma\|\tilde{\Gamma}_k\|+\|d_k\|", 18),
    ("lyap_19_perturbed_bound.png", r"V_\sigma(e_{k+1})\leq (1-\lambda_\sigma\Delta t)V_\sigma(e_k)+c_d\|d_k\|^2+c_g\|\tilde{\Gamma}_k\|^2", 15),
    ("lyap_20_comm_bound.png", r"V_\sigma(e_{k+1})\leq (1-\lambda_\sigma\Delta t)V_\sigma(e_k)+c_d\|d_k\|^2+c_g\|\tilde{\Gamma}_k\|^2+c_q(1-q_k)^2", 14),
    ("lyap_21_predicted_upper.png", r"\widehat V_{k+1}=(1-\lambda_\sigma\Delta t)V_k+\gamma_d(1-q_k)^2+\gamma_g\|\tilde{\Gamma}_k\|^2", 15),
    ("lyap_22_gamma_values.png", r"\gamma_d=0.85,\qquad \gamma_g=0.55", 18),
    ("lyap_23_ftc_reconfig.png", r"u_i^R=\Pi_U\!\left(\hat{\Gamma}_i^{-1}u_i^{\mathrm{MPC}}+\Delta u_i^{\mathrm{redist}}\right)", 17),
    ("lyap_24_actual_input.png", r"u_i^{\mathrm{act}}=\Gamma_i u_i^R", 18),
    ("lyap_25_actual_expand.png", r"u_i^{\mathrm{act}}=u_i^{\mathrm{MPC}}+(\Gamma_i\hat{\Gamma}_i^{-1}-I)u_i^{\mathrm{MPC}}+\Gamma_i\Delta u_i^{\mathrm{redist}}+\varepsilon_\Pi", 13),
    ("lyap_26_gamma_inv_bound.png", r"\|\Gamma_i\hat{\Gamma}_i^{-1}-I\|\leq c_\eta\|\Gamma_i-\hat{\Gamma}_i\|", 17),
    ("lyap_27_safe_mode.png", r"u_i^S=\Pi_U\!\left(D_su_i^{\mathrm{MPC}}+\Delta u_i^{\mathrm{safe}}\right),\qquad D_s=\mathrm{diag}(\alpha_\delta,\alpha_a)", 15),
    ("lyap_28_mu.png", r"\mu=\max_{\sigma,\sigma'}\frac{\lambda_{\max}(P_{\sigma'})}{\lambda_{\min}(P_\sigma)}", 18),
    ("lyap_29_switch_jump.png", r"V_{\sigma_{k+1}}(e_k)\leq \mu V_{\sigma_k}(e_k)", 18),
    ("lyap_30_sum_bound.png", r"V_{\sigma_k}(e_k)\leq C_\mu\alpha^kV_{\sigma_0}(e_0)+C_\mu\sum_{j=0}^{k-1}\alpha^{k-1-j}\zeta_j", 15),
    ("lyap_31_zeta.png", r"\zeta_j=c_d\|d_j\|^2+c_g\|\tilde{\Gamma}_j\|^2+c_q(1-q_j)^2", 17),
    ("lyap_32_uniform_bound.png", r"V_{\sigma_k}(e_k)\leq C_\mu\alpha^kV_{\sigma_0}(e_0)+\frac{C_\mu}{1-\alpha}(c_d\bar d^2+c_g\bar\eta^2+c_q\bar q^2)", 14),
    ("lyap_33_limsup.png", r"\limsup_{k\to\infty}\|e_k\|\leq \sqrt{\frac{C_\mu}{p_{\min}(1-\alpha)}(c_d\bar d^2+c_g\bar\eta^2+c_q\bar q^2)}", 14),
    ("lyap_34_zero_disturbance.png", r"\bar d=0,\quad \bar\eta=0,\quad \bar q=0\quad\Rightarrow\quad \|e_k\|\leq C\alpha^k\|e_0\|", 16),
]


def render_equation(path: Path, expr: str, fontsize: int) -> None:
    fig = plt.figure(figsize=(0.01, 0.01), dpi=240)
    fig.patch.set_alpha(0.0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    txt = ax.text(
        0.5,
        0.5,
        f"${expr}$",
        ha="center",
        va="center",
        fontsize=fontsize,
        color="black",
    )
    fig.canvas.draw()
    bbox = txt.get_window_extent(renderer=fig.canvas.get_renderer()).expanded(1.08, 1.45)
    width = max(2.0, bbox.width / fig.dpi)
    height = max(0.42, bbox.height / fig.dpi)
    plt.close(fig)

    fig = plt.figure(figsize=(width, height), dpi=240)
    fig.patch.set_facecolor("white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.5, 0.5, f"${expr}$", ha="center", va="center", fontsize=fontsize, color="black")
    fig.savefig(path, dpi=240, bbox_inches="tight", pad_inches=0.06, facecolor="white")
    plt.close(fig)


def contact_sheet() -> None:
    imgs = []
    font = ImageFont.load_default()
    for name, _, _ in EQUATIONS:
        p = OUT / name
        im = Image.open(p).convert("RGB")
        tw = 420
        ratio = tw / im.width
        th = max(60, int(im.height * ratio))
        im = im.resize((tw, th))
        canvas = Image.new("RGB", (tw, th + 28), "white")
        canvas.paste(im, (0, 28))
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, 0, tw - 1, 27], fill=(245, 247, 250), outline=(190, 190, 190))
        d.text((8, 8), name, fill=(0, 0, 0), font=font)
        imgs.append(canvas)
    cols = 2
    rows = (len(imgs) + cols - 1) // cols
    cell_h = max(im.height for im in imgs)
    sheet = Image.new("RGB", (cols * 420, rows * cell_h), "white")
    for idx, im in enumerate(imgs):
        sheet.paste(im, ((idx % cols) * 420, (idx // cols) * cell_h))
    sheet.save(OUT / "_lyapunov_equation_contact_sheet.png")


def main():
    for name, expr, fontsize in EQUATIONS:
        render_equation(OUT / name, expr, fontsize)
    contact_sheet()
    print(OUT)


if __name__ == "__main__":
    main()
