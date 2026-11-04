"""Lokales FastAPI-Backend für die GhostWriter Web-/Electron-UI."""

from __future__ import annotations

import contextlib
import shutil
import threading
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ghostwriter import updates
from ghostwriter.costs import calculate_costs
from ghostwriter.extract import ExtractionResult, extract_document_text
from ghostwriter.llm.client import OllamaClient, OllamaError
from ghostwriter.llm.pipeline import ReportPipeline
from ghostwriter.paths import default_data_root
from ghostwriter.settings import load_settings, save_settings
from ghostwriter.store import DocumentRole, ProjectStore, Question
from ghostwriter.updates import set_github_repo

DATA_ROOT = default_data_root()
STORE = ProjectStore(DATA_ROOT)
SETTINGS_PATH = DATA_ROOT / "settings.json"
SETTINGS = load_settings(SETTINGS_PATH)
with contextlib.suppress(ValueError):
    set_github_repo(SETTINGS.github_repo)

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()

app = FastAPI(title="GhostWriter", version=updates.app_version())
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NotesBody(BaseModel):
    notes: str = ""


class QuestionIn(BaseModel):
    number: int
    text: str
    keyword: str = ""


class QuestionsBody(BaseModel):
    questions: list[QuestionIn]


class DraftBody(BaseModel):
    html: str


class CostBody(BaseModel):
    page_count: int = Field(ge=0)
    postage_key: str | None = None
    custom_postage: float | None = None


class SettingsBody(BaseModel):
    ollama_model: str | None = None
    ollama_num_ctx: int | None = None
    flat_fee: float | None = None
    copy_tier_up_to: int | None = None
    copy_tier_price: float | None = None
    after_last_tier_price: float | None = None
    letterhead_html: str | None = None
    signature_html: str | None = None
    github_repo: str | None = None
    postage: dict[str, float] | None = None
    default_postage_key: str | None = None


class CreateProjectBody(BaseModel):
    patient_label: str
    reference: str = ""


def _project_dict(project_id: str) -> dict[str, Any]:
    project = STORE.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    docs = STORE.list_documents(project_id)
    return {
        "id": project.id,
        "patient_label": project.patient_label,
        "reference": project.reference,
        "notes": project.notes,
        "draft_html": project.draft_html,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "questions": [asdict(q) for q in STORE.get_questions(project_id)],
        "documents": [
            {
                "id": d.id,
                "role": d.role.value,
                "display_name": d.display_name,
                "page_count": d.page_count,
                "has_text": bool(d.extracted_text.strip()),
            }
            for d in docs
        ],
        "cost": _cost_dict(project_id),
    }


def _cost_dict(project_id: str) -> dict[str, float | int] | None:
    snap = STORE.get_cost_snapshot(project_id)
    if snap is None:
        return None
    return {
        "page_count": snap.page_count,
        "flat_fee": snap.flat_fee,
        "copy_cost": snap.copy_cost,
        "postage": snap.postage,
        "total": snap.total,
    }


def _ollama_status() -> dict[str, Any]:
    settings = load_settings(SETTINGS_PATH)
    try:
        client = OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            num_ctx=settings.ollama_num_ctx,
        )
        models = client.list_models()
        available = settings.ollama_model in models or any(
            name.startswith(f"{settings.ollama_model}:") for name in models
        )
        return {
            "reachable": True,
            "model": settings.ollama_model,
            "model_available": available,
            "models": models[:20],
        }
    except OllamaError as exc:
        return {
            "reachable": False,
            "model": settings.ollama_model,
            "model_available": False,
            "models": [],
            "error": str(exc),
        }


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "version": updates.app_version(), "ollama": _ollama_status()}


@app.get("/api/projects")
def list_projects() -> list[dict[str, str]]:
    return [
        {
            "id": p.id,
            "patient_label": p.patient_label,
            "reference": p.reference,
            "updated_at": p.updated_at,
        }
        for p in STORE.list_projects()
    ]


@app.post("/api/projects")
def create_project(body: CreateProjectBody) -> dict[str, Any]:
    project = STORE.create_project(
        patient_label=body.patient_label.strip() or "Ohne Name",
        reference=body.reference.strip(),
    )
    return _project_dict(project.id)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    return _project_dict(project_id)


