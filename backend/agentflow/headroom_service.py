"""Pillar 1 — Headroom as an in-process library (input-side token reduction).

Headroom (github.com/headroomlabs-ai/headroom, the ``headroom-ai`` Python
package — a backend dependency) compresses bulky machine context: logs, JSON,
repeated tool output. We call it **in-process** on the context blocks CLITC
embeds into the prompts it builds for its own CLIs (consult output tails,
workspace/task-state summaries). No proxy, no base-URL env injection, no
long-running process: scope is exactly the prompts CLITC assembles — external
CLIs and the agents' own API traffic are untouched.

How it stays safe:
- Headroom's router **protects user-role messages verbatim** and only crushes
  ``tool``-role content, so we send instructions as the user message (it doubles
  as the relevance query) and the bulky context as the tool message. CLITC's
  instructions and the CLITC_RESULT_V1 contract can never be rewritten.
- **Fail-open everywhere**: disabled, library missing, short input, zero savings,
  or any exception → the original text comes back unchanged.
- **Off the event loop**: compression is CPU-bound (rust core), so the async
  entry point runs it in a thread.
"""

from __future__ import annotations

import asyncio
import importlib.util
from typing import Optional

from . import config

_DEFAULTS: dict[str, object] = {
    "enabled": True,  # primary token-reduction path; fail-open keeps it safe
    "minChars": 1500,  # below this, compression can't pay for itself
}

# Token accounting for this backend session (surfaced in Settings/status).
_stats = {"calls": 0, "compressed": 0, "tokensSaved": 0}

# Headroom keys pruning to the model's context budget; any current model id works.
_COMPRESS_MODEL = "claude-sonnet-4-5-20250929"


def settings() -> dict:
    """Merged Headroom settings (defaults + global config `headroom` section)."""
    cfg = config.load_global_config().get("headroom") or {}
    return {**_DEFAULTS, **cfg}


def is_enabled() -> bool:
    return bool(settings().get("enabled"))


def installed() -> bool:
    try:
        return importlib.util.find_spec("headroom") is not None
    except (ImportError, ValueError):
        return False


def _compress_sync(text: str, instructions: str) -> Optional[str]:
    """One in-process compression pass. Returns the compressed context, or None
    when nothing was saved (caller keeps the original). Raises nothing upward —
    the async wrapper owns fail-open."""
    from headroom import compress  # heavy import, deliberately lazy

    result = compress(
        [
            # user role = protected verbatim AND the relevance query for pruning
            {"role": "user", "content": instructions or "Keep what matters from this context."},
            {"role": "tool", "content": text},
        ],
        model=_COMPRESS_MODEL,
    )
    _stats["calls"] += 1
    saved = int(getattr(result, "tokens_saved", 0) or 0)
    if saved <= 0:
        return None
    compressed = next(
        (m.get("content") for m in result.messages if m.get("role") == "tool"),
        None,
    )
    if not isinstance(compressed, str) or not compressed.strip() or len(compressed) >= len(text):
        return None
    _stats["compressed"] += 1
    _stats["tokensSaved"] += saved
    return compressed


async def compress_context(text: str, instructions: str = "") -> str:
    """Compress one bulky, already-redacted context block for a prompt CLITC is
    building. Fail-open: any reason not to compress returns ``text`` unchanged."""
    s = settings()
    if not s.get("enabled") or len(text) < int(s.get("minChars") or 0) or not installed():
        return text
    try:
        compressed = await asyncio.to_thread(_compress_sync, text, instructions)
        return compressed if compressed is not None else text
    except Exception:  # noqa: BLE001 — token saving must never break a prompt
        return text


def status() -> dict:
    """Headroom status for the settings UI / API."""
    s = settings()
    return {
        "enabled": bool(s["enabled"]),
        "installed": installed(),
        "mode": "local",  # in-process library; the proxy integration was retired
        "minChars": int(s.get("minChars") or 0),
        "callsCompressed": _stats["compressed"],
        "tokensSaved": _stats["tokensSaved"],
    }
