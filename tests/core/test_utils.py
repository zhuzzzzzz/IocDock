import os
import re
import stat

import pytest

from core.utils import atomic_write, get_dir_name, get_now_str, get_yaml_tool


def test_get_dir_name_returns_parent_directory_name(tmp_path):
    path = tmp_path / "ioc-demo" / "ioc.yaml"
    assert get_dir_name(str(path)) == "ioc-demo"


def test_get_dir_name_resolves_relative_path(tmp_path, monkeypatch):
    (tmp_path / "ioc-demo").mkdir()
    monkeypatch.chdir(tmp_path / "ioc-demo")
    assert get_dir_name("ioc.yaml") == "ioc-demo"


def test_get_now_str_format():
    assert re.fullmatch(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}", get_now_str())


def test_yaml_tool_round_trip_keeps_key_order():
    import io

    data = {"b": 1, "a": {"y": [1, 2], "x": "text"}}
    yaml = get_yaml_tool()
    buf = io.StringIO()
    yaml.dump(data, buf)
    assert list(yaml.load(buf.getvalue())) == ["b", "a"]
    assert yaml.load(buf.getvalue()) == data


def test_atomic_write_creates_file_with_default_mode(tmp_path):
    path = tmp_path / "new.txt"
    atomic_write(str(path), "hello 测试")
    assert path.read_text(encoding="utf-8") == "hello 测试"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o644


def test_atomic_write_overwrite_keeps_existing_mode(tmp_path):
    path = tmp_path / "exist.txt"
    path.write_text("old")
    os.chmod(path, 0o600)
    atomic_write(str(path), "new")
    assert path.read_text() == "new"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_atomic_write_leaves_no_tmp_file(tmp_path):
    atomic_write(str(tmp_path / "a.txt"), "x")
    assert [p.name for p in tmp_path.iterdir()] == ["a.txt"]


def test_atomic_write_failure_cleans_tmp_and_keeps_original(tmp_path, monkeypatch):
    path = tmp_path / "keep.txt"
    path.write_text("original")

    def boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="replace failed"):
        atomic_write(str(path), "changed")
    monkeypatch.undo()
    assert path.read_text() == "original"
    assert [p.name for p in tmp_path.iterdir()] == ["keep.txt"]