@app.put("/api/projects/{project_id}/notes")
def put_notes(project_id: str, body: NotesBody) -> dict[str, Any]:
    if STORE.get_project(project_id) is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    STORE.set_notes(project_id, body.notes)
    return _project_dict(project_id)


@app.put("/api/projects/{project_id}/questions")
def put_questions(project_id: str, body: QuestionsBody) -> dict[str, Any]:
    if STORE.get_project(project_id) is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    STORE.set_questions(
        project_id,
        [Question(number=q.number, text=q.text, keyword=q.keyword) for q in body.questions],
    )
    return _project_dict(project_id)


@app.put("/api/projects/{project_id}/draft")
def put_draft(project_id: str, body: DraftBody) -> dict[str, Any]:
    if STORE.get_project(project_id) is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    STORE.set_draft_html(project_id, body.html)
    return _project_dict(project_id)


@app.get("/api/projects/{project_id}/documents/{document_id}/file")
def download_document(project_id: str, document_id: str) -> FileResponse:
    if STORE.get_project(project_id) is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    docs = STORE.list_documents(project_id)
    doc = next((d for d in docs if d.id == document_id), None)
    if doc is None:
        raise HTTPException(404, "Dokument nicht gefunden")
    path = Path(doc.stored_path)
    if not path.is_file():
        raise HTTPException(404, "Datei fehlt")
    media = "application/pdf" if path.suffix.lower() == ".pdf" else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=doc.display_name)


@app.post("/api/projects/{project_id}/documents")
async def upload_document(
    project_id: str,
    role: str = Form(...),
    file: UploadFile = File(...),  # noqa: B008
) -> dict[str, Any]:
    if STORE.get_project(project_id) is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    try:
        doc_role = DocumentRole(role)
    except ValueError as exc:
        raise HTTPException(400, "Ungültige Rolle") from exc
    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    tmp = DATA_ROOT / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp / f"{uuid.uuid4().hex}{suffix}"
    with tmp_path.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    try:
        doc = STORE.add_document(
            project_id,
            tmp_path,
            doc_role,
            file.filename or tmp_path.name,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    return _project_dict(project_id) | {"document_id": doc.id}


def _set_job(job_id: str, **kwargs: Any) -> None:
    with _jobs_lock:
        job = _jobs.setdefault(job_id, {"id": job_id, "phase": "queued", "percent": 0, "error": None})
        job.update(kwargs)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job nicht gefunden")
    return dict(job)


@app.post("/api/projects/{project_id}/analyze")
def start_analyze(project_id: str) -> dict[str, str]:
    if STORE.get_project(project_id) is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    job_id = uuid.uuid4().hex
    _set_job(job_id, phase="extracting", percent=5, project_id=project_id)
    thread = threading.Thread(
        target=_run_analyze, args=(job_id, project_id), daemon=True
    )
    thread.start()
    return {"job_id": job_id}


def _run_analyze(job_id: str, project_id: str) -> None:
    try:
        docs = STORE.list_documents(project_id)
        total = max(1, len(docs))
        for index, doc in enumerate(docs):
            _set_job(
                job_id,
                phase="extracting",
                percent=5 + int(35 * index / total),
                message=f"Texterkennung: {doc.display_name}",
            )
            if not doc.extracted_text.strip():
                work = DATA_ROOT / "projects" / project_id / "ocr" / doc.id
                result: ExtractionResult = extract_document_text(
                    Path(doc.stored_path), ocr_work_dir=work
                )
                STORE.update_document_text(doc.id, result.text, result.page_count)

        docs = STORE.list_documents(project_id)
        anfrage = next((d for d in docs if d.role is DocumentRole.ANFRAGE), None)
        if anfrage is None or not anfrage.extracted_text.strip():
            _set_job(job_id, phase="error", error="Keine Anfrage mit Text", percent=100)
            return

        settings = load_settings(SETTINGS_PATH)
        client = OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            num_ctx=settings.ollama_num_ctx,
        )
        _set_job(
            job_id,
            phase="questions",
            percent=42,
            message=f"Ollama-Modell prüfen ({settings.ollama_model}) …",
        )
        client.ensure_model_available()
        pipe = ReportPipeline(client)

        _set_job(job_id, phase="questions", percent=45, message="Fragen extrahieren …")
        questions = STORE.get_questions(project_id)
        if not questions:
            questions = pipe.extract_questions(anfrage.extracted_text)
            STORE.set_questions(project_id, questions)

        findings = [
            d for d in docs if d.role is DocumentRole.BEFUND and d.extracted_text.strip()
        ]
        summaries: list[str] = []
        for index, doc in enumerate(findings):
            _set_job(
                job_id,
                phase="findings",
                percent=55 + int(25 * index / max(1, len(findings))),
                message=f"Befund verdichten: {doc.display_name}",
            )
            summary = pipe.summarize_finding(doc.extracted_text, display_name=doc.display_name)
            summaries.append(summary.summary)

        project = STORE.get_project(project_id)
        assert project is not None
        _set_job(job_id, phase="composing", percent=85, message="Antwortschreiben erzeugen …")
        html = pipe.compose_report(
            questions=questions,
            finding_summaries=summaries,
            notes=project.notes,
            letterhead_html=settings.letterhead_html,
            signature_html=settings.signature_html,
        )
        STORE.set_draft_html(project_id, html)
        _set_job(job_id, phase="done", percent=100, message="Fertig")
    except Exception as exc:
        _set_job(job_id, phase="error", error=_public_job_error(exc), percent=100)


