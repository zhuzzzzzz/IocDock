import fcntl
import glob
import os
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import pytest

from core.exceptions import (
    GitTimeoutError,
    GitUnavailableError,
    UncommittedChangesError,
    VersionedDirectoryError,
)
from core.versioned_directory import DEFAULT_HISTORY_LIMIT, DirectoryState, VersionedDirectory
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
    r.restore(lines[1].split("  ")[1], force=True)
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


NOTHING = {"modified": [], "added": [], "deleted": []}


def test_check_says_there_is_no_repository(tmp_path):
    """check: 目录里没有 .git 是 NO_REPOSITORY,不抛错;每次返回的 changes 是各自的,改一个不影响下一个"""
    report = VersionedDirectory(tmp_path).check()
    check("state", report["state"], DirectoryState.NO_REPOSITORY)
    check("state 也等于字符串", report["state"], "no_repository")
    check("其余是空的", (report["head"], report["changes"], report["error"]), (None, NOTHING, ""))
    report["changes"]["added"].append("x")
    check("下一个不受影响", VersionedDirectory(tmp_path).check()["changes"], NOTHING)


def test_check_says_a_repository_git_cannot_read_is_unreadable(tmp_path, monkeypatch):
    """check: .git 在但 git 读不了、或者 git 没装,是 UNREADABLE 并带着原因,不抛错"""
    (tmp_path / ".git").mkdir()
    report = VersionedDirectory(tmp_path).check()
    check("state", report["state"], DirectoryState.UNREADABLE)
    check_true("有原因", "not a git repository" in report["error"], report["error"])
    check("没有 head 和改动", (report["head"], report["changes"]), (None, NOTHING))
    step("git 没装")
    monkeypatch.setenv("PATH", "/nonexistent")
    report = VersionedDirectory(tmp_path).check()
    check("state", report["state"], DirectoryState.UNREADABLE)
    check_true("说没装", "not installed" in report["error"], report["error"])


def test_check_says_a_repository_without_a_commit_has_no_commit_but_lists_the_files(tmp_path):
    """check: 还没有提交是 NO_COMMIT,head 是 None,目录里的文件都在 added 里"""
    write(tmp_path / "ioc-config.yaml", "a: 1\n")
    r = VersionedDirectory(tmp_path)
    r.init()
    report = r.check()
    check("state", report["state"], DirectoryState.NO_COMMIT)
    check("head", report["head"], None)
    check("改动", report["changes"], {"modified": [], "added": ["ioc-config.yaml"], "deleted": []})
    check("没有错", report["error"], "")


def test_check_reports_the_latest_commit_and_what_differs_from_it(repo):
    """check: 有提交是 OK,带着 head 和相对它的改动;干净时改动是空的"""
    report = repo.check()
    check("干净的 state", report["state"], DirectoryState.OK)
    check("干净的 head", report["head"], repo.head())
    check("干净的改动", report["changes"], NOTHING)
    write(repo.path + "/ioc-config.yaml", "changed\n")
    os.remove(repo.path + "/src/a.proto")
    write(repo.path + "/src/new.db", "x\n")
    report = repo.check()
    check("有改动的 state", report["state"], DirectoryState.OK)
    check("改动", report["changes"], repo.status())
    check(
        "三类",
        report["changes"],
        {"modified": ["ioc-config.yaml"], "added": ["src/new.db"], "deleted": ["src/a.proto"]},
    )


def test_check_reads_again_when_a_commit_comes_between_the_two_looks(repo, monkeypatch):
    """check: head 在看改动前后不一样(中间有人提交了)就重新看,直到一致,这样 head 和改动是同一个提交的"""
    heads = iter(["a", "b", "b", "b"])
    looked = []
    real_status = repo.status
    monkeypatch.setattr(repo, "head", lambda: next(heads))
    monkeypatch.setattr(repo, "status", lambda: looked.append(1) or real_status())
    report = repo.check()
    check("head 是后来那个", report["head"], "b")
    check("看了两次改动", len(looked), 2)


def test_check_gives_up_after_a_few_tries_when_commits_keep_coming(repo, monkeypatch):
    """check: 一直有人提交也不会没完没了,看三次就用最后一次的"""
    counter = iter(range(100))
    looked = []
    real_status = repo.status
    monkeypatch.setattr(repo, "head", lambda: str(next(counter)))
    monkeypatch.setattr(repo, "status", lambda: looked.append(1) or real_status())
    report = repo.check()
    check("state", report["state"], DirectoryState.OK)
    check("看了三次改动", len(looked), 3)
    check("head 是最后一次看的", report["head"], "4")


def test_check_says_so_when_looking_at_the_changes_fails(repo, monkeypatch):
    """check: 看改动时 git 出错是 UNREADABLE,带着 git 的话"""

    def broken():
        raise VersionedDirectoryError("git on fire")

    monkeypatch.setattr(repo, "status", broken)
    report = repo.check()
    check("state", report["state"], DirectoryState.UNREADABLE)
    check("error", report["error"], "git on fire")


def test_restore_brings_back_the_files_of_a_commit_and_keeps_the_history(repo):
    """restore: 改过的、删掉的、新增的文件都回到快照的样子,历史保留,结果记成新提交"""
    snap = repo.head()
    write(repo.path + "/ioc-config.yaml", "broken\n")
    os.remove(repo.path + "/src/a.proto")
    write(repo.path + "/src/extra.db", "x\n")
    write(repo.path + "/build/out.o", "binary\n")
    edited = repo.commit("edited")
    step("又改了一点没提交的,force=True 把它也丢掉")
    write(repo.path + "/src/a.db", "uncommitted\n")
    restored = repo.restore(snap, force=True)
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
    repo.restore(snap[:8], force=True)
    check("内容回来了", Path(repo.path, "src/a.db").read_text(), "record 1\n")
    for bad in ["--hard", "HEAD", "main", "", "zz", "abc"]:
        with expect_error(ValueError, f"{bad!r} 不是提交 id"):
            repo.restore(bad)
    with expect_error(VersionedDirectoryError, "没有这个提交"):
        repo.restore("0" * 40)


