from __future__ import annotations

from html import unescape
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parent
FIG_DIR = ROOT / "figures"
STEM = "fig2_nrkdcc_one_step_control_flow_20260602"
OUT = FIG_DIR / f"{STEM}.drawio"

PAGE_W = 1800
PAGE_H = 680

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
    "neutral_fill": "#F9FAFB",
    "neutral_stroke": "#6B7280",
    "text": "#1F2937",
    "line": "#374151",
    "feedback": "#6B7280",
    "fail": "#D64545",
    "header_fill": "#FFFFFF",
}


def style(**items: str | int | float) -> str:
    return ";".join(f"{k}={v}" for k, v in items.items()) + ";"


def val(text: str) -> str:
    text = unescape(text).replace("\n", "<br>")
    return escape(text, {'"': "&quot;"})


def cell(
    cell_id: str,
    value: str,
    x: float,
    y: float,
    w: float,
    h: float,
    cell_style: str,
    vertex: bool = True,
) -> str:
    v = ' vertex="1"' if vertex else ""
    return (
        f'<mxCell id="{cell_id}" value="{value}" style="{cell_style}"{v} parent="1">'
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
    font: int = 9,
    bold: bool = False,
    rounded: bool = True,
) -> str:
    return cell(
        cell_id,
        val(text),
        x,
        y,
        w,
        h,
        style(
            rounded=1 if rounded else 0,
            whiteSpace="wrap",
            html=1,
            fillColor=fill,
            strokeColor=stroke,
            strokeWidth=1.4,
            fontColor=COLORS["text"],
            fontSize=font,
            fontStyle=1 if bold else 0,
            align="center",
            verticalAlign="middle",
            spacing=5,
            arcSize=8,
        ),
    )


