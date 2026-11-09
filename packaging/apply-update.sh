#!/bin/bash
# Installiert ein GhostWriter-*.deb, beendet alte Instanzen und startet neu.
# Aufruf: pkexec /usr/lib/ghostwriter/apply-update.sh /pfad/zum.deb
set -euo pipefail
DEB="${1:-}"
if [[ -z "$DEB" || ! -f "$DEB" ]]; then
  echo "Usage: $0 /path/to/GhostWriter-VERSION-amd64.deb" >&2
  exit 2
fi
case "$(basename "$DEB")" in
  GhostWriter-*.deb|ghostwriter-*.deb) ;;
  *)
    echo "Nur GhostWriter-*.deb erlaubt." >&2
    exit 2
    ;;
esac

# Laufende App beenden, damit nicht zwei Fenster entstehen
pkill -f 'uvicorn ghostwriter.server:app' 2>/dev/null || true
pkill -f 'uvicorn.*ghostwriter' 2>/dev/null || true
pkill -f '/opt/ghostwriter/desktop/main.cjs' 2>/dev/null || true
pkill -f 'electron.*ghostwriter/desktop' 2>/dev/null || true
sleep 1

export DEBIAN_FRONTEND=noninteractive
if command -v apt-get >/dev/null 2>&1; then
  apt-get install -y --reinstall "$DEB" || dpkg -i "$DEB"
else
  dpkg -i "$DEB"
fi
echo "GhostWriter-Update installiert."

# Als aufrufender Benutzer neu starten (pkexec setzt PKEXEC_UID)
INVOKER_UID="${PKEXEC_UID:-}"
INVOKER=""
if [[ -n "$INVOKER_UID" ]]; then
  INVOKER="$(getent passwd "$INVOKER_UID" | cut -d: -f1 || true)"
fi
if [[ -z "$INVOKER" && -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
  INVOKER="$SUDO_USER"
fi

USER_DISPLAY="${DISPLAY:-:0}"
USER_XAUTHORITY="${XAUTHORITY:-}"
if [[ -n "$INVOKER" && "$INVOKER" != "root" ]]; then
  HOME_DIR="$(getent passwd "$INVOKER" | cut -d: -f6)"
  if [[ -z "$USER_XAUTHORITY" && -f "${HOME_DIR}/.Xauthority" ]]; then
    USER_XAUTHORITY="${HOME_DIR}/.Xauthority"
  fi
  sleep 1
  # Wichtig: nicht im cwd von pkexec (/root) starten – sonst scheitert OCR
  # mit PermissionError: [Errno 13] Permission denied: 'None'.
  if command -v runuser >/dev/null 2>&1; then
    runuser -u "$INVOKER" -- bash -lc \
      "cd \"$HOME_DIR\" && env HOME=\"$HOME_DIR\" DISPLAY=\"$USER_DISPLAY\" \
      XAUTHORITY=\"${USER_XAUTHORITY:-}\" ELECTRON_DISABLE_SANDBOX=1 \
      /usr/bin/ghostwriter >/tmp/ghostwriter-relaunch.log 2>&1 &"
  else
    sudo -u "$INVOKER" -H bash -lc \
      "cd \"$HOME_DIR\" && env HOME=\"$HOME_DIR\" DISPLAY=\"$USER_DISPLAY\" \
      XAUTHORITY=\"${USER_XAUTHORITY:-}\" ELECTRON_DISABLE_SANDBOX=1 \
      /usr/bin/ghostwriter >/tmp/ghostwriter-relaunch.log 2>&1 &"
  fi
  echo "GhostWriter neu gestartet für $INVOKER"
fi
