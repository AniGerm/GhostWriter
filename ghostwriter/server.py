"""Lokales FastAPI-Backend für die GhostWriter Web-/Electron-UI."""

from __future__ import annotations

import contextlib
import os
import shutil
import threading
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ghostwriter import updates
from ghostwriter.costs import calculate_costs
from ghostwriter.extract import ExtractionResult, extract_document_text
from ghostwriter.inbox import (
    list_new_spool_pdfs,
    mark_all_spool_pdfs_processed,
    mark_processed,
)
from ghostwriter.llm.client import OllamaClient, OllamaError, is_allowed_ollama_host
from ghostwriter.llm.pipeline import ReportPipeline
from ghostwriter.paths import default_data_root, default_spool_dir
from ghostwriter.preview import (
    document_page_count,
    page_preview_path,
    preview_cache_dir,
)
from ghostwriter.printers import list_cups_printers
from ghostwriter.settings import load_settings, save_settings
from ghostwriter.store import Document, DocumentRole, ProjectStore, Question
from ghostwriter.updates import set_github_repo

DATA_ROOT = default_data_root()


def ensure_writable_cwd() -> Path:
    """Wechselt aus unbeschreibbaren cwd (z. B. /root nach pkexec) heraus."""
    current = Path.cwd()
    if os.access(current, os.W_OK | os.X_OK):
        return current
    for candidate in (Path.home(), DATA_ROOT, Path("/tmp")):
        if candidate.is_dir() and os.access(candidate, os.W_OK | os.X_OK):
            os.chdir(candidate)
            return candidate
    return current


ensure_writable_cwd()
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


class RegenerateBody(BaseModel):
    revision_notes: str = ""


class CostBody(BaseModel):
    page_count: int = Field(ge=0)
    postage_key: str | None = None
    custom_postage: float | None = None


class SettingsBody(BaseModel):
    ollama_base_url: str | None = None
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
    default_printer: str | None = None
    default_font_size: int | None = Field(default=None, ge=8, le=28)
    heading_font_size: int | None = Field(default=None, ge=8, le=28)
    document_place: str | None = None


class CreateProjectBody(BaseModel):
    patient_label: str
    reference: str = ""
    birth_date: str = ""


class DocumentPatchBody(BaseModel):
    included: bool


def included_finding_documents(docs: list[Document]) -> list[Document]:
    """Befunde, die in Analyse/Regenerate einfließen sollen."""
    return [
        d
        for d in docs
        if d.role is DocumentRole.BEFUND and d.included and d.extracted_text.strip()
    ]


def _dismiss_spool_leftovers() -> None:
    """Markiert aktuelle Spool-PDFs als gesehen, damit ein neues Projekt leer startet."""
    settings = load_settings(SETTINGS_PATH)
    spool = Path(settings.spool_dir) if settings.spool_dir else default_spool_dir()
    state_path = DATA_ROOT / "inbox_state.json"
    mark_all_spool_pdfs_processed(spool, state_path=state_path)


