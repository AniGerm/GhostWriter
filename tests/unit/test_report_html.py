"""HTML-Nachbearbeitung für Berichtsentwürfe."""

from __future__ import annotations

from ghostwriter.report_html import restore_ascii_umlauts, strip_heading_brackets


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


def test_restore_ascii_umlauts_in_body() -> None:
    html = "<p>Kribbelgefuehle fuer den Patienten ueber Wochen.</p>"
    out = restore_ascii_umlauts(html)
    assert "Kribbelgefühle" in out
    assert "für" in out
    assert "über" in out
    assert "gefuehle" not in out.lower()


def test_restore_ascii_umlauts_keeps_tags() -> None:
    html = '<p class="ueber">aerztlich</p>'
    out = restore_ascii_umlauts(html)
    assert 'class="ueber"' in out
    assert "ärztlich" in out
