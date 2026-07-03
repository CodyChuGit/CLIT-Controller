"""Claude stream-json → readable live text (dock live-activity rebuild).

Event shapes are taken from a real `claude -p --verbose --output-format
stream-json` run: system/hook/rate_limit envelopes, assistant thinking/text/
tool_use blocks, user tool_result (string and block-list content), and the
final result envelope.
"""

from __future__ import annotations

import json

from agentflow.stream_normalizer import ClaudeStreamJsonNormalizer, normalizer_for


def line(obj: dict) -> str:
    return json.dumps(obj) + "\n"


def assistant(*blocks: dict) -> str:
    return line({"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}})


def test_tool_use_becomes_marker_and_result_becomes_tail():
    n = ClaudeStreamJsonNormalizer()
    out = n.feed(
        assistant({"type": "tool_use", "name": "Bash", "input": {"command": "echo hello-clitc"}})
        + line(
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "tool_result", "content": "hello-clitc", "is_error": False}],
                },
            }
        )
        + assistant({"type": "text", "text": "done"})
    )
    assert "⏺ Bash(echo hello-clitc)" in out
    assert "⎿ hello-clitc" in out
    assert out.rstrip().endswith("done")


def test_envelopes_and_thinking_are_dropped():
    n = ClaudeStreamJsonNormalizer()
    noise = (
        line({"type": "system", "subtype": "init", "cwd": "/x"})
        + line({"type": "system", "subtype": "hook_started", "hook_name": "SessionStart"})
        + line({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}})
        + assistant({"type": "thinking", "thinking": "secret reasoning", "signature": "abc"})
    )
    assert n.feed(noise) == ""


def test_result_text_not_duplicated_when_already_streamed():
    n = ClaudeStreamJsonNormalizer()
    out = n.feed(assistant({"type": "text", "text": "the answer"}))
    out += n.feed(line({"type": "result", "subtype": "success", "result": "the answer"}))
    assert out.count("the answer") == 1


def test_result_used_as_fallback_when_nothing_streamed():
    n = ClaudeStreamJsonNormalizer()
    out = n.feed(line({"type": "result", "subtype": "success", "result": "only the result"}))
    assert "only the result" in out


def test_error_tool_result_is_labelled():
    n = ClaudeStreamJsonNormalizer()
    out = n.feed(
        line(
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "is_error": True,
                            "content": [{"type": "text", "text": "command not found"}],
                        }
                    ]
                },
            }
        )
    )
    assert "⎿ error: command not found" in out


def test_partial_lines_buffer_until_complete_and_flush_drains():
    n = ClaudeStreamJsonNormalizer()
    whole = assistant({"type": "text", "text": "hello"})
    assert n.feed(whole[:20]) == ""  # incomplete JSON line held
    assert "hello" in n.feed(whole[20:])
    # flush handles a final unterminated line
    n2 = ClaudeStreamJsonNormalizer()
    assert n2.feed(assistant({"type": "text", "text": "tail"}).rstrip("\n")) == ""
    assert "tail" in n2.flush()


def test_non_json_lines_pass_through():
    n = ClaudeStreamJsonNormalizer()
    assert n.feed("some warning from the CLI\n") == "some warning from the CLI\n"


def test_normalizer_only_engages_for_claude_stream_json():
    assert normalizer_for("claude", ["claude", "-p", "--output-format", "stream-json", "x"]) is not None
    assert normalizer_for("claude", ["claude", "-p", "x"]) is None  # user override → untouched
    assert normalizer_for("codex", ["codex", "exec", "x"]) is None


def test_runner_normalizes_claude_stdout_end_to_end(tmp_path):
    """The pipe: RUNNER.start attaches the normalizer for claude+stream-json argv,
    so record.stdout (what chat bubbles / CLITC parse / logs consume) is clean text."""
    import asyncio

    from agentflow.process_runner import RUNNER

    script = tmp_path / "fake-claude"
    lines = (
        assistant({"type": "tool_use", "name": "Read", "input": {"file_path": "src/app.py"}})
        + assistant({"type": "text", "text": "All done."})
    ).replace("'", "'\\''")
    script.write_text(f"#!/bin/sh\nprintf '%s' '{lines}'\n")
    script.chmod(0o755)

    async def run():
        record, consume = await RUNNER.start(
            [str(script), "--output-format", "stream-json"], tmp_path, provider="claude"
        )
        await consume
        return record

    record = asyncio.run(run())
    assert "⏺ Read(src/app.py)" in record.stdout
    assert "All done." in record.stdout
    assert '"type"' not in record.stdout  # no raw JSONL leaked downstream
