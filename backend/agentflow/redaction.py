"""Redact secret-looking values from logs and command previews."""

from __future__ import annotations

import re

REPLACEMENT = "[REDACTED]"

# Order matters: longer/more specific patterns first.
PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"xoxb-[A-Za-z0-9_\-]+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{6,}"),
    # OPENAI_API_KEY=..., ANTHROPIC_API_KEY=..., GEMINI_API_KEY=..., API_KEY=...
    re.compile(r"(?i)\b[A-Z0-9_]*API_KEY\s*=\s*[^\s\"']+"),
    re.compile(r"(?i)\btoken\s*=\s*[^\s\"']+"),
    re.compile(r"(?i)\bpassword\s*=\s*[^\s\"']+"),
]


def redact(text: str | None) -> str:
    """Return text with secret-looking substrings replaced by [REDACTED]."""
    if not text:
        return ""
    for pattern in PATTERNS:
        text = pattern.sub(REPLACEMENT, text)
    return text
