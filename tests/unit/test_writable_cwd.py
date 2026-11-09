"""API darf nicht in /root als Arbeitsverzeichnis hängen bleiben."""

from __future__ import annotations

import os
from pathlib import Path

import ghostwriter.server as server


def test_ensure_writable_cwd_leaves_unwritable_root(tmp_path: Path, monkeypatch) -> None:
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o555)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(server, "DATA_ROOT", home / "data")
    (home / "data").mkdir()
    monkeypatch.chdir(blocked)
    assert not os.access(Path.cwd(), os.W_OK)
    chosen = server.ensure_writable_cwd()
    assert chosen == home
    assert Path(os.getcwd()) == home
    blocked.chmod(0o755)
