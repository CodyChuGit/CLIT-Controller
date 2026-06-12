import asyncio

from agentflow import provider_probe


def test_no_installer_is_graceful():
    # omlx has no one-click installer (Cody's own tool / manual PATH setup)
    result = asyncio.run(provider_probe.install_provider("omlx"))
    if result["status"] == "already_installed":
        return  # machine has omlx — nothing to assert beyond the short-circuit
    assert result["status"] == "no_installer"
    assert "omlx" in result["message"]


def test_already_installed_short_circuits():
    # git is present on any dev machine running this suite
    result = asyncio.run(provider_probe.install_provider("git"))
    assert result["status"] == "already_installed"


def test_every_provider_defines_install_fields():
    for p in provider_probe.PROVIDERS:
        assert "installCommand" in p
        assert "installHint" in p


def test_parse_model_lines_filters_noise():
    out = (
        "Gemini 3.5 Flash (High)\n"
        "  - Claude Sonnet 4.6 (Thinking)\n"
        "\n"
        "Usage of agy:\n"
        "Error: something\n"
        "GPT-OSS 120B (Medium)\n"
    )
    parsed = provider_probe._parse_model_lines(out)
    assert parsed == ["Gemini 3.5 Flash (High)", "Claude Sonnet 4.6 (Thinking)", "GPT-OSS 120B (Medium)"]


def test_agent_providers_have_model_options():
    for pid in ("codex", "claude", "antigravity"):
        d = provider_probe.base_state(pid)
        assert len(d["modelOptions"]) > 0
