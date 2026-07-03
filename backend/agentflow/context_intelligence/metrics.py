"""Token metrics via the already-installed ``headroom`` package, fail-open.

``TokenCounter`` in headroom-ai is a Protocol and cannot be instantiated;
the working recipe is ``get_tokenizer(model)`` + ``count_tokens_text``.
Any failure falls back to the ``len(text) // 4`` estimate — metrics must
never crash the pipeline.
"""

from __future__ import annotations

from typing import Any, Optional

from .types import TokenUsage

_COUNTER_MODEL = "claude-sonnet-4-5-20250929"
_tokenizer: Optional[Any] = None
_tokenizer_failed = False


def _get_tokenizer() -> Optional[Any]:
    global _tokenizer, _tokenizer_failed
    if _tokenizer is None and not _tokenizer_failed:
        try:
            from headroom.tokenizers import get_tokenizer

            _tokenizer = get_tokenizer(_COUNTER_MODEL)
        except Exception:  # noqa: BLE001 — fail open to the estimate
            _tokenizer_failed = True
    return _tokenizer


def count_tokens(text: str) -> tuple[int, str]:
    """Return ``(tokens, counter_name)``; counter_name records which counter ran."""
    tokenizer = _get_tokenizer()
    if tokenizer is not None:
        try:
            from headroom import count_tokens_text

            return int(count_tokens_text(text, tokenizer)), f"headroom:{_COUNTER_MODEL}"
        except Exception:  # noqa: BLE001 — fail open to the estimate
            pass
    return len(text) // 4, "estimate"


def usage(text_before: str, text_after: str) -> TokenUsage:
    before, counter = count_tokens(text_before)
    after, _ = count_tokens(text_after)
    savings = round(100.0 * (before - after) / before, 2) if before > 0 else 0.0
    return TokenUsage(tokensBefore=before, tokensAfter=after, counter=counter, savingsPct=savings)
