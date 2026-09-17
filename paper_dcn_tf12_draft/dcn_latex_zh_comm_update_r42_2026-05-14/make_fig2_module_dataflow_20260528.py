from __future__ import annotations

import html
import math
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon


ROOT = Path(__file__).resolve().parent
FIG_DIR = ROOT / "figures"
TEMPLATE_VSDX = (
    ROOT.parent
    / "nature_visio_diagrams_2026-05-21_review_clean_v5_reference_style"
    / "NRKDCC_control_flow_nature_style_editable.vsdx"
)

OUT_STEM = "fig2_nrkdcc_module_dataflow_pub_20260528"
OUT_PDF = FIG_DIR / f"{OUT_STEM}.pdf"
OUT_PNG = FIG_DIR / f"{OUT_STEM}.png"
OUT_SVG = FIG_DIR / f"{OUT_STEM}.svg"
OUT_VSDX = FIG_DIR / f"{OUT_STEM}.vsdx"

W, H = 19.0, 8.0


@dataclass(frozen=True)
class Module:
    key: str
    title: str
    x: float
    y: float
    w: float
    h: float
    fill: str
    stroke: str


@dataclass(frozen=True)
class Node:
    key: str
    text: str
    x: float
    y: float
    w: float = 1.25
    h: float = 0.42
    kind: str = "rect"
    fill: str = "#FFFFFF"
    stroke: str = "#334E68"


@dataclass(frozen=True)
class Edge:
    points: tuple[tuple[float, float], ...]
    label: str
    color: str
    dashed: bool = False
    label_offset: tuple[float, float] = (0.0, 0.0)
    lw: float = 0.85


MODULES = [
    Module("M1", "M1 Offline learning", 0.25, 5.05, 4.15, 2.55, "#EAF3FF", "#2F6FBB"),
    Module("M2", "M2 Reference and communication", 0.25, 0.90, 4.15, 3.75, "#E8FAF5", "#15847D"),
    Module("M3", "M3 Online prediction and MPC", 4.75, 0.90, 5.45, 6.70, "#EEF4FA", "#4B77A8"),
    Module("M4", "M4 Safety and certificate", 10.55, 0.90, 3.45, 6.70, "#FFF1F2", "#D64545"),
    Module("M5", "M5 Environment feedback", 14.75, 0.90, 3.75, 6.70, "#F3EFFB", "#7E68A4"),
]

NODE_COLORS = {
    "offline": ("#FFFFFF", "#2F6FBB"),
    "ref": ("#FFFFFF", "#15847D"),
    "control": ("#FFFFFF", "#4B77A8"),
    "safety": ("#FFFFFF", "#D64545"),
    "env": ("#FFFFFF", "#7E68A4"),
}


def n(key: str, text: str, x: float, y: float, kind: str, w: float = 1.25, h: float = 0.58, shape: str = "rect") -> Node:
    fill, stroke = NODE_COLORS[kind]
    return Node(key, text, x, y, w, h, shape, fill, stroke)


