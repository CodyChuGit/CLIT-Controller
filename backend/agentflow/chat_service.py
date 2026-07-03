"""Persistent chat with the traffic-control model, executed via the user's own CLI agents."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Optional

from . import (
    config,
    controller_protocol,
    paths,
    policy_service,
    prompt_templates,
    state_store,
    task_service,
    usage_service,
)
from .agent_commands import build_argv, provider_busy_result
from .chat_directives import strip_action_blocks
from .controller import context as controller_context
from .controller import engine as controller_engine
from .process_runner import AGENT_RUN_TIMEOUT, RUNNER, RunRecord, add_log_entry, now_iso
from .provider_probe import AGENT_PROVIDER_IDS, resolve_executable
from .redaction import redact

MAX_STORED_MESSAGES = 200
REPLAY_MESSAGES = 12  # how many past messages are replayed to the CLI
REPLAY_CLIP_CHARS = 1500  # per-message clip when replaying

# "workspace::channel" -> run id of the in-flight chat response
_pending: dict[str, str] = {}

ORCHESTRATOR_CHANNEL = "orchestrator"


def _pkey(workspace: Path, channel: str) -> str:
    return f"{workspace}::{channel}"


def _controller_display(out: str) -> str:
    """The human-readable narrative stored for the controller's chat bubble.

    The controller's raw stdout ends with a deterministic ``CLITC_RESULT_V1`` block
    (Plane 3) that must never render as prose. Strip every action block (the v1
    result + legacy directives); when the controller emitted ONLY a result block and
    no surrounding prose, fall back to the block's own ``message`` so the turn still
    shows a clean one-line summary instead of leaking JSON (or showing nothing)."""
    prose = strip_action_blocks(out)
    if prose:
        return prose
    result, _failure, _meta = controller_protocol.parse_controller_result(out)
    if result is not None and (result.message.summary or result.message.details):
        lines = [result.message.summary] if result.message.summary else []
        lines.extend(f"- {d}" for d in result.message.details)
        return "\n".join(line for line in lines if line).strip()
    return ""


MAX_CONSULTS_PER_TASK = 6
RUN_WAIT_SECONDS = 15  # quick commands report their result; longer ones keep running


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
    """The controller runs simple operational commands directly — no task, no roles.

    ``approved=True`` is the post-approval path: it bypasses the require-approval gate
    (the user already authorized it) but hard denials still apply."""
    import asyncio

    usage = usage_service.ensure_usage(workspace)
    mode = usage.get("orchestrationMode", "balanced")
    policy = policy_service.classify_action(
        command,
        workspace,
        source="orchestrator",
        provider=provider,
        task_id=task_id,
        mode=mode,
    )

    if policy.denied:
        state_store.append_event(
            workspace,
            "policy.denied",
            f"denied `{command}` — {policy.reason}",
            task_id=task_id,
            provider=provider,
            data={"command": command, "reason": policy.reason},
        )
        append_message(workspace, "system", f"Didn't run `{command}` — {policy.reason}.", provider=provider)
        return

    # Risky-but-legitimate actions (installs, git push/pull, deploys) need an explicit,
    # durable approval rather than running automatically.
    if policy.decision == policy_service.REQUIRE_APPROVAL and not approved:
        state_store.create_approval(
            workspace,
            action=command,
            kind="command",
            source="orchestrator",
            provider=provider,
            task_id=task_id,
            reason=policy.reason,
        )
        append_message(
            workspace,
            "system",
            f"Approval needed before `{command}` — {policy.reason}. Approve it to run.",
            provider=provider,
        )
        if task_id:
            try:
                task_service._add_event(
                    workspace,
                    task_id,
                    "approval_required",
                    f"`{command}` needs approval — {policy.reason}",
                    provider=provider,
                )
            except FileNotFoundError:
                pass
        return

    if mode == "manual_approval":
        append_message(
            workspace,
            "system",
            f"Manual Approval mode — run it yourself: `{command}`",
            provider=provider,
        )
        return

    argv = shlex.split(command)
    resolved = resolve_executable(argv[0])
    if resolved is None:
        append_message(workspace, "system", f"Didn't run `{command}` — `{argv[0]}` not found.", provider=provider)
        return
    argv[0] = resolved

    record, consume = await RUNNER.start(
        argv,
        workspace,
        step="run",
        provider="shell",
        task_id=task_id,
        workspace=workspace,
        stream_kind="command",
        max_runtime=AGENT_RUN_TIMEOUT,
    )
    if record.status == "error":
        append_message(
            workspace, "system", f"`{command}` failed to start: {record.stderr.strip()[:200]}", provider=provider
        )
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
                workspace,
                task_id,
                "run",
                f"controller ran `{command}` → {record.status}"
                + (f" (exit {record.exit_code})" if record.exit_code is not None else ""),
                provider=provider,
            )
        except FileNotFoundError:
            pass
    add_log_entry(
        "run",
        f"controller ran: $ {command} → {record.status}",
        provider="shell",
        task_id=task_id,
        output=(record.stdout + "\n" + record.stderr)[-2000:],
    )


def _chat_file(workspace: Path) -> Path:
    return paths.workspace_app_dir(workspace) / "chat.json"


def load_chat(workspace: Path) -> dict:
    data = config.read_json(_chat_file(workspace), None)
    if not isinstance(data, dict) or "messages" not in data:
        data = {"messages": []}
    return data


def _channel_messages(data: dict, channel: str) -> list:
    """Controller history lives in `messages`; direct agent chats under `channels`."""
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
    return provider_busy_result(provider, record.id, record.step)


# Prompt-context builders live in the controller package (Workstream 2 extraction).
_workspace_summary = controller_context.workspace_summary
_focus_task_brief = controller_context.focus_task_brief


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


async def send(
    workspace: Path, message: str, provider: Optional[str] = None, focus_task_id: Optional[str] = None
) -> dict:
    """Append the user message and start a real CLI run for the reply.

    ``focus_task_id`` scopes the turn to a task: its brief is added to the
    controller's context so "continue this task" actually continues *that* task."""
    if pending_state(workspace) is not None:
        return {"status": "busy", "message": "A response is already in progress. Stop it or wait."}

    routing = config.get_workspace_routing(workspace)
    provider = provider or routing.get("orchestrator", "claude")
    # Validate before anything reaches a command template / subprocess launch: an
    # unknown provider would otherwise fall through to a fallback template and be
    # executed as a binary (audit P2-11). Mirrors send_direct.
    if provider not in AGENT_PROVIDER_IDS:
        return {"status": "error", "message": f"unknown provider: {provider}"}
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
    if focus_task_id:
        summary = f"{summary}\n\n{_focus_task_brief(workspace, focus_task_id)}"
    prompt = prompt_templates.orchestrator_chat_prompt(usage, summary, transcript, message)
    argv = build_argv(template, prompt, config.get_models().get(provider))

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
                # Store the display-clean narrative — the raw CLITC_RESULT_V1 / legacy
                # blocks are parsed below but must never render as prose in the bubble.
                display = _controller_display(out)
                if display:
                    append_message(workspace, "assistant", display, provider=provider, durationMs=record.duration_ms)
                # CLITC_RESULT_V1 is the primary mutation path (Workstream 2): a valid
                # block drives exactly one validated action; an invalid block is a
                # typed no-action failure; legacy directives are a warned fallback.
                try:
                    await controller_engine.apply_controller_output(
                        workspace,
                        out,
                        provider=provider,
                        source="controller_chat",
                        run_id=record.id,
                        task_id=focus_task_id,
                    )
                except Exception as exc:  # noqa: BLE001 — never break the chat loop
                    append_message(workspace, "system", f"Controller action failed: {exc}", provider=provider)
            elif record.status == "cancelled":
                append_message(workspace, "system", "Response stopped.", provider=provider)
            else:
                err_tail = (record.stderr or record.stdout or "no output").strip()[-800:]
                append_message(
                    workspace,
                    "system",
                    f"`{provider}` exited with {record.exit_code}: {err_tail}",
                    provider=provider,
                )
            add_log_entry(
                "chat",
                f"controller chat via {provider}: {record.status} in {(record.duration_ms or 0) / 1000:.1f}s",
                provider=provider,
                step="chat",
                status="info" if record.status == "succeeded" else "warn",
            )
        finally:
            if _pending.get(ws_key) == record.id:
                _pending.pop(ws_key, None)

    busy = _provider_busy(provider)
    if busy is not None:
        return busy
    record, _task = await RUNNER.start(
        argv,
        workspace,
        step="chat",
        provider=provider,
        on_complete=on_complete,
        workspace=workspace,
        stream_kind="controller",
        max_runtime=AGENT_RUN_TIMEOUT,
    )
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
    """Direct chat with one agent CLI — no traffic control, no directives, no tasks."""
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
    argv = build_argv(template, prompt, config.get_models().get(provider))
    key = _pkey(workspace, provider)

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
                append_message(
                    workspace, "assistant", out, channel=provider, provider=provider, durationMs=record.duration_ms
                )
            elif record.status == "cancelled":
                append_message(workspace, "system", "Response stopped.", channel=provider, provider=provider)
            else:
                err_tail = (record.stderr or record.stdout or "no output").strip()[-800:]
                append_message(
                    workspace,
                    "system",
                    f"`{provider}` exited with {record.exit_code}: {err_tail}",
                    channel=provider,
                    provider=provider,
                )
            add_log_entry(
                "chat",
                f"direct chat via {provider}: {record.status} in {(record.duration_ms or 0) / 1000:.1f}s",
                provider=provider,
                step="chat",
                status="info" if record.status == "succeeded" else "warn",
            )
        finally:
            if _pending.get(key) == record.id:
                _pending.pop(key, None)

    record, _task = await RUNNER.start(
        argv,
        workspace,
        step="chat",
        provider=provider,
        on_complete=on_complete,
        workspace=workspace,
        stream_kind="chat",
        max_runtime=AGENT_RUN_TIMEOUT,
    )
    if record.status == "error":
        _pending.pop(key, None)
        note = f"Could not start `{provider}`: {record.stderr.strip()[:300]}"
        append_message(workspace, "system", note, channel=provider, provider=provider)
        return {"status": "error", "message": note}

    _pending[key] = record.id
    return {"status": "started", "runId": record.id, "provider": provider}


