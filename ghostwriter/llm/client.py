"""Minimaler Ollama-HTTP-Client (nur localhost)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx


class OllamaClient:
    """Spricht die lokale Ollama Chat-API an."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5:14b",
        num_ctx: int = 16384,
        timeout: float = 300.0,
    ) -> None:
        self._validate_local(base_url)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.num_ctx = num_ctx
        self.timeout = timeout

    @staticmethod
    def _validate_local(base_url: str) -> None:
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").lower()
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("Ollama darf nur lokal (127.0.0.1/localhost) angesprochen werden")

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Sendet eine Chat-Anfrage und erwartet JSON (`format: json`)."""
        payload = {
            "model": model or self.model,
            "stream": False,
            "format": "json",
            "options": {"num_ctx": self.num_ctx},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        content = data.get("message", {}).get("content", "{}")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Ollama-Antwort ist kein JSON-Objekt")
        return parsed

    def list_models(self) -> list[str]:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
