# CODEX ONE-SHOT // AgentComposer Native Context Intelligence System

You are running inside the `AgentComposer` / **CLIT Controller IDE** repository.

You are a principal systems architect and staff-level implementation engineer.
This is an implementation task, not a brainstorming task and not a README-only
research task.

Your mission is to implement the first working version of CLIT Controller IDE's
**Native Context Intelligence System**, adapted to the architecture that already
exists in this repository.

## Current Repo Facts You Must Preserve

- Backend package: `backend/agentflow`, served by FastAPI.
- Frontend: `frontend/src`, React + Vite + Tailwind.
- Runtime state: `~/.agentflow/` and `<workspace>/.agentflow/`.
- App surfaces: Projects, Agents, Tasks, Preview, Usage, Logs, Settings, and the
  right-hand Agent Dock.
- Managed output stream: `backend/agentflow/process_runner.py` ->
  `backend/agentflow/event_bus.py` -> `frontend/src/stream.tsx`.
- Interactive provider terminals: `backend/agentflow/terminal_service.py` and
  `frontend/src/components/TerminalPane.tsx`.
- Controller protocol: `CLITC_RESULT_V1` in `controller_protocol.py`, applied by
  `backend/agentflow/controller/engine.py` and
  `backend/agentflow/controller/actions.py`.
- Default routing: controller `claude`, PM `codex`, engineer `claude`, QA
  `antigravity`.
- Ponytail already exists in `backend/agentflow/ponytail.py` and owns output-side
  behavior discipline.
- Headroom proxy management already exists in `backend/agentflow/headroom_service.py`.
  Do not rip it out. Add native context compression as a separate internal
  boundary that can coexist with the managed proxy.

Begin by reading these files:

```text
README.md
docs/ARCHITECTURE.md
docs/BACKEND.md
docs/FRONTEND.md
docs/API.md
docs/DATA_MODEL.md
docs/CONFIGURATION.md
docs/SECURITY.md
docs/AI_AGENT_GUIDE.md
backend/agentflow/ponytail.py
backend/agentflow/headroom_service.py
backend/agentflow/workspace.py
backend/agentflow/git_service.py
backend/agentflow/process_runner.py
backend/agentflow/event_bus.py
backend/agentflow/prompt_templates.py
backend/agentflow/controller/context.py
frontend/src/pages/SettingsPage.tsx
frontend/src/api.ts
frontend/src/types.ts
```

Do not browse external repositories by default. Use the current repo as the
source of truth. Aider, Continue, OpenHands, Headroom, and Ponytail may inform
the architecture conceptually, but do not copy their structures or add network
research as a dependency for this task.

## Core Goal

Build a minimal, typed, deterministic context pipeline that can preview,
compress, measure, and benchmark the context CLITC would send to an agent.

The long-term lifecycle is:

```text
user task
  -> CLIT Controller
  -> Ponytail behavior policy
  -> repo/file/git/log context selection
  -> session/project memory digest
  -> native compression
  -> prompt package
  -> existing provider routing / process runner
  -> existing event stream
  -> token metrics
  -> session digest update
  -> optimization report
```

The first implementation must create the foundation without rewriting agent
execution, terminal behavior, Agent Dock, or the controller protocol.

## Ownership Rules

Use exactly one owner for each responsibility:

| Responsibility | Owner |
| --- | --- |
| Behavior policy | `ponytail.py` plus a new Context Intelligence Ponytail adapter |
| Repo map, file ranking, changed-file context | new Context Intelligence context selector |
| Git diff extraction | new selector wrapping existing `git_service` behavior where useful |
| Terminal/log summarization | new Context Intelligence log summarizer |
| Native compression | new Context Intelligence compressor |
| Session/project memory | new Context Intelligence memory module |
| Prompt assembly | new Context Intelligence prompt builder |
| Provider routing | existing `routing_service.py`, `agent_commands.py`, `process_runner.py` |
| Streaming | existing `process_runner.py`, `event_bus.py`, and frontend `stream.tsx` |
| Token measurement | new Context Intelligence metrics module |
| Benchmarking | new Context Intelligence benchmark module |

Do not create a parallel streaming engine or a new agent runner. The new system
prepares context and prompt packages; the existing runner still owns execution.

## Backend Package Shape

Create a compact package under the existing backend package:

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

Keep it flat for the first version. Split into subpackages only if a file becomes
too large or the local style clearly demands it.

Add route support only after the service layer works:

```text
backend/agentflow/api/routes_context.py
```

Register it in `backend/agentflow/app.py` under `/api/context`.

## Required Typed Models

Use dataclasses or Pydantic models consistently for internal types. Avoid
untyped dictionaries except at HTTP or persistence boundaries.

Implement types for:

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

Every stage must take structured input and return structured output.

## Canonical Pipeline

Implement `pipeline.py` with a callable service similar to:

```python
def build_context_preview(workspace: Path, user_task: UserTask, *, budget: TokenBudget | None = None) -> OptimizationReport:
    ...
```

