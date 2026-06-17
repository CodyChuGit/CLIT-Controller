"""Regression tests for the cross-origin guard on mutating requests (audit P1-09).

CORS does not stop a cross-site request from executing server-side, so mutating
methods are additionally gated on Origin/Referer — mirroring the WebSocket check.
"""

from __future__ import annotations

from agentflow.app import create_app
from fastapi.testclient import TestClient

POST_PATH = "/api/logs/clear-view"  # simple, side-effect-light mutating endpoint


def _client() -> TestClient:
    return TestClient(create_app())


def test_post_with_foreign_origin_is_rejected():
    r = _client().post(POST_PATH, headers={"origin": "http://evil.example"})
    assert r.status_code == 403


def test_post_with_app_origin_is_allowed():
    r = _client().post(POST_PATH, headers={"origin": "http://localhost:5180"})
    assert r.status_code == 200


def test_post_with_no_origin_is_allowed():
    # Native clients / tests omit Origin; they are intentionally allowed.
    assert _client().post(POST_PATH).status_code == 200


def test_post_with_foreign_referer_is_rejected():
    r = _client().post(POST_PATH, headers={"referer": "http://evil.example/page"})
    assert r.status_code == 403


def test_get_is_not_origin_guarded():
    # Reads are not state-changing; a foreign Origin on GET is fine.
    r = _client().get("/api/health", headers={"origin": "http://evil.example"})
    assert r.status_code == 200
