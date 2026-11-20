import re
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.ioc import IocConfig, IocState
from core.ioc_schema import (
    IocStateSchema,
    IssueEntry,
    IssueLevel,
    IssueReason,
    new_state,
)
from core.utils import get_now_str, get_yaml_tool

REPO_ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- IocConfig
# A change a person would make in an editor is written as a variant of the
# generated text (base), so there is nothing to undo between steps.


def test_create_template_names_config_after_directory(make_conf):
    conf = make_conf("ioc-demo")
    assert conf.file_exists() is True
    conf.load()
    assert conf.issues == [] and conf.data is not None
    assert conf.is_valid is True
    assert conf.data.basic.name == "ioc-demo"
    assert "src" not in conf.data.model_dump()
    assert [p for p in Path(conf.path).parent.iterdir() if p.suffix == ".tmp"] == []


def test_create_template_never_overwrites(make_conf):
    conf = make_conf()
    with pytest.raises(FileExistsError):
        IocConfig.create_template(conf.path, None)


def test_create_template_with_awkward_directory_name(make_conf):
    conf = make_conf('ioc "测试" #1\\x')
    conf.load()
    assert conf.data is not None and conf.data.basic.name == 'ioc "测试" #1\\x'


def test_file_exists_is_false_before_create(tmp_path):
    assert IocConfig(str(tmp_path / "ioc.yaml")).file_exists() is False


def test_typed_access(make_conf):
    conf = make_conf("t-get")
    conf.load()
    assert conf.data.basic.host == "swarm"
    assert conf.data.build.modules[0] == "autosave"
    assert "status-os" not in conf.data.build.modules
    assert conf.data.build.db_load[0].macros["ABC"] == "xxx:"
    assert conf.data.build.settings.report_info is True
    with pytest.raises(AttributeError):
        conf.data.build.no_such_field


def test_load_reads_hand_written_file_and_never_touches_it(make_conf):
    conf = make_conf("t-load")
    base = read(conf.path)
    conf.load()
    assert read(conf.path) == base
    text = base + "# my own note\n"
    text = re.sub(r"image: ''.*", "image: registry.iasf/ioc:1.0", text)
    text = re.sub(
        r"cmd_at_dbload: ''.*",
        'cmd_at_dbload: |\n      line1\n      dbLoadRecords("x.db")',
        text,
    )
    text = text.replace("ABC: 'xxx:'", "P: 'xxx:'")
    write(conf.path, text)
    conf.load()
    assert read(conf.path) == text
    assert conf.data is not None and conf.issues == []
    assert conf.data.basic.image == "registry.iasf/ioc:1.0"
    assert conf.data.build.db_load[0].macros["P"] == "xxx:"
    assert conf.data.build.raw_cmd.cmd_at_dbload == 'line1\ndbLoadRecords("x.db")\n'


def test_empty_list_is_valid_and_stays_empty(make_conf):
    conf = make_conf("t-check")
    base = read(conf.path)
    text = re.sub(r"modules:.*\n    - autosave\n    - caputlog", "modules: []", base)
    assert text != base
    write(conf.path, text)
    conf.load()
    assert conf.is_valid is True and conf.data.build.modules == []


def test_invalid_value_becomes_an_issue_and_there_is_no_config(make_conf, tmp_path):
    conf = make_conf("t-invalid")
    base = read(conf.path)
    write(conf.path, base.replace("cpus: '1'", "cpus: 1"))
    conf.load()
    assert conf.data is None and len(conf.issues) == 1
    assert conf.is_valid is False
    issue = conf.issues[0]
    assert isinstance(issue, IssueEntry) and issue.level == IssueLevel.ERROR
    assert issue.reason == IssueReason.VALIDATION_ERROR
    assert issue.message.startswith("deploy.resources.limits.cpus:")

    never = tmp_path / "never-written.yaml"
    for method, args in (
        (conf.show, ()),
        (conf.to_string, ()),
        (conf.save, (str(never),)),
    ):
        with pytest.raises(RuntimeError):
            method(*args)
    assert not never.exists()

    # the issue is accepted by IocStateSchema as is
    state = IocStateSchema(
        state="error",
        status="created",
        snapshot="untracked",
        is_exported=False,
        src_files={"db_files": [], "protocol_files": [], "other_files": []},
        issues=conf.issues,
    )
    assert state.issues[0].message == issue.message


