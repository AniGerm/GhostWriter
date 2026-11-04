"""CUPS-Spool-Inbox: neue PDFs erkennen (ohne Qt)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def stable_job_id(path: Path) -> str:
    """Stabile ID aus absolutem Pfad und Dateigröße."""
    st = path.stat()
    raw = f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_state(state_path: Path) -> set[str]:
    if not state_path.is_file():
        return set()
    data = json.loads(state_path.read_text(encoding="utf-8"))
    ids = data.get("processed", [])
    return set(ids) if isinstance(ids, list) else set()


def _save_state(state_path: Path, processed: set[str]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"processed": sorted(processed)}, indent=2),
        encoding="utf-8",
    )


def list_new_spool_pdfs(spool_dir: Path, *, state_path: Path) -> list[Path]:
    """Listet unverarbeitete PDF-Dateien im Spool-Verzeichnis."""
    if not spool_dir.is_dir():
        return []
    processed = _load_state(state_path)
    found: list[Path] = []
    for path in sorted(spool_dir.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() != ".pdf":
            continue
        if stable_job_id(path) in processed:
            continue
        found.append(path)
    return found


def mark_processed(path: Path, *, state_path: Path) -> None:
    """Markiert eine Spool-Datei als verarbeitet."""
    processed = _load_state(state_path)
    processed.add(stable_job_id(path))
    _save_state(state_path, processed)
