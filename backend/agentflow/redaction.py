"""Redact secret-looking values from logs and command previews."""

from __future__ import annotations

import re

REPLACEMENT = "[REDACTED]"

# Order matters: longer/more specific patterns first.
PATTERNS: list[re.Pattern[str]] = [
    # Multi-line PEM private key blocks (RSA/EC/OPENSSH/PGP …).
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    # Provider/token literals.
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"gh[oprsu]_[A-Za-z0-9_]+"),  # gho_/ghp_/ghr_/ghs_/ghu_
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]+"),  # Slack bot/app/refresh/… tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),           # AWS access key id
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),     # Google API key
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{6,}"),
    # KEY=value / KEY: value forms for anything that looks secret. Covers
    # *API_KEY, *SECRET*, *TOKEN, *PASSWORD, AWS_SECRET_ACCESS_KEY, etc.
    re.compile(r"(?i)\b[A-Z0-9_]*(?:API[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|ACCESS[_-]?KEY)[A-Z0-9_]*\s*[:=]\s*[^\s\"']+"),
    re.compile(r"(?i)\b(?:token|password|passwd|secret)\s*[:=]\s*[^\s\"']+"),
]

# Credentials embedded in URLs (scheme://user:secret@host): mask only the
# password, keeping the scheme/user and the `@` so the URL stays recognizable.
_URL_CRED: re.Pattern[str] = re.compile(r"([a-zA-Z][a-zA-Z0-9+.\-]*://[^\s:/@]+:)[^\s/@]+(@)")


def redact(text: str | None) -> str:
    """Return text with secret-looking substrings replaced by [REDACTED]."""
    if not text:
        return ""
    text = _URL_CRED.sub(r"\1" + REPLACEMENT + r"\2", text)
    for pattern in PATTERNS:
        text = pattern.sub(REPLACEMENT, text)
    return text
