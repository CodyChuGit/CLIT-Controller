"""Regression tests for the security-review fixes (2026-06-17)."""

import pytest

from agentflow import config, policy_service
from agentflow.redaction import redact


# --------------------------------------------------------------- redaction
def test_redaction_covers_common_secret_formats():
    cases = {
        "AKIAIOSFODNN7EXAMPLE": "aws access key id",
        "AIzaSyD-1234567890abcdefghijklmnopqrstuv": "google api key",
        "gho_16CharsOfTokenABCDEFGHIJKLMNOP": "github oauth token",
        "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY": "aws secret",
        "password: hunter2": "colon password",
        "token: abc123def456": "colon token",
        "MY_SERVICE_TOKEN=supersecretvalue": "token assignment",
    }
    for raw, label in cases.items():
        assert "[REDACTED]" in redact(raw), f"{label} not redacted: {raw!r}"


def test_redaction_masks_pem_private_key_block():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"
    out = redact(pem)
    assert "MIIEpAIBAAKCAQEA" not in out
    assert "[REDACTED]" in out


def test_redaction_masks_url_credentials_but_keeps_structure():
    out = redact("DATABASE_URL=postgres://app:s3cr3tpw@db.internal/prod")
    assert "s3cr3tpw" not in out
    assert "postgres://app:" in out and "@db.internal/prod" in out


def test_redaction_leaves_plain_text_alone():
    assert redact("just a normal log line about files") == "just a normal log line about files"


# ----------------------------------------------------------------- policy
def test_policy_denies_env_var_prefix():
    # `FOO=bar cmd` hides the real binary from classification.
    assert policy_service.classify_action("FOO=bar rm -rf x").denied
    assert policy_service.classify_action("env EVIL=1 node script.js").denied


def test_policy_denies_interpreter_inline_eval():
    for cmd in ["node -e \"require('fs')\"", "python3 -c 'import os'", "ruby -e 'puts 1'", "perl -e '1'"]:
        assert policy_service.classify_action(cmd).denied, cmd


def test_policy_still_allows_normal_workspace_commands(tmp_path):
    for cmd in ["npm test", "git status", "ls", "npm run build"]:
        assert policy_service.classify_action(cmd, tmp_path).allowed, cmd


def test_policy_still_requires_approval_for_remote(tmp_path):
    assert policy_service.classify_action("git push", tmp_path).decision == policy_service.REQUIRE_APPROVAL


# ------------------------------------------------------------- workspace root
def test_set_workspace_refuses_filesystem_root():
    with pytest.raises(ValueError):
        config.set_workspace("/")


def test_set_workspace_refuses_home_directory():
    from pathlib import Path

    with pytest.raises(ValueError):
        config.set_workspace(str(Path.home()))


# ----------------------------------------------------- SPA static-file confinement
def test_spa_route_does_not_serve_files_outside_dist():
    """The catch-all must not become an arbitrary file read via `..`."""
    from fastapi.testclient import TestClient

    from agentflow import paths
    from agentflow.app import create_app

    dist = paths.frontend_dist()
    if not (dist.is_dir() and (dist / "index.html").exists()):
        pytest.skip("frontend not built; SPA route not mounted")

    secret = dist.parent / "outside_secret_test.txt"
    secret.write_text("TOP-SECRET-OUTSIDE-DIST")
    try:
        client = TestClient(create_app())
        # %2f keeps the `..` from being normalized away before it reaches the route.
        resp = client.get("/..%2foutside_secret_test.txt")
        assert "TOP-SECRET-OUTSIDE-DIST" not in resp.text
        # A non-existent in-app path should fall back to the SPA shell, not error.
        assert client.get("/some/spa/route").status_code == 200
    finally:
        secret.unlink(missing_ok=True)
