"""Ollama-Fehler müssen verständlich und ohne Dokumentinhalt gemeldet werden."""

from __future__ import annotations

import httpx
import pytest
from ghostwriter.llm.client import OllamaClient, OllamaError


def test_chat_json_maps_404_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
    response = httpx.Response(404, json={"error": "model 'qwen2.5:14b' not found"}, request=request)

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def post(self, url: str, json: dict[str, object]) -> httpx.Response:
            return response

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = OllamaClient(model="qwen2.5:14b")
    with pytest.raises(OllamaError, match=r"Modell .*qwen2\.5:14b.* nicht gefunden") as excinfo:
        client.chat_json(system="s", user="u")
    assert "Patienten" not in str(excinfo.value)
    assert "user" not in str(excinfo.value).lower() or "qwen" in str(excinfo.value).lower()


def test_ensure_model_available_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OllamaClient(model="missing:model")
    monkeypatch.setattr(client, "list_models", lambda: ["other:1b"])
    with pytest.raises(OllamaError, match="missing:model"):
        client.ensure_model_available()
