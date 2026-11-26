import os
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from core.exceptions import VersionedDirectoryError
from core.versioned_directory import VersionedDirectory
from tests.logutil import check, check_true, expect_error, step


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    """A repository over a directory with a config file and two source files, with
    one commit made"""
    d = tmp_path / "ioc-a"
    write(d / "ioc-config.yaml", "basic:\n  name: ioc-a\n")
    write(d / "src" / "a.db", "record 1\n")
    write(d / "src" / "a.proto", "message A {}\n")
    r = VersionedDirectory(d)
    r.init(ignore=["build/"])
    r.commit("first")
    return r


def test_init_makes_a_repository_only_once(tmp_path):
    """init: 目录变成仓库,.gitignore 写进去;已经是仓库就报 FileExistsError,目录不存在报 FileNotFoundError"""
    d = tmp_path / "ioc-a"
    d.mkdir()
    r = VersionedDirectory(d)
    check("init 前", r.is_initialized(), False)
    r.init(ignore=["build/", "*.log"])
    check("init 后", r.is_initialized(), True)
    check(".gitignore", (d / ".gitignore").read_text(), "build/\n*.log\n")
    check("还没有提交", r.head(), None)
    with expect_error(FileExistsError, "再 init 一次"):
        r.init()
    with expect_error(FileNotFoundError, "目录不存在"):
        VersionedDirectory(tmp_path / "nope").init()


def test_commit_returns_the_commit_id_and_makes_none_when_nothing_changed(repo):
    """commit: 返回提交 id;没有变化时不产生新提交,返回原来的 id"""
    first = repo.head()
    check_true("第一次提交有 id", bool(first))
    check("没有变化", repo.commit("again"), first)
    check("head 没变", repo.head(), first)
    write(repo.path + "/src/a.db", "record 1\nrecord 2\n")
    second = repo.commit("edit")
    check_true("有变化就是新提交", second != first)
    check("head 是新的", repo.head(), second)


def test_first_commit_is_made_even_for_an_empty_directory(tmp_path):
    """commit: 空目录第一次提交也有 id,这样总有一个快照可以记"""
    r = VersionedDirectory(tmp_path)
    r.init()
    check_true("有 id", bool(r.commit("empty")))


def test_history_lists_the_commits_newest_first_with_their_time(tmp_path):
    """history: 没有提交是空列表;有提交按从新到旧列出完整 id、时间(秒)和说明;没有变化的 commit 不多出一条"""
    d = tmp_path / "ioc-a"
    write(d / "f.txt", "1\n")
    r = VersionedDirectory(d)
    r.init()
    check("还没有提交", r.history(), [])
    before = datetime.now().replace(microsecond=0)
    first = r.commit("first")
    write(d / "f.txt", "2\n")
    second = r.commit("second\n\nbody is not shown")
    r.commit("nothing changed")
    restored = r.restore(first)
    after = datetime.now()
    logs = r.history()
    check("从新到旧的 id", [log["id"] for log in logs], [restored, second, first])
    check("id 是完整的", [len(log["id"]) for log in logs], [40, 40, 40])
    check("说明只取第一行", [log["message"] for log in logs], [f"restore {first[:8]}", "second", "first"])
    for log in logs:
        check_true(f"{log['message']} 的时间是 datetime", isinstance(log["time"], datetime))
        check_true(f"{log['message']} 的时间在这次测试期间", before <= log["time"] <= after)
        check("精确到秒", log["time"].microsecond, 0)
    check_true("时间不倒序", logs[0]["time"] >= logs[1]["time"] >= logs[2]["time"])