Pipeline stages:

1. Validate and normalize the user task.
2. Read Ponytail level and block through `ponytail.py`.
3. Convert Ponytail output into a `BehaviorPolicy`.
4. Build a bounded repo map.
5. Rank files by task relevance.
6. Include changed git files and a git diff summary.
7. Summarize provided terminal/log text, if any.
8. Read compact session/project memory, if present.
9. Build a `ContextPackage`.
10. Estimate tokens before compression.
11. Compress context through the native compressor interface.
12. Build a provider-stable `PromptPackage`.
13. Estimate tokens after compression.
14. Persist an optimization report.
15. Generate or update a compact `SessionDigest` only when requested by the
    route/service call.

## Ponytail Adapter

Ponytail owns behavior policy. Do not duplicate its behavior rules in the
selector, compressor, memory engine, or prompt builder.

Create an adapter that reads:

- `ponytail.level()`
- `ponytail.block(level)`

It should return a structured `BehaviorPolicy` containing:

- level
- instruction text
- whether the policy is active
- brief human-readable summary

The prompt builder includes this policy in a stable section. Other modules may
read the summary for scoring, but must not reimplement Ponytail's rules.

## Context Selector

Implement an Aider-inspired but repo-native selector.

Minimum behavior:

- Walk the selected workspace using the same ignore spirit as
  `backend/agentflow/workspace.py`.
- Ignore `.git`, `node_modules`, `.venv`, `venv`, `dist`, `build`, caches,
  generated frontend output, and `.agentflow` logs unless explicitly requested.
- Refuse `.env` files except `.env.example`.
- Build a lightweight repo map with path, extension, size, previewability, and
  detected symbols.
- Detect symbols deterministically:
  - Python: use `ast` for functions/classes.
  - TypeScript/JavaScript/TSX/JSX: use conservative regex for exported functions,
    classes, const components, and named declarations.
  - Markdown/config: headings and top-level keys where cheap.
- Rank files by task terms, path tokens, symbol names, extension relevance,
  current git changes, and existing task/controller context.
- Every included file must have an inclusion reason.
- Top rejected candidates must be reportable with rejection reasons.
- Do not send the whole repo.

## Git Context

Use existing git conventions from `git_service.py` where possible.

Git context must include:

- repo availability
- branch when available
- changed files
- diff stat
- bounded diff summary
- full diff only when it fits budget

Guardrails:

- Include git diff when the repo has changes.
- Preserve file paths and hunk headers.
- Redact output through existing redaction utilities.
- Never expose `.env` contents.

## Log Context

Implement deterministic log summarization.

Preserve:

- command
- exit code
- traceback/error block
- failed test names
- file paths
- line numbers
- final 80 lines

Discard or collapse:

- progress bars
- duplicate lines
- long install output
- irrelevant success output

Guardrails:

- Do not remove the only error block.
- Do not remove all file paths.
- Do not remove line numbers from failure context.

## Native Compression

Create an interface in `compression.py`:

```python
class ContextCompressor:
    def compress(self, package: ContextPackage, budget: TokenBudget) -> CompressionResult:
        ...
```

Implement:

```text
SimpleDeterministicCompressor
HeadroomNativeCompressor
```

`HeadroomNativeCompressor` should be an adapter boundary only unless a stable
local Headroom library API is already available in dependencies. Do not make
network calls. Do not require the existing proxy path.

`SimpleDeterministicCompressor` must work now and must:

- preserve the user task
- preserve Ponytail policy
- preserve file paths
- preserve symbol names
- preserve git diff hunks
- preserve error lines
- preserve line numbers
- trim low-ranked files first
- trim logs before selected source unless logs contain errors
- emit an explanation of what was removed

The existing `headroom_service.py` stays responsible for managed proxy routing.
The new native compressor is an internal context-prep stage.

## Memory Engine

Implement compact session digest generation.

A `SessionDigest` should include:

- task
- files touched
- important decisions
- commands run
- errors encountered
- fixes attempted
- current status
- next suggested step

Persist memory under workspace state, preferably through new helpers in
`paths.py`:

```text
<workspace>/.agentflow/context/session_digests.json
<workspace>/.agentflow/context/project_memory.json
```

Keep writes atomic. Keep digest size bounded.

## Prompt Builder

Prompt sections must be stable and cache-friendly:

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

Do not randomly reorder sections. Add a test that fails when section order
changes unexpectedly.

The prompt builder should return:

- prompt text
- sections with names and token estimates
- selected files
- compression details
- safe preview text for UI

## Token Metrics

Implement deterministic approximate token counting unless an exact tokenizer is
already available locally.

Metrics must track:

- estimated input tokens before compression
- estimated input tokens after compression
- estimated output tokens when available
- compression ratio
- selected file count
- selected context bytes
- prompt section token breakdown

Keep token counting behind a small interface so exact tokenizers can replace it
later.

## Benchmarks

Implement a local deterministic benchmark runner.

Compare these strategies:

