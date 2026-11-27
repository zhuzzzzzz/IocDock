import fcntl
import os
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime
from enum import StrEnum

from core.exceptions import (
    GitTimeoutError,
    GitUnavailableError,
    UncommittedChangesError,
    VersionedDirectoryError,
)

_COMMIT_ID = re.compile(r"[0-9a-f]{4,64}")

# the git commands that take the lock on the index (.git/index.lock)
_INDEX_WRITERS = ("add", "commit", "checkout", "read-tree")

# How many of the newest commits history() and show_history() give when they are not
# told how many (limit=None)
DEFAULT_HISTORY_LIMIT = 100


class DirectoryState(StrEnum):
    """How a directory stands as a repository, see VersionedDirectory.check()."""

    NO_REPOSITORY = "no_repository"  # there is no .git in it
    UNREADABLE = "unreadable"  # there is, but git cannot read it
    NO_COMMIT = "no_commit"  # a repository that has not recorded anything yet
    OK = "ok"  # it has a latest commit, and what differs from it is known


class VersionedDirectory:
    """The version history of one directory (an IOC's config file and source files, for
    one), kept by git in the .git directory inside it. It is deliberately narrow: local
    only, one branch (main), always the same author. It is not a general wrapper of git.

    git is run on exactly this directory and never looks for a repository above it.
    The user's own git configuration is not read, so a global hook, signing,
    line-ending or ignore setting cannot change what happens here, and neither can a GIT_*
    variable in the environment of the process. A failing git command
    raises VersionedDirectoryError with what git printed.

    commit(), restore() and restore_file() change the history, and they wait for each
    other, in threads and in processes, with a lock in the .git directory: two of them
    at the same time are done one after the other, not one of them failed. What only
    looks (head(), history(), status(), diff(), ...) takes no lock and is never kept
    waiting. repair() is for a repository that cannot be read, and takes none.

    A git command that only looks gets `timeout` seconds. One that writes (add, commit,
    ...) gets `write_timeout`, which is also how long a write waits for the lock. A git
    that is killed for taking longer leaves .git/index.lock behind, and no commit could
    be made after that: the lock is removed again."""

    def __init__(self, path, timeout=10, write_timeout=60):
        self.path = os.path.abspath(path)
        self.timeout = timeout
        self.write_timeout = write_timeout

    def is_initialized(self):
        """Whether the directory has been made a repository (init()): there is a .git
        in it. It is not looked into, whether it works is another matter."""
        return os.path.isdir(os.path.join(self.path, ".git"))

    def init(self, ignore=()):
        """Make the directory a repository. `ignore` are .gitignore patterns for
        what is not to be tracked (build output, ...), and they replace the .gitignore
        the directory already has. Nothing is committed yet. A directory that already
        is a repository raises FileExistsError.

        Names like .git.broken-* are never recorded: repair() renames a .git that is
        broken to one, and it is a repository of its own, not part of this one."""
        if not os.path.isdir(self.path):
            raise FileNotFoundError(self.path)
        if self.is_initialized():
            raise FileExistsError(os.path.join(self.path, ".git"))
        self._git("init", "--quiet", "--initial-branch=main", ".")
        # written here, not in repair(): a repository made again by hand needs it too
        exclude = os.path.join(self.path, ".git", "info", "exclude")
        os.makedirs(os.path.dirname(exclude), exist_ok=True)
        with open(exclude, "a", encoding="utf-8") as f:
            f.write("\n.git.broken-*\n")
        if ignore:
            with open(os.path.join(self.path, ".gitignore"), "w", encoding="utf-8") as f:
                f.write("".join(f"{pattern}\n" for pattern in ignore))

    def head(self):
        """The id of the latest commit, or None when there is none yet."""
        result = self._git("rev-parse", "--verify", "--quiet", "HEAD", check=False)
        if result.returncode not in (0, 1):  # 1 is "there is no such commit"
            raise VersionedDirectoryError(f"git rev-parse failed in {self.path}: {result.stderr.strip()}")
        return result.stdout.strip() or None

    def history(self, limit=None):
        """The commits made so far, newest first, as a list of {"id": the full commit id,
        "time": when it was made as a datetime in local time, to the second, "message":
        the first line of its message}. The list is empty when there is no commit yet.

        Only the newest `limit` are given: that many for a whole number of 1 or more,
        DEFAULT_HISTORY_LIMIT for None (not passed). Anything else raises ValueError.
        The list does not say whether older commits were left out."""
        limit = self._limit_of(limit)
        if self.head() is None:  # git log fails when there is nothing to show
            return []
        out = self._git("log", "--format=%H %ct %s", f"--max-count={limit}").stdout
        logs = []
        # split on "\n" only: str.splitlines() would also cut a message at characters
        # like U+2028
        for line in out.split("\n"):
            if not line:
                continue
            commit_id, timestamp, message = line.split(" ", 2)
            logs.append(
                {
                    "id": commit_id,
                    "time": datetime.fromtimestamp(int(timestamp)),
                    # a message is made to be text that can be stored (see _git())
                    "message": message.encode("utf-8", "surrogateescape").decode("utf-8", "replace"),
                }
            )
        return logs

    def show_history(self, limit=None):
        """Print history() to the terminal, one commit a line: its time, the first 8
        characters of its id (enough for restore()) and its message. Says so when there
        is no commit yet, and, with a last line, when older commits than the `limit`
        newest were left out (`limit` is as for history())."""
        limit = self._limit_of(limit)
        commits = self.history(limit + 1)  # one more than will be shown: are there older ones?
        if not commits:
            print("No commits yet.")
            return
        for entry in commits[:limit]:
            print(f"{entry['time']:%Y-%m-%d %H:%M:%S}  {entry['id'][:8]}  {entry['message']}")
        if len(commits) > limit:
            print(f"... older commits not shown (the newest {limit} are listed)")

    @staticmethod
    def _limit_of(limit):
        """How many commits history() gives for `limit`: DEFAULT_HISTORY_LIMIT for None,
        else `limit`, which must be a whole number of 1 or more or ValueError is raised."""
        if limit is None:
            return DEFAULT_HISTORY_LIMIT
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError(f"limit is a whole number of 1 or more, or None, got {limit!r}")
        return limit

    def commit(self, message):
        """Record the directory as it is now and return the id of that commit. When
        nothing changed since the latest commit no commit is made and its id is
        returned. The first commit is made even when the directory is empty. A message
        that is not text, or has nothing but white space in it, raises ValueError, before
        anything is done and whether something changed or not."""
        if not isinstance(message, str) or not message.strip():
            raise ValueError(f"a commit needs a message that is not empty, got {message!r}")
        with self._writing():
            return self._commit(message)

    def _commit(self, message):
        """commit() without the lock, for what holds it already (restore())."""
        self._git("add", "--all", timeout=self.write_timeout)
        head = self.head()
        if head is not None and self._git("diff", "--cached", "--quiet", check=False).returncode == 0:
            return head
        args = ["commit", "--quiet", "--no-verify", "-m", message]
        if head is None:
            args.append("--allow-empty")
        self._git(*args, timeout=self.write_timeout)
        return self.head()

    def status(self):
        """What differs from the latest commit, as {"modified": [...], "added": [...],
        "deleted": [...]}: paths relative to the directory, sorted. Files matched by
        .gitignore are not looked at. A rename shows up as a delete and an add. A name
        that is not valid UTF-8 comes back as os.listdir() gives it (see _git())."""
        out = self._git(
            "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all"
        ).stdout
        changes = {"modified": [], "added": [], "deleted": []}
        for entry in out.split("\0"):
            if not entry:
                continue
            code, path = entry[:2], entry[3:]
            if code == "??" or "A" in code:
                changes["added"].append(path)
            elif "D" in code:
                changes["deleted"].append(path)
            else:
                changes["modified"].append(path)
        return {kind: sorted(paths) for kind, paths in changes.items()}

    def is_clean(self):
        return not any(self.status().values())

    def check(self):
        """How the directory stands, for a check that is run over and over, as
          {"state": a DirectoryState,
           "head": the id of the latest commit, None when there is none,
           "changes": what status() says, with nothing in it when it could not be asked,
           "error": what went wrong when the state is UNREADABLE, "" otherwise}.
        A repository that git cannot read is an answer, not an error: nothing is raised.
        NO_COMMIT has its changes too (every file is an addition then), what is made of
        that is for the caller to say. A commit may be made between looking at the latest
        commit and at the changes; they are asked again, a few times, until the latest
        commit is the same before and after, so that they are about the same commit."""
        if not self.is_initialized():
            return self._report(DirectoryState.NO_REPOSITORY)
        try:
            head, changes = self._read_state()
        except VersionedDirectoryError as e:
            return self._report(DirectoryState.UNREADABLE, error=str(e))
        state = DirectoryState.OK if head is not None else DirectoryState.NO_COMMIT
        return self._report(state, head=head, changes=changes)

    def _read_state(self):
        """(the latest commit, what differs from it) as check() reports them: asked
        again, a few times, until the latest commit is the same before and after.
        Raises VersionedDirectoryError when git cannot read the repository, and also
        when it knows of no commit but the log of HEAD (.git/logs/HEAD, which a new
        repository does not have) remembers some: the branch is lost, and to look as if
        the repository were new would be wrong. GitUnavailableError and GitTimeoutError
        say that git could not tell, which is something else than damage."""
        for _ in range(3):
            head = self.head()
            changes = self.status()
            if self.head() == head:
                break
        if head is None:
            remembered = self._last_logged_commit()
            if remembered is not None:
                raise VersionedDirectoryError(
                    f"{self.path}: main points to no commit, but the log of HEAD remembers "
                    f"commits (the newest that is still there: {remembered[:8]}): "
                    "repair() points main there again"
                )
        return head, changes

    def _last_logged_commit(self):
        """The newest commit that the log of HEAD (.git/logs/HEAD) names and that is
        still in the repository, or None: a repository that never had a commit has no
        such log. Only the last 50 entries are looked at."""
        try:
            with open(os.path.join(self.path, ".git", "logs", "HEAD"), "rb") as f:
                lines = f.read().decode("utf-8", "replace").split("\n")
        except OSError:
            return None
        for line in reversed([line for line in lines if line.strip()][-50:]):
            fields = line.split(" ", 2)  # <old id> <new id> <who and when>	<what>
            if len(fields) < 2 or not _COMMIT_ID.fullmatch(fields[1]):
                continue
            if self._git("cat-file", "-e", f"{fields[1]}^{{commit}}", check=False).returncode == 0:
                return fields[1]
        return None

    @staticmethod
    def _report(state, head=None, changes=None, error=""):
        if changes is None:
            changes = {"modified": [], "added": [], "deleted": []}
        return {"state": state, "head": head, "changes": changes, "error": error}

    def show_status(self):
        """Print status() to the terminal, one changed file a line: what happened to it
        and its path (a name that is not valid UTF-8 is shown as \\xNN). Says so when
        nothing differs."""
        changes = self.status()
        if not any(changes.values()):
            print("No changes.")
            return
        for kind in ("modified", "added", "deleted"):
            for path in changes[kind]:
                shown = path.encode("utf-8", "surrogateescape").decode("utf-8", "backslashreplace")
                print(f"{kind:<8}  {shown}")

    def changed_files(self, commit):
        """What the commit `commit` changed, as status() tells it: {"modified": [...],
        "added": [...], "deleted": [...]}, sorted, against the commit before it. The
        first commit has nothing before it, so all its files are added. `commit` is
        written as for restore(), and raises the same errors."""
        full = self._resolve(commit)
        out = self._git(
            "diff-tree", "--root", "--no-commit-id", "--name-status", "-r", "--no-renames", "-z", full
        ).stdout
        tokens = out.split("\0")  # a letter, then the path, each ended by a NUL
        changes = {"modified": [], "added": [], "deleted": []}
        for code, path in zip(tokens[0::2], tokens[1::2]):
            kind = "added" if code == "A" else "deleted" if code == "D" else "modified"
            changes[kind].append(path)
        return {kind: sorted(paths) for kind, paths in changes.items()}

    def diff(self, commit=None, max_bytes=1_000_000):
        """What changed, as the text of a unified diff, for a person to read.
        Without `commit`: the files of the directory against the latest commit. A file
        that is new has nothing in it, git does not know it yet, status() names it; and
        there is nothing at all before the first commit. With `commit`: what that
        commit changed (see changed_files()). A file that is not text only says that it
        differs.

        A diff that is longer than `max_bytes` (None: no limit) is cut at the end of a
        line, and a last line says how much was left out. A byte that is not valid
        UTF-8 is replaced. ValueError for a `max_bytes` that is not a whole number of 1
        or more."""
        if max_bytes is not None and (
            isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1
        ):
            raise ValueError(f"max_bytes is a whole number of 1 or more, or None, got {max_bytes!r}")
        options = ["--no-renames", "--no-ext-diff", "--no-textconv", "--no-color"]
        if commit is None:
            if self.head() is None:
                return ""
            out = self._git("diff", *options, "HEAD").stdout
        else:
            full = self._resolve(commit)
            out = self._git("diff-tree", "-p", "--root", "--no-commit-id", *options, full).stdout
        text = out.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
        data = text.encode("utf-8")
        if max_bytes is None or len(data) <= max_bytes:
            return text
        cut = data[:max_bytes]
        newline = cut.rfind(b"\n")
        if newline != -1:
            cut = cut[: newline + 1]
        shown = cut.decode("utf-8", "ignore")  # ignore: a character cut in the middle
        if shown and not shown.endswith("\n"):
            shown += "\n"
        return shown + f"... diff cut at {len(cut)} bytes of {len(data)}: raise max_bytes to see more\n"

    def read_file(self, commit, path):
        """The content of the file `path` as it was at `commit`, as bytes (a database
        file need not be text). `path` is relative to the directory, and not outside it
        or in .git, or ValueError is raised. A file that was not there at `commit`, or
        a directory, raises VersionedDirectoryError. `commit` is written as for
        restore()."""
        full = self._resolve(commit)
        name = self._relative(path)
        result = self._git("cat-file", "blob", f"{full}:{name}", check=False)
        if result.returncode != 0:
            raise VersionedDirectoryError(f"{name} is not a file in commit {full[:8]} of {self.path}")
        # the bytes git printed come back as they were (see _git())
        return result.stdout.encode("utf-8", "surrogateescape")

    def verify(self, timeout=60):
        """Look for damage in the repository itself, as git fsck does (the stored
        commits and what they refer to, not the files of the directory), and return
        what it found as a list of lines, empty when the repository is sound. It reads
        everything, so with a long history it is slow: it gets `timeout` seconds
        instead of self.timeout, and it is not for every check(). A directory without a
        .git raises VersionedDirectoryError; a .git that git cannot read is found
        damaged."""
        if not self.is_initialized():
            raise VersionedDirectoryError(f"there is no repository in {self.path}")
        result = self._git("fsck", "--no-dangling", "--no-progress", check=False, timeout=timeout)
        if result.returncode == 0:
            return []
        text = (result.stderr + "\n" + result.stdout).encode("utf-8", "surrogateescape")
        lines = [line for line in text.decode("utf-8", "replace").split("\n") if line.strip()]
        return lines or [f"git fsck failed with exit code {result.returncode}"]

    def restore(self, commit, force=False):
        """Make the directory what it was at `commit`: changed files are put back,
        deleted ones come back, files added since are removed (ignored ones stay).
        The history is kept: the result is recorded as a new commit, whose id is
        returned, or the id of the latest commit when nothing had to change.

        Changes that were not committed (see status()) would be lost with that, so
        when there are any UncommittedChangesError is raised and nothing is touched.
        With force=True they are thrown away. restore(head(), force=True) throws away
        the uncommitted changes and does nothing else.

        When it fails halfway (a timeout, ...) the directory is left half restored,
        which differs from the latest commit: do it again, with force=True."""
        full = self._resolve(commit)
        with self._writing():
            if not force:
                changes = self.status()
                if any(changes.values()):
                    raise UncommittedChangesError(self._uncommitted_message(changes), changes)
            self._git("read-tree", "--reset", "-u", full, timeout=self.write_timeout)
            self._git("clean", "--force", "-d", timeout=self.write_timeout)
            return self._commit(f"restore {full[:8]}")

    def restore_file(self, commit, path, force=False):
        """Make the file `path` what it was at `commit`, and nothing else: the other
        files, changed or not, stay as they are. The result is recorded as a new commit
        of that file alone, whose id is returned, or the id of the latest commit when
        the file was like that already. `path` and `commit` are written as for
        read_file(). A file that was not there at `commit`, or a directory, raises
        VersionedDirectoryError: deleting is not what this is for.

        Changes to the file that were not committed would be lost, so when it has any
        (it is modified, or it is a new file) UncommittedChangesError is raised, with
        only this file in `changes`, and nothing is touched. With force=True they are
        thrown away. A file that was deleted comes back without force, there is
        nothing in it to lose."""
        full = self._resolve(commit)
        name = self._relative(path)
        kind = self._git("cat-file", "-t", f"{full}:{name}", check=False)
        if kind.returncode != 0 or kind.stdout.strip() != "blob":
            raise VersionedDirectoryError(f"{name} is not a file in commit {full[:8]} of {self.path}")
        with self._writing():
            if not force:
                status = self.status()
                changes = {
                    "modified": [p for p in status["modified"] if p == name],
                    "added": [p for p in status["added"] if p == name],
                    "deleted": [],
                }
                if changes["modified"] or changes["added"]:
                    raise UncommittedChangesError(self._uncommitted_message(changes), changes)
            # into the directory and into the index
            self._git("checkout", full, "--", name, timeout=self.write_timeout)
            if self._git("diff", "--cached", "--quiet", "--", name, check=False).returncode == 0:
                return self.head()  # it was like that already
            self._git(
                "commit", "--quiet", "--no-verify", "-m", f"restore {name} from {full[:8]}",
                "--only", "--", name,
                timeout=self.write_timeout,
            )
            return self.head()

    def repair(self):
        """Get a repository that git says it cannot read (check() says UNREADABLE) to work
        again, and return {"restarted": bool, "moved_to": path or None, "commit": id}.

        If the damage is in the pointers only, it is mended and the history is kept:
        HEAD is made to point to main again, and main to the newest commit that the log
        of HEAD (.git/logs/HEAD) names and that is still in the repository. Then it
        returns {"restarted": False, "moved_to": None, "commit": that commit}. Commits
        newer than that, whose objects are lost, are lost: the repository goes on from
        the newest one that is whole. Whether the rest of the history is sound is for
        verify() to say.

        If that does not make it work, the history starts again, and it returns
        {"restarted": True, "moved_to": where the old .git is now, "commit": the id of
        the first commit of the new history}. The old .git is not deleted: it is renamed
        to .git.broken-<date>-<time>, in the directory, and git is told to leave such
        names alone (init() does that). The directory gets a new repository (as init()
        makes it) and the files in it, as they are now, are recorded as its first
        commit. The old history is not part of the new one: it is not in history() and
        cannot be restored, only taken out of the renamed directory by hand. If making
        the new repository fails, what was done is undone: the old .git is back.

        Only a repository that git itself says it cannot read is touched. When git could
        not be run, or took too long, nothing is known about the repository:
        GitUnavailableError or GitTimeoutError is raised, and nothing is changed. So it
        is when the repository works, or there is none (init() makes one): a
        VersionedDirectoryError, and nothing is changed. It takes no lock, and is for one
        person at a time."""
        if not self.is_initialized():
            raise VersionedDirectoryError(f"there is no repository in {self.path} to repair, init() makes one")
        try:
            head, _ = self._read_state()
        except (GitUnavailableError, GitTimeoutError):
            raise  # git could not tell: it is not known to be broken
        except VersionedDirectoryError:
            pass  # git says it is
        else:
            state = DirectoryState.OK if head is not None else DirectoryState.NO_COMMIT
            raise VersionedDirectoryError(f"the repository in {self.path} is not broken ({state}), there is nothing to repair")
        mended = self._mend_pointers()
        if mended is not None:
            return {"restarted": False, "moved_to": None, "commit": mended}
        git_dir = os.path.join(self.path, ".git")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        moved = f"{git_dir}.broken-{stamp}"
        number = 1
        while os.path.exists(moved):
            number += 1
            moved = f"{git_dir}.broken-{stamp}-{number}"
        try:
            os.rename(git_dir, moved)
        except OSError as e:
            raise VersionedDirectoryError(f"cannot move {git_dir} aside: {e}") from e
        try:
            self.init()
            commit = self._commit(
                f"repair: the history starts again, the old one is in {os.path.basename(moved)}"
            )
        except BaseException:
            shutil.rmtree(git_dir, ignore_errors=True)  # whatever there is of the new one
            try:
                os.rename(moved, git_dir)
            except OSError as e:
                raise VersionedDirectoryError(
                    f"the repair failed, and the old .git could not be put back, it is {moved}: {e}"
                ) from e
            raise
        return {"restarted": True, "moved_to": moved, "commit": commit}

    def _mend_pointers(self):
        """Make HEAD point to main, and main to the newest commit the log of HEAD names
        that is still there (see repair()), and return that commit; or, when that does not
        make the repository work, put HEAD back as it was and return None."""
        head_file = os.path.join(self.path, ".git", "HEAD")
        try:
            with open(head_file, "rb") as f:
                before = f.read()
        except OSError:
            before = None
        mended = None
        try:
            with open(head_file, "wb") as f:
                f.write(b"ref: refs/heads/main\n")
            mended = self._latest_commit_if_sound()
            if mended is None:
                remembered = self._last_logged_commit()
                if remembered is not None:
                    self._git("update-ref", "refs/heads/main", remembered)
                    mended = self._latest_commit_if_sound()
        except (GitUnavailableError, GitTimeoutError):
            self._put_back(head_file, before)
            raise
        except (OSError, VersionedDirectoryError):
            mended = None
        if mended is None:
            self._put_back(head_file, before)
        return mended

    def _latest_commit_if_sound(self):
        """The latest commit when the repository can be read and has one, else None.
        GitUnavailableError and GitTimeoutError are raised as they are."""
        try:
            head, _ = self._read_state()
        except (GitUnavailableError, GitTimeoutError):
            raise
        except VersionedDirectoryError:
            return None
        return head

    @staticmethod
    def _put_back(path, content):
        try:
            if content is None:
                os.remove(path)
            else:
                with open(path, "wb") as f:
                    f.write(content)
        except OSError:
            pass

    def _resolve(self, commit):
        """The full id of the commit that `commit`, a full or shortened id, names.
        ValueError when it is not written like an id (a branch name, an option, ...
        are not accepted), VersionedDirectoryError when there is no such commit."""
        if not isinstance(commit, str) or not _COMMIT_ID.fullmatch(commit):
            raise ValueError(f"not a commit id: {commit!r}")
        full = self._git("rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}", check=False)
        if full.returncode != 0:
            raise VersionedDirectoryError(f"no such commit in {self.path}: {commit}")
        return full.stdout.strip()

    @staticmethod
    def _relative(path):
        """`path`, a file of the directory, tidied up (./a/../b is b). It must be relative
        to the directory, not outside it and not in .git, or ValueError is raised."""
        if not isinstance(path, str) or not path or "\0" in path:
            raise ValueError(f"not a path in the directory: {path!r}")
        name = os.path.normpath(path)
        if (
            os.path.isabs(name)
            or name in (".", "..", ".git")
            or name.startswith(("../", ".git/"))
        ):
            raise ValueError(f"not a path in the directory: {path!r}")
        return name

    def _uncommitted_message(self, changes):
        paths = [path for kind in ("modified", "added", "deleted") for path in changes[kind]]
        # a name that is not valid UTF-8 is shown as \xNN: a message is text that can be stored
        shown = ", ".join(
            path.encode("utf-8", "surrogateescape").decode("utf-8", "backslashreplace")
            for path in paths[:5]
        )
        if len(paths) > 5:
            shown += f", and {len(paths) - 5} more"
        return (
            f"{self.path} has changes that are not committed ({shown}): "
            "commit them first, or use force=True to throw them away"
        )

    @contextmanager
    def _writing(self):
        """Hold the lock of the directory while a write (commit(), restore()) is done.
        It is a flock on .git/iocdock.lock, which is let go when the file is closed,
        also when the process dies. It waits for it for at most `write_timeout` seconds:
        as long as what holds it may take. It keeps these methods apart, not a git that
        somebody runs by hand. A directory without a repository has nothing to lock: git
        is left to say so."""
        if not self.is_initialized():
            yield
            return
        lock_path = os.path.join(self.path, ".git", "iocdock.lock")
        try:
            lock = open(lock_path, "a")
        except OSError as e:
            raise VersionedDirectoryError(f"cannot open the lock {lock_path}: {e}") from e
        with lock:
            deadline = time.monotonic() + self.write_timeout
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise VersionedDirectoryError(
                            f"{self.path} is in use by another commit or restore "
                            f"(waited {self.write_timeout}s)"
                        ) from None
                    time.sleep(0.02)
                except OSError as e:
                    raise VersionedDirectoryError(f"cannot take the lock {lock_path}: {e}") from e
            yield

    def _git(self, *args, check=True, timeout=None):
        limit = self.timeout if timeout is None else timeout
        git_dir = os.path.join(self.path, ".git")
        # --git-dir and --work-tree stop git from using a repository above this directory
        command = [
            "git",
            f"--git-dir={git_dir}",
            f"--work-tree={self.path}",
            # looking (status) must not take locks nobody asked for: it runs all the
            # time, and a person's add or commit may be in the middle of its own
            "--no-optional-locks",
            "-c", "user.name=iocdock",
            "-c", "user.email=iocdock@localhost",
            "-c", "core.quotepath=off",
            # the user's global ignore and attributes files (~/.config/git/) are files of
            # their own that GIT_CONFIG_GLOBAL does not reach: what is tracked is to be
            # decided by the .gitignore of the directory alone
            "-c", f"core.excludesFile={os.devnull}",
            "-c", f"core.attributesFile={os.devnull}",
            "-c", f"safe.directory={self.path}",
            *args,
        ]
        # What git needs to run (PATH, TMPDIR, TZ, ...) is taken over from this process,
        # its GIT_* variables are not: GIT_AUTHOR_NAME, GIT_INDEX_FILE and the like
        # would change what git does here
        env = {
            **{name: value for name, value in os.environ.items() if not name.startswith("GIT_")},
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
        started = time.time()
        try:
            result = subprocess.run(
                command,
                cwd=self.path,
                env=env,
                capture_output=True,
                timeout=limit,
            )
        except FileNotFoundError as e:
            # also what is raised when the directory to run in is not there
            if not os.path.isdir(self.path):
                raise GitUnavailableError(f"no such directory: {self.path}") from e
            raise GitUnavailableError(f"git is not installed or not in PATH ({e})") from e
        except subprocess.TimeoutExpired as e:
            if args[0] in _INDEX_WRITERS:
                self._remove_stale_index_lock(started)
            raise GitTimeoutError(f"git {args[0]} took longer than {limit}s in {self.path}") from e
        # A path git prints is the bytes of a name somebody gave a file, which need not
        # be UTF-8. They stay in stdout the way os.listdir() gives them (the bytes that
        # are not UTF-8 are lone surrogates, which the os functions turn back into those
        # bytes), so that the caller can tell. A message is made to be text that can
        # be stored.
        stdout = result.stdout.decode("utf-8", "surrogateescape")
        stderr = result.stderr.decode("utf-8", "replace")
        if check and result.returncode != 0:
            printed = stdout.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
            raise VersionedDirectoryError(
                f"git {args[0]} failed in {self.path}: {stderr.strip() or printed.strip()}"
            )
        return subprocess.CompletedProcess(command, result.returncode, stdout, stderr)

    def _remove_stale_index_lock(self, started):
        """A git that was killed for taking too long (at `started` it was begun) leaves
        the lock it held on the index, .git/index.lock, behind, and no git can write the
        index after that. A lock that was made since it began (a second before, for file
        systems that keep time coarsely) is the killed git's, and is removed. Only called
        for the commands that take that lock, and a git that waits for nothing: if it
        ran that long it was holding it. A lock that is older is somebody else's."""
        lock = os.path.join(self.path, ".git", "index.lock")
        try:
            if os.stat(lock).st_mtime >= started - 1:
                os.remove(lock)
        except OSError:
            pass  # there is none, or it cannot be removed: nothing more to do
