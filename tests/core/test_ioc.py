import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from core import ioc_config
from core.exceptions import IocNotFoundError
from core.ioc import IOC, IocConfig, state_manager
from core.ioc_state import IocStateManager
from core.ioc_schema import (
    IocStateSchema,
    IssueEntry,
    IssueLevel,
    IssueReason,
    new_state,
)
from core.utils import get_now_str, get_yaml_tool
from tests.logutil import check, check_true, expect_error, note, step

REPO_ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


def messages(conf):
    return [i.message for i in conf.issues]


# ---------------------------------------------------------------- IocConfig
# A change a person would make in an editor is written as a variant of the
# generated text (base), so there is nothing to undo between steps.


def test_create_template_names_config_after_directory(make_conf):
    """create_template: 生成的配置文件以目录名命名,能直接加载,没有 .tmp 残留"""
    conf = make_conf("ioc-demo")
    check("文件存在", conf.file_exists(), True)
    conf.load()
    check("issues", conf.issues, [])
    check("is_valid", conf.is_valid, True)
    check("basic.name", conf.data.basic.name, "ioc-demo")
    check_true("配置里没有 src 段", "src" not in conf.data.model_dump())
    check(
        ".tmp 残留",
        [p for p in Path(conf.path).parent.iterdir() if p.suffix == ".tmp"],
        [],
    )


def test_create_template_never_overwrites(make_conf):
    """create_template: 已有文件时拒绝覆盖"""
    conf = make_conf()
    with expect_error(FileExistsError, "文件已存在"):
        IocConfig.create_template(conf.path, None)


def test_create_template_with_awkward_directory_name(make_conf):
    """create_template: 目录名含引号、中文、反斜杠时也能正确生成并加载"""
    conf = make_conf('ioc "测试" #1\\x')
    conf.load()
    check("basic.name", conf.data.basic.name, 'ioc "测试" #1\\x')


@pytest.mark.parametrize("build_type", ["modbus", "stream_device", " Modbus "], ids=repr)
def test_create_template_for_each_build_type(tmp_path, build_type):
    """create_template: 各种 build_type 都能生成可直接加载的配置"""
    path = tmp_path / "ioc-typed" / "ioc.yaml"
    path.parent.mkdir()
    step(f"create_template(build_type={build_type!r})")
    IocConfig.create_template(str(path), build_type)
    conf = IocConfig(str(path))
    conf.load()
    check("issues", conf.issues, [])
    check("basic.name", conf.data.basic.name, "ioc-typed")


def test_file_exists_is_false_before_create(tmp_path):
    """file_exists: 文件还没建时为 False"""
    check("file_exists", IocConfig(str(tmp_path / "ioc.yaml")).file_exists(), False)


def test_typed_access(make_conf):
    """data: 配置按类型访问,字段不存在时报 AttributeError"""
    conf = make_conf("t-get")
    conf.load()
    check("basic.host", conf.data.basic.host, "swarm")
    check("modules[0]", conf.data.build.modules[0], "autosave")
    check_true("默认不装 status-os", "status-os" not in conf.data.build.modules)
    check("macros['ABC']", conf.data.build.db_load[0].macros["ABC"], "xxx:")
    check("settings.report_info", conf.data.build.settings.report_info, True)
    with expect_error(AttributeError, "访问不存在的字段"):
        conf.data.build.no_such_field


def test_load_reads_hand_written_file_and_never_touches_it(make_conf):
    """load: 读取手写修改过的文件,并且绝不改动该文件"""
    conf = make_conf("t-load")
    base = read(conf.path)
    conf.load()
    check_true("load 之后文件没变", read(conf.path) == base)
    text = base + "# my own note\n"
    text = re.sub(r"image: ''.*", "image: registry.iasf/ioc:1.0", text)
    text = re.sub(
        r"cmd_at_dbload: ''.*",
        'cmd_at_dbload: |\n      line1\n      dbLoadRecords("x.db")',
        text,
    )
    text = text.replace("ABC: 'xxx:'", "P: 'xxx:'")
    step("手工修改 image、cmd_at_dbload、macros,并加一行注释")
    write(conf.path, text)
    conf.load()
    check_true("再次 load 后文件没变", read(conf.path) == text)
    check("issues", conf.issues, [])
    check("basic.image", conf.data.basic.image, "registry.iasf/ioc:1.0")
    check("macros['P']", conf.data.build.db_load[0].macros["P"], "xxx:")
    check(
        "cmd_at_dbload",
        conf.data.build.raw_cmd.cmd_at_dbload,
        'line1\ndbLoadRecords("x.db")\n',
    )


def test_empty_list_is_valid_and_stays_empty(make_conf):
    """load: 空列表是合法值,读出来仍是空列表"""
    conf = make_conf("t-check")
    base = read(conf.path)
    text = re.sub(r"modules:.*\n    - autosave\n    - caputlog", "modules: []", base)
    assert text != base
    write(conf.path, text)
    conf.load()
    check("is_valid", conf.is_valid, True)
    check("modules", conf.data.build.modules, [])


def test_invalid_value_becomes_an_issue_and_there_is_no_config(make_conf, tmp_path):
    """load: 取值不合法时产生 issue,data 为 None,show/to_string/save 都拒绝工作"""
    conf = make_conf("t-invalid")
    base = read(conf.path)
    step("把 cpus: '1' 改成 cpus: 1(类型不对)")
    write(conf.path, base.replace("cpus: '1'", "cpus: 1"))
    conf.load()
    check("data", conf.data, None)
    check("is_valid", conf.is_valid, False)
    check("issue 数量", len(conf.issues), 1)
    issue = conf.issues[0]
    note("issue", f"{issue.level.value}/{issue.reason.value}: {issue.message}")
    check_true("issue 是 IssueEntry", isinstance(issue, IssueEntry))
    check("level", issue.level, IssueLevel.ERROR)
    check("reason", issue.reason, IssueReason.VALIDATION_ERROR)
    check_true(
        "message 带字段路径", issue.message.startswith("deploy.resources.limits.cpus:")
    )

    never = tmp_path / "never-written.yaml"
    for method, args in (
        (conf.show, ()),
        (conf.to_string, ()),
        (conf.save, (str(never),)),
    ):
        with expect_error(RuntimeError, f"{method.__name__}() 在没有配置时"):
            method(*args)
    check_true("save 没有写出文件", not never.exists())

    # the issue is accepted by IocStateSchema as is
    state = IocStateSchema(
        state="error",
        snapshot="untracked",
        src_files={"db_files": [], "protocol_files": [], "other_files": []},
        issues=conf.issues,
    )
    check("这条 issue 可以直接放进 IocStateSchema", state.issues[0].message, issue.message)


