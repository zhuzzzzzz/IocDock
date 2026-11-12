def get_yaml_tool():
    from ruamel.yaml import YAML
    yaml = YAML()
    yaml.width = 4096
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml
