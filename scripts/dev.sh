#!/usr/bin/env bash
# Command Line Interface Terminal Controller — run backend (:8787) and frontend dev server (:5180).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
  echo "error: .venv missing — run ./scripts/install.sh first" >&2
  exit 1
fi

BACKEND_PORT=8787
FRONTEND_PORT=5180

# Free our ports before (re)starting so duplicate backends / vite servers can't
# pile up. SIGTERM first: a live backend then runs its shutdown hook and reaps its
# PTY terminal children (agy/codex/claude). Escalate to SIGKILL only if it refuses
# to release the port. (The backend also sweeps any leftover orphans on startup.)
free_port() {
  local port=$1 pids
  pids=$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  [ -z "$pids" ] && return 0
  echo "  freeing :$port (stopping pids: $(echo "$pids" | tr '\n' ' '))"
  kill $pids 2>/dev/null || true
  for _ in $(seq 1 50); do
    lsof -nP -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 || return 0
    sleep 0.1
  done
  pids=$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
}
free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"

echo ""
echo "  Command Line Interface Terminal Controller"
echo "  CLIT Controller IDE"
echo "  Vibe with CLIT Controller"
echo "  Backend  → http://localhost:8787   (API + built frontend, if present)"
echo "  Frontend → http://localhost:5180   (dev server, hot reload)"
echo ""

.venv/bin/python -m agentflow &
BACKEND_PID=$!

cleanup() {
  echo ""
  echo "Stopping backend (pid $BACKEND_PID) and frontend…"
  # Graceful so the backend reaps its terminal children; then make sure the vite
  # dev server (and anything still holding the ports) is gone too.
  kill "$BACKEND_PID" 2>/dev/null || true
  free_port "$FRONTEND_PORT"
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(cd frontend && npm run dev)