def test_load_recovers_after_the_file_is_fixed(make_conf):
    """load: 文件修好之后再次 load,恢复正常"""
    conf = make_conf("t-invalid")
    base = read(conf.path)
    write(conf.path, base.replace("cpus: '1'", "cpus: 1"))
    conf.load()
    check("损坏时 data", conf.data, None)
    write(conf.path, base)
    conf.load()
    check_true("修好后有 data", conf.data is not None)
    check("修好后 issues", conf.issues, [])


def test_invalid_nested_value_is_reported_with_its_path(make_conf):
    """load: 嵌套字段取值不合法时,issue 里带完整路径"""
    conf = make_conf("t-invalid")
    write(conf.path, read(conf.path).replace("report_info: true", "report_info: maybe"))
    conf.load()
    note("issues", messages(conf))
    check_true(
        "路径为 build.settings.report_info",
        any(m.startswith("build.settings.report_info:") for m in messages(conf)),
    )


def test_missing_field_is_reported_including_nested_ones(make_conf):
    """load: 缺字段(含嵌套字段)会被指出来"""
    conf = make_conf("t-missing")
    base = read(conf.path)
    write(conf.path, base.replace("    report_info: true\n", ""))
    conf.load()
    check("data", conf.data, None)
    check("缺嵌套字段", messages(conf), ["build.settings.report_info: Field required"])
    write(conf.path, base.replace("  epics_env: {}\n", ""))
    conf.load()
    check("缺上层字段", messages(conf), ["build.epics_env: Field required"])


def test_extra_field_is_an_error_at_any_depth(make_conf):
    """load: 任何层级出现多余字段都报错"""
    conf = make_conf("t-extra")
    base = read(conf.path)
    write(conf.path, base.replace("  settings:\n", "  foo: 1\n  settings:\n"))
    conf.load()
    check("data", conf.data, None)
    check("上层多余", messages(conf), ["build.foo: Extra inputs are not permitted"])
    write(
        conf.path,
        base.replace("    caputlog_json: false", "    caputlog_json: false\n    bar: 2"),
    )
    conf.load()
    check(
        "嵌套多余",
        messages(conf),
        ["build.settings.bar: Extra inputs are not permitted"],
    )


def test_free_form_mapping_takes_any_key(make_conf):
    """load: macros 这类自由字典可以随意加键"""
    conf = make_conf("t-extra")
    text = read(conf.path).replace(
        "        ABC: 'xxx:'\n", "        ABC: 'xxx:'\n        Z: zzz\n"
    )
    assert "Z: zzz" in text
    write(conf.path, text)
    conf.load()
    check_true("有 data", conf.data is not None)
    check("issues", conf.issues, [])


def test_name_mismatch_is_a_warning_and_config_stays_usable(make_conf):
    """load: basic.name 与目录名不符只是 warning,配置仍可用但 is_valid 为 False"""
    conf = make_conf("t-name")
    base = read(conf.path)
    write(conf.path, base.replace("name: t-name", "name: other"))
    conf.load()
    check_true("仍有 data", conf.data is not None)
    check("issue 数量", len(conf.issues), 1)
    check("is_valid", conf.is_valid, False)  # usable, but the name check failed
    note("issue", conf.issues[0].message)
    check("level", conf.issues[0].level, IssueLevel.WARNING)
    check_true("message 以 basic.name: 开头", conf.issues[0].message.startswith("basic.name:"))
    check("reason", conf.issues[0].reason, IssueReason.VALIDATION_ERROR)
    write(conf.path, base)
    conf.load()
    check("改回之后 issues", conf.issues, [])
    check("改回之后 is_valid", conf.is_valid, True)


@pytest.mark.parametrize(
    "content, expected",
    [
        (b"basic: [unclosed\n", "while parsing a flow sequence"),
        (b"basic:\n  name: a\n  name: b\n", "found duplicate key"),
        (b"", "config file is empty"),
        (b"\xff\xfe\x00bad", "codec can't decode"),
    ],
    ids=["unclosed-bracket", "duplicate-key", "empty-file", "not-utf8"],
)
def test_unreadable_file_becomes_a_file_error_issue(tmp_path, content, expected):
    """load: 读不了的文件(语法错、重复键、空文件、乱码)变成 file_error 的 issue"""
    path = tmp_path / "bad.yaml"
    path.write_bytes(content)
    bad = IocConfig(str(path))
    check("file_exists", bad.file_exists(), True)
    bad.load()
    check("data", bad.data, None)
    check("issue 数量", len(bad.issues), 1)
    check("is_valid", bad.is_valid, False)
    note("message", bad.issues[0].message)
    check("reason", bad.issues[0].reason, IssueReason.FILE_ERROR)
    check("level", bad.issues[0].level, IssueLevel.ERROR)
    check_true(f"message 含 {expected!r}", expected in bad.issues[0].message)


@pytest.mark.parametrize(
    "content", ["- a\n- b\n", "just text\n", "42\n"], ids=["list", "string", "number"]
)
def test_yaml_root_that_is_not_a_mapping_is_reported_as_root(tmp_path, content):
    """load: YAML 根节点不是映射(列表、字符串、数字)时,issue 的路径是 <root>"""
    path = tmp_path / "ioc.yaml"
    path.write_text(content)
    conf = IocConfig(str(path))
    conf.load()
    check("data", conf.data, None)
    check("issue 数量", len(conf.issues), 1)
    note("issue", conf.issues[0].message)
    check_true("message 以 <root>: 开头", conf.issues[0].message.startswith("<root>:"))
    check("reason", conf.issues[0].reason, IssueReason.VALIDATION_ERROR)
    check("is_valid", conf.is_valid, False)


def test_load_of_a_missing_file_raises(tmp_path):
    """load: 文件不存在时抛 FileNotFoundError(这不是 issue)"""
    bad = IocConfig(str(tmp_path / "bad.yaml"))
    check("file_exists", bad.file_exists(), False)
    with expect_error(FileNotFoundError, "文件不存在", match="config file not found"):
        bad.load()
    check("data", bad.data, None)
    check("is_valid", bad.is_valid, False)


def test_file_that_vanishes_after_load_leaves_no_stale_result(make_conf):
    """load: 加载后文件被删,再 load 会报错,并且不留下上一次的旧结果"""
    conf = make_conf("t-vanish")
    conf.load()
    check("第一次 is_valid", conf.is_valid, True)
    Path(conf.path).unlink()
    step("删掉配置文件后再 load")
    with expect_error(FileNotFoundError, "文件没了"):
        conf.load()
    check("data", conf.data, None)
    check("issues", conf.issues, [])
    check("is_valid", conf.is_valid, False)


def test_use_before_load_raises(make_conf, tmp_path):
    """show/to_string/save: 还没 load 时拒绝工作"""
    fresh = make_conf("t-fresh")
    check("data", fresh.data, None)
    check("is_valid", fresh.is_valid, False)
    never = tmp_path / "never-written.yaml"
    for method, args in (
        (fresh.show, ()),
        (fresh.to_string, ()),
        (fresh.save, (str(never),)),
    ):
        with expect_error(RuntimeError, f"{method.__name__}() 在 load 之前"):
            method(*args)
    check_true("save 没有写出文件", not never.exists())
    fresh.load()
    check_true("load 之后有 data", fresh.data is not None)


def test_show_prints_plain_data_without_comments(make_conf, capsys):
    """show: 输出纯数据,不带注释和空行,内容与 to_string 一致"""
    conf = make_conf("t-show")
    with open(conf.path, "a", encoding="utf-8") as f:
        f.write("# my own note\n")
    conf.load()
    conf.show()
    out = capsys.readouterr().out
    check_true("没有注释符号和空行", "#" not in out and "\n\n" not in out)
    check_true("再解析得到同样的数据", get_yaml_tool().load(out) == conf.data.model_dump())
    check_true("与 to_string 一致", out == conf.to_string())


def test_save_writes_validated_config_and_leaves_source_untouched(make_conf, tmp_path):
    """save: 写出校验过的配置(不带注释),源文件不变"""
    source = make_conf("t-save")
    with open(source.path, "a", encoding="utf-8") as f:
        f.write("# my own note\n")
    source_text = read(source.path)
    source.load()
    target_path = tmp_path / "managed" / "t-save" / "ioc.yaml"
    target_path.parent.mkdir(parents=True)
    source.save(str(target_path))
    check_true("源文件没变", read(source.path) == source_text)
    target = IocConfig(str(target_path))
    target.load()
    check("目标文件的 issues", target.issues, [])
    check_true("目标与源的数据相同", target.data == source.data)
    check_true("注释没有被写出", "# my own note" not in read(target_path))


def test_save_of_an_invalid_config_writes_nothing(make_conf, tmp_path):
    """save: 配置不合法时什么都不写"""
    invalid = make_conf("t-save-invalid")
    write(invalid.path, read(invalid.path).replace("cpus: '1'", "cpus: 1"))
    invalid.load()
    check("data", invalid.data, None)
    other = tmp_path / "managed" / "t-save-invalid" / "ioc.yaml"
    other.parent.mkdir(parents=True)
    with expect_error(RuntimeError, "配置不合法"):
        invalid.save(str(other))
    check_true("没有写出文件", not other.exists())


def test_save_into_a_missing_directory_fails_and_creates_nothing(make_conf, tmp_path):
    """save: 目标目录不存在时报错,不会替你建目录"""
    conf = make_conf("t-save-nodir")
    conf.load()
    target = tmp_path / "no-such-dir" / "ioc.yaml"
    with expect_error(FileNotFoundError, "目录不存在"):
        conf.save(str(target))
    check_true("目录没有被创建", not target.parent.exists())


# ---------------------------------------------------------------- IocStateManager
# The database is created on purpose, never by accident.


def make_issue(message="m", level=IssueLevel.WARNING):
    return IssueEntry(
        level=level,
        reason=IssueReason.VALIDATION_ERROR,
        message=message,
        prompt="",
        time=get_now_str(),
    )


def opened(path, **kwargs):
    state = IocStateManager(path, **kwargs)
    state.connect()
    return state


def add_ioc(state, name, data=None):
    data = new_state() if data is None else data
    state.write_ioc(name, {f: getattr(data, f) for f in IocStateManager.ADAPTERS})
    state.write_issues(name, data.issues, append=True)


def count_issues(db):
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT COUNT(*) FROM issue").fetchone()[0]
    finally:
        con.close()


def snapshot_of(state, name="ioc-a"):
    return state.read_ioc(name).snapshot


@pytest.fixture
def db(tmp_path):
    """Path of a database that has been initialized and is empty."""
    path = str(tmp_path / "t-state" / "ioc-state.db")
    Path(path).parent.mkdir()
    IocStateManager.initialize(path)
    return path


@pytest.fixture
def st(db):
    """A connected instance holding two IOCs, ioc-a and ioc-b, in the new state."""
    state = opened(db)
    add_ioc(state, "ioc-b")
    add_ioc(state, "ioc-a")
    yield state
    state.close()


def test_database_is_created_only_by_initialize(tmp_path):
    """数据库只会被 initialize 创建,其他操作不会偷偷建库,也不会碰已有文件"""
    db = str(tmp_path / "ioc-state.db")
    missing = IocStateManager(db)  # building the instance does not touch the database
    check_true("IocStateManager(db) 没有建文件", not Path(db).exists())
    with expect_error(RuntimeError, "还没 connect 就读"):
        missing.list_iocs()
    with expect_error(FileNotFoundError, "库不存在时 connect"):
        missing.connect()
    check_true("connect 失败后仍没有文件", not Path(db).exists())

    Path(db).touch()
    step("放一个空文件在那里")
    with expect_error(RuntimeError, "空文件(没有表)"):
        opened(db)
    with expect_error(FileExistsError, "initialize 遇到已有文件"):
        IocStateManager.initialize(db)

    Path(db).unlink()
    IocStateManager.initialize(db)
    with expect_error(FileExistsError, "initialize 遇到已有数据库"):
        IocStateManager.initialize(db)
    con = sqlite3.connect(db)
    version = con.execute("PRAGMA user_version").fetchone()[0]
    con.close()
    check("user_version", version, IocStateManager.SCHEMA_VERSION)


def test_initialize_creates_missing_parent_directories(tmp_path):
    """initialize: 上级目录不存在时自动创建"""
    db = tmp_path / "a" / "b" / "ioc-state.db"
    check_true("上级目录起初不存在", not db.parent.exists())
    IocStateManager.initialize(str(db))
    check_true("数据库文件已创建", db.is_file())
    state = opened(str(db))
    check("list_iocs", state.list_iocs(), [])
    state.close()


