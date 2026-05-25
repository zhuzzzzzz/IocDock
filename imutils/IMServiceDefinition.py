import os.path
import importlib.util
from pathlib import Path
from imutils.IMConfig import SERVICE_TEMPLATE_PATH

#
GlobalServicesList = [
    # ("name",),  # omit "image" to use original image setting of the compose file
    # ("name", "image")
    ("client", "base:1.0.1"),
    ("iocLogServer", "base:1.0.1"),
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
    ("alertAnalytics", "alert-analytics:0.1.1"),
    ("dbwr", "dbwr:0.0.1"),
    # ("portainerServer",)
    # ("portainerAgent",)
]

#
CustomServicesList = [
    # ("name", "/path/to/service/file"),
    ("hello", os.path.join(SERVICE_TEMPLATE_PATH, "hello.yaml")),
]


####################
## do not modify. ##
#######################################################################################################################
#######################################################################################################################
##
## override from custom definition.
custom_settings_path = Path(__file__).parent.parent / "services.py"
custom_settings_path = Path(custom_settings_path).resolve()
if custom_settings_path.is_file():
    spec = importlib.util.spec_from_file_location(
        "custom_settings", custom_settings_path
    )
    CustomConfig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(CustomConfig)
    import_flag = True
else:
    try:
        import imutils.services as CustomConfig
    except ModuleNotFoundError:
        import_flag = False
    else:
        import_flag = True
if import_flag:
    CustomServicesList = CustomServicesList + CustomConfig.CustomServicesList
