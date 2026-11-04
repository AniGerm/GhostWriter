"""Frontend-Dist muss auch unter /opt/ghostwriter gefunden werden."""

from __future__ import annotations

from pathlib import Path

from ghostwriter.server import resolve_frontend_dist


def test_resolve_frontend_dist_prefers_opt(tmp_path: Path, monkeypatch: object) -> None:
    opt = tmp_path / "opt" / "ghostwriter" / "frontend" / "dist"
    opt.mkdir(parents=True)
    (opt / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(
        "ghostwriter.server.FRONTEND_DIST_CANDIDATES",
        (
            tmp_path / "missing" / "frontend" / "dist",
            opt,
        ),
    )
    assert resolve_frontend_dist() == opt
