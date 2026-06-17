# 05 — Verification

All commands below were executed during the rebuild and passed. Quality gates were
not weakened.

## Results

| Check | Command | Result |
|-------|---------|--------|
| Backend lint | `ruff check backend` | ✅ clean |
| Backend format | `ruff format --check backend` | ✅ clean |
| Backend types | `mypy` | ✅ no issues (41 files) |
| Backend tests + coverage | `pytest backend/tests --cov=agentflow` | ✅ **199 passed**, 64% |
| Frontend types | `tsc --noEmit` | ✅ clean |
| Frontend lint | `eslint .` | ✅ 0 errors |
| Frontend tests | `vitest run` | ✅ **35 passed** |
| Frontend build | `vite build` | ✅ built |
| One-shot gate | `make verify` | ✅ `verify passed` |

## Tests added for the rebuilt path

- [test_controller_protocol.py](../../backend/tests/test_controller_protocol.py) —
  every action type, unknown action, missing field, malformed JSON, oversized
  result, multiple blocks (last wins + count), prose-tolerant extraction, no block,
  unsupported version. **Invalid output yields a failure and no result.**
- [test_protocol_wiring.py](../../backend/tests/test_protocol_wiring.py) — the
  protocol is PRIMARY in `parse_*`; a valid v1 block drives the action; an invalid/
  non-matching block yields no directive and **never** falls back to legacy (a
  legacy `rm -rf /` block alongside an invalid v1 block is NOT executed); the v1
  block is stripped from prose; legacy still works when no v1 block exists.
- [test_io_contracts.py](../../backend/tests/test_io_contracts.py) +
  [ioContracts.test.ts](../../frontend/src/lib/ioContracts.test.ts) — typed input
  submission (destinations, references, intents), operational-event payload union,
  rejection of empty text / unknown destination / unknown payload / unsupported
  version (fail-safe).

## Streaming proof (Pillar 2, retained)

[test_pillars.py::test_pillar2_output_is_visible_before_process_exits](../../backend/tests/test_pillars.py)
deterministically proves a chunk is on the event bus **while the run is still
`running`** (before process exit) — it fails if content is only available after
completion. A companion test proves secrets never reach the live stream (redacted in
deltas). These remain valid for the rebuilt path (transport unchanged; SSE primary).

## Not verified in this stage

- The sequenced frontend UI rebuild (composer family, typed-event pipeline,
  ChatPanel decomposition) — see [04-migration.md](04-migration.md). Its behavior
  is best verified against the running app and is out of scope for this stage.
- A live controller emitting `CLITC_RESULT_V1` end-to-end through a real CLI was not
  run; the protocol is proven by unit tests against the parser + wiring. The legacy
  fallback guarantees no regression if a controller has not yet adopted the new
  contract.
