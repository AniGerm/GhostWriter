"""Ollama-basierte Bericht-Pipeline."""

from __future__ import annotations

from ghostwriter.llm.client import OllamaClient
from ghostwriter.llm.pipeline import ReportPipeline

__all__ = ["OllamaClient", "ReportPipeline"]
