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


def test_code_execution_vectors_require_approval():
    # Auto-run prompt-injection hardening (audit P1-05): things that execute
    # file/package/program code must not auto-run; they route through approval.
    assert c("awk 'BEGIN{system(\"id\")}'").decision == REQUIRE_APPROVAL
    assert c("make").decision == REQUIRE_APPROVAL
    assert c("node build.js").decision == REQUIRE_APPROVAL
    assert c("npx cowsay hi").decision == REQUIRE_APPROVAL
    assert c("python script.py").decision == REQUIRE_APPROVAL
    assert c("pnpm dlx create-app").decision == REQUIRE_APPROVAL
    assert c("sed -e 's/a/b/' f").decision == REQUIRE_APPROVAL


def test_git_config_and_tar_exec_hooks_denied():
    # Known denylist-bypass exec vectors (audit P1-05).
    assert c("git -c core.pager=id diff").decision == DENY
    assert c("git --config core.pager=id log").decision == DENY
    assert c("tar --checkpoint-action=exec=id -cf x.tar .").decision == DENY
    assert c("tar -I pigz -cf x.tar .").decision == DENY


def test_inline_eval_still_denied():
    assert c('node -e "x"').decision == DENY
    assert c("python -c 'x'").decision == DENY


def test_legitimate_npm_scripts_still_allowed():
    # The documented dev/test workflow must keep auto-running (not regressed).
    assert c("npm run dev").decision == ALLOW
    assert c("npm run build").decision == ALLOW
    assert c("npm test").decision == ALLOW


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
