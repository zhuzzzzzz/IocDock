from ruamel.yaml import YAML
import os, sys

yaml = YAML()
yaml.preserve_quotes = True
SERVICE_TEMPLATE_PATH = '/home/zhu/docker/IocDock/templates/service'

template_path = os.path.join(SERVICE_TEMPLATE_PATH, "hello.yaml")
test_path = os.path.join(SERVICE_TEMPLATE_PATH, "hello.yaml2")
with open(template_path, "r", encoding="utf-8") as f:
    data = yaml.load(f)

data["services"]["srv-hello"]["image"] = "world"
with open(test_path, "w", encoding="utf-8") as f:
    yaml.dump(data, f)
yaml.dump(data, sys.stdout)