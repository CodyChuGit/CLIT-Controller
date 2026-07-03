# Feature Status

This is the current implemented feature inventory for CLIT Controller IDE.
Historical notes were removed; this document describes the working app.

## Implemented

| Area | Status |
| --- | --- |
| Workspace selection | Single active workspace stored in `~/.agentflow/config.json`; workspace state under `<workspace>/.agentflow/`. |
| Explorer and editor | File tree, file read/save, persistent editor tabs, unsaved drafts, git status, diffs, stage, unstage, commit. |
| Provider detection | Detects git, `gh`, `codex`, `claude`, `agy` / `antigravity`, Ollama, and MLX entry points. |
| Provider setup | Check, install, login helper, model picker, and cached provider state. |
| Agent Dock | Right-hand control center with controller tab, provider PTY tabs, compact activity cards, approvals, terminal drawer, command palette, and status footer. |
| Controller chat | Runs through the selected controller CLI and streams live output. Default controller role is `claude`. |
| Direct provider terminals | Provider tabs use real PTY sessions through xterm.js, with lifecycle diagnostics. |
| Typed input route | `/api/chat/submit` dispatches explicit controller/provider/task destinations from `InputSubmission`. |
| Context Intelligence | Shipped Phase 1 preview/benchmark APIs with tests; live-prompt wiring is a later phase. |
| Controller protocol | `CLITC_RESULT_V1` is the primary action protocol; invalid result blocks mutate no state. |
| Legacy directive fallback | `agentflow-*` directives are still honored only when no `CLITC_RESULT_V1` block is present, with a compatibility event. |
| Controller actions | answer, create task, queue steps, run command, request approval, request user, retry, reroute, complete task, cancel. |
| Tasks | Task folders, markdown handoff files, step execution, full-sequence run, provider-lane dispatch map, continuation input, raw detail, changed-file and artifact review. |
| Queue | Durable queue, one active item per provider, retry, skip, reroute, remove, clear, blocked/approval states, closed-loop controller consults. |
| Approvals | Durable command approvals with approve/reject endpoints and UI cards. |
| Live streaming | One workspace event store over SSE plus polling fallback; run/chat/controller/command/task/queue/approval events stream live. |
| Logs | Redacted global log entries and active run tails. |
| Preview | Start, stop, check, and monitor a localhost preview/dev server. |
| Usage | Manual health, local counters, routing recommendations, and best-effort live quota for supported CLIs. |
| Settings | Routing, command templates, model settings, Headroom, Ponytail. |
| Headroom | In-process, fail-open input compression of bulky prompt context; enabled by default. |
| Ponytail | Prompt-level output discipline with `off`, `lite`, `full`, and `ultra` levels; `full` by default. |
| Recovery | Startup and workspace-select recovery settles runs, queue items, and task steps after restart. |
| Security controls | Localhost binding, CSRF/origin guard, terminal WS origin check, path confinement, subprocess argv execution, server-side redaction. |
| PWA/app shell | Production build includes manifest/service worker and can run single-port through FastAPI. |

## Provider Roles

| Role | Default Provider | Purpose |
| --- | --- | --- |
| Controller | `claude` | Traffic-control decisions and task consults. |
| PM | `codex` | Specs, implementation plans, final reviews. |
| Engineer | `claude` | Implementation and fixes. |
| QA | `antigravity` | Broad checks and QA. |

Settings can change routing, but the UI prevents Antigravity from being selected
as the controller. Stored configs that used Antigravity or Gemini as controller
are migrated forward.

## Compatibility Notes

- The workflow step id `gemini_qa` remains for existing task folders; it routes
  to the QA role, which defaults to Antigravity.
- The retired `gemini` provider name is migrated to `antigravity` in config and
  usage state.
- Some CLI live-usage data depends on what each provider exposes. Codex and
  Claude have best-effort live usage paths; Antigravity relies on manual health.
- Optional Ollama and MLX providers are detectable but not part of the
  controller/task provider set.
