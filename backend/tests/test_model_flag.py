from agentflow.task_service import _build_argv


def test_model_token_expands_when_set():
    argv = _build_argv("codex exec {model} {prompt}", "do the thing", "gpt-5-codex")
    assert argv[1:] == ["exec", "--model", "gpt-5-codex", "do the thing"]


def test_model_token_vanishes_when_unset():
    argv = _build_argv("claude -p {model} {prompt}", "fix it", None)
    assert argv[1:] == ["-p", "fix it"]


def test_model_before_value_taking_flag():
    # agy's -p takes the prompt as its value, so {model} sits before it.
    argv = _build_argv("agy {model} -p {prompt}", "qa pass", "gemini-3-pro")
    assert argv[1:] == ["--model", "gemini-3-pro", "-p", "qa pass"]


def test_template_without_model_token_ignores_model():
    argv = _build_argv("codex exec {prompt}", "spec", "some-model")
    assert "--model" not in argv
