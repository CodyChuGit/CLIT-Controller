"""Real PTY-backed terminal sessions.

Each CLI terminal in the UI is a genuine pseudo-terminal running an interactive
shell in the workspace (with the agent CLI auto-launched). Output is streamed
raw over a WebSocket and keystrokes/resizes flow back, so the panes behave like
a real terminal — ANSI colors, TUIs, job control and all. Sessions outlive a
single WebSocket connection so switching tabs doesn't kill a running CLI; a
bounded scrollback buffer is replayed when a client (re)connects."""

from __future__ import annotations

import asyncio
import fcntl
import os
import pty
import signal
import struct
import termios
from pathlib import Path
from typing import Optional

from .provider_probe import EXTRA_BIN_DIRS, which

SCROLLBACK_BYTES = 256_000
READ_CHUNK = 65_536

# Queue sentinel meaning "the session ended — stop pumping to this client".
CLOSED = object()


def _shell() -> str:
    return os.environ.get("SHELL") or "/bin/bash"


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env["TERM"] = "xterm-256color"
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("COLORTERM", "truecolor")
    # Make sure user-bin dirs (where the CLIs often live) resolve for commands
    # the user types, not just the auto-launched one.
    extra = os.pathsep.join(str(d) for d in EXTRA_BIN_DIRS)
    if extra:
        env["PATH"] = extra + os.pathsep + env.get("PATH", "")
    return env


class TerminalSession:
    """One PTY + child process, fanning output out to any connected clients."""

    def __init__(self, key: str, cwd: str, launch: Optional[str]) -> None:
        self.key = key
        self.cwd = cwd
        self.launch = launch  # command auto-run once at startup, or None
        self.master_fd: int = -1
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.buffer = bytearray()
        self.clients: set[asyncio.Queue] = set()
        self.rows = 24
        self.cols = 80
        self.exited = False

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd
        self._set_winsize(self.rows, self.cols)
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        self.proc = await asyncio.create_subprocess_exec(
            _shell(),
            "-i",
            cwd=self.cwd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            start_new_session=True,
            env=_child_env(),
        )
        os.close(slave_fd)
        loop.add_reader(master_fd, self._on_readable)
        asyncio.create_task(self._watch_exit())

        if self.launch:
            async def _kick() -> None:
                await asyncio.sleep(0.4)  # let the shell print its prompt first
                self.write((self.launch + "\n").encode())

            asyncio.create_task(_kick())

    # -- pty plumbing -------------------------------------------------------

    def _set_winsize(self, rows: int, cols: int) -> None:
        if self.master_fd < 0:
            return
        try:
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

    def resize(self, rows: int, cols: int) -> None:
        self.rows, self.cols = max(1, rows), max(1, cols)
        self._set_winsize(self.rows, self.cols)

    def write(self, data: bytes) -> None:
        if self.master_fd >= 0 and not self.exited:
            try:
                os.write(self.master_fd, data)
            except OSError:
                pass

    def _broadcast(self, item) -> None:
        for q in list(self.clients):
            try:
                q.put_nowait(item)
            except asyncio.QueueFull:
                pass

    def _on_readable(self) -> None:
        try:
            data = os.read(self.master_fd, READ_CHUNK)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            data = b""
        if not data:  # EOF — the child closed the pty
            self._detach_reader()
            return
        self.buffer += data
        excess = len(self.buffer) - SCROLLBACK_BYTES
        if excess > 0:
            del self.buffer[:excess]
        self._broadcast(bytes(data))

    def _detach_reader(self) -> None:
        if self.master_fd < 0:
            return
        try:
            asyncio.get_running_loop().remove_reader(self.master_fd)
        except (ValueError, OSError, RuntimeError):
            pass

    async def _watch_exit(self) -> None:
        if self.proc is not None:
            await self.proc.wait()
        self.exited = True
        self._detach_reader()
        note = b"\r\n\x1b[2m[session ended \xe2\x80\x94 reconnect to restart]\x1b[0m\r\n"
        self.buffer += note
        self._broadcast(bytes(note))
        self._broadcast(CLOSED)

    async def terminate(self) -> None:
        self._detach_reader()
        if self.proc is not None and self.proc.returncode is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    self.proc.terminate()
                except ProcessLookupError:
                    pass
        if self.master_fd >= 0:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = -1
        self.exited = True
        self._broadcast(CLOSED)


class TerminalManager:
    def __init__(self) -> None:
        self.sessions: dict[str, TerminalSession] = {}

    async def get_or_create(self, key: str, cwd: str, launch: Optional[str]) -> TerminalSession:
        session = self.sessions.get(key)
        if session is not None and not session.exited:
            return session
        session = TerminalSession(key, cwd, launch)
        await session.start()
        self.sessions[key] = session
        return session

    async def kill(self, key: str) -> None:
        session = self.sessions.pop(key, None)
        if session is not None:
            await session.terminate()

    async def shutdown(self) -> None:
        for session in list(self.sessions.values()):
            await session.terminate()
        self.sessions.clear()


def session_key(workspace: Path, provider: str) -> str:
    return f"{workspace}::{provider}"


def launch_command(provider: str) -> Optional[str]:
    """The bare CLI command to auto-run for a provider, or None if not installed."""
    found = which(provider)
    return os.path.basename(found) if found else None


TERMINALS = TerminalManager()
