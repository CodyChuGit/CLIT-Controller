#!/usr/bin/env bash
# Launch CLIT Controller IDE (Command Line Interface Traffic Controller) in an
# app-like Chrome window. Starts the local FastAPI backend if it is not already
# healthy, waits for health, then opens Chrome in --app mode. No Electron/Tauri,
# no native packaging. See docs/pwa-chrome-app-mode.md.
#
#   ./scripts/app-mode.sh
#   AGENTFLOW_PORT=9000 ./scripts/app-mode.sh
#
# It only manages the backend process IT starts; an already-running backend is
# left untouched. It never runs installers, git, or remote-state commands.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO"

PORT="${AGENTFLOW_PORT:-8787}"
URL="http://127.0.0.1:${PORT}"
HEALTH="${URL}/api/health"
RUNTIME_DIR="${CLITC_RUNTIME_DIR:-/tmp/clitc-controller}"
LOG="${RUNTIME_DIR}/backend.log"
PIDFILE="${RUNTIME_DIR}/backend.pid"
CHROME_APP="${CLITC_CHROME_APP:-Google Chrome}"
HEALTH_TIMEOUT="${CLITC_HEALTH_TIMEOUT:-30}"

mkdir -p "$RUNTIME_DIR"

is_healthy() { curl -fsS -o /dev/null --max-time 2 "$HEALTH" >/dev/null 2>&1; }

open_app() {
  # Prefer an app-mode Chrome window; if Chrome is absent the user can still open
  # the normal URL — Chrome is not required.
  if [ -d "/Applications/${CHROME_APP}.app" ] || [ -d "${HOME}/Applications/${CHROME_APP}.app" ]; then
    echo "Opening CLIT Controller IDE in app mode → $URL"
    open -na "$CHROME_APP" --args --app="$URL"
  else
    echo "Google Chrome not found — open CLIT Controller IDE manually at: $URL"
  fi
}

if is_healthy; then
  echo "Backend already healthy on :$PORT — leaving it as is."
  open_app
  exit 0
fi

if [ ! -x "$REPO/.venv/bin/python" ]; then
  echo "error: .venv missing — run ./scripts/install.sh first" >&2
  exit 1
fi

# The backend serves the built frontend; build it if the bundle is missing.
if [ ! -f "$REPO/frontend/dist/index.html" ]; then
  echo "==> Building frontend (first run)…"
  ( cd "$REPO/frontend" && npm run build )
fi

echo "==> Starting backend on :$PORT (logs: $LOG)"
AGENTFLOW_PORT="$PORT" nohup "$REPO/.venv/bin/python" -m agentflow >"$LOG" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" >"$PIDFILE"

deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
until is_healthy; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "error: backend exited during startup. Last log lines ($LOG):" >&2
    tail -n 20 "$LOG" >&2 2>/dev/null || true
    exit 1
  fi
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "error: backend not healthy within ${HEALTH_TIMEOUT}s. See $LOG" >&2
    exit 1
  fi
  sleep 0.4
done

echo "Backend healthy (pid $BACKEND_PID)."
open_app
echo "Backend log: $LOG"
echo "Stop the backend this launcher started:  kill \$(cat \"$PIDFILE\")"
