"""Allowed local origins — single source of truth for the CORS, CSRF, and
WebSocket-origin checks so they can never drift (audit P2-10 / P3-39).

The app only ever serves itself: same-origin on ``:8787`` (single-port mode) or
through the Vite dev server on ``:5180`` which proxies ``/api`` (see
``frontend/vite.config.ts``). It binds loopback only and has no authentication, so
a browser on any other origin must not be able to drive the API."""

from __future__ import annotations

from urllib.parse import urlsplit

LOCAL_ORIGINS: frozenset[str] = frozenset(
    {
        "http://localhost:5180",
        "http://127.0.0.1:5180",
        "http://localhost:8787",
        "http://127.0.0.1:8787",
    }
)


def is_allowed_origin(origin: str | None) -> bool:
    """True if ``origin`` is one of the app's own local origins, OR is absent.

    A missing/empty Origin (native clients, tests, some same-origin navigations) is
    treated as allowed; callers that want to *require* a known origin should check
    presence separately."""
    return not origin or origin in LOCAL_ORIGINS


def origin_of(url: str | None) -> str | None:
    """Reduce a URL (e.g. a Referer header) to its scheme://host[:port] origin."""
    if not url:
        return None
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"