NODES = {
    # M1
    "D1": n("D1", "Offline\ndata", 0.95, 6.65, "offline", w=1.10),
    "D2": n("D2", "Koopman\nlearning", 2.10, 6.65, "offline", w=1.20),
    "D4": n("D4", "IRSP\nprojection", 3.25, 6.65, "offline", w=1.15),
    "D5": n("D5", "Model package\nPhi,A,B,N_l,C,bounds", 2.10, 5.65, "offline", w=2.60, h=0.66),
    # M2
    "R1": n("R1", "Reference path\n+ 4WS model", 1.10, 3.85, "ref", w=1.55),
    "R3": n("R3", "Local path\npacket", 3.05, 3.85, "ref", w=1.25),
    "R5": n("R5", "Link-quality\nmonitor", 1.10, 2.05, "ref", w=1.45),
    "R4": n("R4", "Reference\ncommunication", 3.05, 2.05, "ref", w=1.45),
    # M3
    "C1": n("C1", "Observation\n+ lifting", 5.60, 6.60, "control", w=1.35),
    "C6": n("C6", "Koopman\nprediction", 7.55, 6.60, "control", w=1.35),
    "C3": n("C3", "Delay / remote\nprediction", 5.85, 4.90, "control", w=1.55),
    "C5": n("C5", "Quality-aware\nconsensus", 5.85, 3.05, "control", w=1.55),
    "C7": n("C7", "MPC optimizer\ncost + constraints", 8.45, 4.15, "control", w=1.70, h=0.60),
    "C8": n("C8", "Candidate\ncontrol", 8.45, 2.55, "control", w=1.35),
    # M4
    "S1": n("S1", "FDI/FTC\nrepair", 11.55, 6.55, "safety", w=1.25),
    "S3": n("S3", "Certificate\npasses?", 12.35, 5.25, "safety", w=1.25, h=0.94, shape="diamond"),
    "S4": n("S4", "Projection /\ntightening", 11.55, 3.75, "safety", w=1.35),
    "S5": n("S5", "Fallback", 12.85, 2.70, "safety", w=1.10),
    "S6": n("S6", "Safe\ncommand", 13.10, 6.85, "safety", w=1.10),
    # M5
    "E1": n("E1", "Command\nchannel", 16.70, 6.65, "env", w=1.30),
    "E3": n("E3", "Vehicle-payload\nsystem", 16.70, 4.65, "env", w=1.45),
    "E4": n("E4", "Feedback logs\nerrors / forces /\nconstraints", 16.70, 2.55, "env", w=1.65, h=0.86),
}


def right(key: str) -> tuple[float, float]:
    node = NODES[key]
    return node.x + node.w / 2, node.y


def left(key: str) -> tuple[float, float]:
    node = NODES[key]
    return node.x - node.w / 2, node.y


def top(key: str) -> tuple[float, float]:
    node = NODES[key]
    return node.x, node.y + node.h / 2


def bottom(key: str) -> tuple[float, float]:
    node = NODES[key]
    return node.x, node.y - node.h / 2


