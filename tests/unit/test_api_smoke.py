"""API-Smoke: Projekte, Health, Job-Fehlerformatierung."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from ghostwriter.llm.client import OllamaError
from ghostwriter.server import _public_job_error
from ghostwriter.store import ProjectStore


@pytest.fixture()
def api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    store = ProjectStore(tmp_path / "data")
    import ghostwriter.server as server

    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path / "data")
    monkeypatch.setattr(server, "SETTINGS_PATH", tmp_path / "settings.json")
    return TestClient(server.app)


def test_create_and_list_projects(api: TestClient) -> None:
    created = api.post(
        "/api/projects", json={"patient_label": "  ", "reference": "AZ-9"}
    ).json()
    assert created["patient_label"] == "Ohne Name"
    assert created["reference"] == "AZ-9"
    listed = api.get("/api/projects").json()
    assert any(p["id"] == created["id"] for p in listed)


def test_public_job_error_prefers_ollama_message() -> None:
    assert "nicht gefunden" in _public_job_error(OllamaError("Modell x nicht gefunden"))
    req = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
    resp = httpx.Response(404, json={"error": "model 'x' not found"}, request=req)
    err = httpx.HTTPStatusError("boom", request=req, response=resp)
    mapped = _public_job_error(err)
    assert "HTTPStatusError" not in mapped or "Ollama" in mapped
    assert "nicht gefunden" in mapped or "404" in mapped or "Ollama" in mapped


def test_health_ollama_unreachable(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ghostwriter.server as server

    class Boom:
        def __init__(self, **k: object) -> None:
            raise OllamaError("Ollama nicht erreichbar")

    monkeypatch.setattr(server, "OllamaClient", Boom)
    # Constructor raises - health should catch OllamaError from list_models path.
    # Adjust: Fake that constructs but list_models raises.
    class Fake:
        def __init__(self, **k: object) -> None:
            pass

        def list_models(self) -> list[str]:
            raise OllamaError("Ollama nicht erreichbar unter http://127.0.0.1:11434 - bitte starten.")

    monkeypatch.setattr(server, "OllamaClient", Fake)
    body = api.get("/api/health").json()
    assert body["ok"] is True
    assert body["ollama"]["reachable"] is False
    assert "nicht erreichbar" in body["ollama"]["error"]


def test_notes_and_draft_roundtrip(api: TestClient) -> None:
    project = api.post("/api/projects", json={"patient_label": "B", "reference": ""}).json()
    pid = project["id"]
    notes = api.put(f"/api/projects/{pid}/notes", json={"notes": "Hinweis"}).json()
    assert notes["notes"] == "Hinweis"
    draft = api.put(f"/api/projects/{pid}/draft", json={"html": "<p>Text</p>"}).json()
    assert draft["draft_html"] == "<p>Text</p>"


def test_costs_and_missing_job(api: TestClient) -> None:
    project = api.post("/api/projects", json={"patient_label": "C", "reference": ""}).json()
    pid = project["id"]
    costs = api.post(
        f"/api/projects/{pid}/costs",
        json={"page_count": 3, "postage_key": "standard"},
    ).json()
    assert costs["page_count"] == 3
    assert costs["total"] > 0
    assert api.get("/api/jobs/does-not-exist").status_code == 404
    assert api.get("/api/projects/missing").status_code == 404


def test_analyze_rejects_missing_model_before_pipeline(
    api: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ghostwriter.server as server

    project = api.post("/api/projects", json={"patient_label": "D", "reference": ""}).json()
    pid = project["id"]
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    with pdf.open("rb") as handle:
        api.post(
            f"/api/projects/{pid}/documents",
            data={"role": "anfrage"},
            files={"file": ("a.pdf", handle, "application/pdf")},
        )
    docs = server.STORE.list_documents(pid)
    server.STORE.update_document_text(docs[0].id, "1. Frage?", 1)

    class FakeClient:
        def __init__(self, **k: object) -> None:
            pass

        def ensure_model_available(self) -> None:
            raise OllamaError("Ollama-Modell 'nope' nicht gefunden. Installiert: qwen3:14b-q8_0")

    monkeypatch.setattr(server, "OllamaClient", FakeClient)
    job_id = "job-ensure"
    server._set_job(job_id, phase="queued", percent=0, project_id=pid)
    server._run_analyze(job_id, pid)
    job = api.get(f"/api/jobs/{job_id}").json()
    assert job["phase"] == "error"
    assert "nicht gefunden" in job["error"]
