import io
import os
import re
import stat

from core.utils import atomic_write, get_dir_name, get_now_str, get_yaml_tool
from tests.logutil import check, check_true, expect_error, step


def test_get_dir_name_returns_parent_directory_name(tmp_path):
    """get_dir_name: 返回文件所在目录的名字"""
    path = tmp_path / "ioc-demo" / "ioc.yaml"
    step(f"get_dir_name({path})")
    check("目录名", get_dir_name(str(path)), "ioc-demo")


def test_get_dir_name_resolves_relative_path(tmp_path, monkeypatch):
    """get_dir_name: 相对路径先转成绝对路径再取目录名"""
    (tmp_path / "ioc-demo").mkdir()
    monkeypatch.chdir(tmp_path / "ioc-demo")
    step("进入 ioc-demo 目录,传入相对路径 'ioc.yaml'")
    check("目录名", get_dir_name("ioc.yaml"), "ioc-demo")


def test_get_now_str_format():
    """get_now_str: 时间格式为 YYYY/MM/DD HH:MM:SS"""
    now = get_now_str()
    step("get_now_str()")
    check_true(
        "符合 YYYY/MM/DD HH:MM:SS",
        re.fullmatch(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}", now),
        now,
    )


def test_yaml_tool_round_trip_keeps_key_order():
    """get_yaml_tool: 写出再读回,数据不变,键的顺序也不变"""
    data = {"b": 1, "a": {"y": [1, 2], "x": "text"}}
    yaml = get_yaml_tool()
    buf = io.StringIO()
    yaml.dump(data, buf)
    step("dump 后 load")
    check("键的顺序", list(yaml.load(buf.getvalue())), ["b", "a"])
    check("数据", yaml.load(buf.getvalue()), data)


def test_atomic_write_creates_file_with_default_mode(tmp_path):
    """atomic_write: 新文件内容正确,权限为 0o644"""
    path = tmp_path / "new.txt"
    atomic_write(str(path), "hello 测试")
    check("内容", path.read_text(encoding="utf-8"), "hello 测试")
    check("权限", oct(stat.S_IMODE(os.stat(path).st_mode)), oct(0o644))


def test_atomic_write_overwrite_keeps_existing_mode(tmp_path):
    """atomic_write: 覆盖已有文件时保持它原来的权限"""
    path = tmp_path / "exist.txt"
    path.write_text("old")
    os.chmod(path, 0o600)
    atomic_write(str(path), "new")
    check("内容", path.read_text(), "new")
    check("权限", oct(stat.S_IMODE(os.stat(path).st_mode)), oct(0o600))


def test_atomic_write_leaves_no_tmp_file(tmp_path):
    """atomic_write: 成功后目录里只有目标文件,没有 .tmp 残留"""
    atomic_write(str(tmp_path / "a.txt"), "x")
    check("目录内容", [p.name for p in tmp_path.iterdir()], ["a.txt"])


def test_atomic_write_failure_cleans_tmp_and_keeps_original(tmp_path, monkeypatch):
    """atomic_write: 替换失败时清理 .tmp,原文件保持不变"""
    path = tmp_path / "keep.txt"
    path.write_text("original")

    def boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    step("让 os.replace 失败,再写入 'changed'")
    with expect_error(OSError, "替换失败", match="replace failed"):
        atomic_write(str(path), "changed")
    monkeypatch.undo()
    check("原文件内容", path.read_text(), "original")
    check("目录内容", [p.name for p in tmp_path.iterdir()], ["keep.txt"])


def test_atomic_write_failure_when_tmp_is_already_gone(tmp_path, monkeypatch):
    """atomic_write: 失败时 .tmp 已经不在了,也只抛出原来的错误"""
    path = tmp_path / "keep.txt"
    path.write_text("original")

    def boom(src, dst):
        os.remove(src)
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    step("让 os.replace 先删掉 .tmp 再失败")
    with expect_error(OSError, "原来的错误没有被清理动作盖住", match="replace failed"):
        atomic_write(str(path), "changed")
    monkeypatch.undo()
    check("原文件内容", path.read_text(), "original")
    check("目录内容", [p.name for p in tmp_path.iterdir()], ["keep.txt"])


def test_atomic_write_into_a_missing_directory_fails_and_creates_nothing(tmp_path):
    """atomic_write: 目标目录不存在时报错,不会替你建目录"""
    target = tmp_path / "no-such-dir" / "x.txt"
    step(f"写入 {target}")
    with expect_error(FileNotFoundError, "目录不存在"):
        atomic_write(str(target), "x")
    check_true("目录没有被创建", not target.parent.exists())
