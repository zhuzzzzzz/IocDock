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
    def create_template(path, build_type):
        if os.path.isfile(path):
            raise FileExistsError(path)
        buf = StringIO()
        get_yaml_tool().dump(
            new_config(get_dir_name(path), build_type=build_type).model_dump(), buf
        )
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
            if self._is_database_busy(e):
                raise TimeoutError(
                    f"state database is busy for more than {self.timeout}s: {self.db_path}"
                ) from e
            raise sqlite3.DatabaseError(f"{path}: {e}") from e
        except BaseException:
            conn.close()
            raise
        return conn, (st.st_dev, st.st_ino)

    def _ensure_open(self):
        if self._conn is None:
            raise RuntimeError(f"state database is not connected: {self.db_path}")
        st = os.stat(self.db_path)
        if (st.st_dev, st.st_ino) != self._ident:
            conn, ident = self._open()
            self._conn.close()
            self._conn, self._ident = conn, ident

    def close(self):
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @staticmethod
    def _is_database_busy(error):
        """SQLite reports "the database stayed locked by another process for the
        whole `timeout`" as a sqlite3.OperationalError, the same class as any other
        operational error, so only its message tells them apart."""
        return isinstance(error, sqlite3.OperationalError) and (
            "locked" in str(error) or "busy" in str(error)
        )

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
                if self._is_database_busy(e):
                    raise TimeoutError(
                        f"state database is busy for more than {self.timeout}s: {self.db_path}"
                    ) from e
                raise
            try:
                yield conn
                conn.execute("COMMIT")
            except BaseException as e:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                if self._is_database_busy(e):
                    raise TimeoutError(
                        f"state database is busy for more than {self.timeout}s: {self.db_path}"
                    ) from e
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

    # the columns of the ioc table besides its name, with the schema's type for each.
    # A column keeps the JSON text of its value; issues have a table of their own.
    ADAPTERS = {
        f: TypeAdapter(m.annotation)
        for f, m in IocStateSchema.model_fields.items()
        if f != "issues"
    }

    def read_ioc(self, name):
        """The whole state of an IOC, its issues too, as an IocStateSchema. An IOC
        that is not there raises KeyError."""
        with self._txn(False) as conn:
            row = conn.execute(
                f"SELECT {', '.join(self.ADAPTERS)} FROM ioc WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                raise KeyError(name)
            issues = conn.execute(
                "SELECT level, reason, message, prompt, time FROM issue"
                " WHERE ioc_name = ? ORDER BY id",
                (name,),
            ).fetchall()
        return IocStateSchema(
            **{f: a.validate_json(t) for (f, a), t in zip(self.ADAPTERS.items(), row)},
            issues=[
                IssueEntry(**dict(zip(IssueEntry.model_fields, i))) for i in issues
            ],
        )

    def write_ioc(self, name, values):
        """Write the columns in `values` (a dict) of an IOC. An IOC that is not
        there is added, and then values must have every column. Values are
        validated first; if one is invalid nothing is written."""
        if not isinstance(name, str) or not name:
            raise ValueError("the name of an IOC is a non-empty string")
        unknown = set(values) - set(self.ADAPTERS)
        if unknown or not values:
            raise ValueError(
                f"write_ioc() takes one or more of {list(self.ADAPTERS)}, got {sorted(unknown) or 'none'}"
            )
        encoded = {}
        for field, value in values.items():
            adapter = self.ADAPTERS[field]
            encoded[field] = adapter.dump_json(adapter.validate_python(value)).decode()
        with self._txn(True) as conn:
            changed = conn.execute(
                f"UPDATE ioc SET {', '.join(f'{f} = ?' for f in encoded)} WHERE name = ?",
                (*encoded.values(), name),
            ).rowcount
            if changed == 0:
                conn.execute(
                    f"INSERT INTO ioc (name, {', '.join(encoded)})"
                    f" VALUES (?{', ?' * len(encoded)})",
                    (name, *encoded.values()),
                )

    def delete_ioc(self, name):
        """Remove an IOC with its issues."""
        with self._txn(True) as conn:
            if conn.execute("DELETE FROM ioc WHERE name = ?", (name,)).rowcount == 0:
                raise KeyError(name)

    def names(self):
        """The names of all IOCs, sorted."""
        with self._txn(False) as conn:
            return [r[0] for r in conn.execute("SELECT name FROM ioc ORDER BY name")]

    def read_issues(self, name):
        """Only the issues of an IOC, oldest first, as IssueEntry. An IOC that is
        not there has none."""
        with self._txn(False) as conn:
            rows = conn.execute(
                "SELECT level, reason, message, prompt, time FROM issue"
                " WHERE ioc_name = ? ORDER BY id",
                (name,),
            ).fetchall()
        return [IssueEntry(**dict(zip(IssueEntry.model_fields, row))) for row in rows]

    def write_issues(self, name, issues, append=False):
        """Replace the issues of an IOC with `issues`, or with append=True add them
        after the ones there. Issues are never de-duplicated. Issues of an IOC that
        is not there raise sqlite3.IntegrityError."""
        entries = [IssueEntry.model_validate(i) for i in issues]
        with self._txn(True) as conn:
            if not append:
                conn.execute("DELETE FROM issue WHERE ioc_name = ?", (name,))
            conn.executemany(
                "INSERT INTO issue (ioc_name, level, reason, message, prompt, time)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (name, *(d[f] for f in IssueEntry.model_fields))
                    for d in (e.model_dump(mode="json") for e in entries)
                ],
            )


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

    def add_ioc(state, name, data=None):
        data = new_state() if data is None else data
        state.write_ioc(name, {f: getattr(data, f) for f in IocState.ADAPTERS})
        state.write_issues(name, data.issues, append=True)

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
    assert (
        sqlite3.connect(db).execute("PRAGMA user_version").fetchone()[0]
        == IocState.SCHEMA_VERSION
    )
    print("13. database is created only by initialize() ok")

    # 14. write_ioc, read_ioc, names, delete_ioc.
    st = opened(db)
    assert st.names() == []  # initialize() leaves the tables empty
    add_ioc(st, "ioc-b")
    add_ioc(st, "ioc-a")
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
    # every column keeps the JSON text of its value; read_ioc gives the values back.
    raw = (
        sqlite3.connect(db)
        .execute("SELECT state, is_exported, src_files FROM ioc WHERE name = 'ioc-a'")
        .fetchone()
    )
    assert raw == (
        '"normal"',
        "false",
        '{"db_files":[],"protocol_files":[],"other_files":[]}',
    )
    # the columns of the table are the schema's fields (but issues), so none is left out.
    columns = [r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(ioc)")]
    assert columns == ["name", *IocState.ADAPTERS]
    assert "issues" not in IocState.ADAPTERS
    raises(KeyError, st.read_ioc, "ioc-none")
    raises(ValueError, add_ioc, st, "")
    # any name is just a value: quotes, spaces and non-ASCII are not special.
    odd = 'ioc "测试" \'1\'; DROP TABLE ioc; --'
    add_ioc(st, odd)
    assert odd in st.names() and st.read_ioc(odd) == new_state()
    st.delete_ioc(odd)
    # a whole state can be written, and an invalid one is not written.
    custom = new_state()
    custom.status = "generated"
    custom.is_exported = "unknown"
    custom.issues = [make_issue("kept")]
    add_ioc(st, "ioc-c", custom)
    assert st.read_ioc("ioc-c") == custom
    custom.status = 5
    raises(ValidationError, add_ioc, st, "ioc-d", custom)
    raises(KeyError, st.read_ioc, "ioc-d")
    st.delete_ioc("ioc-c")
    raises(KeyError, st.read_ioc, "ioc-c")
    raises(KeyError, st.delete_ioc, "ioc-c")
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM issue").fetchone()[0] == 0
    # content in the database that does not fit the schema is an error, not a guess.
    add_ioc(st, "ioc-bad")
    for column, text in (("status", "5"), ("status", "not json"), ("src_files", "{}")):
        damage = sqlite3.connect(db)
        damage.execute(f"UPDATE ioc SET {column} = ? WHERE name = 'ioc-bad'", (text,))
        damage.commit()
        damage.close()
        raises(ValidationError, st.read_ioc, "ioc-bad")
    st.delete_ioc("ioc-bad")
    print("14. write_ioc, read_ioc, names, delete_ioc ok")

    # 15. write_ioc on an IOC that is there: changes the given columns, leaves the rest alone.
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
    assert (
        data.src_files.protocol_files == ["a.proto"]
        and data.src_files.other_files == []
    )
    st.write_ioc("ioc-a", {"is_exported": "unknown"})
    assert st.read_ioc("ioc-a").is_exported == "unknown"
    assert st.read_ioc("ioc-b") == new_state()  # another IOC is untouched
    # an invalid value is not written, and one invalid value stops the whole change.
    raises(ValidationError, st.write_ioc, "ioc-a", {"status": 5})
    raises(ValidationError, st.write_ioc, "ioc-a", {"src_files": {"db_files": "a.db"}})
    raises(ValidationError, st.write_ioc, "ioc-a", {"state": "error", "status": 5})
    data = st.read_ioc("ioc-a")
    assert data.status == "generated" and data.state == "warning"
    raises(ValueError, st.write_ioc, "ioc-a", {})  # nothing to write
    raises(ValueError, st.write_ioc, "ioc-a", {"issues": []})  # not a column of ioc
    # an IOC that is not there needs every column, or nothing is added.
    raises(sqlite3.IntegrityError, st.write_ioc, "ioc-none", {"status": "x"})
    raises(KeyError, st.read_ioc, "ioc-none")
    assert "ioc-none" not in st.names()
    print("15. write_ioc on an existing IOC ok")

    # 16. issues: appended in order, never de-duplicated; replacing leaves the state alone.
    issue = make_issue("first")
    st.write_issues("ioc-a", [issue], append=True)
    st.write_issues(
        "ioc-a", [issue, make_issue("second", IssueLevel.ERROR)], append=True
    )
    data = st.read_ioc("ioc-a")
    assert [i.message for i in data.issues] == ["first", "first", "second"]
    assert data.issues[2].level == IssueLevel.ERROR
    assert st.read_issues("ioc-b") == []
    st.write_issues("ioc-a", [make_issue("only")])  # replaces
    assert [i.message for i in st.read_issues("ioc-a")] == ["only"]
    st.write_issues("ioc-a", [])
    data = st.read_ioc("ioc-a")
    assert data.issues == [] and data.state == "warning"
    # an invalid entry stops a replace before the old log is touched.
    st.write_issues("ioc-a", [make_issue("kept")])
    raises(ValidationError, st.write_issues, "ioc-a", [{"level": "nope"}])
    raises(ValidationError, st.write_issues, "ioc-a", [issue, {"level": "nope"}])
    assert [i.message for i in st.read_issues("ioc-a")] == ["kept"]
    raises(sqlite3.IntegrityError, st.write_issues, "ioc-none", [issue])  # no such IOC
    assert st.read_issues("ioc-none") == []
    st.write_issues("ioc-none", [])  # nothing to write for an IOC that is not there
    assert "ioc-none" not in st.names()
    st.write_issues("ioc-a", [issue], append=True)
    st.delete_ioc("ioc-a")  # the issues go with it
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM issue").fetchone()[0] == 0
    add_ioc(st, "ioc-a")
    print("16. issues ok")

    # 17. transaction: several changes as one; undone together when the block raises.
    with st.transaction():
        st.write_ioc("ioc-a", {"status": "exported"})
        st.write_issues("ioc-a", [make_issue("in tx")], append=True)
        add_ioc(st, "ioc-e")
    assert st.read_ioc("ioc-a").status == "exported"
    assert len(st.read_issues("ioc-a")) == 1
    assert "ioc-e" in st.names()
    try:
        with st.transaction():
            st.write_ioc("ioc-a", {"status": "lost"})
            st.delete_ioc("ioc-e")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert st.read_ioc("ioc-a").status == "exported" and "ioc-e" in st.names()
    # a failing call inside the block undoes the calls before it.
    try:
        with st.transaction():
            st.write_ioc("ioc-a", {"status": "lost"})
            st.delete_ioc("ioc-none")
    except KeyError:
        pass
    assert st.read_ioc("ioc-a").status == "exported"
    try:
        with st.transaction():
            with st.transaction():
                pass
    except RuntimeError:
        pass
    else:
        raise AssertionError("a transaction must not be nested")
    # the failed nesting left nothing open
    st.write_ioc("ioc-a", {"status": "exported"})
    print("17. transaction ok")

    # 18. another connection writing: an operation waits, then gives up with TimeoutError.
    #     Readers are not blocked by a writer.
    st2 = opened(db, timeout=0.3)
    with st.transaction():
        st.write_ioc("ioc-a", {"status": "held"})
        assert st2.read_ioc("ioc-a").status == "exported"  # not yet committed
        raises(TimeoutError, st2.write_ioc, "ioc-a", {"status": "blocked"})
    assert st2.read_ioc("ioc-a").status == "held"
    st2.write_ioc("ioc-a", {"status": "exported"})  # free again
    st2.close()
    hold = sqlite3.connect(db, isolation_level=None)
    hold.execute("BEGIN EXCLUSIVE")  # nothing can even read now
    raises(TimeoutError, opened, db, timeout=0.3)
    hold.execute("ROLLBACK")
    hold.close()
    # only "locked by another process" becomes a TimeoutError; other errors are left alone.
    busy = IocState._is_database_busy
    assert busy(sqlite3.OperationalError("database is locked"))
    assert busy(sqlite3.OperationalError("database table is locked"))
    assert not busy(sqlite3.OperationalError("no such table: ioc"))
    assert not busy(ValueError("database is locked"))
    print("18. busy database times out ok")

    # 19. threads sharing one instance, and processes each with their own: nothing is lost.
    #     The processes are started fresh: an instance cannot be carried across fork().
    import subprocess

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
    messages = [i.message for i in st.read_issues("ioc-load")]
    assert messages.count("thread") == 200 and messages.count("process") == 100
    print("19. threads and processes writing together ok")

    # 20. the database file vanishes or is replaced under an open instance.
    os.remove(db)
    raises(FileNotFoundError, st.names)
    assert not os.path.exists(db)  # nothing was created in its place
    IocState.initialize(db)  # a new database: the open instance moves to it
    assert st.names() == []
    add_ioc(st, "ioc-new")
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
