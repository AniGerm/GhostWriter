"""Settings load/save."""

from __future__ import annotations

from pathlib import Path

from ghostwriter.settings import AppSettings, load_settings, save_settings


def test_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = AppSettings(flat_fee=30.0, ollama_model="gemma3:12b")
    save_settings(path, settings)
    loaded = load_settings(path)
    assert loaded.flat_fee == 30.0
    assert loaded.ollama_model == "gemma3:12b"


def test_missing_file_returns_defaults(tmp_path: Path) -> None:
    loaded = load_settings(tmp_path / "missing.json")
    assert loaded.flat_fee == 25.0
