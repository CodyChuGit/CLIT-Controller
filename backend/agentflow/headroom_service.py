"""Pillar 1 — optional, fail-open Headroom token-saving integration.

Headroom (`headroom proxy`) is a context-optimization layer that sits between an
agent CLI and its model provider, compressing prompt context to cut tokens while
preserving accuracy. When enabled and a configured proxy is reachable, we route
the agent CLIs we spawn through it by injecting their base-URL env var:

    claude  → ANTHROPIC_BASE_URL = <proxy>
    codex   → OPENAI_BASE_URL    = <proxy>/v1

Design invariants (see docs/PILLARS.md, Pillar 1):
- **Optional**: off by default; enabled via global config `headroom.enabled`.
- **Fail-open**: if disabled, the proxy is unreachable, or the probe is slow, the
  agent runs directly against its provider. Headroom must never be *required* for
  ordinary execution.
- **Bounded**: the reachability probe is a short TCP connect (300 ms) and its
  result is cached briefly, so it never delays spawning or live output.

The savings *profile* (compression aggressiveness, accuracy guard) is the proxy's
own concern — start it with `scripts/headroom.sh` (which applies the configured
`headroom agent-savings` profile). This module only points the agents at it.
"""

from __future__ import annotations

import socket
import time
from urllib.parse import urlsplit

from . import config

# Default proxy on :8799 — deliberately NOT :8787 (the AgentComposer backend port,
# which is also Headroom's own default — running both on 8787 would collide).
_DEFAULTS: dict[str, object] = {
    "enabled": False,
    "proxyUrl": "http://127.0.0.1:8799",
    "savingsProfile": "agent-90",
}

_PROBE_TIMEOUT = 0.3  # seconds — bounded; fail-open past this
_PROBE_CACHE_TTL = 5.0  # seconds — don't re-probe on every spawn
_probe_cache: dict[str, object] = {"url": None, "ok": False, "at": 0.0}

# Which providers can be routed through the proxy, and the env var to set.
# Antigravity (`agy`, Google) is intentionally excluded — it is not an
# Anthropic/OpenAI-compatible client for this proxy.
_PROVIDER_BASE_URL_ENV = {
    "claude": ("ANTHROPIC_BASE_URL", ""),
    "codex": ("OPENAI_BASE_URL", "/v1"),
}


def settings() -> dict:
    """Merged Headroom settings (defaults + global config `headroom` section)."""
    cfg = config.load_global_config().get("headroom") or {}
    return {**_DEFAULTS, **cfg}


def is_enabled() -> bool:
    return bool(settings().get("enabled"))


def _tcp_reachable(url: str) -> bool:
    parts = urlsplit(url)
    host = parts.hostname or "127.0.0.1"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def proxy_reachable(url: str | None = None) -> bool:
    """Bounded, briefly-cached TCP reachability check for the proxy."""
    url = url or str(settings()["proxyUrl"])
    now = time.monotonic()
    if _probe_cache["url"] == url and (now - float(_probe_cache["at"])) < _PROBE_CACHE_TTL:  # type: ignore[arg-type]
        return bool(_probe_cache["ok"])
    ok = _tcp_reachable(url)
    _probe_cache.update(url=url, ok=ok, at=now)
    return ok


def proxy_env(provider: str | None) -> dict[str, str]:
    """Env to inject into an agent child so its LLM calls route through Headroom.

    Returns ``{}`` (i.e. run directly against the provider) when Headroom is
    disabled, the provider is unsupported, or the proxy is unreachable. This is the
    fail-open path — callers merge the result into the child env unconditionally.
    """
    if not provider or not is_enabled():
        return {}
    mapping = _PROVIDER_BASE_URL_ENV.get(provider)
    if mapping is None:
        return {}
    s = settings()
    url = str(s["proxyUrl"]).rstrip("/")
    if not proxy_reachable(url):
        return {}  # fail-open: proxy down → run direct
    var, suffix = mapping
    return {var: url + suffix}


def status() -> dict:
    """Headroom status for the settings UI / API."""
    s = settings()
    enabled = bool(s["enabled"])
    return {
        "enabled": enabled,
        "proxyUrl": s["proxyUrl"],
        "savingsProfile": s["savingsProfile"],
        "reachable": proxy_reachable(str(s["proxyUrl"])) if enabled else False,
        "routedProviders": sorted(_PROVIDER_BASE_URL_ENV.keys()),
    }
