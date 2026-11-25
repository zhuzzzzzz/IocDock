"""What the tests of more than one file need."""

from pathlib import Path

from core.ioc_schema import IssueCode, IssueEntry, IssueLevel, IssueSource, new_state
from core.ioc_state import IocStateManager
from core.utils import get_now_str

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_issue(message="m", level=IssueLevel.WARNING, time=None, code=IssueCode.CONFIG_INVALID, target=""):
    """An issue of the self-check"""
    return IssueEntry(
        source=IssueSource.CHECK,
        level=level,
        code=code,
        target=target,
        message=message,
        prompt="",
        time=time or get_now_str(),
    )


def make_repair(message="repair"):
    """The record of something the system repaired by itself"""
    return IssueEntry(
        source=IssueSource.REPAIR,
        level=IssueLevel.WARNING,
        code=IssueCode.RECORD_RESET,
        target="",
        message=message,
        prompt="",
        time=get_now_str(),
    )


def make_operation(message="op", success=True, code=IssueCode.BUILD):
    """The record of an operation"""
    return IssueEntry(
        source=IssueSource.OPERATION,
        level=IssueLevel.INFO if success else IssueLevel.ERROR,
        code=code,
        target="",
        message=message,
        prompt="",
        time=get_now_str(),
    )


def opened(path, **kwargs):
    state = IocStateManager(path, **kwargs)
    state.connect()
    return state


def add_ioc(state, name, data=None):
    data = new_state() if data is None else data
    state.write_ioc(name, {f: getattr(data, f) for f in IocStateManager.ADAPTERS})
    state.write_issues(name, data.issues, append=True)
