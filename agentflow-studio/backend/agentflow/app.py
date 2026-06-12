"""FastAPI application: API routes + (optionally) the built frontend."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, paths, queue_service
from .api import (
    routes_agents,
    routes_chat,
    routes_logs,
    routes_preview,
    routes_projects,
    routes_queue,
    routes_tasks,
    routes_usage,
)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # The dispatcher cues queued steps to agents for as long as the app runs.
    dispatcher = asyncio.create_task(queue_service.dispatcher_loop())
    yield
    dispatcher.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="AgentFlow Studio", version=__version__, lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8787",
            "http://127.0.0.1:8787",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_projects.router, prefix="/api/projects", tags=["projects"])
    app.include_router(routes_agents.router, prefix="/api/agents", tags=["agents"])
    app.include_router(routes_tasks.router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(routes_usage.router, prefix="/api/usage", tags=["usage"])
    app.include_router(routes_logs.router, prefix="/api/logs", tags=["logs"])
    app.include_router(routes_chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(routes_queue.router, prefix="/api/queue", tags=["queue"])
    app.include_router(routes_preview.router, prefix="/api/preview", tags=["preview"])

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "app": "AgentFlow Studio", "version": __version__}

    # Serve the built frontend when it exists (single-port mode on :8787).
    dist = paths.frontend_dist()
    if dist.is_dir() and (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str) -> FileResponse:
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
