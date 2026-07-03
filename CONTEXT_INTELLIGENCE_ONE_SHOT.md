# ONE-SHOT // AgentComposer Native Context Intelligence System (v2)

You are running inside the `AgentComposer` / CLIT Controller IDE repo.

Implement the first working version of CLITC's Native Context Intelligence
System. This is an implementation task, not a planning-only task.

This file is the single authoritative brief. If you find any other document in
this repository describing a "Context Intelligence" system, ignore it — this
version supersedes it.

## Current Repo Context

Preserve the existing architecture:

- Backend package: `backend/agentflow` (FastAPI app: `backend/agentflow/app.py`)
- Frontend: `frontend/src` (React + Vite + Tailwind)
- Controller protocol: `CLITC_RESULT_V1` in `controller_protocol.py`, executed by
  `backend/agentflow/controller/engine.py` + `actions.py`
- Live stream: `process_runner.py` -> `event_bus.py` -> `frontend/src/stream.tsx`
- PTY terminals: `terminal_service.py` + `frontend/src/components/TerminalPane.tsx`
- Ponytail (output-side prompt discipline): `backend/agentflow/ponytail.py`
- Headroom (input-side compression): `backend/agentflow/headroom_service.py` —
  **an in-process library wrapper, NOT a proxy**. There is no Headroom proxy in
  this codebase (it was deliberately retired). The local API already exists:
  `await headroom_service.compress_context(text, instructions)` — fail-open,
  threaded, with session stats in `headroom_service.status()`.

Do not rewrite Agent Dock, Tasks, queue dispatch, terminals, or provider
execution.

**Phase 1 is preview/benchmark only. Do NOT modify `chat_service.py`,
`prompt_templates.py`, or any live prompt path.** The pipeline ships as a
standalone typed system with its own API routes; wiring it into live controller
turns is a later phase. "Existing CLITC behavior still works" is an acceptance
criterion — the safest way to satisfy it is to not touch the live paths at all.

## Goal

Create a native typed context pipeline that can:

1. accept a user task
2. apply Ponytail behavior policy
3. build a repo map
4. rank/select relevant files
5. include changed git files and diff context
6. summarize terminal/log context
7. include compact session/project memory
8. compress context through a native compression interface
9. build a stable prompt package
10. measure tokens before/after compression
11. write an optimization report
12. benchmark context strategies locally

## Backend Implementation

Add:

```text
backend/agentflow/context_intelligence/
  __init__.py
  types.py
  pipeline.py
  behavior.py
  repo_map.py
  file_ranker.py
  git_context.py
  log_context.py
  compression.py
  memory.py
  prompt_builder.py
  metrics.py
  reports.py
  benchmarks.py
```

Use **Pydantic v2 models** (the repo convention — see `controller_protocol.py`,
`models.py`, `contracts.py`; do not use plain dataclasses) for:

```text
UserTask
BehaviorPolicy
RepoMapEntry
RepoMap
FileContext
GitContext
LogContext
MemoryContext
ContextSelection
ContextPackage
TokenBudget
CompressionResult
PromptSection
PromptPackage
TokenUsage
OptimizationReport
SessionDigest
BenchmarkCase
BenchmarkResult
```

`ContextPackage` is the selected raw material; `PromptPackage` is the rendered,
ordered result. Keep that distinction.

## Hard Rules

- **No new dependencies.** Everything here is achievable with the standard
  library plus packages already in `pyproject.toml` (`headroom-ai` included).
  Do not add tiktoken, embeddings, vector stores, or anything else.
- No network calls. No external LLM calls. No vector DBs or embeddings.
- **Reuse existing seams instead of re-implementing them** (each is named in
  its section below): `workspace.py` for walking/reading files, `git_service`
  for git data, `process_runner` for logs, `headroom_service` for compression,
  `redaction.redact` for output safety, `paths.workspace_app_dir` for storage.

## Required Behavior

- Ponytail owns behavior policy. Read `ponytail.level()` and `ponytail.block()`,
  then expose a structured `BehaviorPolicy`. When the level is `off`, the
  policy section must be empty — matching how live prompts behave today.
- Do not duplicate Ponytail rules elsewhere.
- Native compression is a small internal interface (a Protocol or ABC) with
  exactly two implementations:
  1. `SimpleDeterministicCompressor` (new): whitespace/blank-line collapsing,
     duplicate-line folding, long-run truncation with `[… N more lines]`
     markers. Pure functions, fully deterministic.
  2. The **existing** `headroom_service.compress_context` wrapped as
     `HeadroomCompressor`. Do NOT build a new Headroom adapter, proxy client,
     or a second call into the `headroom` package — call the service that
     already exists. It is async; the pipeline entry point is therefore async.
- Compression must preserve verbatim: the user task, file paths, symbol names,
  error messages, line numbers, and the Ponytail policy block. Only bulky
  context bodies (file excerpts, logs, diffs) may be compressed.

## Context Selection

Implement deterministic repo context selection:

- **Walk and read through `backend/agentflow/workspace.py`** — it already has
  `IGNORED_DIRS`, `scan_tree()`, `read_text_file()` (size caps), and
  `_resolve_in_workspace()` (path confinement, an audited security invariant).
  Extend `IGNORED_DIRS` locally if needed (caches, generated output); do not
  write your own `os.walk` + ignore list.
- refuse `.env` and any `.env.*` except `.env.example`
- detect Python symbols with `ast`
- detect TS/JS symbols with conservative regex (exported functions/classes/
  consts — do not attempt full parsing)
- rank files by task terms, paths, symbols, extensions, and git changes
- include reasons for selected files
- report top rejected candidates (with reasons)
- never dump the whole repo

## Git Context