async def orchestrator_consult(workspace: Path, task_id: str, trigger: str, output_tail: str = "") -> dict:
    """System-initiated controller turn after a step finishes: it sees the results
    and decides the next action (queue more steps, declare done, or escalate)."""
    meta = task_service._load_meta(workspace, task_id)
    consults = int(meta.get("consults", 0))
    if consults >= MAX_CONSULTS_PER_TASK:
        task_service._add_event(
            workspace,
            task_id,
            "needs_user",
            f"controller consult limit reached ({MAX_CONSULTS_PER_TASK}) — continue manually or via chat",
        )
        return {"status": "consult_limit"}

    routing = config.get_workspace_routing(workspace)
    provider = routing.get("orchestrator", "claude")
    usage = usage_service.ensure_usage(workspace)
    template = config.get_command_templates().get(provider, f"{provider} {{prompt}}")
    busy = _provider_busy(provider)
    if busy is not None:
        return busy
    if resolve_executable(shlex.split(template)[0]) is None:
        task_service._add_event(
            workspace,
            task_id,
            "needs_user",
            f"controller consult skipped — `{provider}` is not installed",
        )
        return {"status": "provider_missing"}

    state = task_service.task_state_summary(workspace, task_id)
    prompt = prompt_templates.orchestrator_consult_prompt(usage, state, trigger, redact(output_tail[-1500:]))
    argv = build_argv(template, prompt, config.get_models().get(provider))

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
        workspace,
        task_id,
        "consult",
        f"system consulted the controller ({provider}): {trigger[:120]}",
        provider=provider,
    )

    async def on_complete(record) -> None:
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
            if record.status != "succeeded" or not out:
                task_service._add_event(
                    workspace,
                    task_id,
                    "needs_user",
                    f"controller consult failed ({record.status}, exit {record.exit_code}) — decide the next step manually",
                    provider=provider,
                )
                return

            # Same engine as controller chat: CLITC_RESULT_V1 first, typed failure
            # on an invalid block (no mutation), warned legacy fallback otherwise.
            turn = await controller_engine.apply_controller_output(
                workspace,
                out,
                provider=provider,
                source="consult",
                run_id=record.id,
                task_id=task_id,
            )
            if turn["status"] == "no_action":
                reasoning = strip_action_blocks(out)[:240]
                task_service._add_event(
                    workspace,
                    task_id,
                    "needs_user",
                    "controller replied without an actionable block — decide the next step manually"
                    + (f" (it said: {reasoning})" if reasoning else ""),
                    provider=provider,
                )
            if record.status == "succeeded":
                state_store.append_event(
                    workspace,
                    "controller.decision_received",
                    "controller decided the next step",
                    task_id=task_id,
                    provider=provider,
                    step="orchestrate",
                    data={"runId": record.id, **turn},
                )
            add_log_entry(
                "orchestrate",
                f"consult for {task_id} via {provider}: {record.status} in {(record.duration_ms or 0) / 1000:.1f}s",
                provider=provider,
                task_id=task_id,
                step="orchestrate",
            )
        except Exception as exc:  # noqa: BLE001 — the loop must never die here
            add_log_entry("orchestrate", f"consult post-processing failed: {exc}", status="error", task_id=task_id)

    record, _task = await RUNNER.start(
        argv,
        workspace,
        task_id=task_id,
        step="orchestrate",
        provider=provider,
        log_file=str(log_file),
        on_complete=on_complete,
        workspace=workspace,
        stream_kind="controller",
        max_runtime=AGENT_RUN_TIMEOUT,
    )
    if record.status == "error":
        task_service._add_event(
            workspace,
            task_id,
            "needs_user",
            f"controller consult could not start: {record.stderr.strip()[:200]}",
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
        "defaultProvider": routing.get("orchestrator", "claude"),
        "providers": provider_options(),
    }
