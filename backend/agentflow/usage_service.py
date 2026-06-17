"""Approximate provider usage tracking in <workspace>/.agentflow/usage.json."""

from __future__ import annotations

import re as _re
import time as _time
from pathlib import Path

from . import paths
from .config import read_json, write_json

DEFAULT_PROVIDER_USAGE = {
    "claude": {
        "limitCalls": None,
        "windowHours": 5,
        "windowStartedAt": None,
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
        "limitCalls": None,
        "windowHours": 5,
        "windowStartedAt": None,
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
        "limitCalls": None,
        "windowHours": 24,
        "windowStartedAt": None,
        "callsToday": 0,
        "manualBudgetLevel": "high",
        "health": "green",
        "preferredUse": "traffic_control_qa",
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
        "limitCalls": None,
        "windowHours": 24,
        "windowStartedAt": None,
        "callsToday": 0,
        "manualBudgetLevel": "normal",
        "health": "green",
        "preferredUse": preferred_use,
        "estimatedPromptChars": 0,
        "estimatedOutputChars": 0,
        "lastCommandDuration": 0,
        "lastStatus": "unknown",
    }


def _maybe_reset_window(entry: dict) -> bool:
    """Reset per-window counters once the usage window has elapsed."""
    from datetime import datetime, timezone

    started = entry.get("windowStartedAt")
    hours = float(entry.get("windowHours") or 24)
    now = datetime.now(timezone.utc)
    if not started:
        entry["windowStartedAt"] = now.isoformat(timespec="seconds")
        return True
    try:
        begun = datetime.fromisoformat(started)
    except ValueError:
        entry["windowStartedAt"] = now.isoformat(timespec="seconds")
        return True
    if (now - begun).total_seconds() >= hours * 3600:
        entry.update(
            callsToday=0,
            estimatedPromptChars=0,
            estimatedOutputChars=0,
            windowStartedAt=now.isoformat(timespec="seconds"),
        )
        return True
    return False


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
    changed = False
    for pid, defaults in DEFAULT_PROVIDER_USAGE.items():
        entry = data["providers"].setdefault(pid, dict(defaults))
        for key, value in defaults.items():
            if key not in entry:
                entry[key] = value
                changed = True
    for entry in data["providers"].values():
        if _maybe_reset_window(entry):
            changed = True
    if changed:
        write_json(path, data)
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


def set_provider_limit(workspace: Path, provider: str, limit_calls, window_hours) -> dict:
    data = ensure_usage(workspace)
    entry = data["providers"].setdefault(provider, _blank_provider())
    entry["limitCalls"] = int(limit_calls) if limit_calls else None
    if window_hours:
        entry["windowHours"] = float(window_hours)
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


# ----------------------------------------------------- live usage from the CLIs
# codex caches the API's real rate-limit snapshots in its session files; claude
# and agy expose nothing headlessly (verified), so they fall back to manual limits.


def _extract_rate_limits(text: str):
    import json as _json

    i = text.rfind('"rate_limits":')
    if i == -1:
        return None
    j = text.find("{", i)
    if j == -1:
        return None
    depth = 0
    for k in range(j, min(len(text), j + 4000)):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return _json.loads(text[j : k + 1])
                except _json.JSONDecodeError:
                    return None
    return None


def _window_label(minutes) -> str:
    minutes = minutes or 0
    if minutes >= 1440:
        return f"{round(minutes / 1440)}d"
    return f"{round(minutes / 60)}h"


def codex_live_usage():
    """Newest rate_limits snapshot from ~/.codex session files (real API data)."""
    from datetime import datetime, timezone

    base = Path.home() / ".codex" / "sessions"
    if not base.is_dir():
        return None
    try:
        files = sorted(base.rglob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)[:12]
    except OSError:
        return None
    for f in files:
        try:
            size = f.stat().st_size
            with open(f, "rb") as fh:
                fh.seek(max(0, size - 200_000))
                text = fh.read().decode("utf-8", "replace")
        except OSError:
            continue
        rl = _extract_rate_limits(text)
        if not rl or not rl.get("primary"):
            continue
        windows = []
        for key in ("primary", "secondary"):
            w = rl.get(key)
            if w and w.get("used_percent") is not None:
                windows.append(
                    {
                        "label": _window_label(w.get("window_minutes")),
                        "usedPercent": float(w["used_percent"]),
                        "resetsAt": w.get("resets_at"),
                    }
                )
        if windows:
            return {
                "available": True,
                "plan": rl.get("plan_type"),
                "windows": windows,
                "sourcedAt": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
            }
    return None


_CLAUDE_USAGE_RE = _re.compile(
    r"Current (session|week \(all models\)|week \(Sonnet only\)):\s*(\d+)% used(?:\s*[·\u00b7]\s*resets (.+))?"
)


def parse_claude_usage_text(text: str) -> list[dict]:
    """Parse the output of `claude -p \"/usage\"` into usage windows."""
    labels = {"session": "session", "week (all models)": "week", "week (Sonnet only)": "wk·sonnet"}
    windows = []
    for line in (text or "").splitlines():
        m = _CLAUDE_USAGE_RE.search(line.strip())
        if m:
            windows.append(
                {
                    "label": labels[m.group(1)],
                    "usedPercent": float(m.group(2)),
                    "resetsAt": None,
                    "resetsText": (m.group(3) or "").strip() or None,
                }
            )
    return windows


async def claude_live_usage():
    """Fresh usage straight from the CLI: `claude -p \"/usage\"` is intercepted
    headlessly (no model call) and prints session/week percentages."""
    from datetime import datetime, timezone

    from .process_runner import RUNNER
    from .provider_probe import resolve_executable

    exe = resolve_executable("claude")
    if exe is None:
        return None
    record = await RUNNER.run_and_wait([exe, "-p", "/usage"], Path.home(), timeout=30, provider="claude")
    if record.exit_code != 0:
        return None
    windows = parse_claude_usage_text(record.stdout)
    if not windows:
        return None
    return {
        "available": True,
        "plan": None,
        "windows": windows,
        "sourcedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


_live_cache: dict = {"at": 0.0, "data": None}


async def live_usage(force: bool = False) -> dict:
    now = _time.time()
    if not force and _live_cache["data"] is not None and now - _live_cache["at"] < 120:
        return _live_cache["data"]
    claude = None
    try:
        claude = await claude_live_usage()
    except Exception:  # noqa: BLE001 — live data is best-effort
        claude = None
    data = {
        "codex": codex_live_usage() or {"available": False, "note": "no recent codex session data — run codex once"},
        "claude": claude or {"available": False, "note": "claude -p /usage returned nothing — manual limit"},
        "antigravity": {"available": False, "note": "agy exposes no usage call — manual limit"},
    }
    _live_cache["at"] = now
    _live_cache["data"] = data
    return data


def live_summary_line() -> str:
    """Compact live-quota lines for the controller (reads the cache only)."""
    from datetime import datetime, timezone

    data = _live_cache["data"] or {}
    parts = []
    codex = data.get("codex", {})
    if codex.get("available"):
        bits = []
        for w in codex.get("windows", []):
            reset = ""
            if w.get("resetsAt"):
                dt = datetime.fromtimestamp(w["resetsAt"], tz=timezone.utc)
                hours = max(0, (dt - datetime.now(timezone.utc)).total_seconds() / 3600)
                reset = f", resets in {hours:.1f}h"
            bits.append(f"{w['label']} {w['usedPercent']:.0f}% used{reset}")
        parts.append(f"Codex live quota ({codex.get('plan', '?')}): " + "; ".join(bits))
    claude = data.get("claude", {})
    if claude.get("available"):
        bits = [
            f"{w['label']} {w['usedPercent']:.0f}% used"
            + (f" (resets {w['resetsText']})" if w.get("resetsText") else "")
            for w in claude.get("windows", [])
        ]
        parts.append("Claude live quota: " + "; ".join(bits))
    return "\n".join(parts)
