import pytest
from agentflow import workspace


def test_write_overwrites_existing_text_file(tmp_path):
    (tmp_path / "hello.py").write_text("print('old')\n")
    result = workspace.write_text_file(tmp_path, "hello.py", "print('new')\n")
    assert result["content"] == "print('new')\n"
    assert result["truncated"] is False
    assert (tmp_path / "hello.py").read_text() == "print('new')\n"
    assert result["size"] == len("print('new')\n".encode("utf-8"))


def test_write_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        workspace.write_text_file(tmp_path, "nope.py", "x = 1\n")


def test_write_refuses_path_escape(tmp_path):
    (tmp_path / "inside.txt").write_text("ok")
    with pytest.raises(PermissionError):
        workspace.write_text_file(tmp_path, "../escape.txt", "nope")


def test_write_refuses_dotenv(tmp_path):
    (tmp_path / ".env").write_text("SECRET=1")
    with pytest.raises(PermissionError):
        workspace.write_text_file(tmp_path, ".env", "SECRET=2")


def test_write_refuses_non_previewable(tmp_path):
    (tmp_path / "blob.bin").write_bytes(b"\x00\x01")
    with pytest.raises(ValueError):
        workspace.write_text_file(tmp_path, "blob.bin", "text")


def test_write_refuses_oversized_content(tmp_path):
    (tmp_path / "big.txt").write_text("seed")
    huge = "a" * (workspace.PREVIEW_LIMIT_BYTES + 1)
    with pytest.raises(ValueError):
        workspace.write_text_file(tmp_path, "big.txt", huge)
