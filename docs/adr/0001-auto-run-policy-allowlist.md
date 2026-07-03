# ADR 0001 - Auto-Run Command Policy

- Status: Accepted
- Date: 2026-06-17

## Context

Controller and task actions can request local commands. The app is designed to
automate low-risk workspace operations, but it also runs on a developer machine
with the user's permissions. Command policy must keep routine reads/checks fast
while preventing silent high-risk execution.

## Decision

Use a three-way policy:

- `allow`: low-risk workspace-confined reads and checks.
- `require_approval`: installs, deploys, remote/shared-state operations, code
  execution helpers, and other risky commands.
- `deny`: known bypasses, shell-control shapes, privileged commands, path
  traversal, and commands outside the workspace.

This policy applies to structured `CLITC_RESULT_V1` command actions and legacy
directive fallback actions.

## Rationale

A strict default-deny allowlist would make common local workflows too noisy. A
targeted hardening policy preserves useful automation while forcing explicit
approval for commands that can mutate shared resources or execute arbitrary code.

## Consequences

- Some legitimate commands require one-click approval.
- Denied command shapes cannot run even after approval.
- New command categories must be reviewed against [../SECURITY.md](../SECURITY.md)
  and tested in `policy_service` coverage.
