# Security Model

CLIT Controller IDE runs **CLI coding agents and shells as subprocesses on your
machine** and exposes them through a local web UI. Its security posture is built
around that reality: the product's whole job is to execute commands you (or an
agent you direct) ask for, so the controls are about *containment* and *not being
driven by someone other than you*, not about sandboxing the agents themselves.

## Threat model

| In scope | Out of scope (by design) |
|----------|--------------------------|
| A malicious web page in your browser reaching the local API (CSRF / CSWSH) | Multi-user authentication / RBAC — this is a single-user local tool |
| Path traversal / arbitrary file read-write outside the selected workspace | Sandboxing a CLI agent you deliberately ran |
| Secrets leaking into logs, ledgers, or the event stream | Network attackers — the server binds loopback only |
| Prompt-injection driving auto-executed commands | Hardening the host OS |
| SSRF via the preview/proxy surface | |

The trust boundary is the **loopback interface plus origin checks**, not a login.
If an attacker already has local code execution as your user, this app is not your
defense.

## Trust boundaries & controls

- **Network exposure.** The backend binds `127.0.0.1` only
  ([`__main__.py`](../backend/agentflow/__main__.py)); it is never reachable from
  the LAN. The Vite dev server (`:5180`) also binds locally and proxies `/api`.
- **CORS / CSRF.** `CORSMiddleware` restricts browser origins to the app's own
  localhost ports ([`app.py`](../backend/agentflow/app.py)). Because CORS does not
  stop a request from *executing* server-side, mutating endpoints are additionally
  guarded by an Origin/Referer check (see hardening below).
- **WebSocket hijack (CSWSH).** The terminal WebSocket — which drives a real
  shell — enforces an Origin allow-list before accepting
  ([`routes_terminals.py`](../backend/agentflow/api/routes_terminals.py)). A
  missing Origin (native clients, tests) is intentionally allowed; see residual
  risks.
- **Workspace confinement.** File read/write resolves and confines paths to the
  selected workspace and refuses `.env` files and binaries
  ([`workspace.py`](../backend/agentflow/workspace.py)). `config.set_workspace`
  refuses the filesystem root and `$HOME`.
- **Command execution.** No `shell=True` anywhere; subprocesses use explicit
  `argv` lists ([`process_runner.py`](../backend/agentflow/process_runner.py),
  [`terminal_service.py`](../backend/agentflow/terminal_service.py)). Command
  templates substitute `{prompt}`/`{model}` as discrete argv elements parsed with
  `shlex`, never interpolated into a shell. Git commands use the `--` separator to
  prevent argument injection ([`git_service.py`](../backend/agentflow/git_service.py)).
- **Auto-executed commands.** Commands an agent emits via `agentflow-run`
  directives are classified by [`policy_service.py`](../backend/agentflow/policy_service.py)
  before running: shell operators, blocked binaries, inline-eval interpreters, and
  out-of-workspace paths are denied; remote/shared-state changes require explicit
  approval.
- **SSRF / preview.** The preview proxy confines target URLs to
  `localhost`/`127.0.0.1` ([`routes_preview.py`](../backend/agentflow/api/routes_preview.py)).
- **Secret handling.** Provider CLIs own their own auth; this app never reads or
  stores provider API keys. All log/command/event output passes through
  [`redaction.py`](../backend/agentflow/redaction.py), which masks PEM keys,
  GitHub/Slack/AWS/Google tokens, bearer tokens, `KEY=value` secret forms, and
  URL-embedded credentials.
- **Output rendering.** Agent output is untrusted and rendered through a custom
  React markdown component that builds elements (no `dangerouslySetInnerHTML` for
  agent text); the one `dangerouslySetInnerHTML` (Prism syntax highlighting) is
  fed Prism-escaped HTML. No agent/markdown output reaches the DOM as raw HTML.

## Secret handling

- Never commit secrets. `~/.agentflow` and `<workspace>/.agentflow` hold local
  state and are kept out of git (the per-workspace dir self-ignores).
- Do not put provider keys in `.env`; the app does not read them.
- Redaction is best-effort defense-in-depth, not a guarantee — do not paste
  secrets into chat or commands expecting them to be scrubbed everywhere.

## Known residual risks

Tracked honestly; see [audit/INITIAL_AUDIT.md](audit/INITIAL_AUDIT.md) for IDs.

- **Auto-run policy is a denylist (P1-05).** Commands like `make`, `node <file>`,
  `npx`, and `awk 'BEGIN{system(...)}'` are not recognized as dangerous and can
  auto-execute in the default mode via prompt injection. Hardened by moving
  high-risk exec forms to require-approval; consider running untrusted workspaces
  in `manual_approval` mode.
- **CSRF on simple-request endpoints (P1-09).** Addressed by an Origin/Referer
  middleware on mutating methods.
- **Structured event payloads were unredacted (P1-02).** A credential embedded in
  an approval-gated command could land in `events.json`/`approvals.json` and the
  SSE stream; redaction now extends to structured payloads.
- **WebSocket accepts missing Origin (P3-38).** Allows non-browser local clients
  to drive a shell. Acceptable for a loopback tool; documented, not closed.
- **Unauthenticated `/docs` and OpenAPI (P3-40).** Local only; harmless on
  loopback.
- **Workspace exec trusts project scripts (P2-09).** Selecting a workspace implies
  trusting its build scripts (`make`, `npm run`, …).

## Reporting

This is a personal/local tool. Report issues via the repository's issue tracker.
Do not include real secrets or exploit-ready details in public reports.

## Deployment-sensitive settings

- Keep the bind address at `127.0.0.1`. Do **not** expose the port to other hosts;
  there is no authentication and the app executes commands.
- If you reverse-proxy it, terminate at loopback and add your own auth in front.
- `AGENTFLOW_PORT` changes the port only; it does not change the bind address.
