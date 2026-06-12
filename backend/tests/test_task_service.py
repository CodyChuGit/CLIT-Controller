from pathlib import Path

from agentflow import config, task_service
from agentflow.prompt_templates import TASK_FILES


def make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "demo-project"
    ws.mkdir()
    config.ensure_workspace(ws)
    return ws


def test_create_task_writes_all_handoff_files(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "Fix playback overlay", "The overlay clips on iPhone SE.")

    folder = ws / ".agentflow" / "tasks" / meta["id"]
    assert folder.is_dir()
    for name in TASK_FILES:
        assert (folder / name).exists(), f"missing {name}"
    assert (folder / "logs").is_dir()
    assert "Fix playback overlay" in (folder / "00_USER_GOAL.md").read_text()


def test_prompts_include_budget_context(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "Add settings toggle", "Add a dark mode toggle.")
    claude_prompt = (ws / ".agentflow" / "tasks" / meta["id"] / "03_CLAUDE_PROMPT.md").read_text()
    assert "Budget context:" in claude_prompt
    assert "Claude usage:" in claude_prompt

    preview = task_service.build_step_preview(ws, meta["id"], "codex_spec")
    assert preview["provider"] == "codex"
    assert "Budget context:" in preview["commandPreview"]


def test_routing_decisions_written(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "Refactor nav", "Tidy the navigation bar.")
    decisions = (ws / ".agentflow" / "tasks" / meta["id"] / "ROUTING_DECISIONS.md").read_text()
    assert "# Routing Decisions" in decisions
    assert "## Budget Context" in decisions
    assert "Mode:" in decisions


def test_task_listing_and_detail(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "A task", "Do the thing.")
    tasks = task_service.list_tasks(ws)
    assert any(t["id"] == meta["id"] for t in tasks)

    detail = task_service.get_task_detail(ws, meta["id"])
    assert detail["task"]["id"] == meta["id"]
    assert len(detail["files"]) == len(TASK_FILES)
    assert set(detail["stepPreviews"]) == set(task_service.STEP_DEFS)
