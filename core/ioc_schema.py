from pydantic import BaseModel


class _Basic(BaseModel):
    name: str | None
    host: str | None
    image: str | None
    bin: str | None
    description: str | None


class _Src(BaseModel):
    db_files: list[str]
    protocol_files: list[str]
    other_files: list[str]


class _DbLoadItem(BaseModel):
    file: str
    macros: dict[str, str]


class _RawCmd(BaseModel):
    cmd_before_dbload: str | None
    cmd_at_dbload: str | None
    cmd_after_iocinit: str | None


class _FileCopyItem(BaseModel):
    src: str
    dest: str
    mode: str


class _Build(BaseModel):
    modules: list[str] | None
    db_load: list[_DbLoadItem]
    raw_cmd: _RawCmd
    file_copy: list[_FileCopyItem] | None
    epics_env: dict[str, str] | None


class _Settings(BaseModel):
    report_info: bool
    caputlog_json: bool


class _ResourceValues(BaseModel):
    cpus: str
    memory: str


class _Resources(BaseModel):
    limits: _ResourceValues
    reservations: _ResourceValues


class _Placement(BaseModel):
    constraints: list[str]


class _Deploy(BaseModel):
    labels: dict[str, str] | None
    resources: _Resources | None
    placement: _Placement | None


class IocConfigSchema(BaseModel):
    basic: _Basic
    src: _Src
    build: _Build
    settings: _Settings
    deploy: _Deploy


class _IssueEntry(BaseModel):
    level: str
    reason: str
    prompt: str
    time: str


class IocStateSchema(BaseModel):
    state: str
    status: str
    snapshot: str
    is_exported: bool | str  # "unknown" when the state file is damaged
    src_files: _Src
    issues: list[_IssueEntry]


if __name__ == "__main__":
    import os
    import sys
    from ruamel.yaml import YAML

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from core.ioc_config import IOC_CONFIG_TEMPLATE

    test_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ioc_test.yaml"
    )
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(IOC_CONFIG_TEMPLATE.replace("__NAME__", "ioc-demo"))
    with open(test_file, "r", encoding="utf-8") as f:
        data = YAML(typ="safe").load(f)

    cfg = IocConfigSchema.model_validate(data)

    print(f"{test_file} is valid")

    print(f"{cfg.src} {type(cfg.src)}")
    print(f"{cfg.src.other_files} {type(cfg.src.other_files)}")
    print(f"{cfg.build.db_load[0]} {type(cfg.build.db_load[0])}")
    print(f"{cfg.build.db_load[0].file}")
