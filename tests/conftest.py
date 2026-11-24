"""Shared pytest fixtures. The layout under tests/ mirrors the source tree:
core/utils.py -> tests/core/test_utils.py."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from core import settings
from core.ioc_config import IocConfig
from core.ioc_state import IocStateManager, get_state_manager
from tests.logutil import log

# The tests never touch /opt/IocDockHome. Everything they keep on disk for core.ioc
# lives in .test-tmp/ of the repository and is removed when the run ends.
TEST_TMP = Path(__file__).resolve().parents[1] / ".test-tmp"
TEST_TMP.mkdir(exist_ok=True)
_RUN_DIR = tempfile.mkdtemp(prefix="run-", dir=TEST_TMP)

# the first IOC opens the state database, so a database has to be there first.
settings.DEFAULT_DB_PATH = os.path.join(_RUN_DIR, "ioc-state.db")
IocStateManager.initialize()

settings.IOCS_DIR = os.path.join(_RUN_DIR, "iocs")


def pytest_unconfigure(config):
    """Close the shared state and delete the temporary files."""
    get_state_manager().close()
    shutil.rmtree(_RUN_DIR, ignore_errors=True)
    try:
        TEST_TMP.rmdir()  # only when no other run is using it
    except OSError:
        pass


def _title(item):
    """What the test is about: the first line of its docstring, else its name."""
    doc = (item.function.__doc__ or "").strip()
    title = doc.splitlines()[0] if doc else item.name.removeprefix("test_").replace("_", " ")
    callspec = getattr(item, "callspec", None)
    return f"{title}  [{callspec.id}]" if callspec else title


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """Print what each test is about when it starts and how it ended."""
    log.info("▶ %s", _title(item))
    outcome = yield
    if outcome.excinfo is None:
        log.info("  ✔ passed")
    else:
        log.error("  ✘ FAILED: %s", outcome.excinfo[1])


@pytest.fixture
def shared():
    """The shared state manager, with no IOC left in it after the test."""
    manager = get_state_manager()
    yield manager
    for name in manager.list_iocs():
        manager.delete_ioc(name)


@pytest.fixture
def make_conf(tmp_path):
    """Create a project directory holding a generated ioc.yaml; return its IocConfig.

    The config name follows the directory name, so a fresh one loads without issues.
    """

    def factory(name="ioc-demo"):
        path = tmp_path / name / "ioc.yaml"
        path.parent.mkdir(parents=True)
        IocConfig.create_template(str(path), None)
        return IocConfig(str(path))

    return factory

