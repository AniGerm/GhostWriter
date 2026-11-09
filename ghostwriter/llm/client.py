"""Minimaler Ollama-HTTP-Client (localhost oder privates LAN)."""

from __future__ import annotations

import ipaddress
import json
import random
from typing import Any
from urllib.parse import urlparse

import httpx


class OllamaError(RuntimeError):
    """Nutzerverständlicher Ollama-Fehler ohne Anfrage-/Dokumentinhalt."""


def is_allowed_ollama_host(host: str) -> bool:
    """Erlaubt Loopback, RFC1918 und ``*.local`` - kein oeffentliches Internet."""
    cleaned = (host or "").strip().lower().rstrip(".")
    if cleaned in {"127.0.0.1", "localhost", "::1"}:
        return True
    if cleaned.endswith(".local"):
        return True
    try:
        addr = ipaddress.ip_address(cleaned)
    except ValueError:
        return False
    return bool(addr.is_loopback or addr.is_private)


def _is_token_repeat_error(detail: str) -> bool:
    low = detail.lower()
    return "token repeat" in low or "repeat limit" in low


class OllamaClient:
    """Spricht die Ollama Chat-API an (lokal oder Praxis-LAN)."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3:14b-q8_0",
        num_ctx: int = 16384,
        timeout: float = 300.0,
    ) -> None:
        self._validate_base_url(base_url)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.num_ctx = num_ctx
        self.timeout = timeout

    @staticmethod
    def _validate_base_url(base_url: str) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Ollama-URL braucht http:// oder https://")
        host = (parsed.hostname or "").lower()
        if not is_allowed_ollama_host(host):
            raise ValueError(
                "Ollama nur lokal oder im privaten LAN "
                "(127.0.0.1/localhost/192.168.x/10.x/172.16-31.x/*.local)"
            )

    def _chat_options(self, *, seed: int | None = None) -> dict[str, Any]:
        """Optionen gegen Wiederholungsschleifen bei langen JSON-Antworten."""
        options: dict[str, Any] = {
            "num_ctx": self.num_ctx,
            "temperature": 0.3,
            "repeat_penalty": 1.15,
            "num_predict": 8192,
        }
        if seed is not None:
            options["seed"] = seed
        return options

    def list_models(self) -> list[str]:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise OllamaError(
                f"Ollama nicht erreichbar unter {self.base_url} - bitte starten bzw. URL prüfen."
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
        raise OllamaError(f"Ollama-Modell '{self.model}' nicht gefunden. Installiert: {available}")

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Sendet eine Chat-Anfrage und erwartet JSON (`format: json`)."""
        used_model = model or self.model
        last_status: httpx.HTTPStatusError | None = None
        for attempt in range(2):
            seed = None if attempt == 0 else random.randint(1, 2_147_483_647)
            payload = {
                "model": used_model,
                "stream": False,
                "format": "json",
                "options": self._chat_options(seed=seed),
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
                detail = self._error_detail(exc)
                if attempt == 0 and _is_token_repeat_error(detail):
                    last_status = exc
                    continue
                raise self._map_status_error(exc, used_model) from exc
            except httpx.HTTPError as exc:
                raise OllamaError(
                    f"Ollama nicht erreichbar unter {self.base_url} "
                    "- bitte starten bzw. URL prüfen."
                ) from exc
            content = data.get("message", {}).get("content", "{}")
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                raise OllamaError("Ollama lieferte ungültiges JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError("Ollama-Antwort ist kein JSON-Objekt")
            return parsed
        assert last_status is not None
        raise self._map_status_error(last_status, used_model) from last_status

    @staticmethod
    def _error_detail(exc: httpx.HTTPStatusError) -> str:
        try:
            payload = exc.response.json()
            if isinstance(payload, dict):
                return str(payload.get("error") or "")
        except Exception:
            return ""
        return ""

    @staticmethod
    def _map_status_error(exc: httpx.HTTPStatusError, model: str) -> OllamaError:
        detail = OllamaClient._error_detail(exc)
        detail_l = detail.lower()
        if exc.response.status_code == 404 or "not found" in detail_l:
            return OllamaError(
                f"Ollama-Modell '{model}' nicht gefunden"
                + (f" ({detail})" if detail and model in detail else "")
                + ". Bitte in den Einstellungen ein installiertes Modell wählen."
            )
        if _is_token_repeat_error(detail):
            return OllamaError(
                "Das Sprachmodell hat sich in Wiederholungen verfangen. "
                "Bitte Analyse erneut starten; ggf. Ollama neu starten "
                "oder weniger/kürzere Befunde einschließen."
            )
        return OllamaError(
            f"Ollama antwortete mit HTTP {exc.response.status_code}"
            + (f": {detail}" if detail else "")
        )
