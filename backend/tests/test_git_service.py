from agentflow.git_service import parse_porcelain


def test_parse_branch_with_ahead_behind():
    out = "## main...origin/main [ahead 2, behind 1]\n M src/app.py\n"
    parsed = parse_porcelain(out)
    assert parsed["branch"] == "main"
    assert parsed["upstream"] == "origin/main"
    assert parsed["ahead"] == 2
    assert parsed["behind"] == 1


def test_parse_staged_and_unstaged_groups():
    out = (
        "## main\n"
        "M  staged_only.py\n"      # staged modify
        " M unstaged_only.py\n"    # unstaged modify
        "MM both.py\n"             # staged + unstaged
        "A  added.py\n"
        " D deleted.py\n"
        "?? brand_new.py\n"
    )
    parsed = parse_porcelain(out)
    staged = {f["path"]: f["code"] for f in parsed["staged"]}
    changes = {f["path"]: f["code"] for f in parsed["changes"]}
    assert staged == {"staged_only.py": "M", "both.py": "M", "added.py": "A"}
    assert changes == {"unstaged_only.py": "M", "both.py": "M", "deleted.py": "D", "brand_new.py": "U"}


def test_parse_rename_shows_new_name():
    out = "## dev\nR  old_name.py -> new_name.py\n"
    parsed = parse_porcelain(out)
    assert parsed["staged"] == [{"path": "new_name.py", "code": "R"}]
