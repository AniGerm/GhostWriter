"""Tests for the GitHub .deb update pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ghostwriter import updates


def test_semver_compare() -> None:
    assert updates.is_version_newer("0.2.0", "0.1.0") is True
    assert updates.is_version_newer("0.1.0", "0.1.0") is False
    assert updates.is_version_newer("0.1.0", "v0.2.0") is False
    assert updates.is_version_newer("v1.0.0", "0.9.9") is True


def test_release_to_deb_info_picks_ghostwriter_asset() -> None:
    info = updates.release_to_deb_info(
        {
            "tag_name": "v0.2.0",
            "assets": [
                {"name": "notes.txt", "browser_download_url": "https://x/notes", "size": 1},
                {
                    "name": "GhostWriter-0.2.0-amd64.deb",
                    "browser_download_url": (
                        "https://github.com/AniGerm/GhostWriter/releases/download/"
                        "v0.2.0/GhostWriter-0.2.0-amd64.deb"
                    ),
                    "size": 42,
                },
            ],
        }
    )
    assert info is not None
    assert info.version == "0.2.0"
    assert info.deb_name == "GhostWriter-0.2.0-amd64.deb"
    assert "api.github.com" not in info.deb_url
    assert info.size == 42


def test_release_without_deb_returns_none() -> None:
    assert updates.release_to_deb_info({"tag_name": "v1", "assets": []}) is None


def test_check_for_update_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(updates, "app_version", lambda: "0.1.0")
    monkeypatch.setattr(
        updates,
        "fetch_latest_deb_release",
        lambda: updates.DebReleaseInfo(
            version="0.2.0",
            deb_url="https://example.invalid/GhostWriter-0.2.0-amd64.deb",
            deb_name="GhostWriter-0.2.0-amd64.deb",
            size=10,
        ),
    )
    status = updates.check_for_update()
    assert status["available"] is True
    assert status["phase"] == "update-available"
    assert status["latest_version"] == "0.2.0"


def test_check_for_update_up_to_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updates, "app_version", lambda: "0.2.0")
    monkeypatch.setattr(
        updates,
        "fetch_latest_deb_release",
        lambda: updates.DebReleaseInfo(
            version="0.2.0",
            deb_url="https://example.invalid/x.deb",
            deb_name="GhostWriter-0.2.0-amd64.deb",
            size=1,
        ),
    )
    status = updates.check_for_update()
    assert status["available"] is False
    assert status["phase"] == "up-to-date"


def test_download_update(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(updates, "_cache_dir", lambda: tmp_path)
    updates._set_state(
        available=True,
        deb_url="https://example.invalid/GhostWriter-0.2.0-amd64.deb",
        deb_name="GhostWriter-0.2.0-amd64.deb",
        deb_size=5,
    )

    class FakeResp:
        def __init__(self) -> None:
            self.headers = {"Content-Length": "5"}
            self._done = False

        def read(self, n: int = -1) -> bytes:
            if self._done:
                return b""
            self._done = True
            return b"hello"

        def __enter__(self) -> FakeResp:
            return self

        def __exit__(self, *a: object) -> None:
            return None

    monkeypatch.setattr(
        updates.urllib.request,
        "urlopen",
        lambda *a, **k: FakeResp(),
    )
    status = updates.download_update()
    assert status["phase"] == "downloaded"
    assert Path(str(status["download_path"])).read_bytes() == b"hello"


def test_install_update_spawns_helper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    deb = tmp_path / "GhostWriter-0.2.0-amd64.deb"
    deb.write_bytes(b"%DEB")
    monkeypatch.setattr(updates, "_cache_dir", lambda: tmp_path)
    updates._set_state(download_path=str(deb), available=True)

    spawned: list[list[str]] = []

    def fake_popen(cmd: list[str], **kwargs: Any) -> object:
        spawned.append(cmd)
        return object()

    monkeypatch.setattr(updates.subprocess, "Popen", fake_popen)
    helper = tmp_path / "apply-update.sh"
    helper.write_text("#!/bin/bash\n")
    monkeypatch.setattr(updates, "APPLY_UPDATE", helper)
    status = updates.install_update()
    assert status["phase"] == "installing"
    assert spawned
