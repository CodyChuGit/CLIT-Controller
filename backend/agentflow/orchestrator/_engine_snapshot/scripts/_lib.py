#!/usr/bin/env python3
"""Shared, dependency-free helpers for the agent-orchestrator.

This module is the single source of truth for the small amount of "real" logic
the orchestrator engine needs without pulling in third-party packages (the
target machines may have neither PyYAML nor jsonschema installed):

  * read_yaml()       - minimal YAML subset reader (maps, lists, scalars)
  * validate()        - minimal JSON-Schema subset validator
  * redact()          - secret detection + redaction
  * runtime helpers   - skill-root / runtime-dir resolution, JSON IO, globbing

Every other Python script imports from here so the parsing/validation/redaction
behaviour stays identical across the engine. Run this file directly to execute
its self-check:  python3 _lib.py
"""
from __future__ import annotations

import json
import os
import re
from fnmatch import fnmatch

# --------------------------------------------------------------------------- #
# Canonical taxonomy (single source of truth; schemas embed the same enums and
# tests/test-validation.py guards against drift between the two)
# --------------------------------------------------------------------------- #

AGENTS = ["claude", "codex", "antigravity", "omlx"]

STATUSES = ["success", "partial", "failed", "blocked"]

QA_LEVELS = ["TARGETED", "CHANGE_SCOPED", "FULL", "RELEASE"]

SEVERITIES = ["P0", "P1", "P2", "P3"]

MONITOR_STATES = ["running", "passed", "failed", "stalled", "blocked", "input_required"]

TASK_TYPES = [
    "LOCAL_CORE_IMPLEMENTATION", "LOCAL_BACKEND_IMPLEMENTATION",
    "LOCAL_FRONTEND_IMPLEMENTATION", "LOCAL_DEBUGGING", "LOCAL_CODE_REVIEW",
    "LOCAL_ARCHITECTURE", "LOCAL_FILE_DISCOVERY", "LOCAL_REPOSITORY_INVENTORY",
    "LOCAL_SYMBOL_SEARCH", "LOCAL_CONFIGURATION_DISCOVERY",
    "LOCAL_DEPENDENCY_INVENTORY", "CODEBASE_SEMANTIC_ANALYSIS",
    "CODEBASE_ARCHITECTURE_MAPPING", "CODEBASE_FLOW_TRACING",
    "BLAST_RADIUS_ANALYSIS", "SPECIFICATION_CONSISTENCY_REVIEW", "WEB_RESEARCH",
    "CURRENT_INFORMATION", "GITHUB_REPOSITORY_SEARCH", "GITHUB_CODE_SEARCH",
    "GITHUB_ISSUE_RESEARCH", "API_DOCUMENTATION", "DEPENDENCY_EVALUATION",
    "TECHNOLOGY_COMPARISON", "RESEARCH_SYNTHESIS", "PARALLEL_INVESTIGATION",
    "INDEPENDENT_IMPLEMENTATION_REVIEW", "TEST_PLAN_DESIGN", "MARKDOWN_AUTHORING",
    "PROJECT_DOCUMENTATION", "FRONTEND_BROWSER_QA", "FRONTEND_VISUAL_REVIEW",
    "FRONTEND_BUG_FIX", "TEST_DISCOVERY", "TEST_EXECUTION", "BUILD_EXECUTION",
    "LINT_EXECUTION", "FORMAT_CHECK", "STATIC_ANALYSIS", "RUNTIME_VALIDATION",
    "QA_EVIDENCE_COLLECTION", "QA_REPORTING", "TASK_EXECUTION", "IMAGE_ASSET_GENERATION",
    "LONG_RUNNING_JOB",
    "LOG_TRIAGE", "GIT_STATUS_INSPECTION", "GIT_DIFF_INSPECTION",
    "GIT_DIFF_SUMMARY", "GIT_CHECKPOINT", "GIT_COMMIT", "GIT_PUSH",
    "GITHUB_VERSION_CONTROL", "CI_MONITORING", "ROUTINE_TOOL_CALL",
    "COMMIT_SUMMARY", "MILESTONE_SUMMARY", "GIT_MILESTONE",
    "XCODE_PROJECT_SETUP", "APPLE_BUILD_TEST", "SIMULATOR_LIFECYCLE",
    "SIMULATOR_VISUAL_QA", "APPLE_VERIFICATION",
    "MIXED_RESEARCH_AND_IMPLEMENTATION", "MIXED_FRONTEND_QA_AND_FIX",
    "MIXED_CORE_CHANGE_AND_VALIDATION", "DO_NOT_DELEGATE",
]