def test_restore_refuses_to_throw_away_changes_that_were_not_committed(repo):
    """restore: 目录里有没提交的改动时报 UncommittedChangesError、什么都不动,force=True 才覆盖"""
    snap = repo.head()
    write(repo.path + "/src/a.db", "record 1\nrecord 2\n")
    edited = repo.commit("edited")
    step("再改一点,还没提交")
    write(repo.path + "/src/a.db", "unsaved\n")
    write(repo.path + "/src/new.db", "new\n")
    with expect_error(UncommittedChangesError, "有没提交的改动") as info:
        repo.restore(snap)
    check(
        "changes",
        info.value.changes,
        {"modified": ["src/a.db"], "added": ["src/new.db"], "deleted": []},
    )
    check_true("信息里有文件名", "src/a.db" in str(info.value) and "src/new.db" in str(info.value))
    check("a.db 没动", Path(repo.path, "src/a.db").read_text(), "unsaved\n")
    check_true("new.db 还在", Path(repo.path, "src/new.db").exists())
    check("head 没变", repo.head(), edited)
    step("force=True 就覆盖")
    restored = repo.restore(snap, force=True)
    check("head 是新提交", repo.head(), restored)
    check_true("是新提交", restored not in (snap, edited))
    check("a.db 回来了", Path(repo.path, "src/a.db").read_text(), "record 1\n")
    check_true("new.db 没了", not Path(repo.path, "src/new.db").exists())


def test_restore_to_the_latest_commit_with_force_throws_the_changes_away(repo):
    """restore: 回到最新提交并且 force=True,就是把没提交的改动丢掉,不产生新提交"""
    head = repo.head()
    write(repo.path + "/src/a.db", "unsaved\n")
    write(repo.path + "/src/new.db", "new\n")
    with expect_error(UncommittedChangesError, "不带 force 会拒绝"):
        repo.restore(head)
    check("force", repo.restore(head, force=True), head)
    check("干净", repo.is_clean(), True)
    check("没有新提交", len(repo.history()), 1)


def test_restore_checks_the_commit_before_it_looks_at_the_changes(repo):
    """restore: 哈希写错时报哈希的错,不是被没提交的改动盖住"""
    write(repo.path + "/src/a.db", "unsaved\n")
    with expect_error(ValueError, "不是提交 id"):
        repo.restore("zz")
    with expect_error(VersionedDirectoryError, "没有这个提交") as info:
        repo.restore("0" * 40)
    check_true("不是 UncommittedChangesError", not isinstance(info.value, UncommittedChangesError))


def test_the_message_about_uncommitted_changes_is_text_that_can_be_stored(repo):
    """restore: 文件名不是 UTF-8 时,UncommittedChangesError 的信息也是能存的文本,changes 里仍是原样的名字"""
    odd = os.fsdecode(b"odd-\xff.db")
    write(repo.path + "/" + odd, "x\n")
    with expect_error(UncommittedChangesError, "名字不是 UTF-8 的文件") as info:
        repo.restore(repo.head())
    check_true("信息能存", bool(str(info.value).encode("utf-8")))
    check("changes 里是原样的名字", info.value.changes["added"], [odd])


def test_commit_needs_a_message_and_says_so_before_it_does_anything(repo):
    """commit: 说明是空的、全是空白或不是字符串时报 ValueError,在 git add 之前,什么都没暂存;没有变化时也一样"""
    write(repo.path + "/src/a.db", "changed\n")
    for bad in ["", "   ", "\n", None, 123]:
        with expect_error(ValueError, f"{bad!r} 不是提交说明"):
            repo.commit(bad)
    check("什么都没暂存", repo._git("diff", "--cached", "--name-only").stdout, "")
    check("没有新提交", len(repo.history()), 1)
    repo.restore(repo.head(), force=True)
    step("没有变化时也要先检查说明")
    with expect_error(ValueError, "没有变化也检查"):
        repo.commit("")


