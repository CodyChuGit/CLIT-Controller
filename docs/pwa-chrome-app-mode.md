# PWA And Chrome App-Mode Launcher

Command Line Interface Traffic Controller (CLIT Controller IDE) should support
an app-like Chrome window without adopting Electron, Tauri, or old Chrome Apps.
The product path is:

1. Make the frontend installable as a Progressive Web App.
2. Keep the FastAPI backend as the local runtime.
3. Add a script and optional macOS `.app` wrapper that start the backend, wait for
   it to become healthy, then open Chrome in app mode.

This gives CLITC the independent-window feel of apps like VJbooth while keeping
the current web + local backend architecture.

The app-mode shell still uses the final
[Live Output Everywhere](./live-output-everywhere.md) implementation for active
assistant progress. It must not cache, replace, or downgrade live generated text
to completed-only snapshots.

## Product Decision

CLITC should feel launchable as a local app, but remain a local-first web app
served by the backend. Chrome app mode is a near-term shell, not a new platform.

Use:

- Web app manifest for name, icon, theme, and standalone display.
- Service worker for static app-shell caching only.
- Backend-served built frontend at `http://127.0.0.1:<port>`.
- Chrome app-mode launch: `--app=http://127.0.0.1:<port>`.
- Optional generated macOS `.app` wrapper that runs the launcher script.

Do not use:

- Deprecated Chrome Apps.
- Chrome Extensions as the app shell.
- Electron.
- Tauri.
- Native desktop packaging.
- Store distribution or auto-update infrastructure in this pass.

## Target UX

- User launches **CLIT Controller IDE** from a script or macOS app icon.
- If the backend is not running, the launcher starts it.
- The launcher waits for the backend health endpoint.
- Chrome opens a dedicated app-mode window with the bean favicon/app icon and
  no normal browser tabs/address bar.
- The app uses the normal CLITC local URL and existing backend APIs.
- Closing the app window does not trigger remote state changes.
- Backend logs are written to a predictable local log path for troubleshooting.

## Frontend Requirements

Add a web app manifest, served by the frontend/backend:

```json
{
  "name": "CLIT Controller IDE",
  "short_name": "CLITC",
  "description": "Vibe with CLIT Controller",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#0f1115",
  "theme_color": "#0f1115",
  "icons": [
    {
      "src": "/icons/bean-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/icons/bean-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}
```

Add `index.html` metadata:

- `link rel="manifest" href="/manifest.webmanifest"`
- `meta name="theme-color"`
- Apple mobile web app tags only if they do not create separate styling rules.

Service worker scope:

- Cache built static assets and the app shell.
- Do not cache `/api/*`.
- Do not cache `/events/stream`.
- Do not cache WebSocket or PTY traffic.
- Do not cache task data, logs, approvals, provider state, or queue responses.
- Streaming and live status must always come from the backend.

## Launcher Requirements

Add a script such as `scripts/app-mode.sh`.

Responsibilities:

- Resolve repo root.
- Ensure `.venv` exists or print the install command.
- Build frontend if the backend should serve `frontend/dist` and it is missing.
- Start the backend if `http://127.0.0.1:${AGENTFLOW_PORT:-8787}` is not healthy.
- Write backend stdout/stderr to a local log file, for example
  `.agentflow/runtime/app-mode-backend.log` or `/tmp/clitc-controller/backend.log`.
- Store a PID file only for the process it starts.
- Poll the health endpoint until ready or timeout.
- Open Chrome in app mode:

```bash
open -na "Google Chrome" --args --app="http://127.0.0.1:${AGENTFLOW_PORT:-8787}"
```

Optional flags may be documented, but should not be defaulted unless needed:

- `--user-data-dir=<local-runtime-profile>` for a separate CLITC Chrome profile.
- `--window-size=1440,960` for first-run sizing.

The launcher must not:

- Kill unrelated backend processes.
- Reset user state.
- Run `git pull`, `git push`, installers, or remote-state commands.
- Hide backend startup failures.
- Require Chrome if the user chooses to open the normal URL manually.

## macOS App Wrapper

Add an optional generated app wrapper after the script works.

Recommended shape:

- `scripts/create-macos-app-mode.sh`
- Generates `dist/CLIT Controller IDE.app`.
- Uses the bean icon.
- Runs `scripts/app-mode.sh`.
- Keeps all real app logic in the shell script so the wrapper stays thin.

The wrapper is convenience only. It is not a native desktop package and should
not introduce Electron, Tauri, notarization, updater logic, or separate app
state.

## Backend Requirements

- Keep serving the built frontend when `frontend/dist` exists.
- Keep `GET /health` or equivalent stable for launcher readiness checks.
- Avoid assuming a browser session; app-mode Chrome and normal browser tabs must
  use the same APIs.
- Preserve current backend safety rules for workspace confinement, redaction,
  approvals, and remote-state actions.

## Non-Goals

- No Electron.
- No Tauri.
- No native desktop packaging.
- No deprecated Chrome App implementation.
- No Chrome Extension shell.
- No Chrome Web Store distribution.
- No service-worker caching for live API, task, log, queue, approval, terminal,
  or streaming data.

## Acceptance Criteria

- `manifest.webmanifest` is served and points to the CLITC bean icons.
- Chrome can install or run CLITC as a standalone PWA-style app window.
- `scripts/app-mode.sh` starts the backend if needed and opens Chrome with
  `--app=http://127.0.0.1:<port>`.
- The launcher waits for backend health before opening Chrome.
- If the backend fails to start, the user gets a clear terminal error and log path.
- Live streaming, API calls, task state, logs, queue state, and approvals are not
  cached by the service worker.
- Optional macOS `.app` generation delegates to the same launcher script.
- No Tauri, Electron, native packager, Chrome Extension, or deprecated Chrome App
  is introduced.