ROUTING_DECISIONS = [
    "HANDLE_WITH_CLAUDE", "DELEGATE_TO_CODEX", "DELEGATE_TO_ANTIGRAVITY",
    "DELEGATE_TO_OMLX_MONITOR", "CODEX_THEN_CLAUDE", "CLAUDE_THEN_CODEX",
    "ANTIGRAVITY_THEN_CODEX", "CODEX_THEN_ANTIGRAVITY",
    "FRONTEND_QA_FIX_LOOP", "RESEARCH_THEN_IMPLEMENT_THEN_VALIDATE",
    "PARALLELIZE_CODEX_AND_ANTIGRAVITY",
    "CLAUDE_WITH_OMLX_MONITOR", "CODEX_WITH_OMLX_MONITOR",
    "ANTIGRAVITY_WITH_OMLX_MONITOR", "ESCALATE_TO_CLAUDE",
]

# Codex is the local truth + control layer: files, repo, QA, git workflow
# execution, Xcode/simulators. It still never writes feature code — Claude
# implements; Codex verifies, executes, and reviews.
CODEX_PERSONAS = [
    "codebase-analyst", "parallel-investigation-lead", "research-synthesizer",
    "independent-reviewer", "test-strategy-designer", "technical-writer",
    "repository-navigator", "environment-operator", "qa-runner", "task-runner",
    "runtime-validator", "qa-reporter", "git-steward", "xcode-controller",
]

# Antigravity (Gemini) looks, searches, repeats: browser + visual truth,
# OCR/vision, live web research, and the commit/milestone narrative.
ANTIGRAVITY_PERSONAS = [
    "browser-qa-operator", "frontend-visual-reviewer", "simulator-qa-analyst",
    "web-researcher", "github-scout", "github-code-investigator",
    "api-documentation-specialist", "dependency-auditor",
    "routine-tool-operator", "commit-summarizer",
]

RETRY_CATEGORIES = [
    "NARROW_SCOPE", "MISSING_EVIDENCE", "INSUFFICIENT_OPTIONS", "OUTDATED_SOURCES",
    "WRONG_PLATFORM", "INCOMPLETE_DELIVERABLE", "INVALID_FORMAT",
    "UNSUPPORTED_CLAIM", "MISSING_BROWSER_EVIDENCE", "FAILED_REPRODUCTION",
    "FAILED_VALIDATION", "ENVIRONMENT_BLOCKED", "UNAPPROVED_FILE_CHANGE",
    "MISSING_ARTIFACT", "UNSAFE_GIT_STATE",
]


# --------------------------------------------------------------------------- #
# Paths / runtime
# --------------------------------------------------------------------------- #

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def project_root() -> str:
    """Working directory the orchestrator operates on (the user's repo)."""
    return os.environ.get("TRIAGENT_PROJECT_ROOT", os.getcwd())


def runtime_dir() -> str:
    """`.claude-runtime` under the project root; created on demand."""
    d = os.environ.get(
        "TRIAGENT_RUNTIME_DIR", os.path.join(project_root(), ".claude-runtime")
    )
    os.makedirs(d, exist_ok=True)
    return d


def config_path(name: str) -> str:
    return os.path.join(SKILL_ROOT, "config", name)


def schema_path(name: str) -> str:
    return os.path.join(SKILL_ROOT, "schemas", name)


