import json
import os
import sqlite3
import sys
import threading
from contextlib import contextmanager
from io import StringIO

from pydantic import TypeAdapter, ValidationError

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ioc_schema import (
    IocConfigSchema,
    IocStateSchema,
    IssueEntry,
    IssueLevel,
    IssueReason,
    new_config,
    new_state,
)
from core.utils import atomic_write, get_dir_name, get_now_str, get_yaml_tool


class IocConfig:

    def __init__(self, path):
        self._yaml = get_yaml_tool()
        self.path = path
        self.data = None
        self.issues = []
        self.is_valid = False

    def file_exists(self):
        return os.path.isfile(self.path)

    @staticmethod
    def create_template(path, template_type):
        if os.path.isfile(path):
            raise FileExistsError(path)
        buf = StringIO()
        get_yaml_tool().dump(new_config(get_dir_name(path)).model_dump(), buf)
        atomic_write(path, buf.getvalue())

    def load(self):
        now = get_now_str()
        self.data = None
        self.issues = []
        self.is_valid = False
        if not self.file_exists():
            raise FileNotFoundError("config file not found")
        error = None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = self._yaml.load(f)
        except Exception as e:
            error = f"{self.path}: {e}"
        else:
            if data is None:
                error = f"{self.path}: config file is empty"
        if error is not None:
            self.issues.append(
                IssueEntry(
                    level=IssueLevel.ERROR,
                    reason=IssueReason.FILE_ERROR,
                    message=error,
                    prompt="",
                    time=now,
                )
            )
            return
        self._validate(data)

    def _validate(self, data):
        now = get_now_str()
        try:
            self.data = IocConfigSchema.model_validate(data)
        except ValidationError as e:
            for err in e.errors():
                path = ".".join(str(p) for p in err["loc"]) or "<root>"
                self.issues.append(
                    IssueEntry(
                        level=IssueLevel.ERROR,
                        reason=IssueReason.VALIDATION_ERROR,
                        message=f"{path}: {err['msg']}",
                        prompt="",
                        time=now,
                    )
                )
        if self.data is not None:
            name, dir_name = self.data.basic.name, get_dir_name(self.path)
            if name != dir_name:
                self.issues.append(
                    IssueEntry(
                        level=IssueLevel.WARNING,
                        reason=IssueReason.VALIDATION_ERROR,
                        message=f"basic.name: {name!r} does not match directory name {dir_name!r}",
                        prompt="",
                        time=now,
                    )
                )
        # passed only if nothing is wrong: a config can be usable (data is not None)
        # and still not pass, e.g. when basic.name does not match the directory.
        self.is_valid = self.data is not None and not any(
            i.level in (IssueLevel.WARNING, IssueLevel.ERROR) for i in self.issues
        )

    def to_string(self):
        if self.data is None:
            raise RuntimeError("config is not loaded")
        buf = StringIO()
        self._yaml.dump(self.data.model_dump(), buf)
        return buf.getvalue()

    def show(self):
        sys.stdout.write(self.to_string())

    def save(self, path):
        atomic_write(path, self.to_string())


