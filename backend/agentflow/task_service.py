"""Tasks: folders, markdown handoff files, and real step execution."""

from __future__ import annotations

import asyncio
import re
import shlex
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import (
    config,
    git_service,
    paths,
    prompt_templates,
    routing_service,
    state_store,
    transitions,
    usage_service,
)
from .agent_commands import build_argv as _build_argv
from .agent_commands import provider_busy_result
from .process_runner import RUNNER, RunRecord, add_log_entry, now_iso
from .redaction import redact
from .workflow import FULL_SEQUENCE, STEP_DEFS, STEP_IO

MAX_EVENTS = 300

_full_sequences_running: set[str] = set()


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:40] or "task"


def _task_meta_file(workspace: Path, task_id: str) -> Path:
    return paths.task_dir(workspace, task_id) / "task.json"


def _load_meta(workspace: Path, task_id: str) -> dict:
    meta = config.read_json(_task_meta_file(workspace, task_id), None)
    if meta is None:
        raise FileNotFoundError(f"task not found: {task_id}")
    return meta


def _save_meta(workspace: Path, meta: dict) -> None:
    config.write_json(_task_meta_file(workspace, meta["id"]), meta)


def _task_rel_dir(task_id: str) -> str:
    return f".agentflow/tasks/{task_id}"


def step_provider(workspace: Path, step: str) -> str:
    routing = config.get_workspace_routing(workspace)
    return routing.get(STEP_DEFS[step]["role"], "claude")


def set_orchestrated(workspace: Path, task_id: str) -> None:
    meta = _load_meta(workspace, task_id)
    if not meta.get("orchestrated"):
        meta["orchestrated"] = True
        meta.setdefault("consults", 0)
        _save_meta(workspace, meta)


def task_state_summary(workspace: Path, task_id: str) -> str:
    """Compact, truthful state for the controller: what each agent actually did."""
    meta = _load_meta(workspace, task_id)
    lines = [f"Task {task_id}: {meta['title']} — goal: {meta.get('goal', '')[:200]}"]
    for step, s in meta.get("steps", {}).items():
        bits = [s.get("status", "idle")]
        if s.get("artifactsWritten"):
            bits.append("wrote " + ", ".join(s["artifactsWritten"]))
        if s.get("codeChanged"):
            bits.append(f"changed {len(s['codeChanged'])} code file(s)")
        lines.append(f"- {step} ({s.get('provider', '?')}): {'; '.join(bits)}")
    events = meta.get("events", [])[-4:]
    if events:
        lines.append("Recent events:")
        lines += [f"  • {e['detail'][:140]}" for e in events]
    return "\n".join(lines)


def _add_event(workspace: Path, task_id: str, type_: str, detail: str, *, step=None, provider=None, extra=None) -> None:
    """Append to the task's structured handoff log (shown as the traffic-control timeline)."""
    meta = _load_meta(workspace, task_id)
    events = meta.setdefault("events", [])
    event = {"time": now_iso(), "type": type_, "step": step, "provider": provider, "detail": detail}
    if extra:
        event.update(extra)
    events.append(event)
    if len(events) > MAX_EVENTS:
        del events[: len(events) - MAX_EVENTS]
    _save_meta(workspace, meta)


def _snapshot_task_files(workspace: Path, task_id: str) -> dict[str, tuple[int, int]]:
    folder = paths.task_dir(workspace, task_id)
    snap = {}
    for name in prompt_templates.TASK_FILES:
        p = folder / name
        if p.exists():
            st = p.stat()
            snap[name] = (st.st_mtime_ns, st.st_size)
    return snap


async def _changed_code_paths(workspace: Path) -> set[str]:
    """Working-tree paths with changes (tracked + untracked), excluding .agentflow."""
    status = await git_service.status_files(workspace)
    if not status.get("isRepo"):
        return set()
    paths_ = {f["path"] for f in status.get("staged", [])} | {f["path"] for f in status.get("changes", [])}
    return {p for p in paths_ if not p.startswith(".agentflow/")}


