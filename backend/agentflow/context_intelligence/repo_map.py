"""Repo map: deterministic file inventory with lightweight symbol detection.

Walking and reading go through ``workspace.py`` (its scan honors IGNORED_DIRS
and its reader enforces the .env refusal, size caps, and path confinement —
an audited security invariant). This module only filters and annotates.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .. import workspace
from .types import RepoMap, RepoMapEntry

# Local extension of workspace.IGNORED_DIRS: caches/generated output that the
# tree scan allows but a repo map should not rank (path-segment filtered here;
# the module-level set in workspace.py is shared state and stays untouched).
EXTRA_IGNORED_DIRS = frozenset({".agentflow", "coverage", ".ruff_cache", "dist-app", ".idea", ".vscode"})

MAX_MAP_FILES = 500
MAX_SYMBOLS_PER_FILE = 30

_LANGUAGES = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".swift": "swift",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".md": "markdown",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".css": "css",
    ".html": "html",
    ".sh": "shell",
}

_SYMBOL_LANGS = {"python", "typescript", "javascript"}

# Conservative TS/JS surface: exported functions/classes/consts only — no
# attempt at full parsing (the spec forbids it, and regex can't do it anyway).
_TS_SYMBOL_RE = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function\s*\*?\s*|class\s+|const\s+|let\s+|var\s+|interface\s+|type\s+|enum\s+)([A-Za-z_$][A-Za-z0-9_$]*)",
    re.MULTILINE,
)


def _flatten(nodes: list[dict], out: list[dict]) -> None:
    for node in nodes:
        if node["type"] == "dir":
            if node["name"] in EXTRA_IGNORED_DIRS:
                continue
            _flatten(node.get("children", []), out)
        else:
            out.append(node)


def python_symbols(source: str) -> list[str]:
    """Top-level defs/classes/assignments via ``ast`` (empty on syntax errors)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
        elif isinstance(node, ast.Assign):
            symbols.extend(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            symbols.append(node.target.id)
    return symbols[:MAX_SYMBOLS_PER_FILE]


def ts_symbols(source: str) -> list[str]:
    return list(dict.fromkeys(_TS_SYMBOL_RE.findall(source)))[:MAX_SYMBOLS_PER_FILE]


def _symbols_for(workspace_path: Path, rel_path: str, language: str) -> list[str]:
    if language not in _SYMBOL_LANGS:
        return []
    try:
        content = workspace.read_text_file(workspace_path, rel_path)["content"]
    except (PermissionError, FileNotFoundError, ValueError, OSError):
        return []
    return python_symbols(content) if language == "python" else ts_symbols(content)


def build_repo_map(workspace_path: Path) -> RepoMap:
    """Bounded, deterministic map of the workspace's text files with symbols."""
    tree = workspace.scan_tree(workspace_path)
    files: list[dict] = []
    _flatten(tree["children"], files)

    entries: list[RepoMapEntry] = []
    truncated = bool(tree["truncated"])
    for node in sorted(files, key=lambda n: n["path"]):
        if not node.get("previewable"):
            continue  # .env and binaries are refused by the workspace reader anyway
        if len(entries) >= MAX_MAP_FILES:
            truncated = True
            break
        language = _LANGUAGES.get(Path(node["name"]).suffix.lower(), "")
        entries.append(
            RepoMapEntry(
                path=node["path"],
                size=int(node.get("size", 0)),
                language=language,
                symbols=_symbols_for(workspace_path, node["path"], language),
            )
        )
    return RepoMap(root=tree["root"], entries=entries, fileCount=len(entries), truncated=truncated)
