"""App-Icon und Desktop-Eintrag für Ubuntu-Suche müssen mitgeliefert werden."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_icon_assets_exist() -> None:
    assert (ROOT / "packaging/icons/ghostwriter.svg").is_file()
    assert (ROOT / "packaging/icons/256x256/ghostwriter.png").is_file()
    for size in (16, 32, 48, 128, 512):
        assert (ROOT / f"packaging/icons/{size}x{size}/ghostwriter.png").is_file()


def test_desktop_entry_uses_ghostwriter_icon() -> None:
    text = (ROOT / "packaging/ghostwriter.desktop").read_text(encoding="utf-8")
    assert "Icon=ghostwriter" in text
    assert "Keywords=" in text
    assert "Name=GhostWriter" in text


def test_postinst_installs_hicolor_icons() -> None:
    text = (ROOT / "packaging/deb/DEBIAN/postinst").read_text(encoding="utf-8")
    assert "hicolor" in text
    assert "update-desktop-database" in text
    assert "gtk-update-icon-cache" in text
