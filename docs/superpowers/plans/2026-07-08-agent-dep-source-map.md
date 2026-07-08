# Agent Dependency-Source Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agent prompts carry a concrete `name → local path` map of the workspace's direct dependencies (resolved via opensrc), so agents read real dependency source instead of guessing APIs.

**Architecture:** One new module, `backend/agentflow/dependency_service.py`: manifest discovery (workspace root + immediate subdirs) → stdlib parsing → resolution through the existing `opensrc_service.fetch()` → a manifest-hash cache at `<ws>/.agentflow/opensrc-deps.json` → a `prompt_section()` string consumed by BOTH prompt paths (`prompt_templates._compose` and `orchestrator/personas.py`), replacing their duplicated hardcoded capability line. Background refresh threads kick off on workspace select and task creation.

**Tech Stack:** Python 3.11 stdlib only (`json`, `tomllib`, `hashlib`, `threading`); existing `opensrc_service` wrapper; pytest with the fake-`OPENSRC_BIN` idiom.

## Global Constraints

- Direct deps only; total capped at **60** (dedup by name, first occurrence wins; manifest order, root first).
- Prompt fallback: when the map is empty/absent, prompts keep the exact generic line (existing `test_opensrc_capability.py` must stay green; the map rendering also contains the literal `opensrc path` escape hatch).
- Resolution never blocks a request: `refresh` runs in daemon threads; `resolved_deps`/`prompt_section` only read the cache.
- Spec: `docs/superpowers/specs/2026-07-08-agent-dep-source-map-design.md`. Gate: `make verify`. Branch: `feat/agent-dep-source-map`.
- No new dependencies. Follow the suite idiom: offline tests, fake binary via `OPENSRC_BIN`.

---

### Task 1: Manifest discovery + parsing (pure functions)

**Files:**
- Create: `backend/agentflow/dependency_service.py`
- Test: `backend/tests/test_dependency_service.py`

**Interfaces:**
- Produces: `_discover_manifests(ws: Path) -> list[Path]`; `_parse_manifests(paths: list[Path]) -> list[tuple[str, str]]` (ordered `(name, opensrc_spec)`, deduped, capped at `MAX_DEPS = 60`); `MANIFEST_NAMES` constant.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_dependency_service.py
"""dependency_service — workspace deps -> opensrc-resolved local source paths."""

from __future__ import annotations

import json

from agentflow import dependency_service


def _ws(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"zod": "^3"}, "devDependencies": {"vitest": "^2"}})
    )
    sub = tmp_path / "backend"
    sub.mkdir()
    (sub / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\n'
        'dependencies = ["fastapi[all]>=0.110,<1", "uvicorn >=0.30"]\n'
        "[project.optional-dependencies]\n"
        'dev = ["pytest>=8.0"]\n'
    )
    (sub / "requirements.txt").write_text("# comment\nrequests==2.32.0\n-r other.txt\n")
    (sub / "Cargo.toml").write_text('[package]\nname = "x"\n[dependencies]\nserde = "1"\n')
    return tmp_path


def test_discovers_root_and_subdir_manifests(tmp_path):
    found = dependency_service._discover_manifests(_ws(tmp_path))
    rels = [str(p.relative_to(tmp_path)) for p in found]
    # Root first, then subdirs alphabetically; fixed filename order within each dir.
    assert rels == [
        "package.json",
        "backend/Cargo.toml",
        "backend/pyproject.toml",
        "backend/requirements.txt",
    ]


def test_parses_all_ecosystems_normalized(tmp_path):
    ws = _ws(tmp_path)
    deps = dependency_service._parse_manifests(dependency_service._discover_manifests(ws))
    assert ("zod", "zod") in deps  # npm -> bare name
    assert ("vitest", "vitest") in deps  # devDependencies included
    assert ("serde", "crates:serde") in deps
    assert ("fastapi", "pypi:fastapi") in deps  # extras + specifiers stripped
    assert ("uvicorn", "pypi:uvicorn") in deps
    assert ("pytest", "pypi:pytest") in deps  # optional-dependencies included
    assert ("requests", "pypi:requests") in deps
    names = [n for n, _ in deps]
    assert "-r other.txt" not in str(deps)  # directives skipped
    assert len(names) == len(set(names))  # deduped


