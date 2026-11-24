"""What the tests of more than one file need."""

from pathlib import Path

from core.ioc_schema import IssueEntry, IssueLevel, IssueReason, new_state
from core.ioc_state import IocStateManager
from core.utils import get_now_str

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_issue(message="m", level=IssueLevel.WARNING):
    return IssueEntry(
        level=level,
        reason=IssueReason.VALIDATION_ERROR,
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
