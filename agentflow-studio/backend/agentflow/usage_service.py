"""Approximate provider usage tracking in <workspace>/.agentflow/usage.json."""

from __future__ import annotations

from pathlib import Path

from . import paths
from .config import read_json, write_json

DEFAULT_PROVIDER_USAGE = {
    "claude": {
        "callsToday": 0,
        "manualBudgetLevel": "limited",
        "health": "yellow",
        "preferredUse": "implementation_only",
        "estimatedPromptChars": 0,
        "estimatedOutputChars": 0,
        "lastCommandDuration": 0,
        "lastStatus": "unknown",
    },
    "codex": {
        "callsToday": 0,
        "manualBudgetLevel": "normal",
        "health": "green",
        "preferredUse": "spec_review_docs",
        "estimatedPromptChars": 0,
        "estimatedOutputChars": 0,
        "lastCommandDuration": 0,
        "lastStatus": "unknown",
    },
    "antigravity": {
        "callsToday": 0,
        "manualBudgetLevel": "high",
        "health": "green",
        "preferredUse": "orchestration_qa",
        "estimatedPromptChars": 0,
        "estimatedOutputChars": 0,
        "lastCommandDuration": 0,
        "lastStatus": "unknown",
    },
}

DEFAULT_USAGE = {
    "mode": "subscription",
    "orchestrationMode": "balanced",
    "providers": DEFAULT_PROVIDER_USAGE,
    "expensiveCallsAvoided": 0,
    "localStepsCompleted": 0,
}


def _blank_provider(preferred_use: str = "general") -> dict:
    return {
        "callsToday": 0,
        "manualBudgetLevel": "normal",
        "health": "green",
        "preferredUse": preferred_use,
        "estimatedPromptChars": 0,
        "estimatedOutputChars": 0,
        "lastCommandDuration": 0,
        "lastStatus": "unknown",
    }


def ensure_usage(workspace: Path) -> dict:
    path = paths.usage_file(workspace)
    data = read_json(path, None)
    if data is None:
        data = {
            "mode": "subscription",
            "orchestrationMode": "balanced",
            "providers": {k: dict(v) for k, v in DEFAULT_PROVIDER_USAGE.items()},
            "expensiveCallsAvoided": 0,
            "localStepsCompleted": 0,
        }
        write_json(path, data)
        return data

    # Backfill any missing keys so older files keep working.
    data.setdefault("mode", "subscription")
    data.setdefault("orchestrationMode", "balanced")
    data.setdefault("providers", {})
    data.setdefault("expensiveCallsAvoided", 0)
    data.setdefault("localStepsCompleted", 0)
    # Gemini CLI was sunset in favor of the Antigravity CLI — carry stats over.
    if "gemini" in data["providers"]:
        if "antigravity" not in data["providers"]:
            data["providers"]["antigravity"] = data["providers"].pop("gemini")
        else:
            data["providers"].pop("gemini")
        write_json(path, data)
    for pid, defaults in DEFAULT_PROVIDER_USAGE.items():
        entry = data["providers"].setdefault(pid, dict(defaults))
        for key, value in defaults.items():
            entry.setdefault(key, value)
    return data


def get_usage(workspace: Path) -> dict:
    return ensure_usage(workspace)


def _save(workspace: Path, data: dict) -> None:
    write_json(paths.usage_file(workspace), data)


def set_orchestration_mode(workspace: Path, mode: str) -> dict:
    data = ensure_usage(workspace)
    data["orchestrationMode"] = mode
    _save(workspace, data)
    return data


def set_provider_health(workspace: Path, provider: str, health: str) -> dict:
    data = ensure_usage(workspace)
    entry = data["providers"].setdefault(provider, _blank_provider())
    entry["health"] = health
    entry["manualBudgetLevel"] = {"green": "normal", "yellow": "limited", "red": "exhausted"}.get(
        health, entry.get("manualBudgetLevel", "normal")
    )
    _save(workspace, data)
    return data


def record_call(
    workspace: Path,
    provider: str,
    prompt_chars: int,
    output_chars: int,
    duration_ms: int,
    status: str,
) -> dict:
    data = ensure_usage(workspace)
    entry = data["providers"].setdefault(provider, _blank_provider())
    entry["callsToday"] = int(entry.get("callsToday", 0)) + 1
    entry["estimatedPromptChars"] = int(entry.get("estimatedPromptChars", 0)) + prompt_chars
    entry["estimatedOutputChars"] = int(entry.get("estimatedOutputChars", 0)) + output_chars
    entry["lastCommandDuration"] = duration_ms
    entry["lastStatus"] = status
    _save(workspace, data)
    return data


def increment_avoided(workspace: Path, count: int = 1) -> dict:
    data = ensure_usage(workspace)
    data["expensiveCallsAvoided"] = int(data.get("expensiveCallsAvoided", 0)) + count
    _save(workspace, data)
    return data


def increment_local_steps(workspace: Path, count: int = 1) -> dict:
    data = ensure_usage(workspace)
    data["localStepsCompleted"] = int(data.get("localStepsCompleted", 0)) + count
    _save(workspace, data)
    return data


def provider_health(usage: dict, provider: str) -> str:
    return usage.get("providers", {}).get(provider, {}).get("health", "green")