def test_load_recovers_after_the_file_is_fixed(make_conf):
    conf = make_conf("t-invalid")
    base = read(conf.path)
    write(conf.path, base.replace("cpus: '1'", "cpus: 1"))
    conf.load()
    assert conf.data is None
    write(conf.path, base)
    conf.load()
    assert conf.data is not None and conf.issues == []


def test_invalid_nested_value_is_reported_with_its_path(make_conf):
    conf = make_conf("t-invalid")
    write(conf.path, read(conf.path).replace("report_info: true", "report_info: maybe"))
    conf.load()
    assert any(i.message.startswith("build.settings.report_info:") for i in conf.issues)


def test_missing_field_is_reported_including_nested_ones(make_conf):
    conf = make_conf("t-missing")
    base = read(conf.path)
    write(conf.path, base.replace("    report_info: true\n", ""))
    conf.load()
    assert conf.data is None
    assert [i.message for i in conf.issues] == [
        "build.settings.report_info: Field required"
    ]
    write(conf.path, base.replace("  epics_env: {}\n", ""))
    conf.load()
    assert [i.message for i in conf.issues] == ["build.epics_env: Field required"]


def test_extra_field_is_an_error_at_any_depth(make_conf):
    conf = make_conf("t-extra")
    base = read(conf.path)
    write(conf.path, base.replace("  settings:\n", "  foo: 1\n  settings:\n"))
    conf.load()
    assert conf.data is None
    assert [i.message for i in conf.issues] == [
        "build.foo: Extra inputs are not permitted"
    ]
    write(
        conf.path,
        base.replace("    caputlog_json: false", "    caputlog_json: false\n    bar: 2"),
    )
    conf.load()
    assert [i.message for i in conf.issues] == [
        "build.settings.bar: Extra inputs are not permitted"
    ]


def test_free_form_mapping_takes_any_key(make_conf):
    conf = make_conf("t-extra")
    text = read(conf.path).replace(
        "        ABC: 'xxx:'\n", "        ABC: 'xxx:'\n        Z: zzz\n"
    )
    assert "Z: zzz" in text
    write(conf.path, text)
    conf.load()
    assert conf.data is not None and conf.issues == []


def test_name_mismatch_is_a_warning_and_config_stays_usable(make_conf):
    conf = make_conf("t-name")
    base = read(conf.path)
    write(conf.path, base.replace("name: t-name", "name: other"))
    conf.load()
    assert conf.data is not None and len(conf.issues) == 1
    assert conf.is_valid is False  # usable, but the name check failed
    assert conf.issues[0].level == IssueLevel.WARNING
    assert conf.issues[0].message.startswith("basic.name:")
    assert conf.issues[0].reason == IssueReason.VALIDATION_ERROR
    write(conf.path, base)
    conf.load()
    assert conf.data is not None and conf.issues == []
    assert conf.is_valid is True


@pytest.mark.parametrize(
    "content, expected",
    [
        (b"basic: [unclosed\n", "while parsing a flow sequence"),
        (b"basic:\n  name: a\n  name: b\n", "found duplicate key"),
        (b"", "config file is empty"),
        (b"\xff\xfe\x00bad", "codec can't decode"),
    ],
)
def test_unreadable_file_becomes_a_file_error_issue(tmp_path, content, expected):
    path = tmp_path / "bad.yaml"
    path.write_bytes(content)
    bad = IocConfig(str(path))
    assert bad.file_exists() is True
    bad.load()
    assert bad.data is None and len(bad.issues) == 1
    assert bad.is_valid is False
    assert bad.issues[0].reason == IssueReason.FILE_ERROR
    assert bad.issues[0].level == IssueLevel.ERROR
    assert expected in bad.issues[0].message


