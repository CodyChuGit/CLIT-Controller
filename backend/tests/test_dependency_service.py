"""dependency_service — workspace deps -> opensrc-resolved local source paths."""

from __future__ import annotations

import json

from agentflow import dependency_service


def _ws(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"zod": "^3"}, "devDependencies": {"vitest": "^2"}})
    )
    sub = tmp_path / "backend"
    sub.mkdir()
    (sub / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0"\n'
        'dependencies = ["fastapi[all]>=0.110,<1", "uvicorn >=0.30"]\n'
        "[project.optional-dependencies]\n"
        'dev = ["pytest>=8.0"]\n'
    )
    (sub / "requirements.txt").write_text("# comment\nrequests==2.32.0\n-r other.txt\n")
    (sub / "Cargo.toml").write_text('[package]\nname = "x"\n[dependencies]\nserde = "1"\n')
    return tmp_path


def test_discovers_root_and_subdir_manifests(tmp_path):
    found = dependency_service._discover_manifests(_ws(tmp_path))
    rels = [str(p.relative_to(tmp_path)) for p in found]
    # Root first, then subdirs alphabetically; fixed filename order within each dir.
    assert rels == [
        "package.json",
        "backend/Cargo.toml",
        "backend/pyproject.toml",
        "backend/requirements.txt",
    ]


def test_parses_all_ecosystems_normalized(tmp_path):
    ws = _ws(tmp_path)
    deps = dependency_service._parse_manifests(dependency_service._discover_manifests(ws))
    assert ("zod", "zod") in deps  # npm -> bare name
    assert ("vitest", "vitest") in deps  # devDependencies included
    assert ("serde", "crates:serde") in deps
    assert ("fastapi", "pypi:fastapi") in deps  # extras + specifiers stripped
    assert ("uvicorn", "pypi:uvicorn") in deps
    assert ("pytest", "pypi:pytest") in deps  # optional-dependencies included
    assert ("requests", "pypi:requests") in deps
    names = [n for n, _ in deps]
    assert "-r other.txt" not in str(deps)  # directives skipped
    assert len(names) == len(set(names))  # deduped


def test_cap_at_60(tmp_path):
    many = {f"pkg{i}": "^1" for i in range(70)}
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": many}))
    deps = dependency_service._parse_manifests([tmp_path / "package.json"])
    assert len(deps) == 60


def test_no_manifests_is_empty(tmp_path):
    assert dependency_service._discover_manifests(tmp_path) == []
