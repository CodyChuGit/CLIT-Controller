# Frontend

The web UI is a React 18 + Vite 5 single-page app under [frontend/src/](../frontend/src/),
styled with Tailwind and rendering live terminals with xterm. It is the cockpit for the
local backend: it never talks to anything but `127.0.0.1:8787` (the FastAPI server) and
holds no secrets of its own. This document covers how it is wired together and how to
extend it. For the product rationale behind the shared UI primitives, see
[docs/PILLARS.md](PILLARS.md) (especially Pillar 3 — readable presentation, and Pillar 4 —
consistent interfaces across every chat window). Coding conventions live in
[docs/ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md).

## Stack and where things run

- React `^18.3.1`, TypeScript `^5.5.4` (strict), Vite `^5.4.8`, Tailwind `^3.4.10`,
  Vitest `^2.1.2` + React Testing Library.
- Dev server: `:5180`, proxying `/api` (HTTP and WebSocket) to the backend — see
  [frontend/vite.config.ts](../frontend/vite.config.ts).
- Production build emits `frontend/dist`; in single-port mode the backend serves that
  directory on `:8787`.
- All page titles read "CLIT Controller IDE" ([frontend/index.html](../frontend/index.html)).

## Entry point and initialization

[frontend/src/main.tsx](../frontend/src/main.tsx) is the only entry:

- Creates the React root on `#root`, renders `<App/>` inside `<React.StrictMode>` and an
  app-level `<ErrorBoundary label="the app">`. A render-phase throw anywhere in the tree
  would otherwise blank the whole IDE; the boundary catches it and offers a recoverable
  fallback (audit P1-08).
- Imports the global stylesheet `./styles.css` (Tailwind layers + component classes).
- Registers the app-shell service worker **only** when `import.meta.env.PROD` is true and
  `serviceWorker` exists. In dev it is skipped so it cannot interfere with Vite HMR;
  registration failures are swallowed (PWA shell caching is optional).

## App shell and state-based page routing

[frontend/src/App.tsx](../frontend/src/App.tsx) is the shell. **There is no React Router** —
the active page is a single `useState<PageId>` value, persisted to `localStorage` under the
`page` key and validated against the known `PAGE_IDS` on load (an unknown saved value falls
back to `projects`). The page id type lives with the nav rail in
[components/ActivityBar.tsx](../frontend/src/components/ActivityBar.tsx).

Layout: a left `ActivityBar` (VS Code-style icon rail, Settings gear pinned at the bottom),
a `main` content region that switches on `page`, a right-hand `ChatPanel`, and a bottom
`StatusBar`. Each region (`main`, the chat panel) is wrapped in its own `ErrorBoundary` so a
crash in one pane does not take down the others; the `main` boundary is keyed on `page` so
navigating away resets a crashed view.

The eight pages (each in [pages/](../frontend/src/pages/)):

| PageId | Label (rail) | Component |
| --- | --- | --- |
| `projects` | Explorer | `ProjectsPage` — file tree, editor tabs, git source-control panel |
| `agents` | Agents | `AgentsPage` — provider install/login/model/health cards |
| `tasks` | Tasks | `TasksPage` — orchestration runs, step timeline, queue |
| `terminals` | Terminals | `TerminalsPage` — live PTY sessions over WebSocket (xterm) |
| `preview` | Preview | `PreviewPage` — dev-server URL preview/start/stop |
| `usage` | Usage | `UsagePage` — per-provider budget/health + live usage windows |
| `logs` | Logs | `LogsPage` — run ledger / event log console |
| `settings` | Settings | `SettingsPage` — routing, command templates, config paths |

`App` also owns app-wide state that must survive page switches: the current project,
backend-reachable flag, git/usage/queue status (refreshed on workspace/page change and on a
20s interval), and the **editor model** — open files, the active path, and unsaved drafts
keyed by path. Open tab paths (excluding transient diff views) are persisted per workspace
under `tabs:<workspacePath>`; switching workspaces clears the model and re-reads the
remembered files fresh. A `wsRef` guard discards in-flight responses from a previous
workspace landing late. Pages that need a workspace (`tasks`, `terminals`, `preview`,
`usage`, `logs`) show a "Choose a workspace" prompt until one is selected.

## API client

