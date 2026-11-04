"""Marked integration stubs (skipped without services)."""

from __future__ import annotations

import pytest


@pytest.mark.ollama
def test_ollama_reachable() -> None:
    pytest.importorskip("httpx")
    import httpx

    try:
        r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=2.0)
        assert r.status_code == 200
    except Exception:
        pytest.skip("Ollama not running")


@pytest.mark.gpu
def test_paddle_import() -> None:
    pytest.importorskip("paddle")
