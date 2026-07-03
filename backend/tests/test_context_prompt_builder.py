"""Context intelligence — prompt builder: the order-lock test and rendering."""

from __future__ import annotations

from agentflow.context_intelligence import prompt_builder
from agentflow.context_intelligence.types import (
    BehaviorPolicy,
    ContextPackage,
    ContextSelection,
    FileContext,
    GitContext,
    LogContext,
    RepoMap,
    RepoMapEntry,
    SessionDigest,
    UserTask,
)


def _package() -> ContextPackage:
    return ContextPackage(
        task=UserTask(text="fix the ranker"),
        policy=BehaviorPolicy(level="full", block="Ponytail discipline block"),
        repoMap=RepoMap(entries=[RepoMapEntry(path="a.py", size=10, language="python", symbols=["rank"])]),
        selection=ContextSelection(
            selected=[FileContext(path="a.py", excerpt="def rank(): ...", reasons=["task terms in path: rank"])]
        ),
        git=GitContext(isRepo=True, branch="main", changedFiles=["a.py"], diff="+def rank"),
        logs=LogContext(summary="Run r1 failed"),
        digest=SessionDigest(text="Recent controller chat:\nuser: hi"),
        projectRules="follow CLAUDE.md",
    )


def test_section_order_is_locked():
    # This test MUST fail if the section order ever changes.
    assert prompt_builder.SECTION_ORDER == (
        "system_instructions",
        "clitc_rules",
        "behavior_policy",
        "project_rules",
        "session_digest",
        "repo_map",
        "selected_files",
        "git_diff",
        "log_context",
        "user_task",
    )
    built = prompt_builder.build_prompt_package(_package())
    assert tuple(s.name for s in built.sections) == prompt_builder.SECTION_ORDER


def test_rendered_text_keeps_relative_order():
    built = prompt_builder.build_prompt_package(_package())
    positions = [built.text.index(f"## {name}") for name in prompt_builder.SECTION_ORDER]
    assert positions == sorted(positions)
    assert built.text.rstrip().endswith("USER TASK:\nfix the ranker")


def test_empty_sections_render_nothing_but_keep_order():
    package = _package()
    package.policy = BehaviorPolicy(level="off", block="")
    package.projectRules = ""
    built = prompt_builder.build_prompt_package(package)
    assert "## behavior_policy" not in built.text
    assert "## project_rules" not in built.text
    # ...but the typed sections still carry every slot, in order.
    assert tuple(s.name for s in built.sections) == prompt_builder.SECTION_ORDER


def test_selected_files_show_scores_and_reasons():
    built = prompt_builder.build_prompt_package(_package())
    assert "### a.py" in built.text and "task terms in path: rank" in built.text