def test_commits_made_at_the_same_time_wait_for_each_other(tmp_path):
    """commit: 几个线程同时提交时排队,没有一个因为 index.lock 失败,每个文件都被记下来"""
    for round_no in range(10):  # without the lock, most commits of a round like this failed
        d = tmp_path / f"ioc-{round_no}"
        write(d / "base.txt", "x\n")
        r = VersionedDirectory(d)
        r.init()
        r.commit("base")
        barrier = threading.Barrier(4)
        errors = []

        def work(i):
            write(d / f"f{i}.txt", f"{i}\n")
            barrier.wait()
            try:
                r.commit(f"t{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=work, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        check(f"第 {round_no} 轮没有出错", errors, [])
        check(f"第 {round_no} 轮干净", r.is_clean(), True)
        tracked = r._git("ls-files").stdout.split()
        check(f"第 {round_no} 轮都记下来了", sorted(tracked), ["base.txt", "f0.txt", "f1.txt", "f2.txt", "f3.txt"])


def test_a_write_that_cannot_get_the_lock_in_time_is_reported(repo):
    """commit、restore: 目录的锁被占着超过 write_timeout 时报 VersionedDirectoryError;读的方法不受影响;锁放开后能继续"""
    repo.write_timeout = 0.5
    write(repo.path + "/src/a.db", "changed\n")
    lock = open(os.path.join(repo.path, ".git", "iocdock.lock"), "a")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        with expect_error(VersionedDirectoryError, "commit 等不到锁", match="in use"):
            repo.commit("x")
        with expect_error(VersionedDirectoryError, "restore 等不到锁", match="in use"):
            repo.restore(repo.head(), force=True)
        step("读的方法照常")
        check("status", repo.status()["modified"], ["src/a.db"])
        check("history", len(repo.history()), 1)
    finally:
        lock.close()
    repo.write_timeout = 10
    check_true("锁放开后能提交", bool(repo.commit("x")))


def test_commit_in_a_directory_without_a_repository_is_a_git_error(tmp_path):
    """commit: 目录不是仓库时报 git 自己的错(VersionedDirectoryError),不是因为拿不到锁而报别的"""
    with expect_error(VersionedDirectoryError, "不是仓库", match="not a git repository"):
        VersionedDirectory(tmp_path).commit("x")


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


# ---- history(limit), show_status, changed_files, diff, read_file, verify -------------


def test_history_can_be_cut_to_the_newest_few(repo, tmp_path):
    """history: limit 只留最新的几条,多于有的就是全部,不是正整数报 ValueError,还没有提交是空列表"""
    write(repo.path + "/src/a.db", "2\n")
    repo.commit("second")
    write(repo.path + "/src/a.db", "3\n")
    repo.commit("third")
    check("最新两条", [h["message"] for h in repo.history(limit=2)], ["third", "second"])
    check("limit 比有的多", len(repo.history(limit=10)), 3)
    check("没传(历史比默认上限短)就是全部", len(repo.history()), 3)
    check("None 就是没传,按默认上限", len(repo.history(limit=None)), 3)
    for bad in [0, -1, 1.5, "2", True]:
        with expect_error(ValueError, f"limit={bad!r}"):
            repo.history(limit=bad)
    empty = VersionedDirectory(tmp_path / "empty")
    (tmp_path / "empty").mkdir()
    empty.init()
    check("没有提交", empty.history(limit=3), [])


def test_the_default_history_limit_is_one_hundred():
    """DEFAULT_HISTORY_LIMIT: 没给 limit 时最多给 100 条"""
    check("DEFAULT_HISTORY_LIMIT", DEFAULT_HISTORY_LIMIT, 100)


def test_history_without_a_limit_gives_only_the_default_number(repo, capsys):
    """history、show_history: 没传 limit(或 None)只给最新的 100 条,show_history 最后一行说还有更早的;传数字就按给的数"""
    for n in range(2, 106):  # empty commits: quick to make, and the files do not matter here
        repo._git("commit", "--quiet", "--allow-empty", "--no-verify", "-m", f"c{n}")
    shown = repo.history()
    check("没传:默认的 100 条", len(shown), DEFAULT_HISTORY_LIMIT)
    check("是最新的 100 条", (shown[0]["message"], shown[-1]["message"]), ("c105", "c6"))
    check("None 和没传一样", repo.history(limit=None), shown)
    check("传数字就按给的数", len(repo.history(limit=102)), 102)
    check("传的比历史长就是全部", len(repo.history(limit=500)), 105)
    repo.show_history()
    lines = capsys.readouterr().out.splitlines()
    check("show_history 没传:100 行加一行说明", len(lines), 101)
    check("最后一行", lines[-1], "... older commits not shown (the newest 100 are listed)")
    repo.show_history(limit=500)
    check("show_history 传够大的数:全部,没有说明", len(capsys.readouterr().out.splitlines()), 105)


def test_the_default_limit_is_read_when_history_is_called(repo, monkeypatch, capsys):
    """history、show_history: 没传 limit 时按 DEFAULT_HISTORY_LIMIT 当时的值,改了它就跟着变"""
    for n in range(2, 6):
        write(repo.path + "/src/a.db", f"{n}\n")
        repo.commit(f"c{n}")
    monkeypatch.setattr("core.versioned_directory.DEFAULT_HISTORY_LIMIT", 3)
    check("没传", [h["message"] for h in repo.history()], ["c5", "c4", "c3"])
    check("None", [h["message"] for h in repo.history(limit=None)], ["c5", "c4", "c3"])
    check("传数字盖过", len(repo.history(limit=4)), 4)
    repo.show_history()
    lines = capsys.readouterr().out.splitlines()
    check("show_history", (len(lines), lines[-1]), (4, "... older commits not shown (the newest 3 are listed)"))


def test_show_history_says_when_older_commits_are_left_out(repo, capsys):
    """show_history: 比上限多就只列最新的,最后一行说明还有更早的;正好够、None 都没有这一行;limit 不对报 ValueError"""
    for n in range(2, 6):
        write(repo.path + "/src/a.db", f"{n}\n")
        repo.commit(f"c{n}")
    repo.show_history(limit=3)
    lines = capsys.readouterr().out.splitlines()
    check("三条加一行说明", len(lines), 4)
    check("是最新的三条", [line.split("  ")[2] for line in lines[:3]], ["c5", "c4", "c3"])
    check("最后一行", lines[3], "... older commits not shown (the newest 3 are listed)")
    step("正好 5 条,limit=5 没有更早的")
    repo.show_history(limit=5)
    lines = capsys.readouterr().out.splitlines()
    check("五条,没有说明", [line.split("  ")[2] for line in lines], ["c5", "c4", "c3", "c2", "first"])
    step("limit 比历史长、None(默认 100 条)都是全部")
    repo.show_history(limit=6)
    check("limit=6", len(capsys.readouterr().out.splitlines()), 5)
    repo.show_history(limit=None)
    check("None", len(capsys.readouterr().out.splitlines()), 5)
    step("limit=1")
    repo.show_history(limit=1)
    lines = capsys.readouterr().out.splitlines()
    check("一条加一行说明", (len(lines), lines[1]), (2, "... older commits not shown (the newest 1 are listed)"))
    with expect_error(ValueError, "limit=0"):
        repo.show_history(limit=0)


def test_show_status_prints_one_line_a_changed_file(repo, capsys):
    """show_status: 没有改动说一句;有改动每个文件一行(改、增、删的顺序),不是 UTF-8 的名字显示成 \\xNN"""
    repo.show_status()
    check("干净", capsys.readouterr().out, "No changes.\n")
    write(repo.path + "/ioc-config.yaml", "changed\n")
    write(repo.path + "/src/new.db", "x\n")
    os.remove(repo.path + "/src/a.proto")
    write(repo.path + "/" + os.fsdecode(b"odd-\xff.db"), "x\n")
    repo.show_status()
    lines = capsys.readouterr().out.splitlines()
    check(
        "每个文件一行",
        lines,
        [
            "modified  ioc-config.yaml",
            "added     odd-\\xff.db",
            "added     src/new.db",
            "deleted   src/a.proto",
        ],
    )


def test_changed_files_tells_what_a_commit_changed_against_the_one_before(repo):
    """changed_files: 第一个提交的文件都是新增;之后的提交是相对上一个的;接受缩短的 id;坏的 id 报错"""
    first = repo.head()
    check(
        "第一个提交",
        repo.changed_files(first),
        {"modified": [], "added": [".gitignore", "ioc-config.yaml", "src/a.db", "src/a.proto"], "deleted": []},
    )
    write(repo.path + "/ioc-config.yaml", "changed\n")
    os.remove(repo.path + "/src/a.proto")
    write(repo.path + "/src/new.db", "x\n")
    odd = os.fsdecode(b"odd-\xff.db")
    write(repo.path + "/" + odd, "x\n")
    second = repo.commit("second")
    expected = {
        "modified": ["ioc-config.yaml"],
        "added": sorted([odd, "src/new.db"]),
        "deleted": ["src/a.proto"],
    }
    check("第二个提交", repo.changed_files(second), expected)
    check("缩短的 id", repo.changed_files(second[:8]), expected)
    with expect_error(ValueError, "不是提交 id"):
        repo.changed_files("HEAD")
    with expect_error(VersionedDirectoryError, "没有这个提交"):
        repo.changed_files("0" * 40)


def test_diff_shows_what_changed_against_the_latest_commit_or_in_a_commit(repo, tmp_path):
    """diff: 不带参数是目录相对最新提交(新文件不在里面,没有提交是空的);带 id 是那个提交改的"""
    check("干净", repo.diff(), "")
    write(repo.path + "/src/a.db", "record 1\nrecord 2\n")
    write(repo.path + "/src/new.db", "brand new\n")
    text = repo.diff()
    check_true("文件头", "diff --git a/src/a.db b/src/a.db" in text, text)
    check_true("加的行", "+record 2" in text, text)
    check_true("新文件不在里面", "new.db" not in text, text)
    second = repo.commit("second")
    check("提交后又是空的", repo.diff(), "")
    in_second = repo.diff(second)
    check_true("提交里有加的行", "+record 2" in in_second and "+brand new" in in_second, in_second)
    check("缩短的 id", repo.diff(second[:8]), in_second)
    first_diff = repo.diff(repo.history()[-1]["id"])
    check_true("第一个提交都是新增", "new file mode" in first_diff and "+++ b/ioc-config.yaml" in first_diff, first_diff)
    with expect_error(ValueError, "不是提交 id"):
        repo.diff("main")
    with expect_error(VersionedDirectoryError, "没有这个提交"):
        repo.diff("0" * 40)
    (tmp_path / "empty").mkdir()
    fresh = VersionedDirectory(tmp_path / "empty")
    fresh.init()
    write(tmp_path / "empty" / "f.txt", "x\n")
    check("还没有提交", fresh.diff(), "")


def test_diff_is_cut_at_the_limit_in_a_whole_line_and_says_so(repo):
    """diff: 超过 max_bytes 就切在行尾,最后一行说切了多少;够长或 None 不切;max_bytes 不对报 ValueError"""
    write(repo.path + "/src/a.db", "".join(f"line {i}\n" for i in range(300)))
    full = repo.diff()
    cut = repo.diff(max_bytes=400)
    body, notice = cut.rsplit("... diff cut at", 1)
    check_true("提示在最后一行", notice.endswith("raise max_bytes to see more\n"), notice)
    check_true("切在行尾", body.endswith("\n"), body[-30:])
    check_true("没超过上限", len(body.encode()) <= 400, len(body.encode()))
    check_true("是全文的开头", full.startswith(body))
    check_true("提示里有全文的大小", f"of {len(full.encode())}:" in notice, notice)
    check("正好够长不切", repo.diff(max_bytes=len(full.encode())), full)
    check("None 不限", repo.diff(max_bytes=None), full)
    tiny = repo.diff(max_bytes=1)
    check_true("一行也放不下时切在字节上", tiny.startswith("d\n... diff cut at 1 bytes of"), tiny)
    for bad in [0, -5, 1.5, "9", True]:
        with expect_error(ValueError, f"max_bytes={bad!r}"):
            repo.diff(max_bytes=bad)


def test_read_file_gives_the_bytes_a_file_had_at_a_commit(repo):
    """read_file: 返回那个提交里文件的原样字节(二进制也一样);路径写法 ./ 会整理;没有这个文件或是目录报 VersionedDirectoryError"""
    first = repo.head()
    binary = bytes(range(256))
    Path(repo.path, "src", "blob.db").write_bytes(binary)
    write(repo.path + "/ioc-config.yaml", "changed\n")
    second = repo.commit("second")
    check("旧的", repo.read_file(first, "ioc-config.yaml"), b"basic:\n  name: ioc-a\n")
    check("新的", repo.read_file(second, "ioc-config.yaml"), b"changed\n")
    check("二进制原样", repo.read_file(second, "src/blob.db"), binary)
    check("缩短的 id 和 ./ 写法", repo.read_file(first[:8], "./src/../src/a.db"), b"record 1\n")
    with expect_error(VersionedDirectoryError, "那个提交里没有这个文件"):
        repo.read_file(first, "src/blob.db")
    with expect_error(VersionedDirectoryError, "是目录不是文件"):
        repo.read_file(first, "src")
    for bad in ["", "/etc/passwd", "../x", "..", ".", ".git", ".git/HEAD", "src/../.git/HEAD", 123]:
        with expect_error(ValueError, f"路径 {bad!r}"):
            repo.read_file(first, bad)
    with expect_error(ValueError, "不是提交 id"):
        repo.read_file("HEAD", "src/a.db")


def test_verify_finds_nothing_in_a_sound_repository_and_something_in_a_damaged_one(repo, tmp_path):
    """verify: 健全是空列表(没有提交的也是);弄坏一个对象就有问题行;.git 读不了也是问题;没有 .git 报错"""
    check("健全", repo.verify(), [])
    (tmp_path / "fresh").mkdir()
    fresh = VersionedDirectory(tmp_path / "fresh")
    fresh.init()
    check("还没有提交也是健全的", fresh.verify(), [])
    step("弄坏一个对象")
    obj = sorted(glob.glob(f"{repo.path}/.git/objects/??/*"))[0]
    os.chmod(obj, 0o644)
    Path(obj).write_bytes(b"junk")
    problems = repo.verify()
    check_true("找到了问题", len(problems) > 0, problems)
    check_true("都是文本行", all(isinstance(p, str) and p.strip() for p in problems), problems)
    step(".git 在但读不了")
    (tmp_path / "broken" / ".git").mkdir(parents=True)
    unreadable = VersionedDirectory(tmp_path / "broken").verify()
    check_true("说不是仓库", any("not a git repository" in p for p in unreadable), unreadable)
    with expect_error(VersionedDirectoryError, "没有 .git", match="no repository"):
        VersionedDirectory(tmp_path).verify()


def test_verify_has_a_time_limit_of_its_own(repo):
    """verify: 用自己的 timeout(默认 60 秒),不受 self.timeout 限制;给得太短就报超时"""
    repo.timeout = 0.0001
    check("self.timeout 太短也能查完", repo.verify(), [])
    with expect_error(VersionedDirectoryError, "verify 的 timeout 太短", match="took longer"):
        repo.verify(timeout=0.0001)


# ---- restore_file, repair -------------------------------------------------------------


def test_restore_file_brings_back_one_file_and_leaves_the_rest(repo):
    """restore_file: 只把一个文件还原成那个提交的样子,记成只动这个文件的新提交;别的文件没提交的改动原样留着"""
    first = repo.head()
    write(repo.path + "/src/a.db", "record 1\nrecord 2\n")
    second = repo.commit("second")
    write(repo.path + "/ioc-config.yaml", "unsaved config\n")
    new = repo.restore_file(first, "src/a.db")
    check_true("是新提交", new not in (first, second))
    check("head", repo.head(), new)
    check("a.db 回来了", Path(repo.path, "src/a.db").read_text(), "record 1\n")
    check("别的文件没动", Path(repo.path, "ioc-config.yaml").read_text(), "unsaved config\n")
    check("没提交的还是没提交", repo.status(), {"modified": ["ioc-config.yaml"], "added": [], "deleted": []})
    check("这次提交只动了 a.db", repo.changed_files(new), {"modified": ["src/a.db"], "added": [], "deleted": []})
    check("说明", repo.history(limit=1)[0]["message"], f"restore src/a.db from {first[:8]}")


def test_restore_file_refuses_to_throw_away_changes_of_that_file(repo):
    """restore_file: 这个文件有没提交的改动(改了或是新文件)报 UncommittedChangesError,changes 里只有它;force=True 才覆盖"""
    first = repo.head()
    write(repo.path + "/src/a.db", "record 1\nrecord 2\n")
    second = repo.commit("second")
    write(repo.path + "/src/a.db", "unsaved\n")
    with expect_error(UncommittedChangesError, "文件有没提交的改动") as info:
        repo.restore_file(first, "src/a.db")
    check("changes 里只有这个文件", info.value.changes, {"modified": ["src/a.db"], "added": [], "deleted": []})
    check("a.db 没动", Path(repo.path, "src/a.db").read_text(), "unsaved\n")
    check("head 没变", repo.head(), second)
    new = repo.restore_file(first, "src/a.db", force=True)
    check("force 之后回来了", Path(repo.path, "src/a.db").read_text(), "record 1\n")
    check("head", repo.head(), new)
    step("文件在旧提交里有,现在是没有提交过的新文件")
    os.remove(repo.path + "/src/a.proto")
    repo.commit("gone")
    write(repo.path + "/src/a.proto", "new content\n")
    with expect_error(UncommittedChangesError, "新文件也算") as info:
        repo.restore_file(first, "src/a.proto")
    check("算新增", info.value.changes, {"modified": [], "added": ["src/a.proto"], "deleted": []})
    repo.restore_file(first, "src/a.proto", force=True)
    check("force 之后回来了", Path(repo.path, "src/a.proto").read_text(), "message A {}\n")


def test_restore_file_brings_back_a_deleted_file_and_a_file_that_is_like_that_already(repo):
    """restore_file: 删掉的文件不用 force 就回来;已经是那个样子就不产生新提交;丢掉这个文件的改动也不产生新提交"""
    first = repo.head()
    os.remove(repo.path + "/src/a.proto")
    check("删掉的回来,内容和最新提交一样所以没有新提交", repo.restore_file(first, "src/a.proto"), first)
    check("文件回来了", Path(repo.path, "src/a.proto").read_text(), "message A {}\n")
    check("干净", repo.is_clean(), True)
    check("已经是那个样子", repo.restore_file(first, "src/a.db"), first)
    write(repo.path + "/src/a.db", "unsaved\n")
    check("force 丢掉改动", repo.restore_file(first, "src/a.db", force=True), first)
    check("改动没了", Path(repo.path, "src/a.db").read_text(), "record 1\n")
    check("还是一个提交", len(repo.history()), 1)


def test_restore_file_rejects_what_it_cannot_do(repo):
    """restore_file: 那个提交里没有这个文件、是目录、路径或 id 写得不对都报错,什么都不动"""
    first = repo.head()
    write(repo.path + "/src/later.db", "later\n")
    second = repo.commit("later")
    with expect_error(VersionedDirectoryError, "那个提交里没有这个文件"):
        repo.restore_file(first, "src/later.db")
    check_true("没去删它", Path(repo.path, "src/later.db").exists())
    with expect_error(VersionedDirectoryError, "是目录"):
        repo.restore_file(first, "src")
    for bad in ["", "/etc/passwd", "../x", ".git/HEAD"]:
        with expect_error(ValueError, f"路径 {bad!r}"):
            repo.restore_file(first, bad)
    with expect_error(ValueError, "不是提交 id"):
        repo.restore_file("HEAD", "src/a.db")
    with expect_error(VersionedDirectoryError, "没有这个提交"):
        repo.restore_file("0" * 40, "src/a.db")
    check("head 没变", repo.head(), second)


def test_restore_file_waits_for_the_lock_like_commit_and_restore(repo):
    """restore_file: 目录的锁被占着超过 write_timeout 时报 VersionedDirectoryError"""
    repo.write_timeout = 0.5
    lock = open(os.path.join(repo.path, ".git", "iocdock.lock"), "a")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        with expect_error(VersionedDirectoryError, "等不到锁", match="in use"):
            repo.restore_file(repo.head(), "src/a.db")
    finally:
        lock.close()


def break_the_repository(repo):
    """Damage that repair() cannot mend, only start again from: HEAD is garbage, and nothing
    is left that remembers the commits (no branch, no log of HEAD)"""
    git = Path(repo.path, ".git")
    (git / "HEAD").write_text("garbage\n")
    shutil.rmtree(git / "logs", ignore_errors=True)
    (git / "refs" / "heads" / "main").unlink(missing_ok=True)


def test_repair_starts_the_history_again_and_keeps_the_old_git_directory(repo):
    """repair: 读不了的仓库——旧 .git 改名留着,新仓库把目录里的文件记成第一个提交,旧的 .git 里的东西不被记"""
    write(repo.path + "/src/extra.db", "not committed yet\n")
    break_the_repository(repo)
    check("读不了", repo.check()["state"], DirectoryState.UNREADABLE)
    result = repo.repair()
    check("重新开始了", result["restarted"], True)
    moved = Path(result["moved_to"])
    check_true("旧的改了名留着", moved.is_dir() and moved.name.startswith(".git.broken-"), moved.name)
    check("旧的东西还在里面", (moved / "HEAD").read_text(), "garbage\n")
    check_true("旧历史的对象还在", (moved / "objects").is_dir())
    report = repo.check()
    check("修好了", report["state"], DirectoryState.OK)
    check("head 是起点提交", report["head"], result["commit"])
    check("历史只有这一条", len(repo.history()), 1)
    check_true("说明里有旧目录的名字", moved.name in repo.history()[0]["message"], repo.history()[0]["message"])
    tracked = repo._git("ls-files").stdout.split()
    check(
        "目录里的文件都记下了",
        sorted(tracked),
        [".gitignore", "ioc-config.yaml", "src/a.db", "src/a.proto", "src/extra.db"],
    )
    check_true("旧 .git 里的东西没被记", not any(".git.broken" in t for t in tracked), tracked)
    check("干净", repo.is_clean(), True)
    check("文件没动", Path(repo.path, "src/extra.db").read_text(), "not committed yet\n")


def test_repair_does_not_touch_a_repository_that_works_or_is_missing(repo, tmp_path):
    """repair: 仓库没坏(有提交的、还没提交的)或者没有仓库都报 VersionedDirectoryError,什么都不改,历史还在"""
    head = repo.head()
    with expect_error(VersionedDirectoryError, "没坏", match="not broken"):
        repo.repair()
    check("历史还在", repo.head(), head)
    check("没有改名的目录", glob.glob(f"{repo.path}/.git.broken-*"), [])
    (tmp_path / "fresh").mkdir()
    fresh = VersionedDirectory(tmp_path / "fresh")
    fresh.init()
    with expect_error(VersionedDirectoryError, "还没提交也没坏", match="not broken"):
        fresh.repair()
    with expect_error(VersionedDirectoryError, "没有仓库", match="init"):
        VersionedDirectory(tmp_path).repair()


def test_repairing_twice_in_the_same_second_keeps_both_old_directories(repo, monkeypatch):
    """repair: 同一秒修两次,两个旧目录名字不同,都留着"""

    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 27, 10, 30, 0)

    monkeypatch.setattr("core.versioned_directory.datetime", Fixed)
    break_the_repository(repo)
    first = repo.repair()
    break_the_repository(repo)
    second = repo.repair()
    check("第一个名字", Path(first["moved_to"]).name, ".git.broken-20261127-103000")
    check("第二个名字", Path(second["moved_to"]).name, ".git.broken-20261127-103000-2")
    check_true("两个都在", Path(first["moved_to"]).is_dir() and Path(second["moved_to"]).is_dir())
    check("现在是好的", repo.check()["state"], DirectoryState.OK)


