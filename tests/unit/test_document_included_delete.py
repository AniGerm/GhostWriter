"""Document included-flag and delete behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.store import DocumentRole, ProjectStore


@pytest.fixture()
def store(tmp_path: Path) -> ProjectStore:
    return ProjectStore(root=tmp_path / "data")


def _pdf(tmp_path: Path, name: str = "doc.pdf") -> Path:
    path = tmp_path / name
    path.write_bytes(b"%PDF-1.4 fake")
    return path


def test_add_document_defaults_to_included(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project(patient_label="P", reference="")
    doc = store.add_document(
        project.id, _pdf(tmp_path), DocumentRole.BEFUND, "befund.pdf"
    )
    assert doc.included is True
    listed = store.list_documents(project.id)
    assert listed[0].included is True


def test_set_document_included_toggles(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project(patient_label="P", reference="")
    doc = store.add_document(
        project.id, _pdf(tmp_path), DocumentRole.BEFUND, "befund.pdf"
    )
    updated = store.set_document_included(doc.id, False)
    assert updated.included is False
    assert store.list_documents(project.id)[0].included is False
    restored = store.set_document_included(doc.id, True)
    assert restored.included is True


def test_set_document_included_missing_raises(store: ProjectStore) -> None:
    with pytest.raises(KeyError):
        store.set_document_included("missing", False)


def test_delete_document_removes_db_and_file(
    store: ProjectStore, tmp_path: Path
) -> None:
    project = store.create_project(patient_label="P", reference="")
    doc = store.add_document(
        project.id, _pdf(tmp_path), DocumentRole.BEFUND, "befund.pdf"
    )
    stored = Path(doc.stored_path)
    assert stored.is_file()
    assert store.delete_document(project.id, doc.id) is True
    assert store.list_documents(project.id) == []
    assert not stored.exists()


def test_delete_document_wrong_project_returns_false(
    store: ProjectStore, tmp_path: Path
) -> None:
    a = store.create_project(patient_label="A", reference="")
    b = store.create_project(patient_label="B", reference="")
    doc = store.add_document(a.id, _pdf(tmp_path), DocumentRole.BEFUND, "b.pdf")
    assert store.delete_document(b.id, doc.id) is False
    assert store.list_documents(a.id)


def test_delete_anfrage_allows_second_upload(
    store: ProjectStore, tmp_path: Path
) -> None:
    project = store.create_project(patient_label="P", reference="")
    first = store.add_document(
        project.id, _pdf(tmp_path, "a.pdf"), DocumentRole.ANFRAGE, "a.pdf"
    )
    assert store.delete_document(project.id, first.id) is True
    second = store.add_document(
        project.id, _pdf(tmp_path, "b.pdf"), DocumentRole.ANFRAGE, "b.pdf"
    )
    assert second.role is DocumentRole.ANFRAGE
    assert len(store.list_documents(project.id)) == 1
