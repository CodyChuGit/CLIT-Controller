"""Helpers for turning provider command templates into executable argv."""

from __future__ import annotations

import shlex
from typing import Optional

from .provider_probe import resolve_executable


def build_argv(template: str, prompt: str, model: Optional[str] = None) -> list[str]:
    tokens = shlex.split(template)
    argv: list[str] = []
    replaced = False
    for token in tokens:
        if token == "{model}":
            if model:
                argv.extend(["--model", model])
        elif "{prompt}" in token:
            argv.append(token.replace("{prompt}", prompt))
            replaced = True
        else:
            argv.append(token)
    if not replaced:
        argv.append(prompt)

    resolved = resolve_executable(argv[0])
    if resolved:
        argv[0] = resolved
    return argv


def provider_busy_result(provider: str, run_id: str, step: Optional[str]) -> dict:
    request = step or "request"
    return {
        "status": "provider_busy",
        "provider": provider,
        "runId": run_id,
        "message": (
            f"`{provider}` is already running `{request}`. "
            f"Wait for it to finish or stop it before starting another `{provider}` request."
        ),
    }
