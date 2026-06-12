"""Tasks: folders, markdown handoff files, and real step execution."""

from __future__ import annotations

import asyncio
import re
import shlex
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import config, git_service, paths, prompt_templates, routing_service, usage_service
from .process_runner import RUNNER, RunRecord, add_log_entry, now_iso
from .redaction import redact

# step id -> (routing role, human label)
STEP_DEFS: dict[str, dict] = {
    # Labels are provider-neutral; the routed provider is shown alongside in the UI.
    "codex_spec": {"role": "pm", "label": "Write Spec"},
    "claude_implement": {"role": "engineer", "label": "Implement"},
    "gemini_qa": {"role": "qa", "label": "QA / Test"},
    "codex_review": {"role": "pm", "label": "Final Review"},
    "claude_fix": {"role": "engineer", "label": "Fix Bugs"},
}

FULL_SEQUENCE = ["codex_spec", "claude_implement", "gemini_qa", "codex_review"]

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


# ----------------------------------------------------------------- create/list


def create_task(workspace: Path, title: str, goal: str) -> dict:
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
    }
    _save_meta(workspace, meta)
    add_log_entry("task", f"created task {task_id}: {title}", task_id=task_id)
    return meta


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
        "runs": [r.to_dict() for r in RUNNER.runs_for_task(task_id)],
        "stepPreviews": previews,
        "recommendation": routing_service.recommend(usage),
    }


def read_task_file(workspace: Path, task_id: str, name: str) -> dict:
    folder = paths.task_dir(workspace, task_id).resolve()
    target = (folder / name).resolve()
    if not str(target).startswith(str(folder)) or not target.is_file():
        raise FileNotFoundError(name)
    content = target.read_text(encoding="utf-8", errors="replace")
    return {"name": name, "content": redact(content)}


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


def _build_argv(template: str, prompt: str) -> list[str]:
    tokens = shlex.split(template)
    argv, replaced = [], False
    for token in tokens:
        if "{prompt}" in token:
            argv.append(token.replace("{prompt}", prompt))
            replaced = True
        else:
            argv.append(token)
    if not replaced:
        argv.append(prompt)
    return argv


def build_step_preview(workspace: Path, task_id: str, step: str, usage: Optional[dict] = None) -> dict:
    usage = usage or usage_service.ensure_usage(workspace)
    provider = step_provider(workspace, step)
    prompt = prompt_templates.STEP_PROMPTS[step](usage, _task_rel_dir(task_id))
    template = config.get_command_templates().get(provider, f"{provider} {{prompt}}")
    argv = _build_argv(template, prompt)
    installed = shutil.which(argv[0]) is not None
    return {
        "step": step,
        "label": STEP_DEFS[step]["label"],
        "provider": provider,
        "providerInstalled": installed,
        "commandPreview": redact(shlex.join(argv)),
        "promptChars": len(prompt),
    }


def _set_step_state(workspace: Path, task_id: str, step: str, **fields) -> None:
    meta = _load_meta(workspace, task_id)
    meta["steps"].setdefault(step, {})
    meta["steps"][step].update(fields, updatedAt=now_iso())
    statuses = [s.get("status") for s in meta["steps"].values()]
    meta["status"] = "running" if "running" in statuses else ("idle" if set(statuses) == {"idle"} else "in_progress")
    _save_meta(workspace, meta)


async def run_step(
    workspace: Path,
    task_id: str,
    step: str,
    confirm: bool = False,
    source: str = "manual",
) -> dict:
    """Run one orchestration step as a real subprocess (or explain why not)."""
    if step not in STEP_DEFS:
        raise ValueError(f"unknown step: {step}")
    _load_meta(workspace, task_id)  # 404 if missing

    usage = usage_service.ensure_usage(workspace)
    mode = usage.get("orchestrationMode", "balanced")
    provider = step_provider(workspace, step)
    prompt = prompt_templates.STEP_PROMPTS[step](usage, _task_rel_dir(task_id))
    preview = build_step_preview(workspace, task_id, step, usage)
    folder = paths.task_dir(workspace, task_id)

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

    argv = _build_argv(config.get_command_templates().get(provider, f"{provider} {{prompt}}"), prompt)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = paths.task_logs_dir(workspace, task_id) / f"{stamp}-{step}.log"

    async def on_complete(record: RunRecord) -> None:
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
        )
        routing_service.append_decision(
            workspace, task_id,
            f"Step `{step}` finished via `{provider}`: {record.status} "
            f"(exit {record.exit_code}, {(record.duration_ms or 0) / 1000:.1f}s). Log: logs/{log_file.name}",
        )
        add_log_entry(
            "task-step",
            f"{step} ({provider}) {record.status} in {(record.duration_ms or 0) / 1000:.1f}s",
            provider=provider, task_id=task_id, step=step,
            status="info" if record.status == "succeeded" else "warn",
            output=(record.stdout + "\n" + record.stderr)[-3000:],
        )

    record, consume_task = await RUNNER.start(
        argv, workspace,
        task_id=task_id, step=step, provider=provider,
        log_file=str(log_file), on_complete=on_complete,
    )
    if record.status == "error":
        _set_step_state(workspace, task_id, step, status="error", provider=provider)
        return {"status": "error", "message": record.stderr[:500], **preview}

    _set_step_state(workspace, task_id, step, status="running", runId=record.id, provider=provider)
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

            for step in FULL_SEQUENCE:
                fresh_usage = usage_service.ensure_usage(workspace)

                if (
                    mode == "budget_saver"
                    and step == "codex_spec"
                    and len(meta.get("goal", "")) < routing_service.SMALL_TASK_GOAL_CHARS
                ):
                    usage_service.increment_avoided(workspace)
                    _set_step_state(workspace, task_id, step, status="skipped_budget")
                    routing_service.append_decision(
                        workspace, task_id,
                        "Budget Saver: skipped Codex spec for this small task — Claude gets the compact "
                        "user goal directly. Expensive call avoided.",
                    )
                    continue

                if step == "claude_implement" and usage_service.provider_health(fresh_usage, "claude") == "red" and not confirm:
                    _set_sequence(workspace, task_id, "blocked_claude_red", step)
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