def mid(points: Iterable[tuple[float, float]], offset: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]:
    pts = list(points)
    if len(pts) == 2:
        x = (pts[0][0] + pts[1][0]) / 2
        y = (pts[0][1] + pts[1][1]) / 2
    else:
        i = max(0, len(pts) // 2 - 1)
        x = (pts[i][0] + pts[i + 1][0]) / 2
        y = (pts[i][1] + pts[i + 1][1]) / 2
    return x + offset[0], y + offset[1]


BLUE = "#2F6FBB"
TEAL = "#15847D"
CONTROL = "#4B77A8"
RED = "#D64545"
ENV = "#7E68A4"
GRAY = "#6B7280"
BLACK = "#263238"

EDGES = [
    # M1 internal
    Edge((right("D1"), left("D2")), "samples", BLUE, label_offset=(0.0, -0.34)),
    Edge((right("D2"), left("D4")), "z,A,B,N,C", BLUE, label_offset=(0.0, -0.34)),
    Edge((bottom("D4"), (3.25, 5.65), right("D5")), "bounds", BLUE, label_offset=(0.06, 0.0)),
    # M2 internal
    Edge((right("R1"), left("R3")), "path,kappa,v; 4WS", TEAL, label_offset=(0.0, 0.22)),
    Edge((bottom("R3"), top("R4")), "P_i,k^tmp", TEAL),
    Edge((right("R5"), left("R4")), "q,tau,loss", TEAL, label_offset=(0.0, -0.50)),
    # M3 internal
    Edge((right("C1"), left("C6")), "chi_i,k -> z_i,k", CONTROL, label_offset=(0.0, -0.18)),
    Edge((right("C3"), left("C7")), "xhat_j,k", CONTROL, label_offset=(0.0, 0.12)),
    Edge((right("C5"), left("C7")), "weights + tightening", TEAL, label_offset=(0.05, -0.10)),
    Edge((bottom("C6"), (7.55, 4.95), top("C7")), "xhat_i,k:k+H", CONTROL, label_offset=(0.10, 0.0)),
    Edge((bottom("C7"), top("C8")), "u_i,k:k+H^*", CONTROL),
    # M4 internal
    Edge((right("S1"), left("S3")), "r_i, eta_i, u_tilde", RED, label_offset=(-0.25, 0.24)),
    Edge((right("S3"), left("S6")), "yes", RED, label_offset=(0.16, 0.16)),
    Edge((bottom("S3"), top("S4")), "no: margin<0", RED, label_offset=(-0.18, -0.05)),
    Edge((right("S4"), left("S5")), "contracted ref", RED),
    Edge((top("S5"), (12.85, 4.85), right("S3")), "u_fb", RED, label_offset=(0.14, 0.04)),
    # M5 internal
    Edge((bottom("E1"), top("E3")), "u_i,k^recv", BLACK),
    Edge((bottom("E3"), top("E4")), "x,payload pose", ENV),
    # cross-module
    Edge((right("D5"), (4.65, 5.65), (5.60, 6.18), bottom("C1")), "Phi,A,B,N_l,C,bounds", BLUE, dashed=True, label_offset=(0.0, 0.10)),
    Edge((right("R4"), left("C3")), "P_i,k-d^tmp", TEAL, label_offset=(0.0, 0.13)),
    Edge((right("R5"), (4.65, 2.05), bottom("C5")), "q_ij,tau,loss", TEAL, label_offset=(1.45, 0.50)),
    Edge((right("C8"), left("S1")), "u_i^*, margins", CONTROL, label_offset=(0.10, 0.16)),
    Edge((right("S6"), left("E1")), "u_i^safe", BLACK, label_offset=(0.0, 0.12)),
    Edge((left("S4"), (10.25, 3.75), bottom("C7")), "tightened bounds", RED, dashed=True, label_offset=(-0.15, -0.10)),
    Edge((left("E4"), (14.55, 1.85), (5.6, 1.85), bottom("C1")), "measured state, e_y, e_s", GRAY, dashed=True, label_offset=(-1.4, -0.12)),
    Edge((left("E4"), (14.55, 2.55), bottom("S3")), "V, margin, F, g", GRAY, dashed=True, label_offset=(0.10, -0.28)),
]


def wrap_label(text: str, width: int = 22) -> str:
    if len(text) <= width:
        return text
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False))


