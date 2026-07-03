"""Normalize a provider CLI's live stdout into human-readable activity text.

Claude Code in headless ``-p`` mode buffers everything until exit — the dock
shows nothing while it works. With ``--output-format stream-json --verbose`` it
streams JSONL events instead, but raw JSONL is unreadable and would poison every
downstream consumer (chat bubbles, CLITC_RESULT_V1 parsing, task exchanges,
logs), which all read ``record.stdout`` as text.

So the normalizer sits at the single point where stdout chunks are read
(``process_runner._read_stream``) and translates JSONL into the same clean text
a human-narrating CLI would print:

- assistant text blocks   → the text itself (the live narrative)
- tool_use blocks         → ``⏺ ToolName(compact summary)`` marker lines
- tool_result blocks      → ``  ⎿ first line of the result``
- system/result envelopes → dropped (the result text was already streamed)
- anything that isn't JSON passes through untouched

The frontend live-activity parser renders the ``⏺``/``⎿`` markers as tool
rows — the same visual grammar Claude Code's own extension uses.
"""

from __future__ import annotations

import json
from typing import Optional

MARKER = "⏺"
RESULT_MARKER = "⎿"
_SUMMARY_MAX = 160
_RESULT_LINE_MAX = 160

# tool name -> the input field that best summarizes the call
_TOOL_SUMMARY_FIELDS = {
    "Bash": "command",
    "Read": "file_path",
    "Write": "file_path",
    "Edit": "file_path",
    "NotebookEdit": "notebook_path",
    "Grep": "pattern",
    "Glob": "pattern",
    "WebFetch": "url",
    "WebSearch": "query",
    "Task": "description",
}


def _tool_summary(name: str, tool_input: dict) -> str:
    field = _TOOL_SUMMARY_FIELDS.get(name)
    value = tool_input.get(field) if field else None
    if not value:
        value = tool_input.get("description") or ""
    if not value and tool_input:
        try:
            value = json.dumps(tool_input, ensure_ascii=False)
        except (TypeError, ValueError):
            value = ""
    text = str(value).replace("\n", " ").strip()
    return text[:_SUMMARY_MAX] + ("…" if len(text) > _SUMMARY_MAX else "")


def _result_first_line(content) -> str:
    """First non-empty line of a tool_result content (string or block list)."""
    if isinstance(content, list):
        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        content = "\n".join(texts)
    if not isinstance(content, str):
        return ""
    for line in content.splitlines():
        line = line.strip()
        if line:
            return line[:_RESULT_LINE_MAX] + ("…" if len(line) > _RESULT_LINE_MAX else "")
    return ""


class ClaudeStreamJsonNormalizer:
    """Incremental JSONL → text translator. ``feed`` returns whatever became
    renderable from this chunk; ``flush`` drains the held partial line."""

    def __init__(self) -> None:
        self._buffer = ""
        self._emitted_text = False

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        out: list[str] = []
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            out.append(self._line(line))
        return "".join(out)

    def flush(self) -> str:
        line, self._buffer = self._buffer, ""
        return self._line(line) if line.strip() else ""

    # ------------------------------------------------------------- internals

    def _line(self, line: str) -> str:
        stripped = line.strip()
        if not stripped:
            return ""
        if not stripped.startswith("{"):
            return line + "\n"  # non-JSON noise (warnings etc.) passes through
        try:
            event = json.loads(stripped)
        except ValueError:
            return line + "\n"
        if not isinstance(event, dict):
            return line + "\n"
        return self._event(event)

    def _event(self, event: dict) -> str:
        etype = event.get("type")
        if etype == "assistant":
            return self._assistant(event.get("message") or {})
        if etype == "user":
            return self._tool_results(event.get("message") or {})
        if etype == "result":
            # The final text was already streamed via assistant blocks; only a
            # failure with no prior narrative is worth surfacing here.
            if not self._emitted_text and event.get("subtype") != "success":
                text = event.get("result") or event.get("error") or ""
                return f"{text}\n" if text else ""
            if not self._emitted_text and isinstance(event.get("result"), str):
                self._emitted_text = True
                return event["result"] + "\n"
            return ""
        # system/init, stream_event partials, unknown envelopes: not narrative.
        return ""

    def _assistant(self, message: dict) -> str:
        out: list[str] = []
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and block.get("text"):
                self._emitted_text = True
                out.append(block["text"].rstrip() + "\n")
            elif block.get("type") == "tool_use":
                name = block.get("name") or "tool"
                summary = _tool_summary(name, block.get("input") or {})
                out.append(f"{MARKER} {name}({summary})\n")
        return "".join(out)

    def _tool_results(self, message: dict) -> str:
        out: list[str] = []
        for block in message.get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            first = _result_first_line(block.get("content"))
            if block.get("is_error"):
                first = f"error: {first}" if first else "error"
            if first:
                out.append(f"  {RESULT_MARKER} {first}\n")
        return "".join(out)


def normalizer_for(provider: Optional[str], argv: list[str]) -> Optional[ClaudeStreamJsonNormalizer]:
    """A stdout normalizer for this run, or None when raw text is already fine.
    Keyed off the actual argv so a user template without stream-json keeps
    today's behavior untouched."""
    if provider == "claude" and "stream-json" in argv:
        return ClaudeStreamJsonNormalizer()
    return None
