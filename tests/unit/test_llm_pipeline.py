"""Tests for the Ollama LLM pipeline with a fake client."""

from __future__ import annotations

from typing import Any

from ghostwriter.llm.pipeline import ReportPipeline
from ghostwriter.store import Question


class FakeOllama:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append({"system": system, "user": user, "model": model})
        n = len(self.calls)
        if n == 1:
            return {
                "questions": [
                    {
                        "number": 1,
                        "text": "Besteht Diabetes mellitus?",
                        "keyword": "Diabetes",
                    }
                ]
            }
        if n == 2:
            return {
                "summary": "Diabetes mellitus Typ 2, HbA1c 7,2 % (2024).",
                "source": "Befund Endokrinologie",
            }
        return {
            "html": (
                "<h1>Ärztlicher Bericht</h1>"
                "<h2>1. Diabetes</h2>"
                "<p>Nach vorliegendem Befund besteht Diabetes mellitus Typ 2.</p>"
            )
        }


def test_extract_questions() -> None:
    client = FakeOllama()
    pipe = ReportPipeline(client=client)  # type: ignore[arg-type]
    questions = pipe.extract_questions("Anfrage: Besteht Diabetes mellitus?")
    assert questions == [Question(number=1, text="Besteht Diabetes mellitus?", keyword="Diabetes")]


def test_summarize_finding() -> None:
    client = FakeOllama()
    # burn first call pattern by calling summarize directly after priming
    pipe = ReportPipeline(client=client)  # type: ignore[arg-type]
    # Force summarize path: fake returns questions on first call — adjust fake
    client.calls.clear()

    class FindingFake(FakeOllama):
        def chat_json(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {
                "summary": "Paresen der unteren Extremität.",
                "source": "Neurologie",
            }

    fake = FindingFake()
    pipe = ReportPipeline(client=fake)  # type: ignore[arg-type]
    summary = pipe.summarize_finding("Befundtext mit Paresen", display_name="Neuro.pdf")
    assert "Paresen" in summary.summary
    assert summary.source == "Neurologie"


def test_compose_report_html() -> None:
    class ComposeFake(FakeOllama):
        def chat_json(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {"html": "<p>Strukturierte Antwort</p>"}

    fake = ComposeFake()
    pipe = ReportPipeline(client=fake)  # type: ignore[arg-type]
    html = pipe.compose_report(
        questions=[Question(1, "Diabetes?", "Diabetes")],
        finding_summaries=["Diabetes Typ 2"],
        notes="Patient unter Metformin.",
        letterhead_html="<p>Praxis</p>",
        signature_html="<p>Gruß</p>",
    )
    assert "Strukturierte Antwort" in html
    assert fake.calls
    payload = fake.calls[0]["user"]
    assert "Diabetes" in payload
    assert "Metformin" in payload


def test_compose_report_does_not_duplicate_signature() -> None:
    class ComposeFake(FakeOllama):
        def chat_json(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {
                "html": (
                    "<p>Antworttext</p>"
                    "<p>Mit freundlichen Grüßen</p>"
                    "<p>Dr. Alt</p>"
                )
            }

    fake = ComposeFake()
    pipe = ReportPipeline(client=fake)  # type: ignore[arg-type]
    html = pipe.compose_report(
        questions=[Question(1, "Diabetes?", "Diabetes")],
        finding_summaries=["Diabetes Typ 2"],
        notes="",
        signature_html="<p>Mit freundlichen Grüßen</p><p>Dr. Neu</p>",
    )
    assert html.count("Mit freundlichen Grüßen") == 1
    assert "Dr. Neu" in html
    assert "Dr. Alt" not in html
    assert html.rstrip().endswith("</p>")


def test_compose_report_includes_revision_context() -> None:
    class ComposeFake(FakeOllama):
        def chat_json(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {"html": "<p>Überarbeitet</p>"}

    fake = ComposeFake()
    pipe = ReportPipeline(client=fake)  # type: ignore[arg-type]
    html = pipe.compose_report(
        questions=[Question(1, "Diabetes?", "Diabetes")],
        finding_summaries=["Diabetes Typ 2"],
        notes="",
        current_html="<p>Alter Entwurf Punkt 6</p>",
        revision_notes="Stil kürzer; neue Grußformel übernehmen",
        signature_html="<p>Mit freundlichen Grüßen</p><p>Dr. Test</p>",
    )
    assert "Überarbeitet" in html
    payload = fake.calls[0]["user"]
    assert "Alter Entwurf Punkt 6" in payload
    assert "Stil kürzer" in payload
    assert "Dr. Test" in payload
    assert "Änderungswünsche" in payload or "Revision" in payload


def test_compose_report_strips_signature_from_current_draft() -> None:
    """Beim Neu-Erzeugen soll die KI keinen alten Fuß im Entwurf sehen."""

    class ComposeFake(FakeOllama):
        def chat_json(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {"html": "<p>Frisch</p>"}

    fake = ComposeFake()
    pipe = ReportPipeline(client=fake)  # type: ignore[arg-type]
    pipe.compose_report(
        questions=[Question(1, "Diabetes?", "Diabetes")],
        finding_summaries=["Diabetes Typ 2"],
        notes="",
        current_html=(
            "<p>Alter Text</p>"
            "<p>Mit freundlichen Grüßen</p>"
            "<p>Dr. Alt</p>"
        ),
        revision_notes="kürzer",
        letterhead_html="<p>Praxis Kopf</p>",
        signature_html="<p>Mit freundlichen Grüßen</p><p>Dr. Neu</p>",
    )
    payload = fake.calls[0]["user"]
    assert "Alter Text" in payload
    assert "Dr. Alt" not in payload
    assert "Mit freundlichen Grüßen" not in payload.split("Signatur-HTML:")[0]
    assert "Praxis Kopf" in payload


def test_compose_report_keeps_letterhead_and_signature() -> None:
    class ComposeFake(FakeOllama):
        def chat_json(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {"html": "<p>Nur Körper</p><p>Mit freundlichen Grüßen</p><p>Dr. Alt</p>"}

    fake = ComposeFake()
    pipe = ReportPipeline(client=fake)  # type: ignore[arg-type]
    html = pipe.compose_report(
        questions=[Question(1, "Diabetes?", "Diabetes")],
        finding_summaries=["Diabetes Typ 2"],
        notes="",
        letterhead_html="<p>Praxis Kopf</p>",
        signature_html="<p>Mit freundlichen Grüßen</p><p>Dr. Neu</p>",
    )
    assert html.startswith("<p>Praxis Kopf</p>")
    assert "Nur Körper" in html
    assert html.count("Mit freundlichen Grüßen") == 1
    assert "Dr. Neu" in html
    assert "Dr. Alt" not in html