class IocState:
    """The state of the managed IOCs, kept in one SQLite database. The database
    is the only record of that state, so it is never created or emptied behind
    the caller's back: connect() on a missing database raises FileNotFoundError,
    and IocState.initialize() creates it.

    IocState() only records where the database is. connect() opens the connection,
    once, and it is kept until close(). One instance can be shared by threads: every operation takes the instance lock for its whole
    transaction. Other processes are kept out by SQLite itself; an operation that
    waits longer than `timeout` seconds for them raises TimeoutError.

    An instance must not be carried across fork(): SQLite copies its lock state
    into the child, which then finds the database locked for good. Start a new
    process and build the instance there."""

    # change this to move the database. A path given to IocState() wins over it.
    DEFAULT_DB_PATH = "/opt/IocDockHome/IocDock/ioc-state.db"

    SCHEMA_VERSION = 1
    # the tables of the database. initialize() runs it, and it can be run by hand:
    #   python3 -c "from core.ioc import IocState; print(IocState.SCHEMA_SQL)" | sqlite3 <db>
    SCHEMA_SQL = f"""\
BEGIN;
CREATE TABLE ioc (
    name        TEXT PRIMARY KEY,
    state       TEXT NOT NULL,
    status      TEXT NOT NULL,
    snapshot    TEXT NOT NULL,
    is_exported TEXT NOT NULL,
    src_files   TEXT NOT NULL
);
CREATE TABLE issue (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ioc_name TEXT NOT NULL REFERENCES ioc(name) ON DELETE CASCADE,
    level    TEXT NOT NULL,
    reason   TEXT NOT NULL,
    message  TEXT NOT NULL,
    prompt   TEXT NOT NULL,
    time     TEXT NOT NULL
);
CREATE INDEX issue_by_ioc ON issue(ioc_name);
PRAGMA user_version = {SCHEMA_VERSION};
COMMIT;
"""

    def __init__(self, db_path=None, timeout=10):
        self.db_path = os.path.abspath(db_path or self.DEFAULT_DB_PATH)
        self.timeout = timeout
        self._lock = threading.RLock()
        self._in_tx = False
        self._conn = None
        self._ident = None

    def connect(self):
        """Open the connection to the database. Does nothing when already connected."""
        with self._lock:
            if self._conn is None:
                self._conn, self._ident = self._open()

    @classmethod
    def initialize(cls, db_path=None):
        path = os.path.abspath(db_path or cls.DEFAULT_DB_PATH)
        if os.path.exists(path):
            raise FileExistsError(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, isolation_level=None)
        try:
            conn.executescript(cls.SCHEMA_SQL)
        except BaseException:
            conn.close()
            os.remove(path)
            raise
        conn.close()

    def _open(self):
        path = self.db_path
        st = os.stat(path)  # a missing database raises FileNotFoundError
        conn = sqlite3.connect(
            path, timeout=self.timeout, isolation_level=None, check_same_thread=False
        )
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA synchronous = FULL")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version != self.SCHEMA_VERSION:
                raise RuntimeError(
                    f"state database {path} is version {version}, "
                    f"this code reads version {self.SCHEMA_VERSION}"
                )
            result = conn.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                raise sqlite3.DatabaseError(f"integrity check failed: {result}")
        except sqlite3.DatabaseError as e:
            conn.close()
            busy = self._busy(e)
            if busy is not e:
                raise busy from e
            raise sqlite3.DatabaseError(f"{path}: {e}") from e
        except BaseException:
            conn.close()
            raise
        return conn, (st.st_dev, st.st_ino)

    def _ensure_open(self):
        """Called before every operation. A database that was deleted is an error,
        not a reason to start a new empty one; one that was replaced is reopened."""
        if self._conn is None:
            raise RuntimeError("IocState is not connected")
        st = os.stat(self.db_path)  # a database that vanished raises FileNotFoundError
        if (st.st_dev, st.st_ino) != self._ident:
            conn, ident = self._open()
            self._conn.close()
            self._conn, self._ident = conn, ident

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def _busy(self, error):
        """TimeoutError for a database another process kept locked, else the error itself."""
        if isinstance(error, sqlite3.OperationalError) and (
            "locked" in str(error) or "busy" in str(error)
        ):
            return TimeoutError(
                f"state database is busy for more than {self.timeout}s: {self.db_path}"
            )
        return error

    @contextmanager
    def _txn(self, write):
        """One transaction on the connection: committed when the block ends, rolled
        back when it raises. Inside transaction() it joins that transaction."""
        with self._lock:
            if self._in_tx:
                yield self._conn
                return
            self._ensure_open()
            conn = self._conn
            try:
                conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            except sqlite3.OperationalError as e:
                raise self._busy(e) from e
            try:
                yield conn
                conn.execute("COMMIT")
            except BaseException as e:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                busy = self._busy(e)
                if busy is not e:
                    raise busy from e
                raise

    @contextmanager
    def transaction(self):
        """Make several changes as one: `with state.transaction(): ...`. Calls on
        this instance inside the block share the transaction, and all of them are
        undone if the block raises. It cannot be nested."""
        with self._lock:
            if self._in_tx:
                raise RuntimeError("a transaction cannot be nested in another one")
            with self._txn(True):
                self._in_tx = True
                try:
                    yield self
                finally:
                    self._in_tx = False

    @staticmethod
    def _require(conn, name):
        if conn.execute("SELECT 1 FROM ioc WHERE name = ?", (name,)).fetchone() is None:
            raise KeyError(name)

    @staticmethod
    def _field(field, value):
        """Validate one value against the schema's type for that field."""
        return TypeAdapter(
            IocStateSchema.model_fields[field].annotation
        ).validate_python(value)

    @staticmethod
    def _exported_text(value):
        return {True: "true", False: "false"}.get(value, value)

    @staticmethod
    def _exported_value(text):
        return {"true": True, "false": False}.get(text, text)

    @staticmethod
    def _entries(issues):
        return [IssueEntry.model_validate(issue) for issue in issues]

    @staticmethod
    def _insert_issues(conn, name, entries):
        conn.executemany(
            "INSERT INTO issue (ioc_name, level, reason, message, prompt, time)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [
                (name, d["level"], d["reason"], d["message"], d["prompt"], d["time"])
                for d in (e.model_dump(mode="json") for e in entries)
            ],
        )

    def create(self, name, data=None):
        """Add an IOC, with the initial state unless data is given. An IOC that is
        already there raises FileExistsError: it is never overwritten."""
        if not isinstance(name, str) or not name:
            raise ValueError("the name of an IOC is a non-empty string")
        data = new_state() if data is None else data
        data = IocStateSchema.model_validate(data.model_dump(warnings=False))
        with self._txn(True) as conn:
            try:
                conn.execute(
                    "INSERT INTO ioc (name, state, status, snapshot, is_exported, src_files)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        name,
                        data.state,
                        data.status,
                        data.snapshot,
                        self._exported_text(data.is_exported),
                        data.src_files.model_dump_json(),
                    ),
                )
            except sqlite3.IntegrityError:
                raise FileExistsError(name) from None
            self._insert_issues(conn, name, data.issues)

    def get(self, name):
        """Return the state of an IOC. An IOC that is not there raises KeyError;
        content that does not fit the schema raises ValidationError. The caller
        decides what then."""
        with self._txn(False) as conn:
            row = conn.execute(
                "SELECT state, status, snapshot, is_exported, src_files FROM ioc WHERE name = ?",
                (name,),
            ).fetchone()
            if row is None:
                raise KeyError(name)
            issues = conn.execute(
                "SELECT level, reason, message, prompt, time FROM issue"
                " WHERE ioc_name = ? ORDER BY id",
                (name,),
            ).fetchall()
        return IocStateSchema.model_validate(
            {
                "state": row[0],
                "status": row[1],
                "snapshot": row[2],
                "is_exported": self._exported_value(row[3]),
                "src_files": json.loads(row[4]),
                "issues": [
                    dict(zip(("level", "reason", "message", "prompt", "time"), issue))
                    for issue in issues
                ],
            }
        )

    def names(self):
        """The names of all IOCs, sorted."""
        with self._txn(False) as conn:
            return [
                row[0] for row in conn.execute("SELECT name FROM ioc ORDER BY name")
            ]

    def delete(self, name):
        """Remove an IOC with its issues."""
        with self._txn(True) as conn:
            if conn.execute("DELETE FROM ioc WHERE name = ?", (name,)).rowcount == 0:
                raise KeyError(name)

    def _update(self, name, column, value):
        with self._txn(True) as conn:
            if (
                conn.execute(
                    f"UPDATE ioc SET {column} = ? WHERE name = ?", (value, name)
                ).rowcount
                == 0
            ):
                raise KeyError(name)

    def set_state(self, name, state):
        self._update(name, "state", self._field("state", state))

    def set_status(self, name, status):
        self._update(name, "status", self._field("status", status))

    def set_snapshot(self, name, snapshot):
        self._update(name, "snapshot", self._field("snapshot", snapshot))

    def set_exported(self, name, is_exported):
        value = self._field("is_exported", is_exported)
        self._update(name, "is_exported", self._exported_text(value))

    def set_src_files(self, name, src_files):
        """src_files is a dict with db_files, protocol_files and other_files."""
        value = self._field("src_files", src_files)
        self._update(name, "src_files", value.model_dump_json())

    def add_issues(self, name, issues):
        """Append issues to the log. They are never de-duplicated."""
        entries = self._entries(issues)
        with self._txn(True) as conn:
            self._require(conn, name)
            self._insert_issues(conn, name, entries)

    def replace_issues(self, name, issues):
        """Empty the log and write issues in it, as one change."""
        entries = self._entries(issues)
        with self._txn(True) as conn:
            self._require(conn, name)
            conn.execute("DELETE FROM issue WHERE ioc_name = ?", (name,))
            self._insert_issues(conn, name, entries)


