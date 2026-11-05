"""API: document included toggle, delete, and clean new-project spool."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ghostwriter.inbox import list_new_spool_pdfs
from ghostwriter.store import DocumentRole, ProjectStore


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import ghostwriter.server as server

    store = ProjectStore(tmp_path / "data")
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path / "data")
    monkeypatch.setattr(server, "SETTINGS_PATH", tmp_path / "settings.json")
    return TestClient(server.app)


def test_project_documents_expose_included(api: TestClient, tmp_path: Path) -> None:
    project = api.post("/api/projects", json={"patient_label": "P", "reference": ""}).json()
    pid = project["id"]
    pdf = tmp_path / "befund.pdf"
    pdf.write_bytes(b"%PDF")
    with pdf.open("rb") as handle:
        up = api.post(
            f"/api/projects/{pid}/documents",
            data={"role": "befund"},
            files={"file": ("befund.pdf", handle, "application/pdf")},
        )
    assert up.status_code == 200
    docs = up.json()["documents"]
    assert docs[0]["included"] is True


def test_patch_document_included(api: TestClient, tmp_path: Path) -> None:
    import ghostwriter.server as server

    project = api.post("/api/projects", json={"patient_label": "P", "reference": ""}).json()
    pid = project["id"]
    pdf = tmp_path / "befund.pdf"
    pdf.write_bytes(b"%PDF")
    with pdf.open("rb") as handle:
        api.post(
            f"/api/projects/{pid}/documents",
            data={"role": "befund"},
            files={"file": ("befund.pdf", handle, "application/pdf")},
        )
    doc_id = server.STORE.list_documents(pid)[0].id
    patched = api.patch(
        f"/api/projects/{pid}/documents/{doc_id}",
        json={"included": False},
    )
    assert patched.status_code == 200
    assert patched.json()["documents"][0]["included"] is False


def test_delete_document_endpoint(api: TestClient, tmp_path: Path) -> None:
    import ghostwriter.server as server

    project = api.post("/api/projects", json={"patient_label": "P", "reference": ""}).json()
    pid = project["id"]
    pdf = tmp_path / "befund.pdf"
    pdf.write_bytes(b"%PDF")
    with pdf.open("rb") as handle:
        api.post(
            f"/api/projects/{pid}/documents",
            data={"role": "befund"},
            files={"file": ("befund.pdf", handle, "application/pdf")},
        )
    doc = server.STORE.list_documents(pid)[0]
    stored = Path(doc.stored_path)
    deleted = api.delete(f"/api/projects/{pid}/documents/{doc.id}")
    assert deleted.status_code == 200
    assert deleted.json()["documents"] == []
    assert not stored.exists()


def test_included_findings_filter_skips_excluded() -> None:
    from ghostwriter.server import included_finding_documents
    from ghostwriter.store import Document

    docs = [
        Document(
            id="1",
            project_id="p",
            role=DocumentRole.BEFUND,
            display_name="a",
            stored_path="/a",
            extracted_text="text a",
            included=True,
        ),
        Document(
            id="2",
            project_id="p",
            role=DocumentRole.BEFUND,
            display_name="b",
            stored_path="/b",
            extracted_text="text b",
            included=False,
        ),
        Document(
            id="3",
            project_id="p",
            role=DocumentRole.ANFRAGE,
            display_name="c",
            stored_path="/c",
            extracted_text="text c",
            included=True,
        ),
    ]
    findings = included_finding_documents(docs)
    assert [d.id for d in findings] == ["1"]


def test_create_project_marks_existing_spool_as_seen(
    api: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ghostwriter.server as server
    from ghostwriter.settings import AppSettings, save_settings

    spool = tmp_path / "spool"
    spool.mkdir()
    leftover = spool / "old.pdf"
    leftover.write_bytes(b"%PDF-old")
    settings = AppSettings(spool_dir=str(spool))
    save_settings(server.SETTINGS_PATH, settings)
    state = server.DATA_ROOT / "inbox_state.json"
    assert list_new_spool_pdfs(spool, state_path=state)

    api.post("/api/projects", json={"patient_label": "Neu", "reference": ""})
    assert list_new_spool_pdfs(spool, state_path=state) == []