def _public_job_error(exc: BaseException) -> str:
    """Fehlertext fuer die UI - ohne Dokument-/Prompt-Inhalte."""
    if isinstance(exc, OllamaError):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        mapped = OllamaClient._map_status_error(exc, model="?")
        return str(mapped)
    msg = str(exc).strip()
    if not msg:
        return type(exc).__name__
    # Keine langen Rohtexte durchreichen
    if len(msg) > 240:
        return f"{type(exc).__name__}: {msg[:200]}…"
    if type(exc).__name__ == "HTTPStatusError":
        return f"Ollama/HTTP-Fehler: {msg}"
    return f"{type(exc).__name__}: {msg}" if type(exc).__name__ not in msg else msg


@app.post("/api/projects/{project_id}/costs")
def compute_costs(project_id: str, body: CostBody) -> dict[str, Any]:
    if STORE.get_project(project_id) is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    settings = load_settings(SETTINGS_PATH)
    result = calculate_costs(
        page_count=body.page_count,
        settings=settings.to_cost_settings(),
        postage_key=body.postage_key,
        custom_postage=body.custom_postage,
    )
    STORE.save_cost_snapshot(
        project_id,
        page_count=result.page_count,
        flat_fee=result.flat_fee,
        copy_cost=result.copy_cost,
        postage=result.postage,
        total=result.total,
    )
    return {
        "page_count": result.page_count,
        "flat_fee": result.flat_fee,
        "copy_cost": result.copy_cost,
        "postage": result.postage,
        "total": result.total,
    }


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    s = load_settings(SETTINGS_PATH)
    return {
        "ollama_model": s.ollama_model,
        "ollama_num_ctx": s.ollama_num_ctx,
        "flat_fee": s.flat_fee,
        "copy_tier_up_to": s.copy_tier_up_to,
        "copy_tier_price": s.copy_tier_price,
        "after_last_tier_price": s.after_last_tier_price,
        "letterhead_html": s.letterhead_html,
        "signature_html": s.signature_html,
        "github_repo": s.github_repo,
        "postage": s.postage,
        "default_postage_key": s.default_postage_key,
    }


@app.put("/api/settings")
def put_settings(body: SettingsBody) -> dict[str, Any]:
    global SETTINGS
    s = load_settings(SETTINGS_PATH)
    data = body.model_dump(exclude_none=True)
    for key, value in data.items():
        setattr(s, key, value)
    if "github_repo" in data:
        try:
            set_github_repo(s.github_repo)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    save_settings(SETTINGS_PATH, s)
    SETTINGS = s
    return get_settings()


@app.get("/api/updates")
def update_status() -> dict[str, Any]:
    return updates.get_status()


@app.post("/api/updates/check")
def update_check() -> dict[str, Any]:
    return updates.check_for_update()


@app.post("/api/updates/download")
def update_download() -> dict[str, Any]:
    return updates.download_update()


@app.post("/api/updates/install")
def update_install() -> dict[str, Any]:
    return updates.install_update()


def _mount_frontend() -> None:
    dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")


_mount_frontend()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "ghostwriter.server:app",
        host="127.0.0.1",
        port=8787,
        reload=False,
    )


if __name__ == "__main__":
    main()
