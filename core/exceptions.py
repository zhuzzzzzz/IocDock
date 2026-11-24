"""The exceptions IocDock raises on its own. Errors that Python or a library
already has a class for (FileNotFoundError, TimeoutError, ...) are not
repeated here."""


class IocNotFoundError(Exception):
    """An IOC that has no record in the state database."""
