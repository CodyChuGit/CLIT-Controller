"""Persistent chat with the orchestration model, executed via the user's own CLI agents."""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Optional

from . import config, git_service, paths, policy_service, prompt_templates, queue_service, state_store, task_service, usage_service
from .process_runner import RUNNER, RunRecord, add_log_entry, now_iso
from .provider_probe import AGENT_PROVIDER_IDS, resolve_executable
from .redaction import redact

MAX_STORED_MESSAGES = 200
REPLAY_MESSAGES = 12      # how many past messages are replayed to the CLI
REPLAY_CLIP_CHARS = 1500  # per-message clip when replaying

# "workspace::channel" -> run id of the in-flight chat response
_pending: dict[str, str] = {}

ORCHESTRATOR_CHANNEL = "orchestrator"


def _pkey(workspace: Path, channel: str) -> str:
    return f"{workspace}::{channel}"

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
    """Direct execution is exec-only, workspace-confined, and refuses the dangerous.

    Thin wrapper over the policy service: returns a reason only for hard denials.
    Commands that merely ``require_approval`` (git push, npm install, …) return None —
    they are gated by the approval flow in ``execute_run_directive``, not denied here.
    """
    return policy_service.deny_reason(command, workspace)


async def execute_run_directive(
    workspace: Path, command: str, provider: str, task_id: Optional[str] = None, approved: bool = False
) -> None:
    """The orchestrator runs simple operational commands directly — no task, no roles.

    ``approved=True`` is the post-approval path: it bypasses the require-approval gate
    (the user already authorized it) but hard denials still apply."""
    import asyncio

    usage = usage_service.ensure_usage(workspace)
    mode = usage.get("orchestrationMode", "balanced")
    policy = policy_service.classify_action(
        command, workspace, source="orchestrator", provider=provider, task_id=task_id, mode=mode,
    )

    if policy.denied:
        state_store.append_event(
            workspace, "policy.denied", f"denied `{command}` — {policy.reason}",
            task_id=task_id, provider=provider, data={"command": command, "reason": policy.reason},
        )
        append_message(workspace, "system", f"Didn't run `{command}` — {policy.reason}.", provider=provider)
        return

    # Risky-but-legitimate actions (installs, git push/pull, deploys) need an explicit,
    # durable approval rather than running automatically.
    if policy.decision == policy_service.REQUIRE_APPROVAL and not approved:
        state_store.create_approval(
            workspace, action=command, kind="command", source="orchestrator",
            provider=provider, task_id=task_id, reason=policy.reason,
        )
        append_message(
            workspace, "system",
            f"Approval needed before `{command}` — {policy.reason}. Approve it to run.",
            provider=provider,
        )
        if task_id:
            try:
                task_service._add_event(
                    workspace, task_id, "approval_required",
                    f"`{command}` needs approval — {policy.reason}", provider=provider,
                )
            except FileNotFoundError:
                pass
        return

    if mode == "manual_approval":
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


def _channel_messages(data: dict, channel: str) -> list:
    """Orchestrator history lives in `messages`; direct agent chats under `channels`."""
    if channel == ORCHESTRATOR_CHANNEL:
        return data["messages"]
    channels = data.setdefault("channels", {})
    return channels.setdefault(channel, [])


def _save_chat(workspace: Path, data: dict) -> None:
    data["updatedAt"] = now_iso()
    if len(data["messages"]) > MAX_STORED_MESSAGES:
        data["messages"] = data["messages"][-MAX_STORED_MESSAGES:]
    for channel, msgs in data.get("channels", {}).items():
        if len(msgs) > MAX_STORED_MESSAGES:
            data["channels"][channel] = msgs[-MAX_STORED_MESSAGES:]
    config.write_json(_chat_file(workspace), data)


def append_message(workspace: Path, role: str, content: str, channel: str = ORCHESTRATOR_CHANNEL, **extra) -> dict:
    data = load_chat(workspace)
    msg = {"role": role, "content": redact(content), "time": now_iso(), **extra}
    _channel_messages(data, channel).append(msg)
    _save_chat(workspace, data)
    return msg


def clear_chat(workspace: Path, channel: str = ORCHESTRATOR_CHANNEL) -> None:
    data = load_chat(workspace)
    _channel_messages(data, channel).clear()
    _save_chat(workspace, data)


def provider_options() -> list[dict]:
    """Agent CLIs selectable in the chat header, with installed flags."""
    templates = config.get_command_templates()
    out = []
    for pid in AGENT_PROVIDER_IDS:
        template = templates.get(pid, f"{pid} {{prompt}}")
        argv0 = shlex.split(template)[0]
        out.append({"id": pid, "installed": resolve_executable(argv0) is not None})
    return out


def pending_state(workspace: Path, channel: str = ORCHESTRATOR_CHANNEL) -> Optional[dict]:
    key = _pkey(workspace, channel)
    run_id = _pending.get(key)
    if not run_id:
        return None
    record = RUNNER.runs.get(run_id)
    if record is None or record.status != "running":
        # finished (on_complete clears) or evicted — either way nothing is in flight
        if record is None:
            _pending.pop(key, None)
        return None
    tail = (record.stdout + ("\n" + record.stderr if record.stderr else ""))[-1200:]
    return {"runId": run_id, "status": record.status, "outputTail": redact(tail)}


