import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core import settings
from core.exceptions import IocExistsError, IocInitError, IocNotFoundError
from core.ioc import IOC, check_name
from core.ioc_config import IocConfig
from core.ioc_repository import IocRepository
from core.ioc_schema import IssueEntry, IssueLevel, IssueReason, new_state
from tests.helpers import REPO_ROOT, add_ioc, make_issue
from tests.logutil import check, check_true, expect_error, note, step


def test_importing_ioc_needs_no_database_but_using_it_does(tmp_path):
    """core.ioc: 库不存在时 import 照常成功,get_state_manager 才抛 FileNotFoundError,也不会建库"""
    missing = tmp_path / "ioc-state.db"
    code = (
        "import sys; sys.path.insert(0, sys.argv[1])\n"
        "from core import settings\n"
        "settings.DEFAULT_DB_PATH = sys.argv[2]\n"
        "import core.ioc\n"
        "print('imported')\n"
        "from core.ioc_state import get_state_manager\n"
        "get_state_manager()\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(REPO_ROOT), str(missing)],
        capture_output=True,
        text=True,
    )
    check("退出码", result.returncode, 1)
    check_true("import 成功了", "imported" in result.stdout, result.stdout)
    check_true("报的是 FileNotFoundError", "FileNotFoundError" in result.stderr, result.stderr)
    check_true("没有建出库文件", not missing.exists())


def test_ioc_reads_its_state_from_the_shared_database(fresh):
    """IOC: 初始化时用共享的 state manager 从库里读自己的状态"""
    shared = fresh
    add_ioc(shared, "ioca")
    os.makedirs(os.path.join(settings.IOCS_DIR, "ioca"))
    ioc = IOC("ioca")
    check("name", ioc.name, "ioca")
    check_true("state_manager 就是 get_state_manager() 的那个", ioc.state_manager is shared)
    check("state_data", ioc.state_data, shared.read_ioc("ioca"))
    check_true("config 是 IocConfig", isinstance(ioc.config, IocConfig))
    check("config.path", ioc.config.path, ioc.config_path)
    check("config 文件名", os.path.basename(ioc.config_path), settings.CONFIG_FILE_NAME)
    check("config 在 IOC 自己的目录里", os.path.dirname(ioc.config_path), os.path.join(settings.IOCS_DIR, "ioca"))
    check_true("config 路径不在 /opt 下", not ioc.config_path.startswith("/opt"))
    check_true("config 路径在开发目录的 .test-tmp 里", ioc.config_path.startswith(str(REPO_ROOT / ".test-tmp")))


def test_ioc_that_is_not_in_the_database_raises_ioc_not_found(fresh):
    """IOC: 库里没有这个 IOC 时抛 IocNotFoundError"""
    add_ioc(fresh, "ioca")
    os.makedirs(os.path.join(settings.IOCS_DIR, "ioca"))
    with expect_error(IocNotFoundError, "库里没有 ioc-b"):
        IOC("iocb")


def test_check_presence_tells_the_four_cases_apart(fresh):
    """IOC.check_presence: 库里的记录和目录各有各没有,四种情况分开返回"""
    check("都没有", IOC.check_presence("ioca"), "missing")
    IOC.create("ioca")
    check("都有", IOC.check_presence("ioca"), "complete")
    shutil.rmtree(os.path.join(settings.IOCS_DIR, "ioca"))
    check("只有记录", IOC.check_presence("ioca"), "no_directory")
    fresh.delete_ioc("ioca")
    os.makedirs(os.path.join(settings.IOCS_DIR, "ioca"))
    check("只有目录", IOC.check_presence("ioca"), "unregistered")
    with expect_error(ValueError, "名字不合法"):
        IOC.check_presence("../x")


def test_ioc_whose_directory_is_gone_is_opened_and_refresh_records_it_once(fresh):
    """IOC: 库里有记录但目录没了,照常打开;refresh 把问题记成一条 issue,再 refresh 多少次也只有这一条"""
    IOC.create("ioca")
    shutil.rmtree(os.path.join(settings.IOCS_DIR, "ioca"))
    ioc = IOC("ioca")
    check("name", ioc.name, "ioca")
    check("打开时不看文件,还没有问题", problems(ioc.state_data.issues), [])
    found = problems(ioc.refresh().issues)
    check("一条", len(found), 1)
    issue = found[0]
    check("level", issue.level, IssueLevel.ERROR)
    check("reason", issue.reason, IssueReason.FILE_ERROR)
    check_true("消息说目录没了", "directory is missing" in issue.message and ioc.dir_path in issue.message)
    check("库里存了同一条", problems(fresh.read_issues("ioca")), [issue])
    ioc.refresh()
    check("还是一条", problems(IOC("ioca").state_data.issues), [issue])
    check("记录还在", fresh.list_iocs(), ["ioca"])


def test_directory_without_a_record_is_opened_and_gets_a_record_and_an_issue(fresh):
    """IOC: 有目录但库里没有记录,照常打开,补一条记录并记一条 RECORD_RESET;目录里的东西不动;再打开不再重复,这条也不会被刷新掉"""
    d = Path(settings.IOCS_DIR) / "ioca"
    (d / "src").mkdir(parents=True)
    (d / "src" / "mine.db").write_text("keep me\n")
    (d / "notes.txt").write_text("also mine\n")
    ioc = IOC("ioca")
    check("name", ioc.name, "ioca")
    reset = [i for i in ioc.state_data.issues if i.reason == IssueReason.RECORD_RESET]
    check("一条 RECORD_RESET", len(reset), 1)
    check("level", reset[0].level, IssueLevel.ERROR)
    check_true("消息说库里没有记录", "not in the database" in reset[0].message and ioc.dir_path in reset[0].message)
    check("打开时只有这一条 issue", ioc.state_data.issues, reset)
    check("src_files 还是空的,要等 refresh", ioc.state_data.src_files.db_files, [])
    check("refresh 之后按目录里实际的文件填", ioc.refresh().src_files.db_files, ["mine.db"])
    check("库里存了同样的 issue", fresh.read_issues("ioca"), ioc.state_data.issues)
    check("目录里的文件没动", sorted(p.name for p in d.iterdir()), ["notes.txt", "src"])
    check("文件内容没动", (d / "src" / "mine.db").read_text(), "keep me\n")
    check_true("没有擅自建仓库", not (d / ".git").exists())
    check("现在是完整的", IOC.check_presence("ioca"), "complete")
    step("再打开两次")
    IOC("ioca")
    again = IOC("ioca")
    check("RECORD_RESET 还是那一条", [i for i in again.state_data.issues if i.reason == IssueReason.RECORD_RESET], reset)


