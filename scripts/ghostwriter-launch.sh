#!/usr/bin/env bash
# Startet API + Desktop-Fenster (Electron falls vorhanden, sonst Browser-App).
set -euo pipefail

APP_ROOT="${GHOSTWRITER_ROOT:-/opt/ghostwriter}"
API_URL="http://127.0.0.1:8787"
ICON="${APP_ROOT}/packaging/icons/256x256/ghostwriter.png"
export ELECTRON_DISABLE_SANDBOX=1

start_api() {
  if curl -sf "${API_URL}/api/health" >/dev/null 2>&1; then
    return 0
  fi
  if [[ -x "${APP_ROOT}/venv/bin/uvicorn" ]]; then
    nohup "${APP_ROOT}/venv/bin/uvicorn" ghostwriter.server:app \
      --host 127.0.0.1 --port 8787 \
      >/tmp/ghostwriter-web.log 2>&1 &
  else
    nohup "${APP_ROOT}/venv/bin/ghostwriter-web" >/tmp/ghostwriter-web.log 2>&1 &
  fi
  for _ in $(seq 1 40); do
    if curl -sf "${API_URL}/api/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  echo "GhostWriter-API startet nicht unter ${API_URL}" >&2
  return 1
}

start_api

ELECTRON_BIN=""
if [[ -x "${APP_ROOT}/node_modules/.bin/electron" ]]; then
  ELECTRON_BIN="${APP_ROOT}/node_modules/.bin/electron"
elif [[ -x "${APP_ROOT}/../Dokumente/GhostWriter/frontend/node_modules/.bin/electron" ]]; then
  ELECTRON_BIN="${APP_ROOT}/../Dokumente/GhostWriter/frontend/node_modules/.bin/electron"
elif command -v electron >/dev/null 2>&1; then
  ELECTRON_BIN="$(command -v electron)"
fi

DESKTOP_MAIN="${APP_ROOT}/desktop/main.cjs"
if [[ -n "${ELECTRON_BIN}" && -f "${DESKTOP_MAIN}" ]]; then
  exec "${ELECTRON_BIN}" "${DESKTOP_MAIN}" --no-sandbox
fi

# Fallback: Chromium/Chrome als App-Fenster mit Klasse GhostWriter (Dock-Icon)
for bin in google-chrome-stable google-chrome chromium-browser chromium; do
  if command -v "$bin" >/dev/null 2>&1; then
    exec "$bin" --app="${API_URL}" --class=GhostWriter --name=GhostWriter
  fi
done

exec xdg-open "${API_URL}"
