"""Characterization tests for the live-terminal WebSocket route.

This route attaches a browser to a PTY running a real interactive shell, so its
defenses are security-critical: the cross-site-WebSocket-hijack (CSWSH) Origin
allow-list, the unknown-provider close code, and workspace gating. These tests
pin that behaviour so it cannot silently regress (see audit finding P1-10). They
exercise only the gating paths and never spawn a real shell — the session
primitives are covered separately by test_terminal_service.py.
"""

from __future__ import annotations

import pytest
from agentflow.app import create_app
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _client() -> TestClient:
    return TestClient(create_app())


def test_ws_rejects_foreign_origin():
    """A page on another origin must not be able to open a shell socket (CSWSH)."""
    client = _client()
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/terminals/claude/ws", headers={"origin": "http://evil.example"}):
            pass
    assert exc.value.code == 4403


def test_ws_allows_app_origin_handshake():
    """The app's own dev/prod origin passes the Origin check (reaches accept)."""
    client = _client()
    # No workspace is selected in the hermetic test env, so after the handshake the
    # server sends the "No workspace" notice and closes normally — proving the
    # Origin check did NOT reject this origin with 4403.
    with client.websocket_connect("/api/terminals/claude/ws", headers={"origin": "http://localhost:5180"}) as ws:
        msg = ws.receive_bytes()
        assert b"No workspace" in msg


def test_ws_rejects_unknown_provider():
    """An unknown provider segment is closed with 4404 after the handshake."""
    client = _client()
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/terminals/bogus/ws") as ws:
            ws.receive_bytes()
    assert exc.value.code == 4404


def test_ws_missing_origin_is_allowed():
    """Native clients/tests send no Origin header and are intentionally allowed
    (documented residual risk); they still hit workspace gating, not 4403."""
    client = _client()
    with client.websocket_connect("/api/terminals/codex/ws") as ws:
        msg = ws.receive_bytes()
        assert b"No workspace" in msg