def _provider_busy(provider: str) -> Optional[dict]:
    record = RUNNER.running_for_provider(provider)
    if record is None:
        return None
    step = record.step or "request"
    return {
        "status": "provider_busy",
        "provider": provider,
        "runId": record.id,
        "message": f"`{provider}` is already running `{step}`. Wait for it to finish or stop it before starting another `{provider}` request.",
    }


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


def _transcript(workspace: Path, channel: str = ORCHESTRATOR_CHANNEL) -> str:
    data = load_chat(workspace)
    msgs = [m for m in _channel_messages(data, channel) if m["role"] in ("user", "assistant")]
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

    busy = _provider_busy(provider)
    if busy is not None:
        return busy

    if provider == "claude" and usage_service.provider_health(usage, "claude") == "red":
        return {
            "status": "claude_red",
            "message": "Claude usage health is RED — pick a cheaper provider for chat (codex/antigravity) or update its health on the Usage page.",
        }

    # History snapshot first — the new message goes into the prompt separately.
    transcript = _transcript(workspace)
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
    summary = await _workspace_summary(workspace)
    prompt = prompt_templates.orchestrator_chat_prompt(usage, summary, transcript, message)
    argv = task_service._build_argv(template, prompt, config.get_models().get(provider))

    ws_key = _pkey(workspace, ORCHESTRATOR_CHANNEL)

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

    busy = _provider_busy(provider)
    if busy is not None:
        return busy
    record, _task = await RUNNER.start(argv, workspace, step="chat", provider=provider, on_complete=on_complete)
    if record.status == "error":
        _pending.pop(ws_key, None)
        note = f"Could not start `{provider}`: {record.stderr.strip()[:300]}"
        append_message(workspace, "system", note, provider=provider)
        return {"status": "error", "message": note}

    _pending[ws_key] = record.id
    return {"status": "started", "runId": record.id, "provider": provider}


async def stop(workspace: Path, channel: str = ORCHESTRATOR_CHANNEL) -> dict:
    run_id = _pending.get(_pkey(workspace, channel))
    if not run_id:
        return {"stopped": False}
    ok = await RUNNER.cancel(run_id)
    return {"stopped": ok}


async def send_direct(workspace: Path, provider: str, message: str) -> dict:
    """Direct chat with one agent CLI — no orchestration, no directives, no tasks."""
    if provider not in AGENT_PROVIDER_IDS:
        return {"status": "error", "message": f"`{provider}` is not a chat agent."}
    if pending_state(workspace, provider) is not None:
        return {"status": "busy", "message": f"`{provider}` is still replying. Stop it or wait."}
    busy = _provider_busy(provider)
    if busy is not None:
        return busy

    # History snapshot first — the new message goes into the prompt separately.
    transcript = _transcript(workspace, channel=provider)
    append_message(workspace, "user", message, channel=provider)

    template = config.get_command_templates().get(provider, f"{provider} {{prompt}}")
    argv0 = shlex.split(template)[0]
    if resolve_executable(argv0) is None:
        note = f"`{provider}` is not installed (`{argv0}` not on PATH) — install it on the Agents page."
        append_message(workspace, "system", note, channel=provider, provider=provider)
        return {"status": "provider_missing", "message": note}

    prompt = prompt_templates.direct_chat_prompt(provider, transcript, message)
    argv = task_service._build_argv(template, prompt, config.get_models().get(provider))
    key = _pkey(workspace, provider)

    async def on_complete(record: RunRecord) -> None:
        try:
            usage_service.record_call(
                workspace, provider,
                prompt_chars=len(prompt),
                output_chars=len(record.stdout) + len(record.stderr),
                duration_ms=record.duration_ms or 0,
                status=record.status,
            )
            out = record.stdout.strip()
            if record.status == "succeeded" and out:
                append_message(workspace, "assistant", out, channel=provider,
                               provider=provider, durationMs=record.duration_ms)
            elif record.status == "cancelled":
                append_message(workspace, "system", "Response stopped.", channel=provider, provider=provider)
            else:
                err_tail = (record.stderr or record.stdout or "no output").strip()[-800:]
                append_message(
                    workspace, "system",
                    f"`{provider}` exited with {record.exit_code}: {err_tail}",
                    channel=provider, provider=provider,
                )
            add_log_entry(
                "chat",
                f"direct chat via {provider}: {record.status} in {(record.duration_ms or 0) / 1000:.1f}s",
                provider=provider, step="chat",
                status="info" if record.status == "succeeded" else "warn",
            )
        finally:
            if _pending.get(key) == record.id:
                _pending.pop(key, None)

    record, _task = await RUNNER.start(argv, workspace, step="chat", provider=provider, on_complete=on_complete)
    if record.status == "error":
        _pending.pop(key, None)
        note = f"Could not start `{provider}`: {record.stderr.strip()[:300]}"
        append_message(workspace, "system", note, channel=provider, provider=provider)
        return {"status": "error", "message": note}

    _pending[key] = record.id
    return {"status": "started", "runId": record.id, "provider": provider}


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
    busy = _provider_busy(provider)
    if busy is not None:
        return busy
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
    data = load_chat(workspace)
    return {
        "messages": data["messages"],
        "pending": pending_state(workspace),
        "channels": {pid: data.get("channels", {}).get(pid, []) for pid in AGENT_PROVIDER_IDS},
        "channelPending": {pid: pending_state(workspace, pid) for pid in AGENT_PROVIDER_IDS},
        "defaultProvider": routing.get("orchestrator", "antigravity"),
        "providers": provider_options(),
    }
