"""Real PTY terminal sessions: output streams to clients, keystrokes reach the
shell, and the session tears down cleanly. Uses a harmless `printf` launch so no
real CLI is spawned."""

import asyncio

from agentflow import terminal_service as ts


async def _drain_until(queue: asyncio.Queue, needle: bytes, timeout: float = 5.0) -> bytes:
    got = bytearray()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while needle not in got:
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        item = await asyncio.wait_for(queue.get(), timeout=remaining)
        if item is ts.CLOSED:
            break
        if isinstance(item, dict):  # lifecycle metadata rides the same queue
            continue
        got += item
    return bytes(got)


async def _streams_and_accepts_input(cwd: str) -> None:
    session = ts.TerminalSession(key="t", cwd=cwd, launch="printf 'AUTORUN\\n'")
    await session.start()
    queue: asyncio.Queue = asyncio.Queue()
    session.clients.add(queue)
    try:
        # The auto-launched command's output is streamed to connected clients.
        assert b"AUTORUN" in await _drain_until(queue, b"AUTORUN")

        # Keystrokes written to the session reach the shell (echoed back).
        session.write(b"echo TYPED\n")
        assert b"TYPED" in await _drain_until(queue, b"TYPED")

        # Output is retained in scrollback for replay to late joiners.
        assert b"AUTORUN" in bytes(session.buffer)
    finally:
        await session.terminate()
    assert session.exited is True


def test_session_streams_output_and_accepts_input(tmp_path):
    asyncio.run(_streams_and_accepts_input(str(tmp_path)))


async def _resize(cwd: str) -> tuple[int, int]:
    session = ts.TerminalSession(key="t", cwd=cwd, launch=None)
    await session.start()
    try:
        session.resize(40, 120)
        return session.rows, session.cols
    finally:
        await session.terminate()


def test_resize_updates_dimensions(tmp_path):
    assert asyncio.run(_resize(str(tmp_path))) == (40, 120)


async def _manager_lifecycle(cwd: str) -> tuple[bool, bool]:
    manager = ts.TerminalManager()
    key = ts.session_key(cwd, "codex")
    first = await manager.get_or_create(key, cwd, launch=None)
    same = await manager.get_or_create(key, cwd, launch=None)
    await manager.kill(key)
    fresh = await manager.get_or_create(key, cwd, launch=None)
    await manager.shutdown()
    return (same is first), (fresh is not first)


def test_manager_reuses_live_session_and_replaces_dead_one(tmp_path):
    reused, replaced = asyncio.run(_manager_lifecycle(str(tmp_path)))
    assert reused is True  # a live session is reused, not duplicated
    assert replaced is True  # once killed, the next connect starts a new one


async def _meta_lifecycle(cwd: str) -> list[dict]:
    """Collect the lifecycle metadata dicts a session broadcasts alongside bytes."""
    session = ts.TerminalSession(
        key="t", cwd=cwd, launch="printf 'AUTORUN\\n'", provider="antigravity", executable_path="/fake/bin/agy"
    )
    await session.start()
    queue: asyncio.Queue = asyncio.Queue()
    session.clients.add(queue)
    metas: list[dict] = []
    try:
        # Wait until the launch output arrives (which flips launching -> ready).
        await _drain_until_meta(queue, metas, state="ready")
    finally:
        await session.terminate()
    # terminate() broadcasts the closed meta too
    while not queue.empty():
        item = queue.get_nowait()
        if isinstance(item, dict):
            metas.append(item)
    return metas


async def _drain_until_meta(queue: asyncio.Queue, metas: list[dict], state: str, timeout: float = 5.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not any(m.get("state") == state for m in metas):
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        item = await asyncio.wait_for(queue.get(), timeout=remaining)
        if item is ts.CLOSED:
            break
        if isinstance(item, dict):
            metas.append(item)


def test_session_broadcasts_lifecycle_meta(tmp_path):
    metas = asyncio.run(_meta_lifecycle(str(tmp_path)))
    states = [m["state"] for m in metas]
    assert "ready" in states  # PTY produced output after the CLI launch
    assert "closed" in states  # terminate() reports closure
    ready = next(m for m in metas if m["state"] == "ready")
    assert ready["type"] == "meta"
    assert ready["provider"] == "antigravity"
    assert ready["executablePath"] == "/fake/bin/agy"


def test_launch_command_uses_resolved_executable_path(monkeypatch):
    monkeypatch.setattr(ts, "which", lambda provider: "/Users/me/.local/bin/agy")
    assert ts.launch_command("antigravity") == "/Users/me/.local/bin/agy"
    # Paths with spaces stay one shell token.
    monkeypatch.setattr(ts, "which", lambda provider: "/Users/me/App Support/agy")
    assert ts.launch_command("antigravity") == "'/Users/me/App Support/agy'"
    monkeypatch.setattr(ts, "which", lambda provider: None)
    assert ts.launch_command("antigravity") is None
