# CLIT Controller IDE

<p align="center">
  <img src="frontend/public/icons/bean_web.svg" alt="CLIT Controller IDE bean icon" width="96" height="96">
</p>

CLIT Controller IDE is a local workspace for UI/UX designers who use AI assistants to plan, hand off, and review interface work.

It brings project files, design tasks, assistant activity, change reviews, approvals, and logs into one app so designers can stay focused on product quality instead of managing separate terminal sessions.

## Core Functionality

- **Workspace view**: open a local project, browse files, inspect changes, and keep task context beside the work.
- **Design task intake**: turn design requests, references, constraints, and QA notes into organized tasks.
- **Assistant coordination**: send work to configured AI assistants such as Codex, Claude Code, and Antigravity from one place.
- **Review flow**: check generated output, file changes, logs, and status before continuing or accepting work.
- **Usage control**: choose quality or budget modes and mark assistant availability so expensive AI runs stay intentional.
- **Local-first privacy**: project state stays on your machine, and assistant login stays with the official tools.

## Screenshots

![CLITC Files](docs/assets/dark_mode_files.png)
*Workspace view with project files, active tasks, and the task queue.*

![CLITC Agents](docs/assets/dark_mode_CLI.png)
*Agents view for checking connected assistants and their setup status.*

## Basic Workflow

1. Open a workspace folder.
2. Check which AI assistants are installed and logged in.
3. Choose a usage mode that matches the task.
4. Describe the design or UI change from the task/chat surface.
5. Review the generated work, file changes, logs, and approvals in Tasks.
6. Continue, reroute, or stop the task as needed.

## Privacy And Control

- The app does not ask for or store provider keys or tokens.
- Each assistant uses its own official login.
- Logs redact common secret patterns.
- Workspace configuration and task history are stored locally.
- Changes, approvals, and assistant runs stay under user control.
