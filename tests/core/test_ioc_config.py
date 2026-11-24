import re
from pathlib import Path

import pytest

from core.ioc_config import IocConfig
from core.ioc_schema import IocStateSchema, IssueEntry, IssueLevel, IssueReason
from core.utils import get_yaml_tool
from tests.logutil import check, check_true, expect_error, note, step


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8")


def messages(conf):
    return [i.message for i in conf.issues]


# ---------------------------------------------------------------- IocConfig
# A change a person would make in an editor is written as a variant of the
# generated text (base), so there is nothing to undo between steps.


def test_create_template_names_config_after_directory(make_conf):
    """create_template: 生成的配置文件以目录名命名,能直接加载,没有 .tmp 残留"""
    conf = make_conf("ioc-demo")
    check("文件存在", conf.file_exists(), True)
    conf.load()
    check("issues", conf.issues, [])
    check("is_valid", conf.is_valid, True)
    check("basic.name", conf.data.basic.name, "ioc-demo")
    check_true("配置里没有 src 段", "src" not in conf.data.model_dump())
    check(
        ".tmp 残留",
        [p for p in Path(conf.path).parent.iterdir() if p.suffix == ".tmp"],
        [],
    )


def test_create_template_never_overwrites(make_conf):
    """create_template: 已有文件时拒绝覆盖"""
    conf = make_conf()
    with expect_error(FileExistsError, "文件已存在"):
        IocConfig.create_template(conf.path, None)


def test_create_template_with_awkward_directory_name(make_conf):
    """create_template: 目录名含引号、中文、反斜杠时也能正确生成并加载"""
    conf = make_conf('ioc "测试" #1\\x')
    conf.load()
    check("basic.name", conf.data.basic.name, 'ioc "测试" #1\\x')


@pytest.mark.parametrize("build_type", ["modbus", "stream_device", " Modbus "], ids=repr)
def test_create_template_for_each_build_type(tmp_path, build_type):
    """create_template: 各种 build_type 都能生成可直接加载的配置"""
    path = tmp_path / "ioc-typed" / "ioc.yaml"
    path.parent.mkdir()
    step(f"create_template(build_type={build_type!r})")
    IocConfig.create_template(str(path), build_type)
    conf = IocConfig(str(path))
    conf.load()
    check("issues", conf.issues, [])
    check("basic.name", conf.data.basic.name, "ioc-typed")


def test_file_exists_is_false_before_create(tmp_path):
    """file_exists: 文件还没建时为 False"""
    check("file_exists", IocConfig(str(tmp_path / "ioc.yaml")).file_exists(), False)


def test_typed_access(make_conf):
    """data: 配置按类型访问,字段不存在时报 AttributeError"""
    conf = make_conf("t-get")
    conf.load()
    check("basic.host", conf.data.basic.host, "swarm")
    check("modules[0]", conf.data.build.modules[0], "autosave")
    check_true("默认不装 status-os", "status-os" not in conf.data.build.modules)
    check("macros['ABC']", conf.data.build.db_load[0].macros["ABC"], "xxx:")
    check("settings.report_info", conf.data.build.settings.report_info, True)
    with expect_error(AttributeError, "访问不存在的字段"):
        conf.data.build.no_such_field


def test_load_reads_hand_written_file_and_never_touches_it(make_conf):
    """load: 读取手写修改过的文件,并且绝不改动该文件"""
    conf = make_conf("t-load")
    base = read(conf.path)
    conf.load()
    check_true("load 之后文件没变", read(conf.path) == base)
    text = base + "# my own note\n"
    text = re.sub(r"image: ''.*", "image: registry.iasf/ioc:1.0", text)
    text = re.sub(
        r"cmd_at_dbload: ''.*",
        'cmd_at_dbload: |\n      line1\n      dbLoadRecords("x.db")',
        text,
    )
    text = text.replace("ABC: 'xxx:'", "P: 'xxx:'")
    step("手工修改 image、cmd_at_dbload、macros,并加一行注释")
    write(conf.path, text)
    conf.load()
    check_true("再次 load 后文件没变", read(conf.path) == text)
    check("issues", conf.issues, [])
    check("basic.image", conf.data.basic.image, "registry.iasf/ioc:1.0")
    check("macros['P']", conf.data.build.db_load[0].macros["P"], "xxx:")
    check(
        "cmd_at_dbload",
        conf.data.build.raw_cmd.cmd_at_dbload,
        'line1\ndbLoadRecords("x.db")\n',
    )


