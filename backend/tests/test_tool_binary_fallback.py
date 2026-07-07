"""Tools installed to ~/.local/bin (the installer default) are found even off-PATH."""

from __future__ import annotations

import shutil

from agentflow import memory_service, opensrc_service


def _stub_local_bin(tmp_path, monkeypatch, name):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(shutil, "which", lambda _n: None)  # not on PATH
    bindir = tmp_path / ".local" / "bin"
    bindir.mkdir(parents=True)
    b = bindir / name
    b.write_text("#!/bin/sh\n")
    b.chmod(0o755)
    return b


def test_memory_binary_found_in_local_bin(tmp_path, monkeypatch):
    monkeypatch.delenv(memory_service.BIN_ENV, raising=False)
    b = _stub_local_bin(tmp_path, monkeypatch, "codebase-memory-mcp")
    assert memory_service.binary() == str(b)


def test_opensrc_binary_found_in_local_bin(tmp_path, monkeypatch):
    monkeypatch.delenv(opensrc_service.BIN_ENV, raising=False)
    b = _stub_local_bin(tmp_path, monkeypatch, "opensrc")
    assert opensrc_service.binary() == str(b)
