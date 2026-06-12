"""All agent prompt templates. Every prompt starts with the budget context header."""

from __future__ import annotations

from .routing_service import budget_context_header

TASK_FILES = [
    "00_USER_GOAL.md",
    "01_CODEX_SPEC.md",
    "02_CODEX_IMPLEMENTATION_PLAN.md",
    "03_CLAUDE_PROMPT.md",
    "04_CLAUDE_IMPLEMENTATION_SUMMARY.md",
    "05_QA_RESULTS.md",
    "06_BUGS_FOR_CLAUDE.md",
    "07_CODEX_FINAL_REVIEW.md",
    "ROUTING_DECISIONS.md",
]


def _compose(usage: dict, task_rel_dir: str, body: str) -> str:
    return (
        f"{budget_context_header(usage)}\n\n"
        f"Task folder: {task_rel_dir}/\n"
        "All numbered markdown files mentioned below live in the task folder.\n\n"
        f"{body.strip()}"
    )


def codex_spec_prompt(usage: dict, task_rel_dir: str) -> str:
    return _compose(
        usage,
        task_rel_dir,
        f"""
Read {task_rel_dir}/00_USER_GOAL.md.
Write 01_CODEX_SPEC.md and 02_CODEX_IMPLEMENTATION_PLAN.md.
Do not edit production code.
Keep the plan compact and specific.
Optimize for minimizing Claude implementation time and usage.
""",
    )


def claude_implement_prompt(usage: dict, task_rel_dir: str) -> str:
    return _compose(
        usage,
        task_rel_dir,
        f"""
Read {task_rel_dir}/01_CODEX_SPEC.md and {task_rel_dir}/02_CODEX_IMPLEMENTATION_PLAN.md.
Implement only the requested production changes.
Do not refactor unrelated files.
Do not write tests unless explicitly asked.
After implementation, write 04_CLAUDE_IMPLEMENTATION_SUMMARY.md.
Keep changes minimal.
""",
    )


def qa_prompt(usage: dict, task_rel_dir: str) -> str:
    return _compose(
        usage,
        task_rel_dir,
        f"""
Read the current git diff and {task_rel_dir}/04_CLAUDE_IMPLEMENTATION_SUMMARY.md.
Run or write tests if appropriate.
Do not modify production code unless explicitly approved.
Write results to 05_QA_RESULTS.md.
If production bugs are found, write 06_BUGS_FOR_CLAUDE.md.
""",
    )


def codex_review_prompt(usage: dict, task_rel_dir: str) -> str:
    return _compose(
        usage,
        task_rel_dir,
        f"""
Review current git diff and all files in the task folder.
Write 07_CODEX_FINAL_REVIEW.md.
Do not edit production code.
Focus on correctness, overreach, risk, and whether the implementation matched the spec.
""",
    )


def claude_fix_prompt(usage: dict, task_rel_dir: str) -> str:
    return _compose(
        usage,
        task_rel_dir,
        f"""
Read {task_rel_dir}/06_BUGS_FOR_CLAUDE.md.
Fix only the listed production bugs.
Do not refactor unrelated code.
After fixing, append to 04_CLAUDE_IMPLEMENTATION_SUMMARY.md.
""",
    )


def orchestrator_chat_prompt(usage: dict, workspace_summary: str, transcript: str, message: str) -> str:
    """Prompt for the persistent orchestrator chat. Compact by design."""
    convo = f"Conversation so far:\n{transcript}\n\n" if transcript else ""
    return (
        f"{budget_context_header(usage)}\n\n"
        "You are the orchestration model for AgentFlow Studio, a local cockpit that routes coding work "
        "between CLI agents: codex (specs/plans/reviews), claude (implementation/bug fixing), "
        "antigravity (QA/broad checks; successor to the sunset Gemini CLI), plus free local git checks.\n\n"
        f"{workspace_summary}\n\n"
        "Your job: help the user plan work, decide routing, draft task goals, and interpret agent results. "
        "Be compact and concrete — prefer specific next actions in AgentFlow (create a task, run a step "
        "with a given agent, run a local git check) over long prose. Respect the budget context above "
        "when recommending providers.\n\n"
        "You can create AgentFlow tasks. When the user asks for one (or the plan clearly needs one), "
        "include exactly one fenced block in your reply:\n"
        "```agentflow-task\n"
        "title: <short imperative title>\n"
        "goal: <compact goal description>\n"
        "```\n"
        "AgentFlow detects the block and creates the task folder with all handoff files automatically. "
        "Apart from task creation you advise; you do not run anything yourself.\n\n"
        f"{convo}"
        f"user: {message}\n\n"
        "Reply as the assistant."
    )


STEP_PROMPTS = {
    "codex_spec": codex_spec_prompt,
    "claude_implement": claude_implement_prompt,
    "gemini_qa": qa_prompt,
    "codex_review": codex_review_prompt,
    "claude_fix": claude_fix_prompt,
}


def initial_task_files(title: str, goal: str, claude_prompt: str) -> dict[str, str]:
    """Initial contents for every markdown handoff file in a new task folder."""
    pending = "_Pending — this file will be written by the {who} step._\n"
    return {
        "00_USER_GOAL.md": f"# User Goal\n\n## {title}\n\n{goal.strip()}\n",
        "01_CODEX_SPEC.md": "# Codex Spec\n\n" + pending.format(who="`codex_spec`"),
        "02_CODEX_IMPLEMENTATION_PLAN.md": "# Codex Implementation Plan\n\n" + pending.format(who="`codex_spec`"),
        "03_CLAUDE_PROMPT.md": "# Claude Prompt\n\n```text\n" + claude_prompt + "\n```\n",
        "04_CLAUDE_IMPLEMENTATION_SUMMARY.md": "# Claude Implementation Summary\n\n"
        + pending.format(who="`claude_implement`"),
        "05_QA_RESULTS.md": "# QA Results\n\n" + pending.format(who="`gemini_qa`"),
        "06_BUGS_FOR_CLAUDE.md": "# Bugs for Claude\n\n_None reported yet._\n",
        "07_CODEX_FINAL_REVIEW.md": "# Codex Final Review\n\n" + pending.format(who="`codex_review`"),
    }
