"""OCR-Worker: Datei → Text (Subprozess-fähig)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ghostwriter.extract import ExtractionResult
from ghostwriter.ocr.pdf_render import render_pages


def ocr_file(path: Path, work_dir: Path) -> ExtractionResult:
    """Rendert Seiten und führt PaddleOCR aus; gibt GPU danach frei."""
    from ghostwriter.ocr.engine import clear_pipeline, ocr_image

    work_dir.mkdir(parents=True, exist_ok=True)
    pages = render_pages(path, work_dir / "pages")
    texts: list[str] = []
    try:
        for page in pages:
            texts.append(ocr_image(page))
    finally:
        clear_pipeline()
    return ExtractionResult(
        text="\n\n".join(t for t in texts if t).strip(),
        page_count=len(pages),
        used_ocr=True,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI: ghostwriter.ocr.worker <input> <work_dir> → JSON auf stdout."""
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("usage: worker <input> <work_dir>", file=sys.stderr)
        return 2
    result = ocr_file(Path(args[0]), Path(args[1]))
    print(
        json.dumps(
            {
                "text": result.text,
                "page_count": result.page_count,
                "used_ocr": result.used_ocr,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
