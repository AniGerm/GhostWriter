"""Tests for spool inbox discovery (no Qt)."""

from __future__ import annotations

from pathlib import Path

from ghostwriter.inbox import (
    list_new_spool_pdfs,
    mark_all_spool_pdfs_processed,
    mark_processed,
    stable_job_id,
)


def test_lists_only_pdfs_not_yet_processed(tmp_path: Path) -> None:
    spool = tmp_path / "spool"
    spool.mkdir()
    (spool / "a.pdf").write_bytes(b"%PDF")
    (spool / "b.txt").write_text("x")
    (spool / "c.PDF").write_bytes(b"%PDF")
    state = tmp_path / "state.json"
    jobs = list_new_spool_pdfs(spool, state_path=state)
    names = sorted(p.name.lower() for p in jobs)
    assert names == ["a.pdf", "c.pdf"]


def test_mark_processed_hides_file(tmp_path: Path) -> None:
    spool = tmp_path / "spool"
    spool.mkdir()
    pdf = spool / "job.pdf"
    pdf.write_bytes(b"%PDF")
    state = tmp_path / "state.json"
    assert list_new_spool_pdfs(spool, state_path=state)
    mark_processed(pdf, state_path=state)
    assert list_new_spool_pdfs(spool, state_path=state) == []


def test_stable_job_id_is_deterministic(tmp_path: Path) -> None:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-data")
    assert stable_job_id(pdf) == stable_job_id(pdf)


def test_mark_all_spool_pdfs_processed(tmp_path: Path) -> None:
    spool = tmp_path / "spool"
    spool.mkdir()
    (spool / "a.pdf").write_bytes(b"%PDF")
    (spool / "b.pdf").write_bytes(b"%PDF")
    state = tmp_path / "state.json"
    assert mark_all_spool_pdfs_processed(spool, state_path=state) == 2
    assert list_new_spool_pdfs(spool, state_path=state) == []
