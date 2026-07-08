"""opensrc integration — fetch any package's real source for agents + the Sources tab.

``opensrc path <pkg>`` fetches + caches a package's source and prints a local path.
Registry prefixes (verified against the CLI source, 2026-07): bare npm, ``npm:``,
``pypi:``/``pip:``/``python:``, ``crates:``/``cargo:``/``rust:``, ``gitlab:``,
``bitbucket:``, or ``<owner>/<repo>`` / a full URL. There is NO ``github:`` prefix
— use ``owner/repo``. Cache lives under ``~/.opensrc`` (override via ``OPENSRC_HOME``).

The binary is resolved from ``$OPENSRC_BIN`` (tests point this at a fake) or
``opensrc`` on PATH.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

BIN_ENV = "OPENSRC_BIN"
DEFAULT_BIN = "opensrc"
_TIMEOUT = 300
_MAX_TREE = 4000
_MAX_FILE_BYTES = 200_000
_IGNORE = {".git", "node_modules", "__pycache__", ".venv", "dist", ".next"}


class OpensrcUnavailable(RuntimeError):
    """Raised when the binary is missing or a command fails."""


def binary() -> Optional[str]:
    explicit = os.environ.get(BIN_ENV)
    if explicit:
        return explicit if os.path.exists(explicit) else None
    found = shutil.which(DEFAULT_BIN)
    if found:
        return found
    fallback = os.path.expanduser(f"~/.local/bin/{DEFAULT_BIN}")
    return fallback if os.access(fallback, os.X_OK) else None


def available() -> bool:
    return binary() is not None


def _run(args: list[str], timeout: int = _TIMEOUT) -> str:
    exe = binary()
    if not exe:
        raise OpensrcUnavailable(f"{DEFAULT_BIN} is not installed")
    try:
        proc = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise OpensrcUnavailable(f"opensrc {args[0]} timed out") from exc
    if proc.returncode != 0:
        raise OpensrcUnavailable(f"opensrc {args[0]} failed: {(proc.stderr or proc.stdout).strip()[:500]}")
    return proc.stdout


def fetch(pkg: str, timeout: int = _TIMEOUT) -> str:
    """Fetch + cache a package's source; return its local root path."""
    out = _run(["path", pkg], timeout=timeout).strip()
    path = out.splitlines()[-1].strip() if out else ""
    if not path or not os.path.isdir(path):
        raise OpensrcUnavailable(f"opensrc did not return a valid path for {pkg!r}")
    return path


def remove(pkg: str) -> None:
    """Remove a package's cached source (wraps ``opensrc remove``)."""
    _run(["remove", pkg])


def list_cached() -> list:
    try:
        out = _run(["list", "--json"]).strip()
    except OpensrcUnavailable:
        return []
    if not out:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("packages") or data.get("sources") or []
    return []


def _safe_join(root: str, relpath: str) -> Path:
    base = Path(root).resolve()
    target = (base / relpath).resolve()
    if not target.is_relative_to(base):
        raise OpensrcUnavailable("path escapes the package root")
    return target


def tree(pkg: str) -> dict:
    root = fetch(pkg)
    base = Path(root)
    entries: list[dict] = []
    for p in sorted(base.rglob("*")):
        rel = p.relative_to(base)
        if any(part in _IGNORE for part in rel.parts):
            continue
        entries.append({"path": str(rel), "type": "dir" if p.is_dir() else "file"})
        if len(entries) >= _MAX_TREE:
            break
    return {"pkg": pkg, "root": root, "entries": entries, "truncated": len(entries) >= _MAX_TREE}


def read(pkg: str, relpath: str) -> dict:
    root = fetch(pkg)
    target = _safe_join(root, relpath)
    if not target.is_file():
        raise OpensrcUnavailable(f"not a file: {relpath}")
    text = target.read_text(errors="replace")[:_MAX_FILE_BYTES]
    return {"pkg": pkg, "path": relpath, "content": text}


def search(pkg: str, query: str, max_results: int = 200) -> list:
    root = fetch(pkg)
    rg = shutil.which("rg")
    matches: list[dict] = []
    if rg:
        proc = subprocess.run(
            [rg, "-n", "--no-heading", "-m", "3", "--", query, root],
            capture_output=True,
            text=True,
            timeout=60,
        )
        for line in proc.stdout.splitlines()[:max_results]:
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            fp, ln, txt = parts
            try:
                rel = str(Path(fp).relative_to(root))
            except ValueError:
                rel = fp
            matches.append({"path": rel, "line": int(ln) if ln.isdigit() else 0, "text": txt.strip()[:200]})
        return matches
    # Python fallback when ripgrep isn't installed.
    base = Path(root)
    for p in base.rglob("*"):
        if not p.is_file() or any(part in _IGNORE for part in p.relative_to(base).parts):
            continue
        try:
            content = p.read_text(errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(content.splitlines(), 1):
            if query in line:
                matches.append({"path": str(p.relative_to(base)), "line": i, "text": line.strip()[:200]})
                if len(matches) >= max_results:
                    return matches
    return matches
