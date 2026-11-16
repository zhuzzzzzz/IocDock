from pydantic import BaseModel, ConfigDict
from enum import StrEnum


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Basic(_ConfigModel):
    name: str | None
    host: str | None
    image: str | None
    bin: str | None
    description: str | None


class _Settings(_ConfigModel):
    report_info: bool
    caputlog_json: bool


class _DbLoadItem(_ConfigModel):
    file: str
    macros: dict[str, str]


class _RawCmd(_ConfigModel):
    cmd_before_dbload: str | None
    cmd_at_dbload: str | None
    cmd_after_iocinit: str | None


class _FileCopyItem(_ConfigModel):
    src: str
    dest: str
    mode: str


class _Build(_ConfigModel):
    modules: list[str] | None
    settings: _Settings
    epics_env: dict[str, str] | None
    db_load: list[_DbLoadItem]
    raw_cmd: _RawCmd
    file_copy: list[_FileCopyItem] | None


class _ResourceValues(_ConfigModel):
    cpus: str
    memory: str


class _Resources(_ConfigModel):
    limits: _ResourceValues
    reservations: _ResourceValues


class _Placement(_ConfigModel):
    constraints: list[str]


class _Deploy(_ConfigModel):
    labels: dict[str, str] | None
    resources: _Resources | None
    placement: _Placement | None


class IocConfigSchema(_ConfigModel):
    basic: _Basic
    build: _Build
    deploy: _Deploy


class _Src(BaseModel):
    db_files: list[str]
    protocol_files: list[str]
    other_files: list[str]


class IssueLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class IssueReason(StrEnum):
    VALIDATION_ERROR = "validation_error"
    FILE_ERROR = "file_error"


class IssueEntry(BaseModel):
    level: IssueLevel
    reason: IssueReason
    message: str
    prompt: str
    time: str


class IocStateSchema(BaseModel):
    state: str
    status: str
    snapshot: str
    is_exported: bool | str  # "unknown" when the state file is damaged
    src_files: _Src
    issues: list[IssueEntry]


def _default_basic(name):
    return _Basic(
        name=name,
        host="swarm",
        image="",
        bin="ST-IOC",
        description="",
    )


def _defualt_build():
    return _Build(
        modules=["autosave", "caputlog"],
        db_load=[_DbLoadItem(file="example.db", macros={"ABC": "xxx:"})],
        raw_cmd=_RawCmd(
            cmd_before_dbload="",
            cmd_at_dbload="",
            cmd_after_iocinit="",
        ),
        file_copy=[],
        epics_env={},
        settings=_Settings(
            report_info=True,
            caputlog_json=False,
        ),
    )


def _stream_device_build():
    return _Build(
        modules=["autosave", "caputlog"],
        db_load=[_DbLoadItem(file="example.db", macros={"ABC": "xxx:"})],
        raw_cmd=_RawCmd(
            cmd_before_dbload="",
            cmd_at_dbload="",
            cmd_after_iocinit="",
        ),
        file_copy=[],
        epics_env={},
        settings=_Settings(
            report_info=True,
            caputlog_json=False,
        ),
    )


def _modbus_build():
    return _Build(
        modules=["autosave", "caputlog"],
        db_load=[_DbLoadItem(file="example.db", macros={"ABC": "xxx:"})],
        raw_cmd=_RawCmd(
            cmd_before_dbload="",
            cmd_at_dbload="",
            cmd_after_iocinit="",
        ),
        file_copy=[],
        epics_env={},
        settings=_Settings(
            report_info=True,
            caputlog_json=False,
        ),
    )


def _default_deploy():
    return _Deploy(
        labels={},
        resources=_Resources(
            limits=_ResourceValues(cpus="1", memory="1G"),
            reservations=_ResourceValues(cpus="", memory=""),
        ),
        placement=_Placement(constraints=["node.role==worker"]),
    )


