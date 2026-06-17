# Roadmap

Forward-looking work for CLIT Controller IDE / AgentComposer, derived **only** from
evidence already in the repository: the audit's recommended next actions
([audit/FINAL_REPORT.md](audit/FINAL_REPORT.md) §6, §15, §16), the gaps in
[FEATURE_STATUS.md](FEATURE_STATUS.md), the partial (◐) acceptance criteria in
[PILLARS.md](PILLARS.md), the phased backend plan in
[orchestrator-backend/03-implementation-roadmap.md](orchestrator-backend/03-implementation-roadmap.md),
the product phases in [NEXT_STEPS.md](../NEXT_STEPS.md), and the README roadmap.

**Status convention.** Unless an item is already committed in repo docs (a phase
the implementation roadmap or README states as the intended direction), every entry
here is a **proposal**. Nothing in this file invents new strategy, dates, or
ownership. Items carry the original finding ID (e.g. `P1-01`) or source doc so each
can be traced back to its evidence.

The tiers below are sequencing, not priority within a tier:

1. [Immediate hardening](#1-immediate-hardening) — correctness/reliability gaps the
   audit left open, no new product surface.
2. [Near-term product completion](#2-near-term-product-completion) — finish features
   already partial/mocked or whose backend phase is committed.
3. [Medium-term improvements](#3-medium-term-improvements) — quality, accessibility,
   and architecture cleanups.
4. [Optional future](#4-optional-future) — explicitly speculative directions from
   `NEXT_STEPS.md` and the later backend phases.

---

## 1. Immediate hardening

Open items from the audit ([FINAL_REPORT.md §6, §15, §16](audit/FINAL_REPORT.md)).
These are correctness/reliability gaps with no new product surface. Proposals; none
is an active P0 defect.

- **Per-workspace ledger locking (P1-01 / P2-07).** Add a per-workspace lock around
  the JSON ledger read-modify-write to close the lost-update race between the
  threadpool and the dispatcher. The audit calls this the **highest-priority
  remaining item** and recommended next action #1. Today the durable ledgers
  ([state_store.py](../backend/agentflow/state_store.py)) use atomic writes but no
  cross-writer lock; the race is rare and largely self-correcting for one user.
- **Move dispatcher file I/O off the event loop (P2-02/06/08/12).** Offload the
  blocking file I/O in the dispatcher tick
  ([queue_service.py](../backend/agentflow/queue_service.py)) and curate the child
  process environment. Recommended next action #2.
- **Reap still-alive agent processes during restart recovery (P2-05).** Clean
  shutdown is covered (`RUNNER.cancel_all()`), but a hard crash can still leak a
  live agent process group; recovery needs pid-reuse-safe killing. Recommended next
  action #5; listed as a remaining risk in §15.

Documented residual risks the audit **accepted** for a loopback single-user tool
(see [SECURITY.md](SECURITY.md)) — listed here so they are not re-discovered as new
findings, not proposed for change:

- WebSocket allows a missing `Origin` (P3-38) and `/docs` is unauthenticated
  (P3-40) — accepted by design.
- Dev-only `esbuild`/`vite` advisory (P3-23) — not in the production bundle; a fix
  would require a breaking Vite major upgrade.

---

## 2. Near-term product completion

Finish features that are already **Partial** or **Mocked** in
[FEATURE_STATUS.md](FEATURE_STATUS.md), or whose backend phase is stated as intended
direction in [03-implementation-roadmap.md](orchestrator-backend/03-implementation-roadmap.md).

### Per-pillar next steps (the ◐ items in [PILLARS.md](PILLARS.md))

- **Pillar 1 — token/latency metrics dashboard.** Context-prep latency,
  time-to-first-token, and original-vs-optimized token counts are already defined as
  the versioned `TokenEfficiencyReport` contract
  ([contracts.py](../backend/agentflow/contracts.py)) but are **not yet surfaced as a
  dashboard**. Proposal: build a UI surface that reads the report and shows realized
  Headroom savings (unmeasured values stay `null`, never fabricated).
- **Pillar 4 — auto-scroll consolidation.** [useAutoScroll.ts](../frontend/src/hooks/useAutoScroll.ts)
  exists with a pure tested core but is **not yet adopted at all six legacy call
  sites**, and reduced-motion is honored in streaming text but not audited on every
  surface. Proposal: migrate the remaining call sites to the shared hook and audit
  reduced-motion across surfaces.
- **Pillar 5 — native structured output.** The orchestrator still *emits* markdown
  directive blocks that are then validated. Proposal (explicitly named as the
  recommended next step in PILLARS.md): have the controller emit **native structured
  output** (provider structured-output mode) instead of markdown directive blocks,
  while keeping the validated-record path
  (`chat_directives.controller_directive_records`) as the contract.
- **Pillar 5 — wire result/summary contracts to live producers/consumers.** The
  result/summary schemas (CommandSummary, TestSummary, TaskSummary, AgentHandoff,
  ApprovalRequest, FailureRecord, TokenEfficiencyReport) are **Mocked** today:
  defined and `validate()`-tested, but no live emitter produces them and no UI reader
  selects on their `kind`. Proposal: add a live producer in the run/step path and a
  `displayModel`-driven reader so the schemas leave schema-only status. Closely
  related: move the directive-form contracts onto the live chat path so the legacy
  `parse_*` parsers are no longer the sole driver (FEATURE_STATUS "Partial").
- **Pillar 3 — CLI normalization beyond ANSI.** Classification of compiler/test/lint
  output into a single Command surface is partial. Proposal: extend normalization so
  these collapse into the existing Command card taxonomy
  ([displayModel.ts](../frontend/src/lib/displayModel.ts)).

### Other partial/mocked features

- **Frontend runtime response validation (P2-14).** The frontend trusts backend
  responses with no runtime schema validation (a §15 remaining risk). Proposal
  (recommended next action #3): introduce zod validation at the
  [api.ts](../frontend/src/api.ts) boundary, starting with the `StreamEvent` path,
  plus per-request stale-guarding (P2-15).
- **Live quota for Antigravity.** `live_usage` returns real data only for Codex and
  Claude; Antigravity exposes no headless usage call, so it relies on a manual limit
  ([FEATURE_STATUS.md](FEATURE_STATUS.md) "Live quota from CLIs"). Proposal: adopt an
  exact provider usage API for Antigravity if/when one exists, replacing the manual
  health toggle (also a `NEXT_STEPS.md` Phase 3 item).
- **Final task report + export (backend Phase 8).** The implementation roadmap's
  Phase 8 commits to generating a final task report from events/artifacts/runs/git
  diff and exporting a task folder to markdown/HTML. Proposal to complete: this is
  the "shareable task reports" item in both `NEXT_STEPS.md` Phase 3 and the README
  roadmap.
- **Context builder + prompt compression (backend Phase 7).** Phase 7 commits to a
  context builder that selects task files/paths/git status/excerpts per step, prompt
  budget estimates, artifact validation, and prompt compression for long histories
  (also `NEXT_STEPS.md` "Prompt compression"). Proposal to complete.

---

## 3. Medium-term improvements

Quality, accessibility, and architecture cleanups recorded in the audit and design
notes. Proposals.

- **Accessibility trio (P2-19/20/21).** Recommended next action #4: command-palette
  focus trap, `aria-live` for streaming replies, and ARIA-widget keyboard support.
  App-wide and per-pane error boundaries already shipped (P1-08); these deepen a11y.
- **Decompose oversized components (P2-18).** Extract hooks from large components
  (ChatPanel / TasksPage) to keep them maintainable.
- **Preview-iframe sandbox (P2-16).** Tighten the preview iframe sandbox
  ([PreviewPage.tsx](../frontend/src/pages/PreviewPage.tsx)); grouped with the
  frontend P2-14/15 items in the audit.
- **Reconcile project naming + consolidate launcher scripts (P2-25/27).**
  Recommended next action #6: the product is referred to as both "CLIT Controller
  IDE" and "AgentComposer", and there are redundant launcher/bundle scripts.
- **HTTP-level route tests + provider-install test isolation (P2-30 / P3-43).**
  Fill the testing gaps the audit left open (current suite is service-level heavy);
  some features still have no dedicated test module (e.g. preview dev-server).

---

## 4. Optional future

Explicitly speculative directions. These come from the later phases of
[03-implementation-roadmap.md](orchestrator-backend/03-implementation-roadmap.md)
and the Phase 2/3 lists in [NEXT_STEPS.md](../NEXT_STEPS.md). Proposals only; none is
committed beyond being named as a direction.

- **Provider adapter layer (backend Phase 3).** Move executable detection, model
  options, command rendering, auth hints, install commands, and failure
  classification behind a per-provider adapter contract with capability flags, so
  adding a provider needs a new adapter rather than changes in task dispatch. Would
  give the currently-partial **Ollama** and **omlx** providers a real orchestration
  path (today they are detectable/installable but not in `AGENT_PROVIDER_IDS`).
- **VS Code-style Agent Dock + Tasks tab parity (backend Phase 9).** Evolve the dock
  and Tasks tab into full provider-tabbed parity surfaces, without embedding VS Code
  (no `.vsix`, webviews, or `vscode://` links — see Phase 9's explicit exclusions).
- **Local summarizer / cheap routing (Ollama / MLX).** `NEXT_STEPS.md` Phase 2 and
  Phase 7's "local summarizer hooks." Reserved use for the currently-partial Ollama
  and omlx providers: local log digests and cheap routing.
- **Local voice I/O — Planned.** Dictation + spoken summaries (MLX Parakeet STT +
  `mlx-swift-dots-tts`), described in [local-voice-io.md](local-voice-io.md) and
  Phase 1.5. **No implementation exists today** (FEATURE_STATUS: Planned).
- **MCP adapter layer.** Expose tasks/usage as MCP tools — `NEXT_STEPS.md` Phase 2
  and backend Phase 8, explicitly sequenced "after the backend state contracts are
  stable."
- **Project templates.** Preconfigured routing + command templates per stack
  (`NEXT_STEPS.md` Phase 1, backend Phase 8).
- **Designer/product workbench items (Phase 1.5).** UI/UX reference library +
  reference-extraction tool, richer designer task briefs, and Calendar-Scheduler
  overflow handoff — see
  [phase-1-5-product-workbench.md](phase-1-5-product-workbench.md) and the README
  roadmap. Experimental product direction.
- **Desktop packaging.** Tauri desktop app, optional SwiftUI shell, Zed
  integration/extension, team mode, model-router plugin system — `NEXT_STEPS.md`
  Phase 2/3. Most speculative tier; the current app-mode launcher is intentionally
  PWA + Chrome `--app` only (no Electron/Tauri/native packager — backend Phase 10
  exclusions).

---

## Related documents

- [audit/FINAL_REPORT.md](audit/FINAL_REPORT.md) — source for §1 hardening items
  (recommended next actions, findings not fixed, remaining risks).
- [FEATURE_STATUS.md](FEATURE_STATUS.md) — per-feature Partial/Mocked/Planned status.
- [PILLARS.md](PILLARS.md) — the per-pillar ◐ acceptance criteria.
- [orchestrator-backend/03-implementation-roadmap.md](orchestrator-backend/03-implementation-roadmap.md)
  — the committed phased backend plan.
- [NEXT_STEPS.md](../NEXT_STEPS.md) — product phase lists (Phase 1/2/3).
- [SECURITY.md](SECURITY.md) — accepted residual risks for the loopback single-user
  model.
</content>
</invoke>
