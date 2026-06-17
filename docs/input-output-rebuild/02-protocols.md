# 02 — I/O Protocols

The rebuild defines three validated, versioned contract layers. They are correlated
by IDs but never collapsed into one Markdown blob. The UI never infers application
behavior from narrative prose.

## Plane 3 — deterministic controller result (CLITC_RESULT_V1)

The authoritative machine-action protocol. Source:
[controller_protocol.py](../../backend/agentflow/controller_protocol.py).

The controller (an installed CLI, not a structured-output API) streams
human-readable reasoning, then emits **exactly one** sentinel-framed JSON result:

```text
...human-readable reasoning streams here as narrative...

<<<CLITC_RESULT_V1
{"schemaVersion":"1","kind":"controller_result",
 "message":{"summary":"Ready to implement.","details":["spec exists"]},
 "action":{"type":"queue_steps","taskId":"task-123","steps":["claude_implement"]}}
CLITC_RESULT_V1>>>
```

**Closed action union** (`type` discriminator): `answer`, `create_task`,
`queue_steps`, `run_command`, `request_approval`, `request_user`, `retry`,
`reroute`, `complete_task`, `cancel`. `ACTION_TYPES` is exported so the prompt
contract is generated from the schema and cannot drift.

**Parsing rules** (`parse_controller_result`):
- Prose-tolerant — surrounding narrative is ignored.
- Exactly one authoritative result; the **last** block wins, and the block count is
  reported in `meta.blocks` (>1 is a model-misbehaviour signal).
- Bounded size (`MAX_RESULT_BYTES = 16384`).
- Full validation before the result is actionable. Malformed JSON, unknown action,
  missing field, or unsupported `schemaVersion` → a typed `FailureRecord` and **no
  result**. Callers mutate **no** state from an invalid result.
- No business field is regex-parsed. `run_command`/`request_approval` carry a
  command STRING vetted by the existing policy classifier + argv runner at
  execution time — this module executes nothing and never touches a shell.

**Primacy + fallback** (`chat_directives.py`): every `parse_*` reads the protocol
first. When a v1 block is present, only it is honored — a valid block drives the
action; an invalid/non-matching block yields no directive and is **never** silently
downgraded to the legacy parsers. The legacy `agentflow` JSON / `agentflow-*`
markdown forms are parsed only when **no** v1 block exists (bounded migration
fallback). The v1 block is stripped from rendered prose; `controller_failure()`
exposes the typed failure to surface. Prompts teach only the v1 contract
(`result_contract_prompt()`); legacy generation was removed from normal operation.

## Plane 1 — input submission

The typed model every input surface produces. Source:
[io_contracts.py](../../backend/agentflow/io_contracts.py) (backend),
[ioContracts.ts](../../frontend/src/lib/ioContracts.ts) (frontend mirror).

`InputSubmission` makes destination and intent **explicit fields** rather than
ambient UI state or prose:

- `destination`: `controller | provider{provider} | task{taskId,intent}` —
  `intent ∈ continue|clarify|retry|fix|reroute|ask`.
- `content`: `{text, references[]}` where `InputReference` is a typed union
  (`file|folder|diff|task_artifact|run|event_range`).
- `behavior.submitMode`: `message|create_task|continue|retry|reroute`.
- `schemaVersion:"1"`; `validateSubmission()` rejects empty text and unsupported
  versions, fail-safe.

## Plane 2 — operational events

The application-owned event contract that replaces the open `{type, data}` dict as
the long-term shape. `OutputEventEnvelope` carries stable correlation IDs
(`taskId/runId/chatId/messageId/queueItemId/approvalId`), `channel`, `sequence`,
`redacted`/`truncated`, and a **discriminated `payload`** union (`narrative.delta`,
`command.started/output/completed`, `task.state`, `queue.state`,
`approval.requested/resolved`, `failure`, `cancellation`, `summary.ready`).
`validate_event()` / `validateOutputEvent()` reject unknown payload types and
versions. During migration the live bus still emits the legacy flat event; the
typed envelope is the validated target shape (see [04-migration.md](04-migration.md)).

## Plane 3 — summaries

Versioned, `kind`-discriminated summary contracts (test/build/QA/failure/task/
completion, agent handoff, token-efficiency) live in
[contracts.py](../../backend/agentflow/contracts.py) with safe `validate()`. They
reference full output by event range (`OutputRef`) rather than re-embedding it.

## Versioning

Every contract carries `schemaVersion`/`version`. Readers reject unknown versions
safely (no silent reinterpretation). Adding/altering a contract is a versioned
change.