# ----------------------------------------------------------------- create/list


def create_task(workspace: Path, title: str, goal: str, orchestrated: bool = False) -> dict:
    usage = usage_service.ensure_usage(workspace)
    routing = config.get_workspace_routing(workspace)

    task_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{_slugify(title)}"
    folder = paths.task_dir(workspace, task_id)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "logs").mkdir()

    claude_prompt = prompt_templates.claude_implement_prompt(usage, _task_rel_dir(task_id))
    for name, content in prompt_templates.initial_task_files(title, goal, claude_prompt).items():
        (folder / name).write_text(content, encoding="utf-8")
    routing_service.write_initial_decisions(workspace, task_id, title, usage, routing)

    meta = {
        "id": task_id,
        "title": title,
        "goal": goal,
        "createdAt": now_iso(),
        "status": "new",
        "steps": {step: {"status": "idle", "provider": step_provider(workspace, step)} for step in STEP_DEFS},
        "fullSequence": {"status": "idle", "currentStep": None},
        "events": [],
        "orchestrated": orchestrated,
        "consults": 0,
    }
    _save_meta(workspace, meta)
    _add_event(
        workspace, task_id, "task_created",
        f"task created — handoff files written to {_task_rel_dir(task_id)}/ ({len(prompt_templates.TASK_FILES)} files)",
    )
    state_store.append_event(
        workspace, "task.created", f"task created: {title}",
        task_id=task_id, data={"title": title, "orchestrated": orchestrated},
    )
    add_log_entry("task", f"created task {task_id}: {title}", task_id=task_id)
    return _load_meta(workspace, task_id)


def list_tasks(workspace: Path) -> list[dict]:
    root = paths.tasks_dir(workspace)
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir(), reverse=True):
        if d.is_dir() and (d / "task.json").exists():
            try:
                out.append(_load_meta(workspace, d.name))
            except (FileNotFoundError, ValueError):
                continue
    return out


def task_runs(workspace: Path, task_id: str) -> list[dict]:
    """Runs for a task, RunInfo-shaped. In-memory (live) records win; the durable run
    ledger fills in anything lost to a restart so completed runs stay visible."""
    by_id: dict[str, dict] = {}
    for rec in state_store.runs_for_task(workspace, task_id):
        by_id[rec["id"]] = {
            "id": rec["id"],
            "taskId": rec.get("taskId"),
            "step": rec.get("step"),
            "provider": rec.get("provider"),
            "status": rec.get("status"),
            "exitCode": rec.get("exitCode"),
            "startedAt": rec.get("startedAt"),
            "endedAt": rec.get("endedAt"),
            "durationMs": rec.get("durationMs"),
            "commandPreview": rec.get("commandPreview", ""),
            "cwd": rec.get("cwd", str(workspace)),
            "stdout": rec.get("stdoutTail", ""),
            "stderr": rec.get("stderrTail", ""),
            "logFile": rec.get("logFile"),
            "failureKind": rec.get("failureKind"),
        }
    for r in RUNNER.runs_for_task(task_id):  # live records override the ledger snapshot
        d = r.to_dict()
        d["failureKind"] = r.failure_kind
        by_id[r.id] = d
    return sorted(by_id.values(), key=lambda d: d.get("startedAt") or "")


def get_task_detail(workspace: Path, task_id: str) -> dict:
    meta = _load_meta(workspace, task_id)
    folder = paths.task_dir(workspace, task_id)
    files = []
    for name in prompt_templates.TASK_FILES:
        p = folder / name
        if p.exists():
            st = p.stat()
            files.append(
                {
                    "name": name,
                    "size": st.st_size,
                    "modifiedAt": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(
                        timespec="seconds"
                    ),
                }
            )
    usage = usage_service.ensure_usage(workspace)
    previews = {step: build_step_preview(workspace, task_id, step, usage) for step in STEP_DEFS}
    return {
        "task": meta,
        "taskDir": str(folder),
        "files": files,
        "runs": task_runs(workspace, task_id),
        "stepPreviews": previews,
        "recommendation": routing_service.recommend(usage),
    }