def test_both_halves_missing_is_still_not_found(fresh):
    """IOC: 目录和记录都没有才是真的找不到,抛 IocNotFoundError"""
    with expect_error(IocNotFoundError, "什么都没有"):
        IOC("ioca")
    check("没有补出记录", fresh.list_iocs(), [])


def test_create_refuses_a_complete_ioc_even_with_force(fresh):
    """IOC.create: 完整的 IOC 即使 force 也不会重建,什么都不动"""
    ioc = IOC.create("ioca")
    mine = Path(ioc.dir_path) / "src" / "mine.db"
    mine.write_text("keep me\n")
    before = fresh.read_ioc("ioca")
    with expect_error(IocExistsError, "force 也不行") as info:
        IOC.create("ioca", force=True)
    check_true("说的是已经存在", str(info.value).endswith("already exists"), str(info.value))
    check("文件没动", mine.read_text(), "keep me\n")
    check("状态没动", fresh.read_ioc("ioca"), before)


def test_forced_create_adopts_a_directory_that_has_no_record(fresh):
    """IOC.create(force=True): 目录已经有、库里没有:目录和里面的东西保留,缺的补上,登记一条默认状态的记录"""
    d = Path(settings.IOCS_DIR) / "ioca"
    d.mkdir(parents=True)
    (d / "ioc-config.yaml").write_text("mine\n")
    ioc = IOC.create("ioca", force=True)
    check("文件还在", (d / "ioc-config.yaml").read_text(), "mine\n")
    check_true("补了 src", (d / "src").is_dir())
    check_true("补了仓库", ioc.repository.exists())
    check("状态是默认值", plain(ioc.state_data), plain(new_state()))
    check("现在是完整的", IOC.check_presence("ioca"), "complete")


def test_forced_create_keeps_an_existing_repository_and_src(fresh):
    """IOC.create(force=True): 目录里已有仓库和 src 就原样用,不重新初始化,历史不丢"""
    d = Path(settings.IOCS_DIR) / "ioca"
    (d / "src").mkdir(parents=True)
    (d / "src" / "mine.db").write_text("keep me\n")
    repo = IocRepository(d)
    repo.init()
    head = repo.commit("mine")
    ioc = IOC.create("ioca", force=True)
    check("提交还在", ioc.repository.head(), head)
    check("文件还在", (d / "src" / "mine.db").read_text(), "keep me\n")


def test_forced_create_rebuilds_a_directory_that_is_gone_and_resets_the_record(fresh):
    """IOC.create(force=True): 有记录目录没了:重新建目录,记录重置为默认状态,旧 issue 清掉"""
    ioc = IOC.create("ioca")
    fresh.write_ioc("ioca", {"snapshot": "old"})
    fresh.write_issues("ioca", [make_issue("old problem")])
    shutil.rmtree(ioc.dir_path)
    again = IOC.create("ioca", force=True)
    check_true("目录又有了", os.path.isdir(again.dir_path))
    check_true("有 src", os.path.isdir(os.path.join(again.dir_path, "src")))
    check_true("有仓库", again.repository.exists())
    check("状态是默认值", plain(again.state_data), plain(new_state()))
    check_true("旧 issue 没了", "old problem" not in messages_of(again), messages_of(again))
    check_true("目录没了的 issue 也没了", not any("missing" in m for m in messages_of(again)))
    check("现在是完整的", IOC.check_presence("ioca"), "complete")


def test_forced_create_that_fails_leaves_an_adopted_directory_as_it_was(fresh, monkeypatch):
    """IOC.create(force=True): 失败时,原来就有的目录和文件不删,只撤销自己加的 src 和 .git,库里不留记录"""
    d = Path(settings.IOCS_DIR) / "ioca"
    d.mkdir(parents=True)
    (d / "mine.txt").write_text("keep me\n")
    monkeypatch.setattr(type(fresh), "write_ioc", lambda *a, **k: (_ for _ in ()).throw(OSError("disk on fire")))
    with expect_error(IocInitError, "写库失败"):
        IOC.create("ioca", force=True)
    check("目录里只剩原来的文件", sorted(p.name for p in d.iterdir()), ["mine.txt"])
    check("文件没动", (d / "mine.txt").read_text(), "keep me\n")
    monkeypatch.undo()
    check("库里没有", fresh.list_iocs(), [])


def test_forced_create_that_fails_leaves_the_old_record_when_it_made_the_directory(fresh, monkeypatch):
    """IOC.create(force=True): 有记录目录没了的情况下失败:刚建的目录删掉,原来的记录和 issue 不变"""
    ioc = IOC.create("ioca")
    fresh.write_ioc("ioca", {"snapshot": "old"})
    shutil.rmtree(ioc.dir_path)
    before = fresh.read_ioc("ioca")
    real_write = type(fresh).write_ioc

    def write_then_fail(self, *args, **kwargs):
        real_write(self, *args, **kwargs)
        raise OSError("disk on fire")

    monkeypatch.setattr(type(fresh), "write_ioc", write_then_fail)
    with expect_error(IocInitError, "写库失败"):
        IOC.create("ioca", force=True)
    monkeypatch.undo()
    check_true("刚建的目录删了", not os.path.exists(os.path.join(settings.IOCS_DIR, "ioca")))
    check("记录回到原样(事务回滚)", fresh.read_ioc("ioca"), before)


