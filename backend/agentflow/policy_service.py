"""Command/action policy: classify before anything reaches the process runner.

Three outcomes (docs/orchestrator-backend/02 §Policy Contract):

- ``allow``            — low-risk, workspace-confined reads/checks and agent steps.
- ``require_approval`` — shared-resource or remote-state changes (installs, git push/pull,
                          publish/deploy, commands the user should consciously authorize).
- ``deny``             — shell operators, path traversal, paths outside the workspace, and
                          destructive commands. Denied actions must never run.

This module is the single source of truth. ``chat_service.command_denied`` is kept as a
thin wrapper (it returns a reason only for ``deny``) so existing callers/tests are
unaffected, while new callers can ask for the full three-way classification.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ALLOW = "allow"
REQUIRE_APPROVAL = "require_approval"
DENY = "deny"

# Hard denials regardless of args.
_BLOCKED_BINARIES = {
    "sudo",
    "su",
    "sh",
    "bash",
    "zsh",
    "fish",
    "env",
    "xargs",
    "shutdown",
    "reboot",
    "halt",
    "mkfs",
    "dd",
}
_SHELL_OPERATORS = ("|", ">", "<", ";", "&&", "||", "`", "$(", "&")

# Interpreters that can execute arbitrary inline code, escaping argument/workspace
# analysis entirely (e.g. `node -e "...fs.writeFileSync('/etc/...')"`).
_INTERPRETERS = {"python", "python3", "node", "nodejs", "deno", "ruby", "perl", "php", "bun", "rscript"}
# Inline-eval flags across these interpreters: -e/-c/-r (eval), -p (print-eval).
# Deliberately omits python's -E (ignore-env, not eval) to avoid false positives.
_EVAL_FLAGS = {"-e", "-c", "-r", "-p", "--eval", "--print"}

# Actions that touch shared/remote state — allowed only with explicit approval.
_APPROVAL_BINARIES = {
    "brew",
    "pip",
    "pip3",
    "docker",
    "kubectl",
    "terraform",
    "vercel",
    "netlify",
    "heroku",
    "flyctl",
    "fly",
}
_GIT_REMOTE_SUBCMDS = {"push", "pull", "fetch", "clone", "remote", "submodule"}
_INSTALL_SUBCMDS = {"install", "add", "ci", "uninstall", "remove", "update", "upgrade", "publish", "link", "create"}
_DEPLOY_SUBCMDS = {"deploy", "publish", "release"}


@dataclass(frozen=True)
class PolicyResult:
    decision: str  # allow | require_approval | deny
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.decision == ALLOW

    @property
    def denied(self) -> bool:
        return self.decision == DENY


def _outside_workspace(tokens: list[str], workspace: Path) -> Optional[str]:
    ws = str(workspace.resolve())
    for t in tokens[1:]:
        arg = t.split("=", 1)[1] if t.startswith("-") and "=" in t else t
        if ".." in arg.split("/"):
            return "path traversal (`..`) is not allowed"
        if arg.startswith(("/", "~")) and not str(Path(arg).expanduser().resolve()).startswith(ws):
            return f"`{arg}` is outside the workspace"
    return None


def classify_action(
    command: str,
    workspace: Optional[Path] = None,
    *,
    source: str = "orchestrator",
    provider: Optional[str] = None,
    task_id: Optional[str] = None,
    mode: str = "balanced",
) -> PolicyResult:
    """Classify a single plain command. ``command`` is one command (no shell), as a
    string; it is parsed with shlex and never interpolated into a shell."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return PolicyResult(DENY, "unparseable quoting")
    if not tokens:
        return PolicyResult(DENY, "empty command")

    # --- deny: shell operators (check raw string, operators may be glued to tokens) ---
    if any(op in command for op in _SHELL_OPERATORS):
        return PolicyResult(DENY, "shell operators are not supported — one plain command only")

    binary = tokens[0]
    sub = tokens[1] if len(tokens) > 1 else ""

    # `FOO=bar cmd` — a var-assignment prefix hides the real binary from
    # classification (the real command is tokens[1]); refuse it.
    if "=" in binary:
        return PolicyResult(DENY, "environment-variable prefixes are not supported — one plain command only")

    if binary in _BLOCKED_BINARIES:
        return PolicyResult(DENY, f"`{binary}` is not allowed for direct execution")

    # Interpreters running inline code (`python -c`, `node -e`, …) bypass all
    # argument and workspace analysis — that's arbitrary code execution.
    if binary in _INTERPRETERS and any(t in _EVAL_FLAGS for t in tokens[1:]):
        return PolicyResult(DENY, f"inline code execution (`{binary} -e/-c`) is not allowed")

    # destructive recursive delete at a filesystem root
    if (
        binary == "rm"
        and any(t.startswith("-") and "r" in t and "f" in t for t in tokens)
        and any(t == "/" or t.startswith("/ ") for t in tokens)
    ):
        return PolicyResult(DENY, "refusing recursive force-delete on /")

    # --- deny: workspace confinement ---
    if workspace is not None:
        outside = _outside_workspace(tokens, workspace)
        if outside:
            return PolicyResult(DENY, outside)

    # --- require approval: shared-resource / remote-state changes ---
    if binary in _APPROVAL_BINARIES:
        return PolicyResult(REQUIRE_APPROVAL, f"`{binary}` changes shared/system state — approval required")
    if binary == "git" and sub in _GIT_REMOTE_SUBCMDS:
        return PolicyResult(REQUIRE_APPROVAL, f"`git {sub}` touches the remote — approval required")
    if binary == "gh":
        return PolicyResult(REQUIRE_APPROVAL, "GitHub CLI changes remote state — approval required")
    if binary in {"npm", "pnpm", "yarn", "bun"} and sub in _INSTALL_SUBCMDS:
        return PolicyResult(REQUIRE_APPROVAL, f"`{binary} {sub}` modifies dependencies — approval required")
    if sub in _DEPLOY_SUBCMDS:
        return PolicyResult(REQUIRE_APPROVAL, f"`{binary} {sub}` deploys/publishes — approval required")

    # --- everything else inside the workspace is allowed ---
    return PolicyResult(ALLOW)


def deny_reason(command: str, workspace: Optional[Path] = None) -> Optional[str]:
    """Backward-compatible helper: a reason string only for hard denials (``deny``).

    ``require_approval`` commands (git push, npm install, …) return ``None`` here so the
    legacy denylist contract — and its tests — keep their exact meaning.
    """
    result = classify_action(command, workspace)
    return result.reason if result.denied else None
