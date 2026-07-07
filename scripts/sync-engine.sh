#!/usr/bin/env bash
# Vendor a snapshot of the Agent_CLI_Skill engine into the repo so `make verify`
# and CI work on machines without the skill checked out. In dev the adapter
# imports the live skill (see backend/agentflow/orchestrator/_engine.py); this
# snapshot is the fallback that keeps CI green.
set -euo pipefail

SRC="${AGENTCLI_CORE_SRC:-/Users/cody/Agent_CLI_Skill/agent-orchestrator}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$REPO/backend/agentflow/orchestrator/_engine_snapshot"

if [ ! -f "$SRC/scripts/route-task.py" ]; then
  echo "engine source not found at $SRC (set AGENTCLI_CORE_SRC)" >&2
  exit 1
fi

mkdir -p "$DEST/scripts" "$DEST/config"

# Only the pure-stdlib library modules the adapter imports — not the shell
# wrappers, tests, or workspaces. `config/` is copied so persona/policy YAML
# resolves relative to the snapshot root (mirrors the real scripts/ + config/ layout).
for f in _lib.py dispatch.py usage_lib.py monitor_lib.py route-task.py; do
  cp "$SRC/scripts/$f" "$DEST/scripts/$f"
done
cp "$SRC"/config/*.yaml "$DEST/config/" 2>/dev/null || true

echo "vendored engine snapshot -> $DEST"