def read_task_file(workspace: Path, task_id: str, name: str) -> dict:
    folder = paths.task_dir(workspace, task_id).resolve()
    target = (folder / name).resolve()
    # is_relative_to confines correctly (a bare startswith would also accept a
    # sibling dir whose name shares the prefix, e.g. `<task>-evil`).
    if not target.is_relative_to(folder) or not target.is_file():
        raise FileNotFoundError(name)
    content = target.read_text(encoding="utf-8", errors="replace")
    return {"name": name, "content": redact(content)}


def step_exchanges(workspace: Path, task_id: str) -> dict[str, list[dict]]:
    """Archived prompt → output pairs per step, rebuilt from the task's logs dir
    (survives backend restarts; in-memory run records do not)."""
    logs_dir = paths.task_logs_dir(workspace, task_id)
    out: dict[str, list[dict]] = {}
    if not logs_dir.is_dir():
        return out
    for pf in sorted(logs_dir.glob("*.prompt.txt")):
        stem = pf.name[: -len(".prompt.txt")]
        parts = stem.split("-")
        if len(parts) < 3:  # <date>-<time>-<step>
            continue
        step = parts[-1]
        stamp = "-".join(parts[:-1])
        try:
            prompt = pf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        output = ""
        log_file = logs_dir / f"{stem}.log"
        if log_file.is_file():
            try:
                output = log_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                output = ""
        out.setdefault(step, []).append(
            {"stamp": stamp, "prompt": redact(prompt[-20_000:]), "output": redact(output[-20_000:])}
        )
    return out


def list_task_logs(workspace: Path, task_id: str) -> list[dict]:
    logs_dir = paths.task_logs_dir(workspace, task_id)
    out = []
    if logs_dir.is_dir():
        for p in sorted(logs_dir.iterdir()):
            if p.is_file():
                text = p.read_text(encoding="utf-8", errors="replace")
                lines = text.splitlines()
                if len(lines) > 400:
                    text = "…[showing last 400 lines]…\n" + "\n".join(lines[-400:])
                out.append({"name": p.name, "size": p.stat().st_size, "content": redact(text)})
    return out


# ------------------------------------------------------------------ run a step


def build_step_preview(
    workspace: Path, task_id: str, step: str, usage: Optional[dict] = None, provider_override: Optional[str] = None
) -> dict:
    usage = usage or usage_service.ensure_usage(workspace)
    provider = provider_override or step_provider(workspace, step)
    prompt = prompt_templates.STEP_PROMPTS[step](usage, _task_rel_dir(task_id))
    template = config.get_command_templates().get(provider, f"{provider} {{prompt}}")
    argv = _build_argv(template, prompt, config.get_models().get(provider))
    installed = shutil.which(argv[0]) is not None
    return {
        "step": step,
        "label": STEP_DEFS[step]["label"],
        "provider": provider,
        "providerInstalled": installed,
        "commandPreview": redact(shlex.join(argv)),
        "promptChars": len(prompt),
        "reads": STEP_IO[step]["reads"],
        "writes": STEP_IO[step]["writes"],
    }


