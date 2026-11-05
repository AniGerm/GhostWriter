"""Dreistufige Bericht-Pipeline: Fragen → Befunde → Schreiben."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ghostwriter.llm import prompts
from ghostwriter.report_html import (
    restore_ascii_umlauts,
    rewrite_frage_labels,
    strip_heading_brackets,
)
from ghostwriter.signature import apply_signature, strip_trailing_signature
from ghostwriter.store import Question


class JsonChatClient(Protocol):
    def chat_json(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
    ) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class FindingSummary:
    """Verdichteter Befund."""

    summary: str
    source: str


class ReportPipeline:
    """Orchestriert die LLM-Schritte."""

    def __init__(self, client: JsonChatClient) -> None:
        self._client = client

    def extract_questions(self, anfrage_text: str) -> list[Question]:
        data = self._client.chat_json(
            system=prompts.EXTRACT_QUESTIONS_SYSTEM,
            user=anfrage_text,
        )
        raw = data.get("questions", [])
        if not isinstance(raw, list):
            return []
        questions: list[Question] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            number = int(item.get("number", len(questions) + 1))
            text = str(item.get("text", "")).strip()
            keyword = str(item.get("keyword", "")).strip()
            if text:
                questions.append(Question(number=number, text=text, keyword=keyword))
        return questions

    def summarize_finding(self, text: str, *, display_name: str) -> FindingSummary:
        data = self._client.chat_json(
            system=prompts.SUMMARIZE_FINDING_SYSTEM,
            user=f"Dokument: {display_name}\n\n{text}",
        )
        return FindingSummary(
            summary=str(data.get("summary", "")).strip(),
            source=str(data.get("source", display_name)).strip() or display_name,
        )

    def compose_report(
        self,
        *,
        questions: list[Question],
        finding_summaries: list[str],
        notes: str,
        letterhead_html: str = "",
        signature_html: str = "",
        current_html: str = "",
        revision_notes: str = "",
    ) -> str:
        q_lines: list[str] = []
        for q in questions:
            if q.keyword.strip():
                q_lines.append(f"{q.number}. {q.text} (Stichwort: {q.keyword.strip()})")
            else:
                q_lines.append(f"{q.number}. {q.text}")
        q_block = "\n".join(q_lines)
        f_block = "\n---\n".join(finding_summaries) if finding_summaries else "(keine)"
        parts = [
            f"Briefkopf-HTML (optional übernehmen):\n{letterhead_html}",
            "Hauptfragen (Überschrift = Stichwort, darunter nur Stichpunkte, "
            "niemals „Zu Frage N“):\n"
            f"{q_block}",
            f"Befundzusammenfassungen:\n{f_block}",
            f"Hinweise des Arztes:\n{notes or '(keine)'}",
        ]
        if current_html.strip():
            # Fuß (Signatur) nie als editierbaren Entwurf mitschicken - wird danach gesetzt
            draft_body = strip_trailing_signature(current_html.strip())
            parts.append(f"Aktueller Entwurf (HTML):\n{draft_body}")
        if revision_notes.strip():
            parts.append(f"Änderungswünsche / Revision:\n{revision_notes.strip()}")
        parts.append(f"Signatur-HTML:\n{signature_html}")
        user = "\n\n".join(parts)
        data = self._client.chat_json(system=prompts.COMPOSE_REPORT_SYSTEM, user=user)
        html = str(data.get("html", "")).strip()
        html = strip_heading_brackets(html)
        html = rewrite_frage_labels(html)
        html = restore_ascii_umlauts(html)
        # Kopf (Briefkopf) und Fuß (Signatur) immer kanonisch aus Einstellungen
        if letterhead_html.strip():
            head = letterhead_html.strip()
            if html.startswith(head):
                html = html[len(head) :].lstrip()
            elif head in html:
                html = html.replace(head, "", 1).strip()
            html = f"{head}\n{html}" if html else head
        html = apply_signature(html, signature_html)
        return html