1. naive full-context prompt
2. repo-map-only prompt
3. selected-context prompt
4. selected-context plus compression prompt
5. selected-context plus compression plus session digest prompt

Benchmark cases:

- small repo task
- long log task
- git diff task
- debugging task
- architecture task

Create minimal fixtures under `backend/tests/fixtures/context_intelligence/` if
none exist.

Benchmark output:

```text
case name
strategy
input tokens before
input tokens after
tokens saved
percentage saved
selected files
compression ratio
latency
quality guardrail result
```

Persist reports under:

```text
<workspace>/.agentflow/context/reports/<report_id>.json
<workspace>/.agentflow/context/reports/<report_id>.md
```

## HTTP API

Implement routes that fit the current FastAPI app:

```text
POST /api/context/preview
POST /api/context/benchmark
GET  /api/context/reports/{report_id}
```

Use `require_workspace()` from `routes_projects.py`. Add request/response types
either in `models.py` or in the route module, following local style.

Do not implement `POST /api/agent/run-contextual` in the first pass unless it is
trivially safe. If not implemented, document the exact integration point with
`chat_service.py`, `controller/context.py`, and `prompt_templates.py`.

## Frontend UI

Add the smallest useful UI. Prefer a compact Context Intelligence section in
Settings or Usage instead of a new navigation page.

Minimum UI:

- user task input for preview
- selected files
- reason each file was included
- top rejected candidates
- tokens before compression
- tokens after compression
- percentage saved
- session digest preview
- optimization report id/link
- prompt package preview behind a disclosure

Use existing frontend patterns:

- API wrappers in `frontend/src/api.ts`
- types in `frontend/src/types.ts`
- compact panels, not nested cards
- loading, empty, error, and retry states

If UI scope becomes too large, implement backend API first and add a clear TODO
in docs with the exact frontend integration point.

## Quality Guardrails

Add tests or benchmark assertions that fail when:

- selected context exceeds budget
- selected files are empty for code tasks
- git diff is omitted when repo has changes
- error logs are dropped
- prompt grows unexpectedly
- compression removes file paths
- compression removes line numbers from error context
- compression removes the user task
- compression removes Ponytail policy
- session digest exceeds configured size
- prompt section order changes unexpectedly

## Required Tests

Backend unit tests:

```text
backend/tests/test_context_repo_map.py
backend/tests/test_context_file_ranker.py
backend/tests/test_context_git_context.py
backend/tests/test_context_log_context.py
backend/tests/test_context_memory.py
backend/tests/test_context_compression.py
backend/tests/test_context_prompt_builder.py
backend/tests/test_context_metrics.py
backend/tests/test_context_benchmarks.py
backend/tests/test_routes_context.py
```

Integration tests:

- full pipeline with small fixture repo
- full pipeline with long log
- full pipeline with git diff
- benchmark report generation

All tests must be deterministic. No network calls. No external LLM calls.

Frontend tests are required only if UI is added.

## Documentation Updates

Update current docs, not old planning docs:

- `docs/API.md`
- `docs/BACKEND.md`
- `docs/FRONTEND.md` if UI is added
- `docs/DATA_MODEL.md`
- `docs/FEATURE_STATUS.md`
- `docs/CONFIGURATION.md` only if settings are added
- `docs/TROUBLESHOOTING.md` if new failure modes are introduced

Do not recreate removed roadmap/audit/planning documents.

## Development Rules

- Do not rewrite unrelated code.
- Do not break Agent Dock, Tasks, terminals, queue dispatch, or controller
  actions.
- Do not duplicate Ponytail.
- Do not replace existing Headroom proxy management.
- Do not require proxy mode for native compression.
- Do not add embeddings, vector databases, or new external services in this
  first pass.
- Do not make network calls in tests.
- Do not hide token calculations.
- Prefer deterministic heuristics before embeddings.
- Prefer explainable file ranking.
- Prefer local-first behavior.
- Preserve user changes already present in the worktree.

## Acceptance Criteria

The implementation is successful only if:

- `backend/agentflow/context_intelligence/` exists and has a typed pipeline.
- Ponytail has a clear adapter-owned place in context prep.
- Native compression exists and works without proxy mode.
- Existing `headroom_service.py` still manages proxy routing unchanged unless a
  small compatibility change is unavoidable.
- Repo context is selected and explained instead of dumping the whole repo.
- Git changes are included when present.
- Log summarization preserves errors, file paths, and line numbers.
- Prompt sections are stable and tested.
- Token usage is measured before and after compression.
- Benchmark reports prove token savings for deterministic fixtures.
- HTTP preview and benchmark endpoints work.
- Existing terminal, controller, queue, and streaming behavior still works.
- Targeted tests pass.

## Final Response Format

When finished, report:

1. implementation summary
2. files created
3. files modified
4. architecture hierarchy
5. execution pipeline
6. API routes added
7. how to run tests
8. how to run benchmarks
9. limitations
10. next implementation phase

Begin by inspecting the repository, then implement the smallest complete version
that satisfies the acceptance criteria.
