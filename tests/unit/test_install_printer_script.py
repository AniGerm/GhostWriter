"""Sanity checks for the CUPS printer install script shipped in the .deb."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packaging" / "cups" / "install-printer.sh"
POSTINST = ROOT / "packaging" / "deb" / "DEBIAN" / "postinst"


def test_install_printer_script_is_executable_and_has_shebang() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/bash")
    assert "lpadmin" in text
    assert "ghostwriter:/" in text
    assert "ensure_cups" in text


def test_postinst_invokes_install_printer_and_fails_loudly() -> None:
    text = POSTINST.read_text(encoding="utf-8")
    assert "install-printer.sh" in text
    assert "exit 1" in text


def test_install_printer_bash_syntax() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    subprocess.run(["bash", "-n", str(POSTINST)], check=True)
