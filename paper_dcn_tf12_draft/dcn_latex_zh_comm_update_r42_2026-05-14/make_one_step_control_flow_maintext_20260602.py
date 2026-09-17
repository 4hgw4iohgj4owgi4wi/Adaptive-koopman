from __future__ import annotations

import base64
import zlib
from html import unescape
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parent
FIG_DIR = ROOT / "figures"
STEM = "fig2_nrkdcc_one_step_control_flow_maintext_20260602"
OUT_DRAWIO = FIG_DIR / f"{STEM}.drawio"
OUT_SVG = FIG_DIR / f"{STEM}.svg"
OUT_URL = FIG_DIR / f"{STEM}.url.txt"

PAGE_W = 1600
PAGE_H = 520

COLORS = {
    "offline_fill": "#EAF3FF",
    "offline_stroke": "#2F6FBB",
    "ref_fill": "#E8FAF5",
    "ref_stroke": "#15847D",
    "online_fill": "#EEF4FA",
    "online_stroke": "#4B77A8",
    "safety_fill": "#FFF1F2",
    "safety_stroke": "#D64545",
    "plant_fill": "#F3EFFB",
    "plant_stroke": "#7E68A4",
    "neutral_stroke": "#6B7280",
    "text": "#1F2937",
    "line": "#374151",
    "feedback": "#6B7280",
    "fail": "#D64545",
}


def st(**items: str | int | float) -> str:
    return ";".join(f"{k}={v}" for k, v in items.items()) + ";"


def value(text: str) -> str:
    text = unescape(text).replace("\n", "<br>")
    return escape(text, {'"': "&quot;"})


def cell(
    cell_id: str,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    style: str,
    vertex: bool = True,
) -> str:
    vertex_attr = ' vertex="1"' if vertex else ""
    return (
        f'<mxCell id="{cell_id}" value="{value(text)}" style="{style}"{vertex_attr} parent="1">'
        f'<mxGeometry x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" as="geometry"/>'
        "</mxCell>"
    )


def rect(
    cell_id: str,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    stroke: str,
    font: int = 10,
) -> str:
    return cell(
        cell_id,
        text,
        x,
        y,
        w,
        h,
        st(
            rounded=1,
            whiteSpace="wrap",
            html=1,
            fillColor=fill,
            strokeColor=stroke,
            strokeWidth=1.6,
            fontColor=COLORS["text"],
            fontSize=font,
            align="center",
            verticalAlign="middle",
            spacing=5,
            arcSize=8,
        ),
    )


def label(cell_id: str, text: str, x: float, y: float, w: float, h: float, font: int = 8) -> str:
    return cell(
        cell_id,
        text,
        x,
        y,
        w,
        h,
        st(
            text=1,
            html=1,
            strokeColor="none",
            fillColor="none",
            align="center",
            verticalAlign="middle",
            whiteSpace="wrap",
            fontSize=font,
            fontColor=COLORS["text"],
        ),
    )


def ellipse(cell_id: str, text: str, x: float, y: float, w: float, h: float) -> str:
    return cell(
        cell_id,
        text,
        x,
        y,
        w,
        h,
        st(
            ellipse=1,
            whiteSpace="wrap",
            html=1,
            fillColor="#FFFFFF",
            strokeColor=COLORS["neutral_stroke"],
            strokeWidth=1.8,
            fontColor=COLORS["text"],
            fontSize=14,
            fontStyle=1,
            align="center",
            verticalAlign="middle",
        ),
    )


def diamond(cell_id: str, text: str, x: float, y: float, w: float, h: float) -> str:
    return cell(
        cell_id,
        text,
        x,
        y,
        w,
        h,
        st(
            rhombus=1,
            whiteSpace="wrap",
            html=1,
            fillColor="#FFFFFF",
            strokeColor=COLORS["safety_stroke"],
            strokeWidth=1.7,
            fontColor=COLORS["text"],
            fontSize=9,
            align="center",
            verticalAlign="middle",
            spacing=4,
        ),
    )