def test_show_history_prints_one_line_a_commit(tmp_path, capsys):
    """show_history: 没有提交时说一句没有;有提交时每个提交一行,从新到旧,是 时间、8 位 id、说明"""
    d = tmp_path / "ioc-a"
    write(d / "f.txt", "1\n")
    r = VersionedDirectory(d)
    r.init()
    r.show_history()
    check("没有提交", capsys.readouterr().out, "No commits yet.\n")
    first = r.commit("first")
    write(d / "f.txt", "2\n")
    second = r.commit("second")
    r.show_history()
    lines = capsys.readouterr().out.splitlines()
    check("两行", len(lines), 2)
    commits = r.history()
    for line, entry in zip(lines, commits):
        check(f"{entry['message']} 那一行", line, f"{entry['time']:%Y-%m-%d %H:%M:%S}  {entry['id'][:8]}  {entry['message']}")
    check("新的在前", [line.split("  ")[1] for line in lines], [second[:8], first[:8]])
    step("打印出来的 id 可以直接拿去 restore")
    write(d / "f.txt", "3\n")
    r.restore(lines[1].split("  ")[1])
    check("回到 first", Path(d, "f.txt").read_text(), "1\n")


def test_history_without_a_repository_raises(tmp_path):
    """history: 目录不是仓库时报 VersionedDirectoryError,不是返回空列表"""
    with expect_error(VersionedDirectoryError, "不是仓库"):
        VersionedDirectory(tmp_path).history()


def test_status_reports_modified_added_and_deleted_files(repo):
    """status: 修改、新增、删除的文件分开列出,路径相对于目录并排序;没动过是空的"""
    check("干净", repo.status(), {"modified": [], "added": [], "deleted": []})
    check("is_clean", repo.is_clean(), True)
    write(repo.path + "/ioc-config.yaml", "basic:\n  name: changed\n")
    write(repo.path + "/src/new.db", "x\n")
    write(repo.path + "/src/sub/deep.txt", "y\n")
    os.remove(repo.path + "/src/a.proto")
    check(
        "有改动",
        repo.status(),
        {
            "modified": ["ioc-config.yaml"],
            "added": ["src/new.db", "src/sub/deep.txt"],
            "deleted": ["src/a.proto"],
        },
    )
    check("is_clean", repo.is_clean(), False)


def test_status_sees_a_rename_as_a_delete_and_an_add(repo):
    """status: 改名显示成一个删除加一个新增"""
    os.rename(repo.path + "/src/a.db", repo.path + "/src/b.db")
    check(
        "改名",
        repo.status(),
        {"modified": [], "added": ["src/b.db"], "deleted": ["src/a.db"]},
    )


def test_status_ignores_what_gitignore_names(repo):
    """status: .gitignore 里列的东西不算改动"""
    write(repo.path + "/build/out.o", "binary\n")
    check("干净", repo.is_clean(), True)


def test_status_notices_a_change_that_was_staged_by_hand(repo):
    """status: 有人自己 git add 过,也还是算改动"""
    write(repo.path + "/src/a.db", "other\n")
    subprocess.run(["git", "-C", repo.path, "add", "."], check=True, capture_output=True)
    check("modified", repo.status()["modified"], ["src/a.db"])


def test_file_names_with_spaces_and_non_ascii_come_back_as_they_are(repo):
    """status: 带空格和中文的文件名原样返回"""
    write(repo.path + "/src/带 空格.db", "x\n")
    check("added", repo.status()["added"], ["src/带 空格.db"])


def test_a_file_name_that_is_not_utf8_comes_back_the_way_os_listdir_gives_it(repo):
    """status: 文件名不是 UTF-8(比如 GBK)时不报错,路径按 os.listdir 的方式返回,拿得去打开;commit 也照常"""
    with open(os.fsencode(repo.path) + b"/src/\xd6\xd0\xce\xc4.db", "w") as f:
        f.write("x\n")
    added = repo.status()["added"]
    check("added", added, [os.fsdecode(b"src/\xd6\xd0\xce\xc4.db")])
    check_true("能拿去打开", os.path.isfile(os.path.join(repo.path, added[0])))
    repo.commit("odd name")
    check("提交之后没有改动", repo.is_clean(), True)


