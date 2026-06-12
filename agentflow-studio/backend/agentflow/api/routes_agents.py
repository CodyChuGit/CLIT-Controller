"""Agents: CLI detection, version checks, login/setup launching."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import config, provider_probe, usage_service
from ..models import AgentActionRequest

router = APIRouter()


def _enrich_with_usage(providers: list[dict]) -> list[dict]:
    """Merge per-workspace usage health into provider cards when a workspace is set."""
    ws = config.get_current_workspace()
    usage = usage_service.ensure_usage(ws) if ws else {"providers": {}}
    for p in providers:
        u = usage.get("providers", {}).get(p["id"], {})
        p["usageHealth"] = u.get("health")
        p["callsToday"] = u.get("callsToday", 0)
        p["manualBudgetLevel"] = u.get("manualBudgetLevel")
    return providers


@router.get("")
def list_agents():
    return _enrich_with_usage(provider_probe.list_providers())


@router.post("/check")
async def check(body: AgentActionRequest):
    if body.id not in provider_probe.PROVIDER_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {body.id}")
    result = await provider_probe.check_provider(body.id)
    return _enrich_with_usage([result])[0]


@router.post("/check-all")
async def check_all():
    return _enrich_with_usage(await provider_probe.check_all())


@router.post("/login")
def login(body: AgentActionRequest):
    if body.id not in provider_probe.PROVIDER_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {body.id}")
    return provider_probe.login_provider(body.id, config.get_current_workspace())
