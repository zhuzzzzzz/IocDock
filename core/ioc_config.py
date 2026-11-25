import os
import sys
from io import StringIO

from pydantic import ValidationError

from core.ioc_schema import (
    IocConfigSchema,
    IssueCategory,
    IssueEntry,
    IssueLevel,
    IssueReason,
    new_config,
)
from core.utils import atomic_write, get_dir_name, get_now_str, get_yaml_tool


class IocConfig:

    def __init__(self, path):
        self._yaml = get_yaml_tool()
        self.path = path
        self.data = None
        self.issues = []
        self.is_valid = False

    def file_exists(self):
        return os.path.isfile(self.path)

    @staticmethod
    def create_template(path, build_type, name=None):
        """Write a config file made from a template to `path`, for the IOC `name`
        (default: the name of the directory of `path`). A file already there raises
        FileExistsError and is left alone."""
        if os.path.isfile(path):
            raise FileExistsError(path)
        buf = StringIO()
        get_yaml_tool().dump(
            new_config(name or get_dir_name(path), build_type=build_type).model_dump(), buf
        )
        atomic_write(path, buf.getvalue())

    def load(self):
        now = get_now_str()
        self.data = None
        self.issues = []
        self.is_valid = False
        if not self.file_exists():
            raise FileNotFoundError("config file not found")
        error = None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = self._yaml.load(f)
        except Exception as e:
            error = f"{self.path}: {e}"
        else:
            if data is None:
                error = f"{self.path}: config file is empty"
        if error is not None:
            self.issues.append(
                IssueEntry(
                    level=IssueLevel.ERROR,
                    reason=IssueReason.FILE_ERROR,
                    category=IssueCategory.STATE,
                    message=error,
                    prompt="",
                    time=now,
                )
            )
            return
        self._validate(data)

    def _validate(self, data):
        now = get_now_str()
        try:
            self.data = IocConfigSchema.model_validate(data)
        except ValidationError as e:
            for err in e.errors():
                path = ".".join(str(p) for p in err["loc"]) or "<root>"
                self.issues.append(
                    IssueEntry(
                        level=IssueLevel.ERROR,
                        reason=IssueReason.VALIDATION_ERROR,
                        category=IssueCategory.STATE,
                        message=f"{path}: {err['msg']}",
                        prompt="",
                        time=now,
                    )
                )
        if self.data is not None:
            name, dir_name = self.data.basic.name, get_dir_name(self.path)
            if name != dir_name:
                self.issues.append(
                    IssueEntry(
                        level=IssueLevel.WARNING,
                        reason=IssueReason.VALIDATION_ERROR,
                        category=IssueCategory.STATE,
                        message=f"basic.name: {name!r} does not match directory name {dir_name!r}",
                        prompt="",
                        time=now,
                    )
                )
        self.is_valid = self.data is not None and not any(
            i.level in (IssueLevel.WARNING, IssueLevel.ERROR) for i in self.issues
        )

    def to_string(self):
        if self.data is None:
            raise RuntimeError("config is not loaded")
        buf = StringIO()
        self._yaml.dump(self.data.model_dump(), buf)
        return buf.getvalue()

    def show(self):
        sys.stdout.write(self.to_string())

    def save(self, path):
        atomic_write(path, self.to_string())
