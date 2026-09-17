#!/usr/bin/env python3
"""Render a compiled PDF into page images for Codex-side visual inspection.

The script can run once or watch the PDF file. It intentionally uses polling
instead of an external watcher package so the project remains portable.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF


def parse_page_spec(spec: str, page_count: int) -> list[int]:
    if spec.lower() == "all":
        return list(range(page_count))

    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = max(1, int(start_s))
            end = min(page_count, int(end_s))
            pages.update(range(start - 1, end))
        else:
            page = int(part)
            if 1 <= page <= page_count:
                pages.add(page - 1)
    return sorted(pages)


def render_pdf(pdf_path: Path, out_dir: Path, dpi: int, pages_spec: str) -> dict:
    pdf_path = pdf_path.resolve()
    out_dir = out_dir.resolve()
    tmp_dir = out_dir.with_name(out_dir.name + "_tmp")

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    rendered: list[dict] = []

    with fitz.open(pdf_path) as doc:
        page_indices = parse_page_spec(pages_spec, doc.page_count)
        for page_index in page_indices:
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image_name = f"page_{page_index + 1:03d}.png"
            image_path = tmp_dir / image_name
            pix.save(str(image_path))
            rendered.append(
                {
                    "page": page_index + 1,
                    "image": image_name,
                    "width": pix.width,
                    "height": pix.height,
                }
            )

        status = {
            "pdf": str(pdf_path),
            "pdf_mtime": pdf_path.stat().st_mtime,
            "rendered_at": datetime.now().isoformat(timespec="seconds"),
            "dpi": dpi,
            "page_count": doc.page_count,
            "pages": rendered,
        }

    (tmp_dir / "preview_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_lines = [
        "# Codex PDF Preview",
        "",
        f"- PDF: `{pdf_path}`",
        f"- Rendered at: `{status['rendered_at']}`",
        f"- DPI: `{dpi}`",
        f"- Pages rendered: `{len(rendered)}` / `{status['page_count']}`",
        "",
    ]
    for item in rendered:
        md_lines.append(f"## Page {item['page']}")
        md_lines.append("")
        md_lines.append(f"![page {item['page']}]({item['image']})")
        md_lines.append("")
    (tmp_dir / "index.md").write_text("\n".join(md_lines), encoding="utf-8")

    out_dir.mkdir(parents=True, exist_ok=True)
    for old_file in out_dir.glob("page_*.png"):
        old_file.unlink(missing_ok=True)
    for old_name in ("index.md", "preview_status.json"):
        (out_dir / old_name).unlink(missing_ok=True)
    for new_file in tmp_dir.iterdir():
        shutil.move(str(new_file), str(out_dir / new_file.name))
    shutil.rmtree(tmp_dir)
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, help="PDF file to render.")
    parser.add_argument("--out", required=True, help="Output preview directory.")
    parser.add_argument("--dpi", type=int, default=130)
    parser.add_argument("--pages", default="all", help='Page spec, e.g. "all" or "1-3,8".')
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=1.5)
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    out_dir = Path(args.out)

    last_mtime = None
    while True:
        try:
            mtime = pdf_path.stat().st_mtime if pdf_path.exists() else None
            if mtime is not None and mtime != last_mtime:
                status = render_pdf(pdf_path, out_dir, args.dpi, args.pages)
                last_mtime = mtime
                print(
                    f"[{status['rendered_at']}] rendered {len(status['pages'])} "
                    f"pages from {pdf_path}",
                    flush=True,
                )
        except Exception as exc:
            print(f"[error] {exc}", file=sys.stderr, flush=True)

        if not args.watch:
            break
        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
