"""CUPS-Druckerabfrage für die Desktop-Einstellungen (ohne Qt)."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PrinterInfo:
    """Ein vom System gemeldeter Drucker."""

    name: str
    is_default: bool = False


_PRINTER_LINE = re.compile(r"^Drucker\s+(\S+)\s+", re.IGNORECASE)
_PRINTER_LINE_EN = re.compile(r"^printer\s+(\S+)\s+", re.IGNORECASE)
_DEFAULT_DE = re.compile(r"systemvoreingestelltes Ziel[:\s]+(\S+)", re.IGNORECASE)
_DEFAULT_EN = re.compile(r"system default destination:\s*(\S+)", re.IGNORECASE)


def list_cups_printers() -> list[PrinterInfo]:
    """Liest Drucker über ``lpstat`` (leer, wenn CUPS fehlt)."""
    try:
        listed = subprocess.run(
            ["lpstat", "-p"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        default_run = subprocess.run(
            ["lpstat", "-d"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []

    default_name = ""
    for pattern in (_DEFAULT_DE, _DEFAULT_EN):
        match = pattern.search(default_run.stdout or "")
        if match:
            default_name = match.group(1)
            break

    printers: list[PrinterInfo] = []
    seen: set[str] = set()
    for line in (listed.stdout or "").splitlines():
        match = _PRINTER_LINE.match(line) or _PRINTER_LINE_EN.match(line)
        if not match:
            continue
        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        printers.append(PrinterInfo(name=name, is_default=(name == default_name)))
    return printers
