"""What the tests of more than one file need."""

from pathlib import Path

from core.ioc_schema import IssueCategory, IssueEntry, IssueLevel, IssueReason, new_state
from core.ioc_state import IocStateManager
from core.utils import get_now_str

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_issue(message="m", level=IssueLevel.WARNING, time=None):
    """A state issue"""
    return IssueEntry(
        level=level,
        reason=IssueReason.VALIDATION_ERROR,
        category=IssueCategory.STATE,
        message=message,
        prompt="",
        time=time or get_now_str(),
    )


def make_operation(message="op", success=True):
    """The record of an operation"""
    return IssueEntry(
        level=IssueLevel.INFO if success else IssueLevel.ERROR,
        reason=IssueReason.OPERATION_SUCCESS if success else IssueReason.OPERATION_FAILED,
        category=IssueCategory.OPERATION,
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