def test_create_says_which_half_of_an_ioc_is_there_and_touches_neither(fresh):
    """IOC.create: 只有记录、只有目录两种异常情况都拒绝创建,而且报错分得清是哪一种,记录和目录都不动"""
    IOC.create("ioca")
    IOC.create("iocb")
    shutil.rmtree(os.path.join(settings.IOCS_DIR, "ioca"))  # a: only the record
    fresh.delete_ioc("iocb")                                  # b: only the directory
    (Path(settings.IOCS_DIR) / "iocb" / "src" / "mine.db").write_text("keep me\n")
    with expect_error(IocExistsError, "只有记录") as only_record:
        IOC.create("ioca")
    with expect_error(IocExistsError, "只有目录") as only_dir:
        IOC.create("iocb")
    check_true("a 的消息说目录没了", "directory is missing" in str(only_record.value))
    check_true("b 的消息说库里没有", "not in the database" in str(only_dir.value))
    check_true("a 的目录没有被建出来", not os.path.exists(os.path.join(settings.IOCS_DIR, "ioca")))
    check("a 的记录还在", fresh.list_iocs(), ["ioca"])
    check("b 的文件还在", (Path(settings.IOCS_DIR) / "iocb" / "src" / "mine.db").read_text(), "keep me\n")


def plain(state):
    """A state without its issues, to compare the rest of it"""
    return state.model_dump(exclude={"issues"})


def problems(issues):
    """The issues of refresh(), without the records of the operations that were done"""
    return [i for i in issues if i.reason not in (IssueReason.OPERATION_SUCCESS, IssueReason.OPERATION_FAILED)]


def messages_of(ioc):
    return [i.message for i in problems(ioc.state_data.issues)]


def fresh_tmp_dir(ioc):
    """An empty directory next to the IOC's, outside of it"""
    d = Path(ioc.dir_path).parent / "_templates"
    d.mkdir(exist_ok=True)
    return d


@pytest.fixture
def fresh(shared):
    """The shared state manager and an empty directory of IOCs, both emptied again
    after the test"""
    shutil.rmtree(settings.IOCS_DIR, ignore_errors=True)
    yield shared
    shutil.rmtree(settings.IOCS_DIR, ignore_errors=True)


@pytest.mark.parametrize(
    "name",
    ["ioca", "ab", "a1", "ioc01", "a" * 63],
    ids=lambda n: n if len(n) < 20 else f"{len(n)} chars",
)
def test_names_that_every_user_of_the_name_accepts(name):
    """check_name: 目录名、Docker service/container 名和 DNS 都能用的名字通过"""
    check_name(name)
    check_true(f"{name[:20]!r} 通过", True)


@pytest.mark.parametrize(
    "name",
    [
        "", "a", "A", "Ioc-a", "ioc_a", "ioc.a", "ioc-a", "-ioc", "ioc-", "a--b", "1ioc", "ioc a", "ioc/a",
        "../x", "..", ".", "ioc\n", "ioc-\u4e2d", "a" * 64, None, 5, b"ioca",
    ],
    ids=repr,
)
def test_names_that_some_user_of_the_name_rejects(name):
    """check_name: 大写、下划线、点、路径符号、太短太长、不是字符串的名字都被拒绝"""
    with expect_error(ValueError, f"{name!r} 不合法"):
        check_name(name)


def test_ioc_rejects_a_bad_name_before_touching_anything(fresh):
    """IOC / IOC.create: 名字不合法就直接报 ValueError,既不查库也不碰目录"""
    with expect_error(ValueError, "打开"):
        IOC("../x")
    with expect_error(ValueError, "创建"):
        IOC.create("../x")
    check_true("没有建出目录", not os.path.exists(settings.IOCS_DIR) or os.listdir(settings.IOCS_DIR) == [])
    check("库里没有", fresh.list_iocs(), [])


def test_create_makes_an_empty_ioc_with_a_repository_and_a_state(fresh):
    """IOC.create: 建出空的 IOC:目录、空的 src、还没有提交的 git 仓库,库里登记状态;不放配置文件"""
    ioc = IOC.create("ioca")
    check_true("返回 IOC", isinstance(ioc, IOC))
    check("name", ioc.name, "ioca")
    check_true("目录在 IOCS_DIR 里", os.path.isdir(os.path.join(settings.IOCS_DIR, "ioca")))
    check("目录里只有 src 和 .git", sorted(p.name for p in Path(ioc.dir_path).iterdir()), [".git", "src"])
    check("src 是空的", list((Path(ioc.dir_path) / "src").iterdir()), [])
    check_true("没有配置文件", not os.path.exists(ioc.config_path))
    check_true("有仓库", ioc.repository.exists())
    check("还没有提交", ioc.repository.head(), None)
    check("没有任何改动", ioc.repository.is_clean(), True)
    check("库里的状态是 new_state() 的默认值", plain(ioc.state_data), plain(new_state()))
    check("只有一条操作记录:创建", [(i.level, i.reason, i.message) for i in ioc.state_data.issues], [(IssueLevel.INFO, IssueReason.OPERATION_SUCCESS, "created")])
    check("库里读到的和对象里的一样", fresh.read_ioc("ioca"), ioc.state_data)
    check("之后能用 IOC(name) 打开", IOC("ioca").state_data, ioc.state_data)
    with expect_error(FileNotFoundError, "还没有配置文件时 load"):
        ioc.config.load()


