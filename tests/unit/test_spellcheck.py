"""Spellchecker unit tests (no GUI)."""

from __future__ import annotations

from pathlib import Path

from ghostwriter.ui.spellcheck import SpellChecker


def test_user_dictionary_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "words.txt"
    checker = SpellChecker(path)
    checker.add("Polyneuropathie")
    assert checker.check("Polyneuropathie")
    reloaded = SpellChecker(path)
    assert reloaded.check("Polyneuropathie")
