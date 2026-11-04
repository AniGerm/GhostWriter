#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3.12 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -e ".[dev]" -q

pkill -f "uvicorn ghostwriter.server:app" 2>/dev/null || true
uvicorn ghostwriter.server:app --host 127.0.0.1 --port 8787 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

cd frontend
if [[ ! -d node_modules ]]; then
  npm install
fi
npm run dev -- --host 127.0.0.1 --port 5174