def _project_dict(project_id: str) -> dict[str, Any]:
    project = STORE.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    docs = STORE.list_documents(project_id)
    return {
        "id": project.id,
        "patient_label": project.patient_label,
        "reference": project.reference,
        "birth_date": project.birth_date,
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
                "included": d.included,
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


def _cups_scheduler_running() -> bool:
    import subprocess

    try:
        proc = subprocess.run(
            ["lpstat", "-r"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        text = f"{proc.stdout} {proc.stderr}".lower()
        return "running" in text or "läuft" in text
    except Exception:
        return False


@app.get("/api/inbox/status")
def inbox_status() -> dict[str, Any]:
    """Diagnose: CUPS-Spool erreichbar? Neue PDFs?"""
    settings = load_settings(SETTINGS_PATH)
    spool = Path(settings.spool_dir) if settings.spool_dir else default_spool_dir()
    state_path = DATA_ROOT / "inbox_state.json"
    result: dict[str, Any] = {
        "spool_dir": str(spool),
        "spool_exists": spool.exists(),
        "spool_is_dir": spool.is_dir(),
        "readable": False,
        "list_error": None,
        "entry_count": 0,
        "pdf_count": 0,
        "new_pdf_count": 0,
        "sample_names": [],
        "owner_hint": None,
        "mode_hint": None,
        "cups_running": _cups_scheduler_running(),
    }
    try:
        st = spool.stat()
        result["mode_hint"] = oct(st.st_mode & 0o777)
        result["owner_hint"] = f"uid={st.st_uid}"
    except OSError as exc:
        result["list_error"] = f"stat: {exc}"
        return result
    try:
        entries = list(spool.iterdir())
        result["readable"] = True
        result["entry_count"] = len(entries)
        pdfs = [p for p in entries if p.is_file() and p.suffix.lower() == ".pdf"]
        result["pdf_count"] = len(pdfs)
        result["sample_names"] = [p.name[:80] for p in sorted(pdfs)[-5:]]
        new_pdfs = list_new_spool_pdfs(spool, state_path=state_path)
        result["new_pdf_count"] = len(new_pdfs)
    except OSError as exc:
        result["list_error"] = f"listdir: {type(exc).__name__}: {exc}"
        result["readable"] = False
    return result


class InboxImportBody(BaseModel):
    role: str = "befund"


@app.post("/api/projects/{project_id}/inbox/import")
def import_inbox(project_id: str, body: InboxImportBody | None = None) -> dict[str, Any]:
    """Übernimmt neue Spool-PDFs in das aktuelle Projekt."""
    if STORE.get_project(project_id) is None or not STORE.is_project_active(project_id):
        raise HTTPException(404, "Projekt nicht gefunden")
    role_raw = (body.role if body else "befund") or "befund"
    try:
        doc_role = DocumentRole(role_raw)
    except ValueError as exc:
        raise HTTPException(400, "Ungültige Rolle") from exc
    settings = load_settings(SETTINGS_PATH)
    spool = Path(settings.spool_dir) if settings.spool_dir else default_spool_dir()
    state_path = DATA_ROOT / "inbox_state.json"
    imported: list[dict[str, str]] = []
    errors: list[str] = []
    try:
        new_pdfs = list_new_spool_pdfs(spool, state_path=state_path)
    except OSError as exc:
        raise HTTPException(503, "Spool nicht lesbar - Drucker-Spool-Rechte prüfen") from exc
    for pdf in new_pdfs:
        try:
            doc = STORE.add_document(project_id, pdf, doc_role, pdf.name)
            mark_processed(pdf, state_path=state_path)
            imported.append({"id": doc.id, "display_name": doc.display_name})
        except Exception as exc:
            errors.append(type(exc).__name__)
    return {
        "imported": imported,
        "errors": errors,
        "project": _project_dict(project_id),
    }


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
    _dismiss_spool_leftovers()
    project = STORE.create_project(
        patient_label=body.patient_label.strip() or "Ohne Name",
        reference=body.reference.strip(),
        birth_date=body.birth_date.strip(),
    )
    return _project_dict(project.id)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    if not STORE.is_project_active(project_id):
        raise HTTPException(404, "Projekt nicht gefunden")
    return _project_dict(project_id)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, bool]:
    if not STORE.soft_delete_project(project_id):
        raise HTTPException(404, "Projekt nicht gefunden")
    return {"ok": True}


@app.post("/api/projects/{project_id}/restore")
def restore_project(project_id: str) -> dict[str, Any]:
    if not STORE.restore_project(project_id):
        raise HTTPException(404, "Projekt nicht gefunden")
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


@app.patch("/api/projects/{project_id}/documents/{document_id}")
def patch_document(
    project_id: str, document_id: str, body: DocumentPatchBody
) -> dict[str, Any]:
    if STORE.get_project(project_id) is None or not STORE.is_project_active(project_id):
        raise HTTPException(404, "Projekt nicht gefunden")
    docs = STORE.list_documents(project_id)
    if not any(d.id == document_id for d in docs):
        raise HTTPException(404, "Dokument nicht gefunden")
    try:
        STORE.set_document_included(document_id, body.included)
    except KeyError as exc:
        raise HTTPException(404, "Dokument nicht gefunden") from exc
    return _project_dict(project_id)


@app.delete("/api/projects/{project_id}/documents/{document_id}")
def delete_document(project_id: str, document_id: str) -> dict[str, Any]:
    if STORE.get_project(project_id) is None or not STORE.is_project_active(project_id):
        raise HTTPException(404, "Projekt nicht gefunden")
    if not STORE.delete_document(project_id, document_id):
        raise HTTPException(404, "Dokument nicht gefunden")
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
    return FileResponse(
        path,
        media_type=media,
        filename=doc.display_name,
        content_disposition_type="inline",
    )


@app.get("/api/projects/{project_id}/documents/{document_id}/preview")
def document_preview_meta(project_id: str, document_id: str) -> dict[str, Any]:
    """Seitenzahl für den internen Dokument-Viewer."""
    if STORE.get_project(project_id) is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    docs = STORE.list_documents(project_id)
    doc = next((d for d in docs if d.id == document_id), None)
    if doc is None:
        raise HTTPException(404, "Dokument nicht gefunden")
    path = Path(doc.stored_path)
    if not path.is_file():
        raise HTTPException(404, "Datei fehlt")
    try:
        page_count = document_page_count(path)
    except ValueError as exc:
        raise HTTPException(400, "Vorschau nicht möglich") from exc
    except Exception as exc:
        raise HTTPException(500, "Vorschau fehlgeschlagen") from exc
    return {"page_count": page_count, "display_name": doc.display_name}


@app.get("/api/projects/{project_id}/documents/{document_id}/pages/{page_number}")
def document_page_preview(project_id: str, document_id: str, page_number: int) -> FileResponse:
    """Gerenderte A4-Seite als PNG für die Druckvorschau."""
    if STORE.get_project(project_id) is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    docs = STORE.list_documents(project_id)
    doc = next((d for d in docs if d.id == document_id), None)
    if doc is None:
        raise HTTPException(404, "Dokument nicht gefunden")
    path = Path(doc.stored_path)
    if not path.is_file():
        raise HTTPException(404, "Datei fehlt")
    try:
        png = page_preview_path(path, preview_cache_dir(DATA_ROOT, document_id), page_number)
    except ValueError as exc:
        raise HTTPException(400, "Vorschau nicht möglich") from exc
    except Exception as exc:
        raise HTTPException(500, "Seitenvorschau fehlgeschlagen") from exc
    if png is None or not png.is_file():
        raise HTTPException(404, "Seite nicht gefunden")
    return FileResponse(
        png,
        media_type="image/png",
        filename=f"page-{page_number}.png",
        headers={"Cache-Control": "private, max-age=86400"},
    )


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


@app.post("/api/projects/{project_id}/regenerate")
def start_regenerate(project_id: str, body: RegenerateBody) -> dict[str, str]:
    """Antwortschreiben mit optionalen Änderungswünschen neu erzeugen."""
    if STORE.get_project(project_id) is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    job_id = uuid.uuid4().hex
    _set_job(job_id, phase="composing", percent=10, project_id=project_id)
    notes = body.revision_notes or ""
    thread = threading.Thread(
        target=_run_regenerate, args=(job_id, project_id, notes), daemon=True
    )
    thread.start()
    return {"job_id": job_id}


def _run_analyze(job_id: str, project_id: str) -> None:
    try:
        docs = STORE.list_documents(project_id)
        to_extract = [d for d in docs if d.included]
        total = max(1, len(to_extract))
        for index, doc in enumerate(to_extract):
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
        anfrage = next(
            (d for d in docs if d.role is DocumentRole.ANFRAGE and d.included),
            None,
        )
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

        findings = included_finding_documents(docs)
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
            patient_label=project.patient_label,
            birth_date=project.birth_date,
            source_texts=[anfrage.extracted_text, *[d.extracted_text for d in findings]],
            document_place=settings.document_place,
        )
        STORE.set_draft_html(project_id, html)
        _set_job(job_id, phase="done", percent=100, message="Fertig")
    except Exception as exc:
        _set_job(job_id, phase="error", error=_public_job_error(exc), percent=100)


def _run_regenerate(job_id: str, project_id: str, revision_notes: str) -> None:
    try:
        project = STORE.get_project(project_id)
        if project is None:
            _set_job(job_id, phase="error", error="Projekt nicht gefunden", percent=100)
            return
        questions = STORE.get_questions(project_id)
        if not questions:
            _set_job(job_id, phase="error", error="Keine Fragen vorhanden", percent=100)
            return
        settings = load_settings(SETTINGS_PATH)
        client = OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            num_ctx=settings.ollama_num_ctx,
        )
        _set_job(job_id, phase="composing", percent=20, message="Ollama-Modell prüfen …")
        client.ensure_model_available()
        pipe = ReportPipeline(client)
        docs = STORE.list_documents(project_id)
        findings = included_finding_documents(docs)
        summaries: list[str] = []
        for index, doc in enumerate(findings):
            _set_job(
                job_id,
                phase="findings",
                percent=25 + int(40 * index / max(1, len(findings))),
                message=f"Befund verdichten: {doc.display_name}",
            )
            summary = pipe.summarize_finding(doc.extracted_text, display_name=doc.display_name)
            summaries.append(summary.summary)
        _set_job(job_id, phase="composing", percent=80, message="Schreiben überarbeiten …")
        anfrage = next(
            (d for d in docs if d.role is DocumentRole.ANFRAGE and d.included),
            None,
        )
        source_texts = [d.extracted_text for d in findings]
        if anfrage is not None and anfrage.extracted_text.strip():
            source_texts.insert(0, anfrage.extracted_text)
        html = pipe.compose_report(
            questions=questions,
            finding_summaries=summaries,
            notes=project.notes,
            letterhead_html=settings.letterhead_html,
            signature_html=settings.signature_html,
            current_html=project.draft_html,
            revision_notes=revision_notes,
            patient_label=project.patient_label,
            birth_date=project.birth_date,
            source_texts=source_texts,
            document_place=settings.document_place,
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
    if isinstance(exc, ModuleNotFoundError):
        missing = str(getattr(exc, "name", "") or exc).lower()
        if "paddleocr" in missing or "paddle" in missing:
            return (
                "PaddleOCR fehlt in der GhostWriter-Installation. "
                "Scans brauchen den OCR-Stack im App-venv unter /opt/ghostwriter."
            )
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
        "ollama_base_url": s.ollama_base_url,
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
        "default_printer": s.default_printer,
        "default_font_size": s.default_font_size,
        "heading_font_size": s.heading_font_size,
        "document_place": s.document_place,
    }


