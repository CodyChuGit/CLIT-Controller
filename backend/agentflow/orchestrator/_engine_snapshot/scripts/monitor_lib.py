#!/usr/bin/env python3
"""monitor_lib.py - shared deterministic logic for the long-running-job layer.

The three monitoring CLIs (job-supervisor.py, omlx-monitor.py,
emit-completion-event.py) have hyphenated names and cannot import one another,
so the Level-0 deterministic logic they must agree on lives here:

  * job directory layout under .claude-runtime/jobs/<job-id>/
  * classify_deterministic()  - exit code / timeout / stall / artifacts -> state
  * build_monitor_report()    - deterministic baseline monitor-report
  * build_completion_event()  - terminal event that recalls Claude

A semantic (oMLX) report may ANNOTATE these, but the deterministic state is the
floor: oMLX can never turn a deterministically failed job into a passed one.

oMLX is OPTIONAL. When it isn't loaded, Antigravity (`agy`, Level 2) takes over
the Level-1 triage role using `operational_triage()` - deterministic, grep-based
failure grouping (no LLM). It is less smart than oMLX's semantic summarization
but needs nothing running, so monitoring never silently degrades to bare exit
codes.
"""
from __future__ import annotations

import os
import re

import _lib

JOBS_DIRNAME = "jobs"
# deterministic states that recall Claude (monitor-policy supervisor.recall_on)
RECALL_STATES = {"passed", "failed", "timeout", "stalled", "missing_artifacts", "input_required"}
# map a deterministic state -> completion-event "event" name
EVENT_FOR_STATE = {
    "passed": "completed", "failed": "failed", "timeout": "timeout",
    "stalled": "stalled", "missing_artifacts": "missing_artifacts",
    "input_required": "input_required", "terminated": "terminated",
}
# map a deterministic state -> monitor-report.state enum
MONITOR_STATE_FOR = {
    "passed": "passed", "failed": "failed", "timeout": "failed",
    "stalled": "stalled", "missing_artifacts": "failed",
    "input_required": "input_required", "running": "running", "terminated": "failed",
}


def jobs_root():
    return os.path.join(_lib.runtime_dir(), JOBS_DIRNAME)


def job_dir(job_id, create=False):
    d = os.path.join(jobs_root(), job_id)
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def job_file(job_id, name, create_dir=False):
    return os.path.join(job_dir(job_id, create=create_dir), name)


def missing_artifacts(working_directory, expected):
    out = []
    for art in expected or []:
        candidate = art if os.path.isabs(art) else os.path.join(working_directory or ".", art)
        if not os.path.exists(candidate):
            out.append(art)
    return out


def classify_deterministic(exit_code, timed_out=False, stalled=False, terminated=False,
                           missing=None, running=False):
    """Deterministic Level-0 state. Order matters: a real timeout/stall is
    reported as such even if the killed process also returned non-zero."""
    if running:
        return "running"
    if timed_out:
        return "timeout"
    if stalled:
        return "stalled"
    if terminated:
        return "terminated"
    if exit_code is None:
        return "failed"
    if exit_code != 0:
        return "failed"
    if missing:
        return "missing_artifacts"
    return "passed"


def recall_claude(state):
    return state in RECALL_STATES


def read_log_tail(path, max_bytes=20000):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
            return fh.read().decode("utf-8", "replace")
    except OSError:
        return ""


# Deterministic failure signatures for Antigravity's operational (grep-based)
# triage. This is the takeover for oMLX's semantic Level-1 summarization when
# oMLX isn't loaded - pattern matching, not understanding, but no LLM required.
FAILURE_SIGNATURES = [
    ("oom", re.compile(r"out of memory|OOMKilled|Killed\b|MemoryError|bad_alloc|Cannot allocate memory", re.I)),
    ("traceback", re.compile(r"Traceback \(most recent call last\)|Exception in thread|^panic:|fatal error:", re.I | re.M)),
    ("assertion", re.compile(r"AssertionError|assert(?:ion)? (?:failed|error)", re.I)),
    ("test_failure", re.compile(r"\bFAILED\b|\bFAIL\b|[0-9]+ failed|✗", re.I)),
    ("build_error", re.compile(r"compilation failed|build failed|cannot find module|ModuleNotFoundError|undefined reference|error TS[0-9]+", re.I)),
    ("timeout", re.compile(r"timed out|ETIMEDOUT|deadline exceeded", re.I)),
    ("connection", re.compile(r"connection refused|ECONNREFUSED|connection reset|host unreachable", re.I)),
    ("generic_error", re.compile(r"\bERROR\b|\bERR!|^error:", re.I | re.M)),
]


