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
