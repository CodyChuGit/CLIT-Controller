"""opensrc routes — called directly over a fake binary (suite idiom)."""

from __future__ import annotations

import stat
import textwrap

from agentflow import opensrc_service
from agentflow.api import routes_opensrc

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
    else:
        print("")
    """
)


def _install(tmp_path, monkeypatch):
    src = tmp_path / "srcpkg"
    src.mkdir()
    (src / "index.js").write_text("export const parse = () => 1;\n")
    p = tmp_path / "opensrc"
    p.write_text(_FAKE_TMPL.format(src=str(src)))
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv(opensrc_service.BIN_ENV, str(p))
    return src


def test_status_reflects_binary(tmp_path, monkeypatch):
    monkeypatch.setenv(opensrc_service.BIN_ENV, str(tmp_path / "nope"))
    assert routes_opensrc.status()["available"] is False


def test_fetch_tree_file(tmp_path, monkeypatch):
    src = _install(tmp_path, monkeypatch)
    assert routes_opensrc.fetch(routes_opensrc.FetchBody(pkg="demo"))["path"] == str(src)
    entries = {e["path"] for e in routes_opensrc.tree("demo")["entries"]}
    assert "index.js" in entries
    assert routes_opensrc.file("demo", "index.js")["content"].startswith("export const parse")
