# Changelog

All notable changes to CLIT Controller IDE. This project has not cut tagged
releases yet, so history before the entries below lives in git. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/).

## Unreleased

### Added

- **Pillar 1 — Headroom token saving** ([headroom_service.py](backend/agentflow/headroom_service.py),
  [scripts/headroom.sh](scripts/headroom.sh)): opt-in, fail-open routing of the
  claude/codex agents through a Headroom context-optimization proxy. Off by
  default; bounded reachability probe; never required.
- **Pillar 5 — deterministic output contracts** ([contracts.py](backend/agentflow/contracts.py)):
  versioned, `kind`-discriminated schemas for controller directives, command/test/
  task summaries, failures, approvals, hand-offs, and token-efficiency reports,
  with safe validation.
- **Pillar 5 — native structured controller output**: the orchestrator can emit a
  fenced `agentflow` JSON block of validated decisions; parsers are structured-first
  with markdown fallback ([chat_directives.py](backend/agentflow/chat_directives.py)).
- **Pillar 4 — shared conversation renderer**:
  [`ConversationView`](frontend/src/components/conversation/ConversationView.tsx) +
  `Message` are the single chat-message renderer (composing `useAutoScroll`); ChatPanel
  uses them instead of its own inline bubble.
- **Pillar 3/4 frontend primitives**: ANSI normalization ([lib/ansi.ts](frontend/src/lib/ansi.ts)),
  network-boundary validation ([lib/streamEvent.ts](frontend/src/lib/streamEvent.ts)),
  and a shared auto-scroll hook ([hooks/useAutoScroll.ts](frontend/src/hooks/useAutoScroll.ts)).
- **React error boundaries** ([ErrorBoundary.tsx](frontend/src/components/ErrorBoundary.tsx))
  around the app, each view, and the chat panel.
- **Verification pipeline & CI**: ruff/mypy/pytest-cov + ESLint/Prettier/Vitest,
  [Makefile](Makefile), [CI workflow](.github/workflows/ci.yml), `requirements.lock`,
  [.env.example](.env.example).
- **Documentation package** under [docs/](docs/) (see [docs/INDEX.md](docs/INDEX.md)),
  including [PILLARS.md](docs/PILLARS.md), the audit reports, and per-subsystem docs.

### Changed

- **Security hardening**: auto-run policy routes code-executing binaries through
  approval and denies `git -c`/`tar` exec hooks ([policy_service.py](backend/agentflow/policy_service.py));
  unified local-origin allowlist backs CORS, the new CSRF guard, and the WebSocket
  check ([origins.py](backend/agentflow/origins.py)); CORS dev port corrected to :5180.
- **Reliability**: agent runs gained a wall-clock watchdog and are cancelled on
  shutdown; background tasks are retained against GC ([process_runner.py](backend/agentflow/process_runner.py)).

### Fixed

- Structured event/approval payloads are now redacted before persistence/SSE
  (secrets no longer leak via the `data` field) ([redaction.py](backend/agentflow/redaction.py)).
- Chat `send()` validates the provider before launch; git `file-diff` no longer
  surfaces `.env` contents; stale-expectation test corrected.

### Security

- See [docs/SECURITY.md](docs/SECURITY.md) for the model, controls, and residual
  risks, and [docs/audit/FINAL_REPORT.md](docs/audit/FINAL_REPORT.md) for the audit.

### Notes

- This is a local-first, single-user developer tool (no authentication by design;
  loopback only). No tagged releases or deployment pipeline exist yet.