class IOC:
    pass


if __name__ == "__main__":
    import contextlib
    import io
    import re
    import shutil

    from core.ioc_schema import IocStateSchema

    # every test case below creates its own project under test_root. A change a
    # person would make in an editor is written as a variant of the generated
    # text (base), so there is nothing to undo between steps.
    test_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ioc_test")
    shutil.rmtree(test_root, ignore_errors=True)
    os.makedirs(test_root)

    # 1. create: name follows the directory name; an existing file is never overwritten.
    path = os.path.join(test_root, "ioc-demo", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    conf = IocConfig(path)
    assert conf.file_exists() is False
    IocConfig.create_template(path, None)
    assert conf.file_exists() is True
    conf.load()
    assert conf.issues == [] and conf.data is not None
    assert conf.is_valid is True
    assert conf.data.basic.name == "ioc-demo"
    assert "src" not in conf.data.model_dump()
    assert [
        f for f in os.listdir(os.path.dirname(conf.path)) if f.endswith(".tmp")
    ] == []
    try:
        IocConfig.create_template(path, None)
    except FileExistsError:
        pass
    else:
        raise AssertionError("create_template() must not overwrite an existing file")
    # an awkward directory name still round-trips.
    path = os.path.join(test_root, 'ioc "测试" #1\\x', "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    odd = IocConfig(path)
    odd.load()
    assert odd.data is not None and odd.data.basic.name == 'ioc "测试" #1\\x'
    print("1. create ok")

    # 2. typed access: values are read from conf.data, lists and mappings as such.
    path = os.path.join(test_root, "t-get", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    conf.load()
    assert conf.data.basic.host == "swarm"
    assert conf.data.build.modules[0] == "autosave"
    assert (
        "autosave" in conf.data.build.modules
        and "status-os" not in conf.data.build.modules
    )
    assert conf.data.build.db_load[0].macros["ABC"] == "xxx:"
    assert conf.data.build.settings.report_info is True
    try:
        conf.data.build.no_such_field
    except AttributeError:
        pass
    else:
        raise AssertionError("a wrong field name must fail loudly")
    print("2. typed access ok")

    # 3. load: never touches the file; hand-written content is read as written.
    path = os.path.join(test_root, "t-load", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    with open(conf.path, encoding="utf-8") as f:
        base = f.read()
    conf.load()
    with open(conf.path, encoding="utf-8") as f:
        assert f.read() == base
    text = base + "# my own note\n"
    text = re.sub(r"image: ''.*", "image: registry.iasf/ioc:1.0", text)
    text = re.sub(
        r"cmd_at_dbload: ''.*",
        'cmd_at_dbload: |\n      line1\n      dbLoadRecords("x.db")',
        text,
    )
    text = text.replace("ABC: 'xxx:'", "P: 'xxx:'")
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(text)
    conf.load()
    with open(conf.path, encoding="utf-8") as f:
        assert f.read() == text and "# my own note" in text
    assert conf.data is not None and conf.issues == []
    assert conf.data.basic.image == "registry.iasf/ioc:1.0"
    assert conf.data.build.db_load[0].macros["P"] == "xxx:"
    assert conf.data.build.raw_cmd.cmd_at_dbload == 'line1\ndbLoadRecords("x.db")\n'
    print("3. load hand-written file ok")

    # 4. an empty list is valid and stays an empty list.
    path = os.path.join(test_root, "t-check", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    with open(conf.path, encoding="utf-8") as f:
        base = f.read()
    text = re.sub(r"modules:.*\n    - autosave\n    - caputlog", "modules: []", base)
    assert text != base
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(text)
    conf.load()
    assert conf.is_valid is True and conf.data.build.modules == []
    print("4. empty list ok")

    # 5. invalid value: becomes an issue that IocStateSchema accepts; there is no config to read.
    path = os.path.join(test_root, "t-invalid", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    with open(conf.path, encoding="utf-8") as f:
        base = f.read()
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(base.replace("cpus: '1'", "cpus: 1"))
    conf.load()
    assert conf.data is None and len(conf.issues) == 1
    assert conf.is_valid is False
    issue = conf.issues[0]
    assert isinstance(issue, IssueEntry) and issue.level == IssueLevel.ERROR
    assert issue.reason == IssueReason.VALIDATION_ERROR
    assert issue.message.startswith("deploy.resources.limits.cpus:")
    assert conf.data is None
    for method, args in (
        (conf.show, ()),
        (conf.to_string, ()),
        (conf.save, (os.path.join(test_root, "never-written.yaml"),)),
    ):
        try:
            method(*args)
        except RuntimeError:
            pass
        else:
            raise AssertionError("an invalid config must not be readable")
    state = IocStateSchema(
        state="error",
        status="created",
        snapshot="untracked",
        is_exported=False,
        src_files={"db_files": [], "protocol_files": [], "other_files": []},
        issues=conf.issues,
    )
    assert state.issues[0].message == issue.message
    print("   issue:", issue.model_dump(mode="json"))
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(base)
    conf.load()
    assert conf.data is not None and conf.issues == []
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(base.replace("report_info: true", "report_info: maybe"))
    conf.load()
    assert any(i.message.startswith("build.settings.report_info:") for i in conf.issues)
    print("5. invalid value ok")

    # 6. missing field: reported, including nested ones.
    path = os.path.join(test_root, "t-missing", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    with open(conf.path, encoding="utf-8") as f:
        base = f.read()
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(base.replace("    report_info: true\n", ""))
    conf.load()
    assert conf.data is None
    assert [i.message for i in conf.issues] == [
        "build.settings.report_info: Field required"
    ]
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(base.replace("  epics_env: {}\n", ""))
    conf.load()
    assert [i.message for i in conf.issues] == ["build.epics_env: Field required"]
    print("6. missing field ok")

    # 7. extra field: an error at any depth; free-form mappings such as macros take any key.
    path = os.path.join(test_root, "t-extra", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    with open(conf.path, encoding="utf-8") as f:
        base = f.read()
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(base.replace("  settings:\n", "  foo: 1\n  settings:\n"))
    conf.load()
    assert conf.data is None
    assert [i.message for i in conf.issues] == [
        "build.foo: Extra inputs are not permitted"
    ]
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(
            base.replace(
                "    caputlog_json: false", "    caputlog_json: false\n    bar: 2"
            )
        )
    conf.load()
    assert [i.message for i in conf.issues] == [
        "build.settings.bar: Extra inputs are not permitted"
    ]
    text = base.replace(
        "        ABC: 'xxx:'\n", "        ABC: 'xxx:'\n        Z: zzz\n"
    )
    assert "Z: zzz" in text
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(text)
    conf.load()
    assert conf.data is not None and conf.issues == []
    print("7. extra field ok")

    # 8. name mismatch: a warning only; the config stays valid.
    path = os.path.join(test_root, "t-name", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    with open(conf.path, encoding="utf-8") as f:
        base = f.read()
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(base.replace("name: t-name", "name: other"))
    conf.load()
    assert conf.data is not None and len(conf.issues) == 1
    assert conf.is_valid is False  # usable, but the name check failed
    assert conf.issues[0].level == IssueLevel.WARNING and conf.issues[
        0
    ].message.startswith("basic.name:")
    assert conf.issues[0].reason == IssueReason.VALIDATION_ERROR
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(base)
    conf.load()
    assert conf.data is not None and conf.issues == []
    assert conf.is_valid is True
    print("8. name mismatch warning ok")

    # 9. a file that cannot be read becomes a file_error issue, and there is no config.
    bad_path = os.path.join(test_root, "bad.yaml")
    for content, expected in (
        ("basic: [unclosed\n", "while parsing a flow sequence"),
        ("basic:\n  name: a\n  name: b\n", "found duplicate key"),
        ("", "config file is empty"),
        (b"\xff\xfe\x00bad", "codec can't decode"),
    ):
        if isinstance(content, bytes):
            with open(bad_path, "wb") as f:
                f.write(content)
        else:
            with open(bad_path, "w", encoding="utf-8") as f:
                f.write(content)
        bad = IocConfig(bad_path)
        assert bad.file_exists() is True
        bad.load()
        assert bad.data is None and len(bad.issues) == 1
        assert bad.is_valid is False
        assert bad.issues[0].reason == IssueReason.FILE_ERROR
        assert bad.issues[0].level == IssueLevel.ERROR
        assert expected in bad.issues[0].message, bad.issues[0].message
    # a missing file is not an issue: load() refuses to run.
    os.remove(bad_path)
    bad = IocConfig(bad_path)
    assert bad.file_exists() is False
    try:
        bad.load()
    except FileNotFoundError as e:
        assert "config file not found" in str(e)
    else:
        raise AssertionError("load() must raise when the file does not exist")
    assert bad.data is None and bad.is_valid is False
    # a file that disappears after a successful load leaves no stale result behind.
    path = os.path.join(test_root, "t-vanish", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    vanish = IocConfig(path)
    vanish.load()
    assert vanish.data is not None and vanish.is_valid is True
    os.remove(path)
    try:
        vanish.load()
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("load() must raise when the file does not exist")
    assert vanish.data is None and vanish.issues == [] and vanish.is_valid is False
    print("9. unreadable file becomes an issue, missing file raises ok")

    # 10. show, to_string and save before load() raise.
    path = os.path.join(test_root, "t-fresh", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    fresh = IocConfig(conf.path)
    assert fresh.data is None and fresh.is_valid is False
    for method, args in (
        (fresh.show, ()),
        (fresh.to_string, ()),
        (fresh.save, (os.path.join(test_root, "never-written.yaml"),)),
    ):
        try:
            method(*args)
        except RuntimeError:
            pass
        else:
            raise AssertionError("must raise before load()")
    fresh.load()
    assert fresh.data is not None
    print("10. use before load() raises ok")

    # 11. show: prints the validated config as plain data: no comments, no blank lines.
    path = os.path.join(test_root, "t-show", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    with open(conf.path, "a", encoding="utf-8") as f:
        f.write("# my own note\n")
    conf.load()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        conf.show()
    out = buf.getvalue()
    assert "#" not in out and "\n\n" not in out
    assert get_yaml_tool().load(out) == conf.data.model_dump()
    assert out == conf.to_string()
    print("11. show ok")

    # 12. save: writes the validated config to another path; the source file is untouched.
    path = os.path.join(test_root, "t-save", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    with open(path, "a", encoding="utf-8") as f:
        f.write("# my own note\n")
    with open(path, encoding="utf-8") as f:
        source_text = f.read()
    source = IocConfig(path)
    source.load()
    target_path = os.path.join(test_root, "managed", "t-save", "ioc.yaml")
    os.makedirs(os.path.dirname(target_path))
    source.save(target_path)
    with open(path, encoding="utf-8") as f:
        assert f.read() == source_text
    target = IocConfig(target_path)
    target.load()
    assert target.issues == [] and target.data == source.data
    with open(target_path, encoding="utf-8") as f:
        assert "# my own note" not in f.read()
    # an invalid config cannot be saved, and nothing is written.
    with open(path, "w", encoding="utf-8") as f:
        f.write(source_text.replace("cpus: '1'", "cpus: 1"))
    invalid = IocConfig(path)
    invalid.load()
    assert invalid.data is None
    other_path = os.path.join(test_root, "managed", "t-save-invalid", "ioc.yaml")
    os.makedirs(os.path.dirname(other_path))
    try:
        invalid.save(other_path)
    except RuntimeError:
        pass
    else:
        raise AssertionError("an invalid config must not be saved")
    assert not os.path.exists(other_path)
    print("12. save ok")

    # 13. the database: created on purpose, never by accident.
    import sqlite3
    import threading

    os.makedirs(os.path.join(test_root, "t-state"))
    db = os.path.join(test_root, "t-state", "ioc-state.db")

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

    def raises(exc, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except exc:
            return True
        raise AssertionError(f"{exc.__name__} not raised by {func.__name__}{args}")

    missing = IocState(db)  # building the instance does not touch the database
    assert not os.path.exists(db)
    raises(RuntimeError, missing.names)  # not connected yet
    raises(FileNotFoundError, missing.connect)  # missing file
    assert not os.path.exists(db)  # looking at it created nothing
    open(db, "w").close()
    raises(RuntimeError, opened, db)  # empty file: no tables
    raises(
        FileExistsError, IocState.initialize, db
    )  # a file that is there is not touched
    os.remove(db)
    IocState.initialize(db)
    raises(FileExistsError, IocState.initialize, db)  # never over an existing database
    with open(db, "wb") as f:
        f.write(b"this is not a database" * 100)
    raises(sqlite3.DatabaseError, opened, db)
    raises(FileExistsError, IocState.initialize, db)  # a damaged file is not touched
    os.remove(db)
    IocState.initialize(db)
    other = sqlite3.connect(db)
    other.execute("PRAGMA user_version = 99")
    other.close()
    raises(RuntimeError, opened, db)  # a version this code does not read
    os.remove(db)
    IocState.initialize(db)
    assert sqlite3.connect(db).execute("PRAGMA user_version").fetchone()[0] == 1
    print("13. database is created only by initialize() ok")

    # 14. create, get, names, delete.
    st = opened(db)
    assert st.names() == []  # initialize() leaves the tables empty
    st.create("ioc-b")
    st.create("ioc-a")
    assert st.names() == ["ioc-a", "ioc-b"]
    data = st.get("ioc-a")
    assert data == new_state()
    assert (data.state, data.status, data.snapshot, data.is_exported) == (
        "normal",
        "created",
        "untracked",
        False,
    )
    assert data.issues == [] and data.src_files.db_files == []
    raises(FileExistsError, st.create, "ioc-a")  # never overwritten
    raises(KeyError, st.get, "ioc-none")
    raises(ValueError, st.create, "")
    # create() can take a whole state, and an invalid one is not written.
    custom = new_state()
    custom.status = "generated"
    custom.is_exported = "unknown"
    custom.issues = [make_issue("kept")]
    st.create("ioc-c", custom)
    assert st.get("ioc-c") == custom
    custom.status = 5
    raises(ValidationError, st.create, "ioc-d", custom)
    raises(KeyError, st.get, "ioc-d")
    st.delete("ioc-c")
    raises(KeyError, st.get, "ioc-c")
    raises(KeyError, st.delete, "ioc-c")
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM issue").fetchone()[0] == 0
    print("14. create, get, names, delete ok")

    # 15. setters: each changes one field and leaves the rest alone.
    st.set_state("ioc-a", "warning")
    st.set_status("ioc-a", "generated")
    st.set_snapshot("ioc-a", "tracked")
    st.set_exported("ioc-a", True)
    st.set_src_files(
        "ioc-a",
        {"db_files": ["a.db"], "protocol_files": ["a.proto"], "other_files": []},
    )
    data = st.get("ioc-a")
    assert (data.state, data.status, data.snapshot, data.is_exported) == (
        "warning",
        "generated",
        "tracked",
        True,
    )
    assert data.src_files.db_files == ["a.db"]
    assert (
        data.src_files.protocol_files == ["a.proto"]
        and data.src_files.other_files == []
    )
    st.set_exported("ioc-a", "unknown")
    assert st.get("ioc-a").is_exported == "unknown"
    assert st.get("ioc-b") == new_state()  # another IOC is untouched
    # an invalid value is not written; an IOC that is not there raises KeyError.
    raises(ValidationError, st.set_status, "ioc-a", 5)
    raises(ValidationError, st.set_src_files, "ioc-a", {"db_files": "a.db"})
    assert st.get("ioc-a").status == "generated"
    raises(KeyError, st.set_status, "ioc-none", "x")
    print("15. setters ok")

    # 16. issues: appended in order, never de-duplicated; clearing leaves the state field alone.
    issue = make_issue("first")
    st.add_issues("ioc-a", [issue])
    st.add_issues("ioc-a", [issue, make_issue("second", IssueLevel.ERROR)])
    data = st.get("ioc-a")
    assert [i.message for i in data.issues] == ["first", "first", "second"]
    assert data.issues[2].level == IssueLevel.ERROR
    assert st.get("ioc-b").issues == []
    st.replace_issues("ioc-a", [make_issue("only")])
    assert [i.message for i in st.get("ioc-a").issues] == ["only"]
    st.replace_issues("ioc-a", [])
    data = st.get("ioc-a")
    assert data.issues == [] and data.state == "warning"
    raises(ValidationError, st.add_issues, "ioc-a", [{"level": "nope"}])
    raises(KeyError, st.add_issues, "ioc-none", [issue])
    raises(KeyError, st.replace_issues, "ioc-none", [])
    st.add_issues("ioc-a", [issue])
    st.delete("ioc-a")  # the issues go with it
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM issue").fetchone()[0] == 0
    st.create("ioc-a")
    print("16. issues ok")

    # 17. transaction: several changes as one; undone together when the block raises.
    with st.transaction():
        st.set_status("ioc-a", "exported")
        st.add_issues("ioc-a", [make_issue("in tx")])
        st.create("ioc-e")
    assert st.get("ioc-a").status == "exported" and len(st.get("ioc-a").issues) == 1
    assert "ioc-e" in st.names()
    try:
        with st.transaction():
            st.set_status("ioc-a", "lost")
            st.delete("ioc-e")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert st.get("ioc-a").status == "exported" and "ioc-e" in st.names()
    # a failing call inside the block undoes the calls before it.
    try:
        with st.transaction():
            st.set_status("ioc-a", "lost")
            st.set_status("ioc-none", "x")
    except KeyError:
        pass
    assert st.get("ioc-a").status == "exported"
    try:
        with st.transaction():
            with st.transaction():
                pass
    except RuntimeError:
        pass
    else:
        raise AssertionError("a transaction must not be nested")
    st.set_status("ioc-a", "exported")  # the failed nesting left nothing open
    print("17. transaction ok")

    # 18. another connection writing: an operation waits, then gives up with TimeoutError.
    #     Readers are not blocked by a writer.
    st2 = opened(db, timeout=0.3)
    with st.transaction():
        st.set_status("ioc-a", "held")
        assert st2.get("ioc-a").status == "exported"  # not yet committed
        raises(TimeoutError, st2.set_status, "ioc-a", "blocked")
    assert st2.get("ioc-a").status == "held"
    st2.set_status("ioc-a", "exported")  # free again
    st2.close()
    hold = sqlite3.connect(db, isolation_level=None)
    hold.execute("BEGIN EXCLUSIVE")  # nothing can even read now
    raises(TimeoutError, opened, db, timeout=0.3)
    hold.execute("ROLLBACK")
    hold.close()
    print("18. busy database times out ok")

    # 19. threads sharing one instance, and processes each with their own: nothing is lost.
    #     The processes are started fresh: an instance cannot be carried across fork().
    import subprocess

    st.create("ioc-load")
    errors = []

    def thread_work():
        try:
            for _ in range(25):
                st.add_issues("ioc-load", [make_issue("thread")])
        except BaseException as e:
            errors.append(e)

    process_code = (
        "import sys; sys.path.insert(0, sys.argv[1])\n"
        "from core.ioc import IocState\n"
        "from core.ioc_schema import IssueEntry\n"
        "own = IocState(sys.argv[2])\n"
        "own.connect()\n"
        "for _ in range(25):\n"
        "    own.add_issues('ioc-load', [IssueEntry(level='info', reason='file_error',"
        " message='process', prompt='', time='t')])\n"
        "own.close()\n"
    )
    root = os.path.dirname(test_root)
    procs = [
        subprocess.Popen(
            [sys.executable, "-I", "-c", process_code, os.path.dirname(root), db]
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
    messages = [i.message for i in st.get("ioc-load").issues]
    assert messages.count("thread") == 200 and messages.count("process") == 100
    print("19. threads and processes writing together ok")

    # 20. the database file vanishes or is replaced under an open instance.
    os.remove(db)
    raises(FileNotFoundError, st.names)
    assert not os.path.exists(db)  # nothing was created in its place
    IocState.initialize(db)  # a new database: the open instance moves to it
    assert st.names() == []
    st.create("ioc-new")
    assert opened(db).names() == ["ioc-new"]
    # close() ends it.
    st.close()
    raises(RuntimeError, st.names)
    scoped = opened(db)
    assert scoped.names() == ["ioc-new"]
    scoped.close()
    raises(RuntimeError, scoped.names)
    scoped.connect()  # and it can be connected again
    assert scoped.names() == ["ioc-new"]
    scoped.close()
    print("20. vanished database is an error, replaced one is followed ok")

    # the generated config of a new project, as show() prints it.
    print("\n--- show() of a new project ---")
    path = os.path.join(test_root, "ioc-demo-show", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    conf.load()
    conf.show()
    print("\nAll tests passed.")