def operational_triage(stdout_text, stderr_text, max_lines=4000):
    """Antigravity's deterministic log triage: group repeated failure
    signatures, pick the first causal line, and flag anomalies. No LLM."""
    groups = {}
    first_causal = None
    ranges = []
    for stream, text in (("stderr", stderr_text or ""), ("stdout", stdout_text or "")):
        lines = text.splitlines()[-max_lines:]
        for i, line in enumerate(lines):
            for name, pat in FAILURE_SIGNATURES:
                if pat.search(line):
                    g = groups.setdefault(name, {"signature": name, "count": 0,
                                                 "sample": line.strip()[:200], "stream": stream})
                    g["count"] += 1
                    if first_causal is None:
                        first_causal = line.strip()[:200]
                        ranges.append({"stream": stream, "around_line": i, "sample": line.strip()[:200]})
                    break
    repeated = sorted(groups.values(), key=lambda g: -g["count"])
    anomalies = [f"{g['signature']} x{g['count']}" for g in repeated if g["count"] > 1]
    return {
        "repeated_failures": repeated,
        "anomalies": anomalies,
        "first_causal_failure": first_causal,
        "relevant_log_ranges": ranges[:5],
    }


def deterministic_report(job_id, with_operational=False):
    """Build a monitor-report from the supervisor's recorded state. When
    with_operational is set, add Codex's grep-based triage and mark the
    report produced_by 'codex' (the oMLX takeover path)."""
    jd = job_dir(job_id)
    man_path = os.path.join(jd, "manifest.json")
    if not os.path.exists(man_path):
        return None
    manifest = _lib.read_json(man_path)
    st_path = os.path.join(jd, "status.json")
    st = _lib.read_json(st_path) if os.path.exists(st_path) else {}
    exit_code = manifest.get("exit_code")
    missing = missing_artifacts(manifest.get("working_directory"), manifest.get("expected_artifacts"))
    state = st.get("state")
    if state not in ("timeout", "stalled", "terminated", "running"):
        state = classify_deterministic(exit_code, missing=missing,
                                       running=(exit_code is None and not st.get("final")))
    operational = None
    produced_by = "deterministic"
    escalation = "none"
    if with_operational:
        operational = operational_triage(read_log_tail(os.path.join(jd, "stdout.log")),
                                         read_log_tail(os.path.join(jd, "stderr.log")))
        produced_by = "codex"
        if state in ("failed", "timeout"):
            escalation = "codex"
        elif state in ("stalled", "missing_artifacts"):
            escalation = "codex"
    return build_monitor_report(manifest, state, missing=missing, operational=operational,
                                produced_by=produced_by, escalation=escalation)


def build_monitor_report(manifest, det_state, missing=None, summary=None,
                         escalation="none", produced_by="deterministic", confidence=1.0,
                         extra=None, operational=None):
    rep = {
        "job_id": manifest["job_id"],
        "state": MONITOR_STATE_FOR.get(det_state, "running"),
        "phase": None,
        "progress": 1.0 if det_state in ("passed", "failed", "timeout", "missing_artifacts") else None,
        "summary": summary or f"Deterministic state: {det_state}.",
        "first_causal_failure": None,
        "repeated_failures": [],
        "anomalies": [],
        "relevant_log_ranges": [],
        "resource_observations": [],
        "expected_artifacts": manifest.get("expected_artifacts", []) or [],
        "missing_artifacts": missing or [],
        "recommended_escalation": escalation,
        "produced_by": produced_by,
        "confidence": confidence,
    }
    if operational:
        for k in ("repeated_failures", "anomalies", "first_causal_failure", "relevant_log_ranges"):
            if operational.get(k):
                rep[k] = operational[k]
        if operational.get("first_causal_failure") and not summary:
            rep["summary"] = f"{det_state}: first failure -> {operational['first_causal_failure']}"
    if extra:
        rep.update(extra)
    return rep


