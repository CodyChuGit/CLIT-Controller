"""Persistent chat with the orchestration model, executed via the user's own CLI agents."""

from __future__ import annotations

import re
import shlex
import shutil
from pathlib import Path
from typing import Optional

from . import config, git_service, paths, prompt_templates, queue_service, task_service, usage_service
from .process_runner import RUNNER, RunRecord, add_log_entry, now_iso
from .provider_probe import AGENT_PROVIDER_IDS, resolve_executable
from .redaction import redact

MAX_STORED_MESSAGES = 200
REPLAY_MESSAGES = 12      # how many past messages are replayed to the CLI
REPLAY_CLIP_CHARS = 1500  # per-message clip when replaying

# workspace path -> run id of the in-flight chat response
_pending: dict[str, str] = {}

_TASK_DIRECTIVE_RE = re.compile(r"```agentflow-task\s*\n(.*?)```", re.DOTALL)
_QUEUE_DIRECTIVE_RE = re.compile(r"```agentflow-queue\s*\n(.*?)```", re.DOTALL)


def _parse_steps(raw: str) -> Optional[list[str]]:
    """'full' → the standard sequence; otherwise a comma list of valid step ids."""
    raw = raw.strip().lower()
    if not raw:
        return None
    if raw == "full":
        return list(task_service.FULL_SEQUENCE)
    steps = [s.strip() for s in raw.split(",") if s.strip()]
    if steps and all(s in task_service.STEP_DEFS for s in steps):
        return steps
    return None


def parse_task_directive(text: str) -> Optional[tuple[str, str, Optional[list[str]]]]:
    """Extract (title, goal, queue_steps) from an ```agentflow-task``` block."""
    m = _TASK_DIRECTIVE_RE.search(text or "")
    if not m:
        return None
    title, goal_lines, queue_steps, in_goal = None, [], None, False
    for line in m.group(1).splitlines():
        lower = line.lower()
        if lower.startswith("title:") and title is None:
            title = line[6:].strip()
            in_goal = False
        elif lower.startswith("goal:"):
            goal_lines.append(line[5:].strip())
            in_goal = True
        elif lower.startswith("queue:"):
            queue_steps = _parse_steps(line[6:])
            in_goal = False
        elif in_goal and line.strip():
            goal_lines.append(line.strip())
    goal = " ".join(goal_lines).strip()
    if not title or not goal:
        return None
    return title[:200], goal, queue_steps


def parse_queue_directive(text: str) -> Optional[tuple[str, list[str]]]:
    """Extract (task_ref, steps) from an ```agentflow-queue``` block. task_ref may be 'latest'."""
    m = _QUEUE_DIRECTIVE_RE.search(text or "")
    if not m:
        return None
    task_ref, steps = None, None
    for line in m.group(1).splitlines():
        lower = line.lower()
        if lower.startswith("task:"):
            task_ref = line[5:].strip()
        elif lower.startswith("steps:"):
            steps = _parse_steps(line[6:])
    if not task_ref or not steps:
        return None
    return task_ref, steps


def _resolve_task_ref(workspace: Path, ref: str) -> Optional[str]:
    tasks = task_service.list_tasks(workspace)
    if not tasks:
        return None
    if ref.lower() in ("latest", "last", "newest"):
        return tasks[0]["id"]
    for t in tasks:
        if t["id"] == ref or t["id"].endswith(ref) or ref in t["id"]:
            return t["id"]
    return None


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
        out.append({"id": pid, "installed": resolve_executable(argv0) is not None})
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
    return (
        f"Workspace: {workspace} ({git_line})\n"
        f"{queue_service.summary_line(workspace)}\n"
        f"Recent AgentFlow tasks:{task_lines}"
    )


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
    provider = provider or routing.get("orchestrator", "antigravity")
    usage = usage_service.ensure_usage(workspace)

    if provider == "claude" and usage_service.provider_health(usage, "claude") == "red":
        return {
            "status": "claude_red",
            "message": "Claude usage health is RED — pick a cheaper provider for chat (codex/antigravity) or update its health on the Usage page.",
        }

    append_message(workspace, "user", message)

    template = config.get_command_templates().get(provider, f"{provider} {{prompt}}")
    argv0 = shlex.split(template)[0]
    if resolve_executable(argv0) is None:
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
    argv = task_service._build_argv(template, prompt, config.get_models().get(provider))

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
                # The orchestrator can create tasks and queue steps via fenced blocks.
                directive = parse_task_directive(out)
                if directive is not None:
                    title, goal, queue_steps = directive
                    try:
                        meta = task_service.create_task(workspace, title, goal)
                        note = f"Task created by the orchestrator: {meta['id']}"
                        if queue_steps:
                            queue_service.add_steps(workspace, meta["id"], queue_steps, source="orchestrator")
                            note += f" — {len(queue_steps)} step(s) queued; the system will cue each agent"
                        append_message(workspace, "system", note + ". Review it on the Tasks tab.", provider=provider)
                        add_log_entry(
                            "chat", f"orchestrator created task {meta['id']}: {title}",
                            provider=provider, task_id=meta["id"],
                        )
                    except Exception as exc:  # noqa: BLE001 — never break the chat loop
                        append_message(workspace, "system", f"Could not create the task: {exc}", provider=provider)

                queue_directive = parse_queue_directive(out)
                if queue_directive is not None:
                    ref, steps = queue_directive
                    try:
                        task_id = _resolve_task_ref(workspace, ref)
                        if task_id is None:
                            append_message(
                                workspace, "system",
                                f"Could not queue steps: no task matches `{ref}`.", provider=provider,
                            )
                        else:
                            queue_service.add_steps(workspace, task_id, steps, source="orchestrator")
                            append_message(
                                workspace, "system",
                                f"Orchestrator queued {len(steps)} step(s) for {task_id}: "
                                f"{', '.join(steps)} — the system will cue each agent in order.",
                                provider=provider,
                            )
                    except Exception as exc:  # noqa: BLE001
                        append_message(workspace, "system", f"Could not queue steps: {exc}", provider=provider)
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
        "defaultProvider": routing.get("orchestrator", "antigravity"),
        "providers": provider_options(),
    }
