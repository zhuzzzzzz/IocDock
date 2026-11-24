"""Readable terminal output for the tests. pytest prints what is logged here live
(see log_cli in pytest.ini), so a person can follow what each test did and what it
saw, instead of only getting a dot or PASSED.

    step("write snapshot=5")                  -> what the test does
    check("snapshot", st.read(...), "tracked")  -> compares, shows both sides
    with expect_error(ValueError, "empty name"):   -> an error that must happen
        ...
"""

import logging
from contextlib import contextmanager

import pytest

log = logging.getLogger("iocdock.test")


def step(message):
    """An action the test takes."""
    log.info("  · %s", message)


def note(label, value):
    """A value the test looked at, with nothing to compare it to."""
    log.info("    → %s: %s", label, _short(value))


def check(label, actual, expected):
    """Assert actual == expected, and show both sides in the log."""
    if actual == expected:
        log.info("    ✔ %s: %s", label, _short(actual))
    else:
        log.error(
            "    ✘ %s: got %s, expected %s", label, _short(actual), _short(expected)
        )
    assert actual == expected, f"{label}: got {actual!r}, expected {expected!r}"


def check_true(label, condition, detail=""):
    """Assert a condition, and show it in the log."""
    if condition:
        log.info("    ✔ %s%s", label, f": {_short(detail)}" if detail != "" else "")
    else:
        log.error("    ✘ %s%s", label, f": {_short(detail)}" if detail != "" else "")
    assert condition, label


@contextmanager
def expect_error(exc_type, why, match=None):
    """Like pytest.raises, and the error that came is shown in the log."""
    with pytest.raises(exc_type, match=match) as info:
        yield info
    log.info(
        "    ✔ %s → raises %s: %s",
        why,
        type(info.value).__name__,
        _short(str(info.value)),
    )


def _short(value, limit=110):
    # a string is shown as it is, on one line; anything else as its repr
    text = " ".join(value.split()) if isinstance(value, str) else repr(value)
    text = text or "''"  # an empty string must not look like nothing
    return text if len(text) <= limit else text[: limit - 1] + "…"
