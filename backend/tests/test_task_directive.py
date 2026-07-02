from agentflow.chat_directives import parse_queue_directive, parse_task_directive
from agentflow.task_service import FULL_SEQUENCE


def test_parses_well_formed_block():
    text = (
        "Here's my plan.\n\n```agentflow-task\n"
        "title: Fix login crash\n"
        "goal: The login screen crashes on empty email. Add validation and a friendly error.\n"
        "```\nLet me know when to run the spec."
    )
    parsed = parse_task_directive(text)
    assert parsed is not None
    title, goal, queue_steps = parsed
    assert title == "Fix login crash"
    assert goal.startswith("The login screen crashes")
    assert queue_steps is None


def test_multiline_goal_is_joined():
    text = "```agentflow-task\ntitle: T\ngoal: line one\nline two continues\n```"
    assert parse_task_directive(text) == ("T", "line one line two continues", None)


def test_no_block_or_incomplete_returns_none():
    assert parse_task_directive("just chatting, no task here") is None
    assert parse_task_directive("```agentflow-task\ntitle: only a title\n```") is None
    assert parse_task_directive("") is None


def test_task_block_with_queue_full():
    text = "```agentflow-task\ntitle: T\ngoal: G\nqueue: full\n```"
    parsed = parse_task_directive(text)
    assert parsed is not None
    assert parsed[2] == list(FULL_SEQUENCE)


def test_task_block_with_queue_list_and_invalid():
    ok = parse_task_directive("```agentflow-task\ntitle: T\ngoal: G\nqueue: codex_spec, gemini_qa\n```")
    assert ok is not None and ok[2] == ["codex_spec", "gemini_qa"]
    bad = parse_task_directive("```agentflow-task\ntitle: T\ngoal: G\nqueue: warp_drive\n```")
    assert bad is not None and bad[2] is None  # invalid steps → create task, queue nothing


def test_queue_directive_parses_and_validates():
    text = "```agentflow-queue\ntask: latest\nsteps: claude_implement, gemini_qa\n```"
    assert parse_queue_directive(text) == ("latest", ["claude_implement", "gemini_qa"])
    assert parse_queue_directive("```agentflow-queue\ntask: x\nsteps: bogus\n```") is None
    assert parse_queue_directive("no block") is None


def test_done_and_needs_user_directives():
    from agentflow.chat_directives import parse_done_directive, parse_needs_user_directive

    assert parse_done_directive("```agentflow-done\nreason: QA passed, review clean\n```") == "QA passed, review clean"
    assert parse_done_directive("nothing here") is None
    assert parse_needs_user_directive("```agentflow-needs-user\nreason: budget call\n```") == "budget call"
    assert parse_needs_user_directive("```agentflow-done\nreason: x\n```") is None


def test_run_directives_parse_and_cap():
    from agentflow.chat_directives import parse_run_directives

    text = "Starting it now.\n```agentflow-run\ncommand: npm run dev\n```\n```agentflow-run\ncommand: git push\n```"
    assert parse_run_directives(text) == ["npm run dev", "git push"]
    many = "\n".join("```agentflow-run\ncommand: echo %d\n```" % i for i in range(5))
    assert len(parse_run_directives(many)) == 3  # capped
    assert parse_run_directives("no blocks") == []


def test_command_denylist():
    from agentflow.chat_service import command_denied

    assert command_denied("npm run dev") is None
    assert command_denied("git push") is None
    assert command_denied("sudo rm -rf /") is not None
    assert command_denied("bash -c 'echo hi'") is not None
    assert command_denied("npm test && rm -rf /") is not None  # shell operators refused
    assert command_denied("cat foo > bar") is not None


def test_command_workspace_confinement(tmp_path):
    from agentflow.chat_service import command_denied

    assert command_denied("npm run dev", tmp_path) is None
    assert command_denied(f"cat {tmp_path}/notes.txt", tmp_path) is None
    assert command_denied("cat /etc/passwd", tmp_path) is not None
    assert command_denied("cat ~/.ssh/id_rsa", tmp_path) is not None
    assert command_denied("cat ../secrets.txt", tmp_path) is not None