def test_initialize_that_fails_leaves_no_file_behind(tmp_path, monkeypatch):
    """initialize: 建表失败时删掉半成品文件,并抛出原来的错误"""
    db = tmp_path / "ioc-state.db"
    step("把建表脚本换成无法执行的 SQL")
    monkeypatch.setattr(IocStateManager, "SCHEMA_SQL", "THIS IS NOT SQL")
    with expect_error(sqlite3.OperationalError, "建表失败", match="syntax error"):
        IocStateManager.initialize(str(db))
    check_true("没有留下文件", not db.exists())
    monkeypatch.undo()
    IocStateManager.initialize(str(db))
    check_true("之后可以正常 initialize", db.is_file())


def test_damaged_database_is_an_error_and_is_not_touched(tmp_path):
    """connect: 文件不是数据库时报错,并且不动它"""
    db = tmp_path / "ioc-state.db"
    db.write_bytes(b"this is not a database" * 100)
    with expect_error(sqlite3.DatabaseError, "乱码文件"):
        opened(str(db))
    with expect_error(FileExistsError, "initialize 不会覆盖它"):
        IocStateManager.initialize(str(db))


def test_database_that_fails_the_integrity_check_is_an_error(db):
    """connect: 完整性检查(quick_check)不通过时报错"""
    step("用 writable_schema 造一个 state 列为 NULL、却声明 NOT NULL 的库")

    def edit_schema(old, new):
        con = sqlite3.connect(db, isolation_level=None)
        con.execute("PRAGMA writable_schema = ON")
        con.execute(
            "UPDATE sqlite_master SET sql = replace(sql, ?, ?) WHERE name = 'ioc'",
            (old, new),
        )
        con.close()

    edit_schema("state     TEXT NOT NULL", "state     TEXT")
    con = sqlite3.connect(db, isolation_level=None)
    con.execute(
        "INSERT INTO ioc (name, state, snapshot, src_files) VALUES ('x', NULL, '\"\"', '{}')"
    )
    con.close()
    edit_schema("state     TEXT,", "state     TEXT NOT NULL,")
    with expect_error(sqlite3.DatabaseError, "完整性检查失败", match="integrity check failed"):
        opened(db)
    with expect_error(FileExistsError, "initialize 不会覆盖它"):
        IocStateManager.initialize(db)


def test_unknown_schema_version_is_an_error(db):
    """connect: 版本号对不上时报错"""
    other = sqlite3.connect(db)
    other.execute("PRAGMA user_version = 99")
    other.close()
    with expect_error(RuntimeError, "版本号 99", match="version 99"):
        opened(db)


def test_default_and_relative_database_paths(tmp_path, monkeypatch):
    """IocStateManager(): 不给路径用 ioc_config.DEFAULT_DB_PATH,相对路径会转成绝对路径,构造时不碰磁盘"""
    check("默认路径", IocStateManager().db_path, os.path.abspath(ioc_config.DEFAULT_DB_PATH))
    monkeypatch.chdir(tmp_path)
    state = IocStateManager("rel/state.db")
    check("相对路径", state.db_path, os.path.join(os.getcwd(), "rel", "state.db"))
    check("磁盘上没有任何东西", list(tmp_path.iterdir()), [])


def test_connect_twice_keeps_the_same_connection(st, db):
    """connect: 重复调用没有副作用,一次 close 就结束"""
    connection = st._conn
    st.connect()
    st.connect()
    check_true("还是原来的连接对象", st._conn is connection)
    check("list_iocs", st.list_iocs(), ["ioc-a", "ioc-b"])
    st.close()
    with expect_error(RuntimeError, "close 一次之后"):
        st.list_iocs()


def test_close_twice_is_harmless(db):
    """close: 重复调用不报错"""
    state = opened(db)
    state.close()
    state.close()
    note("两次 close", "都没有报错")


def test_write_read_list_delete(st, db):
    """写入、读取、列出、删除 IOC 的基本流程"""
    check("list_iocs", st.list_iocs(), ["ioc-a", "ioc-b"])
    data = st.read_ioc("ioc-a")
    check_true("读出的状态等于 new_state()", data == new_state())
    check("(state, snapshot)", (data.state, data.snapshot), ("", ""))
    check("issues", data.issues, [])
    check("db_files", data.src_files.db_files, [])

    st.delete_ioc("ioc-b")
    check("删除 ioc-b 之后", st.list_iocs(), ["ioc-a"])


def test_list_iocs_is_empty_after_initialize(db):
    """list_iocs: 新建的库里没有 IOC"""
    state = opened(db)
    check("list_iocs", state.list_iocs(), [])
    state.close()


def test_columns_keep_the_json_text_of_their_values(st, db):
    """存储格式: 每列保存值的 JSON 文本,列与 schema 字段一一对应"""
    con = sqlite3.connect(db)
    raw = con.execute(
        "SELECT state, snapshot, src_files FROM ioc WHERE name = 'ioc-a'"
    ).fetchone()
    note("数据库里的原始文本", raw)
    check(
        "原始文本",
        raw,
        ('""', '""', '{"db_files":[],"protocol_files":[],"other_files":[]}'),
    )
    # the columns of the table are the schema's fields (but issues), so none is left out.
    columns = [r[1] for r in con.execute("PRAGMA table_info(ioc)")]
    con.close()
    check("表的列", columns, ["name", *IocStateManager.ADAPTERS])
    check_true("issues 不是 ioc 表的列", "issues" not in IocStateManager.ADAPTERS)


def test_unknown_or_empty_name(st):
    """名字: 读不存在的 IOC 报 KeyError,空名字报 ValueError"""
    with expect_error(KeyError, "读不存在的 IOC"):
        st.read_ioc("ioc-none")
    with expect_error(ValueError, "空名字"):
        add_ioc(st, "")


@pytest.mark.parametrize("name", [None, 123, b"ioc-a"], ids=repr)
def test_a_name_that_is_not_a_string(st, name):
    """名字: 不是字符串时,写入报 ValueError,读和删找不到(KeyError)"""
    with expect_error(ValueError, "write_ioc"):
        st.write_ioc(name, {"snapshot": "x"})
    with expect_error(KeyError, "read_ioc"):
        st.read_ioc(name)
    with expect_error(KeyError, "delete_ioc"):
        st.delete_ioc(name)
    check("库没有变化", st.list_iocs(), ["ioc-a", "ioc-b"])


def test_any_name_is_just_a_value(st):
    """名字: 含引号、分号、SQL 语句的名字只是普通的值,不会被当成 SQL"""
    odd = 'ioc "测试" \'1\'; DROP TABLE ioc; --'
    add_ioc(st, odd)
    check_true("名字在列表里", odd in st.list_iocs())
    check_true("能读回", st.read_ioc(odd) == new_state())
    check_true("ioc 表还在", len(st.list_iocs()) == 3)
    st.delete_ioc(odd)
    check_true("删除后不在列表里", odd not in st.list_iocs())


