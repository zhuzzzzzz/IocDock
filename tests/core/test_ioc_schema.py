import pytest
from pydantic import ValidationError

import core.ioc_schema as schema
from core.ioc_schema import (
    IocConfigSchema,
    IocStateSchema,
    IssueCode,
    IssueEntry,
    IssueLevel,
    IssueSource,
    _DbLoadItem,
    _Settings,
    _Src,
    new_config,
    new_state,
    sort_by_priority,
)
from core.utils import get_yaml_tool
from tests.logutil import check, check_true, expect_error, note, step

# ------------------------------------------------------------ config schema


def test_new_config_passes_its_own_schema():
    """new_config: 生成的默认配置能通过自己的 schema 校验"""
    cfg = new_config("ioc-demo")
    step("new_config('ioc-demo')")
    check("basic.name", cfg.basic.name, "ioc-demo")
    check("db_load[0] 的类型", type(cfg.build.db_load[0]), _DbLoadItem)
    check("db_load[0].file", cfg.build.db_load[0].file, "example.db")
    IocConfigSchema.model_validate(cfg.model_dump())
    note("model_validate(model_dump())", "通过")


@pytest.mark.parametrize(
    "build_type",
    [None, "", "modbus", " Modbus ", "STREAM_DEVICE", "stream_device", "unknown", 123],
    ids=repr,
)
def test_new_config_for_every_build_type_is_valid_and_named(build_type):
    """new_config: 任何 build_type(含大小写、空白、未知值、非字符串)都得到可用的配置"""
    step(f"new_config('ioc-x', build_type={build_type!r})")
    cfg = new_config("ioc-x", build_type=build_type)
    check("basic.name", cfg.basic.name, "ioc-x")
    IocConfigSchema.model_validate(cfg.model_dump())
    note("校验", "通过")


@pytest.mark.parametrize(
    "build_type, expected",
    [
        ("modbus", "modbus"),
        (" Modbus ", "modbus"),
        ("MODBUS", "modbus"),
        ("stream_device", "stream_device"),
        (" STREAM_DEVICE ", "stream_device"),
        (None, "default"),
        ("", "default"),
        ("unknown", "default"),
        (123, "default"),
    ],
    ids=repr,
)
def test_new_config_picks_the_build_by_type(monkeypatch, build_type, expected):
    """new_config: 按 build_type 选对 build(忽略大小写和首尾空白,未知值用默认)"""
    plain = schema._default_build()
    for kind, func in (
        ("modbus", "_modbus_build"),
        ("stream_device", "_stream_device_build"),
        ("default", "_default_build"),
    ):
        # three builds are the same today, so tag each one to tell them apart
        monkeypatch.setattr(
            schema, func, lambda kind=kind: plain.model_copy(update={"modules": [kind]})
        )
    cfg = new_config("ioc-x", build_type=build_type)
    step(f"build_type={build_type!r}")
    check("选中的 build", cfg.build.modules, [expected])


def test_missing_field_is_rejected_not_filled_in():
    """schema: 缺字段会被拒绝,不会自动补默认值"""
    step("_Settings(report_info=True),缺 caputlog_json")
    with expect_error(ValidationError, "缺字段") as info:
        _Settings(report_info=True)
    check("出错的字段", [e["loc"] for e in info.value.errors()], [("caputlog_json",)])


def test_extra_field_is_rejected_not_ignored():
    """schema: 多出来的字段会被拒绝,不会被忽略"""
    step("_Settings(..., foo=1)")
    with expect_error(ValidationError, "多余字段") as info:
        _Settings(report_info=True, caputlog_json=False, foo=1)
    check("出错的字段", [e["loc"] for e in info.value.errors()], [("foo",)])


def test_free_form_mapping_accepts_any_key():
    """schema: macros 这类自由字典可以用任意键"""
    item = _DbLoadItem(file="a.db", macros={"ANY": "x", "OTHER": "y"})
    check("macros 的键", list(item.macros), ["ANY", "OTHER"])


