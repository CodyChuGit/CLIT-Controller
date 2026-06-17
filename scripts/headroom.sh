#!/usr/bin/env bash
# Start the Headroom token-saving proxy for CLIT Controller (Pillar 1).
#
# Headroom (https://github.com/headroom-ai) is a context-optimization proxy: it
# compresses prompt context to cut tokens while preserving accuracy. When you
# enable Headroom in Settings (or `~/.agentflow/config.json` -> "headroom":
# {"enabled": true}) AND this proxy is running, the backend routes the claude and
# codex agents it spawns through it (ANTHROPIC_BASE_URL / OPENAI_BASE_URL). It is
# fail-open: if this proxy is not running, agents call their provider directly.
#
# It binds :8799 by NOT :8787 (the CLIT Controller backend port, which is also
# Headroom's own default — they would collide).
set -euo pipefail

HEADROOM_BIN="${HEADROOM_BIN:-$HOME/.local/bin/headroom}"
PORT="${HEADROOM_PROXY_PORT:-8799}"
PROFILE="${HEADROOM_SAVINGS_PROFILE:-agent-90}"

if [ ! -x "$HEADROOM_BIN" ]; then
  echo "error: headroom not found at $HEADROOM_BIN (set HEADROOM_BIN, or install headroom)" >&2
  exit 1
fi

# Apply the savings profile (compression aggressiveness + accuracy guard) to the
# proxy's environment, then start it. `agent-savings --format shell` emits the
# HEADROOM_* env for the chosen profile.
eval "$("$HEADROOM_BIN" agent-savings --profile "$PROFILE" --format shell)"

echo "Headroom proxy → http://127.0.0.1:${PORT}  (profile ${PROFILE})"
echo "Enable it in CLIT Controller Settings, then claude/codex agents route through it."
exec "$HEADROOM_BIN" proxy --port "$PORT"
