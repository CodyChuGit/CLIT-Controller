"""Task A5 — persona prompt builder covers engine, local, and unknown personas."""

from __future__ import annotations

from agentflow.orchestrator import personas


def test_engine_persona_prompt_has_role_folder_and_message():
    p = personas.persona_prompt(
        "qa-runner",
        {"usage_header": "[budget]", "task_rel_dir": "tasks/t1", "message": "run the suite"},
    )
    assert "qa-runner" in p
    assert "[budget]" in p
    assert "tasks/t1" in p
    assert "run the suite" in p


def test_unknown_persona_falls_back_but_names_the_role():
    p = personas.persona_prompt("totally-made-up", {"task_rel_dir": "tasks/t1"})
    assert "totally-made-up" in p
    assert "tasks/t1" in p


def test_legacy_step_maps_to_persona():
    assert personas.LEGACY_STEP_PERSONA["codex_spec"] == "spec-writer"
    assert personas.LEGACY_STEP_PERSONA["codex_review"] == "independent-reviewer"
    p = personas.persona_prompt(personas.LEGACY_STEP_PERSONA["codex_review"], {"task_rel_dir": "t"})
    assert "independent-reviewer" in p


def test_local_spec_writer_persona_resolves():
    p = personas.persona_prompt("spec-writer", {"task_rel_dir": "t"})
    assert "spec-writer" in p
    assert "plan" in p.lower()
