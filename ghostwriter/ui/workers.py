"""Hintergrund-Worker für Extraktion und LLM (Hauptthread bleibt frei)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ghostwriter.extract import extract_document_text
from ghostwriter.llm.client import OllamaClient
from ghostwriter.llm.pipeline import FindingSummary, ReportPipeline
from ghostwriter.settings import AppSettings
from ghostwriter.store import Question


class ExtractWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, path: Path, work_dir: Path) -> None:
        super().__init__()
        self._path = path
        self._work_dir = work_dir

    def run(self) -> None:
        try:
            result = extract_document_text(self._path, ocr_work_dir=self._work_dir)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(type(exc).__name__)


class GenerateWorker(QObject):
    finished = Signal(str)
    questions_ready = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        settings: AppSettings,
        anfrage_text: str,
        findings: list[tuple[str, str]],
        notes: str,
        questions: list[Question] | None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._anfrage_text = anfrage_text
        self._findings = findings
        self._notes = notes
        self._questions = questions

    def run(self) -> None:
        try:
            client = OllamaClient(
                base_url=self._settings.ollama_base_url,
                model=self._settings.ollama_model,
                num_ctx=self._settings.ollama_num_ctx,
            )
            pipe = ReportPipeline(client)
            questions = self._questions
            if not questions:
                questions = pipe.extract_questions(self._anfrage_text)
                self.questions_ready.emit(questions)
            summaries: list[FindingSummary] = []
            for name, text in self._findings:
                summaries.append(pipe.summarize_finding(text, display_name=name))
            html = pipe.compose_report(
                questions=questions or [],
                finding_summaries=[s.summary for s in summaries],
                notes=self._notes,
                letterhead_html=self._settings.letterhead_html,
                signature_html=self._settings.signature_html,
                document_place=self._settings.document_place,
            )
            self.finished.emit(html)
        except Exception as exc:
            self.failed.emit(type(exc).__name__)
