"""Logs: global redacted activity log + live run output."""

from __future__ import annotations

from fastapi import APIRouter

from ..process_runner import RUNNER, clear_log_view, get_log_entries

router = APIRouter()


@router.get("")
def get_logs():
    return {
        "entries": get_log_entries(),
        "running": [r.to_dict(output_tail=4000) for r in RUNNER.running_runs()],
    }


@router.post("/clear-view")
def clear_view():
    clear_log_view()
    return {"ok": True}