def test_repair_says_so_when_it_cannot_move_the_old_directory_and_changes_nothing(repo, monkeypatch):
    """repair: 改名失败报 VersionedDirectoryError,原来的 .git 没动"""
    break_the_repository(repo)

    def refuse(*args, **kwargs):
        raise PermissionError("no")

    with monkeypatch.context() as m:
        m.setattr("core.versioned_directory.os.rename", refuse)
        with expect_error(VersionedDirectoryError, "改不了名", match="cannot move"):
            repo.repair()
    check("原来的 .git 还在", Path(repo.path, ".git", "HEAD").read_text(), "garbage\n")
    check("没有改名的目录", glob.glob(f"{repo.path}/.git.broken-*"), [])


# ---- a missing directory, a killed git, the write timeout, a repository made again --------


def test_a_missing_directory_is_reported_as_such_not_as_a_missing_git(tmp_path):
    """_git: 要在里面跑 git 的目录不存在时说目录不存在,不说 git 没装"""
    r = VersionedDirectory(tmp_path / "nope")
    for name, call in [("head", r.head), ("status", r.status), ("history", r.history), ("commit", lambda: r.commit("x"))]:
        with expect_error(VersionedDirectoryError, f"{name} 在不存在的目录里", match="no such directory") as info:
            call()
        check_true("没说 git 没装", "not installed" not in str(info.value), str(info.value))


