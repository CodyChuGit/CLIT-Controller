"""Context intelligence — compression interface (both implementations) + metrics."""

from __future__ import annotations

import asyncio

from agentflow import headroom_service
from agentflow.context_intelligence import compression, metrics


def test_simple_compressor_collapses_blank_runs():
    text = "a\n\n\n\n\nb"
    assert compression.simple_compress_text(text) == "a\n\nb"


def test_simple_compressor_folds_duplicate_lines():
    text = "\n".join(["INFO heartbeat ok"] * 50 + ["ERROR boom at line 7"])
    out = compression.simple_compress_text(text)
    assert out.count("INFO heartbeat ok") == 2
    assert "[… 48 more identical lines]" in out
    assert "ERROR boom at line 7" in out


def test_simple_compressor_truncates_long_runs_with_marker():
    text = "\n".join(f"line {i}" for i in range(1000))
    out = compression.simple_compress_text(text)
    lines = out.splitlines()
    assert len(lines) <= compression._MAX_LINES + 1
    assert any("more lines]" in line for line in lines)
    assert lines[0] == "line 0" and lines[-1] == "line 999"  # head and tail preserved


def test_simple_compressor_is_deterministic():
    text = "\n".join(f"row {i % 5}" for i in range(300))
    assert compression.simple_compress_text(text) == compression.simple_compress_text(text)


def test_headroom_compressor_delegates_to_existing_service(monkeypatch):
    async def fake(text, instructions=""):
        return "crushed"

    monkeypatch.setattr(headroom_service, "compress_context", fake)
    out = asyncio.run(compression.HeadroomCompressor().compress("bulky " * 500))
    assert out == "crushed"


def test_headroom_compressor_fails_open(monkeypatch):
    # The service already fails open; prove the interface preserves that.
    monkeypatch.setattr(headroom_service, "installed", lambda: False)
    text = "bulk line\n" * 300
    assert asyncio.run(compression.HeadroomCompressor().compress(text)) == text


def test_compress_body_records_both_implementations(monkeypatch):
    async def fake(text, instructions=""):
        return text  # headroom saw nothing to save

    monkeypatch.setattr(headroom_service, "compress_context", fake)
    text = "\n".join(["dup"] * 40)
    out, results = asyncio.run(compression.compress_body("logs", text))
    assert [r.compressor for r in results] == ["simple", "headroom"]
    assert results[0].applied and not results[1].applied
    assert results[0].charsAfter == len(out)
    assert results[0].section == "logs"


# -------------------------------------------------------------------- metrics


def test_count_tokens_uses_headroom_counter():
    tokens, counter = metrics.count_tokens("hello token counting world")
    assert tokens > 0
    assert counter.startswith("headroom:") or counter == "estimate"


def test_count_tokens_fallback_estimate(monkeypatch):
    monkeypatch.setattr(metrics, "_get_tokenizer", lambda: None)
    text = "x" * 400
    tokens, counter = metrics.count_tokens(text)
    assert tokens == 100 and counter == "estimate"


def test_usage_reports_savings(monkeypatch):
    monkeypatch.setattr(metrics, "_get_tokenizer", lambda: None)
    usage = metrics.usage("a" * 400, "a" * 100)
    assert usage.tokensBefore == 100 and usage.tokensAfter == 25
    assert usage.savingsPct == 75.0
    assert usage.counter == "estimate"


def test_usage_zero_input_is_safe(monkeypatch):
    monkeypatch.setattr(metrics, "_get_tokenizer", lambda: None)
    usage = metrics.usage("", "")
    assert usage.tokensBefore == 0 and usage.savingsPct == 0.0