def test_create_template_writes_into_the_given_directory_and_the_ioc_need_not_exist(fresh, tmp_path):
    """IOC.create_template: 模板写进指定目录,不要求 IOC 存在,也不在库里登记任何东西"""
    path = IOC.create_template("ioca", directory=tmp_path)
    check("路径", path, str(tmp_path / settings.CONFIG_FILE_NAME))
    check("库里没有", fresh.list_iocs(), [])
    check_true("IOCS_DIR 里没有", not os.path.exists(os.path.join(settings.IOCS_DIR, "ioca")))
    conf = IocConfig(path)
    conf.load()
    check("模板里的名字是 IOC 的名字,不是目录名", conf.data.basic.name, "ioca")


def test_create_template_without_a_directory_uses_the_current_one(fresh, tmp_path, monkeypatch):
    """IOC.create_template: 不给目录就写在当前目录(终端在哪里执行就在哪里)"""
    monkeypatch.chdir(tmp_path)
    path = IOC.create_template("ioca", build_type="modbus")
    check("路径", Path(path).resolve(), (tmp_path / settings.CONFIG_FILE_NAME).resolve())
    check_true("文件在", Path(path).is_file())


def test_create_template_never_overwrites_and_checks_the_name(tmp_path):
    """IOC.create_template: 已有的文件不覆盖(用户可能已经改过);名字不合法报 ValueError,不写文件"""
    path = Path(IOC.create_template("ioca", directory=tmp_path))
    path.write_text("edited by the user\n")
    with expect_error(FileExistsError, "已有文件"):
        IOC.create_template("ioca", directory=tmp_path)
    check("没被覆盖", path.read_text(), "edited by the user\n")
    other = tmp_path / "other"
    other.mkdir()
    with expect_error(ValueError, "名字不合法"):
        IOC.create_template("Bad_Name", directory=other)
    check("没有写文件", list(other.iterdir()), [])


def test_a_template_copied_into_the_ioc_directory_is_a_valid_config(fresh, tmp_path):
    """IOC.create_template + IOC.create: 模板放进 IOC 目录后,配置有效,名字和目录名对得上,没有警告"""
    template = IOC.create_template("ioca", build_type="stream_device", directory=tmp_path)
    ioc = IOC.create("ioca")
    shutil.copy(template, ioc.config_path)
    ioc.config.load()
    check("没有问题", ioc.config.issues, [])
    check("有效", ioc.config.is_valid, True)
    check("仓库里它是新增的文件", ioc.repository.status()["added"], [settings.CONFIG_FILE_NAME])


def test_create_of_a_name_in_the_database_changes_nothing(fresh):
    """IOC.create: 库里已经有这个名字就报 IocExistsError,已有的东西不动"""
    first = IOC.create("ioca")
    mine = Path(first.dir_path) / "src" / "mine.db"
    mine.write_text("keep me\n")
    before = fresh.read_ioc("ioca")
    with expect_error(IocExistsError, "再建一次"):
        IOC.create("ioca")
    check("库里还是一个", fresh.list_iocs(), ["ioca"])
    check("状态没动", fresh.read_ioc("ioca"), before)
    check("文件没动", mine.read_text(), "keep me\n")
    check_true("仓库还在", first.repository.exists())


def test_create_of_a_name_whose_directory_exists_leaves_the_directory_alone(fresh):
    """IOC.create: 目录已经有了(库里没有)也报 IocExistsError,而且不会把别人的目录当成自己的清理掉"""
    leftover = Path(settings.IOCS_DIR) / "ioca"
    leftover.mkdir(parents=True)
    (leftover / "mine.txt").write_text("keep me\n")
    with expect_error(IocExistsError, "目录已存在"):
        IOC.create("ioca")
    check("文件还在", (leftover / "mine.txt").read_text(), "keep me\n")
    check("目录里没有多出东西", sorted(p.name for p in leftover.iterdir()), ["mine.txt"])
    check("库里没有", fresh.list_iocs(), [])


@pytest.mark.parametrize(
    "target, why",
    [
        ("core.ioc_repository.IocRepository.init", "初始化仓库时"),
        ("core.ioc_state.IocStateManager.write_ioc", "写库时"),
    ],
    ids=lambda v: v if v.startswith("core") else None,
)
def test_create_that_fails_removes_what_it_made(fresh, monkeypatch, target, why):
    """IOC.create: 哪一步失败都把已经建好的目录清掉、库里不留记录,并报 IocInitError"""
    module, cls, attr = target.rsplit(".", 2)
    owner = getattr(__import__(module, fromlist=[cls]), cls)

    def boom(*args, **kwargs):
        raise OSError("disk on fire")

    monkeypatch.setattr(owner, attr, boom)
    with expect_error(IocInitError, why) as info:
        IOC.create("ioca")
    check_true("原因在消息里", "disk on fire" in str(info.value))
    check_true("原因接在后面", isinstance(info.value.__cause__, OSError))
    check_true("目录没有留下", not os.path.exists(os.path.join(settings.IOCS_DIR, "ioca")))
    check("库里没有", fresh.list_iocs(), [])
    monkeypatch.undo()
    check_true("之后可以正常创建", isinstance(IOC.create("ioca"), IOC))


def test_create_that_cannot_make_src_removes_the_directory(fresh, monkeypatch):
    """IOC.create: 建 src 失败也清理刚建的目录"""
    real_mkdir = os.mkdir

    def mkdir_that_fails_for_src(path, *args, **kwargs):
        if os.path.basename(path) == "src":
            raise PermissionError("no src for you")
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", mkdir_that_fails_for_src)
    with expect_error(IocInitError, "建 src 时"):
        IOC.create("ioca")
    check_true("目录没有留下", not os.path.exists(os.path.join(settings.IOCS_DIR, "ioca")))
    check("库里没有", fresh.list_iocs(), [])


