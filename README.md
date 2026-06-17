# CLIT Controller IDE

<p align="center">
  <img src="frontend/public/icons/bean_web.svg" alt="CLIT Controller IDE bean icon" width="112" height="112">
</p>

<p align="center">
  <strong>Vibe with CLIT Controller</strong><br>
  Plan design tasks, coordinate coding assistants, review changes, and keep the whole flow in one unified interface.
</p>

---

## 🫘 What It Is

**Command Line Interface Traffic Controller** is a visual control room for designers who use AI coding assistants to bring interface ideas to life.

Instead of bouncing between chats, terminals, folders, diffs, and task notes, you get one place to describe the work, route it to the right assistant, watch progress, and review the result before moving forward.

| CLI | Role | Best For |
|---|---|---|
| **Antigravity** | Controller / QA | Broad checks, second opinions, and lower-cost verification. |
| **Codex** | Product partner | Specs, task plans, markdown handoffs, and final review. |
| **Claude Code** | Implementation assistant | Code changes, bug fixes, and focused build work. |
| **Local tools** | Workspace helper | STT, TTS, File scanning, git status, diffs, logs, usage tracking, and task folders. |

![CLITC Files](docs/assets/dark_mode_files.png)
*Workspace view with project files, active tasks, file changes, and the task queue.*

![CLITC Agents](docs/assets/dark_mode_CLI.png)
*Agents view for checking connected assistants, setup status, and configuration.*

## ❓ Why You Need It

AI-assisted design work gets messy fast. One assistant is good at planning, another is better at implementation, another is useful for review. Without a controller, the designer becomes the glue: copying prompts, pasting context, checking files, repeating constraints, and hoping the expensive model is used for the right job.

CLIT Controller keeps that workflow tidy.

| Problem | How CLIT Controller Helps |
|---|---|
| Token waste | Routes work intentionally so high-cost assistants are saved for the tasks that need them. |
| Copy-paste fatigue | Keeps project context, task notes, logs, and handoffs together. |
| Lost design intent | Preserves requests, references, approvals, and review history inside the workspace. |
| Slow review loops | Surfaces generated output, file changes, and logs in one place. |
| Too many terminals | Lets designers coordinate Codex, Claude Code, and Antigravity from a single UI. |

The goal is simple: **less prompt wrangling, more product shaping**.

## ⬇️ Install

### Manual Install

Clone the project, then run:

```bash
./scripts/install.sh
```

Build the installable app and start it on `localhost:8787`:

```bash
npm --prefix frontend run build
AGENTFLOW_PORT=8787 .venv/bin/python -m agentflow
```

Open the local app:

```text
http://localhost:8787
```

The install script creates a local Python environment, installs the app backend, and installs the frontend packages. If an assistant is missing, the app shows setup guidance in the Agents view.

For hot-reload development, run `./scripts/dev.sh`; PWA install should use the backend-served production app at `http://localhost:8787`.

### Install via a Coding CLI

You can copy and paste the following prompt into your coding CLI (e.g., Claude Code, Codex or Antigravity) to have it install and run the app for you:

> Clone the repository https://github.com/CodyChuGit/CLIT-Controller.git, navigate into it, run `./scripts/install.sh`, build the frontend with `npm --prefix frontend run build`, start the backend with `AGENTFLOW_PORT=8787 .venv/bin/python -m agentflow`, and open `http://localhost:8787`.

### Chrome PWA Install

Install the PWA from the production single-port app, not the Vite dev server.
If you previously installed a blank-icon copy, remove that installed app first so Chrome refreshes the icon cache.

To run the app in its own standalone window like a native app:

1. Build and start the app at `http://localhost:8787`.
2. Open `http://localhost:8787` in Google Chrome.
3. Click the **Install** icon (a monitor with a down arrow) on the far right side of the address bar.
4. Confirm **Install CLIT Controller IDE**.
5. The installed app uses the bean icon and can be pinned to your Dock or taskbar.

## 🧰 Requirements

### Core App

- **Python 3.11+** for the local backend.
- **Node.js and npm** for the frontend.
- **git** for workspace status, diffs, and source control context.
- **GitHub CLI (`gh`)** for GitHub-aware workflows.

### AI Assistants

CLIT Controller works with the official command-line tools you already use:

- **Codex CLI**: `npm install -g @openai/codex`
- **Claude Code**: `npm install -g @anthropic-ai/claude-code`
- **Antigravity CLI**: `curl -fsSL https://antigravity.google/cli/install.sh | bash`

Prefer buttons over terminal commands? The Agents view also includes easy UI install/setup actions for supported assistants, so you can get connected without memorizing commands.

Each assistant keeps its own official login. CLIT Controller does not ask for or store provider keys or tokens.

### Packages Installed By The App

- Backend: FastAPI, Uvicorn, Pydantic.
- Frontend: React, Vite, TypeScript, Tailwind CSS, xterm, Prism.
- Dev/test support: pytest.

## 🛠️ Development

One command surface (same locally and in CI — see the [Makefile](Makefile)):

```bash
make setup       # create .venv, install backend (editable) + frontend deps
make dev         # backend :8787 + Vite dev server :5180
make verify      # format-check + lint + typecheck + tests + build (run before pushing)
make test        # backend (pytest+coverage) + frontend (vitest)
```

**Documentation:** start at the [docs index](docs/INDEX.md). Highlights —
[Product pillars / interaction model](docs/PILLARS.md) ·
[Getting started](docs/GETTING_STARTED.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Feature status](docs/FEATURE_STATUS.md) · [Backend](docs/BACKEND.md) ·
[Frontend](docs/FRONTEND.md) · [API](docs/API.md) · [Configuration](docs/CONFIGURATION.md) ·
[Testing](docs/TESTING.md) · [Security](docs/SECURITY.md) ·
[Troubleshooting](docs/TROUBLESHOOTING.md) · [Limitations](docs/LIMITATIONS.md) ·
[Roadmap](docs/ROADMAP.md). Contributing: [CONTRIBUTING.md](CONTRIBUTING.md).

**Token saving (optional):** route the claude/codex agents through a
[Headroom](docs/PILLARS.md#pillar-1--token-saving-and-output-speed) proxy — run
[`scripts/headroom.sh`](scripts/headroom.sh) and enable it in Settings.

## 🗺️ Roadmap

- **Richer designer task briefs**: clearer intake for goals, references, constraints, acceptance notes, and visual QA.
- **UI/UX reference library**: collect reusable style references and local design examples for faster frontend iteration.
- **[Live output everywhere](docs/live-output-everywhere.md)**: generated content appears as soon as it is produced, with smoother real-time assistant progress across tasks, logs, approvals, and reviews.
- **App-mode launcher**: a more polished standalone desktop-style launch experience.
- **Local voice I/O**: optional dictation and spoken summaries for hands-light task review.
- **More review intelligence**: better summaries of what changed, what still needs attention, and where design intent may have drifted.

---

<p align="center">
  <em>Vibe with CLIT Controller</em>
</p>