def test_whole_state_can_be_written_and_invalid_one_is_not(st, db):
    """整体写入: 合法的状态能写入读回,非法的整个被拒绝且什么都不留"""
    custom = new_state()
    custom.snapshot = "tracked"
    custom.issues = [make_issue("kept")]
    add_ioc(st, "ioc-c", custom)
    check_true("读回的状态与写入的相同", st.read_ioc("ioc-c") == custom)

    custom.snapshot = 5
    step("写入 snapshot=5(类型不对)")
    with expect_error(ValidationError, "非法取值"):
        add_ioc(st, "ioc-d", custom)
    with expect_error(KeyError, "ioc-d 没有被建出来"):
        st.read_ioc("ioc-d")

    st.delete_ioc("ioc-c")
    with expect_error(KeyError, "删除之后读"):
        st.read_ioc("ioc-c")
    with expect_error(KeyError, "重复删除"):
        st.delete_ioc("ioc-c")
    check("issue 表里剩下的行数", count_issues(db), 0)


@pytest.mark.parametrize(
    "column, text",
    [("snapshot", "5"), ("snapshot", "not json"), ("src_files", "{}")],
    ids=["number-not-str", "not-json", "missing-keys"],
)
def test_content_that_does_not_fit_the_schema_is_an_error(st, db, column, text):
    """读取: 库里的内容不符合 schema(被外部改坏)时报 ValidationError"""
    step(f"绕过程序,直接把 {column} 改成 {text!r}")
    damage = sqlite3.connect(db)
    damage.execute(f"UPDATE ioc SET {column} = ? WHERE name = 'ioc-a'", (text,))
    damage.commit()
    damage.close()
    with expect_error(ValidationError, "读取被改坏的内容"):
        st.read_ioc("ioc-a")


def test_write_ioc_changes_only_the_given_columns(st):
    """write_ioc: 只改给出的列,其他列和其他 IOC 都不变"""
    st.write_ioc("ioc-a", {"state": "warning"})
    st.write_ioc(
        "ioc-a",
        {
            "snapshot": "tracked",
            "src_files": {
                "db_files": ["a.db"],
                "protocol_files": ["a.proto"],
                "other_files": [],
            },
        },
    )
    data = st.read_ioc("ioc-a")
    check("(state, snapshot)", (data.state, data.snapshot), ("warning", "tracked"))
    check("db_files", data.src_files.db_files, ["a.db"])
    check("protocol_files", data.src_files.protocol_files, ["a.proto"])
    check("other_files", data.src_files.other_files, [])
    check_true("另一个 IOC 没有被动", st.read_ioc("ioc-b") == new_state())


def test_write_ioc_rejects_invalid_values_as_a_whole(st):
    """write_ioc: 有一个值非法就整体拒绝,一个都不写"""
    st.write_ioc("ioc-a", {"state": "warning", "snapshot": "tracked"})
    with expect_error(ValidationError, "snapshot=5"):
        st.write_ioc("ioc-a", {"snapshot": 5})
    with expect_error(ValidationError, "db_files 不是列表"):
        st.write_ioc("ioc-a", {"src_files": {"db_files": "a.db"}})
    with expect_error(ValidationError, "一个坏值拦住全部"):
        st.write_ioc("ioc-a", {"state": "error", "snapshot": 5})
    data = st.read_ioc("ioc-a")
    check("(state, snapshot) 没变", (data.state, data.snapshot), ("warning", "tracked"))
    with expect_error(ValueError, "什么都不写"):
        st.write_ioc("ioc-a", {})
    with expect_error(ValueError, "issues 不是 ioc 表的列"):
        st.write_ioc("ioc-a", {"issues": []})


def test_write_ioc_of_a_new_ioc_needs_every_column(st):
    """write_ioc: 新建 IOC 时必须给齐所有列"""
    with expect_error(sqlite3.IntegrityError, "只给了 snapshot"):
        st.write_ioc("ioc-none", {"snapshot": "x"})
    with expect_error(KeyError, "没有留下半个 IOC"):
        st.read_ioc("ioc-none")
    check_true("不在列表里", "ioc-none" not in st.list_iocs())


def test_issues_are_appended_in_order_and_not_deduplicated(st):
    """write_issues(append=True): 按顺序追加,不去重"""
    st.write_ioc("ioc-a", {"state": "warning"})
    issue = make_issue("first")
    st.write_issues("ioc-a", [issue], append=True)
    st.write_issues(
        "ioc-a", [issue, make_issue("second", IssueLevel.ERROR)], append=True
    )
    data = st.read_ioc("ioc-a")
    check("message 顺序", [i.message for i in data.issues], ["first", "first", "second"])
    check("第三条的 level", data.issues[2].level, IssueLevel.ERROR)
    check("另一个 IOC 的 issues", st.read_issues("ioc-b"), [])


def test_write_issues_accepts_plain_dicts_and_an_empty_append(st):
    """write_issues: 可以传 dict;append=True 配空列表什么都不改"""
    entry = dict(level="info", reason="file_error", message="d", prompt="p", time="t")
    st.write_issues("ioc-a", [entry])
    issues = st.read_issues("ioc-a")
    check("条数", len(issues), 1)
    check("读回的 IssueEntry", issues[0], IssueEntry(**entry))
    st.write_issues("ioc-a", [], append=True)
    check("追加空列表之后", [i.message for i in st.read_issues("ioc-a")], ["d"])


def test_replacing_issues_leaves_the_state_alone(st):
    """write_issues: 替换 issue 不影响 IOC 的其他状态"""
    st.write_ioc("ioc-a", {"state": "warning"})
    st.write_issues("ioc-a", [make_issue("old")], append=True)
    st.write_issues("ioc-a", [make_issue("only")])  # replaces
    check("替换后", [i.message for i in st.read_issues("ioc-a")], ["only"])
    st.write_issues("ioc-a", [])
    data = st.read_ioc("ioc-a")
    check("清空后 issues", data.issues, [])
    check("state 没变", data.state, "warning")


