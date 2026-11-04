"""Zusätzliche OllamaClient-Pfade für Coverage und Regression."""

from __future__ import annotations

import json

import httpx
import pytest
from ghostwriter.llm.client import OllamaClient, OllamaError


def test_list_models_and_ensure_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"models": [{"name": "qwen3:14b-q8_0"}, {"name": "other:1b"}]}

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            assert url.endswith("/api/tags")
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = OllamaClient(model="qwen3:14b-q8_0")
    assert "qwen3:14b-q8_0" in client.list_models()
    client.ensure_model_available()


def test_chat_json_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def post(self, *a: object, **k: object) -> None:
            raise httpx.ConnectError("nope")

    monkeypatch.setattr(httpx, "Client", FakeClient)
    with pytest.raises(OllamaError, match="nicht erreichbar"):
        OllamaClient().chat_json(system="s", user="u")


def test_chat_json_invalid_json_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"message": {"content": "not-json"}}

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def post(self, *a: object, **k: object) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    with pytest.raises(OllamaError, match="ungültiges JSON"):
        OllamaClient().chat_json(system="s", user="u")
