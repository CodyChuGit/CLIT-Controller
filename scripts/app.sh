#!/usr/bin/env bash
# Launch CLIT Controller as a standalone Chrome "app" window — its own window,
# no tabs/address bar, separate from your everyday browsing. Mirrors vjbooth's
# kiosk/show scripts.
#
# Single-port mode: the backend on :8787 serves both the API and the built
# frontend, so the app is one URL. This script builds the frontend if needed,
# starts the backend, waits for it, then opens Chrome in --app mode.
#
#   ./scripts/app.sh                 # build (if needed) + serve + open the app window
#   APP_URL=http://localhost:8787 ./scripts/app.sh   # override the URL
#
# For a real Dock/Launchpad icon, run ./scripts/make-app.sh once to build a
# "CLIT Controller.app" bundle that calls this script.
#
# Quit the app window with Cmd+Q (also stops the backend started here).
set -euo pipefail
cd "$(dirname "$0")/.."

URL="${APP_URL:-http://localhost:8787}"
# Dedicated profile so the app window is its own Chrome instance, not a tab in
# your normal browser.
PROFILE="${APP_CHROME_PROFILE:-$HOME/.clitcontroller-chrome}"
CHROME="${CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

if [ ! -x .venv/bin/python ]; then
  echo "error: .venv missing — run ./scripts/install.sh first" >&2
  exit 1
fi
if [ ! -x "$CHROME" ] && ! command -v "$CHROME" >/dev/null 2>&1; then
  echo "error: Google Chrome not found. Set CHROME_BIN to its executable." >&2
  exit 1
fi

# Serve the built frontend from :8787 — build it if the bundle is missing.
if [ ! -f frontend/dist/index.html ]; then
  echo "==> Building frontend (first run)…"
  (cd frontend && npm run build)
fi

echo "==> Starting backend on :8787…"
.venv/bin/python -m agentflow &
BACKEND_PID=$!
cleanup() {
  echo ""
  echo "Stopping backend (pid $BACKEND_PID)…"
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Waiting for $URL …"
until curl -sf -o /dev/null "$URL"; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Backend exited before $URL was reachable." >&2
    exit 1
  fi
  sleep 0.3
done

echo "==> Opening CLIT Controller → $URL"
# Run Chrome in the foreground: with its own profile it stays the lead process
# until the app window is quit (Cmd+Q), at which point the trap stops the
# backend. Ctrl+C in the terminal does the same.
"$CHROME" \
  --app="$URL" \
  --user-data-dir="$PROFILE" \
  --no-first-run \
  --no-default-browser-check
