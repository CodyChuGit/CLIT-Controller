"""Workspace file tree scanning and safe text-file reading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    "DerivedData",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

TEXT_EXTENSIONS = {
    ".swift", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".css", ".html",
    ".py", ".sh", ".yml", ".yaml", ".toml", ".rs", ".go", ".java", ".kt",
    ".c", ".cpp", ".h", ".hpp", ".txt",
}

# Extensionless / special files that are safe to preview.
SPECIAL_FILENAMES = {".env.example", ".gitignore", "Makefile", "Dockerfile", "LICENSE", "README"}

PREVIEW_LIMIT_BYTES = 512 * 1024
MAX_TREE_DEPTH = 8
MAX_FILES = 2000


def _is_previewable(name: str) -> bool:
    if name in SPECIAL_FILENAMES:
        return True
    if name.startswith(".env"):
        return name == ".env.example"  # never preview .env / .env.local / ...
    return Path(name).suffix.lower() in TEXT_EXTENSIONS


def scan_tree(workspace: Path) -> dict:
    """Return a nested tree, bounded by depth/file-count limits."""
    workspace = workspace.resolve()
    count = 0
    truncated = False

    def walk(directory: Path, rel: str, depth: int) -> list[dict]:
        nonlocal count, truncated
        if depth > MAX_TREE_DEPTH or count >= MAX_FILES:
            truncated = True
            return []
        try:
            entries = sorted(
                os.scandir(directory),
                key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()),
            )
        except OSError:
            return []
        nodes: list[dict] = []
        for entry in entries:
            if count >= MAX_FILES:
                truncated = True
                break
            rel_path = f"{rel}/{entry.name}" if rel else entry.name
            if entry.is_dir(follow_symlinks=False):
                if entry.name in IGNORED_DIRS:
                    continue
                # task log folders can grow large; keep them out of the tree
                if entry.name == "logs" and "/.agentflow/tasks/" in f"/{rel_path}/":
                    continue
                children = walk(Path(entry.path), rel_path, depth + 1)
                nodes.append({"name": entry.name, "path": rel_path, "type": "dir", "children": children})
            elif entry.is_file(follow_symlinks=False):
                count += 1
                try:
                    size = entry.stat(follow_symlinks=False).st_size
                except OSError:
                    size = 0
                nodes.append(
                    {
                        "name": entry.name,
                        "path": rel_path,
                        "type": "file",
                        "size": size,
                        "previewable": _is_previewable(entry.name),
                    }
                )
        return nodes

    children = walk(workspace, "", 1)
    return {"root": str(workspace), "children": children, "fileCount": count, "truncated": truncated}


def read_text_file(workspace: Path, rel_path: str) -> dict:
    """Read a text file safely; refuses .env, binary, and out-of-workspace paths."""
    workspace = workspace.resolve()
    target = (workspace / rel_path).resolve()
    if not str(target).startswith(str(workspace) + os.sep) and target != workspace:
        raise PermissionError("Path escapes the workspace")
    if not target.is_file():
        raise FileNotFoundError(rel_path)

    name = target.name
    if name.startswith(".env") and name != ".env.example":
        raise PermissionError(".env files are never previewed")
    if not _is_previewable(name):
        raise ValueError(f"Not a previewable text file: {name}")

    size = target.stat().st_size
    with open(target, "rb") as f:
        raw = f.read(PREVIEW_LIMIT_BYTES)
    if b"\x00" in raw[:8192]:
        raise ValueError("Binary file (refusing preview)")

    return {
        "path": rel_path,
        "size": size,
        "truncated": size > PREVIEW_LIMIT_BYTES,
        "content": raw.decode("utf-8", errors="replace"),
    }