def edge(
    cell_id: str,
    text: str,
    source: str,
    target: str,
    color: str = COLORS["line"],
    dashed: bool = False,
    width: float = 1.8,
    points: list[tuple[float, float]] | None = None,
) -> str:
    pts = ""
    if points:
        pts = "<Array as=\"points\">" + "".join(
            f'<mxPoint x="{x:g}" y="{y:g}"/>' for x, y in points
        ) + "</Array>"
    return (
        f'<mxCell id="{cell_id}" value="{value(text)}" edge="1" parent="1" '
        f'source="{source}" target="{target}" style="'
        + st(
            edgeStyle="orthogonalEdgeStyle",
            rounded=1,
            orthogonalLoop=1,
            jettySize="auto",
            html=1,
            endArrow="block",
            endFill=1,
            strokeColor=color,
            strokeWidth=width,
            fontColor=color,
            fontSize=8,
            labelBackgroundColor="none",
            labelBorderColor="none",
            dashed=1 if dashed else 0,
            dashPattern="6 4" if dashed else "solid",
        )
        + f'"><mxGeometry relative="1" as="geometry">{pts}</mxGeometry></mxCell>'
    )


def point_edge(
    cell_id: str,
    text: str,
    pts: list[tuple[float, float]],
    color: str = COLORS["line"],
    dashed: bool = False,
    width: float = 1.6,
    arrow: bool = True,
) -> str:
    sx, sy = pts[0]
    tx, ty = pts[-1]
    mids = pts[1:-1]
    wp = ""
    if mids:
        wp = "<Array as=\"points\">" + "".join(
            f'<mxPoint x="{x:g}" y="{y:g}"/>' for x, y in mids
        ) + "</Array>"
    return (
        f'<mxCell id="{cell_id}" value="{value(text)}" edge="1" parent="1" style="'
        + st(
            edgeStyle="orthogonalEdgeStyle",
            rounded=1,
            html=1,
            endArrow="block" if arrow else "none",
            endFill=1 if arrow else 0,
            strokeColor=color,
            strokeWidth=width,
            fontColor=color,
            fontSize=8,
            labelBackgroundColor="none",
            dashed=1 if dashed else 0,
            dashPattern="6 4" if dashed else "solid",
        )
        + f'"><mxGeometry relative="1" as="geometry">'
        f'<mxPoint x="{sx:g}" y="{sy:g}" as="sourcePoint"/>'
        f'<mxPoint x="{tx:g}" y="{ty:g}" as="targetPoint"/>'
        f"{wp}</mxGeometry></mxCell>"
    )


