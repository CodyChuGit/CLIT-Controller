"""All agent prompt templates. Every prompt starts with the budget context header."""

from __future__ import annotations

from . import controller_protocol, ponytail
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
    # Ponytail rides in every step prompt (output-side token reduction — the
    # agents write less code and shorter docs). Headroom compresses the input
    # side; together they are the token-management strategy (Pillar 1).
    pony = ponytail.block()
    return (
        f"{budget_context_header(usage)}\n\n"
        f"Task folder: {task_rel_dir}/\n"
        "All numbered markdown files mentioned below live in the task folder.\n\n"
        f"{body.strip()}"
        + (f"\n\n{pony}" if pony else "")
        + "\n\nReading dependency source: run `opensrc path <pkg>` to fetch + cache any open-source "
        "package's real source and get a local path (e.g. `opensrc path zod`, "
        "`opensrc path pypi:requests`, `opensrc path owner/repo`), then read files under it."
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
        """
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


def orchestrator_consult_prompt(usage: dict, task_state: str, trigger: str, output_tail: str) -> str:
    """After a step finishes, the system asks the controller what to do next."""
    tail = f"Output from that step (tail):\n{output_tail}\n\n" if output_tail else ""
    return (
        f"{budget_context_header(usage)}\n\n"
        "You are the controller model for Command Line Interface Terminal Controller "
        "(CLIT Controller IDE), supervising a task whose step just "
        "finished. Decide the next action based on what the task ACTUALLY needs — you are not bound "
        "to a fixed pipeline. Skip steps that add no value; pick the agent that fits the work: "
        "codex (specs/plans/reviews), claude (implementation/bug fixing), antigravity (tool runner: "
        "QA checks, local file access, running dev servers/commands, monitoring — never routing).\n\n"
        f"{task_state}\n\n"
        f"Just happened: {trigger}\n\n"
        f"{tail}"
        "Reply with AT MOST two sentences of human-readable reasoning, then your decision.\n"
        "For this consult the useful actions are queue_steps, run_command, complete_task, "
        "request_user, or answer.\n\n" + controller_protocol.result_contract_prompt()
    )


def orchestrator_chat_prompt(usage: dict, workspace_summary: str, transcript: str, message: str) -> str:
    """Prompt for the persistent controller chat. Compact by design."""
    convo = f"Conversation so far:\n{transcript}\n\n" if transcript else ""
    return (
        f"{budget_context_header(usage)}\n\n"
        "You are the controller model for Command Line Interface Terminal Controller "
        "(CLIT Controller IDE), a local cockpit that routes coding work "
        "between CLI agents: codex (specs/plans/reviews), claude (implementation/bug fixing), "
        "antigravity (the tool runner: tool calling, local file access, running QA/dev "
        "servers/commands, activity monitoring; successor to the sunset Gemini CLI), "
        "plus free local git checks.\n\n"
        f"{workspace_summary}\n\n"
        "Your job: help the user plan work, decide routing, draft task goals, and interpret agent results. "
        "Be compact and concrete — prefer specific next actions in CLITC (create a task, run a step "
        "with a given agent, run a local git check) over long prose. Respect the budget context above "
        "when recommending providers.\n\n"
        "FORMAT for a person, not a terminal: lead with a one-sentence summary of what you did or "
        "recommend; then at most a few short bullets. Use a small markdown table when comparing options "
        "or summarizing step results (| Step | Agent | Result |). Refer to pipeline steps by their ids "
        "(codex_spec, claude_implement, gemini_qa, codex_review, claude_fix) — the UI renders them as "
        "colored chips. Keep replies under ~120 words unless the user asks for depth. No headings "
        "larger than ###, no walls of text.\n\n"
        + (
            (ponytail.block("lite") + " Apply this ladder to the task goals and plans you draft.\n\n")
            if ponytail.level() != "off"
            else ""
        )
        + "You can create CLITC tasks AND queue work to the agents — the system executes the queue "
        "automatically, cueing one step per agent at a time, in order. Default to starting a task with "
        "`codex_spec` (the planning step) and queueing only that first step; CLITC reports back after it "
        "finishes so you decide the next one. Skip straight to `claude_implement` only for a truly trivial "
        "edit. For SIMPLE operational work (dev server, git, install, tests/builds) prefer run_command over "
        "involving agents.\n\n" + controller_protocol.result_contract_prompt() + "\n\n"
        f"{convo}"
        f"user: {message}\n\n"
        "Reply as the assistant."
    )


def direct_chat_prompt(provider: str, transcript: str, message: str) -> str:
    """Direct line to one agent CLI — no traffic-control framing, no directives."""
    convo = f"Conversation so far:\n{transcript}\n\n" if transcript else ""
    return (
        f"You are `{provider}` in a direct chat inside Command Line Interface Terminal Controller "
        "(CLIT Controller IDE). The user is talking to you "
        "one-on-one — there is no controller, no task pipeline, and no agentflow-* directive blocks. "
        "Your working directory is the user's workspace; stay inside it. You may read files, and edit "
        "them when the user asks you to.\n\n"
        "Reply in compact markdown: lead with the answer, keep it under ~150 words unless the user "
        "asks for depth.\n\n"
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
