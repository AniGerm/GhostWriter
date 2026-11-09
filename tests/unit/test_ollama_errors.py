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


def test_chat_json_maps_token_repeat_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
    response = httpx.Response(
        500,
        json={"error": "prediction aborted, token repeat limit reached"},
        request=request,
    )

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
    client = OllamaClient(model="mistral-small")
    with pytest.raises(OllamaError, match=r"(Wiederholung|erneut)") as excinfo:
        client.chat_json(system="s", user="u")
    msg = str(excinfo.value)
    assert "token repeat" not in msg.lower() or "Wiederholung" in msg
    assert "Patienten" not in msg


def test_chat_json_retries_once_on_token_repeat(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/chat")
    fail = httpx.Response(
        500,
        json={"error": "prediction aborted, token repeat limit reached"},
        request=request,
    )
    ok_body = {"message": {"content": '{"html":"<p>ok</p>"}'}}
    calls: list[dict[str, object]] = []

    class FakeResponse:
        def __init__(self, payload: object) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            if isinstance(self._payload, httpx.Response):
                raise httpx.HTTPStatusError(
                    "boom",
                    request=request,
                    response=self._payload,
                )

        def json(self) -> object:
            return self._payload

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def post(self, url: str, json: dict[str, object]) -> FakeResponse:
            calls.append(json)
            if len(calls) == 1:
                return FakeResponse(fail)
            return FakeResponse(ok_body)

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = OllamaClient(model="mistral-small")
    result = client.chat_json(system="s", user="u")
    assert result == {"html": "<p>ok</p>"}
    assert len(calls) == 2
    assert calls[1]["options"]["seed"] != calls[0]["options"].get("seed", 0)
