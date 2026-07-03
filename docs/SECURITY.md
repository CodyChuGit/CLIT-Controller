# Security

CLIT Controller IDE is a local single-user tool that runs CLI agents and shell
commands on the user's machine. The security model is containment and explicit
control, not sandboxing untrusted providers.

## Trust Boundary

Trusted:

- the local user
- the selected workspace
- user-installed provider CLIs
- localhost browser/app window

Untrusted:

- agent output
- markdown returned by agents
- commands proposed by agents
- browser pages from other origins
- file paths and request payloads crossing the API boundary

## Core Controls

| Risk | Control |
| --- | --- |
| Cross-site mutating requests | `OriginGuardMiddleware` rejects foreign `Origin` / `Referer` for mutating HTTP methods. |
| Cross-site terminal WebSocket hijack | Terminal WS checks the same local origin allowlist. |
| Path traversal | Workspace file operations resolve and verify paths stay inside the workspace. |
| Shell injection | Subprocesses use argv lists and do not use `shell=True`. |
| Risky commands | `policy_service` classifies allow / require approval / deny. |
| Secret leakage | `redaction.py` runs before persistence and broadcast. |
| Stale running state | Startup recovery settles runs, queue items, and task steps. |
| Orphaned PTYs | Terminal pidfiles are swept on startup. |
| Raw agent HTML | Markdown rendering does not inject raw agent HTML. |

## Provider Credentials

Provider CLIs own their own authentication. CLIT Controller does not read, store,
or manage provider API keys, passwords, browser sessions, or tokens.

## Command Policy

Low-risk workspace-local reads/checks may run automatically. Shared-resource or
remote-state actions require approval, including:

- installs
- deploys
- package publishing
- `git push`
- `git pull`
- commands outside the workspace

Hard-denied command shapes do not run even after approval.

## Controller Actions

Controller mutations are validated through `CLITC_RESULT_V1` before execution.
Invalid result blocks create failure events and mutate no state. Legacy
`agentflow-*` directives are compatibility fallback only and still flow through
the same policy and approval gates.

## Redaction

Redaction is server-side. The browser is not the primary redaction boundary.
Event payloads, log entries, run output, and structured data are redacted before
they are stored or sent to clients.

## Residual Risk

This app intentionally executes local CLI tools the user asks it to run. A
provider CLI can still edit files or run commands within the permissions granted
to that CLI and the current user. Use normal local development hygiene:

- review diffs
- keep secrets out of workspaces
- use git branches
- approve risky commands deliberately
