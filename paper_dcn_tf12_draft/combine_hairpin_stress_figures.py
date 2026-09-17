
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

SUFFIX_ORDER: List[Tuple[str, str]] = [
    ("team_center_traj_compare", "(a) 团队中心轨迹 / Team trajectory"),
    ("four_vehicle_traj_compare", "(b) 四车轨迹 / Four vehicles"),
    ("team_position_error_compare", "(c) 团队位置误差 / Position error"),
    ("system_lat_long_error_compare", "(d) 系统横纵误差 / System e_y/e_s"),
    ("each_vehicle_lat_long_error_compare", "(e) 四车横纵误差 / Vehicle e_y/e_s"),
    ("payload_force_moment_compare", "(f) 货物受力/力矩 / Payload force"),
    ("connection_error_compare", "(g) 刚柔连接误差 / Connection"),
    ("comm_delay_fault_timeline", "(h) 通信/时延/故障 / Comm-fault timeline"),
    ("fault_window_zoom", "(i) 故障窗口放大 / Fault zoom"),
]

CATEGORY_CN = {
    "nominal": "无噪声无故障实验",
    "fault_degraded": "随机单车输出降额故障实验",
    "fault_zero": "随机单车无输出故障实验",
    "comm_noise": "通信噪声实验",
    "targeted_ablations": "针对性消融实验",
    "summary": "全局汇总",
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates += [
            r"C:\Windows\Fonts\msyhbd.ttc",
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
        ]
    candidates += [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        try:
            if Path(path).exists():
                return ImageFont.truetype(path, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
    # Chinese has no spaces; chunk by character when a line is too wide.
    lines: List[str] = []
    cur = ""
    for ch in text:
        test = cur + ch
        if _text_size(draw, test, font)[0] <= max_width or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def _load_titles(metrics_csv: Path) -> Dict[str, str]:
    titles: Dict[str, str] = {}
    if not metrics_csv.exists():
        return titles
    with metrics_csv.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            exp = str(row.get("experiment", "")).strip()
            title = str(row.get("title_cn", "")).strip()
            if exp and title and exp not in titles:
                titles[exp] = title
    return titles


def _split_group_name(file_name: str) -> Tuple[str, str]:
    for suffix, _label in SUFFIX_ORDER:
        tail = "_" + suffix + ".png"
        if file_name.endswith(tail):
            return file_name[: -len(tail)], suffix
    if file_name.endswith(".png"):
        return file_name[:-4], "unknown"
    return file_name, "unknown"


def _collect_groups(figures_dir: Path) -> Dict[str, Dict[str, Dict[str, Path]]]:
    groups: Dict[str, Dict[str, Dict[str, Path]]] = {}
    for cat_dir in sorted([p for p in figures_dir.iterdir() if p.is_dir()]):
        cat = cat_dir.name
        for img in sorted(cat_dir.glob("*.png")):
            group, kind = _split_group_name(img.name)
            groups.setdefault(cat, {}).setdefault(group, {})[kind] = img
    return groups


def _experiment_id_from_group(group: str) -> str:
    return group[5:] if group.startswith("tf13_") else group


def _make_composite(
    group: str,
    cat: str,
    image_map: Dict[str, Path],
    title: str,
    out_path: Path,
    thumb_w: int = 1160,
    thumb_h: int = 760,
    dpi: int = 180,
    save_pdf: bool = False,
) -> None:
    ordered = [(kind, label, image_map[kind]) for kind, label in SUFFIX_ORDER if kind in image_map]
    if not ordered:
        # Summary-only fallback.
        ordered = [("summary", "(a) 全局汇总 / Global summary", next(iter(image_map.values())))]

    n = len(ordered)
    cols = 3 if n > 4 else 2
    rows = int(math.ceil(n / cols))
    margin = 54
    gutter_x = 34
    gutter_y = 48
    title_h = 148
    caption_h = 54
    cell_w = thumb_w
    cell_h = thumb_h + caption_h
    canvas_w = margin * 2 + cols * cell_w + (cols - 1) * gutter_x
    canvas_h = title_h + margin + rows * cell_h + (rows - 1) * gutter_y + margin

    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    draw = ImageDraw.Draw(canvas)
    font_title = _font(42, bold=True)
    font_sub = _font(24, bold=False)
    font_cap = _font(23, bold=True)
    font_small = _font(18, bold=False)

    cat_cn = CATEGORY_CN.get(cat, cat)
    full_title = f"{cat_cn}：{title}"
    wrapped_title = _wrap_to_width(draw, full_title, font_title, canvas_w - 2 * margin)
    y = 30
    for line in wrapped_title[:2]:
        tw, th = _text_size(draw, line, font_title)
        draw.text(((canvas_w - tw) / 2, y), line, fill=(20, 20, 20), font=font_title)
        y += th + 8
    meta = f"source group: {group}    panels: {n}    units are retained from original subfigures"
    tw, th = _text_size(draw, meta, font_sub)
    draw.text(((canvas_w - tw) / 2, y + 6), meta, fill=(80, 80, 80), font=font_sub)

    for idx, (kind, label, path) in enumerate(ordered):
        r, c = divmod(idx, cols)
        x0 = margin + c * (cell_w + gutter_x)
        y0 = title_h + margin + r * (cell_h + gutter_y)
        try:
            im = Image.open(path).convert("RGB")
        except Exception as exc:
            im = Image.new("RGB", (cell_w, thumb_h), (255, 235, 235))
            d = ImageDraw.Draw(im)
            d.text((20, 20), f"Failed to load:\n{path.name}\n{exc}", fill=(160, 0, 0), font=font_small)
        im.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        frame = Image.new("RGB", (cell_w, thumb_h), (248, 248, 248))
        px = (cell_w - im.width) // 2
        py = (thumb_h - im.height) // 2
        frame.paste(im, (px, py))
        canvas.paste(frame, (x0, y0 + caption_h))
        draw.rectangle([x0, y0 + caption_h, x0 + cell_w, y0 + caption_h + thumb_h], outline=(210, 210, 210), width=2)
        cap_lines = _wrap_to_width(draw, label, font_cap, cell_w - 16)
        draw.text((x0 + 8, y0 + 8), cap_lines[0], fill=(30, 30, 30), font=font_cap)
        if len(cap_lines) > 1:
            draw.text((x0 + 8, y0 + 32), cap_lines[1], fill=(70, 70, 70), font=font_small)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, dpi=(dpi, dpi), quality=96)
    if save_pdf:
        canvas.save(out_path.with_suffix(".pdf"), "PDF", resolution=float(dpi))


def build_composites(
    root: Path,
    out_name: str = "figures_composite",
    thumb_w: int = 1160,
    thumb_h: int = 760,
    dpi: int = 180,
    save_pdf: bool = False,
) -> Dict[str, object]:
    figures_dir = root / "figures"
    data_dir = root / "data"
    out_dir = root / out_name
    metrics_csv = data_dir / "tf13_stress_suite_metrics.csv"
    titles = _load_titles(metrics_csv)
    groups = _collect_groups(figures_dir)

    manifest = {
        "root": str(root),
        "figures_dir": str(figures_dir),
        "output_dir": str(out_dir),
        "composites": [],
    }

    for cat, cat_groups in groups.items():
        for group, image_map in sorted(cat_groups.items()):
            exp_id = _experiment_id_from_group(group)
            title = titles.get(exp_id, exp_id)
            out_path = out_dir / cat / f"{group}_composite.png"
            _make_composite(
                group=group,
                cat=cat,
                image_map=image_map,
                title=title,
                out_path=out_path,
                thumb_w=thumb_w,
                thumb_h=thumb_h,
                dpi=dpi,
                save_pdf=save_pdf,
            )
            manifest["composites"].append({
                "category": cat,
                "group": group,
                "experiment": exp_id,
                "title": title,
                "panel_count": len(image_map),
                "path": str(out_path),
                "pdf_path": str(out_path.with_suffix(".pdf")) if save_pdf else None,
            })

    # Category overview contact sheets: one thumbnail per experiment composite.
    by_cat: Dict[str, List[Path]] = {}
    for item in manifest["composites"]:
        by_cat.setdefault(item["category"], []).append(Path(item["path"]))
    for cat, paths in by_cat.items():
        if not paths:
            continue
        thumbs = []
        for p in paths:
            im = Image.open(p).convert("RGB")
            im.thumbnail((900, 650), Image.Resampling.LANCZOS)
            thumbs.append((p, im.copy()))
        cols = 2 if len(thumbs) <= 4 else 3
        rows = math.ceil(len(thumbs) / cols)
        margin, gx, gy, title_h, cap_h = 40, 28, 42, 105, 44
        cell_w, cell_h = 900, 650 + cap_h
        W = margin * 2 + cols * cell_w + (cols - 1) * gx
        H = title_h + margin + rows * cell_h + (rows - 1) * gy + margin
        canvas = Image.new("RGB", (W, H), "white")
        draw = ImageDraw.Draw(canvas)
        ft = _font(38, True)
        fc = _font(22, True)
        title = f"{CATEGORY_CN.get(cat, cat)}：实验总览"
        tw, th = _text_size(draw, title, ft)
        draw.text(((W - tw) / 2, 32), title, fill=(20, 20, 20), font=ft)
        for i, (p, im) in enumerate(thumbs):
            r, c = divmod(i, cols)
            x = margin + c * (cell_w + gx)
            y = title_h + margin + r * (cell_h + gy)
            frame = Image.new("RGB", (cell_w, 650), (248, 248, 248))
            frame.paste(im, ((cell_w - im.width) // 2, (650 - im.height) // 2))
            canvas.paste(frame, (x, y + cap_h))
            draw.rectangle([x, y + cap_h, x + cell_w, y + cap_h + 650], outline=(210, 210, 210), width=2)
            label = p.stem.replace("tf13_", "").replace("_composite", "")
            draw.text((x + 8, y + 8), label, fill=(30, 30, 30), font=fc)
        overview = out_dir / cat / f"{cat}_overview_composite.png"
        canvas.save(overview, dpi=(dpi, dpi), quality=96)
        if save_pdf:
            canvas.save(overview.with_suffix(".pdf"), "PDF", resolution=float(dpi))
        manifest["composites"].append({
            "category": cat,
            "group": f"{cat}_overview",
            "experiment": f"{cat}_overview",
            "title": f"{CATEGORY_CN.get(cat, cat)}：实验总览",
            "panel_count": len(paths),
            "path": str(overview),
            "pdf_path": str(overview.with_suffix(".pdf")) if save_pdf else None,
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "composite_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\hairpin_stress_suite_2026-05-06_030045"))
    ap.add_argument("--out-name", default="figures_composite")
    ap.add_argument("--thumb-w", type=int, default=1160)
    ap.add_argument("--thumb-h", type=int, default=760)
    ap.add_argument("--dpi", type=int, default=180)
    ap.add_argument("--save-pdf", action="store_true")
    args = ap.parse_args()
    manifest = build_composites(
        args.root,
        args.out_name,
        thumb_w=args.thumb_w,
        thumb_h=args.thumb_h,
        dpi=args.dpi,
        save_pdf=args.save_pdf,
    )
    print(json.dumps({
        "output_dir": manifest["output_dir"],
        "composite_count": len(manifest["composites"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
