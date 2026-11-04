"""ProjectStore must tolerate FastAPI worker threads."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ghostwriter.store import ProjectStore


def test_create_and_list_from_worker_threads(tmp_path: Path) -> None:
    store = ProjectStore(root=tmp_path / "data")

    def work(index: int) -> str:
        project = store.create_project(patient_label=f"P{index}", reference="")
        listed = store.list_projects()
        assert any(p.id == project.id for p in listed)
        return project.id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(work, range(24)))

    assert len(ids) == 24
    assert len(store.list_projects()) == 24
