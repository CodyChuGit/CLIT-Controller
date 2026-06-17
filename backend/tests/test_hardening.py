"""Regression tests for misc production-hardening fixes (audit P2-11, P2-22)."""

from __future__ import annotations

import asyncio
import shutil
import subprocess

import pytest
from agentflow import chat_service, git_service


def test_chat_send_rejects_unknown_provider(tmp_path):
    # An unknown provider must be rejected before any template lookup / launch (P2-11).
    res = asyncio.run(chat_service.send(tmp_path, "hi", provider="bogus"))
    assert res["status"] == "error"
    assert "bogus" in res["message"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_file_diff_refuses_env(tmp_path):
    # The untracked-file synthesis path must not surface .env contents (P2-22).
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".env").write_text("SECRET=ghp_AAAAAAAAAAAAAAAAAAAAAAAA\n")
    res = asyncio.run(git_service.file_diff(tmp_path, ".env", staged=False))
    assert "ghp_" not in res["diff"]
    assert "not shown" in res["diff"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_file_diff_shows_normal_untracked_file(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "notes.txt").write_text("hello world\n")
    res = asyncio.run(git_service.file_diff(tmp_path, "notes.txt", staged=False))
    assert "hello world" in res["diff"]
