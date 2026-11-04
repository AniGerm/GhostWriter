"""Path helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from ghostwriter.paths import default_data_root, default_spool_dir


def test_data_root_respects_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert default_data_root() == tmp_path / "ghostwriter"


def test_spool_uses_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER", "arzt")
    assert default_spool_dir() == Path("/var/spool/ghostwriter/arzt")