def draw_matplotlib() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig, ax = plt.subplots(figsize=(9.2, 5.15), dpi=360)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    for m in MODULES:
        patch = FancyBboxPatch(
            (m.x, m.y),
            m.w,
            m.h,
            boxstyle="round,pad=0.055,rounding_size=0.12",
            linewidth=0.8,
            edgecolor=m.stroke,
            facecolor=m.fill,
            alpha=0.92,
            zorder=0,
        )
        ax.add_patch(patch)
        ax.text(m.x + 0.12, m.y + m.h - 0.18, m.title, ha="left", va="top", fontsize=5.6, color=m.stroke, weight="bold")

    for e in EDGES:
        pts = list(e.points)
        style = (0, (3, 2)) if e.dashed else "solid"
        for idx in range(len(pts) - 1):
            arrow = idx == len(pts) - 2
            arr = FancyArrowPatch(
                pts[idx],
                pts[idx + 1],
                arrowstyle="-|>" if arrow else "-",
                mutation_scale=6.2,
                linewidth=e.lw,
                color=e.color,
                linestyle=style,
                shrinkA=2.0 if arrow else 0.0,
                shrinkB=2.0 if arrow else 0.0,
                zorder=2,
            )
            ax.add_patch(arr)
        lx, ly = mid(pts, e.label_offset)
        ax.text(
            lx,
            ly,
            wrap_label(e.label, 24),
            ha="center",
            va="center",
            fontsize=4.15,
            color="#263238",
            bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "#D0D7DE", "linewidth": 0.35, "alpha": 0.94},
            zorder=4,
        )

    for node in NODES.values():
        if node.kind == "diamond":
            x, y, w, h = node.x, node.y, node.w, node.h
            poly = Polygon(
                [[x, y + h / 2], [x + w / 2, y], [x, y - h / 2], [x - w / 2, y]],
                closed=True,
                facecolor=node.fill,
                edgecolor=node.stroke,
                linewidth=0.75,
                zorder=3,
            )
            ax.add_patch(poly)
        else:
            patch = FancyBboxPatch(
                (node.x - node.w / 2, node.y - node.h / 2),
                node.w,
                node.h,
                boxstyle="round,pad=0.035,rounding_size=0.06",
                linewidth=0.72,
                edgecolor=node.stroke,
                facecolor=node.fill,
                zorder=3,
            )
            ax.add_patch(patch)
        ax.text(node.x, node.y, node.text, ha="center", va="center", fontsize=5.05, color="#111827", linespacing=1.05, zorder=5)

    ax.text(
        0.35,
        0.45,
        "Solid arrows: forward data/command flow; dashed arrows: offline model loading or closed-loop feedback; red arrows: certificate-triggered protection.",
        ha="left",
        va="center",
        fontsize=4.8,
        color="#4B5563",
    )

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT_PNG, bbox_inches="tight", pad_inches=0.02, dpi=420)
    fig.savefig(OUT_SVG, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def esc(text: str) -> str:
    return html.escape(text, quote=False).replace("\n", "&#10;")


def cell(name: str, value: object, unit: str | None = None, formula: str | None = None) -> str:
    attrs = f"N='{name}' V='{value}'"
    if unit:
        attrs += f" U='{unit}'"
    if formula:
        attrs += f" F='{formula}'"
    return f"<Cell {attrs}/>"


def character(size: float = 0.069, color: str = "#111827", bold: bool = False) -> str:
    return (
        "<Section N='Character'><Row IX='0'>"
        "<Cell N='Font' V='Arial' F='FONT(\"Arial\")'/>"
        f"<Cell N='Color' V='{color}'/>"
        f"<Cell N='Style' V='{1 if bold else 0}'/>"
        f"<Cell N='Size' V='{size}' U='PT'/>"
        "</Row></Section>"
    )


def rect_geometry(w: float, h: float, no_fill: int = 0, no_line: int = 0) -> str:
    return (
        "<Section N='Geometry' IX='0'>"
        f"<Cell N='NoFill' V='{no_fill}'/><Cell N='NoLine' V='{no_line}'/><Cell N='NoShow' V='0'/>"
        "<Cell N='NoSnap' V='0'/><Cell N='NoQuickDrag' V='0'/>"
        "<Row T='MoveTo' IX='1'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='0' F='Height*0'/></Row>"
        f"<Row T='LineTo' IX='2'><Cell N='X' V='{w}' F='Width*1'/><Cell N='Y' V='0' F='Height*0'/></Row>"
        f"<Row T='LineTo' IX='3'><Cell N='X' V='{w}' F='Width*1'/><Cell N='Y' V='{h}' F='Height*1'/></Row>"
        f"<Row T='LineTo' IX='4'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h}' F='Height*1'/></Row>"
        "<Row T='LineTo' IX='5'><Cell N='X' V='0' F='Geometry1.X1'/><Cell N='Y' V='0' F='Geometry1.Y1'/></Row>"
        "</Section>"
    )


def diamond_geometry(w: float, h: float) -> str:
    return (
        "<Section N='Geometry' IX='0'>"
        "<Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/>"
        "<Cell N='NoSnap' V='0'/><Cell N='NoQuickDrag' V='0'/>"
        f"<Row T='MoveTo' IX='1'><Cell N='X' V='{w/2}' F='Width*0.5'/><Cell N='Y' V='{h}' F='Height*1'/></Row>"
        f"<Row T='LineTo' IX='2'><Cell N='X' V='{w}' F='Width*1'/><Cell N='Y' V='{h/2}' F='Height*0.5'/></Row>"
        f"<Row T='LineTo' IX='3'><Cell N='X' V='{w/2}' F='Width*0.5'/><Cell N='Y' V='0' F='Height*0'/></Row>"
        f"<Row T='LineTo' IX='4'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='{h/2}' F='Height*0.5'/></Row>"
        f"<Row T='LineTo' IX='5'><Cell N='X' V='{w/2}' F='Geometry1.X1'/><Cell N='Y' V='{h}' F='Geometry1.Y1'/></Row>"
        "</Section>"
    )


def shape_rect(sid: int, x: float, y: float, w: float, h: float, text: str, fill: str, line: str, *, bold: bool = False, font_size: float = 0.069, rounding: float = 0.055) -> str:
    return (
        f"<Shape ID='{sid}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>"
        f"{cell('PinX', x)}{cell('PinY', y)}{cell('Width', w)}{cell('Height', h)}"
        f"{cell('LocPinX', w/2, formula='Width*0.5')}{cell('LocPinY', h/2, formula='Height*0.5')}"
        f"{cell('Angle', 0)}{cell('FlipX', 0)}{cell('FlipY', 0)}{cell('ResizeMode', 0)}"
        f"{cell('FillForegnd', fill)}{cell('LineWeight', 0.009, 'PT')}{cell('LineColor', line)}{cell('Rounding', rounding, 'IN')}"
        f"{character(size=font_size, bold=bold, color=line if bold else '#111827')}"
        f"{rect_geometry(w, h)}"
        f"<Text><cp IX='0'/><pp IX='0'/>{esc(text)}</Text>"
        "</Shape>"
    )


def shape_diamond(sid: int, x: float, y: float, w: float, h: float, text: str, fill: str, line: str) -> str:
    return (
        f"<Shape ID='{sid}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>"
        f"{cell('PinX', x)}{cell('PinY', y)}{cell('Width', w)}{cell('Height', h)}"
        f"{cell('LocPinX', w/2, formula='Width*0.5')}{cell('LocPinY', h/2, formula='Height*0.5')}"
        f"{cell('Angle', 0)}{cell('FlipX', 0)}{cell('FlipY', 0)}{cell('ResizeMode', 0)}"
        f"{cell('FillForegnd', fill)}{cell('LineWeight', 0.009, 'PT')}{cell('LineColor', line)}"
        f"{character(size=0.066, bold=False)}"
        f"{diamond_geometry(w, h)}"
        f"<Text><cp IX='0'/><pp IX='0'/>{esc(text)}</Text>"
        "</Shape>"
    )


def shape_line(sid: int, p1: tuple[float, float], p2: tuple[float, float], color: str, *, dashed: bool = False, arrow: bool = False, lw: float = 0.009) -> str:
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    width = max(math.hypot(dx, dy), 0.0001)
    angle = math.atan2(dy, dx)
    extra = f"{cell('LinePattern', 2)}" if dashed else ""
    end_arrow = f"{cell('EndArrow', 13)}" if arrow else ""
    return (
        f"<Shape ID='{sid}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>"
        f"{cell('PinX', (x1+x2)/2, formula='(BeginX+EndX)/2')}{cell('PinY', (y1+y2)/2, formula='(BeginY+EndY)/2')}"
        f"{cell('Width', width, formula='SQRT((EndX-BeginX)^2+(EndY-BeginY)^2)')}{cell('Height', 0)}"
        f"{cell('LocPinX', width/2, formula='Width*0.5')}{cell('LocPinY', 0, formula='Height*0.5')}"
        f"{cell('Angle', angle, formula='ATAN2(EndY-BeginY,EndX-BeginX)')}"
        f"{cell('FlipX', 0)}{cell('FlipY', 0)}{cell('ResizeMode', 0)}"
        f"{cell('BeginX', x1)}{cell('BeginY', y1)}{cell('EndX', x2)}{cell('EndY', y2)}"
        f"{cell('LineWeight', lw, 'PT')}{cell('LineColor', color)}{extra}{end_arrow}"
        "<Section N='Geometry' IX='0'>"
        "<Cell N='NoFill' V='1'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/>"
        "<Cell N='NoSnap' V='0'/><Cell N='NoQuickDrag' V='0'/>"
        "<Row T='MoveTo' IX='1'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='0'/></Row>"
        f"<Row T='LineTo' IX='2'><Cell N='X' V='{width}' F='Width*1'/><Cell N='Y' V='0'/></Row>"
        "</Section>"
        "</Shape>"
    )


def page_xml() -> str:
    sid = 1
    shapes: list[str] = []
    shapes.append(shape_rect(sid, W / 2, H / 2, W, H, "", "#FFFFFF", "#FFFFFF", rounding=0))
    sid += 1
    for m in MODULES:
        shapes.append(shape_rect(sid, m.x + m.w / 2, m.y + m.h / 2, m.w, m.h, "", m.fill, m.stroke, rounding=0.11))
        sid += 1
        shapes.append(shape_rect(sid, m.x + m.w / 2, m.y + m.h - 0.17, max(1.8, m.w - 0.25), 0.22, m.title, m.fill, m.fill, bold=True, font_size=0.064, rounding=0))
        sid += 1
    for e in EDGES:
        pts = list(e.points)
        for idx in range(len(pts) - 1):
            shapes.append(shape_line(sid, pts[idx], pts[idx + 1], e.color, dashed=e.dashed, arrow=idx == len(pts) - 2, lw=0.0085))
            sid += 1
        lx, ly = mid(pts, e.label_offset)
        shapes.append(shape_rect(sid, lx, ly, min(2.05, max(0.65, len(e.label) * 0.048)), 0.26 if len(e.label) < 24 else 0.40, wrap_label(e.label, 24), "#FFFFFF", "#D0D7DE", font_size=0.047, rounding=0.035))
        sid += 1
    for node in NODES.values():
        if node.kind == "diamond":
            shapes.append(shape_diamond(sid, node.x, node.y, node.w, node.h, node.text, node.fill, node.stroke))
        else:
            shapes.append(shape_rect(sid, node.x, node.y, node.w, node.h, node.text, node.fill, node.stroke, font_size=0.062))
        sid += 1
    note = "Solid: forward data/command; dashed: model loading or feedback; red: certificate-triggered protection."
    shapes.append(shape_rect(sid, 4.2, 0.45, 7.6, 0.28, note, "#FFFFFF", "#FFFFFF", font_size=0.052, rounding=0))
    return (
        "<?xml version='1.0' encoding='utf-8' ?>\n"
        "<PageContents xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
        "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' "
        "xml:space='preserve'><Shapes>"
        + "".join(shapes)
        + "</Shapes><Connects/></PageContents>"
    )


def pages_xml() -> str:
    return (
        "<?xml version='1.0' encoding='utf-8' ?>\n"
        "<Pages xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
        "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' xml:space='preserve'>"
        "<Page ID='0' NameU='Fig. 2 module dataflow' IsCustomNameU='1' Name='Fig. 2 module dataflow' IsCustomName='1' "
        f"ViewScale='-1' ViewCenterX='{W/2}' ViewCenterY='{H/2}'>"
        "<PageSheet LineStyle='0' FillStyle='0' TextStyle='0'>"
        f"<Cell N='PageWidth' V='{W}' U='IN'/><Cell N='PageHeight' V='{H}' U='IN'/>"
        "<Cell N='PageScale' V='1' U='IN'/><Cell N='DrawingScale' V='1' U='IN'/>"
        "<Cell N='DrawingSizeType' V='0'/><Cell N='DrawingScaleType' V='0'/>"
        "</PageSheet><Rel ID='rId1' r:id='rId1'/></Page></Pages>"
    )


def write_vsdx() -> None:
    if not TEMPLATE_VSDX.exists():
        raise FileNotFoundError(TEMPLATE_VSDX)
    with zipfile.ZipFile(TEMPLATE_VSDX, "r") as zin, zipfile.ZipFile(OUT_VSDX, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "visio/pages/page1.xml":
                data = page_xml().encode("utf-8")
            elif item.filename == "visio/pages/pages.xml":
                data = pages_xml().encode("utf-8")
            zout.writestr(item, data)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    draw_matplotlib()
    write_vsdx()
    print(f"Wrote {OUT_PDF}")
    print(f"Wrote {OUT_PNG}")
    print(f"Wrote {OUT_SVG}")
    print(f"Wrote {OUT_VSDX}")


if __name__ == "__main__":
    main()
