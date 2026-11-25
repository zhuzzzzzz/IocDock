import os
import re
import shutil
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import settings
from core.exceptions import (
    IocExistsError,
    IocInitError,
    IocNotFoundError,
    IocRepositoryError,
)
from core.ioc_config import IocConfig
from core.ioc_repository import IocRepository
from core.ioc_schema import (
    IssueCode,
    IssueEntry,
    IssueLevel,
    IssueSource,
    new_state,
    sort_by_priority,
)
from core.ioc_state import get_state_manager
from core.utils import get_now_str

# The name of an IOC is also the name of its directory and of its Docker service and
# container, so it has to be valid for all of them: letters and digits, starting with a
# letter (no "." or "_", which a service name does not take or takes only inside, and
# no "-", which Docker joins names with), 2 to 63 characters (a container name has at
# least 2, a service name at most 63). Upper case is allowed, for camel case names; two names
# that differ only in case are still not allowed together (see _find_case_conflict()).
NAME_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9]+")
MAX_NAME_LENGTH = 63


def check_name(name):
    """Raise ValueError unless `name` can be the name of an IOC."""
    if (
        not isinstance(name, str)
        or len(name) > MAX_NAME_LENGTH
        or not NAME_PATTERN.fullmatch(name)
    ):
        raise ValueError(
            f"invalid IOC name {name!r}: use 2 to {MAX_NAME_LENGTH} letters "
            "and digits, starting with a letter"
        )


_PRESENCE_MESSAGES = {
    "complete": "{name}: already exists",
    "no_directory": "{name}: is in the database, but its directory is missing: {path}",
    "no_record": "{name}: not in the database, but the directory {path} exists",
}

_CASE_CONFLICT_MESSAGE = "{name}: differs only in case from the existing {other}"


def _is_utf8(path):
    """Whether `path` can be stored: a name from the file system that is not valid UTF-8
    has its odd bytes as lone surrogates (see IocRepository._git()), which neither the
    JSON nor the database take."""
    try:
        path.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _name_issue(path):
    """The issue of a file whose name is not valid UTF-8: the file is left out of the
    check. Its odd bytes are shown as \\xNN, which is also how the user finds it."""
    shown = path.encode("utf-8", "surrogateescape").decode("utf-8", "backslashreplace")
    return IssueEntry(
        source=IssueSource.CHECK,
        level=IssueLevel.WARNING,
        code=IssueCode.FILE_NAME_INVALID,
        target=shown,
        message=f"{shown}: the name of the file is not valid UTF-8, the file is left out",
        prompt="",
        time=get_now_str(),
    )


def _content(issue):
    """What of an issue says that it changed: its time is not part of it, the time
    a problem was first seen does not change with it."""
    return (issue.level, issue.code, issue.target, issue.message, issue.prompt)


