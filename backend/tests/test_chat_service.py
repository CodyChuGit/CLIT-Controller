import asyncio
import copy
from pathlib import Path

from agentflow import chat_service, config
from agentflow.prompt_templates import orchestrator_chat_prompt
from agentflow.process_runner import RunRecord
from agentflow.usage_service import DEFAULT_USAGE


def make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    return ws


def test_chat_prompt_includes_budget_and_message():
    usage = copy.deepcopy(DEFAULT_USAGE)
    prompt = orchestrator_chat_prompt(usage, "Workspace: /tmp/x", "user: hi\nassistant: hello", "what next?")
    assert prompt.startswith("Budget context:")
    assert "Workspace: /tmp/x" in prompt
    assert "user: what next?" in prompt
    assert "orchestration model" in prompt


def test_append_load_clear_roundtrip(tmp_path):
    ws = make_workspace(tmp_path)
    chat_service.append_message(ws, "user", "hello there")
    chat_service.append_message(ws, "assistant", "hi", provider="codex")
    data = chat_service.load_chat(ws)
    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]
    chat_service.clear_chat(ws)
    assert chat_service.load_chat(ws)["messages"] == []


def test_send_with_missing_provider_is_graceful(tmp_path):
    ws = make_workspace(tmp_path)
    result = asyncio.run(chat_service.send(ws, "plan my feature", provider="no-such-binary-xyz"))
    assert result["status"] == "provider_missing"
    messages = chat_service.load_chat(ws)["messages"]
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "system"
    assert "not installed" in messages[1]["content"]


def test_direct_channels_are_separate(tmp_path):
    ws = make_workspace(tmp_path)
    chat_service.append_message(ws, "user", "orchestrator question")
    chat_service.append_message(ws, "user", "codex question", channel="codex")
    chat_service.append_message(ws, "assistant", "codex answer", channel="codex", provider="codex")

    state = chat_service.chat_state(ws)
    assert [m["content"] for m in state["messages"]] == ["orchestrator question"]
    assert [m["content"] for m in state["channels"]["codex"]] == ["codex question", "codex answer"]
    assert state["channels"]["claude"] == []
    assert set(state["channelPending"]) == {"codex", "claude", "antigravity"}

    chat_service.clear_chat(ws, channel="codex")
    state = chat_service.chat_state(ws)
    assert state["channels"]["codex"] == []
    assert [m["content"] for m in state["messages"]] == ["orchestrator question"]


def test_direct_send_missing_provider_is_graceful(tmp_path, monkeypatch):
    ws = make_workspace(tmp_path)
    monkeypatch.setattr(chat_service, "resolve_executable", lambda _argv0: None)
    result = asyncio.run(chat_service.send_direct(ws, "codex", "hello"))
    assert result["status"] == "provider_missing"
    msgs = chat_service.chat_state(ws)["channels"]["codex"]
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "system"
    assert "not installed" in msgs[1]["content"]


def test_direct_send_rejects_unknown_provider(tmp_path):
    ws = make_workspace(tmp_path)
    result = asyncio.run(chat_service.send_direct(ws, "shell", "rm everything"))
    assert result["status"] == "error"


def test_orchestrator_send_rejects_busy_provider(tmp_path, monkeypatch):
    ws = make_workspace(tmp_path)
    record = RunRecord(id="busy-codex", argv=["codex"], cwd=str(ws), provider="codex", step="chat")
    monkeypatch.setattr(chat_service.RUNNER, "runs", {record.id: record})

    result = asyncio.run(chat_service.send(ws, "plan this", provider="codex"))

    assert result["status"] == "provider_busy"
    assert result["runId"] == "busy-codex"
    assert chat_service.load_chat(ws)["messages"] == []


def test_direct_send_rejects_busy_provider(tmp_path, monkeypatch):
    ws = make_workspace(tmp_path)
    record = RunRecord(id="busy-codex", argv=["codex"], cwd=str(ws), provider="codex", step="orchestrate")
    monkeypatch.setattr(chat_service.RUNNER, "runs", {record.id: record})

    result = asyncio.run(chat_service.send_direct(ws, "codex", "hello"))

    assert result["status"] == "provider_busy"
    assert result["runId"] == "busy-codex"
    assert chat_service.chat_state(ws)["channels"]["codex"] == []


def test_direct_chat_prompt_has_no_directives():
    from agentflow.prompt_templates import direct_chat_prompt

    prompt = direct_chat_prompt("claude", "user: hi\nassistant: hello", "fix the header")
    assert "agentflow-" in prompt  # the "no directives" instruction names them
    assert "```agentflow" not in prompt  # but teaches no directive blocks
    assert "user: fix the header" in prompt


def test_chat_messages_are_redacted(tmp_path):
    ws = make_workspace(tmp_path)
    chat_service.append_message(ws, "user", "my key is sk-secret12345678 ok?")
    content = chat_service.load_chat(ws)["messages"][0]["content"]
    assert "sk-secret" not in content
    assert "[REDACTED]" in content