def test_load_of_a_missing_file_raises(tmp_path):
    bad = IocConfig(str(tmp_path / "bad.yaml"))
    assert bad.file_exists() is False
    with pytest.raises(FileNotFoundError, match="config file not found"):
        bad.load()
    assert bad.data is None and bad.is_valid is False


def test_file_that_vanishes_after_load_leaves_no_stale_result(make_conf):
    conf = make_conf("t-vanish")
    conf.load()
    assert conf.data is not None and conf.is_valid is True
    Path(conf.path).unlink()
    with pytest.raises(FileNotFoundError):
        conf.load()
    assert conf.data is None and conf.issues == [] and conf.is_valid is False


def test_use_before_load_raises(make_conf, tmp_path):
    fresh = make_conf("t-fresh")
    assert fresh.data is None and fresh.is_valid is False
    never = tmp_path / "never-written.yaml"
    for method, args in (
        (fresh.show, ()),
        (fresh.to_string, ()),
        (fresh.save, (str(never),)),
    ):
        with pytest.raises(RuntimeError):
            method(*args)
    assert not never.exists()
    fresh.load()
    assert fresh.data is not None


def test_show_prints_plain_data_without_comments(make_conf, capsys):
    conf = make_conf("t-show")
    with open(conf.path, "a", encoding="utf-8") as f:
        f.write("# my own note\n")
    conf.load()
    conf.show()
    out = capsys.readouterr().out
    assert "#" not in out and "\n\n" not in out
    assert get_yaml_tool().load(out) == conf.data.model_dump()
    assert out == conf.to_string()


def test_save_writes_validated_config_and_leaves_source_untouched(make_conf, tmp_path):
    source = make_conf("t-save")
    with open(source.path, "a", encoding="utf-8") as f:
        f.write("# my own note\n")
    source_text = read(source.path)
    source.load()
    target_path = tmp_path / "managed" / "t-save" / "ioc.yaml"
    target_path.parent.mkdir(parents=True)
    source.save(str(target_path))
    assert read(source.path) == source_text
    target = IocConfig(str(target_path))
    target.load()
    assert target.issues == [] and target.data == source.data
    assert "# my own note" not in read(target_path)


def test_save_of_an_invalid_config_writes_nothing(make_conf, tmp_path):
    invalid = make_conf("t-save-invalid")
    write(invalid.path, read(invalid.path).replace("cpus: '1'", "cpus: 1"))
    invalid.load()
    assert invalid.data is None
    other = tmp_path / "managed" / "t-save-invalid" / "ioc.yaml"
    other.parent.mkdir(parents=True)
    with pytest.raises(RuntimeError):
        invalid.save(str(other))
    assert not other.exists()


# ---------------------------------------------------------------- IocState
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
    state = IocState(path, **kwargs)
    state.connect()
    return state


def add_ioc(state, name, data=None):
    data = new_state() if data is None else data
    state.write_ioc(name, {f: getattr(data, f) for f in IocState.ADAPTERS})
    state.write_issues(name, data.issues, append=True)


def count_issues(db):
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT COUNT(*) FROM issue").fetchone()[0]
    finally:
        con.close()


@pytest.fixture
def db(tmp_path):
    """Path of a database that has been initialized and is empty."""
    path = str(tmp_path / "t-state" / "ioc-state.db")
    Path(path).parent.mkdir()
    IocState.initialize(path)
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
    db = str(tmp_path / "ioc-state.db")
    missing = IocState(db)  # building the instance does not touch the database
    assert not Path(db).exists()
    with pytest.raises(RuntimeError):
        missing.names()  # not connected yet
    with pytest.raises(FileNotFoundError):
        missing.connect()
    assert not Path(db).exists()  # looking at it created nothing

    Path(db).touch()
    with pytest.raises(RuntimeError):
        opened(db)  # empty file: no tables
    with pytest.raises(FileExistsError):
        IocState.initialize(db)  # a file that is there is not touched

    Path(db).unlink()
    IocState.initialize(db)
    with pytest.raises(FileExistsError):
        IocState.initialize(db)  # never over an existing database
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA user_version").fetchone()[0] == IocState.SCHEMA_VERSION
    con.close()


