"""Usage: orchestration mode, provider health, routing recommendations."""

from __future__ import annotations

from fastapi import APIRouter

from .. import git_service, routing_service, usage_service
from ..models import ModeUpdateRequest, ProviderHealthRequest, ProviderLimitRequest
from ..process_runner import add_log_entry
from .routes_projects import require_workspace

router = APIRouter()


@router.get("")
def get_usage():
    return usage_service.get_usage(require_workspace())


@router.post("/mode")
def set_mode(body: ModeUpdateRequest):
    data = usage_service.set_orchestration_mode(require_workspace(), body.mode)
    add_log_entry("system", f"orchestration mode set to {body.mode}")
    return data


@router.post("/provider-health")
def set_health(body: ProviderHealthRequest):
    data = usage_service.set_provider_health(require_workspace(), body.provider, body.health)
    add_log_entry("system", f"{body.provider} usage health set to {body.health}")
    return data


@router.post("/provider-limit")
def set_limit(body: ProviderLimitRequest):
    return usage_service.set_provider_limit(require_workspace(), body.provider, body.limitCalls, body.windowHours)


@router.get("/live")
async def live(force: bool = False):
    return await usage_service.live_usage(force=force)


@router.get("/recommendations")
async def recommendations():
    ws = require_workspace()
    usage = usage_service.ensure_usage(ws)
    size = await git_service.diff_size(ws)
    return routing_service.recommend(usage, diff_size=size)