def _set_step_state(workspace: Path, task_id: str, step: str, **fields) -> None:
    """Single chokepoint for step status. Validates the transition (logs, never crashes)
    and writes a durable event whenever a step or the task's rolled-up status changes."""
    meta = _load_meta(workspace, task_id)
    prev_step = meta["steps"].get(step, {}).get("status", "idle")
    prev_task = meta.get("status")
    meta["steps"].setdefault(step, {})

    new_step = fields.get("status", prev_step)
    if new_step != prev_step and not transitions.is_valid("step", prev_step, new_step):
        add_log_entry(
            "system", f"invalid step transition {prev_step}→{new_step} for {task_id}/{step}",
            task_id=task_id, step=step, status="error",
        )

    meta["steps"][step].update(fields, updatedAt=now_iso())
    statuses = [s.get("status") for s in meta["steps"].values()]
    meta["status"] = "running" if "running" in statuses else ("idle" if set(statuses) == {"idle"} else "in_progress")
    _save_meta(workspace, meta)

    if new_step != prev_step:
        state_store.append_event(
            workspace, "task.status_changed", f"step {step}: {prev_step} → {new_step}",
            task_id=task_id, step=step, provider=meta["steps"][step].get("provider"),
            data={"scope": "step", "from": prev_step, "to": new_step},
        )
    if meta["status"] != prev_task:
        state_store.append_event(
            workspace, "task.status_changed", f"task {prev_task} → {meta['status']}",
            task_id=task_id, data={"scope": "task", "from": prev_task, "to": meta["status"]},
        )


_AUTH_MARKERS = ("not logged in", "please log in", "unauthorized", "authentication", "401", "api key", "login required")


def _classify_run_failure(record: RunRecord) -> Optional[str]:
    """Map a finished agent run to a durable failure kind (None on success)."""
    if record.status == "succeeded":
        return None
    if record.status == "cancelled":
        return "cancelled"
    if record.status == "error":
        return "start_error"
    blob = (record.stderr + "\n" + record.stdout).lower()
    if any(m in blob for m in _AUTH_MARKERS):
        return "auth_required"
    return "exit_nonzero"


