from agentflow.chat_service import parse_task_directive


def test_parses_well_formed_block():
    text = (
        "Here's my plan.\n\n```agentflow-task\n"
        "title: Fix login crash\n"
        "goal: The login screen crashes on empty email. Add validation and a friendly error.\n"
        "```\nLet me know when to run the spec."
    )
    parsed = parse_task_directive(text)
    assert parsed is not None
    title, goal = parsed
    assert title == "Fix login crash"
    assert goal.startswith("The login screen crashes")


def test_multiline_goal_is_joined():
    text = "```agentflow-task\ntitle: T\ngoal: line one\nline two continues\n```"
    parsed = parse_task_directive(text)
    assert parsed == ("T", "line one line two continues")


def test_no_block_or_incomplete_returns_none():
    assert parse_task_directive("just chatting, no task here") is None
    assert parse_task_directive("```agentflow-task\ntitle: only a title\n```") is None
    assert parse_task_directive("") is None
