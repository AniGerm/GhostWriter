"""Additional store coverage."""

from __future__ import annotations

from pathlib import Path

from ghostwriter.store import DocumentRole, ProjectStore


def test_list_documents_and_update(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    project = store.create_project(patient_label="P", reference="")
    src = tmp_path / "f.pdf"
    src.write_bytes(b"%PDF")
    doc = store.add_document(project.id, src, DocumentRole.BEFUND, "f.pdf")
    store.update_document_text(doc.id, "Inhalt", 2)
    docs = store.list_documents(project.id)
    assert docs[0].extracted_text == "Inhalt"
    assert docs[0].page_count == 2
    assert "root" in store.export_settings_json()
    store.close()


def test_get_missing_project(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    assert store.get_project("nope") is None
    assert store.get_cost_snapshot("nope") is None
    assert store.get_questions("nope") == []
