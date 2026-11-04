"""API-Analyse: Job-Fehler müssen nutzbar sein (kein bloßes HTTPStatusError)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ghostwriter.llm.client import OllamaError
from ghostwriter.store import DocumentRole, ProjectStore


@pytest.fixture()
def api_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, ProjectStore]:
    store = ProjectStore(tmp_path / "data")
    import ghostwriter.server as server

    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path / "data")
    monkeypatch.setattr(server, "SETTINGS_PATH", tmp_path / "settings.json")
    return TestClient(server.app), store


def test_analyze_job_surfaces_ollama_model_error(
    api_env: tuple[TestClient, ProjectStore],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ghostwriter.server as server

    client, store = api_env
    created = client.post("/api/projects", json={"patient_label": "Fall A", "reference": ""}).json()
    project_id = created["id"]
    pdf = tmp_path / "anfrage.pdf"
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    with pdf.open("rb") as handle:
        up = client.post(
            f"/api/projects/{project_id}/documents",
            data={"role": DocumentRole.ANFRAGE.value},
            files={"file": ("anfrage.pdf", handle, "application/pdf")},
        )
    assert up.status_code == 200

    docs = store.list_documents(project_id)
    assert docs
    store.update_document_text(docs[0].id, "1. Frage zur Belastbarkeit?", 1)

    class FakeClient:
        def __init__(self, **_k: object) -> None:
            pass

        def ensure_model_available(self) -> None:
            return None

    class FakePipe:
        def __init__(self, *_a: object, **_k: object) -> None:
            pass

        def extract_questions(self, *_a: object, **_k: object) -> list[object]:
            raise OllamaError("Ollama-Modell 'qwen2.5:14b' nicht gefunden")

    monkeypatch.setattr(server, "OllamaClient", FakeClient)
    monkeypatch.setattr(server, "ReportPipeline", FakePipe)

    job_id = "jobtest1"
    server._set_job(job_id, phase="queued", percent=0, project_id=project_id)
    server._run_analyze(job_id, project_id)
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["phase"] == "error"
    assert "HTTPStatusError" not in (job.get("error") or "")
    assert "qwen2.5:14b" in (job.get("error") or "")
    assert "nicht gefunden" in (job.get("error") or "")


def test_health_reports_ollama_model_status(
    api_env: tuple[TestClient, ProjectStore], monkeypatch: pytest.MonkeyPatch
) -> None:
    import ghostwriter.server as server

    client, _store = api_env
    monkeypatch.setattr(
        server,
        "load_settings",
        lambda _p: type(
            "S",
            (),
            {
                "ollama_base_url": "http://127.0.0.1:11434",
                "ollama_model": "missing:model",
                "ollama_num_ctx": 1024,
            },
        )(),
    )

    class FakeClient:
        def __init__(self, **k: object) -> None:
            pass

        def list_models(self) -> list[str]:
            return ["qwen3:14b-q8_0"]

    monkeypatch.setattr(server, "OllamaClient", FakeClient)
    health = client.get("/api/health").json()
    assert health["ok"] is True
    assert health["ollama"]["reachable"] is True
    assert health["ollama"]["model"] == "missing:model"
    assert health["ollama"]["model_available"] is False
