#!/bin/bash
# Installiert/aktualisiert den virtuellen CUPS-Drucker "GhostWriter".
# Wird vom Deb-postinst (root) aufgerufen.
set -euo pipefail

BACKEND_SRC="${1:-/opt/ghostwriter/packaging/cups/ghostwriter}"
PPD_SRC="${2:-/opt/ghostwriter/packaging/cups/GhostWriter.ppd}"
BACKEND_DST="/usr/lib/cups/backend/ghostwriter"
PPD_DIR="/usr/share/ppd/ghostwriter"
PPD_DST="${PPD_DIR}/GhostWriter.ppd"
SPOOL="/var/spool/ghostwriter"
PRINTER_NAME="GhostWriter"
POLKIT_RULE_SRC="${BACKEND_SRC%/*}/../polkit/49-ghostwriter-cups.rules"
POLKIT_RULE_DST="/etc/polkit-1/rules.d/49-ghostwriter-cups.rules"

log() { echo "ghostwriter-printer: $*"; }
warn() { echo "ghostwriter-printer: WARNUNG: $*" >&2; }

ensure_cups() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable cups.service >/dev/null 2>&1 || true
    systemctl start cups.service >/dev/null 2>&1 || true
    systemctl start cups.socket >/dev/null 2>&1 || true
  fi
  if command -v service >/dev/null 2>&1; then
    service cups start >/dev/null 2>&1 || true
  fi
  if command -v snap >/dev/null 2>&1 && snap list cups >/dev/null 2>&1; then
    snap start cups >/dev/null 2>&1 || true
  fi
  if ! command -v cupsd >/dev/null 2>&1 && ! command -v lpadmin >/dev/null 2>&1; then
    warn "CUPS (lpadmin) nicht installiert"
    return 1
  fi
  local i
  for i in $(seq 1 40); do
    if lpstat -r >/dev/null 2>&1; then
      if lpstat -r 2>/dev/null | grep -Eiq 'running|läuft'; then
        return 0
      fi
    fi
    if [[ -S /run/cups/cups.sock ]] || [[ -S /var/run/cups/cups.sock ]]; then
      if timeout 2 lpstat -r >/dev/null 2>&1; then
        return 0
      fi
    fi
    sleep 0.25
  done
  warn "CUPS-Scheduler antwortet nicht"
  return 1
}

repair_user_spools() {
  [[ -d "${SPOOL}" ]] || return 0
  local dir user
  for dir in "${SPOOL}"/*; do
    [[ -d "${dir}" ]] || continue
    user="$(basename "${dir}")"
    if id "${user}" >/dev/null 2>&1; then
      chown -R "${user}:${user}" "${dir}" 2>/dev/null || true
      chmod 755 "${dir}" 2>/dev/null || true
      find "${dir}" -type f -name '*.pdf' -exec chmod 600 {} + 2>/dev/null || true
      log "Spool-Rechte repariert: ${dir}"
    fi
  done
}

install_polkit_rule() {
  # Verhindert PolicyKit-Passwort-Dialoge beim lokalen Drucken
  local src="${POLKIT_RULE_SRC}"
  if [[ ! -f "${src}" ]]; then
    src="/opt/ghostwriter/packaging/polkit/49-ghostwriter-cups.rules"
  fi
  if [[ -f "${src}" ]]; then
    install -d -m 0755 /etc/polkit-1/rules.d
    install -o root -g root -m 0644 "${src}" "${POLKIT_RULE_DST}"
    log "Polkit-Regel installiert (Druck ohne Admin-Passwort)"
  fi
}

install_files() {
  if [[ ! -f "${BACKEND_SRC}" ]]; then
    echo "ghostwriter-printer: Backend fehlt: ${BACKEND_SRC}" >&2
    exit 1
  fi
  if [[ ! -f "${PPD_SRC}" ]]; then
    echo "ghostwriter-printer: PPD fehlt: ${PPD_SRC}" >&2
    exit 1
  fi
  install -d -m 1777 "${SPOOL}"
  install -d -m 0755 "${PPD_DIR}"
  # CUPS: Backend MUSS root:root und mode 0700 sein, sonst Auth-Dialog / kein root-chown
  install -o root -g root -m 0700 "${BACKEND_SRC}" "${BACKEND_DST}"
  install -o root -g root -m 0644 "${PPD_SRC}" "${PPD_DST}"
  repair_user_spools
  install_polkit_rule
}

disable_printer_auth() {
  # Keine Benutzername/Passwort-Abfrage im Druckdialog
  lpadmin -p "${PRINTER_NAME}" -o auth-info-required=none >/dev/null 2>&1 || true
  # Alle lokalen User dürfen drucken
  lpadmin -p "${PRINTER_NAME}" -u allow:all >/dev/null 2>&1 || true
  # Falls CUPS AuthInfoRequired in printers.conf gesetzt hat: entfernen
  if command -v python3 >/dev/null 2>&1 && [[ -f /etc/cups/printers.conf ]]; then
    python3 - <<'PY' || true
from pathlib import Path
p = Path("/etc/cups/printers.conf")
try:
    text = p.read_text(encoding="utf-8", errors="replace")
except Exception:
    raise SystemExit(0)
lines = text.splitlines(keepends=True)
out = []
in_gw = False
changed = False
for line in lines:
    if line.startswith("<Printer GhostWriter>") or line.startswith("<DefaultPrinter GhostWriter>"):
        in_gw = True
    elif in_gw and line.startswith("</Printer>"):
        in_gw = False
    if in_gw and line.strip().lower().startswith("authinforequired"):
        changed = True
        continue
    out.append(line)
if changed:
    p.write_text("".join(out), encoding="utf-8")
PY
    if command -v systemctl >/dev/null 2>&1; then
      systemctl reload cups.service >/dev/null 2>&1 || true
    fi
  fi
}

register_queue() {
  command -v lpadmin >/dev/null 2>&1 || {
    warn "lpadmin fehlt"
    return 1
  }
  lpadmin -x "${PRINTER_NAME}" >/dev/null 2>&1 || true

  local attempt
  for attempt in 1 2 3 4 5; do
    if lpadmin -p "${PRINTER_NAME}" -E \
      -v "ghostwriter:/" \
      -P "${PPD_DST}" \
      -D "GhostWriter virtuell" \
      -L "Lokal (Befund-Import)"; then
      cupsenable "${PRINTER_NAME}" >/dev/null 2>&1 || true
      cupsaccept "${PRINTER_NAME}" >/dev/null 2>&1 || true
      lpadmin -p "${PRINTER_NAME}" -o printer-is-shared=false >/dev/null 2>&1 || true
      disable_printer_auth
      if lpstat -p "${PRINTER_NAME}" >/dev/null 2>&1; then
        log "Drucker '${PRINTER_NAME}' registriert (Versuch ${attempt}, ohne Auth)"
        lpstat -v "${PRINTER_NAME}" || true
        return 0
      fi
    fi
    warn "lpadmin Versuch ${attempt} fehlgeschlagen – warte auf CUPS"
    sleep 1
    ensure_cups || true
  done
  warn "Drucker konnte nicht registriert werden"
  return 1
}

main() {
  install_files
  if ! ensure_cups; then
    warn "CUPS nicht bereit – Druckerdateien sind installiert, Queue folgt beim nächsten Start von CUPS"
    return 1
  fi
  register_queue
}

main "$@"
