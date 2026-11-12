IOC_CONFIG_FILE = "ioc.yaml"
IOC_SRC_DIR = "src"

DB_SUFFIX = (".db",)
PROTO_SUFFIX = (".proto",)
OTHER_SUFFIX = (".im",)

MODULES_PROVIDED = ("autosave", "caputlog", "status-ioc", "status-os")


IOC_CONFIG_TEMPLATE = """\
basic:
  name: ""
  host: swarm
  image: ""
  bin: ST-IOC
  description: ""

src:
  db_files: []
  protocol_files: []
  other_files: []

build:
  modules:
    - autosave
    - caputlog
  db_load:
    - file: example.db
      macros:
        P: "xxx:"
  raw_cmd:
    cmd_before_dbload: ""
    cmd_at_dbload: ""
    cmd_after_iocinit: ""
  file_copy: []
  epics_env: {}

settings:
  report_info: true
  caputlog_json: false

deploy:
  labels: {}
  resources:
    limits:
      cpus: "1"
      memory: 1G
    reservations:
      cpus: ""
      memory: ""
  placement:
    constraints:
      - node.role==worker
"""