def label(cell_id: str, text: str, x: float, y: float, w: float, h: float, font: int = 8) -> str:
    return cell(
        cell_id,
        val(text),
        x,
        y,
        w,
        h,
        style(
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


def ellipse(cell_id: str, text: str, x: float, y: float, w: float, h: float, fill: str, stroke: str) -> str:
    return cell(
        cell_id,
        val(text),
        x,
        y,
        w,
        h,
        style(
            ellipse=1,
            whiteSpace="wrap",
            html=1,
            fillColor=fill,
            strokeColor=stroke,
            strokeWidth=1.6,
            fontColor=COLORS["text"],
            fontSize=12,
            fontStyle=1,
            align="center",
            verticalAlign="middle",
        ),
    )


def diamond(cell_id: str, text: str, x: float, y: float, w: float, h: float) -> str:
    return cell(
        cell_id,
        val(text),
        x,
        y,
        w,
        h,
        style(
            shape="rhombus",
            whiteSpace="wrap",
            html=1,
            fillColor="#FFFFFF",
            strokeColor=COLORS["safety_stroke"],
            strokeWidth=1.6,
            fontColor=COLORS["text"],
            fontSize=9,
            fontStyle=1,
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
    width: float = 1.7,
    points: list[tuple[float, float]] | None = None,
) -> str:
    e_style = style(
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
    waypoints = ""
    if points:
        waypoints = "<Array as=\"points\">" + "".join(
            f'<mxPoint x="{x:g}" y="{y:g}"/>' for x, y in points
        ) + "</Array>"
    return (
        f'<mxCell id="{cell_id}" value="{val(text)}" style="{e_style}" edge="1" parent="1" '
        f'source="{source}" target="{target}">'
        f'<mxGeometry relative="1" as="geometry">{waypoints}</mxGeometry>'
        "</mxCell>"
    )


def point_edge(
    cell_id: str,
    text: str,
    pts: list[tuple[float, float]],
    color: str = COLORS["line"],
    dashed: bool = False,
    width: float = 1.5,
    arrow: bool = True,
) -> str:
    if len(pts) < 2:
        raise ValueError("point edge requires at least two points")
    sx, sy = pts[0]
    tx, ty = pts[-1]
    mids = pts[1:-1]
    e_style = style(
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
    wp = ""
    if mids:
        wp = "<Array as=\"points\">" + "".join(
            f'<mxPoint x="{x:g}" y="{y:g}"/>' for x, y in mids
        ) + "</Array>"
    return (
        f'<mxCell id="{cell_id}" value="{val(text)}" style="{e_style}" edge="1" parent="1">'
        f'<mxGeometry relative="1" as="geometry">'
        f'<mxPoint x="{sx:g}" y="{sy:g}" as="sourcePoint"/>'
        f'<mxPoint x="{tx:g}" y="{ty:g}" as="targetPoint"/>'
        f"{wp}</mxGeometry></mxCell>"
    )


def build() -> str:
    cells: list[str] = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']

    # Title and lane labels
    cells.append(label("title", "<b>One-step control flow of NR-KDCC within one sampling period</b>", 360, 8, 1080, 28, 15))
    cells.append(rect("offline_band", "", 35, 45, 1730, 142, COLORS["offline_fill"], COLORS["offline_stroke"], 9, False, True))
    cells.append(label("offline_label", "<b>OFFLINE BAND</b>", 50, 55, 120, 22, 10))

    # Offline nodes
    cells.extend(
        [
            rect("o1", "Offline scenario data&lt;br&gt;<font style=\"font-size:8px\">nominal / noisy / fault / mixed</font>", 85, 92, 260, 58, "#FFFFFF", COLORS["offline_stroke"], 9, True),
            rect("o2", "Lifting + bilinear regression&lt;br&gt;<font style=\"font-size:8px\">&chi; &rarr; &Phi;<sub>&theta;</sub> &rarr; z, A, B, N<sub>l</sub></font>", 415, 92, 285, 58, "#FFFFFF", COLORS["offline_stroke"], 9, True),
            rect("o3", "IRSP stability projection&lt;br&gt;<font style=\"font-size:8px\">&rho;(A<sub>eff</sub>(u)) &le; r<sub>u</sub></font>", 770, 92, 285, 58, "#FFFFFF", COLORS["offline_stroke"], 9, True),
            rect("o4", "Model and certificate package&lt;br&gt;<font style=\"font-size:8px\">&Phi;<sub>&theta;</sub>, A, B, N<sub>l</sub>, U<sub>s</sub>, w bounds</font>", 1125, 92, 360, 58, "#FFFFFF", COLORS["offline_stroke"], 9, True),
        ]
    )

    # Online main nodes
    y = 295
    cells.extend(
        [
            rect("m0", "Environment-derived&lt;br&gt;reference path&lt;br&gt;<font style=\"font-size:8px\">p<sub>L</sub><sup>ref</sup>(s), &psi;<sub>L</sub><sup>ref</sup>, &kappa;<sub>r</sub>, v<sub>ref</sub></font>", 45, y, 175, 90, COLORS["ref_fill"], COLORS["ref_stroke"], 9, True),
            ellipse("s1", "&Sigma;&lt;br&gt;<font style=\"font-size:8px\">+ / -</font>", 250, y + 19, 62, 62, "#FFFFFF", COLORS["neutral_stroke"]),
            rect("m1", "Upper 4WS local&lt;br&gt;path publisher&lt;br&gt;<font style=\"font-size:8px\">&kappa;<sub>r</sub> &rarr; &beta;<sup>4ws</sup>, &kappa;<sup>4ws</sup> &rarr; P<sub>i,k</sub><sup>tmp</sup></font>", 350, y, 205, 90, COLORS["ref_fill"], COLORS["ref_stroke"], 9, True),
            rect("m2", "Communication processing&lt;br&gt;and link-quality monitor&lt;br&gt;<font style=\"font-size:8px\">q<sub>ij,k</sub>, q<sub>k</sub><sup>net</sup>, &tau;, loss, bias/noise</font>", 600, y, 230, 90, COLORS["ref_fill"], COLORS["ref_stroke"], 9, True),
            rect("m3", "Observation fusion&lt;br&gt;and Koopman rollout&lt;br&gt;<font style=\"font-size:8px\">&chi;<sub>k</sub> &rarr; &Phi;<sub>&theta;</sub> &rarr; z<sub>k</sub> &rarr; z<sub>k+1|k</sub></font>", 875, y, 230, 90, COLORS["online_fill"], COLORS["online_stroke"], 9, True),
            rect("m4", "C-mode scheduler&lt;br&gt;and consensus MPC&lt;br&gt;<font style=\"font-size:8px\">C0/C1/C2/C3, min J, tightened constraints</font>", 1150, y, 235, 90, COLORS["online_fill"], COLORS["online_stroke"], 9, True),
            rect("m5", "FDI/FTC and&lt;br&gt;command projection&lt;br&gt;<font style=\"font-size:8px\">residual &rarr; &eta;&#770; &rarr; &Pi;<sub>U</sub></font>", 1430, y, 210, 90, COLORS["safety_fill"], COLORS["safety_stroke"], 9, True),
        ]
    )

    cells.extend(
        [
            diamond("d1", "Certificate&lt;br&gt;passes?&lt;br&gt;<font style=\"font-size:8px\">m<sub>k</sub> &ge; -&epsilon;<sub>m</sub></font>", 1455, 438, 155, 92),
            rect("m6", "Projection / tightening&lt;br&gt;/ fallback&lt;br&gt;<font style=\"font-size:8px\">C3, tightened U, contracted ref</font>", 1225, 448, 205, 70, "#FFFFFF", COLORS["safety_stroke"], 9, True),
            rect("m7", "Safe command&lt;br&gt;publication&lt;br&gt;<font style=\"font-size:8px\">u<sub>i,k</sub><sup>safe</sup> = [a<sub>x,i</sub>, &delta;<sub>i</sub>]</font>", 1660, 306, 165, 78, COLORS["safety_fill"], COLORS["safety_stroke"], 9, True),
            rect("p1", "Vehicle-payload plant&lt;br&gt;and environment feedback&lt;br&gt;<font style=\"font-size:8px\">x<sub>k+1</sub>, e<sub>c</sub>, force proxy, logs</font>", 1660, 466, 165, 94, COLORS["plant_fill"], COLORS["plant_stroke"], 9, True),
        ]
    )

    # Internal symbol hints
    cells.extend(
        [
            rect("sym_delay", "z<sup>-&tau;</sup>", 632, 405, 58, 32, "#FFFFFF", COLORS["ref_stroke"], 10, True, False),
            rect("sym_loss", "loss?", 705, 405, 70, 32, "#FFFFFF", COLORS["ref_stroke"], 9, True),
            rect("sym_mux", "MUX", 900, 405, 64, 32, "#FFFFFF", COLORS["online_stroke"], 9, True, False),
            rect("sym_cmp", "risk&lt;br&gt;compare", 1180, 405, 74, 42, "#FFFFFF", COLORS["online_stroke"], 8, True),
            rect("sym_sat", "sat[0,1]", 1270, 405, 76, 32, "#FFFFFF", COLORS["online_stroke"], 8, True, False),
            rect("sym_fdi", "FDI&lt;br&gt;residual", 1445, 405, 80, 42, "#FFFFFF", COLORS["safety_stroke"], 8, True),
            rect("sym_ftc", "FTC&lt;br&gt;realloc.", 1540, 405, 78, 42, "#FFFFFF", COLORS["safety_stroke"], 8, True),
        ]
    )

    # Main flow
    cells.extend(
        [
            edge("e_o1_o2", "samples", "o1", "o2", COLORS["offline_stroke"]),
            edge("e_o2_o3", "A, B, N<sub>l</sub>", "o2", "o3", COLORS["offline_stroke"]),
            edge("e_o3_o4", "projected model + bounds", "o3", "o4", COLORS["offline_stroke"]),
            edge("e_m0_s1", "r<sub>ref</sub>(s)", "m0", "s1"),
            edge("e_s1_m1", "errors + path context", "s1", "m1"),
            edge("e_m1_m2", "P<sub>i,k</sub><sup>tmp</sup>, &kappa;<sub>r</sub>", "m1", "m2"),
            edge("e_m2_m3", "P&#770;<sub>i,k</sub><sup>tmp</sup>, x&#770;<sub>j,k</sub><sup>net</sup>, q, &tau;, loss", "m2", "m3"),
            edge("e_m3_m4", "predicted states, residual bounds", "m3", "m4"),
            edge("e_m4_m5", "u<sub>k</sub><sup>mpc</sup>, margins, &mu;<sub>k</sub>", "m4", "m5"),
            edge("e_m5_d1", "u&#771;<sub>k</sub>, &eta;&#770;, residuals", "m5", "d1", points=[(1535, 420)]),
            edge("e_d1_m7", "pass", "d1", "m7"),
            edge("e_m7_p1", "u<sub>i,k</sub><sup>safe</sup>", "m7", "p1"),
            edge("e_d1_m6", "fail", "d1", "m6", COLORS["fail"], False, 2.0),
            edge("e_m6_m7", "fallback / tightened command", "m6", "m7", COLORS["fail"], False, 2.0, points=[(1550, 575), (1715, 575)]),
        ]
    )

    # Offline package connections
    cells.extend(
        [
            point_edge("e_o4_m3", "&Phi;<sub>&theta;</sub>, A, B, N<sub>l</sub>", [(1305, 150), (1305, 232), (990, 232), (990, 292)], COLORS["feedback"], True),
            point_edge("e_o4_m4", "IRSP bounds, U<sub>s</sub>", [(1370, 150), (1370, 245), (1268, 245), (1268, 292)], COLORS["feedback"], True),
            point_edge("e_o4_d1", "w bounds, certificate terms", [(1440, 150), (1440, 232), (1515, 232), (1515, 438)], COLORS["feedback"], True),
        ]
    )

    # Symbol subflow hints
    cells.extend(
        [
            point_edge("e_m2_delay", "", [(650, 386), (660, 405)], COLORS["ref_stroke"], False),
            point_edge("e_delay_loss", "delayed packets", [(690, 421), (705, 421)], COLORS["ref_stroke"], False),
            point_edge("e_m3_mux", "", [(990, 386), (932, 405)], COLORS["online_stroke"], False),
            point_edge("e_m4_cmp", "", [(1240, 386), (1217, 405)], COLORS["online_stroke"], False),
            point_edge("e_cmp_sat", "&sigma;<sub>k</sub>", [(1254, 426), (1270, 421)], COLORS["online_stroke"], False),
            point_edge("e_fdi_ftc", "flag, &eta;&#770;", [(1525, 426), (1540, 426)], COLORS["safety_stroke"], False),
        ]
    )

    # Feedback bus
    bus_y = 620
    cells.append(point_edge("fb_bus", "", [(1745, 560), (1745, bus_y), (285, bus_y), (285, 357)], COLORS["feedback"], True, 2.0))
    cells.append(point_edge("fb_to_m2", "communication logs", [(1745, bus_y), (725, bus_y), (725, 388)], COLORS["feedback"], True))
    cells.append(point_edge("fb_to_m5", "actuator response, residuals", [(1745, bus_y), (1535, bus_y), (1535, 388)], COLORS["feedback"], True))
    cells.append(point_edge("fb_to_d1", "V, m<sub>k</sub>, force proxy, constraints", [(1745, bus_y), (1515, bus_y), (1515, 530)], COLORS["feedback"], True))
    cells.append(label("fb_label", "feedback bus: x<sub>k+1</sub>, &xi;<sub>L,k+1</sub>, e<sub>y</sub>, e<sub>&psi;</sub>, e<sub>c</sub>, F proxy, constraints, logs", 575, 632, 750, 24, 8))

    # Plus/minus marks for summing junction.
    cells.append(label("plus_mark", "+", 232, 316, 20, 20, 11))
    cells.append(label("minus_mark", "-", 274, 386, 20, 20, 12))

    graph = (
        f'<mxGraphModel dx="1900" dy="820" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
        f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{PAGE_W}" pageHeight="{PAGE_H}" '
        f'math="0" shadow="0"><root>'
        + "".join(cells)
        + "</root></mxGraphModel>"
    )
    mxfile = (
        '<mxfile host="app.diagrams.net" modified="2026-06-02T00:00:00.000Z" '
        'agent="Codex" version="26.0.0" type="device">'
        f'<diagram id="nrkdcc-one-step-20260602" name="NR-KDCC One-step Control Flow">{graph}</diagram>'
        "</mxfile>"
    )
    return mxfile


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
