import fcntl
import os
import sys
from contextlib import contextmanager
from io import StringIO

from pydantic import ValidationError

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
        self.config = None
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
        self.config = None
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
            self.config = IocConfigSchema.model_validate(data)
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
        if self.config is not None:
            name, dir_name = self.config.basic.name, get_dir_name(self.path)
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
        # passed only if nothing is wrong: a config can be usable (config is not None)
        # and still not pass, e.g. when basic.name does not match the directory.
        self.is_valid = self.config is not None and not any(
            i.level in (IssueLevel.WARNING, IssueLevel.ERROR) for i in self.issues
        )

    def to_string(self):
        if self.config is None:
            raise RuntimeError("config is not loaded")
        buf = StringIO()
        self._yaml.dump(self.config.model_dump(), buf)
        return buf.getvalue()

    def show(self):
        sys.stdout.write(self.to_string())

    def save(self, path):
        atomic_write(path, self.to_string())


class IocState:
    """Reads and writes a .state.json. It holds no state of its own and decides
    nothing: every method takes the path of the file, and what the state should
    be is up to the caller."""

    _held_locks = {}  # lock files this process holds, so the lock can be taken again

    @staticmethod
    def create(path):
        """Write the initial state of a new project at path."""
        if os.path.isfile(path):
            raise FileExistsError(path)
        IocState.save(path, new_state())

    @staticmethod
    def load(path):
        """Return the state at path. A file that is missing, damaged or invalid
        raises (FileNotFoundError, ValidationError); the caller decides what then."""
        with open(path, "r", encoding="utf-8") as f:
            return IocStateSchema.model_validate_json(f.read())

    @staticmethod
    def save(path, data):
        """Write data atomically. An invalid state is never written."""
        data = IocStateSchema.model_validate(data.model_dump(warnings=False))
        atomic_write(path, data.model_dump_json(indent=2) + "\n")

    @classmethod
    @contextmanager
    def lock(cls, path):
        """Hold the lock of the state file at path. It sits on <path>.lock, not on
        the state file, because saving replaces the state file. Taking it again in
        the same process is allowed, so a caller can wrap several changes in one lock."""
        lock_path = os.path.abspath(path) + ".lock"
        if lock_path in cls._held_locks:
            cls._held_locks[lock_path] += 1
            try:
                yield
            finally:
                cls._held_locks[lock_path] -= 1
            return
        with open(lock_path, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            cls._held_locks[lock_path] = 1
            try:
                yield
            finally:
                del cls._held_locks[lock_path]
                fcntl.flock(f, fcntl.LOCK_UN)

    @classmethod
    def _update(cls, path, **fields):
        with cls.lock(path):
            data = cls.load(path)
            for name, value in fields.items():
                setattr(data, name, value)
            cls.save(path, data)

    @classmethod
    def set_state(cls, path, state):
        cls._update(path, state=state)

    @classmethod
    def set_status(cls, path, status):
        cls._update(path, status=status)

    @classmethod
    def set_snapshot(cls, path, snapshot):
        cls._update(path, snapshot=snapshot)

    @classmethod
    def set_exported(cls, path, is_exported):
        cls._update(path, is_exported=is_exported)

    @classmethod
    def set_src_files(cls, path, src_files):
        """src_files is a dict with db_files, protocol_files and other_files."""
        with cls.lock(path):
            data = cls.load(path)
            data.src_files = type(data.src_files)(**src_files)
            cls.save(path, data)

    @classmethod
    def add_issues(cls, path, issues):
        """Append issues to the log. They are never de-duplicated."""
        with cls.lock(path):
            data = cls.load(path)
            data.issues.extend(issues)
            cls.save(path, data)

    @classmethod
    def add_issue(cls, path, issue):
        cls.add_issues(path, [issue])

    @classmethod
    def clear_issues(cls, path):
        """Empty the log. The state field is left alone: that is the caller's call."""
        cls._update(path, issues=[])


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
    assert conf.issues == [] and conf.config is not None
    assert conf.is_valid is True
    assert conf.config.basic.name == "ioc-demo"
    assert "src" not in conf.config.model_dump()
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
    assert odd.config is not None and odd.config.basic.name == 'ioc "测试" #1\\x'
    print("1. create ok")

    # 2. typed access: values are read from conf.config, lists and mappings as such.
    path = os.path.join(test_root, "t-get", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    conf.load()
    assert conf.config.basic.host == "swarm"
    assert conf.config.build.modules[0] == "autosave"
    assert "autosave" in conf.config.build.modules and "status-os" not in conf.config.build.modules
    assert conf.config.build.db_load[0].macros["ABC"] == "xxx:"
    assert conf.config.build.settings.report_info is True
    try:
        conf.config.build.no_such_field
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
    assert conf.config is not None and conf.issues == []
    assert conf.config.basic.image == "registry.iasf/ioc:1.0"
    assert conf.config.build.db_load[0].macros["P"] == "xxx:"
    assert conf.config.build.raw_cmd.cmd_at_dbload == 'line1\ndbLoadRecords("x.db")\n'
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
    assert conf.is_valid is True and conf.config.build.modules == []
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
    assert conf.config is None and len(conf.issues) == 1
    assert conf.is_valid is False
    issue = conf.issues[0]
    assert isinstance(issue, IssueEntry) and issue.level == IssueLevel.ERROR
    assert issue.reason == IssueReason.VALIDATION_ERROR
    assert issue.message.startswith("deploy.resources.limits.cpus:")
    assert conf.config is None
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
    assert conf.config is not None and conf.issues == []
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
    assert conf.config is None
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
    assert conf.config is None
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
    assert conf.config is not None and conf.issues == []
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
    assert conf.config is not None and len(conf.issues) == 1
    assert conf.is_valid is False  # usable, but the name check failed
    assert conf.issues[0].level == IssueLevel.WARNING and conf.issues[
        0
    ].message.startswith("basic.name:")
    assert conf.issues[0].reason == IssueReason.VALIDATION_ERROR
    with open(conf.path, "w", encoding="utf-8") as f:
        f.write(base)
    conf.load()
    assert conf.config is not None and conf.issues == []
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
        assert bad.config is None and len(bad.issues) == 1
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
    assert bad.config is None and bad.is_valid is False
    # a file that disappears after a successful load leaves no stale result behind.
    path = os.path.join(test_root, "t-vanish", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    vanish = IocConfig(path)
    vanish.load()
    assert vanish.config is not None and vanish.is_valid is True
    os.remove(path)
    try:
        vanish.load()
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("load() must raise when the file does not exist")
    assert vanish.config is None and vanish.issues == [] and vanish.is_valid is False
    print("9. unreadable file becomes an issue, missing file raises ok")

    # 10. show, to_string and save before load() raise.
    path = os.path.join(test_root, "t-fresh", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    fresh = IocConfig(conf.path)
    assert fresh.config is None and fresh.is_valid is False
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
    assert fresh.config is not None
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
    assert get_yaml_tool().load(out) == conf.config.model_dump()
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
    assert target.issues == [] and target.config == source.config
    with open(target_path, encoding="utf-8") as f:
        assert "# my own note" not in f.read()
    # an invalid config cannot be saved, and nothing is written.
    with open(path, "w", encoding="utf-8") as f:
        f.write(source_text.replace("cpus: '1'", "cpus: 1"))
    invalid = IocConfig(path)
    invalid.load()
    assert invalid.config is None
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

    # 13. state file: create writes the initial state; load reads it back; save writes a change.
    path = os.path.join(test_root, "t-state", ".state.json")
    os.makedirs(os.path.dirname(path))
    IocState.create(path)
    data = IocState.load(path)
    assert data == new_state()
    assert (data.state, data.status, data.snapshot, data.is_exported) == (
        "normal",
        "created",
        "untracked",
        False,
    )
    assert data.issues == [] and data.src_files.db_files == []
    assert [f for f in os.listdir(os.path.dirname(path)) if f.endswith(".tmp")] == []
    try:
        IocState.create(path)
    except FileExistsError:
        pass
    else:
        raise AssertionError("create() must not overwrite an existing file")
    data.status = "generated"
    IocState.save(path, data)
    assert IocState.load(path).status == "generated"
    # an invalid state is never written.
    data.status = 5
    try:
        IocState.save(path, data)
    except ValidationError:
        pass
    else:
        raise AssertionError("an invalid state must not be saved")
    assert IocState.load(path).status == "generated"
    print("13. state file ok")

    # 14. a state file that cannot be loaded raises; what to do about it is up to the caller.
    path = os.path.join(test_root, "t-state-bad", ".state.json")
    os.makedirs(os.path.dirname(path))
    for content, exc in (
        (None, FileNotFoundError),
        ("{not json", ValidationError),
        ('{"state": "normal"}', ValidationError),
        ("", ValidationError),
    ):
        if content is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        try:
            IocState.load(path)
        except exc:
            pass
        else:
            raise AssertionError(f"{exc.__name__} not raised for {content!r}")
    print("14. unreadable state file raises ok")

    # 15. setters: each changes one field on disk and leaves the rest alone.
    path = os.path.join(test_root, "t-state-set", ".state.json")
    os.makedirs(os.path.dirname(path))
    IocState.create(path)
    IocState.set_state(path, "warning")
    IocState.set_status(path, "generated")
    IocState.set_snapshot(path, "tracked")
    IocState.set_exported(path, True)
    IocState.set_src_files(
        path, {"db_files": ["a.db"], "protocol_files": [], "other_files": []}
    )
    data = IocState.load(path)
    assert (data.state, data.status, data.snapshot, data.is_exported) == (
        "warning",
        "generated",
        "tracked",
        True,
    )
    assert data.src_files.db_files == ["a.db"] and data.issues == []
    issue = IssueEntry(
        level=IssueLevel.ERROR,
        reason=IssueReason.VALIDATION_ERROR,
        message="m",
        prompt="",
        time=get_now_str(),
    )
    IocState.add_issue(path, issue)
    IocState.add_issues(path, [issue, issue])
    assert len(IocState.load(path).issues) == 3  # appended, never de-duplicated
    IocState.clear_issues(path)
    data = IocState.load(path)
    assert data.issues == [] and data.state == "warning"  # the state field is not touched
    try:
        IocState.set_status(path, 5)
    except ValidationError:
        pass
    else:
        raise AssertionError("an invalid value must not be saved")
    assert IocState.load(path).status == "generated"
    print("15. state setters ok")

    # 16. lock: keeps others out while held, and can be taken again by the same process.
    import signal

    path = os.path.join(test_root, "t-state-lock", ".state.json")
    os.makedirs(os.path.dirname(path))
    IocState.create(path)
    signal.alarm(10)  # a deadlock would hang here, so stop the test instead
    with IocState.lock(path):
        probe = open(path + ".lock", "a")
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise AssertionError("the lock must keep others out while it is held")
        probe.close()
        IocState.set_status(path, "exported")  # takes the lock again: must not deadlock
        with IocState.lock(path):
            pass
        probe = open(path + ".lock", "a")
        try:
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise AssertionError("an inner lock must not release the outer one")
        probe.close()
    probe = open(path + ".lock", "a")
    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)  # free again
    probe.close()
    signal.alarm(0)
    assert IocState.load(path).status == "exported"
    print("16. state lock ok")

    # the generated config of a new project, as show() prints it.
    print("\n--- show() of a new project ---")
    path = os.path.join(test_root, "ioc-demo-show", "ioc.yaml")
    os.makedirs(os.path.dirname(path))
    IocConfig.create_template(path, None)
    conf = IocConfig(path)
    conf.load()
    conf.show()
    print("\nAll tests passed.")
