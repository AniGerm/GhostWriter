"""SQLite-gestützter Projektspeicher (ohne Qt)."""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class DocumentRole(StrEnum):
    """Rolle eines Projektdokuments."""

    ANFRAGE = "anfrage"
    BEFUND = "befund"


@dataclass(frozen=True, slots=True)
class Question:
    """Eine Frage aus der Landratsamts-Anfrage."""

    number: int
    text: str
    keyword: str = ""


@dataclass(frozen=True, slots=True)
class Document:
    """Gespeichertes Dokument im Projekt."""

    id: str
    project_id: str
    role: DocumentRole
    display_name: str
    stored_path: str
    extracted_text: str = ""
    page_count: int = 0
    included: bool = True


@dataclass(frozen=True, slots=True)
class Project:
    """Ein Patienten-/Aktenzeichen-Projekt."""

    id: str
    patient_label: str
    reference: str
    notes: str = ""
    draft_html: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True, slots=True)
class CostSnapshot:
    """Gespeicherte Kostenberechnung."""

    page_count: int
    flat_fee: float
    copy_cost: float
    postage: float
    total: float


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class ProjectStore:
    """Persistiert Projekte, Dokumente, Fragen und Entwürfe lokal."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "projects").mkdir(exist_ok=True)
        self._db_path = self.root / "ghostwriter.sqlite3"
        # FastAPI/uvicorn führt Sync-Handler in Worker-Threads aus.
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._lock = threading.RLock()
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    patient_label TEXT NOT NULL,
                    reference TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    draft_html TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    extracted_text TEXT NOT NULL DEFAULT '',
                    page_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS questions (
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    number INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    keyword TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (project_id, number)
                );
                CREATE TABLE IF NOT EXISTS cost_snapshots (
                    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                    page_count INTEGER NOT NULL,
                    flat_fee REAL NOT NULL,
                    copy_cost REAL NOT NULL,
                    postage REAL NOT NULL,
                    total REAL NOT NULL
                );
                """
            )
            cols = {
                row[1]
                for row in self._conn.execute("PRAGMA table_info(projects)").fetchall()
            }
            if "deleted_at" not in cols:
                self._conn.execute(
                    "ALTER TABLE projects ADD COLUMN deleted_at TEXT"
                )
            doc_cols = {
                row[1]
                for row in self._conn.execute("PRAGMA table_info(documents)").fetchall()
            }
            if "included" not in doc_cols:
                self._conn.execute(
                    "ALTER TABLE documents ADD COLUMN included INTEGER NOT NULL DEFAULT 1"
                )
            self._conn.commit()

    def create_project(self, *, patient_label: str, reference: str) -> Project:
        project_id = uuid.uuid4().hex
        now = _utc_now()
        project_dir = self.root / "projects" / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "documents").mkdir(exist_ok=True)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO projects (id, patient_label, reference, notes, draft_html, created_at, updated_at)
                VALUES (?, ?, ?, '', '', ?, ?)
                """,
                (project_id, patient_label, reference, now, now),
            )
            self._conn.commit()
        return Project(
            id=project_id,
            patient_label=patient_label,
            reference=reference,
            created_at=now,
            updated_at=now,
        )

    def list_projects(self) -> list[Project]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM projects
                WHERE deleted_at IS NULL
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [self._project_from_row(row) for row in rows]

    def get_project(self, project_id: str) -> Project | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        return self._project_from_row(row) if row else None

    def is_project_active(self, project_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT deleted_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        return row is not None and row["deleted_at"] is None

    def soft_delete_project(self, project_id: str) -> bool:
        """Markiert ein Projekt als gelöscht; Dateien bleiben für Undo."""
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE projects
                SET deleted_at = ?, updated_at = ?
                WHERE id = ? AND deleted_at IS NULL
                """,
                (_utc_now(), _utc_now(), project_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def restore_project(self, project_id: str) -> bool:
        """Macht ein Soft-Delete rückgängig."""
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE projects
                SET deleted_at = NULL, updated_at = ?
                WHERE id = ? AND deleted_at IS NOT NULL
                """,
                (_utc_now(), project_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def _touch(self, project_id: str) -> None:
        self._conn.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?",
            (_utc_now(), project_id),
        )

    def set_notes(self, project_id: str, notes: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE projects SET notes = ?, updated_at = ? WHERE id = ?",
                (notes, _utc_now(), project_id),
            )
            self._conn.commit()

    def set_draft_html(self, project_id: str, html: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE projects SET draft_html = ?, updated_at = ? WHERE id = ?",
                (html, _utc_now(), project_id),
            )
            self._conn.commit()

    def add_document(
        self,
        project_id: str,
        source_path: Path,
        role: DocumentRole,
        display_name: str,
    ) -> Document:
        doc_id = uuid.uuid4().hex
        dest_dir = self.root / "projects" / project_id / "documents"
        dest_dir.mkdir(parents=True, exist_ok=True)
        suffix = source_path.suffix.lower() or ".bin"
        dest = dest_dir / f"{doc_id}{suffix}"
        shutil.copy2(source_path, dest)
        with self._lock:
            if role is DocumentRole.ANFRAGE:
                existing = self._conn.execute(
                    "SELECT id FROM documents WHERE project_id = ? AND role = ?",
                    (project_id, DocumentRole.ANFRAGE.value),
                ).fetchone()
                if existing:
                    raise ValueError("Pro Projekt ist nur eine Anfrage erlaubt")
            self._conn.execute(
                """
                INSERT INTO documents
                (id, project_id, role, display_name, stored_path, extracted_text, page_count, included)
                VALUES (?, ?, ?, ?, ?, '', 0, 1)
                """,
                (doc_id, project_id, role.value, display_name, str(dest)),
            )
            self._touch(project_id)
            self._conn.commit()
        return Document(
            id=doc_id,
            project_id=project_id,
            role=role,
            display_name=display_name,
            stored_path=str(dest),
            included=True,
        )

    def list_documents(self, project_id: str) -> list[Document]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM documents WHERE project_id = ? ORDER BY rowid",
                (project_id,),
            ).fetchall()
        return [self._document_from_row(row) for row in rows]

    def set_document_included(self, document_id: str, included: bool) -> Document:
        """Schließt ein Dokument in Analyse/Druck ein oder aus."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE documents SET included = ? WHERE id = ?",
                (1 if included else 0, document_id),
            )
            if cur.rowcount == 0:
                raise KeyError(document_id)
            row = self._conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            assert row is not None
            self._touch(row["project_id"])
            self._conn.commit()
            return self._document_from_row(row)

    def delete_document(self, project_id: str, document_id: str) -> bool:
        """Löscht Dokument-Metadaten und die gespeicherte Datei."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM documents WHERE id = ? AND project_id = ?",
                (document_id, project_id),
            ).fetchone()
            if row is None:
                return False
            stored = Path(row["stored_path"])
            self._conn.execute(
                "DELETE FROM documents WHERE id = ? AND project_id = ?",
                (document_id, project_id),
            )
            self._touch(project_id)
            self._conn.commit()
        if stored.is_file():
            stored.unlink()
        return True

    def update_document_text(self, document_id: str, text: str, page_count: int) -> None:
        with self._lock:
            self._conn.execute(
                """
                UPDATE documents SET extracted_text = ?, page_count = ?
                WHERE id = ?
                """,
                (text, page_count, document_id),
            )
            row = self._conn.execute(
                "SELECT project_id FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
            if row:
                self._touch(row["project_id"])
            self._conn.commit()

    def set_questions(self, project_id: str, questions: list[Question]) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM questions WHERE project_id = ?", (project_id,))
            for q in questions:
                self._conn.execute(
                    """
                    INSERT INTO questions (project_id, number, text, keyword)
                    VALUES (?, ?, ?, ?)
                    """,
                    (project_id, q.number, q.text, q.keyword),
                )
            self._touch(project_id)
            self._conn.commit()

    def get_questions(self, project_id: str) -> list[Question]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT number, text, keyword FROM questions
                WHERE project_id = ? ORDER BY number
                """,
                (project_id,),
            ).fetchall()
        return [
            Question(number=row["number"], text=row["text"], keyword=row["keyword"]) for row in rows
        ]

    def save_cost_snapshot(
        self,
        project_id: str,
        *,
        page_count: int,
        flat_fee: float,
        copy_cost: float,
        postage: float,
        total: float,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cost_snapshots
                (project_id, page_count, flat_fee, copy_cost, postage, total)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    page_count=excluded.page_count,
                    flat_fee=excluded.flat_fee,
                    copy_cost=excluded.copy_cost,
                    postage=excluded.postage,
                    total=excluded.total
                """,
                (project_id, page_count, flat_fee, copy_cost, postage, total),
            )
            self._touch(project_id)
            self._conn.commit()

    def get_cost_snapshot(self, project_id: str) -> CostSnapshot | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cost_snapshots WHERE project_id = ?", (project_id,)
            ).fetchone()
        if not row:
            return None
        return CostSnapshot(
            page_count=row["page_count"],
            flat_fee=row["flat_fee"],
            copy_cost=row["copy_cost"],
            postage=row["postage"],
            total=row["total"],
        )

    def export_settings_json(self) -> str:
        """Hilfs-Export (z. B. Backup); enthält keine Dokumentinhalte."""
        return json.dumps({"root": str(self.root)}, ensure_ascii=False)

    @staticmethod
    def _project_from_row(row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            patient_label=row["patient_label"],
            reference=row["reference"],
            notes=row["notes"],
            draft_html=row["draft_html"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _document_from_row(row: sqlite3.Row) -> Document:
        keys = row.keys()
        included = True if "included" not in keys else bool(row["included"])
        return Document(
            id=row["id"],
            project_id=row["project_id"],
            role=DocumentRole(row["role"]),
            display_name=row["display_name"],
            stored_path=row["stored_path"],
            extracted_text=row["extracted_text"],
            page_count=row["page_count"],
            included=included,
        )
