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
_DONE_DIRECTIVE_RE = re.compile(r"```agentflow-done\s*\n(.*?)```", re.DOTALL)
_NEEDS_USER_DIRECTIVE_RE = re.compile(r"```agentflow-needs-user\s*\n(.*?)```", re.DOTALL)
_RUN_DIRECTIVE_RE = re.compile(r"```agentflow-run\s*\n(.*?)```", re.DOTALL)

MAX_CONSULTS_PER_TASK = 6
MAX_RUN_DIRECTIVES = 3
RUN_WAIT_SECONDS = 15  # quick commands report their result; longer ones keep running


def parse_run_directives(text: str) -> list[str]:
    """All `command:` lines from ```agentflow-run``` blocks (capped)."""
    commands: list[str] = []
    for m in _RUN_DIRECTIVE_RE.finditer(text or ""):
        for line in m.group(1).splitlines():
            if line.lower().startswith("command:"):
                cmd = line[8:].strip()
                if cmd:
                    commands.append(cmd)
    return commands[:MAX_RUN_DIRECTIVES]


def command_denied(command: str, workspace: Optional[Path] = None) -> Optional[str]:
    """Direct execution is exec-only, workspace-confined, and refuses the dangerous."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return "unparseable quoting"
    if not tokens:
        return "empty command"
    if tokens[0] in ("sudo", "su", "sh", "bash", "zsh", "shutdown", "reboot", "halt", "mkfs", "dd"):
        return f"`{tokens[0]}` is not allowed for direct execution"
    if tokens[0] == "rm" and any(t.startswith("-") and "r" in t and "f" in t for t in tokens) and any(
        t == "/" or t.startswith("/ ") for t in tokens
    ):
        return "refusing recursive force-delete on /"
    if any(ch in command for ch in ("|", ">", "<", ";", "&&", "`", "$(")):
        return "shell operators are not supported — one plain command only"
    # Agents stay inside the workspace: no traversal, no absolute paths outside it.
    if workspace is not None:
        ws = str(workspace.resolve())
        for t in tokens[1:]:
            arg = t.split("=", 1)[1] if t.startswith("-") and "=" in t else t
            if ".." in arg.split("/"):
                return "path traversal (`..`) is not allowed"
            if arg.startswith(("/", "~")) and not str(Path(arg).expanduser().resolve()).startswith(ws):
                return f"`{arg}` is outside the workspace"
    return None


async def execute_run_directive(
    workspace: Path, command: str, provider: str, task_id: Optional[str] = None
) -> None:
    """The orchestrator runs simple operational commands directly — no task, no roles."""
    import asyncio

    denied = command_denied(command, workspace)
    if denied:
        append_message(workspace, "system", f"Didn't run `{command}` — {denied}.", provider=provider)
        return

    usage = usage_service.ensure_usage(workspace)
    if usage.get("orchestrationMode") == "manual_approval":
        append_message(
            workspace, "system",
            f"Manual Approval mode — run it yourself: `{command}`", provider=provider,
        )
        return

    argv = shlex.split(command)
    resolved = resolve_executable(argv[0])
    if resolved is None:
        append_message(workspace, "system", f"Didn't run `{command}` — `{argv[0]}` not found.", provider=provider)
        return
    argv[0] = resolved

    record, consume = await RUNNER.start(argv, workspace, step="run", provider="shell", task_id=task_id)
    if record.status == "error":
        append_message(workspace, "system", f"`{command}` failed to start: {record.stderr.strip()[:200]}", provider=provider)
        return
    try:
        await asyncio.wait_for(asyncio.shield(consume), timeout=RUN_WAIT_SECONDS)
    except asyncio.TimeoutError:
        pass

    usage_service.increment_local_steps(workspace)
    if record.status == "running":
        note = f"$ {command} — running in the background (Logs · Stop via Tasks)"
    else:
        tail = redact((record.stdout + "\n" + record.stderr).strip()[-300:])
        note = f"$ {command} → exit {record.exit_code}" + (f"\n{tail}" if tail else "")
    append_message(workspace, "system", note, provider=provider)
    if task_id:
        try:
            task_service._add_event(
                workspace, task_id, "run",
                f"orchestrator ran `{command}` → {record.status}"
                + (f" (exit {record.exit_code})" if record.exit_code is not None else ""),
                provider=provider,
            )
        except FileNotFoundError:
            pass
    add_log_entry(
        "run", f"orchestrator ran: $ {command} → {record.status}",
        provider="shell", task_id=task_id,
        output=(record.stdout + "\n" + record.stderr)[-2000:],
    )


def _parse_reason_block(regex: re.Pattern[str], text: str) -> Optional[str]:
    m = regex.search(text or "")
    if not m:
        return None
    for line in m.group(1).splitlines():
        if line.lower().startswith("reason:"):
            return line[7:].strip() or "no reason given"
    return "no reason given"


def parse_done_directive(text: str) -> Optional[str]:
    return _parse_reason_block(_DONE_DIRECTIVE_RE, text)


def parse_needs_user_directive(text: str) -> Optional[str]:
    return _parse_reason_block(_NEEDS_USER_DIRECTIVE_RE, text)


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


def _slug(task_id: str) -> str:
    """Human part of a task id: 20260612-201312-create-simple-calendar-app → create-simple-calendar-app."""
    parts = task_id.split("-", 2)
    return parts[2] if len(parts) == 3 else task_id


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
    # The orchestrator must see what each agent actually did, not just task names.
    detail = "\n\n".join(
        task_service.task_state_summary(workspace, t["id"]) for t in tasks[:2]
    )
    live_line = usage_service.live_summary_line()
    return (
        f"Workspace: {workspace} ({git_line})\n"
        f"{queue_service.summary_line(workspace)}\n"
        + (f"{live_line}\n" if live_line else "")
        + f"Recent AgentFlow tasks:{task_lines}"
        + (f"\n\nCurrent task state (per agent):\n{detail}" if detail else "")
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
                        meta = task_service.create_task(workspace, title, goal, orchestrated=True)
                        note = f"Created \u201c{title}\u201d"
                        if queue_steps:
                            queue_service.add_steps(workspace, meta["id"], queue_steps, source="orchestrator")
                            note += f" · queued {', '.join(queue_steps)}"
                        append_message(workspace, "system", note, provider=provider)
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
                                f"Couldn\u2019t queue steps — no task matches `{ref}`.", provider=provider,
                            )
                        else:
                            task_service.set_orchestrated(workspace, task_id)
                            queue_service.add_steps(workspace, task_id, steps, source="orchestrator")
                            append_message(
                                workspace, "system",
                                f"Queued {', '.join(steps)} · {_slug(task_id)}",
                                provider=provider,
                            )
                    except Exception as exc:  # noqa: BLE001
                        append_message(workspace, "system", f"Could not queue steps: {exc}", provider=provider)

                for cmd in parse_run_directives(out):
                    try:
                        await execute_run_directive(workspace, cmd, provider)
                    except Exception as exc:  # noqa: BLE001
                        append_message(workspace, "system", f"`{cmd}` failed: {exc}", provider=provider)
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


async def orchestrator_consult(workspace: Path, task_id: str, trigger: str, output_tail: str = "") -> dict:
    """System-initiated orchestrator turn after a step finishes: it sees the results
    and decides the next action (queue more steps, declare done, or escalate)."""
    meta = task_service._load_meta(workspace, task_id)
    consults = int(meta.get("consults", 0))
    if consults >= MAX_CONSULTS_PER_TASK:
        task_service._add_event(
            workspace, task_id, "needs_user",
            f"orchestrator consult limit reached ({MAX_CONSULTS_PER_TASK}) — continue manually or via chat",
        )
        return {"status": "consult_limit"}

    routing = config.get_workspace_routing(workspace)
    provider = routing.get("orchestrator", "antigravity")
    usage = usage_service.ensure_usage(workspace)
    template = config.get_command_templates().get(provider, f"{provider} {{prompt}}")
    if resolve_executable(shlex.split(template)[0]) is None:
        task_service._add_event(
            workspace, task_id, "needs_user",
            f"orchestrator consult skipped — `{provider}` is not installed",
        )
        return {"status": "provider_missing"}

    state = task_service.task_state_summary(workspace, task_id)
    prompt = prompt_templates.orchestrator_consult_prompt(usage, state, trigger, redact(output_tail[-1500:]))
    argv = task_service._build_argv(template, prompt, config.get_models().get(provider))

    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = paths.task_logs_dir(workspace, task_id) / f"{stamp}-orchestrate.log"
    prompt_file = paths.task_logs_dir(workspace, task_id) / f"{stamp}-orchestrate.prompt.txt"
    prompt_file.parent.mkdir(exist_ok=True)
    prompt_file.write_text(redact(prompt), encoding="utf-8")

    meta = task_service._load_meta(workspace, task_id)
    meta["consults"] = consults + 1
    task_service._save_meta(workspace, meta)
    task_service._add_event(
        workspace, task_id, "consult",
        f"system consulted the orchestrator ({provider}): {trigger[:120]}",
        provider=provider,
    )

    async def on_complete(record) -> None:
        try:
            usage_service.record_call(
                workspace, provider,
                prompt_chars=len(prompt),
                output_chars=len(record.stdout) + len(record.stderr),
                duration_ms=record.duration_ms or 0,
                status=record.status,
            )
            out = record.stdout.strip()
            if record.status != "succeeded" or not out:
                task_service._add_event(
                    workspace, task_id, "needs_user",
                    f"orchestrator consult failed ({record.status}, exit {record.exit_code}) — decide the next step manually",
                    provider=provider,
                )
                return

            from . import queue_service  # local import: queue_service ↔ chat_service

            queued = parse_queue_directive(out)
            done_reason = parse_done_directive(out)
            user_reason = parse_needs_user_directive(out)
            commands = parse_run_directives(out)
            reasoning = _TASK_DIRECTIVE_RE.sub("", _QUEUE_DIRECTIVE_RE.sub("", out))
            reasoning = _RUN_DIRECTIVE_RE.sub("", reasoning)
            reasoning = _DONE_DIRECTIVE_RE.sub("", _NEEDS_USER_DIRECTIVE_RE.sub("", reasoning)).strip()[:240]

            for cmd in commands:
                try:
                    await execute_run_directive(workspace, cmd, provider, task_id=task_id)
                except Exception as exc:  # noqa: BLE001
                    append_message(workspace, "system", f"`{cmd}` failed: {exc}", provider=provider)

            if queued is not None:
                _ref, steps = queued
                queue_service.add_steps(workspace, task_id, steps, source="orchestrator")
                task_service._add_event(
                    workspace, task_id, "consult",
                    f"orchestrator decision: queue {', '.join(steps)}" + (f" — {reasoning}" if reasoning else ""),
                    provider=provider,
                )
                append_message(
                    workspace, "system",
                    f"Reviewed {trigger.split(' via ')[0]} → queued {', '.join(steps)}",
                    provider=provider,
                )
            elif done_reason is not None:
                meta2 = task_service._load_meta(workspace, task_id)
                meta2["status"] = "done"
                meta2["orchestratorVerdict"] = {"verdict": "done", "reason": done_reason, "at": now_iso()}
                task_service._save_meta(workspace, meta2)
                task_service._add_event(
                    workspace, task_id, "done",
                    f"orchestrator declared the task complete: {done_reason}",
                    provider=provider,
                )
                append_message(
                    workspace, "system",
                    f"\u201c{_slug(task_id)}\u201d complete — {done_reason}",
                    provider=provider,
                )
            elif user_reason is not None:
                task_service._add_event(
                    workspace, task_id, "needs_user",
                    f"orchestrator needs your decision: {user_reason}",
                    provider=provider,
                )
                append_message(
                    workspace, "system",
                    f"Needs your input — {user_reason}",
                    provider=provider,
                )
            elif not commands:
                task_service._add_event(
                    workspace, task_id, "needs_user",
                    "orchestrator replied without an actionable block — decide the next step manually"
                    + (f" (it said: {reasoning})" if reasoning else ""),
                    provider=provider,
                )
            add_log_entry(
                "orchestrate",
                f"consult for {task_id} via {provider}: {record.status} in {(record.duration_ms or 0) / 1000:.1f}s",
                provider=provider, task_id=task_id, step="orchestrate",
            )
        except Exception as exc:  # noqa: BLE001 — the loop must never die here
            add_log_entry("orchestrate", f"consult post-processing failed: {exc}", status="error", task_id=task_id)

    record, _task = await RUNNER.start(
        argv, workspace,
        task_id=task_id, step="orchestrate", provider=provider,
        log_file=str(log_file), on_complete=on_complete,
    )
    if record.status == "error":
        task_service._add_event(
            workspace, task_id, "needs_user",
            f"orchestrator consult could not start: {record.stderr.strip()[:200]}",
            provider=provider,
        )
        return {"status": "error"}
    return {"status": "started", "runId": record.id}


def chat_state(workspace: Path) -> dict:
    routing = config.get_workspace_routing(workspace)
    return {
        "messages": load_chat(workspace)["messages"],
        "pending": pending_state(workspace),
        "defaultProvider": routing.get("orchestrator", "antigravity"),
        "providers": provider_options(),
    }
