"""PDFium darf nicht abstürzen, wenn Vorschau und Seitenzahl parallel laufen."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def _text_pdf(path: Path) -> None:
    writer = PdfWriter()
    for index in range(2):
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        resources = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        page[NameObject("/Resources")] = resources
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 18 Tf 72 {700 - index * 40} Td (Seite {index}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    with path.open("wb") as handle:
        writer.write(handle)


def test_parallel_page_count_and_render_stay_alive(tmp_path: Path) -> None:
    src = tmp_path / "brief.pdf"
    _text_pdf(src)
    out = tmp_path / "out"
    out.mkdir()
    script = textwrap.dedent(
        """
        import sys
        import threading
        from pathlib import Path

        from ghostwriter.ocr.pdf_render import count_pages, render_one_page

        src = Path(sys.argv[1])
        dest_dir = Path(sys.argv[2])
        barrier = threading.Barrier(4)

        def work(index: int) -> None:
            barrier.wait()
            for n in range(6):
                count_pages(src)
                render_one_page(src, dest_dir / f"{index}-{n}.png", 1 + (n % 2), dpi=72)

        threads = [threading.Thread(target=work, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        print("ok")
        """
    )
    env = os.environ.copy()
    root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-c", script, str(src), str(out)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