def test_empty_list_is_valid_and_stays_empty(make_conf):
    """load: 空列表是合法值,读出来仍是空列表"""
    conf = make_conf("t-check")
    base = read(conf.path)
    text = re.sub(r"modules:.*\n    - autosave\n    - caputlog", "modules: []", base)
    assert text != base
    write(conf.path, text)
    conf.load()
    check("is_valid", conf.is_valid, True)
    check("modules", conf.data.build.modules, [])


def test_invalid_value_becomes_an_issue_and_there_is_no_config(make_conf, tmp_path):
    """load: 取值不合法时产生 issue,data 为 None,show/to_string/save 都拒绝工作"""
    conf = make_conf("t-invalid")
    base = read(conf.path)
    step("把 cpus: '1' 改成 cpus: 1(类型不对)")
    write(conf.path, base.replace("cpus: '1'", "cpus: 1"))
    conf.load()
    check("data", conf.data, None)
    check("is_valid", conf.is_valid, False)
    check("issue 数量", len(conf.issues), 1)
    issue = conf.issues[0]
    note("issue", f"{issue.level.value}/{issue.reason.value}: {issue.message}")
    check_true("issue 是 IssueEntry", isinstance(issue, IssueEntry))
    check("level", issue.level, IssueLevel.ERROR)
    check("reason", issue.reason, IssueReason.VALIDATION_ERROR)
    check_true(
        "message 带字段路径", issue.message.startswith("deploy.resources.limits.cpus:")
    )

    never = tmp_path / "never-written.yaml"
    for method, args in (
        (conf.show, ()),
        (conf.to_string, ()),
        (conf.save, (str(never),)),
    ):
        with expect_error(RuntimeError, f"{method.__name__}() 在没有配置时"):
            method(*args)
    check_true("save 没有写出文件", not never.exists())

    # the issue is accepted by IocStateSchema as is
    state = IocStateSchema(
        state="error",
        snapshot="untracked",
        src_files={"db_files": [], "protocol_files": [], "other_files": []},
        issues=conf.issues,
    )
    check("这条 issue 可以直接放进 IocStateSchema", state.issues[0].message, issue.message)


def test_load_recovers_after_the_file_is_fixed(make_conf):
    """load: 文件修好之后再次 load,恢复正常"""
    conf = make_conf("t-invalid")
    base = read(conf.path)
    write(conf.path, base.replace("cpus: '1'", "cpus: 1"))
    conf.load()
    check("损坏时 data", conf.data, None)
    write(conf.path, base)
    conf.load()
    check_true("修好后有 data", conf.data is not None)
    check("修好后 issues", conf.issues, [])


def test_invalid_nested_value_is_reported_with_its_path(make_conf):
    """load: 嵌套字段取值不合法时,issue 里带完整路径"""
    conf = make_conf("t-invalid")
    write(conf.path, read(conf.path).replace("report_info: true", "report_info: maybe"))
    conf.load()
    note("issues", messages(conf))
    check_true(
        "路径为 build.settings.report_info",
        any(m.startswith("build.settings.report_info:") for m in messages(conf)),
    )


def test_missing_field_is_reported_including_nested_ones(make_conf):
    """load: 缺字段(含嵌套字段)会被指出来"""
    conf = make_conf("t-missing")
    base = read(conf.path)
    write(conf.path, base.replace("    report_info: true\n", ""))
    conf.load()
    check("data", conf.data, None)
    check("缺嵌套字段", messages(conf), ["build.settings.report_info: Field required"])
    write(conf.path, base.replace("  epics_env: {}\n", ""))
    conf.load()
    check("缺上层字段", messages(conf), ["build.epics_env: Field required"])


