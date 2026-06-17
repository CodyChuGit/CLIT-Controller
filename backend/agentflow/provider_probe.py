"""Detect installed CLIs (git, gh, codex, antigravity, claude, ollama, omlx)."""

from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

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
        "installCommand": "brew install git",
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
        "installCommand": "brew install gh",
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
        "installCommand": "npm install -g @openai/codex --no-fund --no-audit --cache /tmp/agentflow-npm-cache",
        "loginCommand": "codex login",
        "versionCommand": "codex --version",
        "statusCommand": None,
        # Best-effort curated list (codex has no public models subcommand) — Custom covers the rest.
        "modelOptions": ["gpt-5.5-codex", "gpt-5.5", "gpt-5.1-codex", "gpt-5.1-codex-mini"],
    },
    {
        # Successor to the sunset Gemini CLI. Official installer puts the `agy`
        # binary in ~/.local/bin (source: antigravity.google/download#antigravity-cli).
        "id": "antigravity",
        "displayName": "Google Antigravity CLI",
        "role": "controller/qa",
        "executableNames": ["agy", "antigravity"],
        "authMode": "Google login preferred",
        "usageMode": "daily/quota preferred",
        "preferredUse": "traffic control, QA, broad checks",
        "installHint": "curl -fsSL https://antigravity.google/cli/install.sh | bash  (installs `agy` to ~/.local/bin)",
        "installCommand": "bash -c 'curl -fsSL https://antigravity.google/cli/install.sh | bash'",
        "loginCommand": "agy",
        "versionCommand": "{exe} --version",
        "statusCommand": None,
        # Refreshed from `agy models` on every Check; this is the fallback.
        "modelsCommand": "{exe} models",
        "modelOptions": [
            "Gemini 3.5 Flash (Medium)",
            "Gemini 3.5 Flash (High)",
            "Gemini 3.1 Pro (High)",
            "Claude Sonnet 4.6 (Thinking)",
            "Claude Opus 4.6 (Thinking)",
            "GPT-OSS 120B (Medium)",
        ],
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
        "installCommand": "npm install -g @anthropic-ai/claude-code --no-fund --no-audit --cache /tmp/agentflow-npm-cache",
        "loginCommand": "claude",
        "versionCommand": "claude --version",
        "statusCommand": None,
        "modelOptions": [
            "sonnet",
            "opus",
            "haiku",
            "claude-fable-5",
            "claude-opus-4-8",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        ],
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
        "installCommand": "brew install ollama",
        "loginCommand": None,
        "versionCommand": "ollama --version",
        "statusCommand": None,
    },
    {
        "id": "omlx",
        "displayName": "omlx · Apple MLX (optional)",
        "role": "local models",
        "executableNames": ["omlx", "mlx_lm.server", "mlx_lm.generate", "mlx_lm", "mlx-omni-server"],
        "authMode": "none",
        "usageMode": "free/local",
        "preferredUse": "local LLM server on Apple Silicon — future on-device summarization and cheap routing",
        "installHint": "ensure `omlx` is on your PATH (or: pip install mlx-lm / mlx-omni-server)",
        "installCommand": None,
        "loginCommand": None,
        "versionCommand": "{exe} --version",
        "statusCommand": None,
    },
]

PROVIDER_IDS = [p["id"] for p in PROVIDERS]
AGENT_PROVIDER_IDS = ["codex", "claude", "antigravity"]


def _definition(provider_id: str) -> dict:
    for p in PROVIDERS:
        if p["id"] == provider_id:
            return p
    raise KeyError(f"unknown provider: {provider_id}")


def _load_cache() -> dict:
    return config.read_json(paths.providers_cache_file(), {}) or {}


def _save_cache(cache: dict) -> None:
    config.write_json(paths.providers_cache_file(), cache)


# Common user-bin dirs that may be missing from the backend's PATH
# (the official Antigravity installer targets ~/.local/bin).
EXTRA_BIN_DIRS = [Path.home() / ".local" / "bin", Path.home() / "bin"]


def resolve_executable(name: str) -> Optional[str]:
    """shutil.which plus well-known user bin dirs."""
    found = shutil.which(name)
    if found:
        return found
    for directory in EXTRA_BIN_DIRS:
        candidate = directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def which(provider_id: str) -> Optional[str]:
    for name in _definition(provider_id)["executableNames"]:
        found = resolve_executable(name)
        if found:
            return found
    return None


def _parse_model_lines(text: str) -> list[str]:
    """Parse a CLI's `models` listing: one model name per non-noise line."""
    models = []
    for line in (text or "").splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if not line or len(line) > 80:
            continue
        lower = line.lower()
        if any(noise in lower for noise in ("usage", "error", "login", "available", "command", "http")):
            continue
        models.append(line)
        if len(models) >= 24:
            break
    return models


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
            "installing": is_installing(provider_id),
            "modelOptions": cached.get("modelOptions") or d.get("modelOptions", []),
        }
    )
    return d


def list_providers() -> list[dict]:
    return [base_state(pid) for pid in PROVIDER_IDS]


