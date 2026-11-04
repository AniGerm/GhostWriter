"""Pfad-Hilfen für lokale GhostWriter-Daten."""

from __future__ import annotations

import os
from pathlib import Path


def default_data_root() -> Path:
    """Standard-Datenverzeichnis unter XDG_DATA_HOME bzw. ~/.local/share."""
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "ghostwriter"


def default_spool_dir(username: str | None = None) -> Path:
    """CUPS-Spool-Verzeichnis für eingehende Drucke."""
    user = username or os.environ.get("USER") or os.environ.get("LOGNAME") or "user"
    return Path("/var/spool/ghostwriter") / user
