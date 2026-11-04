#!/usr/bin/env bash
# Startet API + gebautes Frontend in Electron (oder Browser-Fallback).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source .venv/bin/activate
pkill -f "uvicorn ghostwriter.server:app" 2>/dev/null || true
uvicorn ghostwriter.server:app --host 127.0.0.1 --port 8787 &
API_PID=$!
sleep 1

export ELECTRON_DISABLE_SANDBOX=1
if command -v electron >/dev/null 2>&1; then
  electron "$ROOT/desktop/main.cjs" --no-sandbox &
elif [[ -x "$ROOT/frontend/node_modules/.bin/electron" ]]; then
  "$ROOT/frontend/node_modules/.bin/electron" "$ROOT/desktop/main.cjs" --no-sandbox &
else
  xdg-open "http://127.0.0.1:8787" >/dev/null 2>&1 || true
fi

wait "$API_PID"
