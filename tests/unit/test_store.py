"""Tests for the SQLite project store."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.store import DocumentRole, ProjectStore, Question


@pytest.fixture()
def store(tmp_path: Path) -> ProjectStore:
    return ProjectStore(root=tmp_path / "data")


def test_birth_date_is_read_back(store: ProjectStore) -> None:
    project = store.create_project(
        patient_label="P",
        reference="",
        birth_date="1965-04-03",
    )
    loaded = store.get_project(project.id)
    assert loaded is not None
    assert loaded.birth_date == "1965-04-03"


def test_create_project_assigns_id_and_dir(store: ProjectStore) -> None:
    project = store.create_project(patient_label="Max Mustermann", reference="AZ-1")
    assert project.id
    assert project.patient_label == "Max Mustermann"
    assert project.reference == "AZ-1"
    assert (store.root / "projects" / project.id).is_dir()


def test_list_projects_orders_by_updated_desc(store: ProjectStore) -> None:
    a = store.create_project(patient_label="A", reference="")
    b = store.create_project(patient_label="B", reference="")
    store.set_notes(a.id, "touch")
    projects = store.list_projects()
    assert [p.id for p in projects] == [a.id, b.id]


def test_add_document_copies_file_and_sets_role(store: ProjectStore, tmp_path: Path) -> None:
    src = tmp_path / "scan.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    project = store.create_project(patient_label="P", reference="")
    doc = store.add_document(
        project_id=project.id,
        source_path=src,
        role=DocumentRole.ANFRAGE,
        display_name="Anfrage.pdf",
    )
    assert doc.role is DocumentRole.ANFRAGE
    assert Path(doc.stored_path).is_file()
    assert Path(doc.stored_path).read_bytes() == b"%PDF-1.4 fake"


def test_only_one_anfrage_per_project(store: ProjectStore, tmp_path: Path) -> None:
    project = store.create_project(patient_label="P", reference="")
    for name in ("a.pdf", "b.pdf"):
        p = tmp_path / name
        p.write_bytes(b"%PDF")
    store.add_document(project.id, tmp_path / "a.pdf", DocumentRole.ANFRAGE, "a.pdf")
    with pytest.raises(ValueError, match="Anfrage"):
        store.add_document(project.id, tmp_path / "b.pdf", DocumentRole.ANFRAGE, "b.pdf")


def test_questions_roundtrip(store: ProjectStore) -> None:
    project = store.create_project(patient_label="P", reference="")
    questions = [
        Question(number=1, text="Besteht Diabetes mellitus?", keyword="Diabetes"),
        Question(number=2, text="Skoliose?", keyword="Skoliose"),
    ]
    store.set_questions(project.id, questions)
    loaded = store.get_questions(project.id)
    assert loaded == questions


def test_draft_html_and_notes(store: ProjectStore) -> None:
    project = store.create_project(patient_label="P", reference="")
    store.set_notes(project.id, "Patient berichtet Belastung.")
    store.set_draft_html(project.id, "<p>Antwort</p>")
    loaded = store.get_project(project.id)
    assert loaded is not None
    assert loaded.notes == "Patient berichtet Belastung."
    assert loaded.draft_html == "<p>Antwort</p>"


def test_save_cost_snapshot(store: ProjectStore) -> None:
    project = store.create_project(patient_label="P", reference="")
    store.save_cost_snapshot(
        project.id,
        page_count=12,
        flat_fee=25.0,
        copy_cost=6.0,
        postage=0.95,
        total=31.95,
    )
    snap = store.get_cost_snapshot(project.id)
    assert snap is not None
    assert snap.total == pytest.approx(31.95)
