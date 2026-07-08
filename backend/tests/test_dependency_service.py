"""dependency_service — workspace deps -> opensrc-resolved local source paths."""

from __future__ import annotations

import json
import stat
import textwrap
from pathlib import Path

from agentflow import dependency_service, opensrc_service


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


# --- resolution + cache (fake opensrc binary; offline) ----------------------

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
    assert root in Path(resolved["zod"]).parents
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


# --- background refresh + prompt_section -------------------------------------


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
    import time

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
        time.sleep(0.05)
    assert calls == [ws]
