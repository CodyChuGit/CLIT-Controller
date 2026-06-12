import asyncio

from agentflow import provider_probe


def test_no_installer_is_graceful():
    # antigravity has no one-click installer
    result = asyncio.run(provider_probe.install_provider("antigravity"))
    assert result["status"] == "no_installer"
    assert "antigravity" in result["message"].lower() or "Antigravity" in result["message"]


def test_already_installed_short_circuits():
    # git is present on any dev machine running this suite
    result = asyncio.run(provider_probe.install_provider("git"))
    assert result["status"] == "already_installed"


def test_every_provider_defines_install_fields():
    for p in provider_probe.PROVIDERS:
        assert "installCommand" in p
        assert "installHint" in p
