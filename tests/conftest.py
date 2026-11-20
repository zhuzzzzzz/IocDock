"""Shared pytest fixtures. The layout under tests/ mirrors the source tree:
core/utils.py -> tests/core/test_utils.py."""

import pytest

from core.ioc import IocConfig


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

