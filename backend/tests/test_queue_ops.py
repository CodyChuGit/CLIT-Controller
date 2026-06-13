"""Retry / skip / reroute and failed-step blocking, plus durable queue events."""

from pathlib import Path

from agentflow import config, queue_service, state_store, task_service


def make_task(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    tid = task_service.create_task(ws, "Queue ops", "Do things.")["id"]
    return ws, tid


def _items_by_step(ws):
    return {i["step"]: i for i in queue_service.load_queue(ws)["items"]}


def test_enqueue_writes_durable_events(tmp_path):
    ws, tid = make_task(tmp_path)
    queue_service.add_steps(ws, tid, ["codex_spec"])
    assert any(e["type"] == "queue.enqueued" for e in state_store.read_events(ws))


def test_failed_step_blocks_later_then_retry_unblocks(tmp_path):
    ws, tid = make_task(tmp_path)
    queue_service.add_steps(ws, tid, ["codex_spec", "claude_implement"])
    data = queue_service.load_queue(ws)
    # First item was running but its run record is gone (e.g. crash mid-flight).
    data["items"][0].update(status="running", runId="ghost-run")
    queue_service._save(ws, data)
    # Finalize settles it to failed and blocks the later queued item for this task.
    queue_service._finalize_running(ws)
    assert _items_by_step(ws)["codex_spec"]["status"] == "failed"
    assert _items_by_step(ws)["claude_implement"]["status"] == "blocked"

    # Retrying the failed item re-queues it AND unblocks the later one.
    res = queue_service.retry_item(ws, _items_by_step(ws)["codex_spec"]["id"])
    assert res["status"] == "ok"
    items = _items_by_step(ws)
    assert items["codex_spec"]["status"] == "queued"
    assert items["codex_spec"]["attempt"] == 2
    assert items["claude_implement"]["status"] == "queued"


def test_skip_marks_skipped_and_unblocks(tmp_path):
    ws, tid = make_task(tmp_path)
    queue_service.add_steps(ws, tid, ["codex_spec", "claude_implement"])
    data = queue_service.load_queue(ws)
    data["items"][0].update(status="failed")
    data["items"][1].update(status="blocked")
    queue_service._save(ws, data)

    res = queue_service.skip_item(ws, _items_by_step(ws)["codex_spec"]["id"])
    assert res["status"] == "ok"
    items = _items_by_step(ws)
    assert items["codex_spec"]["status"] == "skipped"
    assert items["claude_implement"]["status"] == "queued"
    assert any(e["type"] == "queue.skipped" for e in state_store.read_events(ws))


def test_reroute_changes_provider_and_sets_override(tmp_path):
    ws, tid = make_task(tmp_path)
    queue_service.add_steps(ws, tid, ["codex_spec"])
    item_id = _items_by_step(ws)["codex_spec"]["id"]
    data = queue_service.load_queue(ws)
    data["items"][0].update(status="failed")
    queue_service._save(ws, data)

    res = queue_service.reroute_item(ws, item_id, "claude")
    assert res["status"] == "ok"
    item = _items_by_step(ws)["codex_spec"]
    assert item["status"] == "queued"
    assert item["provider"] == "claude"
    assert item["providerOverride"] == "claude"


def test_reroute_rejects_unknown_provider(tmp_path):
    ws, tid = make_task(tmp_path)
    queue_service.add_steps(ws, tid, ["codex_spec"])
    item_id = _items_by_step(ws)["codex_spec"]["id"]
    res = queue_service.reroute_item(ws, item_id, "warp_drive")
    assert res["status"] == "bad_provider"


def test_retry_rejects_non_retryable(tmp_path):
    ws, tid = make_task(tmp_path)
    queue_service.add_steps(ws, tid, ["codex_spec"])
    item_id = _items_by_step(ws)["codex_spec"]["id"]  # status queued
    res = queue_service.retry_item(ws, item_id)
    assert res["status"] == "not_retryable"