def test_cap_at_60(tmp_path):
    many = {f"pkg{i}": "^1" for i in range(70)}
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": many}))
    deps = dependency_service._parse_manifests([tmp_path / "package.json"])
    assert len(deps) == 60


def test_no_manifests_is_empty(tmp_path):
    assert dependency_service._discover_manifests(tmp_path) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests/test_dependency_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agentflow.dependency_service'` (or AttributeError).

- [ ] **Step 3: Write the implementation**

```python
# backend/agentflow/dependency_service.py
"""Workspace direct-deps -> opensrc-resolved local source paths for agent prompts.

Discovery scans the workspace root and immediate subdirectories (repos here are
often root pyproject + frontend/package.json). Parsing is stdlib-only. The
resolved map is cached per-workspace under .agentflow/ keyed by a manifest hash,
and rendered into every agent prompt by prompt_section().
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

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


def _parse_manifests(paths: list[Path]) -> list[tuple[str, str]]:
    deps: list[tuple[str, str]] = []
    seen: set[str] = set()
    for path in paths:
        for name, spec in _parse_one(path):
            if name in seen:
                continue
            seen.add(name)
            deps.append((name, spec))
            if len(deps) >= MAX_DEPS:
                return deps
    return deps
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests/test_dependency_service.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/agentflow/dependency_service.py backend/tests/test_dependency_service.py
git commit -m "feat(deps): manifest discovery + parsing for the dependency-source map"
```

---

### Task 2: Resolution + manifest-hash cache

**Files:**
- Modify: `backend/agentflow/dependency_service.py` (append)
- Modify: `backend/agentflow/opensrc_service.py` (thread a timeout through `fetch`)
- Test: `backend/tests/test_dependency_service.py` (append)

**Interfaces:**
- Consumes: `opensrc_service.fetch(pkg, timeout=...)`, `opensrc_service.available()`, `paths.workspace_app_dir(ws)`.
- Produces: `refresh(ws: Path) -> dict[str, str]`; `resolved_deps(ws: Path) -> dict[str, str]`; cache JSON `{"manifestHash", "resolved", "failed", "updatedAt"}` at `<ws>/.agentflow/opensrc-deps.json`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_dependency_service.py`. The fake binary maps `path <spec>` to a per-spec directory it creates, records every call, and fails for `pypi:privatepkg`:

```python
import stat
import textwrap

from agentflow import opensrc_service

