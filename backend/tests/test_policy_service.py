from agentflow import policy_service
from agentflow.policy_service import ALLOW, DENY, REQUIRE_APPROVAL


def c(cmd, ws=None):
    return policy_service.classify_action(cmd, ws)


def test_safe_local_commands_allowed():
    assert c("git status").decision == ALLOW
    assert c("git diff").decision == ALLOW
    assert c("npm test").decision == ALLOW
    assert c("npm run build").decision == ALLOW
    assert c("ls").decision == ALLOW


def test_remote_and_install_require_approval():
    assert c("git push").decision == REQUIRE_APPROVAL
    assert c("git pull").decision == REQUIRE_APPROVAL
    assert c("npm install left-pad").decision == REQUIRE_APPROVAL
    assert c("pnpm add react").decision == REQUIRE_APPROVAL
    assert c("brew install jq").decision == REQUIRE_APPROVAL
    assert c("gh pr create").decision == REQUIRE_APPROVAL
    assert c("npm publish").decision == REQUIRE_APPROVAL


def test_dangerous_commands_denied():
    assert c("sudo rm -rf /").decision == DENY
    assert c("bash -c 'echo hi'").decision == DENY
    assert c("npm test && rm -rf /").decision == DENY  # shell operator
    assert c("cat foo > bar").decision == DENY


def test_workspace_confinement(tmp_path):
    assert c("npm run dev", tmp_path).decision == ALLOW
    assert c(f"cat {tmp_path}/notes.txt", tmp_path).decision == ALLOW
    assert c("cat /etc/passwd", tmp_path).decision == DENY
    assert c("cat ../secrets.txt", tmp_path).decision == DENY


def test_deny_reason_matches_legacy_denylist():
    # require_approval commands are NOT denied by the legacy helper
    assert policy_service.deny_reason("git push") is None
    assert policy_service.deny_reason("npm run dev") is None
    # hard denials still produce a reason
    assert policy_service.deny_reason("sudo rm -rf /") is not None
    assert policy_service.deny_reason("cat foo > bar") is not None


def test_command_denied_wrapper_unchanged(tmp_path):
    from agentflow.chat_service import command_denied

    assert command_denied("npm run dev") is None
    assert command_denied("git push") is None
    assert command_denied("sudo rm -rf /") is not None
    assert command_denied("cat ../secrets.txt", tmp_path) is not None
