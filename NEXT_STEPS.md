# Next Steps

## Phase 1 — polish the beta

- Better streaming logs (SSE/WebSocket instead of polling)
- Robust pseudo-terminal support for interactive CLIs
- Exact CLI syntax tuning per provider (flags, permission modes, model pins)
- Better frontend folder picker (native dialog via a small helper, or recent-paths list)
- Diff viewer (side-by-side, per-file)
- Prompt compression (summarize task history before re-prompting)
- Project templates (preconfigured routing + command templates per stack)

## Phase 2 — productize

- Package as a desktop app with Tauri
- Optional SwiftUI shell later
- Zed integration / Zed fork later
- MCP adapter layer (expose tasks/usage as MCP tools)
- Browser screenshot QA step for UI work
- Local Qwen/Ollama/MLX summarizer for cheap routing and log digests

## Phase 3 — extend

- VS Code / Zed companion extension
- Team mode (shared task folders, multiple operators)
- Model-router plugin system
- Exact provider usage APIs where available (replace manual health toggles)
- Shareable task reports (export task folder as a single markdown/HTML report)
