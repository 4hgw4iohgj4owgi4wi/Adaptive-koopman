from __future__ import annotations

import html
import math
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TEMPLATE = (
    ROOT.parent
    / "nature_visio_diagrams_2026-05-21_review_clean_v5_reference_style"
    / "NRKDCC_control_flow_nature_style_editable.vsdx"
)
OUT_VSDX = ROOT / "figures" / "fig2_online_signal_flow_tikz_replicated_corrected_20260528.vsdx"
OUT_SVG = ROOT / "figures" / "fig2_online_signal_flow_tikz_replicated_corrected_20260528_preview.svg"

PAGE_W = 16.0
PAGE_H = 5.4


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def cell(name: str, value: object, unit: str | None = None, formula: str | None = None) -> str:
    attrs = f"N='{name}' V='{value}'"
    if unit:
        attrs += f" U='{unit}'"
    if formula:
        attrs += f" F='{formula}'"
    return f"<Cell {attrs}/>"


def character(size: float = 0.087, color: str = "#1f2937", bold: bool = False) -> str:
    style = 1 if bold else 0
    return (
        "<Section N='Character'><Row IX='0'>"
        "<Cell N='Font' V='Arial' F='FONT(\"Arial\")'/>"
        f"<Cell N='Color' V='{color}'/>"
        f"<Cell N='Style' V='{style}'/>"
        f"<Cell N='Size' V='{size}' U='PT'/>"
        "</Row></Section>"
    )


