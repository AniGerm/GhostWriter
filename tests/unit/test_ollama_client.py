"""Tests for Ollama client locality guard."""

from __future__ import annotations

import json

import httpx
import pytest
from ghostwriter.llm.client import OllamaClient


def test_rejects_remote_host() -> None:
    with pytest.raises(ValueError, match="lokal"):
        OllamaClient(base_url="http://evil.example:11434")


def test_chat_json_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"message": {"content": json.dumps({"ok": True})}}

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def post(self, url: str, json: dict[str, object]) -> FakeResponse:
            assert "127.0.0.1" in url
            assert json["format"] == "json"
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = OllamaClient()
    assert client.chat_json(system="s", user="u") == {"ok": True}
