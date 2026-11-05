"""Soft-Delete und Wiederherstellen von Projekten."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ghostwriter.store import ProjectStore


@pytest.fixture()
def store(tmp_path: Path) -> ProjectStore:
    return ProjectStore(root=tmp_path / "data")


def test_soft_delete_hides_from_list_and_restore(store: ProjectStore) -> None:
    project = store.create_project(patient_label="Heinz Mueller2", reference="AZ-1")
    assert store.soft_delete_project(project.id) is True
    assert [p.id for p in store.list_projects()] == []
    # get_project bleibt für Restore/API erreichbar
    loaded = store.get_project(project.id)
    assert loaded is not None
    assert store.restore_project(project.id) is True
    assert [p.id for p in store.list_projects()] == [project.id]
    # Dateien bleiben
    assert (store.root / "projects" / project.id).is_dir()


def test_soft_delete_missing_returns_false(store: ProjectStore) -> None:
    assert store.soft_delete_project("missing") is False
    assert store.restore_project("missing") is False


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    store = ProjectStore(tmp_path / "data")
    import ghostwriter.server as server

    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path / "data")
    monkeypatch.setattr(server, "SETTINGS_PATH", tmp_path / "settings.json")
    return TestClient(server.app)


def test_delete_and_restore_endpoints(api: TestClient) -> None:
    created = api.post(
        "/api/projects", json={"patient_label": "Fall", "reference": "R"}
    ).json()
    pid = created["id"]
    deleted = api.delete(f"/api/projects/{pid}")
    assert deleted.status_code == 200
    assert api.get("/api/projects").json() == []
    restored = api.post(f"/api/projects/{pid}/restore")
    assert restored.status_code == 200
    listed = api.get("/api/projects").json()
    assert len(listed) == 1
    assert listed[0]["id"] == pid