class IOC:
    """One IOC: its state in the database, its config file and the version history
    of its directory. IOC(name) opens an IOC that exists, IOC.create(name) makes a
    new one.

    The database and the directory are equally part of an IOC, and when only one of
    them is there the IOC is opened all the same: a directory that is gone cannot be
    put back, so refresh() reports it as a problem; a directory without a record gets
    one, with the default state, and that repair is recorded as an issue of the IOC.

    Opening an IOC only reads its record. The files are looked at by refresh(), which
    a service calls over and over for every IOC (refresh_all()); call it yourself
    when the state and issues must be up to date right now."""

    def __init__(self, name):
        check_name(name)
        self.name = name
        self.dir_path = self._dir_of(name)
        self.config_path = os.path.join(self.dir_path, settings.CONFIG_FILE_NAME)
        self.src_path = os.path.join(self.dir_path, "src")
        self.state_manager = get_state_manager()
        self.config = IocConfig(path=self.config_path)
        self.repository = IocRepository(self.dir_path)
        try:
            self.state_data = self.state_manager.read_ioc(name)
        except KeyError:
            if not os.path.isdir(self.dir_path):
                raise IocNotFoundError(name) from None
            self._add_record()

    def _add_record(self):
        """A directory that has no record: make one, with the default state, and a
        repair record saying so. Nothing in the directory is touched."""
        message = _PRESENCE_MESSAGES["no_record"].format(
            name=self.name, path=self.dir_path
        ) + "; a record with the default state was made"
        with self.state_manager.transaction():
            if not self.state_manager.exists(self.name):  # else another process did
                if not os.path.isdir(self.dir_path):  # and one that was being made failed
                    raise IocNotFoundError(self.name)
                self.state_manager.write_ioc(
                    self.name, new_state().model_dump(exclude={"issues"})
                )
                self.state_manager.write_issues(
                    self.name,
                    [
                        IssueEntry(
                            source=IssueSource.REPAIR,
                            level=IssueLevel.WARNING,
                            code=IssueCode.RECORD_RESET,
                            target="",
                            message=message,
                            prompt="",
                            time=get_now_str(),
                        )
                    ],
                )
        self.state_data = self.state_manager.read_ioc(self.name)

    def record_operation(self, level, code, message, target=""):
        """Record the result of an operation the user did (a build, an export, ...),
        as an issue of the source OPERATION. `code` is the operation (one of the
        OPERATION_CODES of IssueCode) and `level` how it went: IssueLevel.INFO it
        worked, WARNING it worked but with problems, ERROR it failed. `target` is
        what it is about, for instance what it made. refresh() leaves it alone. Only
        the newest settings.MAX_OPERATION_RECORDS of them are kept, the state manager
        drops the oldest."""
        entry = IssueEntry(
            source=IssueSource.OPERATION,
            level=level,
            code=code,
            target=target,
            message=message,
            prompt="",
            time=get_now_str(),
        )
        self.state_manager.write_issues(self.name, [entry], append=True)
        self.state_data = self.state_manager.read_ioc(self.name)

    @classmethod
    def refresh_all(cls):
        """refresh() every IOC that has a record, for a service that runs it every few
        seconds. Returns {name: None or the exception it raised}: one IOC that cannot
        be refreshed does not stop the others. Only the IOCs of the database are
        visited, a directory without a record is left alone (opening it would make
        a record for it, and one that is just being created has none yet)."""
        results = {}
        for name in get_state_manager().list_iocs():
            try:
                cls(name).refresh()
                results[name] = None
            except Exception as e:
                results[name] = e
        return results

    def refresh(self):
        """Bring the record of the IOC up to date with what is on disk now, and
        return it (also in self.state_data):
          - src_files: the files in src/, told apart by their suffix (settings);
          - issues: the directory being gone, the config file (missing, unreadable,
            invalid), a missing src/ or git repository, and every file that differs
            from the latest snapshot. All of those are worked out again and replace
            the earlier ones, so what was fixed is gone and what stays is not added
            twice (it keeps the time it was first seen). Nothing is written when
            nothing changed.
        Nothing on disk is touched. A directory that is gone only gets its issue."""
        issues = []
        src_files = None
        if not os.path.isdir(self.dir_path):
            issues.append(
                IssueEntry(
                    source=IssueSource.CHECK,
                    level=IssueLevel.ERROR,
                    code=IssueCode.DIR_MISSING,
                    target="",
                    message=_PRESENCE_MESSAGES["no_directory"].format(
                        name=self.name, path=self.dir_path
                    ),
                    prompt="",
                    time=get_now_str(),
                )
            )
        else:
            issues += self._check_config()
            src_files, src_issues = self._scan_src()
            issues += src_issues
            issues += self._check_repository()
        with self.state_manager.transaction():
            if src_files is not None and src_files != self.state_manager.read_ioc(self.name).src_files:
                self.state_manager.write_ioc(self.name, {"src_files": src_files})
            self._replace_issues(issues)
        self.state_data = self.state_manager.read_ioc(self.name)
        return self.state_data

    def _check_config(self):
        try:
            self.config.load()
        except FileNotFoundError:
            return [
                IssueEntry(
                    source=IssueSource.CHECK,
                    level=IssueLevel.INFO,
                    code=IssueCode.CONFIG_MISSING,
                    target=settings.CONFIG_FILE_NAME,
                    message=f"config file not found: {self.config_path}",
                    prompt="",
                    time=get_now_str(),
                )
            ]
        return list(self.config.issues)

    def _scan_src(self):
        """The files directly in src/ (not hidden ones, not directories) as the three
        lists of src_files, each sorted, and the issues of src/ itself (it cannot be
        read, or the name of a file is not valid UTF-8: the file is left out)."""
        try:
            with os.scandir(self.src_path) as entries:
                names = sorted(
                    e.name for e in entries if e.is_file() and not e.name.startswith(".")
                )
        except OSError as e:
            return (
                new_state().src_files,
                [
                    IssueEntry(
                        source=IssueSource.CHECK,
                        level=IssueLevel.WARNING,
                        code=IssueCode.SRC_UNREADABLE,
                        target="src",
                        message=f"cannot read the source directory {self.src_path}: {e}",
                        prompt="",
                        time=get_now_str(),
                    )
                ],
            )
        bad_names = [n for n in names if not _is_utf8(n)]
        names = [n for n in names if _is_utf8(n)]
        db = [n for n in names if n.endswith(settings.DB_FILE_SUFFIXES)]
        protocol = [n for n in names if n.endswith(settings.PROTOCOL_FILE_SUFFIXES)]
        other = [n for n in names if n not in db and n not in protocol]
        return new_state().src_files.model_copy(
            update={"db_files": db, "protocol_files": protocol, "other_files": other}
        ), [_name_issue(f"src/{n}") for n in bad_names]

    def _check_repository(self):
        if not self.repository.is_initialized():
            return [
                IssueEntry(
                    source=IssueSource.CHECK,
                    level=IssueLevel.WARNING,
                    code=IssueCode.REPO_MISSING,
                    target="",
                    message=f"no git repository in {self.dir_path}, its history is not kept",
                    prompt="",
                    time=get_now_str(),
                )
            ]
        try:
            head = self.repository.head()
            if head is None:  # nothing has been committed, so there is nothing to differ from
                return []
            status = self.repository.status()
        except IocRepositoryError as e:
            return [
                IssueEntry(
                    source=IssueSource.CHECK,
                    level=IssueLevel.ERROR,
                    code=IssueCode.REPO_UNREADABLE,
                    target="",
                    message=f"cannot read the history of {self.dir_path}: {e}",
                    prompt="",
                    time=get_now_str(),
                )
            ]
        issues = []
        for kind in ("modified", "added", "deleted"):
            for path in status[kind]:
                if _is_utf8(path):
                    issues.append(
                        IssueEntry(
                            source=IssueSource.CHECK,
                            level=IssueLevel.WARNING,
                            code=IssueCode.FILE_CHANGED,
                            target=path,
                            message=f"{path}: {kind} since the snapshot {head[:8]}",
                            prompt="",
                            time=get_now_str(),
                        )
                    )
                elif kind != "deleted":  # a file that is gone is not there to be told about
                    issues.append(_name_issue(path))
        return issues

    def _replace_issues(self, found):
        """Make `found` the check issues of the IOC, and leave the repair and
        operation records alone. An issue that was there before and is found again,
        told by (code, target), keeps the time it was first seen, even when its
        message changed. An issue found twice (the same file by two scans) is one. Of `found` no more than settings.MAX_CHECK_ISSUES stay, the
        ones that matter most (sort_by_priority()), and they are cut before they are
        compared with what is there, or a `found` that is too long would never equal
        it. Nothing is written when nothing changed. Run inside a transaction."""
        old = self.state_manager.read_issues(self.name)
        ours = [i for i in old if i.source is IssueSource.CHECK]
        kept = [i for i in old if i.source is not IssueSource.CHECK]
        found = list({_content(i): i for i in found}.values())  # found twice is one issue
        first_seen = {}
        for i in ours:
            first_seen.setdefault((i.code, i.target), i.time)
        found = [
            i.model_copy(update={"time": first_seen.get((i.code, i.target), i.time)})
            for i in found
        ]
        found = sort_by_priority(found)[: settings.MAX_CHECK_ISSUES]
        if [_content(i) for i in ours] == [_content(i) for i in found]:
            return
        self.state_manager.write_issues(self.name, kept + found)

    @staticmethod
    def create_template(name, build_type=None, directory=None):
        """Write a config file made from a template for the IOC `name`, into
        `directory` (default: the current directory) and not into the IOC, which
        need not exist yet. The user edits it and adds it to the IOC afterwards.
        Returns its path. A file already there raises FileExistsError and is left
        alone, a name that is not valid raises ValueError."""
        check_name(name)
        path = os.path.join(directory or os.getcwd(), settings.CONFIG_FILE_NAME)
        IocConfig.create_template(path, build_type, name=name)
        return path

    @classmethod
    def create(cls, name, force=False):
        """Make a new, empty IOC and return it: its directory with an empty src/,
        a git repository without any commit yet, and its state in the database, with
        an issue of the operation CREATE saying it was created. The config and the source files are
        added afterwards. When a step fails what this call made is removed again and
        IocInitError is raised.

        The whole job is done inside one write transaction of the database, from
        looking at what is there to the commit. Another process that wants to write
        about this IOC, for instance by opening it while only the directory is there,
        waits for it to end and then finds the complete IOC.

        A name that is not valid raises ValueError. A name that is taken raises
        IocExistsError, and nothing is touched: an IOC whose name differs from it
        only in case (in the database or as a directory) always, even with `force`,
        a complete IOC always, and one that has only half of itself unless `force`
        is given:
          - only a record: the directory is made again and the record is reset to
            the default state, its old issues gone;
          - only a directory: it is kept as it is, with what is in it (an existing
            src/ and git repository too); what is missing is added, and it gets a
            record."""
        check_name(name)
        state_manager = get_state_manager()
        dir_path = cls._dir_of(name)
        src_path = os.path.join(dir_path, "src")
        made = []  # what this call made, so that it can be taken away again
        try:
            with state_manager.transaction():
                try:
                    other = cls._find_case_conflict(name)
                    if other is not None:
                        raise IocExistsError(
                            _CASE_CONFLICT_MESSAGE.format(name=name, other=other)
                        )
                    presence = cls.check_presence(name)
                    if presence == "complete" or (presence != "missing" and not force):
                        raise IocExistsError(
                            _PRESENCE_MESSAGES[presence].format(name=name, path=dir_path)
                        )
                    os.makedirs(settings.IOCS_DIR, exist_ok=True)
                    if presence != "no_record":
                        try:
                            os.mkdir(dir_path)  # fails if there is one, whoever made it
                        except FileExistsError:
                            raise IocExistsError(
                                _PRESENCE_MESSAGES["no_record"].format(name=name, path=dir_path)
                            ) from None
                        made.append(dir_path)
                    if not os.path.isdir(src_path):
                        os.makedirs(src_path)
                        made.append(src_path)
                    repository = IocRepository(dir_path)
                    if not repository.is_initialized():
                        repository.init()
                        made.append(os.path.join(dir_path, ".git"))
                    state_manager.write_ioc(name, new_state().model_dump(exclude={"issues"}))
                    state_manager.write_issues(
                        name,
                        [
                            IssueEntry(
                                source=IssueSource.OPERATION,
                                level=IssueLevel.INFO,
                                code=IssueCode.CREATE,
                                target="",
                                message="created"
                                if presence != "no_record"
                                else "created on the existing directory",
                                prompt="",
                                time=get_now_str(),
                            )
                        ],
                    )  # replaces the issues there were, which were about files that are gone
                except BaseException:
                    # undone before the lock is let go, so nobody sees the half
                    for path in [dir_path] if dir_path in made else made:
                        shutil.rmtree(path, ignore_errors=True)
                    raise
        except IocExistsError:
            raise
        except Exception as e:
            raise IocInitError(f"{name}: {e}") from e
        return cls(name)

    @classmethod
    def check_presence(cls, name):
        """How much of the IOC `name` is there. Only the first two are consistent:
            "missing"       nothing: no record in the database, no directory
            "complete"      a record in the database and its directory
            "no_directory"  a record, but the directory is gone
            "no_record"     a directory, but no record in the database"""
        check_name(name)
        registered = get_state_manager().exists(name)
        has_dir = os.path.isdir(cls._dir_of(name))
        if registered:
            return "complete" if has_dir else "no_directory"
        return "no_record" if has_dir else "missing"

    @classmethod
    def _find_case_conflict(cls, name):
        """The name of an IOC that differs from `name` only in case, or None. The
        IOCs looked at are the records of the database and the directories of
        IOCS_DIR (a name is the name of its directory, so every directory counts, one
        without a record too); files are not IOCs. The same name is not a conflict,
        that is check_presence()'s business. Run inside the transaction of create()."""
        lower = name.lower()
        taken = set(get_state_manager().list_iocs())
        try:
            with os.scandir(settings.IOCS_DIR) as entries:
                taken.update(e.name for e in entries if e.is_dir())
        except FileNotFoundError:
            pass
        return next((n for n in sorted(taken) if n != name and n.lower() == lower), None)

    @staticmethod
    def _dir_of(name):
        return os.path.join(settings.IOCS_DIR, name)