Use the existing `backend/agentflow/git_service.py` (`git_info()`,
`file_diff()` — both async). Do not shell out to `git` directly.

## Log Context

Sources are exactly:

- `process_runner.get_log_entries()` (the bounded, already-redacted log buffer)
- recent `RUNNER.runs` records via their `to_dict()` tails

Do NOT read PTY terminal scrollback (`TERMINALS.sessions[*].buffer`): it is raw
ANSI bytes and the backend has no ANSI stripper (only the frontend does).

## Memory

There is no existing memory store — define `MemoryContext` as a deterministic
digest built from:

- recent controller chat history: `chat_service.load_chat(workspace)`
- recent task state: `task_service.list_tasks()` +
  `task_service.task_state_summary()` for the newest 1–2 tasks

Truncation and extraction only. Do not invent a new persistence layer.

## Token Metrics

Count tokens with the already-installed `headroom` package. The exact working
recipe (verified against headroom-ai 0.29 — `TokenCounter` itself is a Protocol
and cannot be instantiated):

```python
from headroom import count_tokens_text
from headroom.tokenizers import get_tokenizer

_counter = get_tokenizer("claude-sonnet-4-5-20250929")  # cached module-level
tokens = count_tokens_text(text, _counter)
```

Wrap it fail-open with a `len(text) // 4` estimate as the fallback so metrics
never crash the pipeline. Record which counter was used in `TokenUsage`.

## Prompt Builder

Build prompt sections in this exact stable order:

1. stable system instructions
2. stable CLITC rules
3. stable Ponytail behavior policy
4. project rules
5. session digest
6. repo map
7. selected files
8. git diff
9. terminal/log context
10. current user task

Add a test that fails if section order changes.

## Reports

- Persist under `paths.workspace_app_dir(workspace) / "context"` (this lands in
  `<workspace>/.agentflow/context/`, which is auto-gitignored).
- Report ids must match `^[A-Za-z0-9_-]+$`; generate them yourself (uuid hex is
  fine) and validate on read.
- **Everything persisted or returned by the API — prompt previews, file
  excerpts, log context, reports — must pass `redaction.redact()` first.**
  The `.env` refusal alone does not cover secrets inside logs or source files.
  This is an existing audit invariant in this repo.

## API

Add FastAPI routes in a new `backend/agentflow/api/routes_context.py`:

```text
POST /api/context/preview     body: {"task": str, "maxTokens": int | None}
POST /api/context/benchmark   body: {"task": str}
GET  /api/context/reports/{report_id}
```

- Use `require_workspace()` from `routes_projects.py`.
- **Register the router in `backend/agentflow/app.py`** alongside the other
  `include_router` calls (prefix `/api/context`, tag `context`).
- `GET .../reports/{report_id}`: reject ids that do not match
  `^[A-Za-z0-9_-]+$` with a 400 before touching the filesystem — same
  path-traversal defense class as the SPA route in `app.py`.

## Benchmarks

Compare exactly these three strategies on the same `BenchmarkCase` inputs:

1. `naive` — top-N whole files by simple term match, no compression
2. `ranked` — full ranking pipeline, per-file excerpt trimming, no compression
3. `ranked_compressed` — strategy 2 plus the compression interface

A `BenchmarkResult` records, per strategy: token count, selected-file count,
and required-content retention (did the packed output still contain the
must-keep strings the case declares — task text, named symbols, error lines).
Benchmark cases are local fixtures; no network.

## Frontend

If scope allows, add a compact Context Intelligence panel in Settings or Usage.

Minimum UI:

- task input
- selected files
- inclusion reasons
- rejected candidates
- tokens before/after
- savings percentage
- session digest preview
- report link/id
- prompt preview behind disclosure

If UI scope is too large, implement backend APIs first and document the exact
frontend integration point (which page, which component, which `api.ts`
methods) in `docs/FRONTEND.md`.

## Tests

Add deterministic backend tests (follow the existing style in `backend/tests`:
hermetic `tmp_path` workspaces via `config.ensure_workspace`, no fixture dirs,
no network, no external models) for:

- repo map generation (ignored dirs, `.env` refusal, confinement)
- file ranking (reasons present, rejected candidates reported)
- git context
- log summarization
- memory digest
- compression (both implementations; preservation guarantees; fail-open)
- prompt section order (the order-lock test)
- token metrics (headroom counter + fallback)
- benchmark reports (all three strategies, retention scoring)
- context routes (preview, benchmark, report fetch, bad report id -> 400,
  no-workspace -> 409)
- full pipeline fixture (task in -> report out)

## Docs

Update only current docs:

- `docs/API.md`
- `docs/BACKEND.md`
- `docs/DATA_MODEL.md`
- `docs/FEATURE_STATUS.md`
- `docs/FRONTEND.md` if UI is added

Do not recreate old roadmap, audit, or planning docs.

## Verification

Run `make verify` (mirrors CI: ruff format/lint, mypy, pytest, eslint,
prettier, tsc, vitest, build) and make it pass before declaring done.

## Acceptance Criteria

Done means:

- typed context intelligence package exists (Pydantic v2 models)
- preview API works; benchmark API works
- selected context is explained (reasons + rejected candidates)
- git diff is included when changes exist
- compression preserves the user task, file paths, symbols, errors, line
  numbers, and Ponytail policy
- token metrics show before/after counts (headroom counter, fail-open)
- reports are persisted under `<workspace>/.agentflow/context/` and redacted
- no live prompt path was modified (`chat_service.py`, `prompt_templates.py`
  untouched)
- no new dependencies were added
- `make verify` passes
- existing CLITC behavior still works

Begin by inspecting the repo, then implement the smallest complete version.
