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

**CLIT Controller IDE** is a visual control room for designers who use AI coding assistants to bring interface ideas to life.

Instead of bouncing between chats, terminals, folders, diffs, and task notes, you get one place to describe the work, route it to the right assistant, watch progress, and review the result before moving forward.

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

Start the app:

```bash
./scripts/dev.sh
```

Open the local app:

```text
http://localhost:5173
```

The install script creates a local Python environment, installs the app backend, and installs the frontend packages. If an assistant is missing, the app shows setup guidance in the Agents view.

### Install via a Coding CLI

You can copy and paste the following prompt into your coding CLI (e.g., Claude Code, Codex or Antigravity) to have it install and run the app for you:

> Clone the repository https://github.com/CodyChuGit/CLIT-Controller.git, navigate into it, run `./scripts/install.sh`, and then start the dev server with `./scripts/dev.sh`.

### Chrome PWA Install

To run the app in its own standalone window like a native app:

1. Open `http://localhost:5173` in Google Chrome.
2. Click the **Install** icon (a monitor with a down arrow) on the far right side of the address bar.
3. The app will install and open in its own window, and you can pin it to your Dock or taskbar.

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

Each assistant keeps its own official login. CLIT Controller does not ask for or store provider keys or tokens.

### Packages Installed By The App

- Backend: FastAPI, Uvicorn, Pydantic.
- Frontend: React, Vite, TypeScript, Tailwind CSS, xterm, Prism.
- Dev/test support: pytest.

## 🗺️ Roadmap

- **Richer designer task briefs**: clearer intake for goals, references, constraints, acceptance notes, and visual QA.
- **UI/UX reference library**: collect reusable style references and local design examples for faster frontend iteration.
- **Live output everywhere**: smoother real-time assistant progress across tasks, logs, approvals, and reviews.
- **App-mode launcher**: a more polished standalone desktop-style launch experience.
- **Local voice I/O**: optional dictation and spoken summaries for hands-light task review.
- **More review intelligence**: better summaries of what changed, what still needs attention, and where design intent may have drifted.

---

<p align="center">
  <em>Vibe with CLIT Controller</em>
</p>
