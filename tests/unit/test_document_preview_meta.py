"""Dokument-Vorschau: Seitenzahl für internen Viewer."""

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


def _blank_pdf(path: Path, pages: int = 3) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with path.open("wb") as handle:
        writer.write(handle)


def test_document_preview_meta_returns_page_count(
    api: TestClient, tmp_path: Path
) -> None:
    import ghostwriter.server as server

    project = api.post("/api/projects", json={"patient_label": "Meta", "reference": ""}).json()
    pid = project["id"]
    pdf = tmp_path / "befund.pdf"
    _blank_pdf(pdf, pages=3)
    with pdf.open("rb") as handle:
        api.post(
            f"/api/projects/{pid}/documents",
            data={"role": "befund"},
            files={"file": ("befund.pdf", handle, "application/pdf")},
        )
    doc_id = server.STORE.list_documents(pid)[0].id

    response = api.get(f"/api/projects/{pid}/documents/{doc_id}/preview")
    assert response.status_code == 200
    assert response.json() == {"page_count": 3, "display_name": "befund.pdf"}


def test_document_file_served_inline(api: TestClient, tmp_path: Path) -> None:
    import ghostwriter.server as server

    project = api.post("/api/projects", json={"patient_label": "Inline", "reference": ""}).json()
    pid = project["id"]
    pdf = tmp_path / "anfrage.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    with pdf.open("rb") as handle:
        api.post(
            f"/api/projects/{pid}/documents",
            data={"role": "anfrage"},
            files={"file": ("anfrage.pdf", handle, "application/pdf")},
        )
    doc_id = server.STORE.list_documents(pid)[0].id
    response = api.get(f"/api/projects/{pid}/documents/{doc_id}/file")
    assert response.status_code == 200
    disposition = response.headers.get("content-disposition", "").lower()
    assert "inline" in disposition
    assert "attachment" not in disposition
