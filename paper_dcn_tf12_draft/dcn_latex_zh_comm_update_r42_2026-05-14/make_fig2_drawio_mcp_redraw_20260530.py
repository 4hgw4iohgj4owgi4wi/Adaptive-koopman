from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parent
FIG_DIR = ROOT / "figures"
STEM = "fig2_nrkdcc_mcp_redraw_20260530"
OUT_DRAWIO = FIG_DIR / f"{STEM}.drawio"

PAGE_W = 1107
PAGE_H = 200

COLORS = {
    "offline_fill": "#EAF3FF",
    "offline_stroke": "#2F6FBB",
    "upper_fill": "#E8FAF5",
    "upper_stroke": "#15847D",
    "network_fill": "#F2FBF9",
    "online_fill": "#EEF4FA",
    "online_stroke": "#4B77A8",
    "safety_fill": "#FFF1F2",
    "safety_stroke": "#D64545",
    "env_fill": "#F3EFFB",
    "env_stroke": "#7E68A4",
    "feedback": "#6B7280",
    "text": "#1F2937",
}


def y_top(y_bottom: float, y_top_: float) -> float:
    return PAGE_H - y_top_


def style(**items: str | int | float) -> str:
    return ";".join(f"{k}={v}" for k, v in items.items()) + ";"


def label(text: str) -> str:
    return escape(text).replace("\n", "&lt;br&gt;")


def rect(
    cell_id: str,
    text: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    fill: str,
    stroke: str,
    font_size: int = 10,
    rounded: bool = True,
    extra_style: str = "",
) -> str:
    x = x1
    y = y_top(y1, y2)
    w = x2 - x1
    h = y2 - y1
    base = style(
        rounded=1 if rounded else 0,
        whiteSpace="wrap",
        html=1,
        fillColor=fill,
        strokeColor=stroke,
        strokeWidth=1.6,
        fontColor=COLORS["text"],
        fontSize=font_size,
        fontStyle=1,
        spacing=3,
        align="center",
        verticalAlign="middle",
        shadow=0,
        arcSize=8,
    )
    cell_style = base + extra_style
    return (
        f'<mxCell id="{cell_id}" value="{label(text)}" style="{cell_style}" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" as="geometry"/>'
        "</mxCell>"
    )


def edge(
    cell_id: str,
    text: str,
    points: list[tuple[float, float]],
    color: str,
    dashed: bool = False,
    width: float = 1.6,
    arrow: bool = True,
    font_size: int = 8,
    bend: bool = True,
) -> str:
    if len(points) < 2:
        raise ValueError("edge needs at least two points")
    transformed = [(x, PAGE_H - y) for x, y in points]
    sx, sy = transformed[0]
    tx, ty = transformed[-1]
    waypoints = transformed[1:-1]
    end_arrow = "block" if arrow else "none"
    edge_style = style(
        edgeStyle="orthogonalEdgeStyle" if bend else "elbowEdgeStyle",
        rounded=1,
        orthogonalLoop=1,
        jettySize="auto",
        html=1,
        endArrow=end_arrow,
        endFill=1 if arrow else 0,
        strokeColor=color,
        strokeWidth=width,
        fontColor=color,
        fontSize=font_size,
        labelBackgroundColor="#FFFFFF",
        labelBorderColor="none",
        dashed=1 if dashed else 0,
        dashPattern="6 4" if dashed else "solid",
        startArrow="none",
    )
    wp = ""
    if waypoints:
        wp = "<Array as=\"points\">" + "".join(
            f'<mxPoint x="{x:g}" y="{y:g}"/>' for x, y in waypoints
        ) + "</Array>"
    return (
        f'<mxCell id="{cell_id}" value="{label(text)}" style="{edge_style}" edge="1" parent="1">'
        '<mxGeometry relative="1" as="geometry">'
        f'<mxPoint x="{sx:g}" y="{sy:g}" as="sourcePoint"/>'
        f'<mxPoint x="{tx:g}" y="{ty:g}" as="targetPoint"/>'
        f"{wp}"
        "</mxGeometry></mxCell>"
    )


def text_cell(cell_id: str, text: str, x: float, y: float, w: float, h: float, color: str) -> str:
    cell_style = style(
        text=1,
        html=1,
        strokeColor="none",
        fillColor="#FFFFFF",
        opacity=88,
        align="center",
        verticalAlign="middle",
        whiteSpace="wrap",
        rounded=0,
        fontSize=8,
        fontColor=color,
    )
    return (
        f'<mxCell id="{cell_id}" value="{label(text)}" style="{cell_style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x:g}" y="{PAGE_H - y - h:g}" width="{w:g}" height="{h:g}" as="geometry"/>'
        "</mxCell>"
    )