def new_config(name, build_type=None):
    if not isinstance(build_type, str):
        build_type = ""
    if build_type.strip().lower() == "modbus":
        return IocConfigSchema(
            basic=_default_basic(name=name),
            build=_modbus_build(),
            deploy=_default_deploy(),
        )
    elif build_type.strip().lower() == "stream_device":
        return IocConfigSchema(
            basic=_default_basic(name=name),
            build=_stream_device_build(),
            deploy=_default_deploy(),
        )
    else:
        return IocConfigSchema(
            basic=_default_basic(name=name),
            build=_defualt_build(),
            deploy=_default_deploy(),
        )


def new_state():
    return IocStateSchema(
        state="normal",
        status="created",
        snapshot="untracked",
        is_exported=False,
        src_files=_Src(db_files=[], protocol_files=[], other_files=[]),
        issues=[],
    )


if __name__ == "__main__":
    import os
    import sys

    from pydantic import ValidationError

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from core.utils import get_yaml_tool

    # 1. new_config: every field is set, and the result passes its own schema.
    cfg = new_config("ioc-demo")
    assert cfg.basic.name == "ioc-demo"
    assert (
        type(cfg.build.db_load[0]) is _DbLoadItem
        and cfg.build.db_load[0].file == "example.db"
    )
    IocConfigSchema.model_validate(cfg.model_dump())
    # the generated config, as it would be written to ioc.yaml.
    print("--- new_config('ioc-demo') ---")
    get_yaml_tool().dump(cfg.model_dump(), sys.stdout)
    print("---")
    print("1. new_config ok")

    # 2. missing field: rejected, not filled in.
    try:
        _Settings(report_info=True)
    except ValidationError as e:
        assert [err["loc"] for err in e.errors()] == [("caputlog_json",)]
    else:
        raise AssertionError("a missing field must be an error")
    print("2. missing field rejected ok")

    # 3. extra field: rejected, not ignored.
    try:
        _Settings(report_info=True, caputlog_json=False, foo=1)
    except ValidationError as e:
        assert [err["loc"] for err in e.errors()] == [("foo",)]
    else:
        raise AssertionError("an extra field must be an error")
    print("3. extra field rejected ok")

    # 4. free-form mapping: keys of macros are chosen by the user, any key is accepted.
    item = _DbLoadItem(file="a.db", macros={"ANY": "x", "OTHER": "y"})
    assert list(item.macros) == ["ANY", "OTHER"]
    print("4. free-form mapping ok")

    # 5. output: write the generated config to a file, read it back, validate it,
    # and show the model objects and their types.
    test_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ioc_test.yaml"
    )
    with open(test_file, "w", encoding="utf-8") as f:
        get_yaml_tool().dump(new_config("ioc-demo").model_dump(), f)
    with open(test_file, "r", encoding="utf-8") as f:
        data = get_yaml_tool().load(f)

    cfg = IocConfigSchema.model_validate(data)

    print(f"{test_file} is valid")

    print(f"{cfg.build.modules} {type(cfg.build.modules)}")
    print(f"{cfg.build.settings} {type(cfg.build.settings)}")
    print(f"{cfg.build.db_load[0]} {type(cfg.build.db_load[0])}")
    print(f"{cfg.build.db_load[0].file}")
    print("5. output ok")

    # 6. issue level and reason: only the defined values are accepted.
    entry = dict(
        level="error", reason="validation_error", message="m", prompt="p", time="t"
    )
    issue = IssueEntry(**entry)
    assert (
        issue.level is IssueLevel.ERROR and issue.reason is IssueReason.VALIDATION_ERROR
    )
    for level in ("info", "warning", "error"):
        assert IssueEntry(**{**entry, "level": level}).level == level
    dumped = IssueEntry(
        **{**entry, "level": IssueLevel.INFO, "reason": IssueReason.FILE_ERROR}
    ).model_dump(mode="json")
    assert dumped["level"] == "info" and dumped["reason"] == "file_error"
    for field, bad in (("level", "eror"), ("reason", "validaton_error")):
        try:
            IssueEntry(**{**entry, field: bad})
        except ValidationError as e:
            assert [err["loc"] for err in e.errors()] == [(field,)]
        else:
            raise AssertionError(f"an undefined {field} must be rejected")
    print("6. issue level and reason ok")
