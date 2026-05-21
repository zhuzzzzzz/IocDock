import os.path
import importlib.util
from pathlib import Path

# resolve custom settings
custom_settings_path = Path(__file__).parent.parent / "settings.py"
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
        import imutils.settings as CustomConfig
    except ModuleNotFoundError:
        import_flag = False
    else:
        import_flag = True

########################
## Tool Path Settings ##
#######################################################################################################################

HOME_PATH = "/opt/IocDockHome"
PROJECT_NAME = "IocDock"
MANAGER_PATH = os.path.join(HOME_PATH, PROJECT_NAME)

REPOSITORY_DIR = "ioc-repository"
REPOSITORY_PATH = os.path.join(MANAGER_PATH, REPOSITORY_DIR)

IOC_SNAPSHOT_DIR = "ioc-snapshot"
SNAPSHOT_PATH = os.path.join(MANAGER_PATH, IOC_SNAPSHOT_DIR)

TOOLS_DIR = "imtools"
TOOLS_PATH = os.path.join(MANAGER_PATH, TOOLS_DIR)
ANSIBLE_PATH = os.path.join(TOOLS_PATH, "ansible")
ANSIBLE_INVENTORY_PATH = os.path.join(ANSIBLE_PATH, "inventory")
CLUSTER_INVENTORY_FILE_PATH = os.path.join(ANSIBLE_INVENTORY_PATH, "cluster")
DEFAULT_INVENTORY_FILE_PATH = os.path.join(ANSIBLE_INVENTORY_PATH, "default")
SCRIPTS_CERT_PATH = os.path.join(TOOLS_PATH, "certs", "scripts")
ROOT_CERT_PATH = os.path.join(TOOLS_PATH, "certs", "root")
SERVER_CERT_PATH = os.path.join(TOOLS_PATH, "certs", "server")
OPERATION_LOG_FILE_PATH = os.path.join(TOOLS_PATH, "operation-log", "OperationLog")

SERVICES_DIR = "imsrvs"
SERVICES_PATH = os.path.join(MANAGER_PATH, SERVICES_DIR)
GLOBAL_SERVICE_FILE_DIR = "global-services"
GLOBAL_SERVICES_PATH = os.path.join(SERVICES_PATH, GLOBAL_SERVICE_FILE_DIR)
GLOBAL_SERVICES_CONFIG_DIR_PATH = os.path.join(GLOBAL_SERVICES_PATH, "config")
CUSTOM_SERVICE_FILE_DIR = "custom-services"
CUSTOM_SERVICE_PATH = os.path.join(SERVICES_PATH, CUSTOM_SERVICE_FILE_DIR)

TEMPLATE_DIR = "templates"
TEMPLATE_PATH = os.path.join(MANAGER_PATH, TEMPLATE_DIR)
SERVICE_TEMPLATE_PATH = os.path.join(TEMPLATE_PATH, "service")
DB_TEMPLATE_PATH = os.path.join(TEMPLATE_PATH, "db")

# MOUNT_DIR = 'ioc-for-docker'
MOUNT_DIR = "IocDock-data"  # top directory for nfs mounting
MOUNT_PATH = os.getenv("MOUNT_PATH", os.path.join(MANAGER_PATH, "..", MOUNT_DIR))
MOUNT_PATH = os.path.normpath(MOUNT_PATH)
MOUNT_DIR_NFS_MOUNT_SRC = "192.168.1.50:/home/zhu/NFS/IocDock-data"
SWARM_DIR = "swarm"  # top directory for swarm deploying
LOG_FILE_DIR = "iocLog"  # directory for running iocLogServer in docker

IOC_BACKUP_DIR = "ioc-backup"  # backup directory for IOC project files

SWARM_BACKUP_DIR = "swarm-backup"  # backup directory for swarm

###########################
## IOC Managing Settings ##
#######################################################################################################################

IOC_CONFIG_FILE = "ioc.ini"
IOC_STATE_INFO_FILE = ".info.ini"
IOC_SERVICE_FILE = "compose-swarm.yaml"

STATE_NORMAL = "normal"  # IOC state string
STATE_WARNING = "warning"
STATE_ERROR = "error"

DB_SUFFIX = (".db",)  # file name suffix recognized by get_src_file()
PROTO_SUFFIX = (".proto",)
OTHER_SUFFIX = (".im",)

MODULES_PROVIDED = ["autosave", "caputlog", "status-ioc", "status-os"]
DEFAULT_MODULES = (
    "autosave, caputlog"  # default modules installed for newly created IOC projects
)

############################
## Node Managing Settings ##
#######################################################################################################################

CLUSTER_MANAGER_NODES = {
    # "hostname": "ip address",
    "ubuntu-server": "192.168.1.50",
    "ubuntu-new": "192.168.1.51",
    "manager0": "192.168.1.52",
    "manager1": "192.168.1.53",
}
CLUSTER_WORKER_NODES = {
    # "hostname": "ip address",
    "worker0": "192.168.1.54",
    "worker1": "192.168.1.55",
}
DEFAULT_NODES = {
    # "hostname": "ip address",
    "nfs": "192.168.1.50"
}

SWARM_ADDVERTISER_IP = ""
SWARM_ADDVERTISER_INTERFACE = ""

ANSIBLE_SSH_USER = "root"
ANSIBLE_FOR_USER = "iocdock"
ANSIBLE_CREATE_PASSWORD = ""

#############################
## Ansible Server Settings ##
#######################################################################################################################

