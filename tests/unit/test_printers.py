"""CUPS-Druckerliste aus lpstat-Ausgabe."""

from __future__ import annotations

from ghostwriter.printers import list_cups_printers


def test_list_cups_printers_parses_german_lpstat(monkeypatch: object) -> None:
    class Result:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout
            self.returncode = 0

    def fake_run(cmd: list[str], **_k: object) -> Result:
        if cmd[:2] == ["lpstat", "-p"]:
            return Result(
                "Drucker GhostWriter ist im Leerlauf.  Aktiviert seit …\n"
                "Drucker Dell_C2665dnf ist im Leerlauf.  Aktiviert seit …\n"
            )
        return Result("Systemvoreingestelltes Ziel: Dell_C2665dnf\n")

    import subprocess

    monkeypatch.setattr(subprocess, "run", fake_run)  # type: ignore[attr-defined]
    printers = list_cups_printers()
    assert [p.name for p in printers] == ["GhostWriter", "Dell_C2665dnf"]
    assert printers[1].is_default is True
