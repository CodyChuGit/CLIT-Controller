# Vendored: codebase-memory-mcp graph UI (the "galaxy")

These files are copied **verbatim** from
[DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)
(`graph-ui/src/`), which is MIT-licensed — see [`LICENSE`](./LICENSE).

CLITC renders the upstream three.js `GraphScene` galaxy **natively** (fed by the
backend's `/api/memory/layout` proxy) instead of embedding the whole viewer in a
cross-origin iframe. That's the only way to show *just* the galaxy — no viewer
dashboard, tabs, or filter chrome — scoped to the current workspace and matching
CLITC's shell.

## Files (unmodified upstream copies)

- `components/` — `GraphScene`, `NodeCloud`, `EdgeLines`, `NodeLabels`, `NodeTooltip`
- `lib/` — `types`, `density`, `colors`

They are excluded from CLITC's eslint/prettier (see `.prettierignore` and
`eslint.config.js`) so they stay byte-for-byte upstream. All CLITC-side wiring
(data fetch, layout proxy, gating) lives in `pages/MemoryGalaxy.tsx` and
`pages/MemoryPage.tsx`, **not** here.

## Updating

Re-copy from upstream `graph-ui/src/` when bumping. Before doing so, confirm the
`/api/layout` response shape and the react-three-fiber major version still match
(R3F v9 requires React 19). Keep the copies verbatim.

Copyright (c) 2025 DeusData — MIT.
