# Agent dependency-source map (opensrc extension)

**Date:** 2026-07-08 · **Status:** approved

## Goal

Agents read a dependency's *real* source instead of guessing its API. Today agent
prompts only advertise `opensrc path <pkg>`; agents must know the exact spec and
choose to run it — so they usually don't. This feature resolves the workspace's
**direct dependencies** to local source paths ahead of time and puts the concrete
`name → path` map in every agent prompt.

## Decisions (user-approved)

- **Delivery:** resolved local paths in the prompt (agents read files with their
  own tools). No source excerpts in-context — token cost stays near zero.
- **Scope:** direct deps from the workspace's manifests, resolved eagerly.
- **Trigger:** background resolution kicks off on **workspace select**
  (`routes_projects.set_workspace`); never blocks a request or a task.
- **Prompt:** when the map exists, it **replaces** the generic
  `opensrc path` capability line in `prompt_templates._compose`; until then the
  generic line stays as the fallback.

## New unit: `backend/agentflow/dependency_service.py`

One job: workspace → cached `{name: local_path}` of resolved direct deps.

- `resolved_deps(ws: Path) -> dict[str, str]` — read the cache (fast path; never
  resolves inline).
- `refresh(ws: Path) -> dict[str, str]` — parse manifests, resolve via
  `opensrc_service.fetch()` (which wraps `opensrc path`), write the cache.
  Skipped when opensrc is unavailable or no manifest is found.
- `start_background_refresh(ws: Path)` — daemon thread wrapping `refresh`;
  invoked from `set_workspace`. One in-flight refresh per workspace (a simple
  lock set); repeat calls while running are no-ops.

### Manifest discovery & parsing

Scan the workspace **root and immediate subdirectories** (this repo itself is
`pyproject.toml` at root + `frontend/package.json`):

| Manifest | Deps taken | opensrc spec |
| --- | --- | --- |
| `package.json` | `dependencies` + `devDependencies` | bare name (npm) |
| `pyproject.toml` | `[project] dependencies` + optional-dependencies | `pypi:<name>` |
| `requirements.txt` | non-comment lines | `pypi:<name>` |
| `Cargo.toml` | `[dependencies]` | `crates:<name>` |

Names are normalized (version specifiers/extras/markers stripped). Total deps
capped at **60** (deterministic order: manifest order, root first) so prompts and
resolution stay lean. go.mod is skipped — not an opensrc ecosystem.

Parsing is stdlib-only: `json` for package.json, `tomllib` for the TOMLs, line
parsing for requirements.txt.

### Cache

`<workspace>/.agentflow/opensrc-deps.json`:

```json
{ "manifestHash": "sha256-…", "resolved": {"zod": "/…/zod/3.25.76"}, "updatedAt": "…" }
```

- `manifestHash` = sha256 over the sorted (path, mtime, size) of discovered
  manifests. `refresh` is a no-op when the hash matches; the hash check re-runs
  on every task creation, so a manifest edit re-resolves on the next task.
- Paths whose directory no longer exists are dropped on read (opensrc cache may
  have been cleaned; `opensrc remove` is exposed in the Sources tab).

### Failure behavior

- opensrc missing → service is inert; prompts keep the generic line.
- A dep that fails to resolve (private, unknown registry) → skipped and recorded
  in the cache under `"failed"` so refreshes don't retry it until the manifest
  changes. Partial maps are valid.
- Per-dep resolution timeout 120s (opensrc fetch of a big repo is slow once,
  then cached globally in `~/.opensrc`).

## Prompt integration

`prompt_templates._compose` gains the map (threaded from `task_service`, which
knows the workspace). Rendering:

```
Dependency source (real code, read with your file tools):
- zod → /Users/…/.opensrc/repos/github.com/colinhacks/zod/3.25.76
- fastapi → /Users/…/repos/…/fastapi/0.115.0
(+ run `opensrc path <pkg>` for anything not listed)
```

- Map non-empty → this section replaces the generic capability line.
- Map empty/absent → today's generic `opensrc path` line, unchanged.
- The trailing `(+ run …)` line keeps the escape hatch for transitive deps.

`task_service` also calls `start_background_refresh` on task creation (cheap
no-op when the hash matches) so long-lived workspaces stay fresh.

## Testing

Suite idiom: offline, fake `opensrc` binary via `OPENSRC_BIN` (existing pattern).

- Manifest parsing per ecosystem (fixture files), name normalization, the cap,
  root+subdir discovery.
- Resolution: partial failure (one dep fails → skipped + recorded), cache write.
- Cache: hash hit → no re-resolution (fake binary writes a marker per call);
  manifest edit → re-resolves; stale path dropped on read.
- Prompt: section renders the map; absent map → generic line (existing
  `test_opensrc_capability.py` keeps passing).

## Out of scope (YAGNI)

Transitive deps · task-relevance inference · in-context source excerpts ·
Sources-tab UI for the map · go.mod.
