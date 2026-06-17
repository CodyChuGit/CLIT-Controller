import copy

from agentflow.routing_service import budget_context_header, recommend
from agentflow.usage_service import DEFAULT_USAGE


def usage_with(claude="green", antigravity="green", codex="green", mode="balanced"):
    data = copy.deepcopy(DEFAULT_USAGE)
    data["orchestrationMode"] = mode
    data["providers"]["claude"]["health"] = claude
    data["providers"]["antigravity"]["health"] = antigravity
    data["providers"]["codex"]["health"] = codex
    return data


def test_claude_red_recommends_cheaper_route():
    rec = recommend(usage_with(claude="red"))
    assert rec["cheaperRouteRecommended"] is True
    assert rec["selectedProvider"] == "codex"
    assert rec["manualApprovalRecommended"] is True
    text = " ".join(rec["lines"]) + " ".join(rec["warnings"])
    assert "Avoid Claude" in text or "avoid Claude" in text
    assert any("Codex" in line for line in rec["lines"])
    assert any("local tests" in line.lower() for line in rec["lines"])


def test_claude_yellow_allows_implementation_only():
    rec = recommend(usage_with(claude="yellow"))
    assert rec["cheaperRouteRecommended"] is True
    assert rec["selectedProvider"] == "claude"
    assert any("implementation only" in line for line in rec["lines"])


def test_claude_green_standard_chain():
    rec = recommend(usage_with())
    assert rec["cheaperRouteRecommended"] is False
    assert any("standard chain" in line for line in rec["lines"])
    assert any("Antigravity" in line for line in rec["lines"])  # antigravity green preference


def test_manual_mode_flags_manual_approval():
    rec = recommend(usage_with(mode="manual_approval"))
    assert rec["manualApprovalRecommended"] is True


def test_budget_context_header_format():
    header = budget_context_header(usage_with(claude="yellow"))
    assert header.startswith("Budget context:")
    assert "- Current traffic control mode: Balanced" in header
    assert "- Claude usage: yellow" in header
    assert "minimize full-file context" in header