def test_damaged_database_is_an_error_and_is_not_touched(tmp_path):
    db = tmp_path / "ioc-state.db"
    db.write_bytes(b"this is not a database" * 100)
    with pytest.raises(sqlite3.DatabaseError):
        opened(str(db))
    with pytest.raises(FileExistsError):
        IocState.initialize(str(db))


def test_unknown_schema_version_is_an_error(db):
    other = sqlite3.connect(db)
    other.execute("PRAGMA user_version = 99")
    other.close()
    with pytest.raises(RuntimeError):
        opened(db)


def test_write_read_names_delete(st, db):
    assert st.names() == ["ioc-a", "ioc-b"]
    data = st.read_ioc("ioc-a")
    assert data == new_state()
    assert (data.state, data.status, data.snapshot, data.is_exported) == (
        "normal",
        "created",
        "untracked",
        False,
    )
    assert data.issues == [] and data.src_files.db_files == []

    st.delete_ioc("ioc-b")
    assert st.names() == ["ioc-a"]


def test_names_is_empty_after_initialize(db):
    state = opened(db)
    assert state.names() == []
    state.close()


def test_columns_keep_the_json_text_of_their_values(st, db):
    con = sqlite3.connect(db)
    raw = con.execute(
        "SELECT state, is_exported, src_files FROM ioc WHERE name = 'ioc-a'"
    ).fetchone()
    assert raw == (
        '"normal"',
        "false",
        '{"db_files":[],"protocol_files":[],"other_files":[]}',
    )
    # the columns of the table are the schema's fields (but issues), so none is left out.
    columns = [r[1] for r in con.execute("PRAGMA table_info(ioc)")]
    con.close()
    assert columns == ["name", *IocState.ADAPTERS]
    assert "issues" not in IocState.ADAPTERS


def test_unknown_or_empty_name(st):
    with pytest.raises(KeyError):
        st.read_ioc("ioc-none")
    with pytest.raises(ValueError):
        add_ioc(st, "")


def test_any_name_is_just_a_value(st):
    odd = 'ioc "测试" \'1\'; DROP TABLE ioc; --'
    add_ioc(st, odd)
    assert odd in st.names() and st.read_ioc(odd) == new_state()
    st.delete_ioc(odd)
    assert odd not in st.names()


def test_whole_state_can_be_written_and_invalid_one_is_not(st, db):
    custom = new_state()
    custom.status = "generated"
    custom.is_exported = "unknown"
    custom.issues = [make_issue("kept")]
    add_ioc(st, "ioc-c", custom)
    assert st.read_ioc("ioc-c") == custom

    custom.status = 5
    with pytest.raises(ValidationError):
        add_ioc(st, "ioc-d", custom)
    with pytest.raises(KeyError):
        st.read_ioc("ioc-d")

    st.delete_ioc("ioc-c")
    with pytest.raises(KeyError):
        st.read_ioc("ioc-c")
    with pytest.raises(KeyError):
        st.delete_ioc("ioc-c")
    assert count_issues(db) == 0


@pytest.mark.parametrize(
    "column, text", [("status", "5"), ("status", "not json"), ("src_files", "{}")]
)
def test_content_that_does_not_fit_the_schema_is_an_error(st, db, column, text):
    damage = sqlite3.connect(db)
    damage.execute(f"UPDATE ioc SET {column} = ? WHERE name = 'ioc-a'", (text,))
    damage.commit()
    damage.close()
    with pytest.raises(ValidationError):
        st.read_ioc("ioc-a")


def test_write_ioc_changes_only_the_given_columns(st):
    st.write_ioc("ioc-a", {"state": "warning"})
    st.write_ioc(
        "ioc-a",
        {
            "status": "generated",
            "snapshot": "tracked",
            "is_exported": True,
            "src_files": {
                "db_files": ["a.db"],
                "protocol_files": ["a.proto"],
                "other_files": [],
            },
        },
    )
    data = st.read_ioc("ioc-a")
    assert (data.state, data.status, data.snapshot, data.is_exported) == (
        "warning",
        "generated",
        "tracked",
        True,
    )
    assert data.src_files.db_files == ["a.db"]
    assert data.src_files.protocol_files == ["a.proto"]
    assert data.src_files.other_files == []
    st.write_ioc("ioc-a", {"is_exported": "unknown"})
    assert st.read_ioc("ioc-a").is_exported == "unknown"
    assert st.read_ioc("ioc-b") == new_state()  # another IOC is untouched