def test_an_error_message_never_holds_bytes_that_are_not_utf8(repo):
    """_git: git 报错时带着不是 UTF-8 的文件名,错误信息里也是能存的文本"""
    with expect_error(VersionedDirectoryError, "git add 一个不存在的、名字不是 UTF-8 的文件") as info:
        repo._git("add", "--", os.fsdecode(b"no-\xff-such"))
    message = str(info.value)
    check_true("信息是能存的文本", message.encode("utf-8") is not None)
    check_true("说了是哪个命令", message.startswith("git add failed"))


def test_restore_brings_back_the_files_of_a_commit_and_keeps_the_history(repo):
    """restore: 改过的、删掉的、新增的文件都回到快照的样子,历史保留,结果记成新提交"""
    snap = repo.head()
    write(repo.path + "/ioc-config.yaml", "broken\n")
    os.remove(repo.path + "/src/a.proto")
    write(repo.path + "/src/extra.db", "x\n")
    write(repo.path + "/build/out.o", "binary\n")
    edited = repo.commit("edited")
    step("又改了一点没提交的")
    write(repo.path + "/src/a.db", "uncommitted\n")
    restored = repo.restore(snap)
    check_true("是新提交", restored not in (snap, edited))
    check("head", repo.head(), restored)
    check("干净", repo.is_clean(), True)
    check("配置回来了", Path(repo.path, "ioc-config.yaml").read_text(), "basic:\n  name: ioc-a\n")
    check("a.db 回来了", Path(repo.path, "src/a.db").read_text(), "record 1\n")
    check_true("删掉的回来了", Path(repo.path, "src/a.proto").exists())
    check_true("新增的没了", not Path(repo.path, "src/extra.db").exists())
    check_true("被忽略的不动", Path(repo.path, "build/out.o").exists())
    log = subprocess.run(
        ["git", "-C", repo.path, "log", "--format=%H"], capture_output=True, text=True, check=True
    ).stdout.split()
    check_true("旧提交都还在", {snap, edited} <= set(log))


def test_restore_to_the_state_it_already_is_makes_no_commit(repo):
    """restore: 已经是那个样子就不产生新提交"""
    snap = repo.head()
    check("返回原 id", repo.restore(snap), snap)
    check("head", repo.head(), snap)


def test_restore_accepts_a_short_id_and_rejects_bad_ones(repo):
    """restore: 接受缩短的 id;不是 id 的写法报 ValueError,没有这个提交报 VersionedDirectoryError"""
    snap = repo.head()
    write(repo.path + "/src/a.db", "x\n")
    repo.restore(snap[:8])
    check("内容回来了", Path(repo.path, "src/a.db").read_text(), "record 1\n")
    for bad in ["--hard", "HEAD", "main", "", "zz", "abc"]:
        with expect_error(ValueError, f"{bad!r} 不是提交 id"):
            repo.restore(bad)
    with expect_error(VersionedDirectoryError, "没有这个提交"):
        repo.restore("0" * 40)


def test_a_directory_without_a_repository_is_not_taken_for_one_above_it(tmp_path):
    """VersionedDirectory: 目录自己没有 .git 时报错,不会去用上一层目录的仓库"""
    outer = VersionedDirectory(tmp_path)
    outer.init()
    inner = tmp_path / "ioc-a"
    write(inner / "f.txt", "x\n")
    r = VersionedDirectory(inner)
    check("is_initialized", r.is_initialized(), False)
    with expect_error(VersionedDirectoryError, "status"):
        r.status()
    with expect_error(VersionedDirectoryError, "head"):
        r.head()
    check("上一层没有被动过", outer.head(), None)


