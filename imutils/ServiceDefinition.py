import os.path
from imutils.IMConfig import COMPOSE_TEMPLATE_PATH

#
GlobalServicesList = [
    # ("name",),  # omit "image" to use original image setting of the compose file
    # ("name", "image")
    ("client", "base:beta-0.2.2"),
    ("iocLogServer", "base:beta-0.2.2"),
    ("cAdvisor", "cadvisor:v0.52.1"),
    ("nodeExporter", "node-exporter:v1.9.1"),
    ("alloy", "alloy:v1.9.2"),
]

#
LocalServicesList = [
    # ("name",),  # omit "image" to use original image setting of the compose file
    # ("name", "image")
    ("registry", "registry:3.0.0"),
    ("prometheus", "prometheus:v3.5.0"),
    ("alertManager", "alertmanager:v0.28.1"),
    ("loki", "loki:3.5.2"),
    ("grafana", "grafana:12.0.2-ubuntu"),
    ("alertAnalytics", "alert-analytics:0.1.0"),
    # ("portainerServer",)
    # ("portainerAgent",)
]

#
CustomServicesList = [
    # ("name", "/path/to/compose/file"),
    ('hello', os.path.join(COMPOSE_TEMPLATE_PATH, 'hello.yaml')),
]
