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
from core.ioc_schema import IssueEntry, IssueLevel, IssueReason, new_state
from core.ioc_state import get_state_manager
from core.utils import get_now_str

# The name of an IOC is also the name of its directory, of its Docker service and
# container, and a DNS label in the swarm network, so it has to be valid for all of
# them: lowercase letters and digits, starting with a letter (no "_" or ".", which DNS
# names and swarm service names do not take, and no "-", which Docker joins names
# with), 2 to 63 characters (a container name has at least 2, a DNS label at most 63).
NAME_PATTERN = re.compile(r"[a-z][a-z0-9]+")
MAX_NAME_LENGTH = 63


def check_name(name):
    """Raise ValueError unless `name` can be the name of an IOC."""
    if (
        not isinstance(name, str)
        or len(name) > MAX_NAME_LENGTH
        or not NAME_PATTERN.fullmatch(name)
    ):
        raise ValueError(
            f"invalid IOC name {name!r}: use 2 to {MAX_NAME_LENGTH} lowercase letters "
            "and digits, starting with a letter"
        )


# The issues refresh() finds out again each time it runs. It replaces all of them, so
# one that is gone (the file was fixed) disappears and one that stays is not added
# twice. The others are not about what is there now and are kept: RECORD_RESET, and
# the records of the operations that were done (see record_success()).
_OPERATION_REASONS = {IssueReason.OPERATION_SUCCESS, IssueReason.OPERATION_FAILED}
_REFRESHED_REASONS = {IssueReason.VALIDATION_ERROR, IssueReason.FILE_ERROR, IssueReason.FILE_CHANGED}

_PRESENCE_MESSAGES = {
    "complete": "{name}: already exists",
    "no_directory": "{name}: is in the database, but its directory is missing: {path}",
    "unregistered": "{name}: not in the database, but the directory {path} exists",
}