def now_iso() -> str:
    """UTC timestamp, second precision (passed in via results, never random)."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str, obj) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=False)
        fh.write("\n")
    return path


def path_matches_any(path: str, patterns) -> bool:
    """True if `path` matches any glob pattern. `**` is treated as a wildcard
    that also spans directory separators (fnmatch already allows `*` to cross
    `/`, which is what we want for `frontend/**` style rules)."""
    p = path.lstrip("./")
    for pat in patterns or []:
        pat = pat.lstrip("./")
        if fnmatch(p, pat):
            return True
        # `dir/**` should also match `dir/file` (no trailing segment)
        if pat.endswith("/**") and fnmatch(p, pat[:-3]):
            return True
        if pat.endswith("/**") and fnmatch(p, pat[:-1] + "*"):
            return True
    return False


# --------------------------------------------------------------------------- #
# Minimal YAML reader (the documented config subset only)
# --------------------------------------------------------------------------- #
# Supported: nested maps via indentation, `- ` lists (scalar items and inline
# `- key: value` maps), scalars (bool/null/int/float/quoted+bare strings) and
# `#` comments. Not supported (and not used by our config files): anchors,
# multi-line scalars, flow `{}`/`[]` collections.


class YAMLError(ValueError):
    pass


def _scalar(token: str):
    token = token.strip()
    if not token:
        return None
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
        inner = token[1:-1]
        if token[0] == '"':
            # process double-quote escapes (so regex configs like "\\d" -> \d).
            # Unknown escapes (e.g. \d) keep their backslash, matching YAML.
            out, i, esc = [], 0, {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r", "/": "/"}
            while i < len(inner):
                if inner[i] == "\\" and i + 1 < len(inner):
                    out.append(esc.get(inner[i + 1], "\\" + inner[i + 1]))
                    i += 2
                else:
                    out.append(inner[i]); i += 1
            inner = "".join(out)
        return inner
    # strip trailing inline comment from a bare scalar (before flow-list/scalar
    # detection, so `key: [a, b]  # note` still parses as a list)
    if "#" in token:
        token = token.split(" #", 1)[0].strip()
        if not token:
            return None
    # compact flow sequence: [a, b, c] (one level, no nested flow collections)
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part.strip()) for part in inner.split(",")]
    low = token.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "~", "none", ""):
        return None
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _strip_comment_line(raw: str) -> str:
    # drop full-line comments; keep `#` inside quotes alone (rare in our config)
    s = raw.rstrip("\n")
    stripped = s.lstrip()
    if stripped.startswith("#"):
        return ""
    return s


def _tokenize(text: str):
    out = []
    for raw in text.splitlines():
        line = _strip_comment_line(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        out.append((indent, line.strip()))
    return out


def _parse_block(lines, i, indent):
    """Return (value, next_index) for the block starting at lines[i]."""
    if i >= len(lines):
        return None, i
    if lines[i][1].startswith("- "):
        return _parse_list(lines, i, indent)
    if lines[i][1] == "-":
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines, i, indent):
    result = {}
    while i < len(lines):
        cur_indent, content = lines[i]
        if cur_indent < indent:
            break
        if cur_indent > indent:  # belongs to a deeper, already-consumed block
            raise YAMLError(f"unexpected indent at: {content!r}")
        if ":" not in content:
            raise YAMLError(f"expected 'key: value', got: {content!r}")
        key, _, rest = content.partition(":")
        key = key.strip().strip('"').strip("'")
        rest = rest.strip()
        if rest == "":
            # nested block (map or list) on following deeper lines, else null
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                child, i = _parse_block(lines, i + 1, lines[i + 1][0])
                result[key] = child
                continue
            result[key] = None
            i += 1
        else:
            result[key] = _scalar(rest)
            i += 1
    return result, i


def _parse_list(lines, i, indent):
    result = []
    while i < len(lines):
        cur_indent, content = lines[i]
        if cur_indent != indent or not (content == "-" or content.startswith("- ")):
            break
        item = content[1:].strip()  # drop leading '-'
        # Everything indented deeper than the dash belongs to this item.
        j = i + 1
        sub = []
        while j < len(lines) and lines[j][0] > indent:
            sub.append(lines[j])
            j += 1
        if item == "":
            value = _parse_block(sub, 0, sub[0][0])[0] if sub else None
        elif ":" in item and item[0] not in "\"'":
            # inline map item: '- key: value' plus any deeper sibling keys/lists
            virtual_indent = indent + 2
            synthetic = [(virtual_indent, item)] + sub
            value, _ = _parse_map(synthetic, 0, virtual_indent)
        else:
            value = _scalar(item)
        result.append(value)
        i = j
    return result, i


def read_yaml_str(text: str):
    lines = _tokenize(text)
    if not lines:
        return {}
    value, _ = _parse_block(lines, 0, lines[0][0])
    return value


def read_yaml(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return read_yaml_str(fh.read())


def load_config(name: str):
    """Read a config file from the skill's config/ dir, tolerating absence."""
    p = config_path(name)
    if not os.path.exists(p):
        return {}
    return read_yaml(p)