def build_completion_event(manifest, det_state, exit_code=None, duration=None,
                           missing=None, last_activity_age=None, monitor_report=None,
                           reason=None):
    state = det_state
    escalation = "none"
    if state in ("failed", "timeout"):
        escalation = "codex"   # complex failure -> Codex semantic analysis first
    elif state in ("stalled", "missing_artifacts"):
        escalation = "codex"   # Codex owns operational inspection (v2)
    elif state == "input_required":
        escalation = "claude"
    return {
        "job_id": manifest["job_id"],
        "label": manifest.get("label", manifest["job_id"]),
        "event": EVENT_FOR_STATE.get(state, "failed"),
        "deterministic_state": "passed" if state == "passed" else
                               ("timeout" if state == "timeout" else
                                ("stalled" if state == "stalled" else
                                 ("terminated" if state == "terminated" else
                                  ("failed" if state in ("failed", "missing_artifacts") else "unknown")))),
        "exit_code": exit_code,
        "duration_seconds": round(duration, 3) if isinstance(duration, (int, float)) else None,
        "expected_artifacts": manifest.get("expected_artifacts", []) or [],
        "missing_artifacts": missing or [],
        "last_activity_age_seconds": round(last_activity_age, 3) if isinstance(last_activity_age, (int, float)) else None,
        "recall_claude": recall_claude(state),
        "recommended_escalation": escalation,
        "monitor_report": monitor_report,
        "reason": reason or f"Job reached deterministic state '{state}'.",
        "emitted_at": _lib.now_iso(),
    }


def merge_semantic_over_deterministic(deterministic_event, semantic_report):
    """Apply an oMLX semantic report WITHOUT letting it override a failure.
    Returns the (possibly annotated) completion event."""
    ev = dict(deterministic_event)
    ev["monitor_report"] = semantic_report
    det = ev["deterministic_state"]
    # Hard floor: a deterministically failed/timed-out/stalled job stays failed.
    if det in ("failed", "timeout", "stalled", "terminated"):
        return ev  # semantic summary is advisory only
    # For a passed job, oMLX may still flag anomalies and request escalation up.
    if semantic_report.get("state") in ("failed", "stalled", "blocked"):
        ev["recall_claude"] = True
        ev["recommended_escalation"] = semantic_report.get("recommended_escalation", "codex")
        ev["reason"] = "Deterministic pass but oMLX flagged a semantic anomaly."
    return ev


def _self_check():
    assert classify_deterministic(0) == "passed"
    assert classify_deterministic(1) == "failed"
    assert classify_deterministic(0, missing=["out.bin"]) == "missing_artifacts"
    assert classify_deterministic(0, timed_out=True) == "timeout"
    assert classify_deterministic(0, stalled=True) == "stalled"
    assert classify_deterministic(None, running=True) == "running"
    assert recall_claude("passed") and recall_claude("failed") and not recall_claude("running")

    manifest = {"job_id": "j1", "label": "demo", "expected_artifacts": ["out.bin"], "working_directory": "/tmp"}
    ev_fail = build_completion_event(manifest, "failed", exit_code=2, duration=1.0)
    assert ev_fail["recall_claude"] and ev_fail["event"] == "failed"

    # semantic cannot override a deterministic failure
    sem = {"state": "passed", "summary": "looks fine to me", "recommended_escalation": "none"}
    merged = merge_semantic_over_deterministic(ev_fail, sem)
    assert merged["deterministic_state"] == "failed" and merged["recall_claude"], merged

    # semantic CAN escalate a deterministic pass
    ev_pass = build_completion_event(manifest, "passed", exit_code=0, duration=1.0, missing=[])
    sem_bad = {"state": "failed", "summary": "OOM signature in logs", "recommended_escalation": "claude"}
    merged2 = merge_semantic_over_deterministic(ev_pass, sem_bad)
    assert merged2["recall_claude"] and merged2["recommended_escalation"] == "claude", merged2

    # operational (grep-based) triage = Antigravity's oMLX takeover
    tri = operational_triage(
        "building...\nERROR: cannot find module 'x'\nERROR: cannot find module 'y'\n",
        "Traceback (most recent call last):\n  AssertionError: nope\n")
    sigs = {g["signature"] for g in tri["repeated_failures"]}
    assert "traceback" in sigs and "build_error" in sigs, tri  # most-specific wins
    assert tri["first_causal_failure"], tri
    assert any("build_error x2" == a for a in tri["anomalies"]), tri  # 2 "cannot find module"
    rep = build_monitor_report(manifest, "failed", produced_by="codex", operational=tri)
    assert rep["produced_by"] == "codex" and rep["repeated_failures"], rep
    print("OK monitor_lib self-check passed")


if __name__ == "__main__":
    _self_check()
