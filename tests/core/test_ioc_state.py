import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from core import settings
from core.ioc_schema import IssueEntry, IssueLevel, new_state
from core.ioc_state import IocStateManager, get_state_manager
from tests.helpers import REPO_ROOT, add_ioc, make_issue, opened
from tests.logutil import check, check_true, expect_error, note, step


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
    """IocStateManager(): 不给路径用 settings.DEFAULT_DB_PATH,相对路径会转成绝对路径,构造时不碰磁盘"""
    check("默认路径", IocStateManager().db_path, os.path.abspath(settings.DEFAULT_DB_PATH))
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


def test_exists_looks_only_at_the_record(st):
    """exists: 有记录就是 True,没有就是 False;删除之后又是 False"""
    check("ioc-a", st.exists("ioc-a"), True)
    check("没有的", st.exists("nope"), False)
    st.delete_ioc("ioc-a")
    check("删除之后", st.exists("ioc-a"), False)


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


def test_get_state_manager_returns_one_connected_state(shared):
    """get_state_manager: 同一进程里每次拿到同一个已连接的 IocStateManager,用的是临时库"""
    check_true("是 IocStateManager", isinstance(shared, IocStateManager))
    check_true("每次都是同一个", get_state_manager() is shared)
    check("db_path", shared.db_path, os.path.abspath(settings.DEFAULT_DB_PATH))
    check_true("库在开发目录的 .test-tmp 里", shared.db_path.startswith(str(REPO_ROOT / ".test-tmp")))
    check_true("不在 /opt 下", not shared.db_path.startswith("/opt"))
    check("没有数据时", shared.list_iocs(), [])