class IOC:
    """One IOC: its state in the database, its config file and the version history
    of its directory. IOC(name) opens an IOC that exists, IOC.create(name) makes a
    new one.

    The database and the directory are equally part of an IOC, and when only one of
    them is there the IOC is opened all the same and the problem is recorded as an
    issue of the IOC: a directory that is gone cannot be put back; a directory
    without a record gets one, with the default state.

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
        """A directory that has no record: make one, with the default state, and an
        issue saying so. Nothing in the directory is touched."""
        message = _PRESENCE_MESSAGES["unregistered"].format(
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
                    [self._issue(IssueLevel.ERROR, IssueReason.RECORD_RESET, message)],
                )
        self.state_data = self.state_manager.read_ioc(self.name)

    def record_success(self, message):
        """Record that an operation (a build, an export, ...) succeeded, as an INFO
        issue. refresh() leaves it alone."""
        self._record_operation(IssueLevel.INFO, IssueReason.OPERATION_SUCCESS, message)

    def record_failure(self, message):
        """Record that an operation failed, as an ERROR issue. refresh() leaves it
        alone."""
        self._record_operation(IssueLevel.ERROR, IssueReason.OPERATION_FAILED, message)

    def _record_operation(self, level, reason, message):
        """Successes and failures share one limit: only the newest
        settings.MAX_OPERATION_RECORDS of them are kept, the oldest are dropped."""
        with self.state_manager.transaction():
            self.state_manager.write_issues(
                self.name, [self._issue(level, reason, message)], append=True
            )
            issues = self.state_manager.read_issues(self.name)
            records = [n for n, i in enumerate(issues) if i.reason in _OPERATION_REASONS]
            excess = len(records) - settings.MAX_OPERATION_RECORDS
            if excess > 0:
                dropped = set(records[:excess])
                self.state_manager.write_issues(
                    self.name, [i for n, i in enumerate(issues) if n not in dropped]
                )
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
                self._issue(
                    IssueLevel.ERROR,
                    IssueReason.FILE_ERROR,
                    _PRESENCE_MESSAGES["no_directory"].format(name=self.name, path=self.dir_path),
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
                self._issue(
                    IssueLevel.INFO,
                    IssueReason.FILE_ERROR,
                    f"config file not found: {self.config_path}",
                )
            ]
        return list(self.config.issues)

    def _scan_src(self):
        """The files directly in src/ (not hidden ones, not directories) as the three
        lists of src_files, each sorted, and the issues of src/ itself."""
        try:
            with os.scandir(self.src_path) as entries:
                names = sorted(
                    e.name for e in entries if e.is_file() and not e.name.startswith(".")
                )
        except OSError as e:
            return (
                new_state().src_files,
                [
                    self._issue(
                        IssueLevel.WARNING,
                        IssueReason.FILE_ERROR,
                        f"cannot read the source directory {self.src_path}: {e}",
                    )
                ],
            )
        db = [n for n in names if n.endswith(settings.DB_FILE_SUFFIXES)]
        protocol = [n for n in names if n.endswith(settings.PROTOCOL_FILE_SUFFIXES)]
        other = [n for n in names if n not in db and n not in protocol]
        return new_state().src_files.model_copy(
            update={"db_files": db, "protocol_files": protocol, "other_files": other}
        ), []

    def _check_repository(self):
        if not self.repository.exists():
            return [
                self._issue(
                    IssueLevel.WARNING,
                    IssueReason.FILE_ERROR,
                    f"no git repository in {self.dir_path}, its history is not kept",
                )
            ]
        try:
            head = self.repository.head()
            if head is None:  # nothing has been committed, so there is nothing to differ from
                return []
            status = self.repository.status()
        except IocRepositoryError as e:
            return [
                self._issue(
                    IssueLevel.ERROR,
                    IssueReason.FILE_ERROR,
                    f"cannot read the history of {self.dir_path}: {e}",
                )
            ]
        return [
            self._issue(
                IssueLevel.WARNING,
                IssueReason.FILE_CHANGED,
                f"{path}: {kind} since the snapshot {head[:8]}",
            )
            for kind in ("modified", "added", "deleted")
            for path in status[kind]
        ]

    def _replace_issues(self, found):
        """Make `found` the refreshed issues of the IOC, and leave the others alone.
        Run inside a transaction."""
        old = self.state_manager.read_issues(self.name)
        ours = [i for i in old if i.reason in _REFRESHED_REASONS]
        first_seen = {(i.level, i.reason, i.message): i.time for i in ours}
        found = [
            i.model_copy(update={"time": first_seen.get((i.level, i.reason, i.message), i.time)})
            for i in found
        ]
        if [(i.level, i.reason, i.message) for i in ours] == [
            (i.level, i.reason, i.message) for i in found
        ]:
            return
        kept = [i for i in old if i.reason not in _REFRESHED_REASONS]
        self.state_manager.write_issues(self.name, kept + found)

    @staticmethod
    def _issue(level, reason, message):
        return IssueEntry(level=level, reason=reason, message=message, prompt="", time=get_now_str())

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
        an OPERATION_SUCCESS issue saying it was created. The config and the source files are
        added afterwards. When a step fails what this call made is removed again and
        IocInitError is raised.

        The whole job is done inside one write transaction of the database, from
        looking at what is there to the commit. Another process that wants to write
        about this IOC, for instance by opening it while only the directory is there,
        waits for it to end and then finds the complete IOC.

        A name that is not valid raises ValueError. A name that is taken raises
        IocExistsError, and nothing is touched: a complete IOC always, and one that
        has only half of itself unless `force` is given:
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
                    presence = cls.check_presence(name)
                    if presence == "complete" or (presence != "missing" and not force):
                        raise IocExistsError(
                            _PRESENCE_MESSAGES[presence].format(name=name, path=dir_path)
                        )
                    os.makedirs(settings.IOCS_DIR, exist_ok=True)
                    if presence != "unregistered":
                        try:
                            os.mkdir(dir_path)  # fails if there is one, whoever made it
                        except FileExistsError:
                            raise IocExistsError(
                                _PRESENCE_MESSAGES["unregistered"].format(name=name, path=dir_path)
                            ) from None
                        made.append(dir_path)
                    if not os.path.isdir(src_path):
                        os.makedirs(src_path)
                        made.append(src_path)
                    repository = IocRepository(dir_path)
                    if not repository.exists():
                        repository.init()
                        made.append(os.path.join(dir_path, ".git"))
                    state_manager.write_ioc(name, new_state().model_dump(exclude={"issues"}))
                    state_manager.write_issues(
                        name,
                        [
                            cls._issue(
                                IssueLevel.INFO,
                                IssueReason.OPERATION_SUCCESS,
                                "created"
                                if presence != "unregistered"
                                else "created on the existing directory",
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
            "unregistered"  a directory, but no record in the database"""
        check_name(name)
        registered = get_state_manager().exists(name)
        has_dir = os.path.isdir(cls._dir_of(name))
        if registered:
            return "complete" if has_dir else "no_directory"
        return "unregistered" if has_dir else "missing"

    @staticmethod
    def _dir_of(name):
        return os.path.join(settings.IOCS_DIR, name)
