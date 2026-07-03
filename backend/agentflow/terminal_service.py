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
import shlex
import signal
import struct
import subprocess
import termios
from pathlib import Path
from typing import Optional

from . import paths
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


# -- orphan reaping ---------------------------------------------------------
# Sessions detach from the backend (start_new_session=True) so their TUIs get
# clean keystroke delivery — but that also means they outlive a backend that is
# SIGKILLed or crashes before its shutdown hook runs. We drop a pidfile per
# session and sweep stale ones on the next startup, so leaked agy/codex/claude
# process groups (each holding memory + random ports) can't pile up across runs.


def _record_session(pid: int, shell: str) -> Optional[Path]:
    try:
        run_dir = paths.terminals_run_dir()
        run_dir.mkdir(parents=True, exist_ok=True)
        pidfile = run_dir / f"{pid}.session"
        pidfile.write_text(shell)
        return pidfile
    except OSError:
        return None


def _clear_session_file(pidfile: Optional[Path]) -> None:
    if pidfile is None:
        return
    try:
        pidfile.unlink()
    except OSError:
        pass


def _proc_tty_and_cmd(pid: int) -> tuple[str, str]:
    """(controlling tty, command) for a live pid, or ("", "") if it's gone."""
    try:
        out = subprocess.run(
            ["ps", "-o", "tty=", "-o", "command=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "", ""
    line = out.stdout.strip()
    if not line:
        return "", ""
    tty, _, cmd = line.partition(" ")
    return tty, cmd.strip()


def sweep_orphaned_sessions() -> int:
    """Reap terminal process-groups left behind by a previously crashed or
    SIGKILLed backend. Safe to call on startup: it only signals a recorded pid
    that is still a detached shell we plausibly spawned (no controlling tty plus a
    matching shell name), which guards against pid reuse pointing at an unrelated
    process. Returns the number of groups signalled."""
    try:
        run_dir = paths.terminals_run_dir()
    except OSError:
        return 0
    if not run_dir.is_dir():
        return 0
    reaped = 0
    for pidfile in run_dir.glob("*.session"):
        try:
            pid = int(pidfile.stem)
        except ValueError:
            _clear_session_file(pidfile)
            continue
        try:
            shell_base = os.path.basename(pidfile.read_text().strip())
        except OSError:
            shell_base = ""
        tty, cmd = _proc_tty_and_cmd(pid)
        # Our PTY shells have no controlling tty ("??"); a real user shell always
        # has one. Together with the recorded shell name this avoids killing an
        # unrelated process that happened to reuse the pid.
        ours = bool(cmd) and tty in ("??", "?") and (not shell_base or shell_base in cmd)
        if ours:
            # SIGKILL the whole group: these are already abandoned, and an
            # interactive shell ignores SIGTERM while a TUI ignores the pty EOF,
            # so a gentle signal would leave them lingering.
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
                reaped += 1
            except (ProcessLookupError, PermissionError, OSError):
                pass
        _clear_session_file(pidfile)
    return reaped


class TerminalSession:
    """One PTY + child process, fanning output out to any connected clients.

    Besides raw PTY bytes, the session broadcasts small ``dict`` metadata items
    (state transitions) through the same client queues; the WS route serializes
    them as JSON text frames while bytes stay binary — so the UI can tell "PTY
    up but the CLI is still launching" apart from "dead box"."""

    def __init__(
        self,
        key: str,
        cwd: str,
        launch: Optional[str],
        provider: Optional[str] = None,
        executable_path: Optional[str] = None,
    ) -> None:
        self.key = key
        self.cwd = cwd
        self.launch = launch  # command auto-run once at startup, or None
        self.provider = provider
        self.executable_path = executable_path
        self.state = "launching"  # launching -> ready -> closed
        self.exit_code: Optional[int] = None
        self.master_fd: int = -1
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.buffer = bytearray()
        self.clients: set[asyncio.Queue] = set()
        self.rows = 24
        self.cols = 80
        self.exited = False
        self._pidfile: Optional[Path] = None
        self._launch_written = launch is None  # readiness counts output after the CLI launch

    def current_meta(self) -> dict:
        meta: dict[str, object] = {
            "type": "meta",
            "state": self.state,
            "provider": self.provider,
            "executablePath": self.executable_path,
        }
        if self.state == "closed":
            meta["exitCode"] = self.exit_code
            meta["reason"] = "pty_closed"
        return meta

    def _set_state(self, state: str) -> None:
        if self.state != state:
            self.state = state
            self._broadcast(self.current_meta())

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
            # New session so the shell owns its own process group, but WITHOUT
            # claiming the pty as a controlling terminal. That keeps bash -i's
            # job control effectively off, so keystrokes flow straight through
            # to an auto-launched TUI like `agy` (bubbletea). Making the shell a
            # controlling-tty owner turns job control on and swallows input.
            start_new_session=True,
            env=_child_env(),
        )
        os.close(slave_fd)
        # Record the child's pid (== its process-group id, since start_new_session
        # makes it the group leader) so a future backend can reap this session if
        # we die abruptly without running our shutdown hook. See sweep_orphaned_sessions.
        self._pidfile = _record_session(self.proc.pid, _shell())
        loop.add_reader(master_fd, self._on_readable)
        asyncio.create_task(self._watch_exit())

        if self.launch:
            launch = self.launch  # bind non-None value for the closure

            async def _kick() -> None:
                await asyncio.sleep(0.4)  # let the shell print its prompt first
                self.write((launch + "\n").encode())
                self._launch_written = True

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
        # ponytail: "ready" = first PTY output after the CLI launch was submitted —
        # a round-trip heuristic, not TUI introspection; auth/init text still shows
        # in the terminal itself. Upgrade path: classify known auth/error patterns.
        if self.state == "launching" and self._launch_written:
            self._set_state("ready")
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
            self.exit_code = self.proc.returncode
        self.exited = True
        _clear_session_file(self._pidfile)
        self._detach_reader()
        # Close the PTY master here too: a child that exits on its own (the user
        # typed `exit`, the CLI quit) leaves the session in the manager until
        # someone reconnects, so without this the master fd leaks for the life of
        # the process and eventually exhausts the fd limit.
        if self.master_fd >= 0:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = -1
        note = b"\r\n\x1b[2m[session ended \xe2\x80\x94 reconnect to restart]\x1b[0m\r\n"
        self.buffer += note
        self._broadcast(bytes(note))
        self._set_state("closed")
        self._broadcast(CLOSED)

    async def terminate(self) -> None:
        self._detach_reader()
        pgid: Optional[int] = None
        if self.proc is not None and self.proc.returncode is None:
            try:
                pgid = os.getpgid(self.proc.pid)
            except (ProcessLookupError, OSError):
                pgid = None
            try:
                if pgid is not None:
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    self.proc.terminate()
            except (ProcessLookupError, PermissionError, OSError):
                pass
        if self.master_fd >= 0:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = -1
        # Force-kill backstop: an interactive shell ignores SIGTERM and a TUI can
        # ignore the EOF from closing the pty, so without this a restarted/closed
        # session could linger as an orphan (and slip past the startup sweep, since
        # we clear its pidfile below). Give it ~1s to go on its own, then SIGKILL.
        if pgid is not None:
            for _ in range(10):
                if self.proc is None or self.proc.returncode is not None:
                    break
                await asyncio.sleep(0.1)
            else:
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
        self.exited = True
        _clear_session_file(self._pidfile)
        self._set_state("closed")
        self._broadcast(CLOSED)


class TerminalManager:
    def __init__(self) -> None:
        self.sessions: dict[str, TerminalSession] = {}

    async def get_or_create(
        self,
        key: str,
        cwd: str,
        launch: Optional[str],
        provider: Optional[str] = None,
        executable_path: Optional[str] = None,
    ) -> TerminalSession:
        session = self.sessions.get(key)
        if session is not None and not session.exited:
            return session
        session = TerminalSession(key, cwd, launch, provider=provider, executable_path=executable_path)
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


# NOTE: do NOT auto-submit a starter prompt to Antigravity's `agy` via
# `-i <prompt>`. agy spends several seconds after launch on auth / experiment /
# quota init (the log shows transient "You are not logged into Antigravity"
# errors until it settles). A prompt handed to it during that window — whether
# typed or passed with `-i` — is accepted, cleared, and never dispatched, leaving
# the TUI stuck in a busy state that won't take input. Launch the bare CLI and
# let the user type once it's ready.
def launch_command(provider: str) -> Optional[str]:
    """The bare CLI command to auto-run for a provider, or None if not installed.

    Uses the RESOLVED executable path (quoted — user-bin paths can contain spaces)
    rather than the basename, so launch does not depend on the child shell's PATH
    happening to include the install dir (revamp Workstream 3)."""
    found = which(provider)
    return shlex.quote(found) if found else None


TERMINALS = TerminalManager()