def build() -> str:
    cells: list[str] = [
        '<mxCell id="0"/>',
        '<mxCell id="1" parent="0"/>',
    ]

    cells.extend(
        [
            rect(
                "offline",
                "Offline Bilinear Koopman\nPredictor & IRSP Projection",
                30,
                130,
                200,
                190,
                COLORS["offline_fill"],
                COLORS["offline_stroke"],
                10,
            ),
            rect(
                "upper",
                "Upper-Layer Reference\n& Path Publisher",
                240,
                120,
                400,
                180,
                COLORS["upper_fill"],
                COLORS["upper_stroke"],
                10,
            ),
            rect(
                "network",
                "Network\n(delay, loss,\nnoise)",
                430,
                125,
                500,
                175,
                COLORS["network_fill"],
                COLORS["upper_stroke"],
                8,
                False,
                "shape=cloud;perimeter=ellipsePerimeter;",
            ),
            rect(
                "online",
                "Link-Quality-Aware\nConsensus MPC\n+ Koopman Predictor",
                530,
                110,
                730,
                190,
                COLORS["online_fill"],
                COLORS["online_stroke"],
                10,
            ),
            rect(
                "safety",
                "FDI/FTC,\nCommand Projection\n& Certificate Check",
                770,
                110,
                930,
                190,
                COLORS["safety_fill"],
                COLORS["safety_stroke"],
                10,
            ),
            rect(
                "env",
                "Vehicle-Payload\nSystem & Feedback",
                970,
                110,
                1100,
                190,
                COLORS["env_fill"],
                COLORS["env_stroke"],
                10,
            ),
        ]
    )

    # Fine labels on the network cloud keep the main node compact while retaining manuscript notation.
    cells.append(text_cell("network_q", "q_ij,k, q_k^net", 421, 112, 90, 12, COLORS["upper_stroke"]))

    cells.extend(
        [
            # Offline model package. Routed above the upper/network blocks to avoid visual overlap.
            edge(
                "A",
                "",
                [(200, 160), (215, 160), (215, 196), (620, 196), (620, 190)],
                COLORS["offline_stroke"],
                dashed=True,
                width=1.5,
                font_size=8,
            ),
            edge(
                "B",
                "",
                [(400, 150), (430, 150)],
                COLORS["upper_stroke"],
                width=1.6,
            ),
            edge(
                "C",
                "",
                [(500, 150), (530, 150)],
                COLORS["upper_stroke"],
                width=1.6,
                font_size=7,
            ),
            edge(
                "D",
                "",
                [(730, 150), (770, 150)],
                COLORS["online_stroke"],
                width=1.7,
            ),
            edge(
                "E",
                "",
                [(930, 150), (970, 150)],
                "#263238",
                width=1.7,
            ),
            # Feedback bus and branches.
            edge(
                "F_bus",
                "",
                [(1035, 110), (1035, 60), (30, 60)],
                COLORS["feedback"],
                dashed=True,
                width=1.35,
                arrow=False,
                font_size=7,
            ),
            edge(
                "F1",
                "",
                [(630, 60), (630, 110)],
                COLORS["feedback"],
                dashed=True,
                width=1.35,
                font_size=7,
            ),
            edge(
                "F2",
                "",
                [(320, 60), (320, 120)],
                COLORS["feedback"],
                dashed=True,
                width=1.35,
                font_size=7,
            ),
            edge(
                "G",
                "",
                [(850, 110), (850, 100), (630, 100), (630, 110)],
                COLORS["safety_stroke"],
                dashed=True,
                width=1.35,
                font_size=7,
            ),
        ]
    )

    cells.extend(
        [
            text_cell("lab_A", "model package", 635, 188, 110, 10, COLORS["offline_stroke"]),
            text_cell("lab_B", "path packets", 382, 154, 64, 10, COLORS["upper_stroke"]),
            text_cell("lab_C", "packets + q", 490, 154, 62, 10, COLORS["upper_stroke"]),
            text_cell("lab_D", "u_i*", 738, 154, 28, 10, COLORS["online_stroke"]),
            text_cell("lab_E", "u_i^safe", 934, 154, 42, 10, "#263238"),
            text_cell("lab_F_bus", "closed-loop feedback: states, errors, force/constraint logs", 410, 52, 300, 10, COLORS["feedback"]),
            text_cell("lab_F1", "state & connection errors", 565, 82, 130, 10, COLORS["feedback"]),
            text_cell("lab_F2", "payload-center progress", 248, 88, 140, 10, COLORS["feedback"]),
            text_cell("lab_G", "certificate margins / FDI flags", 705, 96, 170, 10, COLORS["safety_stroke"]),
        ]
    )

    metadata = (
        "NR-KDCC Fig. 2 module data flow redraw; "
        "five color groups follow Fig. 1: offline, upper/communication, online MPC, safety, environment"
    )

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" modified="{datetime.now().isoformat(timespec='seconds')}" agent="Codex draw.io MCP" version="30.0.4" type="device">
  <diagram id="fig2-nrkdcc-mcp-redraw" name="Fig2 NR-KDCC data flow">
    <mxGraphModel dx="{PAGE_W}" dy="{PAGE_H}" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{PAGE_W}" pageHeight="{PAGE_H}" math="0" shadow="0">
      <root>
        {''.join(cells)}
      </root>
    </mxGraphModel>
  </diagram>
  <!-- {escape(metadata)} -->
</mxfile>
'''


if __name__ == "__main__":
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DRAWIO.write_text(build(), encoding="utf-8")
    print(OUT_DRAWIO)
