"""Pillar 5 tests — deterministic output contracts must validate, version, and
fail safely. These encode the Pillar 5 acceptance criteria (docs/PILLARS.md)."""

from __future__ import annotations

from agentflow import chat_directives, contracts


def test_every_contract_is_versioned_and_kinded():
    for kind, model_cls in contracts._REGISTRY.items():
        inst = model_cls.model_construct()  # type: ignore[call-arg]
        assert getattr(inst, "version", None) == contracts.CONTRACT_VERSION
        # the declared kind default matches the registry key
        assert model_cls.model_fields["kind"].default == kind


def test_valid_payload_round_trips():
    model, failure = contracts.validate(
        "task_summary",
        {
            "version": "1",
            "kind": "task_summary",
            "status": "completed",
            "title": "Done",
            "summary": "All good",
            "verification": [{"command": "pytest", "status": "passed"}],
        },
    )
    assert failure is None
    assert isinstance(model, contracts.TaskSummary)
    assert model.verification[0].status == "passed"


def test_unknown_kind_fails_safely():
    model, failure = contracts.validate("not_a_real_kind", {"x": 1})
    assert model is None
    assert isinstance(failure, contracts.FailureRecord)
    assert "Unknown contract kind" in failure.title


def test_unsupported_version_rejected():
    model, failure = contracts.validate("failure", {"version": "999", "kind": "failure", "title": "x", "summary": "y"})
    assert model is None
    assert failure is not None and "version" in failure.summary.lower()


def test_invalid_schema_fails_safely_without_raising():
    # missing required fields → structured failure, not an exception
    model, failure = contracts.validate("command_summary", {"kind": "command_summary"})
    assert model is None
    assert isinstance(failure, contracts.FailureRecord)
    assert "validation" in failure.summary.lower()


def test_token_efficiency_report_allows_unmeasured():
    rep = contracts.TokenEfficiencyReport(headroomApplied=True, profile="agent-90")
    assert rep.tokensSaved is None  # unmeasured is null, never fabricated
    assert rep.kind == "token_efficiency_report"


def test_directive_records_are_validated_kinded_records():
    text = (
        "intro\n"
        "```agentflow-task\ntitle: Add login\ngoal: implement login\nqueue: full\n```\n"
        "```agentflow-run\ncommand: npm test\n```\n"
        "```agentflow-done\nreason: shipped\n```\n"
    )
    records = chat_directives.controller_directive_records(text)
    kinds = [r["kind"] for r in records]
    assert "task" in kinds and "run" in kinds and "done" in kinds
    # every emitted record validates against its contract
    for r in records:
        model, failure = contracts.validate(r["kind"], r)
        assert failure is None, f"{r['kind']} failed: {failure}"
    task = next(r for r in records if r["kind"] == "task")
    assert task["title"] == "Add login" and task["version"] == "1"


def test_no_directives_yields_no_records():
    assert chat_directives.controller_directive_records("just prose, no blocks") == []