[frontend/src/api.ts](../frontend/src/api.ts) is the single centralized client. Every backend
call goes through a private `request<T>()` helper that prefixes `/api`, sets
`Content-Type: application/json`, and on a non-OK response throws an `ApiError` carrying the
HTTP `status` and the parsed `detail` field (falling back to status text). Thin `get`/`post`
wrappers build on it. The exported `api` object groups endpoints by domain (projects, agents,
tasks, usage, logs, terminals, queue, durable state / events / runs / approvals, preview,
chat). Components catch `ApiError` and surface `.message`; nothing else constructs fetch
calls directly. Live PTY terminals and the SSE event stream are the only paths that bypass
this object (they use WebSocket / `EventSource` directly).

## Event store (live output)

[frontend/src/stream.tsx](../frontend/src/stream.tsx) holds the one workspace-scoped
subscription to the backend event bus, shared by every surface that shows live agent output.
The backend owns streaming (redaction, ordering, durability); the frontend just accumulates.

- `EventStreamProvider` (mounted once at the app root, keyed on `workspacePath`) opens a
  single SSE connection to `/api/events/stream?cursor=…`. If `EventSource` is unavailable or
  never connects, it falls back to **polling** `/api/events` every 1.5s; a transient SSE drop
  shows a degraded "polling" state while the browser auto-reconnects. Connection state is
  `live | polling | off`.
- `StreamStore` is a plain external store. It dedupes/resumes by monotonic event `id`
  (cursor), routes events: text deltas (`run.output`, `run.stderr`, `chat.delta`,
  `controller.delta`) accumulate into per-run `stdout`/`stderr` (capped to a 300k tail — full
  output lives in on-disk logs); lifecycle and structural events bump a `structuralRev`
  counter and append to a capped `recent` ring. `run.heartbeat` only advances the cursor.
  Notifications are coalesced to one `requestAnimationFrame` flush so rapid deltas do not
  thrash React, without batching so hard the user waits for full output.
