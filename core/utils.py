import os
import tempfile
from datetime import datetime


def get_dir_name(path):
    return os.path.basename(os.path.dirname(os.path.abspath(path)))


def get_now_str():
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def get_yaml_tool():
    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.representer.sort_base_mapping_type_on_output = False
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def atomic_write(path: str, text: str) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(path):
            os.chmod(tmp_path, os.stat(path).st_mode & 0o777)
        else:
            os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
