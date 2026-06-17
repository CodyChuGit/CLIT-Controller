# ADR 0001 — Auto-run command policy: targeted hardening, not full allowlist inversion

- Status: Accepted
- Date: 2026-06-17
- Context: audit finding P1-05

## Context

`policy_service.classify_action` gates commands an agent emits via `agentflow-run`
directives, which auto-execute in the default "balanced" mode. It was a **denylist**
that fell through to `ALLOW` for anything unrecognized. Verification confirmed a
prompt-injection-to-RCE path: `make`, `node <file>`, `npx`, and
`awk 'BEGIN{system(...)}'` all classified `ALLOW` and ran without approval.

The audit offered two fixes: (a) invert to a strict **allowlist** (default →
require approval), or (b) **targeted hardening** of the known exec vectors.

## Decision

Adopt (b). Route code-executing binaries (interpreters running a file, `make`,
`npx`, `awk`/`sed`, `pnpm dlx`) through the existing approval flow, and hard-deny
the `git -c`/`--config` pager-exec and `tar` exec-hook bypass vectors. Keep
recognized-safe workflow commands (`npm run`, `npm test`, `git status`/`diff`,
`ls`, `cat` within the workspace) auto-allowed.

## Rationale

- A full allowlist inversion would force approval for many legitimate auto-commands
  the autonomous workflow relies on (and would break existing tests/behavior),
  contradicting the directive's "preserve existing product behavior" and "smallest
  coherent change" rules.
- Targeted hardening closes every verified exploit vector while keeping the
  documented dev/test workflow auto-running.
- The approval flow already exists and is durable, so denied-by-default-for-exec
  degrades to a user prompt, not a hard failure.

## Consequences

- New code-execution attempts (`node script.js`, `make`, `npx`, …) now require a
  one-click approval instead of running silently. This is the intended safer
  default; it is mildly more interactive for power users.
- The denylist can still, in principle, miss a novel exec vector. A future move to
  a strict allowlist (with a curated read-only safe set) remains the stronger
  long-term posture and is recorded as possible follow-up.
- For workspaces that may contain untrusted content, running in `manual_approval`
  mode is recommended (see [SECURITY.md](../SECURITY.md)).