def test_the_users_git_configuration_is_not_used(repo, tmp_path, monkeypatch):
    """VersionedDirectory: 用户全局的 git 配置(强制签名、钩子目录)不影响提交"""
    gitconfig = tmp_path / "gitconfig"
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    marker = tmp_path / "hook-ran"
    hook = hooks / "pre-commit"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
    hook.chmod(0o755)
    gitconfig.write_text(f"[commit]\n\tgpgsign = true\n[core]\n\thooksPath = {hooks}\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    write(repo.path + "/src/a.db", "x\n")
    check_true("提交成功", bool(repo.commit("edit")))
    check_true("钩子没有运行", not marker.exists())


def test_commits_are_made_as_iocdock_whatever_the_machine_is_set_to(repo):
    """commit: 作者固定是 iocdock,不看机器上有没有配置 user.name"""
    author = subprocess.run(
        ["git", "-C", repo.path, "log", "-1", "--format=%an <%ae>"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    check("作者", author, "iocdock <iocdock@localhost>")


def test_git_variables_of_the_process_do_not_reach_git(repo, tmp_path, monkeypatch):
    """_git: 进程环境里的 GIT_* 变量(作者、索引文件、仓库位置)一个都不传给 git,提交照常记在自己的仓库里"""
    other = tmp_path / "other"
    other.mkdir()
    for name, value in {
        "GIT_AUTHOR_NAME": "someone",
        "GIT_AUTHOR_EMAIL": "someone@example.com",
        "GIT_COMMITTER_NAME": "someone",
        "GIT_COMMITTER_EMAIL": "someone@example.com",
        "GIT_INDEX_FILE": str(other / "index"),
        "GIT_DIR": str(other / ".git"),
        "GIT_WORK_TREE": str(other),
    }.items():
        monkeypatch.setenv(name, value)
    write(repo.path + "/src/a.db", "changed\n")
    commit = repo.commit("edit")
    check("记在自己的仓库里", repo.head(), commit)
    check("历史两条", len(repo.history()), 2)
    check("干净", repo.is_clean(), True)
    people = repo._git("log", "-1", "--format=%an <%ae> %cn <%ce>").stdout.strip()
    check("作者和提交者", people, "iocdock <iocdock@localhost> iocdock <iocdock@localhost>")
    check_true("没有碰别处的索引", not (other / "index").exists())
    check_true("没有在别处建仓库", not (other / ".git").exists())


def test_the_global_ignore_and_attributes_files_of_the_user_are_not_read(repo, tmp_path, monkeypatch):
    """_git: 用户全局的忽略文件和属性文件($XDG_CONFIG_HOME/git/ignore、attributes)不起作用,哪些文件被记录只看目录自己的 .gitignore"""
    xdg = tmp_path / "xdg"
    write(xdg / "git" / "ignore", "*.secret\n")
    write(xdg / "git" / "attributes", "*.db eol=crlf\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    write(repo.path + "/token.secret", "x\n")
    check("全局忽略文件不起作用", repo.status()["added"], ["token.secret"])
    attr = repo._git("check-attr", "eol", "--", "src/a.db").stdout.strip()
    check("全局属性文件不起作用", attr, "src/a.db: eol: unspecified")
    step("目录自己的 .gitignore 仍然起作用")
    write(repo.path + "/build/out.o", "binary\n")
    check("build/ 还是被忽略", repo.status()["added"], ["token.secret"])


def test_a_git_that_is_not_installed_is_reported_as_such(repo, monkeypatch):
    """VersionedDirectory: 找不到 git 命令时报 VersionedDirectoryError,说明是没装"""
    monkeypatch.setenv("PATH", "/nonexistent")
    with expect_error(VersionedDirectoryError, "没有 git"):
        repo.status()


def test_a_command_that_takes_too_long_is_reported(repo):
    """VersionedDirectory: git 超过 timeout 报 VersionedDirectoryError"""
    repo.timeout = 0.0001
    with expect_error(VersionedDirectoryError, "超时"):
        repo.status()


def test_status_does_not_rewrite_the_index(repo):
    """status: 只是看,不写 .git/index(不会去占 index.lock),这样一直在跑的 refresh 不会妨碍别人的 add 和 commit"""
    f = Path(repo.path, "src", "a.db")
    os.utime(f, (1, 1))  # only the time stamp is different: git would like to write that down in the index
    index = Path(repo.path, ".git", "index")
    before = index.read_bytes(), index.stat().st_mtime_ns
    check("status 照常能用", repo.is_clean(), True)
    check("index 没被写", (index.read_bytes(), index.stat().st_mtime_ns), before)
