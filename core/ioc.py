import os
import sys
import tempfile
from typing import Any

from pydantic import ValidationError
from ruamel.yaml.error import YAMLError
from ruamel.yaml.scalarstring import LiteralScalarString

from .ioc_config import IOC_CONFIG_TEMPLATE
from .ioc_schema import IocConfigSchema
from .utils import get_yaml_tool


class IocConfig:
    def __init__(self, path: str):
        self.path = path
        self.doc: Any = None  # round-trip document, keeps comments
        self.cfg: IocConfigSchema | None = None  # set only when validation passes
        self.errors: list[str] = []
        self._yaml = get_yaml_tool()

    def load(self, create: bool = False) -> bool:
        self.doc = self.cfg = None
        self.errors = []
        if create and not os.path.exists(self.path):
            self._atomic_write(lambda f: f.write(IOC_CONFIG_TEMPLATE))
            self._read()
            self.set("basic.name", self._dir_name())
            self.save()
            return not self.errors
        self._read()
        return not self.errors

    def save(self) -> None:
        if self.doc is None:
            raise RuntimeError("config not loaded")
        self._atomic_write(lambda f: self._yaml.dump(self.doc, f))

    def get(self, path: str, default: Any = None) -> Any:
        node = self.doc
        for part in path.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            else:
                return default
        return node

    def set(self, path: str, value: Any) -> None:
        if self.doc is None:
            raise RuntimeError("config not loaded")
        if isinstance(value, str) and "\n" in value:
            value = LiteralScalarString(value)
        parts = path.split(".")
        node = self.doc
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
        self._validate()

    def check(self, path: str, value: Any) -> bool:
        node = self.get(path)
        if isinstance(node, list):
            return not node if value == "" else value in node
        return node == value

    def show(self) -> None:
        print(f' "{self.get("basic.name") or self._dir_name()}" '.center(70, "="))
        for error in self.errors:
            print(f"[error] {error}")
        if self.doc is not None:
            self._yaml.dump(self.doc, sys.stdout)

    def _dir_name(self) -> str:
        return os.path.basename(os.path.dirname(os.path.abspath(self.path)))

    def _read(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.doc = self._yaml.load(f)
        except FileNotFoundError:
            self.errors.append("config file lost")
            return
        except (YAMLError, UnicodeDecodeError) as e:
            self.errors.append(f"unrecognized config file: {e}")
            return
        self._validate()

    def _validate(self) -> None:
        self.cfg = None
        self.errors = []
        try:
            self.cfg = IocConfigSchema.model_validate(self.doc)
        except ValidationError as e:
            for err in e.errors():
                path = ".".join(str(p) for p in err["loc"])
                self.errors.append(f"{path}: {err['msg']}")

    def _atomic_write(self, write) -> None:
        directory = os.path.dirname(os.path.abspath(self.path))
        fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                write(f)
                f.flush()
                os.fsync(f.fileno())
            if os.path.exists(self.path):
                os.chmod(tmp_path, os.stat(self.path).st_mode & 0o777)
            else:
                os.chmod(tmp_path, 0o644)
            os.replace(tmp_path, self.path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
