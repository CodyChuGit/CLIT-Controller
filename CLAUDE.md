<!-- agent-orchestrator:enabled -->
## Use the agent-orchestrator skill in this project

For multi-step engineering work here — building/fixing/refactoring, dependency or
license audits, tool comparisons, docs or migration guides, and wrap-up (commit,
push, open a PR, watch CI) — and whenever I want to conserve Claude tokens or
spread work across my agent accounts, use the `agent-orchestrator` skill. It
routes the token-heavy grind to Codex (research, docs, analysis, review,
frontend), Antigravity/`agy` (discovery, tests, browser QA, runtime, Git/GitHub,
diff & version-update summaries, tasks, CI), and an optional local oMLX
(long-job monitoring), keeping Claude for architecture and final decisions.
Honor its usage-exhaustion fallbacks (agy out → Codex; oMLX out → agy; all
delegates out → Claude) and its Git/QA safety gates — never skip them. Skip the
skill for trivial edits, status checks, casual writing, or one-line questions.
<!-- /agent-orchestrator:enabled -->