# --------------------------------------------------------------------------- #
# Minimal JSON-Schema validator (the subset our schemas use)
# --------------------------------------------------------------------------- #

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _type_ok(value, type_spec) -> bool:
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    return any(_TYPE_CHECKS.get(t, lambda v: True)(value) for t in types)


def validate(value, schema, path: str = "$"):
    """Return a list of human-readable validation errors ([] == valid)."""
    errors = []
    if not isinstance(schema, dict):
        return errors

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")
    if "type" in schema and not _type_ok(value, schema["type"]):
        errors.append(f"{path}: expected type {schema['type']}, got {type(value).__name__}")
        return errors  # further checks assume the type held

    if isinstance(value, str) and "pattern" in schema:
        if re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: {value!r} does not match /{schema['pattern']}/")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required property '{key}'")
        props = schema.get("properties", {})
        for key, subval in value.items():
            if key in props:
                errors += validate(subval, props[key], f"{path}.{key}")
            else:
                ap = schema.get("additionalProperties", True)
                if ap is False:
                    errors.append(f"{path}: additional property '{key}' not allowed")
                elif isinstance(ap, dict):
                    errors += validate(subval, ap, f"{path}.{key}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: has {len(value)} items < minItems {schema['minItems']}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                errors += validate(item, item_schema, f"{path}[{idx}]")
    return errors


def validate_against_file(value, schema_filename: str):
    return validate(value, read_json(schema_path(schema_filename)))


# --------------------------------------------------------------------------- #
# Secret detection / redaction
# --------------------------------------------------------------------------- #

REDACTION_RULES = [
    ("pem_private_key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")),
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_\-]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{12,}")),
    ("connection_string", re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqps?)://[^\s:'\"]+:[^\s:'\"@]+@[^\s'\"/]+")),
    ("ssh_authorized_key", re.compile(r"\bssh-(?:rsa|ed25519|dss)\s+[A-Za-z0-9+/]{60,}={0,3}")),
    ("secret_assignment", re.compile(r"(?im)\b(?:password|passwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token|client[_-]?secret|private[_-]?key)\b\s*[:=]\s*[\"']?[^\s\"']{6,}")),
]

_ENV_FILE_RE = re.compile(r"(^|/)[^/]*\.env(\.[\w.-]+)?$|\.(pem|key|p12|pfx|keystore)$|(^|/)id_(rsa|ed25519|dsa)$")


def looks_like_secret_file(path: str) -> bool:
    return bool(_ENV_FILE_RE.search(path or ""))


def redact(text: str):
    """Redact likely secrets. Returns (redacted_text, findings) where findings
    is a list of {type, count}. Original secret values are never returned."""
    if not text:
        return text, []
    findings = {}
    out = text
    for name, pattern in REDACTION_RULES:
        def _sub(_m, n=name):
            findings[n] = findings.get(n, 0) + 1
            return f"«REDACTED:{n}»"
        out = pattern.sub(_sub, out)
    return out, [{"type": k, "count": v} for k, v in sorted(findings.items())]