def test_create_that_meets_a_directory_made_at_the_last_moment_leaves_it_alone(fresh, monkeypatch):
    """IOC.create: 检查之后、建目录之前有人手动建了同名目录:报 IocExistsError,那个目录和里面的东西不动,库里没有记录"""
    d = Path(settings.IOCS_DIR) / "ioca"
    d.mkdir(parents=True)
    (d / "mine.txt").write_text("keep me\n")
    monkeypatch.setattr(IOC, "check_presence", classmethod(lambda cls, name: "missing"))  # it was not there yet
    with expect_error(IocExistsError, "后来才有的目录") as info:
        IOC.create("ioca")
    check_true("说的是目录已存在", "directory" in str(info.value) and "exists" in str(info.value), str(info.value))
    check("文件还在", (d / "mine.txt").read_text(), "keep me\n")
    check("目录里没有多出东西", sorted(p.name for p in d.iterdir()), ["mine.txt"])
    check("库里没有", fresh.list_iocs(), [])


def test_create_that_is_interrupted_cleans_up_and_raises_the_interrupt_itself(fresh, monkeypatch):
    """IOC.create: 被 Ctrl-C 打断也清理,而且抛的还是 KeyboardInterrupt,不包成 IocInitError"""

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(IocRepository, "init", interrupted)
    with expect_error(KeyboardInterrupt, "打断"):
        IOC.create("ioca")
    check_true("目录没有留下", not os.path.exists(os.path.join(settings.IOCS_DIR, "ioca")))
    check("库里没有", fresh.list_iocs(), [])


CREATE_SLOWLY = """
import sys, time
sys.path.insert(0, sys.argv[1])
from core import settings
settings.DEFAULT_DB_PATH, settings.IOCS_DIR = sys.argv[2], sys.argv[3]
from core.ioc_repository import IocRepository
real_init = IocRepository.init
def slow_init(self, *args, **kwargs):
    real_init(self, *args, **kwargs)
    time.sleep(1.5)  # the directory and the repository are there, the record is not yet
IocRepository.init = slow_init
from core.ioc import IOC
IOC.create("ioca")
"""


