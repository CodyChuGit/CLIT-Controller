"""Detect installed CLIs (git, gh, codex, gemini, antigravity, claude, ollama)."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Optional

from . import config, paths
from .process_runner import RUNNER, add_log_entry, now_iso
from .redaction import redact

PROVIDERS: list[dict] = [
    {
        "id": "git",
        "displayName": "Git",
        "role": "local version control",
        "executableNames": ["git"],
        "authMode": "none",
        "usageMode": "free/local",
        "preferredUse": "local version control",
        "installHint": "xcode-select --install  (or: brew install git)",
        "loginCommand": None,
        "versionCommand": "git --version",
        "statusCommand": None,
    },
    {
        "id": "gh",
        "displayName": "GitHub CLI",
        "role": "GitHub operations",
        "executableNames": ["gh"],
        "authMode": "GitHub login (gh auth login)",
        "usageMode": "free/local",
        "preferredUse": "PRs, issues, repo operations",
        "installHint": "brew install gh",
        "loginCommand": "gh auth login",
        "versionCommand": "gh --version",
        "statusCommand": "gh auth status",
    },
    {
        "id": "codex",
        "displayName": "OpenAI Codex CLI",
        "role": "pm",
        "executableNames": ["codex"],
        "authMode": "subscription login preferred",
        "usageMode": "plan/quota preferred",
        "preferredUse": "specs, plans, reviews",
        "installHint": "npm install -g @openai/codex",
        "loginCommand": "codex login",
        "versionCommand": "codex --version",
        "statusCommand": None,
    },
    {
        "id": "gemini",
        "displayName": "Google Gemini CLI",
        "role": "orchestrator/qa",
        "executableNames": ["gemini"],
        "authMode": "Google login preferred",
        "usageMode": "daily/quota preferred",
        "preferredUse": "orchestration, QA, broad checks",
        "installHint": "npm install -g @google/gemini-cli",
        "loginCommand": "gemini",
        "versionCommand": "gemini --version",
        "statusCommand": None,
    },
    {
        "id": "antigravity",
        "displayName": "Google Antigravity",
        "role": "orchestrator",
        "executableNames": ["antigravity"],
        "authMode": "Google login preferred",
        "usageMode": "daily/quota preferred",
        "preferredUse": "orchestration, UI checks",
        "installHint": "Install Google Antigravity and ensure `antigravity` is on your PATH",
        "loginCommand": "antigravity",
        "versionCommand": "antigravity --version",
        "statusCommand": None,
    },
    {
        "id": "claude",
        "displayName": "Claude Code",
        "role": "engineer",
        "executableNames": ["claude"],
        "authMode": "Claude Pro/Max login preferred",
        "usageMode": "plan/quota preferred",
        "preferredUse": "implementation and bug fixing only",
        "installHint": "npm install -g @anthropic-ai/claude-code",
        "loginCommand": "claude",
        "versionCommand": "claude --version",
        "statusCommand": None,
    },
    {
        "id": "ollama",
        "displayName": "Ollama (optional)",
        "role": "local models",
        "executableNames": ["ollama"],
        "authMode": "none",
        "usageMode": "free/local",
        "preferredUse": "future local summarization and cheap routing",
        "installHint": "brew install ollama",
        "loginCommand": None,
        "versionCommand": "ollama --version",
        "statusCommand": None,
    },
]

PROVIDER_IDS = [p["id"] for p in PROVIDERS]
AGENT_PROVIDER_IDS = ["codex", "claude", "gemini", "antigravity"]


def _definition(provider_id: str) -> dict:
    for p in PROVIDERS:
        if p["id"] == provider_id:
            return p
    raise KeyError(f"unknown provider: {provider_id}")


def _load_cache() -> dict:
    return config.read_json(paths.providers_cache_file(), {}) or {}


def _save_cache(cache: dict) -> None:
    config.write_json(paths.providers_cache_file(), cache)


def which(provider_id: str) -> Optional[str]:
    for name in _definition(provider_id)["executableNames"]:
        found = shutil.which(name)
        if found:
            return found
    return None


def base_state(provider_id: str) -> dict:
    """Static definition + cached check results (no subprocess calls)."""
    d = dict(_definition(provider_id))
    cached = _load_cache().get(provider_id, {})
    d.update(
        {
            "installed": cached.get("installed", which(provider_id) is not None),
            "executablePath": cached.get("executablePath", which(provider_id)),
            "version": cached.get("version"),
            "status": cached.get("status", "unchecked"),
            "lastChecked": cached.get("lastChecked"),
            "lastLog": cached.get("lastLog", ""),
        }
    )
    return d


def list_providers() -> list[dict]:
    return [base_state(pid) for pid in PROVIDER_IDS]


async def check_provider(provider_id: str) -> dict:
    """Run the real version/status commands and cache the result."""
    d = dict(_definition(provider_id))
    path = which(provider_id)
    result = {
        "installed": path is not None,
        "executablePath": path,
        "version": None,
        "status": "missing",
        "lastChecked": now_iso(),
        "lastLog": "",
    }

    if path is not None:
        logs: list[str] = []
        version_argv = d["versionCommand"].split()
        rec = await RUNNER.run_and_wait(version_argv, Path.home(), timeout=15, provider=provider_id)
        out = (rec.stdout + rec.stderr).strip()
        logs.append(f"$ {d['versionCommand']}\n{out}")
        if rec.exit_code == 0 and out:
            result["version"] = out.splitlines()[0][:120]
            result["status"] = "ok"
        else:
            result["status"] = "error"

        if d.get("statusCommand"):
            rec2 = await RUNNER.run_and_wait(d["statusCommand"].split(), Path.home(), timeout=15, provider=provider_id)
            out2 = (rec2.stdout + rec2.stderr).strip()
            logs.append(f"$ {d['statusCommand']}\n{out2}")
            if provider_id == "gh":
                result["status"] = "ok" if rec2.exit_code == 0 else "needs_login"

        result["lastLog"] = redact("\n\n".join(logs))[-4000:]

    cache = _load_cache()
    cache[provider_id] = result
    _save_cache(cache)

    add_log_entry(
        "agent-check",
        f"checked {d['displayName']}: {result['status']}"
        + (f" ({result['version']})" if result["version"] else ""),
        provider=provider_id,
        status="info" if result["status"] in ("ok",) else "warn",
        output=result["lastLog"],
    )

    full = dict(d)
    full.update(result)
    return full


async def check_all() -> list[dict]:
    out = []
    for pid in PROVIDER_IDS:
        out.append(await check_provider(pid))
    return out


def login_provider(provider_id: str, workspace: Optional[Path]) -> dict:
    """Open the login/setup command in Terminal on macOS, else return it for manual use."""
    d = _definition(provider_id)
    command = d.get("loginCommand")
    if not command:
        return {"launched": False, "command": None, "message": f"{d['displayName']} does not need a login step."}

    if sys.platform != "darwin":
        return {
            "launched": False,
            "command": command,
            "message": f"Run this in your terminal: {command}",
        }

    cwd = str(workspace) if workspace else str(Path.home())
    script_dir = paths.login_scripts_dir()
    script_dir.mkdir(parents=True, exist_ok=True)
    script = script_dir / f"login-{provider_id}.command"
    script.write_text(
        "#!/bin/zsh\n"
        f"cd {subprocess.list2cmdline([cwd])}\n"
        f'echo "AgentFlow Studio — {d["displayName"]} login/setup"\n'
        f'echo "$ {command}"\n'
        f"{command}\n"
        'echo ""\n'
        'echo "AgentFlow: command finished. You can close this window."\n'
        "exec /bin/zsh -i\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    try:
        subprocess.Popen(["open", "-a", "Terminal", str(script)], env=os.environ.copy())
        launched = True
        message = f"Opened Terminal running: {command}"
    except OSError as exc:
        launched = False
        message = f"Could not open Terminal ({exc}). Run manually: {command}"

    add_log_entry("agent-login", f"login/setup for {d['displayName']}: {message}", provider=provider_id)
    return {"launched": launched, "command": command, "message": message}
