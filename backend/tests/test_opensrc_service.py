"""opensrc wrapper — tested against a fake binary + a real fixture source dir."""

from __future__ import annotations

import stat
import textwrap

import pytest
from agentflow import opensrc_service

_FAKE_TMPL = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    SRC = {src!r}
    if cmd == "path":
        print(SRC)
    elif cmd == "list":
        print(json.dumps([{{"name": "demo", "path": SRC}}]))
    elif cmd == "remove":
        target = sys.argv[2] if len(sys.argv) > 2 else ""
        if target != "demo":
            sys.stderr.write("not cached")
            sys.exit(1)
        open(SRC + "/.removed-" + target, "w").write("1")
    else:
        print("")
    """
)


def _install(tmp_path, monkeypatch):
    src = tmp_path / "srcpkg"
    (src / "sub").mkdir(parents=True)
    (src / "index.js").write_text("export const parse = () => 1;\n")
    (src / "sub" / "util.js").write_text("// util\nfunction helper() {}\n")
    p = tmp_path / "opensrc"
    p.write_text(_FAKE_TMPL.format(src=str(src)))
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv(opensrc_service.BIN_ENV, str(p))
    return src


def test_fetch_returns_path(tmp_path, monkeypatch):
    src = _install(tmp_path, monkeypatch)
    assert opensrc_service.fetch("demo") == str(src)


def test_list_cached(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch)
    assert opensrc_service.list_cached()[0]["name"] == "demo"


def test_tree_and_read(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch)
    paths = {e["path"] for e in opensrc_service.tree("demo")["entries"]}
    assert "index.js" in paths
    assert "sub/util.js" in paths
    assert opensrc_service.read("demo", "index.js")["content"].startswith("export const parse")


def test_read_rejects_path_escape(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch)
    with pytest.raises(opensrc_service.OpensrcUnavailable):
        opensrc_service.read("demo", "../../etc/passwd")


def test_search_finds_matches(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch)
    hits = opensrc_service.search("demo", "helper")
    assert any(h["path"] == "sub/util.js" for h in hits)


def test_remove_invokes_cli(tmp_path, monkeypatch):
    src = _install(tmp_path, monkeypatch)
    opensrc_service.remove("demo")
    assert (src / ".removed-demo").exists()


def test_remove_unknown_package_raises(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch)
    with pytest.raises(opensrc_service.OpensrcUnavailable):
        opensrc_service.remove("missing")


def test_missing_binary(tmp_path, monkeypatch):
    monkeypatch.setenv(opensrc_service.BIN_ENV, str(tmp_path / "nope"))
    with pytest.raises(opensrc_service.OpensrcUnavailable):
        opensrc_service.fetch("demo")
