"""Context intelligence API (Phase 1: preview/benchmark only — no live prompt path)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..context_intelligence import benchmarks, pipeline, reports
from ..context_intelligence.types import UserTask
from .routes_projects import require_workspace

router = APIRouter()


class ContextPreviewRequest(BaseModel):
    task: str = Field(min_length=1, max_length=10_000)
    maxTokens: Optional[int] = Field(default=None, ge=1)


class ContextBenchmarkRequest(BaseModel):
    task: str = Field(min_length=1, max_length=10_000)


@router.post("/preview")
async def preview(body: ContextPreviewRequest) -> dict:
    ws = require_workspace()
    report = await pipeline.run_preview(ws, UserTask(text=body.task, maxTokens=body.maxTokens))
    return reports.save_report(ws, report)  # persisted AND returned redacted


@router.post("/benchmark")
async def benchmark(body: ContextBenchmarkRequest) -> dict:
    ws = require_workspace()
    report = await benchmarks.run_benchmark(ws, UserTask(text=body.task))
    return reports.save_report(ws, report)


@router.get("/reports/{report_id}")
def get_report(report_id: str) -> dict:
    ws = require_workspace()
    try:
        return reports.load_report(ws, report_id)
    except ValueError as exc:
        # Malformed id → 400 BEFORE any filesystem access (path-traversal defense).
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"report not found: {report_id}") from exc