SOCKET_PATH = "/tmp/IocDock.sock"

NODE_IP_FILE = "~/.NodeInfo"  # file to store node ip in cluster for services init

############################
## Global Deploy settings ##
#######################################################################################################################

PREFIX_STACK_NAME = "iasf"  # managed stack name in swarm

#########################
## IOC Deploy settings ##
#######################################################################################################################

DEFAULT_IOC = "ST-IOC"  # default executable IOC in container

CONTAINER_TOP_PATH = os.path.join(
    "/", "opt", "EPICS"
)  # path definition in running container.
CONTAINER_IOC_PATH = os.path.join(CONTAINER_TOP_PATH, "IOC")
CONTAINER_IOC_RUN_PATH = os.path.join(CONTAINER_TOP_PATH, "RUN")

RESOURCE_IOC_CPU_LIMIT = "1"  # default resources limit
RESOURCE_IOC_MEMORY_LIMIT = "1G"

#############################
## Service Deploy settings ##
#######################################################################################################################

## registry ##
REGISTRY_COMMON_NAME = (
    f"registry.{PREFIX_STACK_NAME}"  # common name for registry https server
)
REGISTRY_PORT = 443  # port for registry https server
REGISTRY_CERT_DOCKER_DIR = (
    REGISTRY_COMMON_NAME
    if REGISTRY_PORT == 443
    else f"{REGISTRY_COMMON_NAME}:{REGISTRY_PORT}"
)
REGISTRY_MASTER_IP = "192.168.1.50"
REGISTRY_LOGIN_USERNAME = ""
REGISTRY_LOGIN_PASSWORD = ""

REGISTRY_NFS_MOUNT_SRC = "192.168.1.50:/home/zhu/NFS/registry-data"

## alertManager ##
ALERT_MANAGER_SHELL_VAR_FILE = "AlertManagerVar"
ALERT_MANAGER_MASTER_IP = "192.168.1.50"
ALERT_MANAGER_MASTER_GOSSIP_PORT = "9094"
ALERT_MANAGER_SMTP_SMART_HOST = "smtp.qiye.aliyun.com:465"
ALERT_MANAGER_SMTP_AUTH_USERNAME = "zhujunhua@mail.iasf.ac.cn"
ALERT_MANAGER_SMTP_AUTH_PASSWORD = None
ALERT_MANAGER_SMTP_EMAIL_SEND_ADDRESS = "zhujunhua@mail.iasf.ac.cn"
ALERT_MANAGER_RECEIVE_EMAIL_LIST = []
ALERT_MANAGER_DEFAULT_WEBHOOK_RECEIVER: str = (
    "http://192.168.20.170:8081/webhook/prometheus"
)
ALERT_MANAGER_INFO_WEBHOOK_RECEIVER: str = "http://192.168.1.51:8000/alerts"

####################
## do not modify. ##
#######################################################################################################################
#######################################################################################################################
##
ALLOWED_VARS = [
    "PREFIX_STACK_NAME",
    "MOUNT_DIR_NFS_MOUNT_SRC",
    "REGISTRY_MASTER_IP",
    "REGISTRY_NFS_MOUNT_SRC",
    "DEFAULT_MODULES",
    "RESOURCE_IOC_CPU_LIMIT",
    "RESOURCE_IOC_MEMORY_LIMIT",
    "CLUSTER_MANAGER_NODES",
    "CLUSTER_WORKER_NODES",
    "DEFAULT_NODES",
    "SWARM_ADDVERTISER_IP",
    "SWARM_ADDVERTISER_INTERFACE",
    "ANSIBLE_SSH_USER",
    "ANSIBLE_CREATE_PASSWORD",
    "REGISTRY_LOGIN_USERNAME",
    "REGISTRY_LOGIN_PASSWORD",
    "ALERT_MANAGER_MASTER_IP",
    "ALERT_MANAGER_SMTP_SMART_HOST",
    "ALERT_MANAGER_SMTP_AUTH_USERNAME",
    "ALERT_MANAGER_SMTP_AUTH_PASSWORD",
    "ALERT_MANAGER_SMTP_EMAIL_SEND_ADDRESS",
    "ALERT_MANAGER_RECEIVE_EMAIL_LIST",
    "ALERT_MANAGER_DEFAULT_WEBHOOK_RECEIVER",
    "ALERT_MANAGER_INFO_WEBHOOK_RECEIVER",
]
## override from custom definition.
if import_flag:
    not_allowed_vars = []
    unrecognized_variable = []
    for item in dir(CustomConfig):
        if not item.startswith("__"):
            if item in globals().keys():
                if item in ALLOWED_VARS:
                    globals()[item] = getattr(CustomConfig, item)
                    # print(f'set {item} {getattr(CustomConfig, item)}')
                else:
                    not_allowed_vars.append(item)
            else:
                unrecognized_variable.append(item)
    else:
        if not_allowed_vars:
            print(
                f'settings.py: Warning. Definitions not allowed: {", ".join(not_allowed_vars).strip()}.'
            )
        if unrecognized_variable:
            print(
                f'settings.py: Warning. Definitions unrecognized: {", ".join(unrecognized_variable).strip()}.'
            )

    #
    REGISTRY_COMMON_NAME = f"registry.{PREFIX_STACK_NAME}"
    REGISTRY_CERT_DOCKER_DIR = (
        REGISTRY_COMMON_NAME
        if REGISTRY_PORT == 443
        else f"{REGISTRY_COMMON_NAME}:{REGISTRY_PORT}"
    )
