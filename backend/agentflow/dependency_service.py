"""Workspace direct-deps -> opensrc-resolved local source paths for agent prompts.

Discovery scans the workspace root and immediate subdirectories (repos here are
often root pyproject + frontend/package.json). Parsing is stdlib-only. The
resolved map is cached per-workspace under .agentflow/ keyed by a manifest hash,
and rendered into every agent prompt by prompt_section().
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from . import opensrc_service, paths

MAX_DEPS = 60
# Fixed order within a directory (deterministic prompts).
MANIFEST_NAMES = ["package.json", "Cargo.toml", "pyproject.toml", "requirements.txt"]


def _discover_manifests(ws: Path) -> list[Path]:
    found: list[Path] = []
    for name in MANIFEST_NAMES:
        p = ws / name
        if p.is_file():
            found.append(p)
    for sub in sorted(d for d in ws.iterdir() if d.is_dir() and not d.name.startswith(".")):
        for name in MANIFEST_NAMES:
            p = sub / name
            if p.is_file():
                found.append(p)
    return found


# PEP 508-ish: name up to the first extra/specifier/marker character.
_PY_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _py_name(requirement: str) -> str | None:
    line = requirement.strip()
    if not line or line.startswith(("#", "-")):  # comments + pip directives (-r, -e, --hash)
        return None
    m = _PY_NAME.match(line)
    return m.group(1) if m else None


def _parse_one(path: Path) -> list[tuple[str, str]]:
    try:
        if path.name == "package.json":
            data = json.loads(path.read_text())
            names = list(data.get("dependencies") or {}) + list(data.get("devDependencies") or {})
            return [(n, n) for n in names]
        if path.name == "pyproject.toml":
            data = tomllib.loads(path.read_text())
            reqs = list((data.get("project") or {}).get("dependencies") or [])
            for extra in ((data.get("project") or {}).get("optional-dependencies") or {}).values():
                reqs.extend(extra)
            names = [n for n in (_py_name(r) for r in reqs) if n]
            return [(n, f"pypi:{n}") for n in names]
        if path.name == "requirements.txt":
            names = [n for n in (_py_name(line) for line in path.read_text().splitlines()) if n]
            return [(n, f"pypi:{n}") for n in names]
        if path.name == "Cargo.toml":
            data = tomllib.loads(path.read_text())
            return [(n, f"crates:{n}") for n in (data.get("dependencies") or {})]
    except (OSError, ValueError):  # unreadable/malformed manifest -> contribute nothing
        return []
    return []


def _parse_manifests(manifests: list[Path]) -> list[tuple[str, str]]:
    deps: list[tuple[str, str]] = []
    seen: set[str] = set()
    for path in manifests:
        for name, spec in _parse_one(path):
            if name in seen:
                continue
            seen.add(name)
            deps.append((name, spec))
            if len(deps) >= MAX_DEPS:
                return deps
    return deps


# --- resolution + cache ------------------------------------------------------

_CACHE_NAME = "opensrc-deps.json"
_PER_DEP_TIMEOUT = 120  # a big first fetch is slow once; opensrc caches globally


def _cache_path(ws: Path) -> Path:
    return paths.workspace_app_dir(ws) / _CACHE_NAME


def _manifest_hash(manifests: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(manifests):
        st = p.stat()
        h.update(f"{p}|{st.st_mtime_ns}|{st.st_size}\n".encode())
    return h.hexdigest()


def _read_cache(ws: Path) -> dict:
    try:
        return json.loads(_cache_path(ws).read_text())
    except (OSError, ValueError):
        return {}


def refresh(ws: Path) -> dict[str, str]:
    """Resolve the workspace's direct deps to local source paths and cache them.
    No-op when opensrc is missing, no manifest exists, or the manifests are
    unchanged since the last run."""
    if not opensrc_service.available():
        return {}
    manifests = _discover_manifests(ws)
    if not manifests:
        return {}
    digest = _manifest_hash(manifests)
    cache = _read_cache(ws)
    if cache.get("manifestHash") == digest:
        return dict(cache.get("resolved") or {})
    resolved: dict[str, str] = {}
    failed: list[str] = []
    for name, spec in _parse_manifests(manifests):
        try:
            resolved[name] = opensrc_service.fetch(spec, timeout=_PER_DEP_TIMEOUT)
        except opensrc_service.OpensrcUnavailable:
            failed.append(name)
    out = {
        "manifestHash": digest,
        "resolved": resolved,
        "failed": failed,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    cache_file = _cache_path(ws)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(out, indent=2))
    return resolved


def resolved_deps(ws: Path) -> dict[str, str]:
    """Cached name -> path map (fast read; never resolves). Drops entries whose
    source dir no longer exists (e.g. removed from the Sources tab)."""
    cached = _read_cache(ws).get("resolved") or {}
    return {n: p for n, p in cached.items() if os.path.isdir(p)}