def test_opening_an_ioc_that_another_process_is_still_creating_waits_for_it(fresh):
    """IOC.create: 别的进程正在创建(目录和仓库已经有、记录还没写)时,这时打开同名 IOC 会等它做完,拿到完整的 IOC,不会抢先给目录补记录"""
    proc = subprocess.Popen(
        [sys.executable, "-I", "-c", CREATE_SLOWLY, str(REPO_ROOT), settings.DEFAULT_DB_PATH, settings.IOCS_DIR],
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        git_dir = Path(settings.IOCS_DIR) / "ioca" / ".git"
        deadline = time.monotonic() + 10
        while not git_dir.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        check_true("创建进程已经建好目录和仓库", git_dir.exists())
        check("这时库里还没有记录", fresh.exists("ioca"), False)
        started = time.monotonic()
        opened = IOC("ioca")
        waited = time.monotonic() - started
        note("等了(秒)", round(waited, 2))
        check_true("确实等了它", waited > 0.5)
        check("拿到的是完整的 IOC", IOC.check_presence("ioca"), "complete")
        check("只有创建时那一条记录", [i.message for i in opened.state_data.issues], ["created"])
        check_true("没有补记录的 RECORD_RESET", not any(i.reason == IssueReason.RECORD_RESET for i in opened.state_data.issues))
    finally:
        proc.wait(timeout=20)
    check("创建进程成功结束", proc.returncode, 0)
    check("它没有报错", proc.stderr.read(), "")


def test_create_that_fails_takes_its_files_away_before_anyone_else_can_look(fresh, monkeypatch):
    """IOC.create: 失败时先把自己建的东西删掉,再放开数据库锁,所以别人不会看到做了一半的目录"""
    seen = {}

    def failing_write(self, *args, **kwargs):
        raise OSError("disk on fire")

    monkeypatch.setattr(type(fresh), "write_ioc", failing_write)
    real_transaction = type(fresh).transaction

    from contextlib import contextmanager

    @contextmanager
    def watching(self):
        try:
            with real_transaction(self):
                yield self
        finally:
            seen["directory_after_lock_was_let_go"] = os.path.exists(os.path.join(settings.IOCS_DIR, "ioca"))

    monkeypatch.setattr(type(fresh), "transaction", watching)
    with expect_error(IocInitError, "写库失败"):
        IOC.create("ioca")
    check("锁放开时目录已经没有了", seen, {"directory_after_lock_was_let_go": False})


def test_opening_a_directory_whose_creation_failed_meanwhile_is_not_found(fresh, monkeypatch):
    """IOC: 打开只有目录的 IOC 时拿到写锁后发现目录已经没了(创建失败清理掉了),报 IocNotFoundError,不会给不存在的目录补记录"""
    d = Path(settings.IOCS_DIR) / "ioca"
    d.mkdir(parents=True)
    real_exists = type(fresh).exists

    def exists_then_the_directory_is_gone(self, name):
        result = real_exists(self, name)
        shutil.rmtree(d, ignore_errors=True)
        return result

    monkeypatch.setattr(type(fresh), "exists", exists_then_the_directory_is_gone)
    with expect_error(IocNotFoundError, "目录没了"):
        IOC("ioca")
    monkeypatch.undo()
    check("没有补出记录", fresh.list_iocs(), [])


def test_create_records_that_it_happened_and_says_so_for_an_existing_directory(fresh):
    """IOC.create: 成功后记一条 INFO 的操作记录;在已有目录上创建时消息不同;重置有记录的 IOC 时旧记录清掉"""
    a = IOC.create("ioca")
    check("记录", [(i.level, i.reason, i.message) for i in a.state_data.issues], [(IssueLevel.INFO, IssueReason.OPERATION_SUCCESS, "created")])
    (Path(settings.IOCS_DIR) / "iocb").mkdir()
    b = IOC.create("iocb", force=True)
    check("已有目录", [i.message for i in b.state_data.issues], ["created on the existing directory"])
    a.record_success("exported")
    shutil.rmtree(a.dir_path)
    again = IOC.create("ioca", force=True)
    check("重新创建后只有新的一条", [i.message for i in again.state_data.issues], ["created"])


def test_record_success_and_record_failure_add_issues_that_refresh_never_removes(ioc, fresh):
    """record_success / record_failure: 成功是 INFO + OPERATION_SUCCESS,失败是 ERROR + OPERATION_FAILED;一条条追加,refresh 不会刷掉,顺序不变"""
    ioc.record_success("built")
    ioc.record_failure("export failed: no space left")
    ioc.record_success("exported")
    (Path(ioc.src_path) / "a.db").write_text("x\n")
    ioc.refresh()
    ioc.refresh()
    ops = [i for i in ioc.state_data.issues if i.reason in (IssueReason.OPERATION_SUCCESS, IssueReason.OPERATION_FAILED)]
    check(
        "按顺序",
        [(i.level, i.reason, i.message) for i in ops],
        [
            (IssueLevel.INFO, IssueReason.OPERATION_SUCCESS, "created"),
            (IssueLevel.INFO, IssueReason.OPERATION_SUCCESS, "built"),
            (IssueLevel.ERROR, IssueReason.OPERATION_FAILED, "export failed: no space left"),
            (IssueLevel.INFO, IssueReason.OPERATION_SUCCESS, "exported"),
        ],
    )
    check("库里一样", [i for i in fresh.read_issues("ioca") if i in ops], ops)
    check_true("同时 refresh 查出来的 FILE_CHANGED 也在", any(i.reason == IssueReason.FILE_CHANGED for i in ioc.state_data.issues))


# ------------------------------------------------------------------ refresh


@pytest.fixture
def ioc(fresh, tmp_path):
    """An IOC whose config is valid and committed, with nothing changed since"""
    made = IOC.create("ioca")
    shutil.copy(IOC.create_template("ioca", directory=tmp_path), made.config_path)
    made.repository.commit("config")
    return made.refresh() and made


def kinds(ioc):
    return [(i.level.value, i.reason.value) for i in problems(ioc.state_data.issues)]


def test_refresh_of_an_ioc_that_is_in_order_finds_nothing(ioc):
    """refresh: 一切正常时没有 issue,src_files 是空的"""
    check("issues", problems(ioc.state_data.issues), [])
    check("src_files", ioc.state_data.src_files.model_dump(), new_state().src_files.model_dump())


def test_opening_an_ioc_does_not_look_at_the_files_but_refresh_does(ioc, fresh):
    """IOC(name): 打开只读记录,不看文件;refresh 才去看并写回库"""
    (Path(ioc.src_path) / "a.db").write_text("x\n")
    opened = IOC("ioca")
    check("打开时还是旧的", opened.state_data.src_files.db_files, [])
    check("库里也还是旧的", fresh.read_ioc("ioca").src_files.db_files, [])
    check("refresh 之后更新了", opened.refresh().src_files.db_files, ["a.db"])
    check("库里也更新了", fresh.read_ioc("ioca").src_files.db_files, ["a.db"])


def test_refresh_sorts_the_source_files_by_suffix_and_ignores_the_rest(ioc):
    """refresh: src_files 按后缀分成 db / 协议 / 其他,排序;隐藏文件和子目录不算;删掉文件后也同步"""
    src = Path(ioc.src_path)
    for name in ["b.db", "a.db", "x.proto", "readme.txt", "ioc.cmd", ".hidden.db"]:
        (src / name).write_text("x\n")
    (src / "sub").mkdir()
    (src / "sub" / "deep.db").write_text("x\n")
    files = ioc.refresh().src_files
    check("db_files", files.db_files, ["a.db", "b.db"])
    check("protocol_files", files.protocol_files, ["x.proto"])
    check("other_files", files.other_files, ["ioc.cmd", "readme.txt"])
    (src / "a.db").unlink()
    check("删掉之后", ioc.refresh().src_files.db_files, ["b.db"])


def test_refresh_records_a_config_that_is_invalid_and_forgets_it_once_fixed(ioc):
    """refresh: 配置有问题就记成 issue,改好之后 issue 自己消失"""
    good = Path(ioc.config_path).read_text(encoding="utf-8")
    Path(ioc.config_path).write_text("basic: [not, a, mapping]\n", encoding="utf-8")
    ioc.refresh()
    check_true("有 VALIDATION_ERROR", any(r == "validation_error" for _, r in kinds(ioc)), kinds(ioc))
    Path(ioc.config_path).write_text(good, encoding="utf-8")
    ioc.repository.commit("fixed")
    check("改好之后没有了", problems(ioc.refresh().issues), [])


def test_refresh_reports_a_missing_config_as_information(fresh):
    """refresh: 还没有配置文件只是一条 INFO,不算错误"""
    ioc = IOC.create("ioca")
    ioc.refresh()
    check("issues", kinds(ioc), [("info", "file_error")])


def test_refresh_reports_files_that_differ_from_the_latest_snapshot(ioc):
    """refresh: 相对最近一次提交,改了、新增、删除的文件各记一条 FILE_CHANGED;改回去就没了"""
    src = Path(ioc.src_path)
    good_config = Path(ioc.config_path).read_text(encoding="utf-8")
    (src / "a.db").write_text("one\n")
    ioc.repository.commit("a")
    check("没有变化", problems(ioc.refresh().issues), [])
    (src / "a.db").write_text("two\n")
    (src / "new.db").write_text("x\n")
    Path(ioc.config_path).unlink()
    ioc.refresh()
    changed = [i for i in ioc.state_data.issues if i.reason == IssueReason.FILE_CHANGED]
    check(
        "改动的文件",
        sorted(i.message.split(" since")[0] for i in changed),
        ["ioc-config.yaml: deleted", "src/a.db: modified", "src/new.db: added"],
    )
    check_true("消息带着快照 id", all(ioc.repository.head()[:8] in i.message for i in changed))
    (src / "a.db").write_text("one\n")
    (src / "new.db").unlink()
    Path(ioc.config_path).write_text(good_config, encoding="utf-8")
    check("改回去之后没有了", problems(ioc.refresh().issues), [])


def test_refresh_does_not_look_for_changes_before_there_is_a_snapshot(fresh):
    """refresh: 还没有任何提交时没有可比较的,不报 FILE_CHANGED"""
    ioc = IOC.create("ioca")
    (Path(ioc.src_path) / "a.db").write_text("x\n")
    ioc.refresh()
    check_true("没有 FILE_CHANGED", not any(r == "file_changed" for _, r in kinds(ioc)), kinds(ioc))


def test_refresh_reports_a_missing_repository_and_a_missing_src(ioc):
    """refresh: .git 或 src 没了各记一条 WARNING"""
    shutil.rmtree(Path(ioc.dir_path) / ".git")
    shutil.rmtree(ioc.src_path)
    ioc.refresh()
    check_true("说没有 git 仓库", any("no git repository" in m for m in messages_of(ioc)), messages_of(ioc))
    check_true("说读不了 src", any("source directory" in m for m in messages_of(ioc)), messages_of(ioc))
    check("都是 WARNING", {i.level for i in problems(ioc.state_data.issues)}, {IssueLevel.WARNING})
    check("src_files 清空", ioc.state_data.src_files.model_dump(), new_state().src_files.model_dump())


def test_refresh_survives_a_git_that_fails_and_says_so(ioc, monkeypatch):
    """refresh: 读 git 失败不会让 refresh 抛错,记成一条 ERROR"""
    from core.exceptions import IocRepositoryError

    def broken(self):
        raise IocRepositoryError("git on fire")

    monkeypatch.setattr(IocRepository, "status", broken)
    (Path(ioc.src_path) / "a.db").write_text("x\n")
    ioc.refresh()
    check_true("记了 ERROR", any(i.level == IssueLevel.ERROR and "git on fire" in i.message for i in ioc.state_data.issues), messages_of(ioc))
    check("src_files 照常更新", ioc.state_data.src_files.db_files, ["a.db"])


def test_a_problem_that_stays_is_not_added_again_and_keeps_the_time_it_was_first_seen(ioc, fresh):
    """refresh: 同一个问题一直在时只有一条,时间还是第一次发现的时间,而且没有变化时不写库"""
    (Path(ioc.src_path) / "a.db").write_text("x\n")
    first = problems(ioc.refresh().issues)
    check("一条", len(first), 1)
    writes = []
    real = type(fresh).write_issues
    original_time = first[0].time
    import core.ioc as ioc_module

    ioc_module.get_now_str = lambda: "later"  # what a new issue would be stamped with
    try:
        type(fresh).write_issues = lambda self, *a, **k: (writes.append(a), real(self, *a, **k))[1]
        again = problems(ioc.refresh().issues)
        reopened = problems(IOC("ioca").state_data.issues)
    finally:
        type(fresh).write_issues = real
        import core.utils as utils
        ioc_module.get_now_str = utils.get_now_str
    check("还是那一条", again, first)
    check("重新打开也是", reopened, first)
    check("时间没变", again[0].time, original_time)
    check("没有写过库", writes, [])


def test_a_change_adds_the_new_problem_and_keeps_the_old_one_as_it_was(ioc):
    """refresh: 又出现新问题时,旧的那条保持原样(包括时间),新的加在后面"""
    (Path(ioc.src_path) / "a.db").write_text("x\n")
    first = problems(ioc.refresh().issues)
    (Path(ioc.src_path) / "b.db").write_text("x\n")
    second = problems(ioc.refresh().issues)
    check("两条", len(second), 2)
    check_true("旧的还在而且没变", first[0] in second)


def test_refresh_leaves_issues_of_other_kinds_alone(ioc, fresh):
    """refresh: 不是它自己查出来的 issue(RECORD_RESET)不会被刷掉"""
    fresh.write_issues("ioca", [IssueEntry(level=IssueLevel.ERROR, reason=IssueReason.RECORD_RESET, message="reset", prompt="", time="t")], append=True)
    (Path(ioc.src_path) / "a.db").write_text("x\n")
    ioc.refresh()
    check_true("RECORD_RESET 还在", any(i.reason == IssueReason.RECORD_RESET and i.message == "reset" for i in ioc.state_data.issues))
    ioc.refresh()
    check("仍然只有一条", sum(i.reason == IssueReason.RECORD_RESET for i in ioc.state_data.issues), 1)


def test_refresh_of_a_directory_that_is_gone_only_records_that(ioc, fresh):
    """refresh: 目录没了只记一条目录丢了,src_files 保持原样不被清空,目录回来后这条消失"""
    (Path(ioc.src_path) / "a.db").write_text("x\n")
    ioc.repository.commit("a")
    ioc.refresh()
    backup = Path(str(ioc.dir_path) + ".bak")
    os.rename(ioc.dir_path, backup)
    ioc.refresh()
    check("只有一条", [m.split(":")[1].strip().split(",")[0] for m in messages_of(ioc)], ["is in the database"])
    check("src_files 没被清空", ioc.state_data.src_files.db_files, ["a.db"])
    os.rename(backup, ioc.dir_path)
    check("回来后没有了", problems(ioc.refresh().issues), [])


def test_successes_and_failures_share_one_limit_and_the_newest_are_kept(ioc, fresh, monkeypatch):
    """record_success / record_failure: 成功和失败共用 MAX_OPERATION_RECORDS,超过就丢最旧的(不分成败),顺序不变;refresh 查出来的问题不受影响"""
    check("默认保留 100 条", settings.MAX_OPERATION_RECORDS, 100)
    monkeypatch.setattr(settings, "MAX_OPERATION_RECORDS", 3)
    (Path(ioc.src_path) / "a.db").write_text("x\n")
    ioc.refresh()
    ioc.record_success("op1")
    ioc.record_failure("op2")
    ioc.record_failure("op3")
    ioc.record_success("op4")
    ioc.record_failure("op5")
    ops = lambda issues: [(i.reason, i.message) for i in issues if i.reason in (IssueReason.OPERATION_SUCCESS, IssueReason.OPERATION_FAILED)]
    expected = [
        (IssueReason.OPERATION_FAILED, "op3"),
        (IssueReason.OPERATION_SUCCESS, "op4"),
        (IssueReason.OPERATION_FAILED, "op5"),
    ]
    check("对象里最新的 3 条", ops(ioc.state_data.issues), expected)
    check("库里一样", ops(fresh.read_issues("ioca")), expected)
    check_true("refresh 查出来的问题还在", any(i.reason == IssueReason.FILE_CHANGED for i in fresh.read_issues("ioca")))
    ioc.refresh()
    check("refresh 之后也一样", ops(fresh.read_issues("ioca")), expected)


def test_nothing_is_dropped_while_there_is_room(ioc, monkeypatch):
    """record_success / record_failure: 没超过上限时一条都不丢(包括创建时的那一条)"""
    monkeypatch.setattr(settings, "MAX_OPERATION_RECORDS", 3)
    ioc.record_success("op1")
    ioc.record_failure("op2")
    check(
        "三条",
        [i.message for i in ioc.state_data.issues if i.reason in (IssueReason.OPERATION_SUCCESS, IssueReason.OPERATION_FAILED)],
        ["created", "op1", "op2"],
    )


def test_refresh_all_refreshes_every_ioc_that_has_a_record(fresh):
    """IOC.refresh_all: 库里每个 IOC 都 refresh,返回 {名字: None}"""
    a, b = IOC.create("ioca"), IOC.create("iocb")
    (Path(a.src_path) / "a.db").write_text("x\n")
    (Path(b.src_path) / "b.proto").write_text("x\n")
    check("结果", IOC.refresh_all(), {"ioca": None, "iocb": None})
    check("ioca", fresh.read_ioc("ioca").src_files.db_files, ["a.db"])
    check("iocb", fresh.read_ioc("iocb").src_files.protocol_files, ["b.proto"])


def test_refresh_all_with_no_iocs_does_nothing(fresh):
    """IOC.refresh_all: 库里一个 IOC 也没有时返回空"""
    check("结果", IOC.refresh_all(), {})


def test_one_ioc_that_cannot_be_refreshed_does_not_stop_the_others(fresh, monkeypatch):
    """IOC.refresh_all: 有一个 IOC 出错,错误放进结果里,其他的照常 refresh"""
    IOC.create("ioca")
    bad = IOC.create("iocb")
    IOC.create("iocc")
    (Path(bad.src_path).parent / "x").mkdir()
    real = IOC.refresh

    def refresh_that_fails_for_iocb(self):
        if self.name == "iocb":
            raise OSError("disk on fire")
        return real(self)

    monkeypatch.setattr(IOC, "refresh", refresh_that_fails_for_iocb)
    results = IOC.refresh_all()
    check("出错的是 iocb", sorted(n for n, e in results.items() if e is not None), ["iocb"])
    check_true("错误原样放在结果里", isinstance(results["iocb"], OSError) and "disk on fire" in str(results["iocb"]))
    check_true("其他的 refresh 了(有了配置文件还没有的提示)", all(fresh.read_issues(n) for n in ("ioca", "iocc")))


def test_refresh_all_does_not_make_a_record_for_a_directory_that_has_none(fresh):
    """IOC.refresh_all: 只有目录没有记录的不去碰(打开它会补记录;正在创建的 IOC 也还没有记录)"""
    IOC.create("ioca")
    (Path(settings.IOCS_DIR) / "iocb" / "src").mkdir(parents=True)
    IOC.refresh_all()
    check("库里还是只有 ioca", fresh.list_iocs(), ["ioca"])


def test_refresh_all_survives_a_name_in_the_database_that_is_not_a_valid_ioc_name(fresh):
    """IOC.refresh_all: 库里有个不合法的名字(别的途径写进去的),记成 ValueError,不影响其他"""
    IOC.create("ioca")
    add_ioc(fresh, "Bad_Name")
    results = IOC.refresh_all()
    check_true("Bad_Name 是 ValueError", isinstance(results["Bad_Name"], ValueError))
    check("ioca 正常", results["ioca"], None)


def test_refresh_all_records_a_directory_that_has_gone(fresh):
    """IOC.refresh_all: 目录被删了的 IOC 记一条 issue,其他不受影响"""
    IOC.create("ioca")
    IOC.create("iocb")
    shutil.rmtree(os.path.join(settings.IOCS_DIR, "iocb"))
    IOC.refresh_all()
    check_true("iocb 有目录丢了的 issue", any("directory is missing" in i.message for i in fresh.read_issues("iocb")))
    check_true("ioca 没有", not any("directory is missing" in i.message for i in fresh.read_issues("ioca")))
