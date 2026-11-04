"""API: Antwortschreiben mit Anmerkungen neu erzeugen."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ghostwriter.store import ProjectStore, Question


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    store = ProjectStore(tmp_path / "data")
    import ghostwriter.server as server

    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path / "data")
    monkeypatch.setattr(server, "SETTINGS_PATH", tmp_path / "settings.json")
    return TestClient(server.app)


def test_regenerate_runs_compose_with_revision_notes(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ghostwriter.server as server

    project = api.post(
        "/api/projects", json={"patient_label": "Heinz Müller2", "reference": ""}
    ).json()
    pid = project["id"]
    server.STORE.set_questions(
        pid, [Question(number=1, text="Belastbarkeit?", keyword="Belastbarkeit")]
    )
    server.STORE.set_draft_html(pid, "<p>Alter Entwurf</p>")
    server.STORE.set_notes(pid, "Stammhinweis")

    src = Path(server.DATA_ROOT) / "upload.pdf"
    src.write_bytes(b"%PDF-1.4\n%%EOF\n")
    doc = server.STORE.add_document(
        pid, src, server.DocumentRole.BEFUND, "befund.pdf"
    )
    server.STORE.update_document_text(doc.id, "Befundtext belastbar eingeschraenkt.", 1)

    captured: dict[str, object] = {}

    class FakePipe:
        def __init__(self, client: object) -> None:
            pass

        def summarize_finding(self, text: str, *, display_name: str) -> object:
            return type("S", (), {"summary": "Kurzbefund", "source": display_name})()

        def compose_report(self, **kwargs: object) -> str:
            captured.update(kwargs)
            return "<p>Neuer Entwurf</p>"

    class FakeClient:
        def __init__(self, **k: object) -> None:
            pass

        def ensure_model_available(self) -> None:
            return None

    monkeypatch.setattr(server, "ReportPipeline", FakePipe)
    monkeypatch.setattr(server, "OllamaClient", FakeClient)

    def immediate_thread(*, target: object, args: tuple[object, ...] = (), **kwargs: object) -> object:
        class _T:
            def start(self) -> None:
                assert callable(target)
                target(*args)

        return _T()

    monkeypatch.setattr(server.threading, "Thread", immediate_thread)

    started = api.post(
        f"/api/projects/{pid}/regenerate",
        json={"revision_notes": "Punkt 7 ergaenzen; Grussformel anpassen"},
    )
    assert started.status_code == 200
    job_id = started.json()["job_id"]
    job = api.get(f"/api/jobs/{job_id}").json()
    assert job["phase"] == "done"
    assert captured.get("revision_notes") == "Punkt 7 ergaenzen; Grussformel anpassen"
    assert captured.get("current_html") == "<p>Alter Entwurf</p>"
    assert "Stammhinweis" in str(captured.get("notes", ""))
    fresh = api.get(f"/api/projects/{pid}").json()
    assert fresh["draft_html"] == "<p>Neuer Entwurf</p>"
