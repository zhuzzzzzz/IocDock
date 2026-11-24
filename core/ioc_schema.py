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
    FILE_CHANGED = "file_changed"
    RECORD_RESET = "record_reset"
    OPERATION_SUCCESS = "operation_success"
    OPERATION_FAILED = "operation_failed"


class IssueEntry(BaseModel):
    level: IssueLevel
    reason: IssueReason
    message: str
    prompt: str
    time: str


class IocStateSchema(BaseModel):
    state: str
    snapshot: str
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
        state="",
        snapshot="",
        src_files=_Src(db_files=[], protocol_files=[], other_files=[]),
        issues=[],
    )
