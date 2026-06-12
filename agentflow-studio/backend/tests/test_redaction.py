from agentflow.redaction import redact


def test_redacts_openai_style_keys():
    assert "sk-" not in redact("key is sk-abc123DEF456ghi789")
    assert "[REDACTED]" in redact("key is sk-abc123DEF456ghi789")


def test_redacts_github_tokens():
    assert "ghp_" not in redact("token ghp_abcdef1234567890")
    assert "github_pat_" not in redact("github_pat_11ABCDEF_xyz")


def test_redacts_slack_and_bearer():
    assert "xoxb-" not in redact("xoxb-1234-abcd")
    assert "Bearer" not in redact("Authorization: Bearer abc123def456")


def test_redacts_env_style_assignments():
    text = "OPENAI_API_KEY=sk-test123456789 ANTHROPIC_API_KEY=foo token=tok123 password=hunter2"
    cleaned = redact(text)
    for secret in ("sk-test", "foo", "tok123", "hunter2"):
        assert secret not in cleaned
    assert cleaned.count("[REDACTED]") >= 4


def test_leaves_normal_text_alone():
    text = "git status --short shows 3 modified files"
    assert redact(text) == text


def test_handles_none_and_empty():
    assert redact(None) == ""
    assert redact("") == ""


def test_children_do_not_inherit_port(monkeypatch, tmp_path):
    """Dev servers honor PORT; inheriting AgentFlow's would hijack localhost:8787."""
    import asyncio

    from agentflow.process_runner import ProcessRunner

    monkeypatch.setenv("PORT", "8787")
    runner = ProcessRunner()
    record = asyncio.run(runner.run_and_wait(["printenv", "PORT"], tmp_path, timeout=10))
    assert record.exit_code != 0 or record.stdout.strip() == ""