async def check_provider(provider_id: str) -> dict:
    """Run the real version/status commands and cache the result."""
    d = dict(_definition(provider_id))
    path = which(provider_id)
    # Heterogeneous result dict (strings, bools, None, and later list[str] for
    # modelOptions); annotate as Any-valued so mypy doesn't pin it to the initial
    # literal's value type.
    result: dict[str, Any] = {
        "installed": path is not None,
        "executablePath": path,
        "version": None,
        "status": "missing",
        "lastChecked": now_iso(),
        "lastLog": "",
    }

    if path is not None:
        logs: list[str] = []
        # "{exe}" lets multi-binary providers (e.g. MLX) probe whichever binary was found.
        # Split the template FIRST, then substitute {exe} into the token — the
        # resolved path may contain spaces (e.g. ~/Library/Application Support/…),
        # which a post-substitution .split() would shatter into bad argv tokens
        # and make the probe falsely report the provider broken/missing.
        version_argv = [tok.replace("{exe}", path) for tok in d["versionCommand"].split()]
        rec = await RUNNER.run_and_wait(version_argv, Path.home(), timeout=15, provider=provider_id)
        out = (rec.stdout + rec.stderr).strip()
        logs.append(f"$ {' '.join(version_argv)}\n{out}")
        if rec.exit_code == 0 and out:
            result["version"] = out.splitlines()[0][:120]
            result["status"] = "ok"
        else:
            # Binary exists but doesn't answer --version cleanly (common for
            # mlx_lm.* entry points): installed, version unknown.
            result["status"] = "version_unknown"

        if d.get("statusCommand"):
            rec2 = await RUNNER.run_and_wait(d["statusCommand"].split(), Path.home(), timeout=15, provider=provider_id)
            out2 = (rec2.stdout + rec2.stderr).strip()
            logs.append(f"$ {d['statusCommand']}\n{out2}")
            if provider_id == "gh":
                result["status"] = "ok" if rec2.exit_code == 0 else "needs_login"

        if d.get("modelsCommand"):
            models_argv = [tok.replace("{exe}", path) for tok in d["modelsCommand"].split()]
            rec3 = await RUNNER.run_and_wait(models_argv, Path.home(), timeout=10, provider=provider_id)
            parsed = _parse_model_lines(rec3.stdout)
            if parsed:
                result["modelOptions"] = parsed
                logs.append(f"$ {' '.join(models_argv)}\n{rec3.stdout.strip()[:600]}")

        result["lastLog"] = redact("\n\n".join(logs))[-4000:]

    cache = _load_cache()
    cache[provider_id] = result
    _save_cache(cache)

    add_log_entry(
        "agent-check",
        f"checked {d['displayName']}: {result['status']}" + (f" ({result['version']})" if result["version"] else ""),
        provider=provider_id,
        status="info" if result["status"] in ("ok",) else "warn",
        output=result["lastLog"],
    )

    full = dict(d)
    full.update(result)
    full["installing"] = is_installing(provider_id)
    return full


async def check_all() -> list[dict]:
    out = []
    for pid in PROVIDER_IDS:
        out.append(await check_provider(pid))
    return out


# provider id -> run id of an in-flight one-click install
_installs: dict[str, str] = {}


def is_installing(provider_id: str) -> bool:
    run_id = _installs.get(provider_id)
    if not run_id:
        return False
    record = RUNNER.runs.get(run_id)
    if record is None or record.status != "running":
        _installs.pop(provider_id, None)
        return False
    return True


async def install_provider(provider_id: str) -> dict:
    """One-click install: run the provider's real install command in the background."""
    d = _definition(provider_id)

    if which(provider_id) is not None:
        return {"status": "already_installed", "message": f"{d['displayName']} is already installed."}
    if is_installing(provider_id):
        return {"status": "already_installing", "message": f"{d['displayName']} is already being installed."}

    command = d.get("installCommand")
    if not command:
        return {
            "status": "no_installer",
            "message": f"No one-click installer for {d['displayName']}. {d['installHint']}",
        }

    argv = shlex.split(command)
    if shutil.which(argv[0]) is None:
        return {
            "status": "error",
            "message": f"`{argv[0]}` is not available on this machine — run manually: {command}",
        }

    async def on_complete(record) -> None:
        _installs.pop(provider_id, None)
        refreshed = await check_provider(provider_id)  # refresh cache with the new reality
        ok = record.status == "succeeded" and refreshed["installed"]
        add_log_entry(
            "agent-install",
            f"install {d['displayName']}: {'succeeded' if ok else record.status} "
            f"(exit {record.exit_code}, {(record.duration_ms or 0) / 1000:.0f}s)",
            provider=provider_id,
            status="info" if ok else "error",
            output=(record.stdout + "\n" + record.stderr)[-3000:],
        )

    record, _task = await RUNNER.start(argv, Path.home(), provider=provider_id, step="install", on_complete=on_complete)
    if record.status == "error":
        return {"status": "error", "message": f"Could not start installer: {record.stderr.strip()[:300]}"}

    _installs[provider_id] = record.id
    add_log_entry("agent-install", f"installing {d['displayName']}: $ {command}", provider=provider_id)
    return {"status": "started", "runId": record.id, "command": command}


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
        f'echo "Command Line Interface Terminal Controller — {d["displayName"]} login/setup"\n'
        f'echo "$ {command}"\n'
        f"{command}\n"
        'echo ""\n'
        'echo "Command Line Interface Terminal Controller: command finished. You can close this window."\n'
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