def test_invalid_issue_stops_a_replace_before_the_old_log_is_touched(st):
    """write_issues: issue 非法时在动手之前就拒绝,旧记录保持原样"""
    issue = make_issue("x")
    st.write_issues("ioc-a", [make_issue("kept")])
    with expect_error(ValidationError, "level 不合法"):
        st.write_issues("ioc-a", [{"level": "nope"}])
    with expect_error(ValidationError, "第二条不合法"):
        st.write_issues("ioc-a", [issue, {"level": "nope"}])
    check("旧记录", [i.message for i in st.read_issues("ioc-a")], ["kept"])


def test_a_failing_insert_undoes_the_replace_and_the_append(st, db):
    """write_issues: 写到一半失败时整体撤销(替换不会丢旧记录,追加不会留下前几条)"""
    step("在库里加一个触发器,message 为 'bad' 的 issue 一律拒绝")
    con = sqlite3.connect(db, isolation_level=None)
    con.execute(
        "CREATE TRIGGER no_bad BEFORE INSERT ON issue WHEN NEW.message = 'bad' "
        "BEGIN SELECT RAISE(ABORT, 'bad issue'); END"
    )
    con.close()
    st.write_issues("ioc-a", [make_issue("kept")])

    with expect_error(sqlite3.IntegrityError, "替换:第二条被拒绝", match="bad issue"):
        st.write_issues("ioc-a", [make_issue("new"), make_issue("bad")])
    check("替换失败后旧记录还在", [i.message for i in st.read_issues("ioc-a")], ["kept"])

    with expect_error(sqlite3.IntegrityError, "追加:第二条被拒绝", match="bad issue"):
        st.write_issues("ioc-a", [make_issue("new"), make_issue("bad")], append=True)
    check("追加失败后第一条也没留下", [i.message for i in st.read_issues("ioc-a")], ["kept"])


def test_issues_of_an_ioc_that_is_not_there(st):
    """write_issues: 给不存在的 IOC 写 issue 报错,读则返回空"""
    with expect_error(sqlite3.IntegrityError, "IOC 不存在"):
        st.write_issues("ioc-none", [make_issue()])
    check("read_issues", st.read_issues("ioc-none"), [])
    st.write_issues("ioc-none", [])  # nothing to write for an IOC that is not there
    check_true("没有凭空建出 IOC", "ioc-none" not in st.list_iocs())


def test_deleting_an_ioc_deletes_its_issues(st, db):
    """delete_ioc: 删除 IOC 时它的 issue 一起被删"""
    st.write_issues("ioc-a", [make_issue()], append=True)
    check("删除前 issue 行数", count_issues(db), 1)
    st.delete_ioc("ioc-a")  # the issues go with it
    check("删除后 issue 行数", count_issues(db), 0)


# ------------------------------------------------------------- transactions


def test_transaction_commits_several_changes_as_one(st):
    """transaction: 块正常结束时,里面的多个操作一起生效"""
    with st.transaction():
        st.write_ioc("ioc-a", {"snapshot": "tracked"})
        st.write_issues("ioc-a", [make_issue("in tx")], append=True)
        add_ioc(st, "ioc-e")
    check("snapshot", snapshot_of(st), "tracked")
    check("issue 条数", len(st.read_issues("ioc-a")), 1)
    check_true("ioc-e 已加入", "ioc-e" in st.list_iocs())


def test_transaction_is_undone_together_when_the_block_raises(st):
    """transaction: 块里抛异常时,里面的多个操作一起撤销"""
    st.write_ioc("ioc-a", {"snapshot": "tracked"})
    add_ioc(st, "ioc-e")
    with expect_error(RuntimeError, "块里抛异常", match="boom"):
        with st.transaction():
            st.write_ioc("ioc-a", {"snapshot": "error"})
            st.delete_ioc("ioc-e")
            raise RuntimeError("boom")
    check("snapshot 回到原值", snapshot_of(st), "tracked")
    check_true("ioc-e 还在", "ioc-e" in st.list_iocs())


def test_failing_call_inside_a_transaction_undoes_the_calls_before_it(st):
    """transaction: 其中一个调用失败时,它之前的调用也撤销"""
    st.write_ioc("ioc-a", {"snapshot": "tracked"})
    with expect_error(KeyError, "删除不存在的 IOC"):
        with st.transaction():
            st.write_ioc("ioc-a", {"snapshot": "error"})
            st.delete_ioc("ioc-none")
    check("snapshot 回到原值", snapshot_of(st), "tracked")


def test_transaction_cannot_be_nested_and_leaves_nothing_open(st):
    """transaction: 不能嵌套,报错之后实例仍可正常使用"""
    with expect_error(RuntimeError, "嵌套"):
        with st.transaction():
            with st.transaction():
                pass
    st.write_ioc("ioc-a", {"snapshot": "tracked"})
    check("之后可以正常写", snapshot_of(st), "tracked")


def test_transaction_reads_its_own_writes_but_others_see_nothing_until_commit(st, db):
    """transaction: 块里能读到自己未提交的写入,别的连接要等提交后才看得到"""
    other = opened(db)
    try:
        with st.transaction():
            st.write_ioc("ioc-a", {"snapshot": "tracked"})
            check("块里自己读", snapshot_of(st), "tracked")
            check("块里别的连接读", snapshot_of(other), "")
        check("提交后别的连接读", snapshot_of(other), "tracked")
    finally:
        other.close()


def test_other_thread_waits_until_the_transaction_ends(st):
    """transaction: 事务期间,同一实例上别的线程的操作要等事务结束才能执行"""
    done = threading.Event()
    errors = []

    def other_thread():
        try:
            st.write_ioc("ioc-a", {"snapshot": "from-thread"})
        except BaseException as e:
            errors.append(e)
        finally:
            done.set()

    worker = threading.Thread(target=other_thread)
    with st.transaction():
        st.write_ioc("ioc-a", {"snapshot": "in-tx"})
        step("事务还开着时,启动另一个线程去写")
        worker.start()
        check("0.5 秒内线程没有完成", done.wait(0.5), False)
        check("事务里的值没被它改掉", snapshot_of(st), "in-tx")
    worker.join(5)
    check("事务结束后线程完成", done.is_set(), True)
    check("线程没有出错", errors, [])
    check("最后写入的是线程的值", snapshot_of(st), "from-thread")


def test_transaction_of_another_thread_waits_instead_of_failing_as_nested(st):
    """transaction: 另一个线程也想开事务时,要排队等待,不能被当成"嵌套"报错"""
    done = threading.Event()
    errors = []

    def other_thread():
        try:
            with st.transaction():
                st.write_ioc("ioc-a", {"snapshot": "from-thread"})
        except BaseException as e:
            errors.append(e)
        finally:
            done.set()

    worker = threading.Thread(target=other_thread)
    with st.transaction():
        st.write_ioc("ioc-a", {"snapshot": "in-tx"})
        step("事务还开着时,另一个线程也去开事务")
        worker.start()
        check("0.5 秒内线程在等待", done.wait(0.5), False)
    worker.join(5)
    check("线程的事务在之后完成", done.is_set(), True)
    check("线程没有出错", errors, [])
    check("最后写入的是线程的值", snapshot_of(st), "from-thread")