async def run_step(
    workspace: Path,
    task_id: str,
    step: str,
    confirm: bool = False,
    source: str = "manual",
    provider_override: Optional[str] = None,
) -> dict:
    """Run one traffic-control step as a real subprocess (or explain why not).

    ``provider_override`` lets a rerouted queue item run on a different provider than the
    workspace routing default for the step's role.
    """
    if step not in STEP_DEFS:
        raise ValueError(f"unknown step: {step}")
    _load_meta(workspace, task_id)  # 404 if missing

    usage = usage_service.ensure_usage(workspace)
    mode = usage.get("orchestrationMode", "balanced")
    provider = provider_override or step_provider(workspace, step)
    prompt = prompt_templates.STEP_PROMPTS[step](usage, _task_rel_dir(task_id))
    preview = build_step_preview(workspace, task_id, step, usage, provider_override=provider_override)
    folder = paths.task_dir(workspace, task_id)

    busy = RUNNER.running_for_provider(provider)
    if busy is not None:
        return {**provider_busy_result(provider, busy.id, busy.step), **preview}

    # Keep 03_CLAUDE_PROMPT.md current whenever a Claude implementation runs.
    if step == "claude_implement":
        (folder / "03_CLAUDE_PROMPT.md").write_text(
            "# Claude Prompt\n\n```text\n" + prompt + "\n```\n", encoding="utf-8"
        )

    if mode == "manual_approval" and source == "auto":
        return {"status": "manual_preview", **preview}

    if not preview["providerInstalled"]:
        saved = folder / "logs" / f"{step}.intended-prompt.txt"
        saved.parent.mkdir(exist_ok=True)
        saved.write_text(
            f"# Provider '{provider}' is not installed.\n# Intended command:\n"
            f"{preview['commandPreview']}\n\n# Prompt:\n{prompt}\n",
            encoding="utf-8",
        )
        _set_step_state(workspace, task_id, step, status="provider_missing", provider=provider)
        _add_event(
            workspace, task_id, "provider_missing",
            f"`{provider}` is not installed — prompt ({len(prompt):,} chars) saved to logs/{saved.name}",
            step=step, provider=provider,
        )
        state_store.append_event(
            workspace, "run.finished", f"`{provider}` not installed — step skipped",
            task_id=task_id, step=step, provider=provider,
            data={"status": "provider_missing", "failureKind": "provider_missing"},
        )
        routing_service.append_decision(
            workspace, task_id,
            f"Step `{step}` skipped: provider `{provider}` is not installed. "
            f"Prompt saved to logs/{saved.name}. Install hint and command preview shown in UI.",
        )
        add_log_entry(
            "task-step", f"{step}: provider {provider} missing — saved prompt instead",
            provider=provider, task_id=task_id, step=step, status="warn",
        )
        return {
            "status": "provider_missing",
            "savedPromptTo": f"{_task_rel_dir(task_id)}/logs/{saved.name}",
            "message": f"`{provider}` is not installed. The prompt was saved to the task folder.",
            **preview,
        }

    if provider == "claude" and usage_service.provider_health(usage, "claude") == "red" and not confirm:
        return {
            "status": "needs_confirmation",
            "warning": (
                "Claude usage health is RED. Routing recommends Codex planning + Antigravity QA + local tests "
                "instead. Run Claude anyway?"
            ),
            **preview,
        }

    argv = _build_argv(
        config.get_command_templates().get(provider, f"{provider} {{prompt}}"),
        prompt,
        config.get_models().get(provider),
    )
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = paths.task_logs_dir(workspace, task_id) / f"{stamp}-{step}.log"

    # Audit trail: the exact (redacted) prompt this agent received.
    prompt_file = paths.task_logs_dir(workspace, task_id) / f"{stamp}-{step}.prompt.txt"
    prompt_file.parent.mkdir(exist_ok=True)
    prompt_file.write_text(redact(prompt), encoding="utf-8")

    # Snapshots for artifact/handoff detection on completion.
    pre_files = _snapshot_task_files(workspace, task_id)
    pre_code = await _changed_code_paths(workspace)

    async def on_complete(record: RunRecord) -> None:
        record.prompt_file = prompt_file.name
        record.failure_kind = _classify_run_failure(record)
        post_files = _snapshot_task_files(workspace, task_id)
        artifacts = sorted(
            name
            for name, sig in post_files.items()
            if name != "ROUTING_DECISIONS.md" and pre_files.get(name) != sig
        )
        code_changed = sorted((await _changed_code_paths(workspace)) - pre_code)

        usage_service.record_call(
            workspace, provider,
            prompt_chars=len(prompt),
            output_chars=len(record.stdout) + len(record.stderr),
            duration_ms=record.duration_ms or 0,
            status=record.status,
        )
        _set_step_state(
            workspace, task_id, step,
            status=record.status, exitCode=record.exit_code, runId=record.id, provider=provider,
            artifactsWritten=artifacts, codeChanged=code_changed,
            promptFile=prompt_file.name, logFile=log_file.name,
        )
        wrote = (", wrote " + ", ".join(artifacts)) if artifacts else ""
        touched = (f", changed {len(code_changed)} production file(s): " + ", ".join(code_changed[:5])) if code_changed else ""
        _add_event(
            workspace, task_id, "step_finished",
            f"{provider} finished {STEP_DEFS[step]['label']}: {record.status} "
            f"(exit {record.exit_code}, {(record.duration_ms or 0) / 1000:.1f}s, "
            f"{len(record.stdout):,} chars out){wrote}{touched}",
            step=step, provider=provider,
            extra={"artifacts": artifacts, "codeChanged": code_changed, "status": record.status},
        )
        routing_service.append_decision(
            workspace, task_id,
            f"Step `{step}` finished via `{provider}`: {record.status} "
            f"(exit {record.exit_code}, {(record.duration_ms or 0) / 1000:.1f}s). Log: logs/{log_file.name}"
            + (f" Wrote: {', '.join(artifacts)}." if artifacts else "")
            + (f" Production files changed: {', '.join(code_changed)}." if code_changed else ""),
        )
        add_log_entry(
            "task-step",
            f"{step} ({provider}) {record.status} in {(record.duration_ms or 0) / 1000:.1f}s",
            provider=provider, task_id=task_id, step=step,
            status="info" if record.status == "succeeded" else "warn",
            output=(record.stdout + "\n" + record.stderr)[-3000:],
        )
        # Durable run ledger + finish event survive restart; in-memory records do not.
        state_store.persist_run(workspace, record.to_ledger(workspace))
        state_store.append_event(
            workspace, "run.finished",
            f"{provider} {record.status} (exit {record.exit_code}, {(record.duration_ms or 0) / 1000:.1f}s)",
            task_id=task_id, step=step, provider=provider,
            data={"runId": record.id, "status": record.status, "failureKind": record.failure_kind},
        )

    busy = RUNNER.running_for_provider(provider)
    if busy is not None:
        return {**provider_busy_result(provider, busy.id, busy.step), **preview}

    record, consume_task = await RUNNER.start(
        argv, workspace,
        task_id=task_id, step=step, provider=provider,
        log_file=str(log_file), on_complete=on_complete,
        workspace=workspace, stream_kind="run",
    )
    record.prompt_file = prompt_file.name
    if record.status == "error":
        record.failure_kind = "start_error"
        _set_step_state(workspace, task_id, step, status="error", provider=provider)
        state_store.persist_run(workspace, record.to_ledger(workspace))
        state_store.append_event(
            workspace, "run.finished", f"failed to start `{provider}`",
            task_id=task_id, step=step, provider=provider,
            data={"runId": record.id, "status": "error", "failureKind": "start_error"},
        )
        return {"status": "error", "message": record.stderr[:500], **preview}

    _set_step_state(workspace, task_id, step, status="running", runId=record.id, provider=provider)
    # Persist the running run immediately so a restart before completion can recover it.
    state_store.persist_run(workspace, record.to_ledger(workspace))
    state_store.append_event(
        workspace, "run.started", f"{provider} started {STEP_DEFS[step]['label']}",
        task_id=task_id, step=step, provider=provider, data={"runId": record.id, "pid": record.pid},
    )
    reads = ", ".join(r.replace("@diff", "git diff").replace("@folder", "task folder") for r in STEP_IO[step]["reads"])
    _add_event(
        workspace, task_id, "step_started",
        f"controller routed {STEP_DEFS[step]['label']} → {provider} "
        f"(sent {len(prompt):,} chars; reads: {reads})",
        step=step, provider=provider,
    )
    add_log_entry("task-step", f"started {step} via {provider}", provider=provider, task_id=task_id, step=step)
    return {"status": "started", "runId": record.id, "consumeTaskName": consume_task.get_name(), **preview}


