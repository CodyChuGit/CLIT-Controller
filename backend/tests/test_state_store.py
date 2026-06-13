from pathlib import Path

from agentflow import config, state_store
from agentflow.process_runner import RunRecord


def make_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    return ws


def test_events_append_read_and_cursor(tmp_path):
    ws = make_ws(tmp_path)
    e1 = state_store.append_event(ws, "task.created", "one", task_id="t1")
    e2 = state_store.append_event(ws, "run.started", "two", task_id="t1", step="codex_spec")
    assert e1["id"] == 1 and e2["id"] == 2
    assert state_store.events_cursor(ws) == 2
    # cursor filtering returns only newer events
    assert [e["id"] for e in state_store.read_events(ws, after=1)] == [2]
    assert state_store.read_events(ws, after=2) == []


def test_events_are_bounded(tmp_path, monkeypatch):
    ws = make_ws(tmp_path)
    monkeypatch.setattr(state_store, "MAX_EVENTS", 5)
    for i in range(12):
        state_store.append_event(ws, "x", str(i))
    events = state_store.read_events(ws)
    assert len(events) == 5
    # ids stay monotonic even after pruning the oldest
    assert [e["id"] for e in events] == [8, 9, 10, 11, 12]
    assert state_store.events_cursor(ws) == 12


def test_run_ledger_roundtrip_and_prune_keeps_running(tmp_path, monkeypatch):
    ws = make_ws(tmp_path)
    monkeypatch.setattr(state_store, "MAX_RUNS", 3)
    # one running run plus several finished ones
    running = RunRecord(id="run-live", argv=["x"], cwd=str(ws), task_id="t", status="running")
    state_store.persist_run(ws, running.to_ledger(ws))
    for i in range(6):
        rec = RunRecord(id=f"done-{i}", argv=["x"], cwd=str(ws), task_id="t", status="succeeded")
        rec.started_at = f"2026-01-01T00:00:0{i}+00:00"
        state_store.persist_run(ws, rec.to_ledger(ws))
    runs = state_store.load_runs(ws)
    assert "run-live" in runs                      # never pruned while running
    assert len(runs) <= 3
    assert state_store.get_run(ws, "run-live")["status"] == "running"


def test_runs_for_task_filters_and_sorts(tmp_path):
    ws = make_ws(tmp_path)
    a = RunRecord(id="a", argv=["x"], cwd=str(ws), task_id="t1", status="succeeded")
    a.started_at = "2026-01-01T00:00:02+00:00"
    b = RunRecord(id="b", argv=["x"], cwd=str(ws), task_id="t1", status="failed")
    b.started_at = "2026-01-01T00:00:01+00:00"
    other = RunRecord(id="c", argv=["x"], cwd=str(ws), task_id="t2", status="succeeded")
    for r in (a, b, other):
        state_store.persist_run(ws, r.to_ledger(ws))
    got = state_store.runs_for_task(ws, "t1")
    assert [r["id"] for r in got] == ["b", "a"]     # sorted by startedAt


def test_approvals_create_and_resolve(tmp_path):
    ws = make_ws(tmp_path)
    ap = state_store.create_approval(ws, action="git push", reason="touches remote", provider="codex", task_id="t1")
    assert ap["status"] == "pending"
    assert [a["id"] for a in state_store.list_approvals(ws, pending_only=True)] == [ap["id"]]
    resolved = state_store.resolve_approval(ws, ap["id"], approved=True)
    assert resolved["status"] == "approved" and resolved["resolver"] == "user"
    assert state_store.list_approvals(ws, pending_only=True) == []
    # resolving again is a no-op (stays approved)
    again = state_store.resolve_approval(ws, ap["id"], approved=False)
    assert again["status"] == "approved"
    # the create + grant both wrote durable events
    types = {e["type"] for e in state_store.read_events(ws)}
    assert {"approval.required", "approval.granted"} <= types


def test_ledgers_are_schema_versioned(tmp_path):
    ws = make_ws(tmp_path)
    state_store.append_event(ws, "x", "y")
    doc = config.read_json(state_store.events_file(ws), None)
    assert doc["schemaVersion"] == state_store.SCHEMA_VERSION