def test_transaction_waits_for_another_writer_instead_of_failing(st, db):
    """transaction: 先读后写的事务遇到别人正在写时,会等对方结束,而不是立刻失败"""
    other = opened(db)
    holding, release = threading.Event(), threading.Event()

    def hold():
        with other.transaction():
            other.write_ioc("ioc-b", {"snapshot": "held"})
            holding.set()
            release.wait(10)

    holder = threading.Thread(target=hold)
    holder.start()
    try:
        check("另一个连接已持有写事务", holding.wait(5), True)
        threading.Timer(0.5, release.set).start()
        step("先读后写的事务开始(对方 0.5 秒后结束)")
        started = time.monotonic()
        with st.transaction():
            st.read_ioc("ioc-a")
            st.write_ioc("ioc-a", {"snapshot": "tracked"})
        waited = time.monotonic() - started
        note("等待了", f"{waited:.2f} 秒")
        check_true("确实等了对方", waited >= 0.4, f"{waited:.2f}s")
        check("写入成功", snapshot_of(st), "tracked")
    finally:
        release.set()
        holder.join(5)
        other.close()


# ------------------------------------------------- how a transaction can fail


def test_begin_failure_that_is_not_busy_is_raised_as_it_is(st):
    """_txn: BEGIN 失败但不是锁忙时,原样抛出(不会被当成超时)"""
    step("手工开一个事务,让下一次 BEGIN 失败")
    st._conn.execute("BEGIN")
    try:
        with expect_error(
            sqlite3.OperationalError, "BEGIN 失败", match="within a transaction"
        ):
            st.list_iocs()
    finally:
        st._conn.execute("ROLLBACK")
    check("清理之后又能用了", st.list_iocs(), ["ioc-a", "ioc-b"])


def test_busy_error_inside_the_block_becomes_a_timeout(st):
    """_txn: 块里遇到"数据库被锁"时转成 TimeoutError,别的 OperationalError 不转"""
    with expect_error(TimeoutError, "锁忙", match="busy") as info:
        with st._txn(True):
            raise sqlite3.OperationalError("database is locked")
    check_true(
        "原始错误保留在 __cause__",
        isinstance(info.value.__cause__, sqlite3.OperationalError),
    )
    with expect_error(sqlite3.OperationalError, "别的运行错误", match="no such table"):
        with st._txn(True):
            raise sqlite3.OperationalError("no such table: ioc")
    check("两次失败后仍可用", st.list_iocs(), ["ioc-a", "ioc-b"])


def test_a_rollback_that_fails_does_not_hide_the_real_error(st):
    """_txn: ROLLBACK 自己失败时,抛出的仍是原来的错误,实例之后仍可用"""
    step("块里先让 SQLite 结束事务,再抛错,于是 _txn 的 ROLLBACK 会失败")
    with expect_error(RuntimeError, "原来的错误", match="boom"):
        with st._txn(True) as conn:
            conn.execute("ROLLBACK")
            raise RuntimeError("boom")
    check("之后仍可用", st.list_iocs(), ["ioc-a", "ioc-b"])
    st.write_ioc("ioc-a", {"snapshot": "tracked"})
    check("之后仍可写", snapshot_of(st), "tracked")


def test_busy_database_times_out_for_writers_but_not_readers(st, db):
    """锁: 别人在写事务里时,写的一方超时报 TimeoutError,读的一方不受影响"""
    st.write_ioc("ioc-a", {"snapshot": "tracked"})
    st2 = opened(db, timeout=0.3)
    try:
        with st.transaction():
            st.write_ioc("ioc-a", {"snapshot": "error"})
            check("st2 读到的是提交前的值", snapshot_of(st2), "tracked")
            with expect_error(TimeoutError, "st2 写入"):
                st2.write_ioc("ioc-a", {"snapshot": "untracked"})
        check("提交后 st2 读到新值", snapshot_of(st2), "error")
        st2.write_ioc("ioc-a", {"snapshot": "tracked"})  # free again
        check("锁释放后 st2 可以写", snapshot_of(st2), "tracked")
    finally:
        st2.close()


def test_exclusive_lock_blocks_even_connecting(db):
    """锁: 别人持有独占锁时,连 connect 都会超时"""
    hold = sqlite3.connect(db, isolation_level=None)
    try:
        hold.execute("BEGIN EXCLUSIVE")  # nothing can even read now
        with expect_error(TimeoutError, "独占锁下 connect"):
            opened(db, timeout=0.3)
        hold.execute("ROLLBACK")
    finally:
        hold.close()


def test_only_locked_by_another_process_counts_as_busy():
    """_is_database_busy: 只有"锁/忙"类的 OperationalError 才算忙"""
    busy = IocStateManager._is_database_busy
    check("database is locked", busy(sqlite3.OperationalError("database is locked")), True)
    check("table is locked", busy(sqlite3.OperationalError("database table is locked")), True)
    check("database is busy", busy(sqlite3.OperationalError("database is busy")), True)
    check("no such table", busy(sqlite3.OperationalError("no such table: ioc")), False)
    check("不是 OperationalError", busy(ValueError("database is locked")), False)