def contains_secret(text: str) -> bool:
    _, findings = redact(text or "")
    return bool(findings)


# --------------------------------------------------------------------------- #
# Self-check
# --------------------------------------------------------------------------- #

def _selfcheck():
    y = read_yaml_str(
        """
orchestrator:
  enabled: true
  retries: 2
codex:
  source_edits:
    default: false
    approved_frontend_patterns:
      - frontend/**
      - "**/*.css"
personas:
  - name: codebase-analyst
    agent: codex
  - name: git-steward
    agent: antigravity
"""
    )
    assert y["orchestrator"]["enabled"] is True, y
    assert y["orchestrator"]["retries"] == 2
    assert y["codex"]["source_edits"]["default"] is False
    assert y["codex"]["source_edits"]["approved_frontend_patterns"] == ["frontend/**", "**/*.css"]
    assert y["personas"][0] == {"name": "codebase-analyst", "agent": "codex"}, y["personas"]
    assert y["personas"][1]["agent"] == "antigravity"

    # nested list inside an inline-map list item (the personas.yaml shape)
    y2 = read_yaml_str(
        """
codex_personas:
  - name: codebase-analyst
    purpose: explain the system
    allowed_task_types:
      - CODEBASE_SEMANTIC_ANALYSIS
      - BLAST_RADIUS_ANALYSIS
    escalation_rules: escalate to claude on architecture
  - name: git-steward
    allowed_commands:
      - git status
      - git push
"""
    )
    a = y2["codex_personas"][0]
    assert a["name"] == "codebase-analyst", a
    assert a["allowed_task_types"] == ["CODEBASE_SEMANTIC_ANALYSIS", "BLAST_RADIUS_ANALYSIS"], a
    assert a["escalation_rules"] == "escalate to claude on architecture", a
    assert y2["codex_personas"][1]["allowed_commands"] == ["git status", "git push"], y2

    # compact flow sequences
    y3 = read_yaml_str("chains:\n  research: [codex, antigravity, claude]  # with a comment\n  empty: []\n")
    assert y3["chains"]["research"] == ["codex", "antigravity", "claude"], y3
    assert y3["chains"]["empty"] == [], y3

    # double-quote escape processing (regex configs): "\\d" -> \d, "\d" -> \d
    y4 = read_yaml_str('pats:\n  - "try again in (\\\\d+)"\n  - "\\\\b429\\\\b"\nlit: \'\\\\d\'\n')
    assert y4["pats"] == [r"try again in (\d+)", r"\b429\b"], y4["pats"]
    assert y4["lit"] == r"\\d", y4["lit"]   # single quotes stay literal

    schema = {
        "type": "object",
        "required": ["status", "count"],
        "properties": {
            "status": {"enum": ["success", "failed"]},
            "count": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    }
    assert validate({"status": "success", "count": 1}, schema) == []
    assert validate({"status": "nope", "count": -1}, schema)  # two errors
    assert validate({"status": "success", "count": 1, "x": 9}, schema)  # additional prop

    assert path_matches_any("frontend/app/Button.tsx", ["frontend/**"])
    assert path_matches_any("src/x.css", ["**/*.css"])
    assert not path_matches_any("backend/server.py", ["frontend/**", "**/*.css"])

    red, found = redact("token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345 and key sk-ant-aaaaaaaaaaaaaaaaaaaaaa")
    assert "ghp_" not in red and "sk-ant-" not in red, red
    types = {f["type"] for f in found}
    assert "github_token" in types and "anthropic_key" in types, found
    assert looks_like_secret_file(".env")
    assert looks_like_secret_file("config/prod.env.local")
    assert not looks_like_secret_file("src/app.tsx")
    print("OK _lib self-check passed")


if __name__ == "__main__":
    _selfcheck()
