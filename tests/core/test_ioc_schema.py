import pytest
from pydantic import ValidationError

from core.ioc_schema import (
    IocConfigSchema,
    IssueEntry,
    IssueLevel,
    IssueReason,
    _DbLoadItem,
    _Settings,
    new_config,
)
from core.utils import get_yaml_tool


def test_new_config_passes_its_own_schema():
    cfg = new_config("ioc-demo")
    assert cfg.basic.name == "ioc-demo"
    assert type(cfg.build.db_load[0]) is _DbLoadItem
    assert cfg.build.db_load[0].file == "example.db"
    IocConfigSchema.model_validate(cfg.model_dump())


def test_missing_field_is_rejected_not_filled_in():
    with pytest.raises(ValidationError) as exc:
        _Settings(report_info=True)
    assert [err["loc"] for err in exc.value.errors()] == [("caputlog_json",)]


def test_extra_field_is_rejected_not_ignored():
    with pytest.raises(ValidationError) as exc:
        _Settings(report_info=True, caputlog_json=False, foo=1)
    assert [err["loc"] for err in exc.value.errors()] == [("foo",)]


def test_free_form_mapping_accepts_any_key():
    item = _DbLoadItem(file="a.db", macros={"ANY": "x", "OTHER": "y"})
    assert list(item.macros) == ["ANY", "OTHER"]


def test_generated_config_survives_a_yaml_round_trip(tmp_path):
    path = tmp_path / "ioc.yaml"
    with open(path, "w", encoding="utf-8") as f:
        get_yaml_tool().dump(new_config("ioc-demo").model_dump(), f)
    with open(path, "r", encoding="utf-8") as f:
        data = get_yaml_tool().load(f)
    cfg = IocConfigSchema.model_validate(data)
    assert cfg == new_config("ioc-demo")
    assert isinstance(cfg.build.modules, list)
    assert isinstance(cfg.build.db_load[0], _DbLoadItem)


ISSUE = dict(level="error", reason="validation_error", message="m", prompt="p", time="t")


def test_issue_entry_converts_to_enums():
    issue = IssueEntry(**ISSUE)
    assert issue.level is IssueLevel.ERROR
    assert issue.reason is IssueReason.VALIDATION_ERROR


@pytest.mark.parametrize("level", ["info", "warning", "error"])
def test_issue_entry_accepts_every_defined_level(level):
    assert IssueEntry(**{**ISSUE, "level": level}).level == level


def test_issue_entry_dumps_enums_as_plain_strings():
    entry = IssueEntry(
        **{**ISSUE, "level": IssueLevel.INFO, "reason": IssueReason.FILE_ERROR}
    )
    dumped = entry.model_dump(mode="json")
    assert dumped["level"] == "info" and dumped["reason"] == "file_error"


@pytest.mark.parametrize(
    "field, bad", [("level", "eror"), ("reason", "validaton_error")]
)
def test_issue_entry_rejects_undefined_values(field, bad):
    with pytest.raises(ValidationError) as exc:
        IssueEntry(**{**ISSUE, field: bad})
    assert [err["loc"] for err in exc.value.errors()] == [(field,)]