def rect_geometry(w: float, h: float) -> str:
    return (
        "<Section N='Geometry' IX='0'>"
        "<Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/>"
        "<Cell N='NoSnap' V='0'/><Cell N='NoQuickDrag' V='0'/>"
        f"<Row T='MoveTo' IX='1'><Cell N='X' V='0' F='Width*0'/><Cell N='Y' V='0' F='Height*0'/></Row>"
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


def text_to_visio(text: str) -> str:
    return "&#10;".join(esc(part) for part in text.split("\n"))


def shape_rect(
    sid: int,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    fill: str,
    line: str,
    *,
    size: float = 0.083,
    bold: bool = False,
    rounding: float = 0.06,
) -> str:
    return (
        f"<Shape ID='{sid}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>"
        f"{cell('PinX', x)}{cell('PinY', y)}{cell('Width', w)}{cell('Height', h)}"
        f"{cell('LocPinX', w/2, formula='Width*0.5')}{cell('LocPinY', h/2, formula='Height*0.5')}"
        f"{cell('Angle', 0)}{cell('FlipX', 0)}{cell('FlipY', 0)}{cell('ResizeMode', 0)}"
        f"{cell('FillForegnd', fill)}{cell('LineWeight', 0.012, 'PT')}{cell('LineColor', line)}"
        f"{cell('Rounding', rounding, 'IN')}"
        f"{character(size=size, bold=bold)}"
        f"{rect_geometry(w, h)}"
        f"<Text><cp IX='0'/><pp IX='0'/>{text_to_visio(text)}</Text>"
        "</Shape>"
    )


def shape_diamond(
    sid: int,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    fill: str,
    line: str,
) -> str:
    return (
        f"<Shape ID='{sid}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>"
        f"{cell('PinX', x)}{cell('PinY', y)}{cell('Width', w)}{cell('Height', h)}"
        f"{cell('LocPinX', w/2, formula='Width*0.5')}{cell('LocPinY', h/2, formula='Height*0.5')}"
        f"{cell('Angle', 0)}{cell('FlipX', 0)}{cell('FlipY', 0)}{cell('ResizeMode', 0)}"
        f"{cell('FillForegnd', fill)}{cell('LineWeight', 0.012, 'PT')}{cell('LineColor', line)}"
        f"{character(size=0.079, bold=True)}"
        f"{diamond_geometry(w, h)}"
        f"<Text><cp IX='0'/><pp IX='0'/>{text_to_visio(text)}</Text>"
        "</Shape>"
    )


def shape_text(sid: int, x: float, y: float, w: float, h: float, text: str, color: str = "#374151", size: float = 0.075) -> str:
    return (
        f"<Shape ID='{sid}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>"
        f"{cell('PinX', x)}{cell('PinY', y)}{cell('Width', w)}{cell('Height', h)}"
        f"{cell('LocPinX', w/2, formula='Width*0.5')}{cell('LocPinY', h/2, formula='Height*0.5')}"
        f"{cell('Angle', 0)}{cell('FlipX', 0)}{cell('FlipY', 0)}{cell('ResizeMode', 0)}"
        f"{cell('FillPattern', 0)}{cell('LinePattern', 0)}"
        f"{character(size=size, color=color)}"
        f"{rect_geometry(w, h)}"
        f"<Text><cp IX='0'/><pp IX='0'/>{text_to_visio(text)}</Text>"
        "</Shape>"
    )


def shape_line(
    sid: int,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: str,
    *,
    dashed: bool = False,
    arrow: bool = True,
) -> str:
    dx = x2 - x1
    dy = y2 - y1
    width = math.hypot(dx, dy)
    angle = math.atan2(dy, dx)
    pinx = (x1 + x2) / 2
    piny = (y1 + y2) / 2
    extra = f"{cell('LinePattern', 2)}" if dashed else ""
    end_arrow = f"{cell('EndArrow', 13)}" if arrow else ""
    return (
        f"<Shape ID='{sid}' Type='Shape' LineStyle='3' FillStyle='3' TextStyle='3'>"
        f"{cell('PinX', pinx, formula='(BeginX+EndX)/2')}{cell('PinY', piny, formula='(BeginY+EndY)/2')}"
        f"{cell('Width', width, formula='SQRT((EndX-BeginX)^2+(EndY-BeginY)^2)')}{cell('Height', 0)}"
        f"{cell('LocPinX', width/2, formula='Width*0.5')}{cell('LocPinY', 0, formula='Height*0.5')}"
        f"{cell('Angle', angle, formula='ATAN2(EndY-BeginY,EndX-BeginX)')}"
        f"{cell('FlipX', 0)}{cell('FlipY', 0)}{cell('ResizeMode', 0)}"
        f"{cell('BeginX', x1)}{cell('BeginY', y1)}{cell('EndX', x2)}{cell('EndY', y2)}"
        f"{cell('LineWeight', 0.012, 'PT')}{cell('LineColor', color)}{extra}{end_arrow}"
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
    shapes.append(
        shape_rect(sid, PAGE_W / 2, PAGE_H / 2, PAGE_W, PAGE_H, "", "#ffffff", "#ffffff", rounding=0)
    )
    sid += 1

    colors = {
        "proc": ("#eef5ff", "#2563eb"),
        "comm": ("#ecfdf5", "#0f766e"),
        "safe": ("#fff1f2", "#dc2626"),
        "decide": ("#fff7ed", "#ea580c"),
    }

    nodes = {
        "obs": (0.8, 4.45, "Observation\nfusion", "proc"),
        "lift": (2.9, 4.45, "Lifted state\nz = Phi_theta(chi)", "proc"),
        "koop": (5.0, 4.45, "IRSP Koopman\nprediction", "proc"),
        "remote": (7.1, 4.45, "Remote-state\nprediction", "proc"),
        "mpc": (9.2, 4.45, "MPC cost and\nconstraints", "proc"),
        "fourws": (0.8, 2.9, "4WS reference\nmodel", "comm"),
        "pathlink": (2.9, 2.9, "Reference\ncommunication", "comm"),
        "quality": (5.0, 2.9, "Link-quality\nconsensus", "comm"),
        "delay": (7.1, 2.9, "Delay\ncompensation", "comm"),
        "fdi": (9.2, 2.9, "FDI residual\nmonitoring", "safe"),
        "fallback": (9.2, 1.25, "Degraded\nfallback", "safe"),
        "filter": (11.35, 1.25, "Projection and\ntightening", "safe"),
        "cert": (11.35, 3.55, "Certificate\npasses?", "decide"),
        "cmd": (13.35, 3.55, "Command\npublication", "proc"),
        "cmdlink": (13.35, 1.65, "Command\ncommunication", "comm"),
        "plant": (15.2, 3.55, "Vehicle-payload\nsystem", "proc"),
        "logs": (15.2, 1.65, "Errors, forces,\nconstraints, logs", "proc"),
    }
    node_w = 1.42
    node_h = 0.52
    for name, (x, y, text, kind) in nodes.items():
        fill, line = colors[kind]
        if kind == "decide":
            shapes.append(shape_diamond(sid, x, y, 1.25, 0.9, text, fill, line))
        else:
            shapes.append(shape_rect(sid, x, y, node_w, node_h, text, fill, line))
        sid += 1

    def right(n: str) -> tuple[float, float]:
        x, y = nodes[n][0], nodes[n][1]
        w = 0.625 if n == "cert" else node_w / 2
        return x + w, y

    def left(n: str) -> tuple[float, float]:
        x, y = nodes[n][0], nodes[n][1]
        w = 0.625 if n == "cert" else node_w / 2
        return x - w, y

    def top(n: str) -> tuple[float, float]:
        x, y = nodes[n][0], nodes[n][1]
        h = 0.45 if n == "cert" else node_h / 2
        return x, y + h

    def bottom(n: str) -> tuple[float, float]:
        x, y = nodes[n][0], nodes[n][1]
        h = 0.45 if n == "cert" else node_h / 2
        return x, y - h

    blue = "#2563eb"
    teal = "#0f766e"
    red = "#dc2626"
    green = "#16a34a"
    gray = "#6b7280"

    for a, b, c in [
        ("obs", "lift", blue),
        ("lift", "koop", blue),
        ("koop", "remote", blue),
        ("remote", "mpc", blue),
        ("fourws", "pathlink", teal),
        ("pathlink", "quality", teal),
        ("quality", "delay", teal),
        ("cmd", "plant", blue),
    ]:
        x1, y1 = right(a)
        x2, y2 = left(b)
        shapes.append(shape_line(sid, x1, y1, x2, y2, c))
        sid += 1

    for a, b, c in [
        ("delay", "remote", teal),
        ("mpc", "fdi", red),
        ("fdi", "cert", red),
        ("cert", "cmd", green),
        ("cert", "filter", red),
        ("filter", "fallback", red),
        ("fallback", "fdi", red),
        ("cmd", "cmdlink", teal),
        ("cmdlink", "plant", teal),
        ("plant", "logs", gray),
    ]:
        if a == "cert" and b == "cmd":
            x1, y1 = right(a)
            x2, y2 = left(b)
        elif a == "cert" and b == "filter":
            x1, y1 = bottom(a)
            x2, y2 = top(b)
        elif a == "fallback" and b == "fdi":
            x1, y1 = top(a)
            x2, y2 = bottom(b)
        elif a == "filter" and b == "fallback":
            x1, y1 = left(a)
            x2, y2 = right(b)
        elif a == "fdi" and b == "cert":
            x1, y1 = right(a)
            x2, y2 = left(b)
        elif a == "cmdlink" and b == "plant":
            x1, y1 = right(a)
            x2, y2 = bottom(b)
        else:
            x1, y1 = bottom(a)
            x2, y2 = top(b)
        shapes.append(shape_line(sid, x1, y1, x2, y2, c))
        sid += 1

    # Text labels for the certificate branch.
    shapes.append(shape_text(sid, 12.35, 3.80, 0.38, 0.22, "yes", "#166534", 0.068))
    sid += 1
    shapes.append(shape_text(sid, 11.78, 2.35, 0.32, 0.22, "no", "#991b1b", 0.068))
    sid += 1

    # Dashed feedback/degradation channels, kept as editable orthogonal segments.
    x1, y1 = bottom("logs")
    x2, y2 = bottom("obs")
    via_y = 0.62
    for p1, p2, arr in [
        ((x1, y1), (x1, via_y), False),
        ((x1, via_y), (x2, via_y), False),
        ((x2, via_y), (x2, y2), True),
    ]:
        shapes.append(shape_line(sid, p1[0], p1[1], p2[0], p2[1], gray, dashed=True, arrow=arr))
        sid += 1

    x1, y1 = left("logs")
    # Logged errors/forces/constraints are feedback inputs to the next
    # certificate evaluation, not the "no" branch of the decision.
    x2, y2 = top("cert")
    mid_x = x2
    for p1, p2, arr in [
        ((x1, y1), (mid_x, y1), False),
        ((mid_x, y1), (x2, y2 + 0.08), False),
        ((x2, y2 + 0.08), (x2, y2), True),
    ]:
        shapes.append(shape_line(sid, p1[0], p1[1], p2[0], p2[1], gray, dashed=True, arrow=arr))
        sid += 1

    x1, y1 = bottom("quality")
    x2, y2 = bottom("filter")
    via_y = 0.90
    for p1, p2, arr in [
        ((x1, y1), (x1, via_y), False),
        ((x1, via_y), (x2, via_y), False),
        ((x2, via_y), (x2, y2), True),
    ]:
        shapes.append(shape_line(sid, p1[0], p1[1], p2[0], p2[1], teal, dashed=True, arrow=arr))
        sid += 1

    note = "Dashed paths denote communication degradation, certificate feedback, and safety fallback channels."
    shapes.append(shape_text(sid, 5.1, 0.38, 8.6, 0.34, note, "#4b5563", 0.072))

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
        "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' "
        "xml:space='preserve'>"
        "<Page ID='0' NameU='Fig. 2 Online signal-flow diagram' IsCustomNameU='1' "
        "Name='Fig. 2 Online signal-flow diagram' IsCustomName='1' "
        f"ViewScale='-1' ViewCenterX='{PAGE_W/2}' ViewCenterY='{PAGE_H/2}'>"
        "<PageSheet LineStyle='0' FillStyle='0' TextStyle='0'>"
        f"<Cell N='PageWidth' V='{PAGE_W}' U='IN'/><Cell N='PageHeight' V='{PAGE_H}' U='IN'/>"
        "<Cell N='ShdwOffsetX' V='0.1181102362204724'/>"
        "<Cell N='ShdwOffsetY' V='-0.1181102362204724'/>"
        "<Cell N='PageScale' V='1' U='IN'/><Cell N='DrawingScale' V='1' U='IN'/>"
        "<Cell N='DrawingSizeType' V='0'/><Cell N='DrawingScaleType' V='0'/>"
        "</PageSheet><Rel ID='rId1' r:id='rId1'/></Page></Pages>"
    )


def svg_preview() -> str:
    # A lightweight visual preview generated from the same layout decisions.
    scale = 90
    width = int(PAGE_W * scale)
    height = int(PAGE_H * scale)

    def sx(x: float) -> float:
        return x * scale

    def sy(y: float) -> float:
        return (PAGE_H - y) * scale

    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        "<rect width='100%' height='100%' fill='white'/>",
        "<defs><marker id='arrow' markerWidth='8' markerHeight='8' refX='7' refY='4' orient='auto' markerUnits='strokeWidth'><path d='M0,0 L8,4 L0,8 z' fill='#1f2937'/></marker></defs>",
        "<style>text{font-family:Arial,sans-serif;font-size:12px;fill:#1f2937;text-anchor:middle}.small{font-size:10px;fill:#4b5563}</style>",
    ]

    nodes = {
        "obs": (0.8, 4.45, "Observation\nfusion", "proc"),
        "lift": (2.9, 4.45, "Lifted state\nz = Phi_theta(chi)", "proc"),
        "koop": (5.0, 4.45, "IRSP Koopman\nprediction", "proc"),
        "remote": (7.1, 4.45, "Remote-state\nprediction", "proc"),
        "mpc": (9.2, 4.45, "MPC cost and\nconstraints", "proc"),
        "fourws": (0.8, 2.9, "4WS reference\nmodel", "comm"),
        "pathlink": (2.9, 2.9, "Reference\ncommunication", "comm"),
        "quality": (5.0, 2.9, "Link-quality\nconsensus", "comm"),
        "delay": (7.1, 2.9, "Delay\ncompensation", "comm"),
        "fdi": (9.2, 2.9, "FDI residual\nmonitoring", "safe"),
        "fallback": (9.2, 1.25, "Degraded\nfallback", "safe"),
        "filter": (11.35, 1.25, "Projection and\ntightening", "safe"),
        "cert": (11.35, 3.55, "Certificate\npasses?", "decide"),
        "cmd": (13.35, 3.55, "Command\npublication", "proc"),
        "cmdlink": (13.35, 1.65, "Command\ncommunication", "comm"),
        "plant": (15.2, 3.55, "Vehicle-payload\nsystem", "proc"),
        "logs": (15.2, 1.65, "Errors, forces,\nconstraints, logs", "proc"),
    }
    colors = {
        "proc": ("#eef5ff", "#2563eb"),
        "comm": ("#ecfdf5", "#0f766e"),
        "safe": ("#fff1f2", "#dc2626"),
        "decide": ("#fff7ed", "#ea580c"),
    }
    node_w = 1.42
    node_h = 0.52

    def side(n: str, which: str) -> tuple[float, float]:
        x, y = nodes[n][0], nodes[n][1]
        w = 0.625 if n == "cert" else node_w / 2
        h = 0.45 if n == "cert" else node_h / 2
        if which == "r":
            return x + w, y
        if which == "l":
            return x - w, y
        if which == "t":
            return x, y + h
        return x, y - h

    def line(a: tuple[float, float], b: tuple[float, float], color: str, dashed: bool = False) -> None:
        dash = " stroke-dasharray='7 5'" if dashed else ""
        parts.append(
            f"<line x1='{sx(a[0]):.1f}' y1='{sy(a[1]):.1f}' x2='{sx(b[0]):.1f}' y2='{sy(b[1]):.1f}' "
            f"stroke='{color}' stroke-width='2'{dash} marker-end='url(#arrow)'/>"
        )

    for a, b, c in [
        ("obs", "lift", "#2563eb"),
        ("lift", "koop", "#2563eb"),
        ("koop", "remote", "#2563eb"),
        ("remote", "mpc", "#2563eb"),
        ("fourws", "pathlink", "#0f766e"),
        ("pathlink", "quality", "#0f766e"),
        ("quality", "delay", "#0f766e"),
        ("cmd", "plant", "#2563eb"),
    ]:
        line(side(a, "r"), side(b, "l"), c)

    line(side("delay", "t"), side("remote", "b"), "#0f766e")
    line(side("mpc", "b"), side("fdi", "t"), "#dc2626")
    line(side("fdi", "r"), side("cert", "l"), "#dc2626")
    line(side("cert", "r"), side("cmd", "l"), "#16a34a")
    line(side("cert", "b"), side("filter", "t"), "#dc2626")
    line(side("filter", "l"), side("fallback", "r"), "#dc2626")
    line(side("fallback", "t"), side("fdi", "b"), "#dc2626")
    line(side("cmd", "b"), side("cmdlink", "t"), "#0f766e")
    line(side("cmdlink", "r"), side("plant", "b"), "#0f766e")
    line(side("plant", "b"), side("logs", "t"), "#6b7280")
    def line_plain(a: tuple[float, float], b: tuple[float, float], color: str, dashed: bool = False, arrow: bool = False) -> None:
        dash = " stroke-dasharray='7 5'" if dashed else ""
        marker = " marker-end='url(#arrow)'" if arrow else ""
        parts.append(
            f"<line x1='{sx(a[0]):.1f}' y1='{sy(a[1]):.1f}' x2='{sx(b[0]):.1f}' y2='{sy(b[1]):.1f}' "
            f"stroke='{color}' stroke-width='2'{dash}{marker}/>"
        )

    a = side("logs", "b")
    b = side("obs", "b")
    via_y = 0.62
    line_plain(a, (a[0], via_y), "#6b7280", dashed=True)
    line_plain((a[0], via_y), (b[0], via_y), "#6b7280", dashed=True)
    line_plain((b[0], via_y), b, "#6b7280", dashed=True, arrow=True)

    a = side("logs", "l")
    b = side("cert", "t")
    line_plain(a, (b[0], a[1]), "#6b7280", dashed=True)
    line_plain((b[0], a[1]), (b[0], b[1] + 0.08), "#6b7280", dashed=True)
    line_plain((b[0], b[1] + 0.08), b, "#6b7280", dashed=True, arrow=True)

    a = side("quality", "b")
    b = side("filter", "b")
    via_y = 0.90
    line_plain(a, (a[0], via_y), "#0f766e", dashed=True)
    line_plain((a[0], via_y), (b[0], via_y), "#0f766e", dashed=True)
    line_plain((b[0], via_y), b, "#0f766e", dashed=True, arrow=True)

    for name, (x, y, text, kind) in nodes.items():
        fill, stroke = colors[kind]
        cx, cy = sx(x), sy(y)
        if kind == "decide":
            w, h = sx(1.25), sx(0.9)
            pts = f"{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}"
            parts.append(f"<polygon points='{pts}' fill='{fill}' stroke='{stroke}' stroke-width='1.5'/>")
        else:
            w, h = sx(node_w), sx(node_h)
            parts.append(
                f"<rect x='{cx-w/2:.1f}' y='{cy-h/2:.1f}' width='{w:.1f}' height='{h:.1f}' "
                f"rx='7' fill='{fill}' stroke='{stroke}' stroke-width='1.5'/>"
            )
        lines = text.split("\n")
        base_y = cy - (len(lines) - 1) * 7
        for idx, t in enumerate(lines):
            parts.append(f"<text x='{cx:.1f}' y='{base_y + idx*15:.1f}'>{esc(t)}</text>")

    parts.append(f"<text x='{sx(12.35):.1f}' y='{sy(3.80):.1f}' fill='#166534'>yes</text>")
    parts.append(f"<text x='{sx(11.78):.1f}' y='{sy(2.35):.1f}' fill='#991b1b'>no</text>")
    parts.append(
        f"<text class='small' x='{sx(5.1):.1f}' y='{sy(0.38):.1f}'>"
        "Dashed paths denote communication degradation, certificate feedback, and safety fallback channels.</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    if not TEMPLATE.exists():
        raise FileNotFoundError(TEMPLATE)
    OUT_VSDX.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(TEMPLATE, "r") as zin, zipfile.ZipFile(OUT_VSDX, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "visio/pages/page1.xml":
                data = page_xml().encode("utf-8")
            elif item.filename == "visio/pages/pages.xml":
                data = pages_xml().encode("utf-8")
            zout.writestr(item, data)
    OUT_SVG.write_text(svg_preview(), encoding="utf-8")
    print(f"Wrote {OUT_VSDX}")
    print(f"Wrote {OUT_SVG}")


if __name__ == "__main__":
    main()