def test_write_ioc_rejects_invalid_values_as_a_whole(st):
    st.write_ioc("ioc-a", {"state": "warning", "status": "generated"})
    with pytest.raises(ValidationError):
        st.write_ioc("ioc-a", {"status": 5})
    with pytest.raises(ValidationError):
        st.write_ioc("ioc-a", {"src_files": {"db_files": "a.db"}})
    with pytest.raises(ValidationError):
        st.write_ioc("ioc-a", {"state": "error", "status": 5})  # one bad stops all
    data = st.read_ioc("ioc-a")
    assert data.status == "generated" and data.state == "warning"
    with pytest.raises(ValueError):
        st.write_ioc("ioc-a", {})  # nothing to write
    with pytest.raises(ValueError):
        st.write_ioc("ioc-a", {"issues": []})  # not a column of ioc


def test_write_ioc_of_a_new_ioc_needs_every_column(st):
    with pytest.raises(sqlite3.IntegrityError):
        st.write_ioc("ioc-none", {"status": "x"})
    with pytest.raises(KeyError):
        st.read_ioc("ioc-none")
    assert "ioc-none" not in st.names()


def test_issues_are_appended_in_order_and_not_deduplicated(st):
    st.write_ioc("ioc-a", {"state": "warning"})
    issue = make_issue("first")
    st.write_issues("ioc-a", [issue], append=True)
    st.write_issues(
        "ioc-a", [issue, make_issue("second", IssueLevel.ERROR)], append=True
    )
    data = st.read_ioc("ioc-a")
    assert [i.message for i in data.issues] == ["first", "first", "second"]
    assert data.issues[2].level == IssueLevel.ERROR
    assert st.read_issues("ioc-b") == []


def test_replacing_issues_leaves_the_state_alone(st):
    st.write_ioc("ioc-a", {"state": "warning"})
    st.write_issues("ioc-a", [make_issue("old")], append=True)
    st.write_issues("ioc-a", [make_issue("only")])  # replaces
    assert [i.message for i in st.read_issues("ioc-a")] == ["only"]
    st.write_issues("ioc-a", [])
    data = st.read_ioc("ioc-a")
    assert data.issues == [] and data.state == "warning"


def test_invalid_issue_stops_a_replace_before_the_old_log_is_touched(st):
    issue = make_issue("x")
    st.write_issues("ioc-a", [make_issue("kept")])
    with pytest.raises(ValidationError):
        st.write_issues("ioc-a", [{"level": "nope"}])
    with pytest.raises(ValidationError):
        st.write_issues("ioc-a", [issue, {"level": "nope"}])
    assert [i.message for i in st.read_issues("ioc-a")] == ["kept"]


def test_issues_of_an_ioc_that_is_not_there(st):
    with pytest.raises(sqlite3.IntegrityError):
        st.write_issues("ioc-none", [make_issue()])
    assert st.read_issues("ioc-none") == []
    st.write_issues("ioc-none", [])  # nothing to write for an IOC that is not there
    assert "ioc-none" not in st.names()


def test_deleting_an_ioc_deletes_its_issues(st, db):
    st.write_issues("ioc-a", [make_issue()], append=True)
    assert count_issues(db) == 1
    st.delete_ioc("ioc-a")  # the issues go with it
    assert count_issues(db) == 0


def test_transaction_commits_several_changes_as_one(st):
    with st.transaction():
        st.write_ioc("ioc-a", {"status": "exported"})
        st.write_issues("ioc-a", [make_issue("in tx")], append=True)
        add_ioc(st, "ioc-e")
    assert st.read_ioc("ioc-a").status == "exported"
    assert len(st.read_issues("ioc-a")) == 1
    assert "ioc-e" in st.names()