_FAKE = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import os, sys
    ROOT = {root!r}
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    spec = sys.argv[2] if len(sys.argv) > 2 else ""
    open(os.path.join(ROOT, "calls.log"), "a").write(cmd + " " + spec + "\\n")
    if cmd == "path":
        if spec == "pypi:privatepkg":
            sys.stderr.write("not found"); sys.exit(1)
        d = os.path.join(ROOT, spec.replace(":", "_").replace("/", "_"))
        os.makedirs(d, exist_ok=True)
        print(d)
    """
)


def _fake_bin(tmp_path, monkeypatch):
    root = tmp_path / "opensrc-cache"
    root.mkdir()
    p = tmp_path / "opensrc"
    p.write_text(_FAKE.format(root=str(root)))
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv(opensrc_service.BIN_ENV, str(p))
    return root


def _calls(root) -> list[str]:
    log = root / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


def test_refresh_resolves_and_caches(tmp_path, monkeypatch):
    root = _fake_bin(tmp_path, monkeypatch)
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "package.json").write_text(json.dumps({"dependencies": {"zod": "^3"}}))
    resolved = dependency_service.refresh(ws)
    assert set(resolved) == {"zod"}
    assert (tmp_path / "opensrc-cache") in Path(resolved["zod"]).parents
    cache = json.loads((ws / ".agentflow" / "opensrc-deps.json").read_text())
    assert cache["resolved"]["zod"] == resolved["zod"]
    assert cache["manifestHash"]


def test_refresh_skips_failures_and_records_them(tmp_path, monkeypatch):
    _fake_bin(tmp_path, monkeypatch)
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "requirements.txt").write_text("privatepkg==1.0\nrequests==2.32.0\n")
    resolved = dependency_service.refresh(ws)
    assert "requests" in resolved and "privatepkg" not in resolved
    cache = json.loads((ws / ".agentflow" / "opensrc-deps.json").read_text())
    assert cache["failed"] == ["privatepkg"]


def test_refresh_is_noop_when_manifest_unchanged(tmp_path, monkeypatch):
    root = _fake_bin(tmp_path, monkeypatch)
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "package.json").write_text(json.dumps({"dependencies": {"zod": "^3"}}))
    dependency_service.refresh(ws)
    first = len(_calls(root))
    dependency_service.refresh(ws)  # same manifest -> no new CLI calls
    assert len(_calls(root)) == first
    (ws / "package.json").write_text(json.dumps({"dependencies": {"zod": "^3", "ms": "^2"}}))
    dependency_service.refresh(ws)  # manifest changed -> re-resolves
    assert len(_calls(root)) > first


def test_resolved_deps_drops_stale_paths(tmp_path, monkeypatch):
    _fake_bin(tmp_path, monkeypatch)
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "package.json").write_text(json.dumps({"dependencies": {"zod": "^3"}}))
    resolved = dependency_service.refresh(ws)
    import shutil as _sh

    _sh.rmtree(resolved["zod"])  # cache dir cleaned behind our back
    assert dependency_service.resolved_deps(ws) == {}


def test_refresh_inert_without_binary_or_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv(opensrc_service.BIN_ENV, str(tmp_path / "nope"))
    ws = tmp_path / "ws"
    ws.mkdir()
    assert dependency_service.refresh(ws) == {}
    _fake_bin(tmp_path, monkeypatch)
    assert dependency_service.refresh(ws) == {}  # no manifests
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests/test_dependency_service.py -q`
Expected: new tests FAIL with `AttributeError: ... has no attribute 'refresh'`.

- [ ] **Step 3: Implementation**

**Imports:** ruff enforces E402 (imports at module top) — merge every import shown in the appended snippets into the top-of-file import block of `dependency_service.py` (`hashlib`, `os`, `datetime`, plus `from . import opensrc_service, paths`), never mid-file. The test file's `stat`/`textwrap`/`opensrc_service` imports likewise go to its top.

In `backend/agentflow/opensrc_service.py`, change `fetch` to accept a timeout:

```python
def fetch(pkg: str, timeout: int = _TIMEOUT) -> str:
    """Fetch + cache a package's source; return its local root path."""
    out = _run(["path", pkg], timeout=timeout).strip()
    path = out.splitlines()[-1].strip() if out else ""
    if not path or not os.path.isdir(path):
        raise OpensrcUnavailable(f"opensrc did not return a valid path for {pkg!r}")
    return path
```

Append to `backend/agentflow/dependency_service.py`:

```python
import hashlib
import os
from datetime import datetime, timezone

from . import opensrc_service, paths

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests/test_dependency_service.py backend/tests/test_opensrc_service.py -q`
Expected: all pass (fetch signature change is backward-compatible).

- [ ] **Step 5: Commit**

```bash
git add backend/agentflow/dependency_service.py backend/agentflow/opensrc_service.py backend/tests/test_dependency_service.py
git commit -m "feat(deps): opensrc resolution + manifest-hash cache"
```

---

### Task 3: Background refresh + prompt_section

**Files:**
- Modify: `backend/agentflow/dependency_service.py` (append)
- Test: `backend/tests/test_dependency_service.py` (append)

**Interfaces:**
- Consumes: `config.get_current_workspace() -> Optional[Path]`.
- Produces: `start_background_refresh(ws: Path) -> None` (daemon thread, one in-flight per workspace); `prompt_section() -> str` (map section, or the generic line verbatim).

- [ ] **Step 1: Write the failing tests**

```python
def test_prompt_section_falls_back_to_generic(monkeypatch):
    monkeypatch.setattr(dependency_service.config, "get_current_workspace", lambda: None)
    assert "opensrc path" in dependency_service.prompt_section()


def test_prompt_section_renders_map(tmp_path, monkeypatch):
    _fake_bin(tmp_path, monkeypatch)
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "package.json").write_text(json.dumps({"dependencies": {"zod": "^3"}}))
    dependency_service.refresh(ws)
    monkeypatch.setattr(dependency_service.config, "get_current_workspace", lambda: ws)
    section = dependency_service.prompt_section()
    assert "Dependency source" in section
    assert "zod →" in section
    assert "opensrc path" in section  # escape hatch keeps the capability test green


