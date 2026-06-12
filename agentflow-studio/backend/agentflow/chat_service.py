"""Persistent chat with the orchestration model, executed via the user's own CLI agents."""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path
from typing import Optional

from . import config, git_service, paths, prompt_templates, task_service, usage_service
from .process_runner import RUNNER, RunRecord, add_log_entry, now_iso
from .provider_probe import AGENT_PROVIDER_IDS
from .redaction import redact

MAX_STORED_MESSAGES = 200
REPLAY_MESSAGES = 12      # how many past messages are replayed to the CLI
REPLAY_CLIP_CHARS = 1500  # per-message clip when replaying

# workspace path -> run id of the in-flight chat response
_pending: dict[str, str] = {}


def _chat_file(workspace: Path) -> Path:
    return paths.workspace_app_dir(workspace) / "chat.json"


def load_chat(workspace: Path) -> dict:
    data = config.read_json(_chat_file(workspace), None)
    if not isinstance(data, dict) or "messages" not in data:
        data = {"messages": []}
    return data


def _save_chat(workspace: Path, data: dict) -> None:
    data["updatedAt"] = now_iso()
    if len(data["messages"]) > MAX_STORED_MESSAGES:
        data["messages"] = data["messages"][-MAX_STORED_MESSAGES:]
    config.write_json(_chat_file(workspace), data)


def append_message(workspace: Path, role: str, content: str, **extra) -> dict:
    data = load_chat(workspace)
    msg = {"role": role, "content": redact(content), "time": now_iso(), **extra}
    data["messages"].append(msg)
    _save_chat(workspace, data)
    return msg


def clear_chat(workspace: Path) -> None:
    _save_chat(workspace, {"messages": []})


def provider_options() -> list[dict]:
    """Agent CLIs selectable in the chat header, with installed flags."""
    templates = config.get_command_templates()
    out = []
    for pid in AGENT_PROVIDER_IDS:
        template = templates.get(pid, f"{pid} {{prompt}}")
        argv0 = shlex.split(template)[0]
        out.append({"id": pid, "installed": shutil.which(argv0) is not None})
    return out


def pending_state(workspace: Path) -> Optional[dict]:
    run_id = _pending.get(str(workspace))
    if not run_id:
        return None
    record = RUNNER.runs.get(run_id)
    if record is None or record.status != "running":
        # finished (on_complete clears) or evicted — either way nothing is in flight
        if record is None:
            _pending.pop(str(workspace), None)
        return None
    tail = (record.stdout + ("\n" + record.stderr if record.stderr else ""))[-1200:]
    return {"runId": run_id, "status": record.status, "outputTail": redact(tail)}


async def _workspace_summary(workspace: Path) -> str:
    git = await git_service.git_info(workspace)
    if git.get("isRepo"):
        git_line = f"branch {git.get('branch')}, {git.get('changedFileCount', 0)} changed files"
    else:
        git_line = "not a git repository"
    tasks = task_service.list_tasks(workspace)[:5]
    task_lines = "".join(f"\n- {t['id']}: {t['title']} ({t['status']})" for t in tasks) or " none yet"
    return f"Workspace: {workspace} ({git_line})\nRecent AgentFlow tasks:{task_lines}"


def _transcript(workspace: Path) -> str:
    msgs = [m for m in load_chat(workspace)["messages"] if m["role"] in ("user", "assistant")]
    recent = msgs[-REPLAY_MESSAGES:]
    lines = []
    for m in recent:
        content = m["content"]
        if len(content) > REPLAY_CLIP_CHARS:
            content = content[:REPLAY_CLIP_CHARS] + " …[clipped]"
        lines.append(f"{m['role']}: {content}")
    return "\n".join(lines)


async def send(workspace: Path, message: str, provider: Optional[str] = None) -> dict:
    """Append the user message and start a real CLI run for the reply."""
    if pending_state(workspace) is not None:
        return {"status": "busy", "message": "A response is already in progress. Stop it or wait."}

    routing = config.get_workspace_routing(workspace)
    provider = provider or routing.get("orchestrator", "gemini")
    usage = usage_service.ensure_usage(workspace)

    if provider == "claude" and usage_service.provider_health(usage, "claude") == "red":
        return {
            "status": "claude_red",
            "message": "Claude usage health is RED — pick a cheaper provider for chat (codex/gemini) or update its health on the Usage page.",
        }

    append_message(workspace, "user", message)

    template = config.get_command_templates().get(provider, f"{provider} {{prompt}}")
    argv0 = shlex.split(template)[0]
    if shutil.which(argv0) is None:
        note = (
            f"`{provider}` is not installed (`{argv0}` not on PATH). "
            "Switch the chat provider in the header, or install it and re-check on the Agents page."
        )
        append_message(workspace, "system", note, provider=provider)
        return {"status": "provider_missing", "message": note}

    # Build the prompt only after the cheap checks pass.
    transcript = _transcript(workspace)
    summary = await _workspace_summary(workspace)
    prompt = prompt_templates.orchestrator_chat_prompt(usage, summary, transcript, message)
    argv = task_service._build_argv(template, prompt)

    ws_key = str(workspace)

    async def on_complete(record: RunRecord) -> None:
        try:
            usage_service.record_call(
                workspace,
                provider,
                prompt_chars=len(prompt),
                output_chars=len(record.stdout) + len(record.stderr),
                duration_ms=record.duration_ms or 0,
                status=record.status,
            )
            out = record.stdout.strip()
            if record.status == "succeeded" and out:
                append_message(workspace, "assistant", out, provider=provider,
                               durationMs=record.duration_ms)
            elif record.status == "cancelled":
                append_message(workspace, "system", "Response stopped.", provider=provider)
            else:
                err_tail = (record.stderr or record.stdout or "no output").strip()[-800:]
                append_message(
                    workspace, "system",
                    f"`{provider}` exited with {record.exit_code}: {err_tail}",
                    provider=provider,
                )
            add_log_entry(
                "chat",
                f"orchestrator chat via {provider}: {record.status} in {(record.duration_ms or 0) / 1000:.1f}s",
                provider=provider, step="chat",
                status="info" if record.status == "succeeded" else "warn",
            )
        finally:
            if _pending.get(ws_key) == record.id:
                _pending.pop(ws_key, None)

    record, _task = await RUNNER.start(argv, workspace, step="chat", provider=provider, on_complete=on_complete)
    if record.status == "error":
        _pending.pop(ws_key, None)
        note = f"Could not start `{provider}`: {record.stderr.strip()[:300]}"
        append_message(workspace, "system", note, provider=provider)
        return {"status": "error", "message": note}

    _pending[ws_key] = record.id
    return {"status": "started", "runId": record.id, "provider": provider}


async def stop(workspace: Path) -> dict:
    run_id = _pending.get(str(workspace))
    if not run_id:
        return {"stopped": False}
    ok = await RUNNER.cancel(run_id)
    return {"stopped": ok}


def chat_state(workspace: Path) -> dict:
    routing = config.get_workspace_routing(workspace)
    return {
        "messages": load_chat(workspace)["messages"],
        "pending": pending_state(workspace),
        "defaultProvider": routing.get("orchestrator", "gemini"),
        "providers": provider_options(),
    }