# ------------------------------------------------------------- full sequence


async def _await_run(run_id: str) -> RunRecord:
    record = RUNNER.runs[run_id]
    while record.status == "running":
        await asyncio.sleep(0.5)
    return record


def _set_sequence(workspace: Path, task_id: str, status: str, current: Optional[str]) -> None:
    meta = _load_meta(workspace, task_id)
    meta["fullSequence"] = {"status": status, "currentStep": current}
    _save_meta(workspace, meta)


async def run_full_sequence(workspace: Path, task_id: str, confirm: bool = False) -> dict:
    """Run codex_spec → claude_implement → gemini_qa → codex_review sequentially."""
    meta = _load_meta(workspace, task_id)
    usage = usage_service.ensure_usage(workspace)
    mode = usage.get("orchestrationMode", "balanced")

    if mode == "manual_approval":
        previews = [build_step_preview(workspace, task_id, s, usage) for s in FULL_SEQUENCE]
        return {
            "status": "manual_preview",
            "message": "Manual Approval mode: nothing was run. Review each command preview and run steps individually.",
            "previews": previews,
        }

    if task_id in _full_sequences_running:
        return {"status": "already_running", "message": "A full sequence is already running for this task."}

    claude_red = usage_service.provider_health(usage, "claude") == "red"

    async def sequence() -> None:
        _full_sequences_running.add(task_id)
        try:
            # Local pre-check first: free, and informs routing.
            git = await git_service.git_info(workspace)
            usage_service.increment_local_steps(workspace)
            precheck = paths.task_logs_dir(workspace, task_id) / "local_precheck.log"
            precheck.parent.mkdir(exist_ok=True)
            precheck.write_text(
                f"# Local pre-check (no AI calls)\nbranch: {git.get('branch')}\n"
                f"status:\n{git.get('statusShort', git.get('error', ''))}\n\ndiff --stat:\n{git.get('diffStat', '')}\n",
                encoding="utf-8",
            )
            add_log_entry("git", f"local pre-check for {task_id} (branch {git.get('branch', '-')})", task_id=task_id)
            _add_event(
                workspace, task_id, "local_check",
                f"local git pre-check (free): branch {git.get('branch', '-')}, "
                f"{git.get('changedFileCount', 0)} changed file(s) — no AI call",
                provider="git",
            )

            for step in FULL_SEQUENCE:
                fresh_usage = usage_service.ensure_usage(workspace)

                if (
                    mode == "budget_saver"
                    and step == "codex_spec"
                    and len(meta.get("goal", "")) < routing_service.SMALL_TASK_GOAL_CHARS
                ):
                    usage_service.increment_avoided(workspace)
                    _set_step_state(workspace, task_id, step, status="skipped_budget")
                    _add_event(
                        workspace, task_id, "skipped",
                        "Budget Saver skipped the Codex spec for this small task — expensive call avoided",
                        step=step, provider=step_provider(workspace, step),
                    )
                    routing_service.append_decision(
                        workspace, task_id,
                        "Budget Saver: skipped Codex spec for this small task — Claude gets the compact "
                        "user goal directly. Expensive call avoided.",
                    )
                    continue

                if step == "claude_implement" and usage_service.provider_health(fresh_usage, "claude") == "red" and not confirm:
                    _set_sequence(workspace, task_id, "blocked_claude_red", step)
                    _add_event(
                        workspace, task_id, "blocked",
                        "sequence paused before Implement — Claude health is RED (explicit confirmation required)",
                        step=step, provider="claude",
                    )
                    routing_service.append_decision(
                        workspace, task_id,
                        "Full sequence stopped before `claude_implement`: Claude health is RED. "
                        "Run the step manually with explicit confirmation, or route around Claude.",
                    )
                    add_log_entry(
                        "task-step", f"sequence blocked before {step}: Claude is red",
                        task_id=task_id, step=step, status="warn",
                    )
                    return

                _set_sequence(workspace, task_id, "running", step)
                result = await run_step(workspace, task_id, step, confirm=confirm, source="auto")
                if result["status"] == "started":
                    record = await _await_run(result["runId"])
                    if record.status != "succeeded":
                        _set_sequence(workspace, task_id, f"stopped_at_{step}", step)
                        return
                elif result["status"] in ("provider_missing",):
                    continue  # prompt saved; later steps may still be useful
                else:
                    _set_sequence(workspace, task_id, f"stopped_at_{step}", step)
                    return

            _set_sequence(workspace, task_id, "completed", None)
            _add_event(workspace, task_id, "sequence", "full sequence completed")
            add_log_entry("task-step", f"full sequence completed for {task_id}", task_id=task_id)
        finally:
            _full_sequences_running.discard(task_id)

    _set_sequence(workspace, task_id, "running", FULL_SEQUENCE[0])
    asyncio.create_task(sequence())
    warning = (
        "Claude is RED: the sequence will pause before claude_implement unless confirmed." if claude_red else None
    )
    return {"status": "started", "message": "Full sequence started.", "warning": warning}


async def stop(run_id: Optional[str]) -> dict:
    if run_id:
        ok = await RUNNER.cancel(run_id)
        stopped = [run_id] if ok else []
    else:
        stopped = await RUNNER.cancel_all()
    add_log_entry("system", f"stop requested — cancelled {len(stopped)} process(es)")
    return {"stopped": stopped}
