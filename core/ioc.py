import os
import sys
from io import StringIO

from pydantic import ValidationError
from ruamel.yaml.scalarstring import LiteralScalarString

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ioc_config import IOC_CONFIG_TEMPLATE
from core.ioc_schema import IocConfigSchema
from core.utils import atomic_write, get_dir_name, get_yaml_tool, to_plain


class IocConfig:
    def __init__(self, path):
        self._yaml = get_yaml_tool()
        self.path = path
        self._config = None
        self.is_loaded = False
        self.is_valid = False
        self.errors = []

    def create(self):
        if os.path.exists(self.path):
            raise FileExistsError(self.path)
        atomic_write(self.path, IOC_CONFIG_TEMPLATE)
        self.load()
        self.set("basic.name", get_dir_name(self.path))
        self.save()

    def load(self):
        self._config = None
        self.is_loaded = False
        self.is_valid = False
        self.errors = []
        with open(self.path, "r", encoding="utf-8") as f:
            self._config = self._yaml.load(f)
        if self._config is None:
            raise ValueError(f"config file is empty: {self.path}")
        self.is_loaded = True
        self.validate()

    def _require_loaded(self):
        if not self.is_loaded:
            raise RuntimeError("config not loaded")

    def save(self):
        self._require_loaded()
        buf = StringIO()
        self._yaml.dump(self._config, buf)
        atomic_write(self.path, buf.getvalue())

    def get(self, path, default=None):
        self._require_loaded()
        node = self._config
        for part in path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            else:
                return default
        return node

    def set(self, path, value):
        self._require_loaded()
        if isinstance(value, str) and "\n" in value:
            value = LiteralScalarString(value)
        parts = path.split(".")
        node = self._config
        for part in parts[:-1]:
            if isinstance(node, list):
                node = node[int(part)]
            else:
                if part not in node or not isinstance(node[part], (dict, list)):
                    node[part] = {}
                node = node[part]
        if isinstance(node, list):
            node[int(parts[-1])] = value
        else:
            node[parts[-1]] = value
        self.validate()

    def check(self, path, value):
        node = self.get(path)
        if isinstance(node, list):
            return not node if value == "" else value in node
        return node == value

    def show(self):
        self._require_loaded()
        self._yaml.dump(to_plain(self._config), sys.stdout)

    def validate(self):
        self.is_valid = False
        self.errors = []
        try:
            IocConfigSchema.model_validate(self._config)
            self.is_valid = True
        except ValidationError as e:
            for err in e.errors():
                path = ".".join(str(p) for p in err["loc"])
                self.errors.append(f"{path}: {err['msg']}")
        return not self.errors


if __name__ == "__main__":
    import shutil

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    test_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ioc_test")
    shutil.rmtree(test_root, ignore_errors=True)
    ioc_dir = os.path.join(test_root, "ioc-demo")
    os.makedirs(ioc_dir)
    config_path = os.path.join(ioc_dir, "ioc.yaml")

    # 1. create from template; name follows the directory name.
    conf = IocConfig(config_path)
    conf.create()
    assert conf.errors == []
    assert conf.is_valid is True and conf.get("basic.name") == "ioc-demo"
    try:
        conf.create()
    except FileExistsError:
        pass
    else:
        raise AssertionError("create() must not overwrite an existing file")
    print("1. create ok")

    # 2. get: existing value, list item, missing path with default.
    assert conf.get("basic.host") == "swarm"
    assert conf.get("build.modules.0") == "autosave"
    assert conf.get("not.exist", "dflt") == "dflt"
    print("2. get ok")

    # 3. set + save + reload; a hand-written comment must survive.
    with open(config_path, "a", encoding="utf-8") as f:
        f.write("# my own note\n")
    conf.load()
    conf.set("basic.image", "registry.iasf/ioc:1.0")
    conf.set("build.db_load", [{"file": "x.db", "macros": {"P": "xxx:"}}])
    conf.set("build.raw_cmd.cmd_at_dbload", 'line1\ndbLoadRecords("x.db")\n')
    conf.save()
    text = open(config_path, encoding="utf-8").read()
    assert "# my own note" in text and "cmd_at_dbload: |" in text
    assert [f for f in os.listdir(ioc_dir) if f.endswith(".tmp")] == []
    again = IocConfig(config_path)
    again.load()
    assert again.is_valid
    assert again.get("basic.image") == "registry.iasf/ioc:1.0"
    assert again.get("build.db_load.0.macros.P") == "xxx:"
    print("3. set/save/reload ok")

    # 4. check.
    assert again.check("basic.host", "swarm") is True
    assert again.check("build.modules", "autosave") is True
    assert again.check("build.modules", "status-os") is False
    assert again.check("settings.report_info", True) is True
    again.set("build.modules", [])
    assert again.check("build.modules", "") is True
    print("4. check ok")

    # 5. invalid content is reported but values stay readable; fixing clears it.
    again.set("deploy.resources.limits.cpus", 1)
    assert again.validate() is False
    assert again.is_valid is False and again.errors
    assert again.get("basic.host") == "swarm"
    print("   errors:", again.errors)
    again.set("deploy.resources.limits.cpus", "1")
    assert again.validate() is True
    assert again.is_valid is True and again.errors == []
    print("5. validation ok")

    # 6. files that cannot be loaded raise, so nothing runs on empty content.
    from ruamel.yaml.error import YAMLError

    def load_raises(content, exc):
        path = os.path.join(test_root, "bad.yaml")
        if content is not None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        elif os.path.exists(path):
            os.remove(path)
        c = IocConfig(path)
        try:
            c.load()
        except exc:
            assert c.is_loaded is False and c.is_valid is False
            return
        raise AssertionError(f"{exc.__name__} not raised")

    load_raises("basic: [unclosed\n", YAMLError)
    load_raises("basic:\n  name: a\n  name: b\n", YAMLError)
    load_raises("", ValueError)
    load_raises(None, FileNotFoundError)
    print("6. unreadable file raises ok")

    fresh = IocConfig(config_path)
    assert fresh.is_loaded is False
    for call in (lambda: fresh.get("basic.name"), lambda: fresh.set("basic.name", "x"), fresh.save):
        try:
            call()
        except RuntimeError:
            pass
        else:
            raise AssertionError("must raise before load()")
    fresh.load()
    assert fresh.is_loaded is True
    print("   use before load() raises ok")

    # 7. show prints plain data: no comments, no blank lines, same content.
    import contextlib
    import io

    def shown(conf):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            conf.show()
        return buf.getvalue()

    out = shown(again)
    assert "#" not in out and "\n\n" not in out
    printed = get_yaml_tool().load(out)
    for key in ("basic", "src", "build", "settings", "deploy"):
        assert printed[key] == again.get(key)
    print("7. show plain output ok")
    again.show()
    print("\nAll tests passed.")
