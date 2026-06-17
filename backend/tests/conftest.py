"""Shared test fixtures.

The whole suite must be hermetic: it must never read or write the developer's
real global state under ``~/.agentflow``. The autouse fixture below redirects the
global config directory (and ``$HOME``) to a per-test temp dir, so selecting a
workspace, recording usage, sweeping terminal sessions, etc. all operate on
throwaway state. Per-workspace state already lives under each test's ``tmp_path``.
"""

from __future__ import annotations

import pytest
from agentflow import paths


@pytest.fixture(autouse=True)
def isolated_global_state(tmp_path_factory, monkeypatch):
    # Use a uniquely-named temp dir for the fake home, never under (or a string
    # prefix of) the test's tmp_path workspace: many tests use tmp_path itself as
    # the workspace, so a home inside it — or one whose path prefix-matches it —
    # would make ~-relative paths resolve "inside" and break confinement asserts.
    home = tmp_path_factory.mktemp("fakehome")
    global_dir = home / ".agentflow"
    global_dir.mkdir(parents=True, exist_ok=True)
    # Redirect both the explicit accessor and HOME, so code paths that call
    # paths.global_config_dir() and any that reach for Path.home() directly
    # (e.g. config.set_workspace's home-dir guard) stay inside the sandbox.
    monkeypatch.setattr(paths, "global_config_dir", lambda: global_dir)
    monkeypatch.setenv("HOME", str(home))
    yield
