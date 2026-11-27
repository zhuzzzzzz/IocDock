class IocNotFoundError(Exception):
    pass


class IocInitError(Exception):
    pass


class VersionedDirectoryError(Exception):
    pass


class GitUnavailableError(VersionedDirectoryError):
    """git could not be run: it is not installed, or the directory to run it in is not
    there. Nothing is known about the repository then, and it is not known to be broken."""


class GitTimeoutError(VersionedDirectoryError):
    """A git command took longer than it was given, and was stopped. Nothing is known
    about the repository then, and it is not known to be broken."""


class UncommittedChangesError(VersionedDirectoryError):
    """The directory has changes that were not committed, and what was asked would
    throw them away. `changes` is what VersionedDirectory.status() says about them."""

    def __init__(self, message, changes):
        super().__init__(message)
        self.changes = changes


class IocExistsError(Exception):
    pass