def test_extra_field_is_an_error_at_any_depth(make_conf):
    """load: 任何层级出现多余字段都报错"""
    conf = make_conf("t-extra")
    base = read(conf.path)
    write(conf.path, base.replace("  settings:\n", "  foo: 1\n  settings:\n"))
    conf.load()
    check("data", conf.data, None)
    check("上层多余", messages(conf), ["build.foo: Extra inputs are not permitted"])
    write(
        conf.path,
        base.replace("    caputlog_json: false", "    caputlog_json: false\n    bar: 2"),
    )
    conf.load()
    check(
        "嵌套多余",
        messages(conf),
        ["build.settings.bar: Extra inputs are not permitted"],
    )


def test_free_form_mapping_takes_any_key(make_conf):
    """load: macros 这类自由字典可以随意加键"""
    conf = make_conf("t-extra")
    text = read(conf.path).replace(
        "        ABC: 'xxx:'\n", "        ABC: 'xxx:'\n        Z: zzz\n"
    )
    assert "Z: zzz" in text
    write(conf.path, text)
    conf.load()
    check_true("有 data", conf.data is not None)
    check("issues", conf.issues, [])


def test_name_mismatch_is_a_warning_and_config_stays_usable(make_conf):
    """load: basic.name 与目录名不符只是 warning,配置仍可用但 is_valid 为 False"""
    conf = make_conf("t-name")
    base = read(conf.path)
    write(conf.path, base.replace("name: t-name", "name: other"))
    conf.load()
    check_true("仍有 data", conf.data is not None)
    check("issue 数量", len(conf.issues), 1)
    check("is_valid", conf.is_valid, False)  # usable, but the name check failed
    note("issue", conf.issues[0].message)
    check("level", conf.issues[0].level, IssueLevel.WARNING)
    check_true("message 以 basic.name: 开头", conf.issues[0].message.startswith("basic.name:"))
    check("reason", conf.issues[0].reason, IssueReason.VALIDATION_ERROR)
    write(conf.path, base)
    conf.load()
    check("改回之后 issues", conf.issues, [])
    check("改回之后 is_valid", conf.is_valid, True)


@pytest.mark.parametrize(
    "content, expected",
    [
        (b"basic: [unclosed\n", "while parsing a flow sequence"),
        (b"basic:\n  name: a\n  name: b\n", "found duplicate key"),
        (b"", "config file is empty"),
        (b"\xff\xfe\x00bad", "codec can't decode"),
    ],
    ids=["unclosed-bracket", "duplicate-key", "empty-file", "not-utf8"],
)
def test_unreadable_file_becomes_a_file_error_issue(tmp_path, content, expected):
    """load: 读不了的文件(语法错、重复键、空文件、乱码)变成 file_error 的 issue"""
    path = tmp_path / "bad.yaml"
    path.write_bytes(content)
    bad = IocConfig(str(path))
    check("file_exists", bad.file_exists(), True)
    bad.load()
    check("data", bad.data, None)
    check("issue 数量", len(bad.issues), 1)
    check("is_valid", bad.is_valid, False)
    note("message", bad.issues[0].message)
    check("reason", bad.issues[0].reason, IssueReason.FILE_ERROR)
    check("level", bad.issues[0].level, IssueLevel.ERROR)
    check_true(f"message 含 {expected!r}", expected in bad.issues[0].message)


@pytest.mark.parametrize(
    "content", ["- a\n- b\n", "just text\n", "42\n"], ids=["list", "string", "number"]
)
def test_yaml_root_that_is_not_a_mapping_is_reported_as_root(tmp_path, content):
    """load: YAML 根节点不是映射(列表、字符串、数字)时,issue 的路径是 <root>"""
    path = tmp_path / "ioc.yaml"
    path.write_text(content)
    conf = IocConfig(str(path))
    conf.load()
    check("data", conf.data, None)
    check("issue 数量", len(conf.issues), 1)
    note("issue", conf.issues[0].message)
    check_true("message 以 <root>: 开头", conf.issues[0].message.startswith("<root>:"))
    check("reason", conf.issues[0].reason, IssueReason.VALIDATION_ERROR)
    check("is_valid", conf.is_valid, False)


