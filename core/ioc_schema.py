from pydantic import BaseModel, ConfigDict, model_validator
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


class IssueSource(StrEnum):
    # the state of the IOC as the self-check sees it now: what is wrong. Every scan
    # works all of it out again and replaces what was there, so a problem that is
    # gone is gone from the list, and it says nothing about what happened in between
    CHECK = "check"
    # what the system repaired by itself, without being asked (a record that was
    # lost and made again, ...). A record of something that happened, it stays
    REPAIR = "repair"
    # the result of an operation the user did (a build, an export, ...). Stays too
    OPERATION = "operation"


class IssueCode(StrEnum):
    """What kind of problem (source CHECK), what was repaired (source REPAIR) or which
    operation (source OPERATION) an issue is about. The code is what identifies an
    issue, not its message, which is for people to read and may be reworded."""

    # source CHECK
    DIR_MISSING = "dir_missing"  # the record is there, the directory is gone
    CONFIG_MISSING = "config_missing"
    CONFIG_UNREADABLE = "config_unreadable"
    CONFIG_INVALID = "config_invalid"  # target: the field
    SRC_UNREADABLE = "src_unreadable"
    REPO_MISSING = "repo_missing"
    REPO_UNREADABLE = "repo_unreadable"
    FILE_CHANGED = "file_changed"  # target: the file
    FILE_NAME_INVALID = "file_name_invalid"  # target: the file, left out of the check
    # source REPAIR
    RECORD_RESET = "record_reset"  # the directory was there, the record was lost
    # source OPERATION
    CREATE = "create"
    BUILD = "build"
    EXPORT = "export"


# the codes of the other two sources; every code that is not one of them is a CHECK code
REPAIR_CODES = (IssueCode.RECORD_RESET,)
OPERATION_CODES = (IssueCode.CREATE, IssueCode.BUILD, IssueCode.EXPORT)


class IssueEntry(BaseModel):
    """One issue of an IOC.
      source   which of the three kinds it is
      level    CHECK: how serious the problem is. REPAIR and OPERATION: how it went,
               INFO it worked, WARNING it worked but with a loss or with problems,
               ERROR it failed
      code     what the problem is, what was repaired or which operation (a code
               belongs to one source)
      target   what it is about, "" for the IOC as a whole: a file ("src/a.db"), a
               field of the config ("build.db_load.0.file"), what the operation made
      message  for people to read
      prompt   a hint to the user on what to do about it, "" when there is none
      time     CHECK: when the problem was first seen (a scan keeps it as long as
               the problem stays). REPAIR and OPERATION: when it was done
    A CHECK issue is told from the others of its scan by (code, target)."""

    source: IssueSource
    level: IssueLevel
    code: IssueCode
    target: str
    message: str
    prompt: str
    time: str

    @model_validator(mode="after")
    def _code_belongs_to_source(self):
        if self.code in OPERATION_CODES:
            expected = IssueSource.OPERATION
        elif self.code in REPAIR_CODES:
            expected = IssueSource.REPAIR
        else:
            expected = IssueSource.CHECK
        if self.source is not expected:
            raise ValueError(
                f"code {self.code.value!r} does not belong to source {self.source.value!r}"
            )
        return self


_LEVEL_RANK = {IssueLevel.ERROR: 0, IssueLevel.WARNING: 1, IssueLevel.INFO: 2}


def sort_by_priority(issues):
    """A new list of the issues, the ones that matter most first: by level (error,
    warning, info), and of one level the newest first. Issues that are still equal
    stay in the order they were in."""
    newest_first = sorted(issues, key=lambda i: i.time, reverse=True)
    return sorted(newest_first, key=lambda i: _LEVEL_RANK[i.level])


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
