"""HTML-Nachbearbeitung für Berichtsentwürfe."""

from __future__ import annotations

from datetime import date

from ghostwriter.report_html import (
    ensure_reply_intro,
    extract_patient_identity,
    resolve_reply_identity,
    restore_ascii_umlauts,
    rewrite_frage_labels,
    strip_heading_brackets,
)


def test_strip_heading_brackets_from_h2() -> None:
    html = "<h2>12. [Hilfsmittel]</h2><p>Text</p>"
    assert strip_heading_brackets(html) == "<h2>12. Hilfsmittel</h2><p>Text</p>"


def test_strip_heading_brackets_keeps_body_brackets() -> None:
    html = "<h2>1. [Diabetes]</h2><p>Siehe [Befund A] im Anhang.</p>"
    out = strip_heading_brackets(html)
    assert "<h2>1. Diabetes</h2>" in out
    assert "[Befund A]" in out


def test_strip_heading_brackets_h1_and_nested() -> None:
    html = "<h1>[Ärztlicher Bericht]</h1><h2>3. [Operationen]</h2>"
    out = strip_heading_brackets(html)
    assert "<h1>Ärztlicher Bericht</h1>" in out
    assert "<h2>3. Operationen</h2>" in out


def test_reply_intro_uses_name_and_german_birth_date() -> None:
    html = ensure_reply_intro(
        "<h2>Hilfsmittel</h2><ul><li>Rollator.</li></ul>",
        "Erika Muster",
        "1970-02-01",
        letterhead_html="<p>Praxis</p>",
        subjects=["Wirbelsäule", "Diabetes mellitus"],
        place="Musterstadt",
        issued_on=date(2026, 11, 5),
    )
    assert html.startswith("<p>Praxis</p>")
    assert ">Ärztlicher Befundbericht<" in html
    assert ">Stellungnahme<" not in html
    assert "font-size:14pt" in html
    assert "font-weight:700" in html
    assert "text-decoration:underline" in html
    assert 'class="gw-reply-place"' in html
    assert "text-align:right" in html
    assert "Musterstadt" in html
    assert "05.11.2026" in html
    assert "Grades der Behinderung" in html
    assert "Erika Muster, geb.: 01.02.1970" in html
    assert "Wirbelsäule" not in html
    assert "Das Amtsschreiben betrifft" not in html
    assert html.index("gw-reply-lead") < html.index("<h2>Hilfsmittel</h2>")


def test_reply_intro_replaces_previous_block() -> None:
    once = ensure_reply_intro(
        "<p>Text</p>",
        "A",
        "2000-01-02",
        place="Köln",
        issued_on=date(2026, 11, 5),
    )
    twice = ensure_reply_intro(once, "B", "", place="Bonn", issued_on=date(2026, 11, 5))
    assert twice.count("gw-reply-title") == 1
    assert twice.count("gw-reply-place") == 1
    assert "für B." in twice
    assert "geboren" not in twice
    assert "Bonn" in twice
    assert "Köln" not in twice


def test_reply_intro_replaces_legacy_title() -> None:
    old = (
        '<h3 class="gw-reply-title">Stellungnahme</h3><p class="gw-reply-lead">Alt.</p><p>Text</p>'
    )
    html = ensure_reply_intro(old, "B", "", place="Köln", issued_on=date(2026, 11, 5))
    assert html.count("gw-reply-title") == 1
    assert "Ärztlicher Befundbericht" in html
    assert ">Stellungnahme<" not in html
    assert "Köln" in html
    assert html.endswith("<p>Text</p>")


def test_extract_patient_identity_from_letter() -> None:
    text = (
        "Betrifft: Grad der Behinderung\n"
        "Patientin: Erika Muster, geboren am 01.02.1970\n"
        "Diagnose: Skoliose"
    )
    name, born = extract_patient_identity(text)
    assert name == "Erika Muster"
    assert born == "1970-02-01"


def test_resolve_reply_identity_uses_project_date_when_documents_have_none() -> None:
    name, born = resolve_reply_identity("Max Mustermann", "1965-04-03", "Kein Datum im Text.")
    assert name == "Max Mustermann"
    assert born == "1965-04-03"


def test_resolve_reply_identity_prefers_document_date() -> None:
    text = "Herr Max Mustermann, geb. 03.04.1965."
    _name, born = resolve_reply_identity("Max Mustermann", "1970-01-01", text)
    assert born == "1965-04-03"


def test_resolve_reply_identity_prefers_document_name() -> None:
    befund = "Herr Max Mustermann, geb. 03.04.1965, Gehstrecke 2 km."
    name, born = resolve_reply_identity("Max D.", "", befund)
    assert name == "Max Mustermann"
    assert born == "1965-04-03"


def test_restore_ascii_umlauts_in_body() -> None:
    html = "<p>Kribbelgefuehle fuer den Patienten ueber Wochen.</p>"
    out = restore_ascii_umlauts(html)
    assert "Kribbelgefühle" in out
    assert "für" in out
    assert "über" in out
    assert "gefuehle" not in out.lower()


def test_restore_ascii_umlauts_keeps_aktuell() -> None:
    html = "<p>Der aktuelle HbA1c-Wert und die aktuelle Therapie.</p>"
    out = restore_ascii_umlauts(html)
    assert "aktuelle" in out
    assert "aktüller" not in out
    assert "aktülle" not in out


def test_restore_ascii_umlauts_fixes_llm_aktuell() -> None:
    """Modelle setzen fälschlich ü in aktuell; zurück auf ue."""
    html = "<p>Der aktülle Befund und die aktüllen Werte. Aktüll keine Einschränkung.</p>"
    out = restore_ascii_umlauts(html)
    assert "aktuelle" in out
    assert "aktuellen" in out
    assert "Aktuell" in out
    assert "aktüll" not in out.lower()


def test_rewrite_frage_heading_keeps_title() -> None:
    html = "<h2>Zu Frage 20: Hilfsmittel</h2><ul><li>Rollator vorhanden.</li></ul>"
    out = rewrite_frage_labels(html)
    assert out == "<h2>Hilfsmittel</h2><ul><li>Rollator vorhanden.</li></ul>"
    assert "Zu Frage" not in out


def test_rewrite_frage_drops_empty_heading_and_paragraph_prefix() -> None:
    html = "<h2>Zu Frage 20</h2><p>Zu Frage 3: Keine Einschränkung bekannt.</p>"
    out = rewrite_frage_labels(html)
    assert "<h2>" not in out
    assert out.startswith("<p>Keine Einschränkung bekannt.</p>")
    assert "Zu Frage" not in out


def test_restore_ascii_umlauts_keeps_tags() -> None:
    html = '<p class="ueber">aerztlich</p>'
    out = restore_ascii_umlauts(html)
    assert 'class="ueber"' in out
    assert "ärztlich" in out
