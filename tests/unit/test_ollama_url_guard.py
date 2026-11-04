"""Ollama-URL: localhost und privates LAN erlaubt, öffentliches Internet nicht."""

from __future__ import annotations

import pytest
from ghostwriter.llm.client import OllamaClient


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://192.168.1.20:11434",
        "http://10.0.0.5:11434",
        "http://172.16.3.4:11434",
        "http://ollama.local:11434",
    ],
)
def test_allows_loopback_and_private_lan(url: str) -> None:
    client = OllamaClient(base_url=url)
    assert client.base_url == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "http://evil.example:11434",
        "https://api.openai.com",
        "http://8.8.8.8:11434",
    ],
)
def test_rejects_public_hosts(url: str) -> None:
    with pytest.raises(ValueError, match="privat|lokal|LAN"):
        OllamaClient(base_url=url)
