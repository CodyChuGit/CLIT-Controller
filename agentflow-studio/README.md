# AgentFlow Studio (beta)

A **local-first cockpit for orchestrating CLI coding agents** — Codex, Claude Code, and Antigravity — from one clean UI, with Git and the GitHub CLI alongside them.

## Why it exists

Running several coding agents by hand means juggling terminals, re-pasting context, and burning tokens on the wrong model. AgentFlow Studio routes work deliberately:

| Role | Provider | Used for |
|---|---|---|
| Orchestrator / QA | Antigravity | broad checks, QA, cheap verification |
| PM | Codex | specs, markdown plans, final reviews |
| Engineer | Claude Code | implementation and bug fixing **only** |
| Local deterministic code | none (free) | file scanning, task folders, git status/diff, logs, usage tracking |

## How it saves tokens

- Every generated prompt carries a **budget context header** (current mode + per-provider health) instructing agents to prefer diffs, file paths, and task markdown over whole files.
- **Orchestration modes**: Maximum Quality, Balanced, Budget Saver (skips the Codex spec for small tasks and runs local checks first), and Manual Approval (nothing runs without a click).
- When Claude's health is **yellow** it is reserved for implementation only; when **red**, AgentFlow recommends Codex planning + Antigravity QA + local tests, and requires explicit confirmation before any Claude run.
- Local steps (git status/diff, file reads, task scaffolding) never touch an AI model. Avoided expensive calls are counted in `.agentflow/usage.json`.
- Every task records its reasoning in `ROUTING_DECISIONS.md`.

## Required CLIs

AgentFlow shells out to the official CLIs you already have installed and logged in:

- `git`, `gh` (GitHub CLI)
- `codex` (OpenAI Codex CLI) — `npm install -g @openai/codex`
- `claude` (Claude Code) — `npm install -g @anthropic-ai/claude-code`
- `agy` (Google Antigravity CLI — successor to the sunset Gemini CLI) — orchestration and QA. Official install: `curl -fsSL https://antigravity.google/cli/install.sh | bash` (puts `agy` in `~/.local/bin`; the Agents page Install button runs exactly this)
- `ollama` — optional, future local routing
- `omlx` (local Apple MLX LLM server; also detects `mlx_lm.*` / `mlx-omni-server`) — optional, future on-device routing on Apple Silicon

Missing CLIs are handled gracefully: the step's prompt is saved into the task folder, the exact command is shown for copy/paste, and the Agents page shows an install hint. Providers with a known installer (npm/brew) support **one-click install** — click the "not installed" badge or the Install button and the real install command runs in the background (npm installs use an isolated cache at `/tmp/agentflow-npm-cache` to dodge broken `~/.npm` permissions); the card flips to its detected version when done.

## Install

```bash
./scripts/install.sh
```

Creates a Python 3.11+ virtualenv at `.venv`, installs backend deps (FastAPI, Uvicorn, Pydantic), and runs `npm install` for the frontend.

## Run

```bash
./scripts/dev.sh
```

- Backend (API + built frontend, if present): **http://localhost:8787**
- Frontend dev server (hot reload): **http://localhost:5173**

Backend alone: `.venv/bin/python -m agentflow`. If you build the frontend once (`npm --prefix frontend run build`), the backend serves the whole app at **http://localhost:8787** with no dev server needed.

## Beta workflow

1. **Explorer** → enter a workspace folder path and open it. The backend creates `<workspace>/.agentflow/` (config, usage.json, tasks/). The explorer is laid out like an IDE: side panel (workspace, source control, files), tabbed read-only editor with line numbers, a collapsible Output/Logs panel, and a status bar (backend, workspace, branch, orchestration mode). The **Source Control** section works like VS Code's: live per-file status (M/A/D/U badges), click a file to open its color-coded diff in a tab, stage/unstage per file or Stage All, and commit with a message — staging and committing only ever happen when you click them. Local folder paths are resolved by the Python backend — browsers can't pick arbitrary folders.
2. **Agents** → Check All. See versions, auth status (`gh auth status`), and launch login/setup commands in Terminal (macOS) or copy them. Each agent card has a **Model** field — set the model that CLI should use (passed as `--model <name>` via the `{model}` placeholder in its command template; empty = the CLI's own default).
3. **Usage** → pick an orchestration mode and set provider health (green/yellow/red) to match your real quota state.
4. **Tasks** → create a task (title + goal). AgentFlow writes the task folder with all markdown handoff files (`00_USER_GOAL.md` … `07_CODEX_FINAL_REVIEW.md`, `ROUTING_DECISIONS.md`).
5. Run steps individually (**Write Spec**, **Implement**, **QA / Test**, **Final Review**, **Fix Bugs** — each step shows its routed provider) or **Run Full Sequence**. Logs stream into the UI (polling) and are saved, redacted, under the task's `logs/` folder.
6. **Logs** → global redacted activity console.

## Auth & security model

- **Subscription-first**: AgentFlow never asks for or stores API keys, passwords, or tokens. Each CLI uses its own official login (Claude Pro/Max, ChatGPT/Codex, Google).
- AgentFlow never reads token files and never prints environment variables.
- Logs and command previews are **redacted** (`sk-…`, `ghp_…`, `github_pat_…`, `xoxb-…`, `Bearer …`, `*API_KEY=…`, `token=…`, `password=…` → `[REDACTED]`).
- `.env` files are never previewable in the file reader (`.env.example` is allowed).
- Nothing is sent to any cloud service except through the official CLIs you invoke.
- Config lives at `~/.agentflow/config.json` (global) and `<workspace>/.agentflow/` (per project).

## Usage tracking limitations

Usage is **approximate by design**: calls per provider, estimated prompt/output characters, and last command duration — not exact tokens. Provider health (green/yellow/red) is set manually by you; the beta does not query provider quota APIs.

## Known limitations

- Logs update by polling (2.5–3s), not streaming.
- Agent CLIs run **non-interactively** (`codex exec`, `claude -p`, `antigravity -p`). Interactive sessions (logins) open in Terminal.app on macOS. Agents that want to edit files may need permission flags added to their command template in Settings (e.g. Claude Code permission modes) — deliberately not defaulted for safety.
- Command templates are global (`~/.agentflow/config.json`), editable in Settings.
- "Open in Finder" is macOS-only and fails gracefully elsewhere.
- One workspace is active at a time.
- The file tree caps at depth 8 / 2000 files; previews cap at 512 KB.

## Troubleshooting

- **Backend offline banner** → `./scripts/dev.sh` not running, or port 8787 is taken (`AGENTFLOW_PORT=8890 .venv/bin/python -m agentflow`).
- **`python3` too old** → install Python 3.11+ (`brew install python@3.12`), re-run `./scripts/install.sh`.
- **A step "fails" instantly** → open its log in the task folder; usually the CLI isn't logged in (use Agents → Login / Setup) or the command template needs tuning in Settings.
- **Stop doesn't kill a stuck CLI** → AgentFlow SIGTERMs the process group, then SIGKILLs after 4s; check Activity Monitor if a CLI ignores both.
- **Tests** → `.venv/bin/pytest`.
