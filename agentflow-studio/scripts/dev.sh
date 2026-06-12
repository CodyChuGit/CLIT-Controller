#!/usr/bin/env bash
# AgentFlow Studio — run backend (:8787) and frontend dev server (:5173).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
  echo "error: .venv missing — run ./scripts/install.sh first" >&2
  exit 1
fi

echo ""
echo "  AgentFlow Studio (beta)"
echo "  Backend  → http://localhost:8787   (API + built frontend, if present)"
echo "  Frontend → http://localhost:5173   (dev server, hot reload)"
echo ""

.venv/bin/python -m agentflow &
BACKEND_PID=$!

cleanup() {
  echo ""
  echo "Stopping backend (pid $BACKEND_PID)…"
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(cd frontend && npm run dev)
