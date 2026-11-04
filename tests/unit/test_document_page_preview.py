"""Dokument-Seitenbilder für die Druckvorschau."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ghostwriter.store import ProjectStore
from pypdf import PdfWriter


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    store = ProjectStore(tmp_path / "data")
    import ghostwriter.server as server

    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path / "data")
    monkeypatch.setattr(server, "SETTINGS_PATH", tmp_path / "settings.json")
    return TestClient(server.app)


def _blank_pdf(path: Path, pages: int = 2) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with path.open("wb") as handle:
        writer.write(handle)


def test_document_page_preview_returns_png(api: TestClient, tmp_path: Path) -> None:
    import ghostwriter.server as server

    project = api.post("/api/projects", json={"patient_label": "Preview", "reference": ""}).json()
    pid = project["id"]
    pdf = tmp_path / "befund.pdf"
    _blank_pdf(pdf, pages=2)
    with pdf.open("rb") as handle:
        up = api.post(
            f"/api/projects/{pid}/documents",
            data={"role": "befund"},
            files={"file": ("befund.pdf", handle, "application/pdf")},
        )
    assert up.status_code == 200
    doc_id = server.STORE.list_documents(pid)[0].id

    page1 = api.get(f"/api/projects/{pid}/documents/{doc_id}/pages/1")
    assert page1.status_code == 200
    assert page1.headers["content-type"].startswith("image/png")
    assert page1.content[:8] == b"\x89PNG\r\n\x1a\n"

    page2 = api.get(f"/api/projects/{pid}/documents/{doc_id}/pages/2")
    assert page2.status_code == 200
    assert page2.content[:8] == b"\x89PNG\r\n\x1a\n"

    missing = api.get(f"/api/projects/{pid}/documents/{doc_id}/pages/99")
    assert missing.status_code == 404