- Components subscribe via `useSyncExternalStore` hooks: `useConnection()`,
  `useStructuralRevision()` (add to a poll effect's deps to refetch snapshots event-driven),
  `useRunStream(runId)`, `useRecentEvents()`.

**Boundary validation.** SSE and polling both deliver arbitrary JSON. Every frame passes
through `coerceStreamEvent()` ([lib/streamEvent.ts](../frontend/src/lib/streamEvent.ts))
before the store ingests it: a frame missing the load-bearing `id` (number) and `type`
(string) is dropped (returns `null`); all other fields are normalized to their declared
shape. This is the Pillar 5 network trust boundary (P2-14) — the store never ingests an
unvalidated frame. See [docs/text-streaming-across-the-board.md](text-streaming-across-the-board.md).

## Persistence

[frontend/src/persist.ts](../frontend/src/persist.ts) is two tiny `localStorage` helpers,
`loadState<T>(key, fallback)` and `saveState(key, value)`, namespaced under `agentflow.`.
Both swallow exceptions (private mode, quota) so UI state that fails to persist degrades
silently. Used for the active page and per-workspace open tabs; this is UI state only, never
agent data (that lives in the backend's JSON ledgers).

## Shared presentation primitives (Pillar 4)

These are the shared-ownership components: every chat/output surface composes them rather
than re-rendering markdown, timelines, or raw output itself. See
[docs/task-controller-io-surface.md](task-controller-io-surface.md) for the I/O alignment
rules they enforce.

- **`Markdown`** ([components/Markdown.tsx](../frontend/src/components/Markdown.tsx)) — the
  one markdown renderer for all agent prose (chat bubbles and step outputs alike): headings,
  lists, tables, code blocks, and pipeline-step chips (`STEP_META` maps each role to a hue).
  It builds React elements from parsed text and **never** uses `dangerouslySetInnerHTML`, so
  hostile HTML in untrusted agent output renders as inert text (pinned by
  [Markdown.test.tsx](../frontend/src/components/Markdown.test.tsx), finding P3-37).
- **`displayModel`** ([lib/displayModel.ts](../frontend/src/lib/displayModel.ts)) — the
  deterministic projection layer. Maps the structured records the backend already emits (task
  events, run/queue/approval lifecycle stream events) into a fixed `CardModel` taxonomy
  (`CardType` + `Severity` + style). `cardFromTaskEvent` and `cardFromStreamEvent` select the
  card; freeform agent prose is never re-parsed to decide UI state.
- **`TimelineCard`** ([components/TimelineCard.tsx](../frontend/src/components/TimelineCard.tsx)) —
  the single card renderer for both the controller dock (`density="compact"`) and the Tasks
  page (`density="detailed"`). Driven entirely by a `CardModel`, so the same state looks
  identical at both densities.
- **`RawDetail`** ([components/RawDetail.tsx](../frontend/src/components/RawDetail.tsx)) — the
  shared paginated, read-only viewer for machine-readable detail (prompts, stdout, stderr,
  logs, JSON, events, directives, diffs) with filter, copy, and diff coloring. For ANSI
  stream kinds it normalizes escapes via [lib/ansi.ts](../frontend/src/lib/ansi.ts).
- **`Composer`** ([components/Composer.tsx](../frontend/src/components/Composer.tsx)) — the one
  prompt composer (context chips, optional leading control, textarea with Enter-to-send /
  Shift+Enter newline, send/stop button) shared by the controller dock and Tasks
  continuation/retry/reroute.
- **`SmoothStreamingText`** ([components/SmoothStreamingText.tsx](../frontend/src/components/SmoothStreamingText.tsx)) —
  presentation-only smoothing that reveals newly-appended characters over animation frames so
  output reads like a live CLI stream. It owns no state and opens no connection — it consumes
  the already-redacted, already-accumulated text from the event store and respects
  `prefers-reduced-motion`. See [docs/streaming-renderer-decision.md](streaming-renderer-decision.md).
- **`lib/ansi`** ([lib/ansi.ts](../frontend/src/lib/ansi.ts)) — `stripAnsi`/`hasAnsi` for
  normalizing CLI escape sequences in prose views (Pillar 3). Live xterm terminals keep
  their ANSI; this is only for the normalized text views.
- **`useAutoScroll`** ([hooks/useAutoScroll.ts](../frontend/src/hooks/useAutoScroll.ts)) —
  follow-the-tail scrolling that stops following when the user scrolls up to read and exposes
  `atBottom` for a "jump to bottom" affordance.
- **`ErrorBoundary`** ([components/ErrorBoundary.tsx](../frontend/src/components/ErrorBoundary.tsx)) —
  reusable boundary wrapping the app and each major pane; renders a labelled fallback with
  Try-again / Reload.

## Styling

Tailwind (`darkMode: "media"`) with semantic color tokens in
[frontend/tailwind.config.js](../frontend/tailwind.config.js) — `surface` (canvas) and
`accent` (blue-600) — so raw hex stays out of components. Reusable component classes live in
the `@layer components` block of [frontend/src/styles.css](../frontend/src/styles.css):
`.card`, `.btn`/`.btn-primary`/`.btn-secondary`/`.btn-danger`/`.btn-xs`, `.icon-btn`,
`.input`, `.select`, `.label`, `.section-title`, `.mono-block`, `.chip`, `.skeleton`, and a
shared `.focusable` ring. Dark mode follows the OS; the file also defines the editor's
syntax-highlight palette (VS Code Light+/Dark+) and respects `prefers-reduced-motion`. New UI
should reuse these classes and tokens rather than introducing one-off colors. The repo-root
[DESIGN.md](../DESIGN.md) is the canonical style guide; these tokens and component classes
are the design system of record.

## Strict TypeScript

[frontend/tsconfig.json](../frontend/tsconfig.json) sets `strict: true`, plus
`noUnusedLocals`, `noUnusedParameters`, and `noFallthroughCasesInSwitch`; `noEmit` (Vite/esbuild
transpile, `tsc` is type-check only). Shared shapes live in
[frontend/src/types.ts](../frontend/src/types.ts) and mirror the backend contracts. `any` is
not used; unknown external data (e.g. stream frames) is typed `unknown` and narrowed at the
boundary (`coerceStreamEvent`). `import.meta.env` types come from `vite/client` via
[frontend/src/vite-env.d.ts](../frontend/src/vite-env.d.ts).

## Environment

The frontend reads only Vite's built-in `import.meta.env`:

- `import.meta.env.PROD` — gates service-worker registration ([main.tsx](../frontend/src/main.tsx)).

There are no custom `VITE_*` variables; the API base is always the relative `/api` (dev proxy
or same-origin in production), so no backend URL is configured at build time.

## Testing

Vitest + React Testing Library, jsdom environment, globals enabled, global setup at
[frontend/src/test/setup.ts](../frontend/src/test/setup.ts) (loads jest-dom matchers) — all
configured in [vite.config.ts](../frontend/vite.config.ts). Current test files:
[ansi.test.ts](../frontend/src/lib/ansi.test.ts),
[streamEvent.test.ts](../frontend/src/lib/streamEvent.test.ts),
[taskFormat.test.ts](../frontend/src/lib/taskFormat.test.ts),
[useAutoScroll.test.ts](../frontend/src/hooks/useAutoScroll.test.ts),
[ErrorBoundary.test.tsx](../frontend/src/components/ErrorBoundary.test.tsx),
[Markdown.test.tsx](../frontend/src/components/Markdown.test.tsx).

Run them:

```bash
npm --prefix frontend run test        # one-shot
npm --prefix frontend run test:watch  # watch mode
```

**Add a test:** create `<name>.test.ts` (pure logic) or `<name>.test.tsx` (component) next to
the unit under test. Import `describe`/`it`/`expect` from `vitest` and `render`/`screen` from
`@testing-library/react` (jest-dom matchers are already global). Favor pure helpers in
`lib/`/`hooks/` (e.g. `isNearBottom`, `stripAnsi`, `coerceStreamEvent`) — they are the easiest
to test without mounting. For components, assert on rendered text/DOM, not internals.

## Build, lint, typecheck

From the repo root, the Makefile targets drive everything (same locally and in CI):
`make lint`, `make typecheck`, `make test`, `make build`, `make verify`. The underlying
frontend scripts ([frontend/package.json](../frontend/package.json)):

```bash
npm --prefix frontend run lint        # eslint .
npm --prefix frontend run typecheck   # tsc --noEmit
npm --prefix frontend run build       # tsc && vite build -> frontend/dist
npm --prefix frontend run format      # prettier --write
npm --prefix frontend run dev         # vite dev server on :5180
```

`build` runs `tsc` first, so a type error fails the build.

## How to extend

- **Add a page:** add the id to the `PageId` union and the nav list in
  [components/ActivityBar.tsx](../frontend/src/components/ActivityBar.tsx), add the same id to
  `PAGE_IDS` in [App.tsx](../frontend/src/App.tsx), create `pages/<Name>Page.tsx`, and render
  it in the `page === …` switch inside the keyed `ErrorBoundary`. If it needs a workspace, add
  it to the `needsWorkspace` guard.
- **Add an API call:** add a typed method to the `api` object in
  [api.ts](../frontend/src/api.ts) (use the `get`/`post` helpers and a return type from
  `types.ts`); never call `fetch` directly from a component. Handle `ApiError` at the call
  site.
- **Add a component:** put shared, cross-surface UI in `components/` and reuse the styling
  classes/tokens. If it renders agent output, compose the existing primitives (`Markdown`,
  `TimelineCard`, `RawDetail`, `SmoothStreamingText`) instead of re-implementing them — that
  is the Pillar 4 contract.
- **Add a feature that consumes live events:** read from the shared store via the
  `stream.tsx` hooks; do not open a second `EventSource`. New event types map to cards in
  `displayModel`'s `STREAM_EVENT_MAP` / `TASK_EVENT_MAP`.

## Known limitations

A summary of the frontend's open items; the full cross-cutting list is in
[LIMITATIONS.md](LIMITATIONS.md).

- **Oversized files.** [ChatPanel.tsx](../frontend/src/components/ChatPanel.tsx) (~980 lines)
  and [TasksPage.tsx](../frontend/src/pages/TasksPage.tsx) (~530 lines) carry more logic than
  is comfortable; ongoing extraction has split task UI into
  [pages/tasks/](../frontend/src/pages/tasks/) (`StepChat`, `TaskFlowChart`,
  `TaskStatusPanels`, `taskPageModel`), but the top-level files remain large.
- **Auto-scroll consolidation is partial.** `useAutoScroll` is the shared hook (Pillar 4) but
  is not yet adopted by all live-output surfaces; some still scroll independently. See
  [docs/PILLARS.md](PILLARS.md) Pillar 4.
- **No router / no deep links.** Page state is a single value in `localStorage`; there are no
  URLs per page, so navigation cannot be bookmarked or shared and the browser back button does
  not move between pages.
- **Local-only by design.** The UI assumes a loopback backend with no auth and renders a
  "Backend not reachable" banner otherwise; it is not built to run against a remote origin.
