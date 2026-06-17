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
        "codex (specs/plans/reviews), claude (implementation/bug fixing), antigravity (QA/broad checks).\n\n"
        f"{task_state}\n\n"
        f"Just happened: {trigger}\n\n"
        f"{tail}"
        "Reply with AT MOST two sentences of reasoning, then your decision(s).\n\n"
        "PREFERRED — emit ONE fenced `agentflow` block of structured JSON decisions "
        "(version 1; kinds: queue/run/done/needs_user):\n"
        "```agentflow\n"
        '{"version":"1","decisions":[{"kind":"queue","taskRef":"<task id>","steps":["codex_spec"]},'
        '{"kind":"run","command":"npm test"}]}\n'
        "```\n"
        "(steps come from: codex_spec, claude_implement, gemini_qa, codex_review, claude_fix; "
        '`done` and `needs_user` take {"reason":"<one line>"}.)\n\n'
        "Or use ONE of the legacy single blocks below (agentflow-run may accompany another block):\n\n"
        "Queue the next step(s):\n"
        "```agentflow-queue\n"
        "task: <task id>\n"
        "steps: <comma list from: codex_spec, claude_implement, gemini_qa, codex_review, claude_fix>\n"
        "```\n\n"
        "Run a simple command directly yourself (tests, builds, git, dev server — one plain command, "
        "no pipes) instead of spending an agent on it:\n"
        "```agentflow-run\n"
        "command: npm test\n"
        "```\n\n"
        "The task is complete (or further agent spend isn't worth it):\n"
        "```agentflow-done\n"
        "reason: <one line>\n"
        "```\n\n"
        "A human decision is required:\n"
        "```agentflow-needs-user\n"
        "reason: <one line>\n"
        "```"
    )


def orchestrator_chat_prompt(usage: dict, workspace_summary: str, transcript: str, message: str) -> str:
    """Prompt for the persistent controller chat. Compact by design."""
    convo = f"Conversation so far:\n{transcript}\n\n" if transcript else ""
    return (
        f"{budget_context_header(usage)}\n\n"
        "You are the controller model for Command Line Interface Terminal Controller "
        "(CLIT Controller IDE), a local cockpit that routes coding work "
        "between CLI agents: codex (specs/plans/reviews), claude (implementation/bug fixing), "
        "antigravity (QA/broad checks; successor to the sunset Gemini CLI), plus free local git checks.\n\n"
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
        "You can create CLITC tasks AND queue work to the agents — the system executes the queue "
        "automatically, cueing one step per agent at a time, in order.\n\n"
        "PREFERRED — emit ONE fenced `agentflow` block of structured JSON decisions "
        "(version 1; kinds: task/queue/run):\n"
        "```agentflow\n"
        '{"version":"1","decisions":[{"kind":"task","title":"<short imperative>","goal":"<compact goal>",'
        '"queueSteps":["codex_spec"]},{"kind":"run","command":"npm run dev"}]}\n'
        "```\n"
        "(`queueSteps`/`steps` come from: codex_spec, claude_implement, gemini_qa, codex_review, claude_fix, "
        'or ["full"]; `queue` takes {"taskRef":"latest","steps":[...]}.)\n\n'
        "Or use the legacy fenced blocks below.\n\n"
        "Create a task (optionally queueing its steps immediately):\n"
        "```agentflow-task\n"
        "title: <short imperative title>\n"
        "goal: <compact goal description>\n"
        "queue: full\n"
        "```\n"
        "(`queue:` is optional, but DEFAULT to starting a task with `codex_spec` — that is the planning "
        "step, and codex owns specs and plans. Queue only that first step; CLITC reports back after "
        "it finishes so you decide the next one from the actual spec. Skip straight to `claude_implement` "
        "ONLY for a truly trivial edit (a one-liner, a rename, a copy tweak) that genuinely needs no plan. "
        "`full` queues the whole standard pipeline — use it when you want the fixed sequence.)\n\n"
        "Queue steps for an existing task:\n"
        "```agentflow-queue\n"
        "task: <task id, or `latest`>\n"
        "steps: claude_implement, gemini_qa\n"
        "```\n"
        "Valid steps: codex_spec, claude_implement, gemini_qa, codex_review, claude_fix. "
        "Steps within a task run in queue order; a failed step pauses that task's queue.\n\n"
        "For SIMPLE operational work — start the dev server, git add/commit/push, install deps, run "
        "tests or builds — do NOT create a task or involve other agents. Just run it directly:\n"
        "```agentflow-run\n"
        "command: npm run dev\n"
        "```\n"
        "One plain command per block (no pipes/redirection), up to three blocks; the system executes "
        "them in the workspace and reports the result here.\n\n"
        "Beyond these blocks you advise; the system runs the agents.\n\n"
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
