"""Session/project memory: a deterministic digest of existing state.

There is no memory store — this truncates and extracts from what already
persists: recent controller chat (``chat_service.load_chat``) and the newest
task state (``task_service``). No new persistence layer.
"""

from __future__ import annotations

from pathlib import Path

from .. import chat_service, task_service
from .types import MemoryContext, SessionDigest

MAX_CHAT_MESSAGES = 8
CHAT_CLIP_CHARS = 240
MAX_TASKS = 2


def build_memory_context(workspace_path: Path) -> MemoryContext:
    chat_lines: list[str] = []
    data = chat_service.load_chat(workspace_path)
    for message in data.get("messages", [])[-MAX_CHAT_MESSAGES:]:
        role = str(message.get("role", "?"))
        content = str(message.get("content", "")).strip().replace("\n", " ")
        if len(content) > CHAT_CLIP_CHARS:
            content = content[:CHAT_CLIP_CHARS] + " …[clipped]"
        if content:
            chat_lines.append(f"{role}: {content}")

    task_lines: list[str] = []
    tasks = task_service.list_tasks(workspace_path)[:MAX_TASKS]
    for meta in tasks:
        try:
            task_lines.extend(task_service.task_state_summary(workspace_path, meta["id"]).splitlines())
        except (FileNotFoundError, KeyError):
            continue

    return MemoryContext(chatLines=chat_lines, taskLines=task_lines)


def build_session_digest(memory: MemoryContext) -> SessionDigest:
    parts: list[str] = []
    sources: list[str] = []
    if memory.chatLines:
        sources.append("chat")
        parts.append("Recent controller chat:")
        parts.extend(memory.chatLines)
    if memory.taskLines:
        sources.append("tasks")
        parts.append("Recent task state:")
        parts.extend(memory.taskLines)
    return SessionDigest(text="\n".join(parts), sources=sources)