def build_drawio() -> str:
    cells: list[str] = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']

    cells.append(
        rect(
            "offline",
            "<b>Offline data and bilinear Koopman predictor</b><br>"
            "<font style=\"font-size:8px\">curvature / communication / actuator-degradation data</font><br>"
            "<font style=\"font-size:8px\">input-aware robust spectral projection (IRSP)</font><br>"
            "<font style=\"font-size:8px\">model, residual bound, and certificate terms</font>",
            70,
            52,
            1460,
            84,
            COLORS["offline_fill"],
            COLORS["offline_stroke"],
            10,
        )
    )

    cells.extend(
        [
            rect(
                "ref_input",
                "<b>Reference path, payload-center progress,<br>and temporary path packet</b><br>"
                "<font style=\"font-size:8px\">p<sub>L</sub><sup>ref</sup>(s), ψ<sub>L</sub><sup>ref</sup>, κ<sub>r</sub>, P<sub>i,k</sub><sup>tmp</sup></font>",
                50,
                210,
                235,
                108,
                COLORS["ref_fill"],
                COLORS["ref_stroke"],
            ),
            ellipse("sum", "Σ<br><font style=\"font-size:8px\">+ / -</font>", 310, 238, 60, 60),
            rect(
                "network",
                "<b>4WS local paths and<br>communication degradation</b><br>"
                "<font style=\"font-size:8px\">link quality, delay, packet loss</font><br>"
                "<font style=\"font-size:8px\">q<sub>ij,k</sub>, q<sub>k</sub><sup>net</sup>, τ, ℓ<sub>ij,k</sub></font>",
                395,
                210,
                235,
                108,
                COLORS["ref_fill"],
                COLORS["ref_stroke"],
            ),
            rect(
                "koopman_mpc",
                "<b>Koopman prediction and<br>communication-quality-aware consensus MPC</b><br>"
                "<font style=\"font-size:8px\">z<sub>k+1|k</sub>, C0--C3 schedules</font><br>"
                "<font style=\"font-size:8px\">consensus weights and constraint tightening</font>",
                660,
                210,
                235,
                108,
                COLORS["online_fill"],
                COLORS["online_stroke"],
            ),
            rect(
                "execution",
                "<b>Execution-layer protection</b><br>"
                "<font style=\"font-size:8px\">FDI/FTC, PPC guard, role scheduling</font><br>"
                "<font style=\"font-size:8px\">curvature-window payload-protection switch</font>",
                925,
                210,
                235,
                108,
                COLORS["safety_fill"],
                COLORS["safety_stroke"],
            ),
            diamond(
                "cert_decision",
                "<b>Certificate<br>passes?</b><br><font style=\"font-size:8px\">m<sub>k</sub> ≥ -ε<sub>m</sub></font>",
                1200,
                225,
                86,
                78,
            ),
            rect(
                "plant",
                "<b>Four-vehicle rigid-payload<br>system and feedback</b><br>"
                "<font style=\"font-size:8px\">states, errors, forces, constraints, logs</font>",
                1330,
                210,
                235,
                108,
                COLORS["plant_fill"],
                COLORS["plant_stroke"],
            ),
            rect(
                "fallback",
                "<b>Projection / tightening /<br>C3 degraded fallback</b><br>"
                "<font style=\"font-size:8px\">reference contraction if needed</font>",
                925,
                365,
                235,
                72,
                COLORS["safety_fill"],
                COLORS["safety_stroke"],
            ),
        ]
    )

    cells.extend(
        [
            edge("e_ref_sum", "", "ref_input", "sum"),
            edge("e_sum_net", "tracking error", "sum", "network"),
            edge("e_net_mpc", "path, q, τ", "network", "koopman_mpc"),
            edge("e_mpc_exec", "u<sub>k</sub><sup>mpc</sup>", "koopman_mpc", "execution"),
            edge("e_exec_cert", "candidate u<sub>k</sub>", "execution", "cert_decision"),
            edge("e_cert_pass", "pass", "cert_decision", "plant"),
            point_edge(
                "e_cert_fail",
                "fail",
                [(1243, 303), (1243, 340), (1042, 340), (1042, 365)],
                COLORS["fail"],
                False,
                1.8,
            ),
            point_edge(
                "e_fallback_plant",
                "degraded safe command",
                [(1160, 401), (1448, 401), (1448, 318)],
                COLORS["fail"],
                False,
                1.8,
            ),
            point_edge(
                "e_off_mpc",
                "Φ<sub>θ</sub>, A, B, N<sub>l</sub>, residual bound",
                [(800, 136), (800, 187), (777, 187), (777, 210)],
                COLORS["feedback"],
                True,
                1.5,
            ),
            point_edge(
                "e_off_cert",
                "IRSP and certificate terms",
                [(1220, 136), (1220, 202), (1243, 202), (1243, 225)],
                COLORS["feedback"],
                True,
                1.5,
            ),
            point_edge(
                "fb_main",
                "closed-loop feedback: states, errors, forces, constraints, logs",
                [(1448, 318), (1448, 455), (340, 455), (340, 298)],
                COLORS["feedback"],
                True,
                1.7,
            ),
            point_edge(
                "fb_to_network",
                "",
                [(512, 455), (512, 318)],
                COLORS["feedback"],
                True,
                1.2,
            ),
            point_edge(
                "fb_to_cert",
                "",
                [(1243, 455), (1243, 303)],
                COLORS["feedback"],
                True,
                1.2,
            ),
            label("plus", "+", 293, 225, 18, 20, 11),
            label("minus", "-", 333, 301, 18, 20, 12),
            label(
                "line_legend",
                "<font style=\"font-size:8px\">solid: online data/command flow; dashed: offline loading or feedback; red: certificate-failing path</font>",
                395,
                485,
                1120,
                20,
                8,
            ),
        ]
    )

    graph = (
        f'<mxGraphModel dx="1700" dy="680" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
        f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{PAGE_W}" pageHeight="{PAGE_H}" '
        f'math="0" shadow="0"><root>'
        + "".join(cells)
        + "</root></mxGraphModel>"
    )
    return (
        '<mxfile host="app.diagrams.net" modified="2026-06-02T00:00:00.000Z" '
        'agent="Codex" version="26.0.0" type="device">'
        f'<diagram id="nrkdcc-maintext-20260602" name="NR-KDCC Main-text Flow">{graph}</diagram>'
        "</mxfile>"
    )