def test_load_of_a_missing_file_raises(tmp_path):
    """load: 文件不存在时抛 FileNotFoundError(这不是 issue)"""
    bad = IocConfig(str(tmp_path / "bad.yaml"))
    check("file_exists", bad.file_exists(), False)
    with expect_error(FileNotFoundError, "文件不存在", match="config file not found"):
        bad.load()
    check("data", bad.data, None)
    check("is_valid", bad.is_valid, False)


def test_file_that_vanishes_after_load_leaves_no_stale_result(make_conf):
    """load: 加载后文件被删,再 load 会报错,并且不留下上一次的旧结果"""
    conf = make_conf("t-vanish")
    conf.load()
    check("第一次 is_valid", conf.is_valid, True)
    Path(conf.path).unlink()
    step("删掉配置文件后再 load")
    with expect_error(FileNotFoundError, "文件没了"):
        conf.load()
    check("data", conf.data, None)
    check("issues", conf.issues, [])
    check("is_valid", conf.is_valid, False)


def test_use_before_load_raises(make_conf, tmp_path):
    """show/to_string/save: 还没 load 时拒绝工作"""
    fresh = make_conf("t-fresh")
    check("data", fresh.data, None)
    check("is_valid", fresh.is_valid, False)
    never = tmp_path / "never-written.yaml"
    for method, args in (
        (fresh.show, ()),
        (fresh.to_string, ()),
        (fresh.save, (str(never),)),
    ):
        with expect_error(RuntimeError, f"{method.__name__}() 在 load 之前"):
            method(*args)
    check_true("save 没有写出文件", not never.exists())
    fresh.load()
    check_true("load 之后有 data", fresh.data is not None)


def test_show_prints_plain_data_without_comments(make_conf, capsys):
    """show: 输出纯数据,不带注释和空行,内容与 to_string 一致"""
    conf = make_conf("t-show")
    with open(conf.path, "a", encoding="utf-8") as f:
        f.write("# my own note\n")
    conf.load()
    conf.show()
    out = capsys.readouterr().out
    check_true("没有注释符号和空行", "#" not in out and "\n\n" not in out)
    check_true("再解析得到同样的数据", get_yaml_tool().load(out) == conf.data.model_dump())
    check_true("与 to_string 一致", out == conf.to_string())


def test_save_writes_validated_config_and_leaves_source_untouched(make_conf, tmp_path):
    """save: 写出校验过的配置(不带注释),源文件不变"""
    source = make_conf("t-save")
    with open(source.path, "a", encoding="utf-8") as f:
        f.write("# my own note\n")
    source_text = read(source.path)
    source.load()
    target_path = tmp_path / "managed" / "t-save" / "ioc.yaml"
    target_path.parent.mkdir(parents=True)
    source.save(str(target_path))
    check_true("源文件没变", read(source.path) == source_text)
    target = IocConfig(str(target_path))
    target.load()
    check("目标文件的 issues", target.issues, [])
    check_true("目标与源的数据相同", target.data == source.data)
    check_true("注释没有被写出", "# my own note" not in read(target_path))


def test_save_of_an_invalid_config_writes_nothing(make_conf, tmp_path):
    """save: 配置不合法时什么都不写"""
    invalid = make_conf("t-save-invalid")
    write(invalid.path, read(invalid.path).replace("cpus: '1'", "cpus: 1"))
    invalid.load()
    check("data", invalid.data, None)
    other = tmp_path / "managed" / "t-save-invalid" / "ioc.yaml"
    other.parent.mkdir(parents=True)
    with expect_error(RuntimeError, "配置不合法"):
        invalid.save(str(other))
    check_true("没有写出文件", not other.exists())


def test_save_into_a_missing_directory_fails_and_creates_nothing(make_conf, tmp_path):
    """save: 目标目录不存在时报错,不会替你建目录"""
    conf = make_conf("t-save-nodir")
    conf.load()
    target = tmp_path / "no-such-dir" / "ioc.yaml"
    with expect_error(FileNotFoundError, "目录不存在"):
        conf.save(str(target))
    check_true("目录没有被创建", not target.parent.exists())