def test_generated_config_survives_a_yaml_round_trip(tmp_path):
    """schema: 默认配置写成 YAML 再读回,内容和类型都不变"""
    path = tmp_path / "ioc.yaml"
    with open(path, "w", encoding="utf-8") as f:
        get_yaml_tool().dump(new_config("ioc-demo").model_dump(), f)
    with open(path, "r", encoding="utf-8") as f:
        data = get_yaml_tool().load(f)
    cfg = IocConfigSchema.model_validate(data)
    check_true("读回的配置与原配置相等", cfg == new_config("ioc-demo"))
    check_true("modules 是 list", isinstance(cfg.build.modules, list))
    check_true("db_load[0] 是 _DbLoadItem", isinstance(cfg.build.db_load[0], _DbLoadItem))


# -------------------------------------------------------------- issue entry

ISSUE = dict(
    source="check", level="error", code="config_invalid", target="build.modules",
    message="m", prompt="p", time="t",
)


def test_issue_entry_converts_to_enums():
    """IssueEntry: 字符串自动转成枚举"""
    issue = IssueEntry(**ISSUE)
    check_true("source 是 IssueSource.CHECK", issue.source is IssueSource.CHECK)
    check_true("level 是 IssueLevel.ERROR", issue.level is IssueLevel.ERROR)
    check_true("code 是 IssueCode.CONFIG_INVALID", issue.code is IssueCode.CONFIG_INVALID)


@pytest.mark.parametrize("level", ["info", "warning", "error"])
def test_issue_entry_accepts_every_defined_level(level):
    """IssueEntry: 接受每一个定义过的 level"""
    check("level", IssueEntry(**{**ISSUE, "level": level}).level, level)


def test_issue_entry_dumps_enums_as_plain_strings():
    """IssueEntry: 导出成 JSON 时枚举是普通字符串,字段顺序就是数据库的列"""
    entry = IssueEntry(
        **{**ISSUE, "level": IssueLevel.INFO, "code": IssueCode.FILE_CHANGED}
    )
    dumped = entry.model_dump(mode="json")
    check("source", dumped["source"], "check")
    check("level", dumped["level"], "info")
    check("code", dumped["code"], "file_changed")
    check(
        "字段",
        list(IssueEntry.model_fields),
        ["source", "level", "code", "target", "message", "prompt", "time"],
    )


@pytest.mark.parametrize(
    "field, bad",
    [("source", "chek"), ("level", "eror"), ("code", "validaton_error")],
)
def test_issue_entry_rejects_undefined_values(field, bad):
    """IssueEntry: 没定义过的 source / level / code 会被拒绝"""
    step(f"{field}={bad!r}")
    with expect_error(ValidationError, "未定义的取值") as info:
        IssueEntry(**{**ISSUE, field: bad})
    check("出错的字段", [e["loc"] for e in info.value.errors()], [(field,)])


def test_issue_entry_needs_every_field():
    """IssueEntry: 少一个字段就拒绝(target 和 prompt 没有该有的默认值,要写 "")"""
    for field in ISSUE:
        step(f"没有 {field}")
        with expect_error(ValidationError, f"没有 {field}") as info:
            IssueEntry(**{k: v for k, v in ISSUE.items() if k != field})
        check("出错的字段", [e["loc"] for e in info.value.errors()], [(field,)])


# The source of every code, written out here on purpose: a new code has to be put here,
# which is when somebody decides which source it belongs to.
SOURCE_OF_CODE = {
    "dir_missing": "check",
    "config_missing": "check",
    "config_unreadable": "check",
    "config_invalid": "check",
    "src_unreadable": "check",
    "repo_missing": "check",
    "repo_unreadable": "check",
    "file_changed": "check",
    "file_name_invalid": "check",
    "record_reset": "repair",
    "create": "operation",
    "build": "operation",
    "export": "operation",
}


def test_every_code_has_its_source_in_this_file():
    """IssueCode: 上面的表列全了所有的 code,没有多也没有少"""
    check("code", sorted(SOURCE_OF_CODE), sorted(c.value for c in IssueCode))


@pytest.mark.parametrize("code, source", SOURCE_OF_CODE.items())
def test_issue_entry_accepts_a_code_with_its_own_source(code, source):
    """IssueEntry: code 配它自己的 source 才接受"""
    entry = IssueEntry(**{**ISSUE, "source": source, "code": code})
    check("source", entry.source, source)
    check("code", entry.code, code)


@pytest.mark.parametrize(
    "code, source",
    [(c, s) for c, own in SOURCE_OF_CODE.items() for s in ("check", "repair", "operation") if s != own],
)
def test_issue_entry_rejects_a_code_with_another_source(code, source):
    """IssueEntry: code 配了别的 source 就拒绝"""
    with expect_error(ValidationError, f"{code} 不能是 {source}"):
        IssueEntry(**{**ISSUE, "source": source, "code": code})


