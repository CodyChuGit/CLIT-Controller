# Changelog

This project has not cut tagged releases yet. Current changes are tracked under
Unreleased.

## Unreleased

### Added

- Right-hand Agent Dock with controller transcript, provider PTY tabs, terminal
  drawer, activity cards, approvals, composer, status footer, and live run
  output.
- Structured controller action engine based on `CLITC_RESULT_V1`.
- Controller action support for answer, create task, queue steps, run command,
  request approval, request user, retry, reroute, complete task, and cancel.
- Provider-lane Tasks dispatch map for Controller, Codex, Claude, Antigravity,
  and local tools.
- PTY terminal diagnostics, lifecycle metadata frames, restart/kill support, and
  startup orphan cleanup.
- Shared frontend live activity derivation for Agent Dock and Tasks.
- Headroom and Ponytail settings surfaced as current token controls.

### Changed

- Default controller routing is now `claude`; QA defaults to `antigravity`.
- Legacy `agentflow-*` directives are compatibility fallback only when no
  `CLITC_RESULT_V1` block is present.
- Headroom is enabled by default and fail-open for `claude` and `codex`.
- Documentation has been rebuilt around the current working app and obsolete
  planning/audit markdown has been removed.

### Fixed

- Agent Dock and Tasks render live managed output from the shared event store
  instead of cached final text.
- Antigravity terminal startup uses the resolved `agy` executable path and shows
  diagnostic states when unavailable or closed.
- Stale Gemini and Antigravity-controller config values migrate to current
  provider routing.

### Security

- Controller command actions continue through policy and durable approvals.
- Terminal WebSockets and mutating HTTP routes use local-origin checks.
- Logs, events, run records, and terminal diagnostics are redacted before
  persistence or broadcast.