def svg_rect(x: int, y: int, w: int, h: int, fill: str, stroke: str) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>'


def svg_text(lines: list[str], x: int, y: int, size: int = 12, bold: bool = False, anchor: str = "middle") -> str:
    weight = "700" if bold else "400"
    out = [
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{COLORS["text"]}">'
    ]
    for i, line in enumerate(lines):
        dy = 0 if i == 0 else size + 3
        out.append(f'<tspan x="{x}" dy="{dy}">{escape(line)}</tspan>')
    out.append("</text>")
    return "".join(out)


def svg_path(
    points: list[tuple[int, int]],
    color: str = COLORS["line"],
    dashed: bool = False,
    label_text: str = "",
    label_xy: tuple[int, int] | None = None,
) -> str:
    marker = "arrowFail" if color == COLORS["fail"] else "arrow"
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    d = "M" + " L".join(f"{x},{y}" for x, y in points)
    line = f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" marker-end="url(#{marker})"{dash}/>'
    if label_text:
        if label_xy is None:
            xs = [x for x, _ in points]
            ys = [y for _, y in points]
            label_xy = (sum(xs) // len(xs), sum(ys) // len(ys) - 6)
        line += svg_text([label_text], label_xy[0], label_xy[1], 9, False)
    return line


def svg_box(
    x: int,
    y: int,
    w: int,
    h: int,
    fill: str,
    stroke: str,
    title_lines: list[str],
    sub_lines: list[str],
) -> list[str]:
    return [
        svg_rect(x, y, w, h, fill, stroke),
        svg_text(title_lines, x + w // 2, y + 26, 11, True),
        svg_text(sub_lines, x + w // 2, y + 61, 10, False),
    ]


def build_svg() -> str:
    body: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}" height="{PAGE_H}" viewBox="0 0 {PAGE_W} {PAGE_H}">',
        "<defs>"
        '<marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L0,6 L9,3 z" fill="#374151"/></marker>'
        '<marker id="arrowFail" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L0,6 L9,3 z" fill="#D64545"/></marker>'
        "</defs>",
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        svg_rect(70, 52, 1460, 84, COLORS["offline_fill"], COLORS["offline_stroke"]),
        svg_text(["Offline data and bilinear Koopman predictor"], 800, 75, 13, True),
        svg_text(
            [
                "curvature / communication / actuator-degradation data",
                "input-aware robust spectral projection (IRSP)",
                "model, residual bound, and certificate terms",
            ],
            800,
            98,
            10,
            False,
        ),
    ]

    for item in [
        (50, 210, 235, 108, COLORS["ref_fill"], COLORS["ref_stroke"], ["Reference path, payload-center progress,", "and temporary path packet"], ["p_L^ref(s), psi_L^ref, kappa_r, P_i,k^tmp"]),
        (395, 210, 235, 108, COLORS["ref_fill"], COLORS["ref_stroke"], ["4WS local paths and", "communication degradation"], ["link quality, delay, packet loss", "q_ij,k, q_k^net, tau, ell_ij,k"]),
        (660, 210, 235, 108, COLORS["online_fill"], COLORS["online_stroke"], ["Koopman prediction and", "communication-quality-aware consensus MPC"], ["z_k+1|k, C0--C3 schedules", "consensus weights and constraint tightening"]),
        (925, 210, 235, 108, COLORS["safety_fill"], COLORS["safety_stroke"], ["Execution-layer protection"], ["FDI/FTC, PPC guard, role scheduling", "curvature-window payload-protection switch"]),
        (1330, 210, 235, 108, COLORS["plant_fill"], COLORS["plant_stroke"], ["Four-vehicle rigid-payload", "system and feedback"], ["states, errors, forces, constraints, logs"]),
        (925, 365, 235, 72, COLORS["safety_fill"], COLORS["safety_stroke"], ["Projection / tightening /", "C3 degraded fallback"], ["reference contraction if needed"]),
    ]:
        body.extend(svg_box(*item))

    body.extend(
        [
            '<circle cx="340" cy="268" r="30" fill="#FFFFFF" stroke="#6B7280" stroke-width="1.8"/>',
            svg_text(["Σ"], 340, 273, 18, True),
            svg_text(["+"], 294, 236, 13, True),
            svg_text(["-"], 342, 314, 13, True),
            '<polygon points="1243,225 1286,264 1243,303 1200,264" fill="#FFFFFF" stroke="#D64545" stroke-width="1.7"/>',
            svg_text(["Certificate", "passes?", "m_k >= -epsilon_m"], 1243, 254, 9, True),
            svg_path([(285, 264), (310, 264)]),
            svg_path([(370, 264), (395, 264)], label_text="tracking error", label_xy=(383, 250)),
            svg_path([(630, 264), (660, 264)], label_text="path, q, tau", label_xy=(645, 204)),
            svg_path([(895, 264), (925, 264)], label_text="u_k^mpc", label_xy=(910, 204)),
            svg_path([(1160, 264), (1200, 264)], label_text="candidate u_k", label_xy=(1180, 204)),
            svg_path([(1286, 264), (1330, 264)], label_text="pass", label_xy=(1308, 244)),
            svg_path([(1243, 303), (1243, 340), (1042, 340), (1042, 365)], COLORS["fail"], label_text="fail", label_xy=(1135, 333)),
            svg_path([(1160, 401), (1448, 401), (1448, 318)], COLORS["fail"], label_text="degraded safe command", label_xy=(1288, 391)),
            svg_path([(800, 136), (800, 187), (777, 187), (777, 210)], COLORS["feedback"], True, "Phi_theta, A, B, N_l, residual bound", (840, 178)),
            svg_path([(1220, 136), (1220, 202), (1243, 202), (1243, 225)], COLORS["feedback"], True, "IRSP and certificate terms", (1278, 194)),
            svg_path([(1448, 318), (1448, 455), (340, 455), (340, 298)], COLORS["feedback"], True, "closed-loop feedback: states, errors, forces, constraints, logs", (815, 444)),
            svg_path([(512, 455), (512, 318)], COLORS["feedback"], True),
            svg_path([(1243, 455), (1243, 303)], COLORS["feedback"], True),
            svg_text(
                ["solid: online data/command flow; dashed: offline loading or feedback; red: certificate-failing path"],
                955,
                499,
                10,
                False,
            ),
        ]
    )
    body.append("</svg>")
    return "\n".join(body)


def build_url(xml: str) -> str:
    raw = quote(xml, safe="").encode("utf-8")
    comp = zlib.compressobj(level=9, wbits=-15)
    data = comp.compress(raw) + comp.flush()
    return "https://app.diagrams.net/?src=about#R" + base64.b64encode(data).decode("ascii")


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    xml = build_drawio()
    OUT_DRAWIO.write_text(xml, encoding="utf-8")
    OUT_SVG.write_text(build_svg(), encoding="utf-8")
    OUT_URL.write_text(build_url(xml), encoding="ascii")
    print(OUT_DRAWIO)
    print(OUT_SVG)
    print(OUT_URL)


if __name__ == "__main__":
    main()
