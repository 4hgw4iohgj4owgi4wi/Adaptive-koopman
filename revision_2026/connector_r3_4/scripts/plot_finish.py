from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def png_to_pdf(png: Path, pdf: Path) -> None:
    image = plt.imread(png)
    height, width = image.shape[:2]
    dpi = 150.0
    figure = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi, frameon=False)
    axis = figure.add_axes((0.0, 0.0, 1.0, 1.0))
    axis.imshow(image)
    axis.axis("off")
    figure.savefig(pdf, format="pdf", dpi=dpi, bbox_inches="tight", pad_inches=0.0)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    project = args.project_root.resolve()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"plot output must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    command = [
        sys.executable,
        "-B",
        str(ROOT / "scripts" / "plot_flow.py"),
        "--project-root",
        str(project),
        "--output-dir",
        str(output),
        "--final",
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    (output / "plot_flow.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output / "plot_flow.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)

    figures = output / "figures"
    data = output / "figure_data"
    pngs = sorted(figures.glob("*.png"))
    csv_stems = {path.stem for path in data.glob("*.csv")}
    meta_stems = {path.name.removesuffix(".meta.json") for path in data.glob("*.meta.json")}
    png_stems = {path.stem for path in pngs}
    for png in pngs:
        png_to_pdf(png, png.with_suffix(".pdf"))
    pdf_stems = {path.stem for path in figures.glob("*.pdf")}
    passed = len(pngs) >= 12 and png_stems == pdf_stems == csv_stems == meta_stems
    result = {
        "stage": "PLOT_FINISH",
        "passed": passed,
        "command": command,
        "plot_returncode": completed.returncode,
        "png_count": len(pngs),
        "pdf_count": len(pdf_stems),
        "csv_count": len(csv_stems),
        "meta_count": len(meta_stems),
        "common_stems": sorted(png_stems),
        "runtime_s": time.perf_counter() - started,
    }
    write_json(output / "plot_finish.json", result)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
