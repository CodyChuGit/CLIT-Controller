"""CLITC_RESULT_V1 action execution — the controller engine's mutation path.

Covers the revamp's Workstream 2 acceptance criteria: a valid result block
mutates state through the action executor (chat and consult sources), an invalid
block produces a typed failure event and NO mutation, legacy directives still
work but emit a compatibility warning, and every turn leaves a durable
``controller.turn_completed`` record.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from agentflow import chat_service, config, queue_service, state_store, task_service
from agentflow.controller import actions, engine
from agentflow.controller_protocol import CLOSE, OPEN


def make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    return ws


def v1(action_json: str, summary: str = "ok") -> str:
    return (
        "some reasoning prose\n\n"
        f"{OPEN}\n"
        f'{{"schemaVersion":"1","kind":"controller_result","message":{{"summary":"{summary}"}},'
        f'"action":{action_json}}}\n'
        f"{CLOSE}\n"
    )


def apply(ws: Path, out: str, source: str = "controller_chat", task_id: str | None = None) -> dict:
    return asyncio.run(
        engine.apply_controller_output(ws, out, provider="antigravity", source=source, run_id="run_x", task_id=task_id)
    )


def events(ws: Path) -> list[dict]:
    return config.read_json(state_store.events_file(ws), {}).get("events", [])


def event_types(ws: Path) -> list[str]:
    return [e["type"] for e in events(ws)]


# ------------------------------------------------------------------ valid actions


def test_create_task_action_creates_and_queues(tmp_path):
    ws = make_workspace(tmp_path)
    turn = apply(ws, v1('{"type":"create_task","title":"Add login","goal":"implement login"}'))
    assert turn == {"resultSource": "clitc_result_v1", "status": "actioned", "actionType": "create_task"}
    tasks = task_service.list_tasks(ws)
    assert len(tasks) == 1 and tasks[0]["title"] == "Add login"
    items = queue_service.load_queue(ws)["items"]
    assert [i["step"] for i in items] == ["codex_spec"]  # default first step
    assert "controller.turn_completed" in event_types(ws)


def test_queue_steps_action_queues_to_latest_task(tmp_path):
    ws = make_workspace(tmp_path)
    task_service.create_task(ws, "T", "goal")
    turn = apply(ws, v1('{"type":"queue_steps","taskId":"latest","steps":["claude_implement"]}'))
    assert turn["status"] == "actioned"
    items = queue_service.load_queue(ws)["items"]
    assert [i["step"] for i in items] == ["claude_implement"]


def test_queue_steps_uses_consult_task_when_ref_unresolvable(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "T", "goal")
    out = v1('{"type":"queue_steps","taskId":"no-such-task-zzz","steps":["gemini_qa"]}')
    turn = apply(ws, out, source="consult", task_id=meta["id"])
    assert turn["status"] == "actioned"
    items = queue_service.load_queue(ws)["items"]
    assert items and items[0]["taskId"] == meta["id"]


def test_run_command_action_goes_through_policy_gate(tmp_path, monkeypatch):
    ws = make_workspace(tmp_path)
    calls: list[tuple] = []

    async def fake_run(workspace, command, provider, task_id=None, approved=False):
        calls.append((command, provider, task_id))

    monkeypatch.setattr(chat_service, "execute_run_directive", fake_run)
    turn = apply(ws, v1('{"type":"run_command","command":"npm test"}'))
    assert turn["status"] == "actioned"
    assert calls == [("npm test", "antigravity", None)]


def test_request_approval_creates_durable_pending_approval(tmp_path):
    ws = make_workspace(tmp_path)
    turn = apply(ws, v1('{"type":"request_approval","command":"git push","reason":"remote write"}'))
    assert turn["status"] == "actioned"
    approvals = state_store.list_approvals(ws, pending_only=True)
    assert len(approvals) == 1
    assert approvals[0]["action"] == "git push" and approvals[0]["status"] == "pending"


def test_request_user_marks_task_needs_user(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "T", "goal")
    apply(ws, v1('{"type":"request_user","reason":"pick a database"}'), source="consult", task_id=meta["id"])
    task_events = task_service._load_meta(ws, meta["id"]).get("events", [])
    assert any(e["type"] == "needs_user" and "pick a database" in e["detail"] for e in task_events)


def test_complete_task_sets_done_and_verdict(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "T", "goal")
    turn = apply(ws, v1('{"type":"complete_task","reason":"shipped"}'), source="consult", task_id=meta["id"])
    assert turn["status"] == "actioned"
    meta2 = task_service._load_meta(ws, meta["id"])
    assert meta2["status"] == "done"
    assert meta2["orchestratorVerdict"]["reason"] == "shipped"
    assert "task.summary_ready" in event_types(ws)


def test_retry_requeues_failed_item(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "T", "goal")
    queue_service.add_steps(ws, meta["id"], ["claude_implement"])
    data = queue_service.load_queue(ws)
    data["items"][0]["status"] = "failed"
    queue_service._save(ws, data)

    turn = apply(ws, v1(f'{{"type":"retry","taskId":"{meta["id"]}"}}'))
    assert turn["status"] == "actioned"
    item = queue_service.load_queue(ws)["items"][0]
    assert item["status"] == "queued" and item["attempt"] == 2


def test_reroute_moves_step_to_another_provider(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "T", "goal")
    queue_service.add_steps(ws, meta["id"], ["gemini_qa"])
    out = v1(f'{{"type":"reroute","taskId":"{meta["id"]}","step":"gemini_qa","provider":"codex"}}')
    turn = apply(ws, out)
    assert turn["status"] == "actioned"
    item = queue_service.load_queue(ws)["items"][0]
    assert item["provider"] == "codex" and item["providerOverride"] == "codex"


def test_cancel_action_cancels_run(tmp_path, monkeypatch):
    ws = make_workspace(tmp_path)
    cancelled: list[str] = []

    async def fake_cancel(run_id):
        cancelled.append(run_id)
        return True

    monkeypatch.setattr(actions.RUNNER, "cancel", fake_cancel)
    turn = apply(ws, v1('{"type":"cancel","runId":"run_123"}'))
    assert turn["status"] == "actioned"
    assert cancelled == ["run_123"]


def test_answer_action_mutates_nothing(tmp_path):
    ws = make_workspace(tmp_path)
    turn = apply(ws, v1('{"type":"answer"}'))
    assert turn["status"] == "actioned"
    assert task_service.list_tasks(ws) == []
    assert queue_service.load_queue(ws)["items"] == []


# --------------------------------------------------- invalid / fallback / records


def test_invalid_result_emits_typed_failure_and_mutates_nothing(tmp_path):
    ws = make_workspace(tmp_path)
    out = (
        f"{OPEN}\n"
        '{"schemaVersion":"1","kind":"controller_result","action":{"type":"frobnicate"}}\n'
        f"{CLOSE}\n"
        "```agentflow-task\ntitle: Sneaky\ngoal: should not run\n```\n"
    )
    turn = apply(ws, out)
    assert turn == {"resultSource": "clitc_result_v1", "status": "invalid", "actionType": None}
    assert task_service.list_tasks(ws) == []  # the legacy block was NOT honored
    assert queue_service.load_queue(ws)["items"] == []
    types = event_types(ws)
    assert "controller.result_invalid" in types
    # The user is told no action was taken.
    msgs = chat_service.load_chat(ws)["messages"]
    assert any("no action" in m["content"].lower() for m in msgs)


def test_invalid_result_in_consult_marks_needs_user(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "T", "goal")
    out = f"{OPEN}\nnot json at all\n{CLOSE}\n"
    turn = apply(ws, out, source="consult", task_id=meta["id"])
    assert turn["status"] == "invalid"
    task_events = task_service._load_meta(ws, meta["id"]).get("events", [])
    assert any(e["type"] == "needs_user" for e in task_events)


def test_legacy_directive_fallback_works_and_warns(tmp_path):
    ws = make_workspace(tmp_path)
    task_service.create_task(ws, "T", "goal")
    out = "no v1 block here\n```agentflow-queue\ntask: latest\nsteps: codex_review\n```\n"
    turn = apply(ws, out)
    assert turn["resultSource"] == "legacy"
    assert [i["step"] for i in queue_service.load_queue(ws)["items"]] == ["codex_review"]
    assert "controller.legacy_directives" in event_types(ws)


def test_prose_only_reply_is_no_action(tmp_path):
    ws = make_workspace(tmp_path)
    turn = apply(ws, "just some thoughts, nothing actionable")
    assert turn == {"resultSource": "none", "status": "no_action", "actionType": None}


def test_multiple_blocks_emit_misbehaviour_signal(tmp_path):
    ws = make_workspace(tmp_path)
    block = v1('{"type":"answer"}')
    apply(ws, block + "\n" + block)
    assert "controller.result_misbehaviour" in event_types(ws)


def test_turn_completed_record_carries_typed_fields(tmp_path):
    ws = make_workspace(tmp_path)
    apply(ws, v1('{"type":"answer"}'))
    turn_events = [e for e in events(ws) if e["type"] == "controller.turn_completed"]
    assert len(turn_events) == 1
    data = turn_events[0]["data"]
    assert data["source"] == "controller_chat"
    assert data["resultSource"] == "clitc_result_v1"
    assert data["actionType"] == "answer"
    assert data["status"] == "actioned"
    assert data["runId"] == "run_x"


def test_chat_send_executes_v1_action_end_to_end(tmp_path, monkeypatch):
    """The live path: a real controller CLI run (stubbed with a script that emits
    prose + a CLITC_RESULT_V1 block) whose completion queues steps via the engine."""
    import time

    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "T", "goal")

    script = tmp_path / "fake-claude"
    body = (
        '{"schemaVersion":"1","kind":"controller_result",'
        '"message":{"summary":"Queueing implementation."},'
        '"action":{"type":"queue_steps","taskId":"latest","steps":["claude_implement"]}}'
    )
    script.write_text(
        "#!/bin/sh\nprintf 'Narrative first.\\n\\n<<<CLITC_RESULT_V1\\n%s\\nCLITC_RESULT_V1>>>\\n' " + f"'{body}'\n"
    )
    script.chmod(0o755)

    monkeypatch.setattr(config, "get_command_templates", lambda: {"claude": f"{script} {{prompt}}"})

    async def run() -> None:
        res = await chat_service.send(ws, "continue the task", provider="claude")
        assert res["status"] == "started"
        # Wait for the run (and its on_complete) to finish.
        for _ in range(100):
            if chat_service.pending_state(ws) is None:
                break
            await asyncio.sleep(0.05)

    asyncio.run(run())
    time.sleep(0.05)  # on_complete runs as a callback after the process exits

    items = queue_service.load_queue(ws)["items"]
    assert [i["step"] for i in items] == ["claude_implement"]
    assert items[0]["taskId"] == meta["id"]
    # The narrative (not the JSON block) landed in the chat bubble.
    msgs = chat_service.load_chat(ws)["messages"]
    assistant = [m for m in msgs if m["role"] == "assistant"]
    assert assistant and "Narrative first." in assistant[0]["content"]
    assert "CLITC_RESULT_V1" not in assistant[0]["content"]
    assert "controller.turn_completed" in event_types(ws)
