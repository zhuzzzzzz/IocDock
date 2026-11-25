import os
import re
import subprocess

from core.exceptions import IocRepositoryError

_COMMIT_ID = re.compile(r"[0-9a-f]{4,64}")


class IocRepository:
    """The version history of the directory of one IOC (its config file and its
    source files), kept by git in the .git directory inside it.

    git is run on exactly this directory and never looks for a repository above it.
    The user's own git configuration is not read, so a global hook, signing or
    line-ending setting cannot change what happens here. A failing git command
    raises IocRepositoryError with what git printed."""

    def __init__(self, path, timeout=10):
        self.path = os.path.abspath(path)
        self.timeout = timeout

    def is_initialized(self):
        """Whether the directory has been made a repository (init()): there is a .git
        in it. It is not looked into, whether it works is another matter."""
        return os.path.isdir(os.path.join(self.path, ".git"))

    def init(self, ignore=()):
        """Make the directory a repository. `ignore` are .gitignore patterns for
        what is not to be tracked (build output, ...). Nothing is committed yet.
        A directory that already is a repository raises FileExistsError."""
        if not os.path.isdir(self.path):
            raise FileNotFoundError(self.path)
        if self.is_initialized():
            raise FileExistsError(os.path.join(self.path, ".git"))
        self._git("init", "--quiet", "--initial-branch=main", ".")
        if ignore:
            with open(os.path.join(self.path, ".gitignore"), "w", encoding="utf-8") as f:
                f.write("".join(f"{pattern}\n" for pattern in ignore))

    def head(self):
        """The id of the latest commit, or None when there is none yet."""
        result = self._git("rev-parse", "--verify", "--quiet", "HEAD", check=False)
        if result.returncode not in (0, 1):  # 1 is "there is no such commit"
            raise IocRepositoryError(f"git rev-parse failed in {self.path}: {result.stderr.strip()}")
        return result.stdout.strip() or None

    def commit(self, message):
        """Record the directory as it is now and return the id of that commit. When
        nothing changed since the latest commit no commit is made and its id is
        returned. The first commit is made even when the directory is empty."""
        self._git("add", "--all")
        head = self.head()
        if head is not None and self._git("diff", "--cached", "--quiet", check=False).returncode == 0:
            return head
        args = ["commit", "--quiet", "--no-verify", "-m", message]
        if head is None:
            args.append("--allow-empty")
        self._git(*args)
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

    def restore(self, commit):
        """Make the directory what it was at `commit`: changed files are put back,
        deleted ones come back, files added since are removed (ignored ones stay).
        The history is kept: the result is recorded as a new commit, whose id is
        returned, or the id of the latest commit when nothing had to change."""
        if not _COMMIT_ID.fullmatch(commit):
            raise ValueError(f"not a commit id: {commit!r}")
        full = self._git("rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}", check=False)
        if full.returncode != 0:
            raise IocRepositoryError(f"no such commit in {self.path}: {commit}")
        self._git("read-tree", "--reset", "-u", full.stdout.strip())
        self._git("clean", "--force", "-d")
        return self.commit(f"restore {commit[:8]}")

    def _git(self, *args, check=True):
        git_dir = os.path.join(self.path, ".git")
        # --git-dir and --work-tree stop git from using a repository above this directory
        command = [
            "git",
            f"--git-dir={git_dir}",
            f"--work-tree={self.path}",
            # looking (status) must not take locks nobody asked for: it runs all the
            # time, and a person's add or commit may be in the middle of its own
            "--no-optional-locks",
            "-c", "user.name=IocDock",
            "-c", "user.email=iocdock@localhost",
            "-c", "core.quotepath=off",
            "-c", f"safe.directory={self.path}",
            *args,
        ]
        env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
        try:
            result = subprocess.run(
                command,
                cwd=self.path,
                env=env,
                capture_output=True,
                timeout=self.timeout,
            )
        except FileNotFoundError as e:
            raise IocRepositoryError(f"git is not installed or not in PATH ({e})") from e
        except subprocess.TimeoutExpired as e:
            raise IocRepositoryError(f"git {args[0]} took longer than {self.timeout}s in {self.path}") from e
        # A path git prints is the bytes of a name somebody gave a file, which need not
        # be UTF-8. They stay in stdout the way os.listdir() gives them (the bytes that
        # are not UTF-8 are lone surrogates, which the os functions turn back into those
        # bytes), so that the caller can tell. A message is made to be text that can
        # be stored.
        stdout = result.stdout.decode("utf-8", "surrogateescape")
        stderr = result.stderr.decode("utf-8", "replace")
        if check and result.returncode != 0:
            printed = stdout.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
            raise IocRepositoryError(
                f"git {args[0]} failed in {self.path}: {stderr.strip() or printed.strip()}"
            )
        return subprocess.CompletedProcess(command, result.returncode, stdout, stderr)
