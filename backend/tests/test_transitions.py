from agentflow import transitions


def test_queue_transitions_valid_and_invalid():
    assert transitions.is_valid("queue", "queued", "running")
    assert transitions.is_valid("queue", "running", "done")
    assert transitions.is_valid("queue", "failed", "queued")  # retry
    assert transitions.is_valid("queue", "failed", "skipped")  # skip
    assert not transitions.is_valid("queue", "done", "running")  # terminal
    assert not transitions.is_valid("queue", "queued", "done")  # must run first


def test_step_transitions():
    assert transitions.is_valid("step", "running", "succeeded")
    assert transitions.is_valid("step", "failed", "queued")  # retryable
    assert transitions.is_valid("step", "provider_missing", "running")
    assert not transitions.is_valid("step", "succeeded", "failed")


def test_task_transitions():
    assert transitions.is_valid("task", "new", "in_progress")
    assert transitions.is_valid("task", "in_progress", "done")
    assert transitions.is_valid("task", "failed", "in_progress")  # reopen
    assert not transitions.is_valid("task", "abandoned", "in_progress")


def test_noop_and_unknown_are_permissive():
    assert transitions.is_valid("queue", "running", "running")  # no-op allowed
    assert transitions.is_valid("step", "legacy_value", "running")  # unknown frm
    assert transitions.is_valid("queue", "queued", "brand_new")  # unknown to