def test_background_refresh_runs_once_per_workspace(tmp_path, monkeypatch):
    import threading

    started = threading.Event()
    release = threading.Event()
    calls = []

    def slow_refresh(ws):
        calls.append(ws)
        started.set()
        release.wait(timeout=5)

    monkeypatch.setattr(dependency_service, "refresh", slow_refresh)
    ws = tmp_path / "ws"
    ws.mkdir()
    dependency_service.start_background_refresh(ws)
    assert started.wait(timeout=5)
    dependency_service.start_background_refresh(ws)  # in-flight -> no second thread
    release.set()
    for _ in range(50):
        if not dependency_service._inflight:
            break
        __import__("time").sleep(0.05)
    assert calls == [ws]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest backend/tests/test_dependency_service.py -q`
Expected: FAIL with `AttributeError: ... 'prompt_section'`.

- [ ] **Step 3: Implementation**

Append to `backend/agentflow/dependency_service.py` (again: `threading` and `config` join the top-of-file imports, not mid-file):

```python
import threading

from . import config

GENERIC_LINE = (
    "Reading dependency source: run `opensrc path <pkg>` to fetch + cache any open-source "
    "package's real source and get a local path (e.g. `opensrc path zod`, "
    "`opensrc path pypi:requests`, `opensrc path owner/repo`), then read files under it."
)

_inflight: set[str] = set()
_inflight_lock = threading.Lock()


def start_background_refresh(ws: Path) -> None:
    """Kick off refresh(ws) on a daemon thread; no-op while one is in flight."""
    key = str(ws)
    with _inflight_lock:
        if key in _inflight:
            return
        _inflight.add(key)

    def _job() -> None:
        try:
            refresh(ws)
        except Exception:  # noqa: BLE001 — background best-effort, never crashes the app
            pass
        finally:
            with _inflight_lock:
                _inflight.discard(key)

    threading.Thread(target=_job, daemon=True, name="opensrc-deps-refresh").start()


