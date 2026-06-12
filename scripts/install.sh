#!/usr/bin/env bash
# AgentFlow Studio — one-time setup: Python venv + backend deps + frontend deps.
set -euo pipefail
cd "$(dirname "$0")/.."

# Find a Python >= 3.11
PY=""
for candidate in "${PYTHON:-}" python3.13 python3.12 python3.11 python3; do
  [ -z "$candidate" ] && continue
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      PY="$candidate"
      break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "error: Python 3.11+ not found. Install it (e.g. brew install python@3.12) and re-run." >&2
  exit 1
fi
echo "==> Using $PY ($($PY --version))"

if [ ! -d .venv ]; then
  echo "==> Creating virtualenv at .venv"
  "$PY" -m venv .venv
fi

echo "==> Installing backend dependencies"
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -e ".[dev]" --quiet

echo "==> Installing frontend dependencies"
if ! (cd frontend && npm install --no-fund --no-audit); then
  echo "==> npm install failed (often a ~/.npm permissions issue) — retrying with an isolated cache"
  (cd frontend && npm install --no-fund --no-audit --cache "${TMPDIR:-/tmp}/agentflow-npm-cache")
fi

echo ""
echo "✓ Install complete. Start the app with: ./scripts/dev.sh"
