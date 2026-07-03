"""Pillar 1 — Headroom, the primary token-reduction layer (fail-open).

Headroom (`headroom proxy`, github.com/headroomlabs-ai/headroom) is a
context-optimization proxy between an agent CLI and its model provider: it
compresses prompts/tool output (60–95% fewer tokens) while preserving accuracy.
When enabled and reachable, agent CLIs we spawn route through it via their
base-URL env var:

    claude  → ANTHROPIC_BASE_URL = <proxy>
    codex   → OPENAI_BASE_URL    = <proxy>/v1

Design invariants (see docs/PILLARS.md, Pillar 1):
- **Primary but fail-open**: ON by default; if headroom isn't installed, the
  proxy is unreachable, or the probe is slow, the agent runs directly against
  its provider. Headroom must never be *required* for ordinary execution.
- **Bounded**: the reachability probe is a short TCP connect (300 ms) and its
  result is cached briefly, so it never delays spawning or live output.
- **Managed**: when enabled and the `headroom` executable is installed, CLITC
  starts and owns the proxy itself (`ensure_proxy`) with the configured
  `agent-savings` profile applied — no manual `scripts/headroom.sh` step.
"""

from __future__ import annotations

import shlex
import socket
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from . import config

# Default proxy on :8799 — deliberately NOT :8787 (the AgentComposer backend port,
# which is also Headroom's own default — running both on 8787 would collide).
_DEFAULTS: dict[str, object] = {
    "enabled": True,  # primary token-reduction path; fail-open keeps it safe
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


# ------------------------------------------------------------ managed proxy
# CLITC owns the proxy process when enabled+installed: started on backend boot
# and on settings save, with the configured `agent-savings` profile applied.
# Everything below is best-effort — failure to manage the proxy must never
# break the app (agents just run direct, per fail-open).

_proxy_run_id: Optional[str] = None


def executable() -> Optional[str]:
    from .provider_probe import resolve_executable  # local: avoid import cycle

    return resolve_executable("headroom")


def _proxy_port(url: str) -> int:
    return urlsplit(url).port or 8799


def managed_running() -> bool:
    from .process_runner import RUNNER  # local: avoid import cycle

    if not _proxy_run_id:
        return False
    record = RUNNER.runs.get(_proxy_run_id)
    return record is not None and record.status == "running"


async def _savings_profile_env(binary: str, profile: str) -> dict[str, str]:
    """The HEADROOM_* env for the chosen savings profile, from
    `headroom agent-savings --profile <p> --format shell` (export KEY=VALUE lines)."""
    from .process_runner import RUNNER  # local

    record = await RUNNER.run_and_wait(
        [binary, "agent-savings", "--profile", profile, "--format", "shell"],
        Path.home(),
        timeout=15,
        provider="headroom",
    )
    env: dict[str, str] = {}
    if record.exit_code != 0:
        return env
    for line in record.stdout.splitlines():
        line = line.strip()
        if line.startswith("export "):
            key, _, value = line[len("export ") :].partition("=")
            if key and value:
                try:
                    parts = shlex.split(value)
                except ValueError:
                    continue
                if parts:
                    env[key.strip()] = parts[0]
    return env


async def ensure_proxy() -> dict:
    """Start the managed Headroom proxy if enabled, installed, and not already
    serving. Returns the resulting status(). Never raises."""
    global _proxy_run_id
    try:
        s = settings()
        if not s.get("enabled"):
            return status()
        url = str(s["proxyUrl"]).rstrip("/")
        if managed_running() or proxy_reachable(url):
            return status()  # ours is up, or the user runs their own — done
        binary = executable()
        if binary is None:
            return status()  # not installed → agents run direct (fail-open)

        from .process_runner import RUNNER, add_log_entry  # local

        profile = str(s.get("savingsProfile") or "agent-90")
        env = await _savings_profile_env(binary, profile)
        record, _task = await RUNNER.start(
            [binary, "proxy", "--port", str(_proxy_port(url))],
            Path.home(),
            step="headroom",
            provider="headroom",
            extra_env=env,
            # no max_runtime: like the preview dev server, it runs for the session
        )
        if record.status == "error":
            add_log_entry(
                "system",
                f"headroom proxy failed to start: {record.stderr.strip()[:200]}",
                status="warn",
            )
            return status()
        _proxy_run_id = record.id
        _probe_cache.update(url=None)  # forget the failed probe immediately
        add_log_entry("system", f"headroom proxy started on :{_proxy_port(url)} (profile {profile})")
    except Exception as exc:  # noqa: BLE001 — managing the proxy is best-effort
        try:
            from .process_runner import add_log_entry

            add_log_entry("system", f"headroom proxy management failed: {exc}", status="warn")
        except Exception:  # noqa: BLE001
            pass
    return status()


async def stop_proxy() -> None:
    """Stop the managed proxy (settings toggled off). User-run proxies untouched."""
    global _proxy_run_id
    if _proxy_run_id:
        from .process_runner import RUNNER  # local

        await RUNNER.cancel(_proxy_run_id)
        _proxy_run_id = None
        _probe_cache.update(url=None)


def status() -> dict:
    """Headroom status for the settings UI / API."""
    s = settings()
    enabled = bool(s["enabled"])
    return {
        "enabled": enabled,
        "installed": executable() is not None,
        "executablePath": executable(),
        "proxyUrl": s["proxyUrl"],
        "savingsProfile": s["savingsProfile"],
        "reachable": proxy_reachable(str(s["proxyUrl"])) if enabled else False,
        "managed": managed_running(),
        "routedProviders": sorted(_PROVIDER_BASE_URL_ENV.keys()),
    }