def test_sort_by_priority_puts_the_level_first_then_the_newest():
    """sort_by_priority: 先按级别(error、warning、info),同级别新的在前,完全相同的保持原来的顺序"""
    def issue(message, level, time):
        return IssueEntry(**{**ISSUE, "message": message, "level": level, "time": time})

    issues = [
        issue("w-old", "warning", "2026/01/01 00:00:00"),
        issue("i-new", "info", "2026/03/01 00:00:00"),
        issue("e-old", "error", "2026/01/01 00:00:00"),
        issue("w-new", "warning", "2026/02/01 00:00:00"),
        issue("e-new-a", "error", "2026/02/01 00:00:00"),
        issue("e-new-b", "error", "2026/02/01 00:00:00"),
    ]
    check(
        "顺序",
        [i.message for i in sort_by_priority(issues)],
        ["e-new-a", "e-new-b", "e-old", "w-new", "w-old", "i-new"],
    )
    check("原来的列表没动", [i.message for i in issues][0], "w-old")


# ------------------------------------------------------------- state schema


def test_new_state_is_the_default_state_of_a_new_ioc():
    """new_state: 新 IOC 的默认状态(state 和 snapshot 为空字符串,文件列表为空)"""
    state = new_state()
    check("state", state.state, "")
    check("snapshot", state.snapshot, "")
    check("src_files", state.src_files.model_dump(), {
        "db_files": [],
        "protocol_files": [],
        "other_files": [],
    })
    check("issues", state.issues, [])


def test_new_state_returns_independent_objects():
    """new_state: 每次返回独立对象,改一个不会影响另一个"""
    first, second = new_state(), new_state()
    step("往 first 的 db_files 和 issues 里各加一项")
    first.src_files.db_files.append("a.db")
    first.issues.append(IssueEntry(**ISSUE))
    check("second.src_files.db_files", second.src_files.db_files, [])
    check("second.issues", second.issues, [])
    check("再取一个新的 db_files", new_state().src_files.db_files, [])


def test_state_schema_fields():
    """IocStateSchema: 只有 state / snapshot / src_files / issues 四个字段"""
    check(
        "字段",
        list(IocStateSchema.model_fields),
        ["state", "snapshot", "src_files", "issues"],
    )


def test_state_schema_accepts_a_plain_dict_for_src_files():
    """IocStateSchema: src_files 可以直接传 dict"""
    state = IocStateSchema(
        state="normal",
        snapshot="tracked",
        src_files={"db_files": ["a.db"], "protocol_files": [], "other_files": []},
        issues=[],
    )
    check_true("转成了 _Src", isinstance(state.src_files, _Src))
    check("db_files", state.src_files.db_files, ["a.db"])


@pytest.mark.parametrize("missing", ["state", "snapshot", "src_files", "issues"])
def test_state_schema_rejects_a_missing_field(missing):
    """IocStateSchema: 缺任何一个字段都会被拒绝"""
    values = new_state().model_dump()
    del values[missing]
    step(f"去掉 {missing}")
    with expect_error(ValidationError, "缺字段") as info:
        IocStateSchema(**values)
    check("出错的字段", [e["loc"] for e in info.value.errors()], [(missing,)])


@pytest.mark.parametrize("field, bad", [("state", 5), ("snapshot", None)])
def test_state_schema_rejects_values_of_the_wrong_type(field, bad):
    """IocStateSchema: 字段类型不对会被拒绝(不会把 5 悄悄转成 '5')"""
    values = new_state().model_dump()
    values[field] = bad
    step(f"{field}={bad!r}")
    with expect_error(ValidationError, "类型不对") as info:
        IocStateSchema(**values)
    check("出错的字段", [e["loc"] for e in info.value.errors()], [(field,)])


def test_src_files_needs_all_three_lists():
    """_Src: 三个文件列表缺一个都不行"""
    step("_Src(db_files=[], protocol_files=[]),缺 other_files")
    with expect_error(ValidationError, "缺字段") as info:
        _Src(db_files=[], protocol_files=[])
    check("出错的字段", [e["loc"] for e in info.value.errors()], [("other_files",)])
