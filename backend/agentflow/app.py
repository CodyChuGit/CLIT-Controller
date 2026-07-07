"""FastAPI application: API routes + (optionally) the built frontend."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from . import __version__, config, paths, queue_service, state_store
from .api import (
    routes_agents,
    routes_chat,
    routes_context,
    routes_logs,
    routes_memory,
    routes_opensrc,
    routes_preview,
    routes_projects,
    routes_queue,
    routes_state,
    routes_tasks,
    routes_terminals,
    routes_usage,
)
from .origins import LOCAL_ORIGINS, is_allowed_origin, origin_of
from .process_runner import RUNNER, add_log_entry
from .terminal_service import TERMINALS, sweep_orphaned_sessions

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class OriginGuardMiddleware(BaseHTTPMiddleware):
    """Reject state-changing requests carrying a foreign browser Origin/Referer.

    CORS controls whether a browser may *read* a cross-origin response, not whether
    the request *executes* — a cross-site "simple request" (e.g. text/plain POST)
    runs server-side regardless. Since this app has no auth and executes commands,
    that is a CSRF vector (audit P1-09). We mirror the WebSocket origin check: a
    present-but-foreign Origin (or Referer, when Origin is absent) is refused; a
    missing one (native clients, tests, same-origin GET nav) is allowed."""

    async def dispatch(self, request: Request, call_next):
        if request.method in _MUTATING_METHODS:
            origin = request.headers.get("origin") or origin_of(request.headers.get("referer"))
            if origin is not None and not is_allowed_origin(origin):
                return JSONResponse({"detail": "cross-origin request rejected"}, status_code=403)
        return await call_next(request)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Recover durable state before the dispatcher starts: a restart must not leave any
    # run / queue item / task step stuck `running`.
    try:
        ws = config.get_current_workspace()
        if ws is not None:
            summary = state_store.recover_workspace(ws)
            if any(summary.values()):
                add_log_entry(
                    "system",
                    f"startup recovery: {summary['runs']} run(s), {summary['items']} queue item(s), "
                    f"{summary['steps']} step(s) settled after restart",
                    status="warn",
                )
    except Exception as exc:  # noqa: BLE001 — recovery must never block startup
        add_log_entry("system", f"startup recovery failed: {exc}", status="error")

    # Reap PTY terminal sessions orphaned by a prior backend that died without
    # running its shutdown hook (crash / SIGKILL), so leaked agy/codex/claude
    # process groups don't accumulate across restarts.
    try:
        reaped = sweep_orphaned_sessions()
        if reaped:
            add_log_entry("system", f"startup cleanup: reaped {reaped} orphaned terminal session(s)", status="warn")
    except Exception as exc:  # noqa: BLE001 — cleanup must never block startup
        add_log_entry("system", f"terminal cleanup failed: {exc}", status="error")

    # The dispatcher cues queued steps to agents for as long as the app runs.
    dispatcher = asyncio.create_task(queue_service.dispatcher_loop())
    yield
    dispatcher.cancel()
    # Cancel in-flight agent/dev-server runs so their detached process groups don't
    # outlive the backend (esp. a preview server holding a port) — audit P1-04.
    try:
        await RUNNER.cancel_all()
    except Exception as exc:  # noqa: BLE001 — shutdown must not raise
        add_log_entry("system", f"run cancel_all on shutdown failed: {exc}", status="error")
    await TERMINALS.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Command Line Interface Terminal Controller",
        description="Vibe with CLIT Controller",
        version=__version__,
        lifespan=_lifespan,
    )

    # CSRF guard on mutating methods (runs before routes); origins shared with CORS
    # and the WebSocket check via agentflow.origins (audit P1-09 / P2-10).
    app.add_middleware(OriginGuardMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(LOCAL_ORIGINS),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_projects.router, prefix="/api/projects", tags=["projects"])
    app.include_router(routes_agents.router, prefix="/api/agents", tags=["agents"])
    app.include_router(routes_tasks.router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(routes_usage.router, prefix="/api/usage", tags=["usage"])
    app.include_router(routes_logs.router, prefix="/api/logs", tags=["logs"])
    app.include_router(routes_terminals.router, prefix="/api/terminals", tags=["terminals"])
    app.include_router(routes_chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(routes_queue.router, prefix="/api/queue", tags=["queue"])
    app.include_router(routes_state.router, prefix="/api", tags=["state"])
    app.include_router(routes_preview.router, prefix="/api/preview", tags=["preview"])
    app.include_router(routes_context.router, prefix="/api/context", tags=["context"])
    app.include_router(routes_memory.router, prefix="/api/memory", tags=["memory"])
    app.include_router(routes_opensrc.router, prefix="/api/opensrc", tags=["opensrc"])

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "app": "CLIT Controller IDE",
            "fullName": "Command Line Interface Terminal Controller",
            "tagline": "Vibe with CLIT Controller",
            "version": __version__,
        }

    # Serve the built frontend when it exists (single-port mode on :8787).
    dist = paths.frontend_dist()
    if dist.is_dir() and (dist / "index.html").exists():
        dist_root = dist.resolve()
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str) -> FileResponse:
            # Confine to dist: `full_path` is attacker-controllable and may contain
            # `..` (Starlette URL-decodes the path), so resolve and verify the
            # candidate stays inside dist before serving — otherwise this is an
            # arbitrary file read. Anything else falls back to the SPA shell.
            candidate = (dist_root / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(dist_root):
                return FileResponse(candidate)
            return FileResponse(dist_root / "index.html")

    return app


app = create_app()
