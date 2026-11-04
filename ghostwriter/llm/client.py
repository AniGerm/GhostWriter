"""Minimaler Ollama-HTTP-Client (nur localhost)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx


class OllamaError(RuntimeError):
    """Nutzerverständlicher Ollama-Fehler ohne Anfrage-/Dokumentinhalt."""


class OllamaClient:
    """Spricht die lokale Ollama Chat-API an."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3:14b-q8_0",
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

    def list_models(self) -> list[str]:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise OllamaError(
                "Ollama nicht erreichbar unter http://127.0.0.1:11434 - bitte starten."
            ) from exc
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    def ensure_model_available(self) -> None:
        """Prüft, ob das konfigurierte Modell lokal installiert ist."""
        models = self.list_models()
        if self.model in models:
            return
        # Ollama akzeptiert oft Tags ohne :latest
        if any(name == self.model or name.startswith(f"{self.model}:") for name in models):
            return
        available = ", ".join(models[:8]) if models else "(keine Modelle)"
        raise OllamaError(
            f"Ollama-Modell '{self.model}' nicht gefunden. Installiert: {available}"
        )

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Sendet eine Chat-Anfrage und erwartet JSON (`format: json`)."""
        used_model = model or self.model
        payload = {
            "model": used_model,
            "stream": False,
            "format": "json",
            "options": {"num_ctx": self.num_ctx},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise self._map_status_error(exc, used_model) from exc
        except httpx.HTTPError as exc:
            raise OllamaError(
                "Ollama nicht erreichbar unter http://127.0.0.1:11434 - bitte starten."
            ) from exc
        content = data.get("message", {}).get("content", "{}")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OllamaError("Ollama lieferte ungültiges JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Ollama-Antwort ist kein JSON-Objekt")
        return parsed

    @staticmethod
    def _map_status_error(exc: httpx.HTTPStatusError, model: str) -> OllamaError:
        detail = ""
        try:
            payload = exc.response.json()
            if isinstance(payload, dict):
                detail = str(payload.get("error") or "")
        except Exception:
            detail = ""
        # Keine Prompt-/Dokumenttexte in die Fehlermeldung übernehmen
        detail_l = detail.lower()
        if exc.response.status_code == 404 or "not found" in detail_l:
            return OllamaError(
                f"Ollama-Modell '{model}' nicht gefunden"
                + (f" ({detail})" if detail and model in detail else "")
                + ". Bitte in den Einstellungen ein installiertes Modell wählen."
            )
        return OllamaError(
            f"Ollama antwortete mit HTTP {exc.response.status_code}"
            + (f": {detail}" if detail else "")
        )