def test_threads_and_processes_writing_together_lose_nothing(st, db):
    """并发: 8 个线程 + 4 个进程同时写 issue,一条都不丢"""
    # The processes are started fresh: an instance cannot be carried across fork().
    add_ioc(st, "ioc-load")
    errors = []

    def thread_work():
        try:
            for _ in range(25):
                st.write_issues("ioc-load", [make_issue("thread")], append=True)
        except BaseException as e:
            errors.append(e)

    process_code = (
        "import sys; sys.path.insert(0, sys.argv[1])\n"
        "from core.ioc_state import IocStateManager\n"
        "from core.ioc_schema import IssueEntry\n"
        "own = IocStateManager(sys.argv[2])\n"
        "own.connect()\n"
        "for _ in range(25):\n"
        "    own.write_issues('ioc-load', [IssueEntry(level='info', reason='file_error',"
        " message='process', prompt='', time='t')], append=True)\n"
        "own.close()\n"
    )
    step("启动 4 个进程(各写 25 条)和 8 个线程(各写 25 条)")
    procs = [
        subprocess.Popen(
            [sys.executable, "-I", "-c", process_code, str(REPO_ROOT), db]
        )
        for _ in range(4)
    ]
    threads = [threading.Thread(target=thread_work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    check("各进程的退出码", [p.wait() for p in procs], [0, 0, 0, 0])
    check("线程里的错误", errors, [])
    found = [i.message for i in st.read_issues("ioc-load")]
    check("线程写入的条数(期望 8×25)", found.count("thread"), 200)
    check("进程写入的条数(期望 4×25)", found.count("process"), 100)


def test_database_that_vanishes_is_an_error_and_a_replaced_one_is_followed(st, db):
    """文件: 库被删报 FileNotFoundError 且不会重建;被换成新库时实例跟着用新库"""
    Path(db).unlink()
    with expect_error(FileNotFoundError, "库文件被删"):
        st.list_iocs()
    check_true("原位置没有被偷偷建出文件", not Path(db).exists())
    IocStateManager.initialize(db)  # a new database: the open instance moves to it
    check("换成新库之后", st.list_iocs(), [])
    add_ioc(st, "ioc-new")
    other = opened(db)
    check("另一个实例看到的", other.list_iocs(), ["ioc-new"])
    other.close()


def test_close_ends_the_instance_and_it_can_be_connected_again(st, db):
    """close: 关闭后不能再用,可以重新 connect"""
    scoped = opened(db)
    check("关闭前", scoped.list_iocs(), ["ioc-a", "ioc-b"])
    scoped.close()
    with expect_error(RuntimeError, "关闭后使用"):
        scoped.list_iocs()
    scoped.connect()
    check("重新 connect 后", scoped.list_iocs(), ["ioc-a", "ioc-b"])
    scoped.close()


# --------------------------------------------------------------------- IOC


@pytest.fixture
def shared():
    """core.ioc.state_manager, with no IOC left in it after the test."""
    yield state_manager
    for name in state_manager.list_iocs():
        state_manager.delete_ioc(name)


def test_ioc_module_holds_one_connected_state():
    """core.ioc.state_manager: import 时就连好的共享 IocStateManager,用的是临时库"""
    check_true("是 IocStateManager", isinstance(state_manager, IocStateManager))
    check("db_path", state_manager.db_path, os.path.abspath(ioc_config.DEFAULT_DB_PATH))
    check_true("库在开发目录的 .test-tmp 里", state_manager.db_path.startswith(str(REPO_ROOT / ".test-tmp")))
    check_true("不在 /opt 下", not state_manager.db_path.startswith("/opt"))
    check("没有数据时", state_manager.list_iocs(), [])


def test_importing_ioc_without_a_database_fails(tmp_path):
    """core.ioc: 库不存在时 import 直接抛 FileNotFoundError,也不会建库"""
    missing = tmp_path / "ioc-state.db"
    code = (
        "import sys; sys.path.insert(0, sys.argv[1])\n"
        "from core import ioc_config\n"
        "ioc_config.DEFAULT_DB_PATH = sys.argv[2]\n"
        "import core.ioc\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(REPO_ROOT), str(missing)],
        capture_output=True,
        text=True,
    )
    check("退出码", result.returncode, 1)
    check_true("报的是 FileNotFoundError", "FileNotFoundError" in result.stderr, result.stderr)
    check_true("没有建出库文件", not missing.exists())


def test_ioc_reads_its_state_from_the_shared_database(shared):
    """IOC: 初始化时用 core.ioc.state_manager 从库里读自己的状态"""
    add_ioc(shared, "ioc-a")
    ioc = IOC("ioc-a")
    check("name", ioc.name, "ioc-a")
    check_true("state_manager 就是 core.ioc.state_manager", ioc.state_manager is shared)
    check("state_data", ioc.state_data, shared.read_ioc("ioc-a"))
    check_true("config 是 IocConfig", isinstance(ioc.config, IocConfig))
    check("config.path", ioc.config.path, ioc.config_path)
    check("config 文件名", os.path.basename(ioc.config_path), ioc_config.CONFIG_FILE_NAME)
    check("config 在 IOC 自己的目录里", os.path.dirname(ioc.config_path), os.path.join(ioc_config.IOCS_DIR, "ioc-a"))
    check_true("config 路径不在 /opt 下", not ioc.config_path.startswith("/opt"))
    check_true("config 路径在开发目录的 .test-tmp 里", ioc.config_path.startswith(str(REPO_ROOT / ".test-tmp")))


def test_ioc_that_is_not_in_the_database_raises_ioc_not_found(shared):
    """IOC: 库里没有这个 IOC 时抛 IocNotFoundError"""
    add_ioc(shared, "ioc-a")
    with expect_error(IocNotFoundError, "库里没有 ioc-b"):
        IOC("ioc-b")


# ------------------------------------------------------- scripts/init_state_db.py

INIT_SCRIPT = REPO_ROOT / "scripts" / "init_state_db.py"


def run_init_script(*args):
    return subprocess.run(
        [sys.executable, "-I", str(INIT_SCRIPT), *args], capture_output=True, text=True
    )


def test_init_script_creates_the_database_and_creating_it_again_is_harmless(tmp_path):
    """建库脚本: 新路径建库(包括缺的目录);已有的库不改动,退出码仍是 0"""
    db = tmp_path / "new-dir" / "ioc-state.db"
    first = run_init_script(str(db))
    check("第一次的退出码", first.returncode, 0)
    check_true("库建出来了", db.is_file(), first.stderr)
    opened_db = opened(str(db))
    add_ioc(opened_db, "ioc-a")
    opened_db.close()
    second = run_init_script(str(db))
    check("第二次的退出码", second.returncode, 0)
    check_true("提示已存在", "already exists" in second.stdout, second.stdout)
    again = opened(str(db))
    check("已有的数据没有被动", again.list_iocs(), ["ioc-a"])
    again.close()


def test_init_script_reports_failures_and_bad_arguments(tmp_path):
    """建库脚本: 建不出来退出码 1 并写 stderr;参数多了退出码 2"""
    blocker = tmp_path / "a-file"
    blocker.write_text("x")
    bad = run_init_script(str(blocker / "ioc-state.db"))
    check("目录建不出来的退出码", bad.returncode, 1)
    check_true("错误写在 stderr", "failed to create" in bad.stderr, bad.stderr)
    usage = run_init_script("a", "b")
    check("参数多了的退出码", usage.returncode, 2)
    check_true("提示用法", "usage" in usage.stderr, usage.stderr)