def test_transaction_is_undone_together_when_the_block_raises(st):
    st.write_ioc("ioc-a", {"status": "exported"})
    add_ioc(st, "ioc-e")
    with pytest.raises(RuntimeError, match="boom"):
        with st.transaction():
            st.write_ioc("ioc-a", {"status": "lost"})
            st.delete_ioc("ioc-e")
            raise RuntimeError("boom")
    assert st.read_ioc("ioc-a").status == "exported" and "ioc-e" in st.names()


def test_failing_call_inside_a_transaction_undoes_the_calls_before_it(st):
    st.write_ioc("ioc-a", {"status": "exported"})
    with pytest.raises(KeyError):
        with st.transaction():
            st.write_ioc("ioc-a", {"status": "lost"})
            st.delete_ioc("ioc-none")
    assert st.read_ioc("ioc-a").status == "exported"


def test_transaction_cannot_be_nested_and_leaves_nothing_open(st):
    with pytest.raises(RuntimeError):
        with st.transaction():
            with st.transaction():
                pass
    st.write_ioc("ioc-a", {"status": "exported"})
    assert st.read_ioc("ioc-a").status == "exported"


def test_busy_database_times_out_for_writers_but_not_readers(st, db):
    st.write_ioc("ioc-a", {"status": "exported"})
    st2 = opened(db, timeout=0.3)
    try:
        with st.transaction():
            st.write_ioc("ioc-a", {"status": "held"})
            assert st2.read_ioc("ioc-a").status == "exported"  # not yet committed
            with pytest.raises(TimeoutError):
                st2.write_ioc("ioc-a", {"status": "blocked"})
        assert st2.read_ioc("ioc-a").status == "held"
        st2.write_ioc("ioc-a", {"status": "exported"})  # free again
    finally:
        st2.close()


def test_exclusive_lock_blocks_even_connecting(db):
    hold = sqlite3.connect(db, isolation_level=None)
    try:
        hold.execute("BEGIN EXCLUSIVE")  # nothing can even read now
        with pytest.raises(TimeoutError):
            opened(db, timeout=0.3)
        hold.execute("ROLLBACK")
    finally:
        hold.close()


def test_only_locked_by_another_process_counts_as_busy():
    busy = IocState._is_database_busy
    assert busy(sqlite3.OperationalError("database is locked"))
    assert busy(sqlite3.OperationalError("database table is locked"))
    assert not busy(sqlite3.OperationalError("no such table: ioc"))
    assert not busy(ValueError("database is locked"))


def test_threads_and_processes_writing_together_lose_nothing(st, db):
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
        "from core.ioc import IocState\n"
        "from core.ioc_schema import IssueEntry\n"
        "own = IocState(sys.argv[2])\n"
        "own.connect()\n"
        "for _ in range(25):\n"
        "    own.write_issues('ioc-load', [IssueEntry(level='info', reason='file_error',"
        " message='process', prompt='', time='t')], append=True)\n"
        "own.close()\n"
    )
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
    assert [p.wait() for p in procs] == [0, 0, 0, 0]
    assert errors == []
    messages = [i.message for i in st.read_issues("ioc-load")]
    assert messages.count("thread") == 200 and messages.count("process") == 100


def test_database_that_vanishes_is_an_error_and_a_replaced_one_is_followed(st, db):
    Path(db).unlink()
    with pytest.raises(FileNotFoundError):
        st.names()
    assert not Path(db).exists()  # nothing was created in its place
    IocState.initialize(db)  # a new database: the open instance moves to it
    assert st.names() == []
    add_ioc(st, "ioc-new")
    other = opened(db)
    assert other.names() == ["ioc-new"]
    other.close()


def test_close_ends_the_instance_and_it_can_be_connected_again(st, db):
    scoped = opened(db)
    assert scoped.names() == ["ioc-a", "ioc-b"]
    scoped.close()
    with pytest.raises(RuntimeError):
        scoped.names()
    scoped.connect()
    assert scoped.names() == ["ioc-a", "ioc-b"]
    scoped.close()
