# GhostWriter

Lokale Desktop-App für ärztliche Antwortschreiben zum Grad der Behinderung (SGB): Anfrage und Befunde digitalisieren, mit Ollama strukturierte Berichte entwerfen, bearbeiten, drucken und Kosten berechnen.

## Anforderungen

- Ubuntu mit CUPS
- Python 3.12+
- Ollama lokal (`127.0.0.1:11434`)
- Optional: NVIDIA-GPU + PaddleOCR für Scans ohne Textebene

## Entwicklung

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Start (neue Web-UI)

```bash
# API + React (Entwicklung)
./scripts/dev_web.sh
# Browser: http://127.0.0.1:5174

# API + Electron-Fenster
./scripts/start_desktop.sh
# oder nur Backend mit gebautem Frontend:
ghostwriter-web   # http://127.0.0.1:8787
```

Die frühere Qt-UI bleibt vorübergehend als `ghostwriter` erreichbar.

## Updates

Wie bei DigitizeMyBook/Fax-Inbox über öffentliche GitHub-Releases:

1. Tag `vX.Y.Z` pushen (muss mit `VERSION` übereinstimmen)
2. GitHub Actions baut `GhostWriter-X.Y.Z-amd64.deb` und veröffentlicht es
3. In der App: **Update** → prüfen / laden / mit `pkexec` installieren

Standard-Repo: `AniGerm/GhostWriter` (in den Einstellungen änderbar).
