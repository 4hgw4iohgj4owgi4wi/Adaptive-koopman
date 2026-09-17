from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_MD = ROOT / "manuscript_zh_word_export.md"
BIB_FILE = ROOT / "refs_zh_docx.bib"
OUTPUT_DOCX = ROOT / "manuscript_zh.docx"


def main() -> None:
    cmd = [
        "pandoc",
        str(SOURCE_MD),
        "--from",
        "markdown+tex_math_dollars",
        "--to",
        "docx",
        "--output",
        str(OUTPUT_DOCX),
        "--citeproc",
        "--bibliography",
        str(BIB_FILE),
    ]
    subprocess.run(cmd, check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
