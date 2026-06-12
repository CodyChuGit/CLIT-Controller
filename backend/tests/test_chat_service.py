import asyncio
import copy
from pathlib import Path

from agentflow import chat_service, config
from agentflow.prompt_templates import orchestrator_chat_prompt
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


def test_chat_messages_are_redacted(tmp_path):
    ws = make_workspace(tmp_path)
    chat_service.append_message(ws, "user", "my key is sk-secret12345678 ok?")
    content = chat_service.load_chat(ws)["messages"][0]["content"]
    assert "sk-secret" not in content
    assert "[REDACTED]" in content