def test_a_git_killed_for_taking_too_long_does_not_leave_the_index_locked(repo, monkeypatch):
    """_git: 写索引的 git 超时被杀,它留下的 index.lock 会被删掉,之后还能提交"""
    lock = Path(repo.path, ".git", "index.lock")
    real_run = subprocess.run

    def killed(command, **kwargs):
        if "add" in command:
            lock.write_text("")  # what a git that is killed while it holds the lock leaves behind
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return real_run(command, **kwargs)

    write(repo.path + "/src/a.db", "changed\n")
    with monkeypatch.context() as m:
        m.setattr("core.versioned_directory.subprocess.run", killed)
        with expect_error(VersionedDirectoryError, "add 超时", match="took longer"):
            repo.commit("x")
    check_true("锁被删了", not lock.exists())
    check_true("之后能提交", bool(repo.commit("x")))


def test_a_lock_that_is_not_the_killed_gits_is_left_alone(repo, monkeypatch):
    """_git: 比这条命令开始得早的锁、或者只读命令超时时存在的锁,都是别人的,不删"""
    lock = Path(repo.path, ".git", "index.lock")
    lock.write_text("")
    os.utime(lock, (1, 1))  # made long before, by somebody else

    def killed(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    with monkeypatch.context() as m:
        m.setattr("core.versioned_directory.subprocess.run", killed)
        with expect_error(VersionedDirectoryError, "add 超时", match="took longer"):
            repo.commit("x")
    check_true("旧的锁还在", lock.exists())
    step("一把新的锁,但超时的是只读的 status")
    lock.write_text("")
    with monkeypatch.context() as m:
        m.setattr("core.versioned_directory.subprocess.run", killed)
        with expect_error(VersionedDirectoryError, "status 超时", match="took longer"):
            repo.status()
    check_true("新的锁也还在", lock.exists())


def test_what_writes_gets_the_write_timeout_and_what_looks_gets_the_timeout(repo, monkeypatch):
    """git 命令的超时: 写的(add、commit、read-tree、clean、checkout)用 write_timeout,看的用 timeout"""
    repo.timeout, repo.write_timeout = 7, 70
    first = repo.head()
    seen = {}
    real_run = subprocess.run
    verbs = ("add", "commit", "read-tree", "clean", "checkout", "status", "rev-parse", "diff")

    def spy(command, **kwargs):
        verb = next((a for a in command if a in verbs), "other")
        seen.setdefault(verb, set()).add(kwargs["timeout"])
        return real_run(command, **kwargs)

    monkeypatch.setattr("core.versioned_directory.subprocess.run", spy)
    write(repo.path + "/src/a.db", "changed\n")
    repo.commit("x")
    repo.restore(first, force=True)
    repo.restore_file(first, "src/a.db")
    repo.status()
    check("写的", {v: seen[v] for v in ("add", "commit", "read-tree", "clean", "checkout")}, {v: {70} for v in ("add", "commit", "read-tree", "clean", "checkout")})
    check("看的", {v: seen[v] for v in ("status", "rev-parse", "diff")}, {v: {7} for v in ("status", "rev-parse", "diff")})


def test_a_repository_made_again_by_hand_does_not_record_the_old_git_directory(tmp_path):
    """init: .git.broken-* 每次初始化都写进 .git/info/exclude,手动改名再 init 也不会把旧 .git 记进新历史"""
    d = tmp_path / "ioc"
    write(d / "f.txt", "1\n")
    r = VersionedDirectory(d)
    r.init()
    check_true("规则在 exclude 里", ".git.broken-*" in (d / ".git" / "info" / "exclude").read_text().split())
    r.commit("one")
    os.rename(d / ".git", d / ".git.broken-by-hand")
    r.init()
    r.commit("again")
    check("只记了目录里的文件", r._git("ls-files").stdout.split(), ["f.txt"])
    check("干净", r.is_clean(), True)


# ---- what is told apart: git cannot tell / git says broken; repair mends or restarts -----


def test_errors_that_say_git_could_not_tell_have_a_class_of_their_own(tmp_path, repo, monkeypatch):
    """_git: git 找不到、目录不存在是 GitUnavailableError,超时是 GitTimeoutError,都还是 VersionedDirectoryError"""
    with expect_error(GitUnavailableError, "目录不存在", match="no such directory") as info:
        VersionedDirectory(tmp_path / "nope").head()
    check_true("是 VersionedDirectoryError", isinstance(info.value, VersionedDirectoryError))
    repo.timeout = 0.0001
    with expect_error(GitTimeoutError, "超时", match="took longer") as info:
        repo.status()
    check_true("是 VersionedDirectoryError", isinstance(info.value, VersionedDirectoryError))
    repo.timeout = 10
    monkeypatch.setenv("PATH", "/nonexistent")
    with expect_error(GitUnavailableError, "git 没装", match="not installed"):
        repo.status()


def test_repair_leaves_a_repository_alone_when_git_could_not_tell_whether_it_is_broken(repo, monkeypatch):
    """repair: git 找不到或者超时,说明什么都不知道,不能当成仓库坏了:原样抛出,什么都不改"""
    head = repo.head()
    with monkeypatch.context() as m:
        m.setenv("PATH", "/nonexistent")
        with expect_error(GitUnavailableError, "git 找不到"):
            repo.repair()
    repo.timeout = 0.0001
    with expect_error(GitTimeoutError, "git 超时"):
        repo.repair()
    repo.timeout = 10
    check("仓库没被动", (repo.check()["state"], repo.head()), (DirectoryState.OK, head))
    check("没有改名的目录", glob.glob(f"{repo.path}/.git.broken-*"), [])


def test_repair_mends_a_head_that_is_garbage_and_keeps_the_history(repo):
    """repair: 只是 HEAD 坏了,把它指回 main,历史原样保留,不重新开始"""
    write(repo.path + "/src/a.db", "record 1\nrecord 2\n")
    second = repo.commit("second")
    before = repo.history()
    Path(repo.path, ".git", "HEAD").write_text("garbage\n")
    check("读不了", repo.check()["state"], DirectoryState.UNREADABLE)
    result = repo.repair()
    check("没有重新开始", result, {"restarted": False, "moved_to": None, "commit": second})
    check("历史原样", repo.history(), before)
    check("修好了", repo.check()["state"], DirectoryState.OK)
    check("没有改名的目录", glob.glob(f"{repo.path}/.git.broken-*"), [])


def test_check_tells_a_lost_branch_from_a_new_repository(repo, tmp_path):
    """check: 分支文件丢了但日志还记得提交,是 UNREADABLE 并说明;真的还没有提交的新仓库仍是 NO_COMMIT"""
    head = repo.head()
    os.remove(os.path.join(repo.path, ".git", "refs", "heads", "main"))
    report = repo.check()
    check("state", report["state"], DirectoryState.UNREADABLE)
    check_true("说日志还记得,并给出能找回的提交", "remembers" in report["error"] and head[:8] in report["error"], report["error"])
    (tmp_path / "fresh").mkdir()
    fresh = VersionedDirectory(tmp_path / "fresh")
    fresh.init()
    check("新仓库", fresh.check()["state"], DirectoryState.NO_COMMIT)


def test_repair_points_a_lost_branch_at_the_commit_the_log_remembers(repo):
    """repair: 分支文件丢了,把 main 指回日志里记得的最后一个提交,历史原样保留"""
    write(repo.path + "/src/a.db", "record 1\nrecord 2\n")
    second = repo.commit("second")
    before = repo.history()
    os.remove(os.path.join(repo.path, ".git", "refs", "heads", "main"))
    check("丢了之后看起来像没有历史", (repo.head(), repo.history()), (None, []))
    result = repo.repair()
    check("没有重新开始", result, {"restarted": False, "moved_to": None, "commit": second})
    check("历史原样", repo.history(), before)
    check("修好了", repo.check()["state"], DirectoryState.OK)


def test_repair_goes_on_from_the_newest_commit_that_is_whole(repo):
    """repair: 最新提交的对象丢了,main 指回日志里还完整的最新一个提交"""
    first = repo.head()
    write(repo.path + "/src/a.db", "record 1\nrecord 2\n")
    second = repo.commit("second")
    obj = os.path.join(repo.path, ".git", "objects", second[:2], second[2:])
    os.chmod(obj, 0o644)
    os.remove(obj)
    check("读不了", repo.check()["state"], DirectoryState.UNREADABLE)
    result = repo.repair()
    check("没有重新开始,回到完整的那个", result, {"restarted": False, "moved_to": None, "commit": first})
    check("历史只剩完整的", [h["id"] for h in repo.history()], [first])
    check("修好了", repo.check()["state"], DirectoryState.OK)


def test_repair_undoes_what_it_did_when_making_the_new_repository_fails(repo, monkeypatch):
    """repair: 重新开始时新仓库建失败(init 或第一次提交),新的删掉、旧的 .git 改名改回来,和修复之前一样"""
    break_the_repository(repo)
    before = Path(repo.path, ".git", "HEAD").read_text()

    def half_made(self, ignore=()):
        os.mkdir(os.path.join(self.path, ".git"))  # a repository that is only begun
        raise VersionedDirectoryError("init failed")

    with monkeypatch.context() as m:
        m.setattr(VersionedDirectory, "init", half_made)
        with expect_error(VersionedDirectoryError, "init 失败", match="init failed"):
            repo.repair()
    check("旧的 .git 回来了", Path(repo.path, ".git", "HEAD").read_text(), before)
    check("没有改名的目录", glob.glob(f"{repo.path}/.git.broken-*"), [])

    def no_commit(self, message):
        raise VersionedDirectoryError("commit failed")

    with monkeypatch.context() as m:
        m.setattr(VersionedDirectory, "_commit", no_commit)
        with expect_error(VersionedDirectoryError, "第一次提交失败", match="commit failed"):
            repo.repair()
    check("旧的 .git 又回来了", Path(repo.path, ".git", "HEAD").read_text(), before)
    check("还是没有改名的目录", glob.glob(f"{repo.path}/.git.broken-*"), [])
    step("之后还能正常修")
    check("重新开始", repo.repair()["restarted"], True)
