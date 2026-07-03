"""Context intelligence — benchmark: all three strategies + retention scoring."""

from __future__ import annotations

import asyncio

from agentflow import config
from agentflow.context_intelligence import benchmarks, pipeline
from agentflow.context_intelligence.types import UserTask


def _ws(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    (ws / "parser.py").write_text("def parse_input():\n    pass\n" + "# filler comment line\n" * 400)
    (ws / "parser_utils.py").write_text("def parse_helper():\n    pass\n")
    return ws


def test_benchmark_compares_exactly_three_strategies(tmp_path):
    ws = _ws(tmp_path)
    report = asyncio.run(benchmarks.run_benchmark(ws, UserTask(text="speed up the parser input path")))
    assert report.kind == "benchmark"
    assert [r.strategy for r in report.benchmark] == ["naive", "ranked", "ranked_compressed"]
    for result in report.benchmark:
        assert result.tokens > 0
        assert result.selectedFileCount >= 1
        assert 0.0 <= result.retention <= 1.0
        assert result.mustKeepRetained + len(result.missing) == result.mustKeepTotal


def test_benchmark_retention_keeps_task_and_symbols(tmp_path):
    ws = _ws(tmp_path)
    report = asyncio.run(benchmarks.run_benchmark(ws, UserTask(text="speed up the parser input path")))
    ranked = next(r for r in report.benchmark if r.strategy == "ranked")
    assert ranked.retention == 1.0, f"ranked strategy dropped: {ranked.missing}"
    compressed = next(r for r in report.benchmark if r.strategy == "ranked_compressed")
    assert "speed up the parser input path" not in compressed.missing  # task text always survives


def test_benchmark_case_declares_must_keeps(tmp_path):
    ws = _ws(tmp_path)

    async def scenario():
        package = await pipeline.build_context_package(ws, UserTask(text="speed up the parser input path"))
        return benchmarks.build_case(package)

    case = asyncio.run(scenario())
    assert case.task in case.mustKeep
    assert "parse_input" in case.mustKeep  # named symbol of a selected file
