"""The terminal WS must never go half-dead: when the output pump stops (session
killed, transient send failure), the socket must CLOSE so the pane's onclose
fires and it self-heals by reconnecting. A half-open socket is a frozen pane
that still silently forwards keystrokes to the PTY (the "agy terminal is
broken" bug)."""

from __future__ import annotations

import pytest
from agentflow import config
from agentflow.api import routes_terminals
from agentflow.app import create_app
from agentflow.terminal_service import TERMINALS
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


class FakeSession:
    """Session double: enough surface for the WS route, no real PTY."""

    def __init__(self) -> None:
        self.buffer = bytearray(b"$ ")
        self.clients: set = set()
        self.writes: list[bytes] = []
        self.repaints = 0

    def current_meta(self) -> dict:
        return {"type": "meta", "state": "ready", "provider": "antigravity", "executablePath": "/bin/agy"}

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def resize(self, rows: int, cols: int) -> None:
        pass

    def force_repaint(self) -> None:
        self.repaints += 1


@pytest.fixture()
def fake_terminal(tmp_path, monkeypatch):
    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    config.ensure_workspace(ws_dir)
    monkeypatch.setattr(config, "get_current_workspace", lambda: ws_dir)
    session = FakeSession()

    async def fake_get_or_create(key, cwd, cmd, provider=None, executable_path=None):
        return session

    monkeypatch.setattr(TERMINALS, "get_or_create", fake_get_or_create)
    return session


def test_pump_death_closes_socket_so_client_can_reconnect(fake_terminal):
    client = TestClient(create_app())
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/terminals/antigravity/ws") as ws:
            assert ws.receive_bytes() == b"$ "  # scrollback snapshot
            assert ws.receive_json()["state"] == "ready"  # lifecycle meta
            assert len(fake_terminal.clients) == 1
            # Kill the pump the way terminal_service does on session teardown.
            queue = next(iter(fake_terminal.clients))
            queue.put_nowait(routes_terminals.CLOSED)
            # The socket must CLOSE (not hang half-open): this receive should
            # raise, proving the client's onclose would fire and reconnect.
            ws.receive_bytes()


def test_input_still_reaches_session_before_close(fake_terminal):
    client = TestClient(create_app())
    with client.websocket_connect("/api/terminals/antigravity/ws") as ws:
        ws.receive_bytes()
        ws.receive_json()
        ws.send_json({"type": "input", "data": "hi"})
        # receive loop and pump are independent; give the loop one turn via a
        # second frame round-trip (resize is a no-op ack path).
        ws.send_json({"type": "resize", "rows": 30, "cols": 100})
    assert b"hi" in b"".join(fake_terminal.writes)
    # Every attachment must force a TUI repaint — a same-size reattach otherwise
    # shows a blank screen (replayed paint history) while input flows invisibly.
    assert fake_terminal.repaints >= 1