@app.put("/api/settings")
def put_settings(body: SettingsBody) -> dict[str, Any]:
    global SETTINGS
    s = load_settings(SETTINGS_PATH)
    data = body.model_dump(exclude_none=True)
    if "ollama_base_url" in data:
        host = (urlparse(str(data["ollama_base_url"])).hostname or "").lower()
        if not is_allowed_ollama_host(host):
            raise HTTPException(
                400,
                "Ollama-URL nur lokal oder privates LAN "
                "(127.0.0.1/localhost/192.168.x/10.x/*.local)",
            )
        try:
            OllamaClient(base_url=str(data["ollama_base_url"]))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
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


@app.get("/api/printers")
def get_printers() -> dict[str, Any]:
    printers = list_cups_printers()
    settings = load_settings(SETTINGS_PATH)
    return {
        "printers": [{"name": p.name, "is_default": p.is_default} for p in printers],
        "default_printer": settings.default_printer,
        "system_default": next((p.name for p in printers if p.is_default), ""),
    }


@app.get("/api/ollama/models")
def get_ollama_models(base_url: str | None = None) -> dict[str, Any]:
    settings = load_settings(SETTINGS_PATH)
    url = (base_url or settings.ollama_base_url).strip()
    host = (urlparse(url).hostname or "").lower()
    if not is_allowed_ollama_host(host):
        raise HTTPException(
            400,
            "Ollama-URL nur lokal oder privates LAN "
            "(127.0.0.1/localhost/192.168.x/10.x/*.local)",
        )
    try:
        client = OllamaClient(base_url=url, model=settings.ollama_model)
        models = client.list_models()
    except (OllamaError, ValueError) as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"base_url": url.rstrip("/"), "models": models}


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


FRONTEND_DIST_CANDIDATES: tuple[Path, ...] = (
    Path("/opt/ghostwriter/frontend/dist"),
    Path(__file__).resolve().parents[1] / "frontend" / "dist",
    Path(__file__).resolve().parents[2] / "frontend" / "dist",
)


def resolve_frontend_dist() -> Path | None:
    """Findet das gebaute React-Frontend (Repo oder Deb-Installation)."""
    for candidate in FRONTEND_DIST_CANDIDATES:
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return None


def _mount_frontend() -> None:
    dist = resolve_frontend_dist()
    if dist is not None:
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")


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
