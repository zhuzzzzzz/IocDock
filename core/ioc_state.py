import os
import sqlite3
import threading
from contextlib import contextmanager

from pydantic import TypeAdapter

from core import settings
from core.ioc_schema import IocStateSchema, IssueEntry


class IocStateManager:
    """The state of the managed IOCs, kept in one SQLite database. The database
    is the only record of that state, so it is never created or emptied behind
    the caller's back: connect() on a missing database raises FileNotFoundError,
    and IocStateManager.initialize() creates it.

    IocStateManager() only records where the database is. connect() opens the connection,
    once, and it is kept until close(). One instance can be shared by threads: every operation takes the instance lock for its whole
    transaction. Other processes are kept out by SQLite itself; an operation that
    waits longer than `timeout` seconds for them raises TimeoutError.

    An instance must not be carried across fork(): SQLite copies its lock state
    into the child, which then finds the database locked for good. Start a new
    process and build the instance there."""

    SCHEMA_VERSION = 1
    # the tables of the database. initialize() runs it, and it can be run by hand:
    #   python3 -c "from core.ioc_state import IocStateManager; print(IocStateManager.SCHEMA_SQL)" | sqlite3 <db>
    SCHEMA_SQL = f"""\
BEGIN;
CREATE TABLE ioc (
    name      TEXT PRIMARY KEY,
    state     TEXT NOT NULL,
    snapshot  TEXT NOT NULL,
    src_files TEXT NOT NULL
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
        self.db_path = os.path.abspath(db_path or settings.DEFAULT_DB_PATH)
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
        path = os.path.abspath(db_path or settings.DEFAULT_DB_PATH)
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
        """Internal. Makes one operation (one read or one write method) atomic:
        its SQL either all takes effect or none of it does. Commits when the block
        ends, rolls back if it raises. Every read/write method wraps its SQL in it:
            with self._txn(False) as conn: ...   # a read
            with self._txn(True) as conn: ...    # a write
        Inside transaction() it does not start its own transaction, it joins that one.
        """
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
        """For callers. Makes several operations atomic together: either all of
        them take effect, or, if one raises, none does (the earlier ones are undone
        too). Without it each call commits by itself, so the earlier ones would stay.
            with state.transaction():
                state.write_ioc("ioc-a", {"snapshot": "tracked"})
                state.write_issues("ioc-a", [issue], append=True)
        It cannot be nested."""
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

    def exists(self, name):
        """Whether there is a record of the IOC `name`. Only that is looked at, not
        its state."""
        with self._txn(False) as conn:
            return conn.execute("SELECT 1 FROM ioc WHERE name = ?", (name,)).fetchone() is not None

    def list_iocs(self):
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


# The IocStateManager shared by everything in this process. It is connected the first
# time get_state_manager() is called, not when this module is imported, so importing
# it needs no database (scripts/init_state_db.py relies on that), and a process that
# forks gets its own connection instead of the parent's.
_shared = None
_shared_pid = None
_shared_lock = threading.Lock()


def get_state_manager():
    """The process-wide IocStateManager, connected on first use. A missing or broken
    database raises here, with the errors of IocStateManager.connect()."""
    global _shared, _shared_pid
    with _shared_lock:
        if _shared is None or _shared_pid != os.getpid():
            manager = IocStateManager()
            manager.connect()
            _shared, _shared_pid = manager, os.getpid()
        return _shared