def prompt_section() -> str:
    """The dependency-source block for agent prompts: the concrete resolved map
    when we have one, else the generic capability line."""
    ws = config.get_current_workspace()
    if ws is None:
        return GENERIC_LINE
    deps = resolved_deps(ws)
    if not deps:
        return GENERIC_LINE
    lines = "\n".join(f"- {name} → {path}" for name, path in deps.items())
    return (
        "Dependency source (real code — read these with your file tools instead of guessing APIs):\n"
        f"{lines}\n"
        "(+ run `opensrc path <pkg>` for anything not listed)"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest backend/tests/test_dependency_service.py -q`
Expected: `12 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/agentflow/dependency_service.py backend/tests/test_dependency_service.py
git commit -m "feat(deps): background refresh + prompt_section"
```

---

### Task 4: Wire into prompts and hooks

**Files:**
- Modify: `backend/agentflow/prompt_templates.py:21-35` (`_compose`)
- Modify: `backend/agentflow/orchestrator/personas.py:109-116` (persona prompt tail)
- Modify: `backend/agentflow/api/routes_projects.py:46-57` (`set_workspace`)
- Modify: `backend/agentflow/task_service.py:140` (`create_task`)
- Test: `backend/tests/test_opensrc_capability.py` (extend)

**Interfaces:**
- Consumes: `dependency_service.prompt_section()`, `dependency_service.start_background_refresh(ws)`, `dependency_service.GENERIC_LINE`.

- [ ] **Step 1: Extend the capability test (failing first)**

Append to `backend/tests/test_opensrc_capability.py`:

```python
def test_prompts_carry_resolved_map_when_available(monkeypatch):
    from agentflow import dependency_service

    section = (
        "Dependency source (real code — read these with your file tools instead of guessing APIs):\n"
        "- zod → /cache/zod\n"
        "(+ run `opensrc path <pkg>` for anything not listed)"
    )
    monkeypatch.setattr(dependency_service, "prompt_section", lambda: section)
    legacy = prompt_templates.codex_spec_prompt(_usage(), "tasks/t1")
    persona = task_service._build_step_prompt(_usage(), "t1", "gemini_qa", "qa-runner")
    for p in (legacy, persona):
        assert "zod → /cache/zod" in p
        assert "opensrc path" in p  # escape hatch
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest backend/tests/test_opensrc_capability.py -q`
Expected: FAIL — prompts still contain only the hardcoded generic line, not `zod → /cache/zod`.

- [ ] **Step 3: Implementation (4 small edits)**

`prompt_templates.py` — import and replace the hardcoded tail in `_compose`:

```python
from . import controller_protocol, dependency_service, ponytail
```

```python
def _compose(usage: dict, task_rel_dir: str, body: str) -> str:
    # Ponytail rides in every step prompt (output-side token reduction — the
    # agents write less code and shorter docs). Headroom compresses the input
    # side; together they are the token-management strategy (Pillar 1).
    pony = ponytail.block()
    return (
        f"{budget_context_header(usage)}\n\n"
        f"Task folder: {task_rel_dir}/\n"
        "All numbered markdown files mentioned below live in the task folder.\n\n"
        f"{body.strip()}"
        + (f"\n\n{pony}" if pony else "")
        + f"\n\n{dependency_service.prompt_section()}"
    )
```

`orchestrator/personas.py` — replace the duplicated literal (lines 111-116):

```python
    from .. import dependency_service

    prompt = "\n\n".join(parts)
    pony = ponytail.block()
    return prompt + (f"\n\n{pony}" if pony else "") + f"\n\n{dependency_service.prompt_section()}"
```

(Put the import at the top of the file with the other `from .. import` lines if one exists; otherwise module-top `from agentflow import dependency_service` matching the file's existing import style.)

`api/routes_projects.py` — kick off resolution on workspace select (after the recovery block, before `return`):

```python
    # Resolve the workspace's dependency sources in the background so agent
    # prompts can list real local paths (never blocks selection).
    dependency_service.start_background_refresh(Path(cfg["workspacePath"]))
```

with `from .. import dependency_service` added to the module imports.

`task_service.py` — first line of `create_task` body:

```python
    dependency_service.start_background_refresh(workspace)  # cheap no-op when fresh
```

with `dependency_service` added to the module's existing `from . import ...` line.

- [ ] **Step 4: Run the affected suites**

Run: `.venv/bin/python -m pytest backend/tests/test_opensrc_capability.py backend/tests/test_dependency_service.py backend/tests/test_task_engine_prompt.py backend/tests/test_task_service.py backend/tests/test_context_routes.py -q`
Expected: all pass — the fallback keeps every existing "opensrc path" assertion green.

- [ ] **Step 5: Commit**

```bash
git add backend/agentflow/prompt_templates.py backend/agentflow/orchestrator/personas.py backend/agentflow/api/routes_projects.py backend/agentflow/task_service.py backend/tests/test_opensrc_capability.py
git commit -m "feat(deps): agent prompts carry the resolved dependency-source map"
```

---

### Task 5: Full gate + live check + PR

**Files:** none new.

- [ ] **Step 1: Full local gate**

Run: `make verify`
Expected: ruff + format + mypy + full backend pytest + frontend checks all pass.

- [ ] **Step 2: Live smoke (real opensrc, real workspace)**

```bash
# restart the backend so the new hooks load, select a workspace with a
# package.json, then:
curl -s -X POST http://localhost:8787/api/projects/workspace \
  -H 'Content-Type: application/json' -d '{"path":"/Users/cody/AgentComposer"}' | head -c 200
sleep 20  # background resolution
cat /Users/cody/AgentComposer/.agentflow/opensrc-deps.json | head -c 400
.venv/bin/python -c "
from agentflow import dependency_service
print(dependency_service.prompt_section()[:500])
"
```

Expected: the cache file lists resolved deps; `prompt_section()` prints the `name → path` map.

- [ ] **Step 3: Push + PR**

```bash
git push -u origin feat/agent-dep-source-map
gh pr create --base main --head feat/agent-dep-source-map \
  --title "Agent prompts carry a resolved dependency-source map (opensrc)" \
  --body "Resolves the workspace's direct deps to local source paths (background, cached by manifest hash) and lists them in every agent prompt, replacing the generic opensrc capability line. Spec: docs/superpowers/specs/2026-07-08-agent-dep-source-map-design.md"
```

Expected: PR opens; CI green (no opensrc on CI → the service is inert and prompts keep the generic line, which the tests cover).
