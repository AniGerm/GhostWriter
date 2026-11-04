"""Signatur einmalig ans Schreiben anhängen."""

from __future__ import annotations

from ghostwriter.signature import apply_signature, strip_trailing_signature


def test_strip_trailing_greeting_block() -> None:
    html = "<p>Text</p><p>Mit freundlichen Grüßen</p><p>Dr. Alt</p>"
    assert strip_trailing_signature(html) == "<p>Text</p>"


def test_apply_signature_once() -> None:
    html = "<p>Text</p><p>Mit freundlichen Grüßen</p>"
    out = apply_signature(html, "<p>Mit freundlichen Grüßen</p><p>Dr. Neu</p>")
    assert out.count("Mit freundlichen Grüßen") == 1
    assert "Dr. Neu" in out
