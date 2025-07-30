import os.path
from imutils.IMError import IMInitError


def get_manager_path() -> str:
    manager_path = os.environ.get("MANAGER_PATH", default='')
    if manager_path:
        if os.path.isdir(manager_path):
            return manager_path
        else:
            raise IMInitError(f'Invalid system environment variable "$MANAGER_PATH".')
    else:
        raise IMInitError(f'System environment variable "$MANAGER_PATH" is not defined.')


########################
## Tool Path Settings ##
#######################################################################################################################

## directories ##

REPOSITORY_DIR = 'ioc-repository'

TOOLS_DIR = 'imtools'

SERVICES_DIR = 'imsrvs'
GLOBAL_SERVICE_FILE_DIR = 'global-services'

# MOUNT_DIR = 'ioc-for-docker'
MOUNT_DIR = 'IocDock-data'  # top directory for nfs mounting
SWARM_DIR = 'swarm'  # top directory for swarm deploying
LOG_FILE_DIR = 'iocLog'  # directory for running iocLogServer in docker

IOC_BACKUP_DIR = 'ioc-backup'  # backup directory for IOC project files

SWARM_BACKUP_DIR = 'swarm-backup'  # backup directory for swarm

## files ##
IOC_CONFIG_FILE = 'ioc.ini'
IOC_STATE_INFO_FILE = '.info.ini'
IOC_SERVICE_FILE = 'compose-swarm.yaml'

## path ##
MANAGER_PATH = os.path.normpath(get_manager_path())
REPOSITORY_PATH = os.path.join(MANAGER_PATH, REPOSITORY_DIR)
TOOLS_PATH = os.path.join(MANAGER_PATH, TOOLS_DIR)
ANSIBLE_PATH = os.path.join(TOOLS_PATH, 'ansible')
ANSIBLE_INVENTORY_PATH = os.path.join(ANSIBLE_PATH, 'inventory')
CLUSTER_INVENTORY_FILE_PATH = os.path.join(ANSIBLE_INVENTORY_PATH, 'cluster')
DEFAULT_INVENTORY_FILE_PATH = os.path.join(ANSIBLE_INVENTORY_PATH, 'default')
SERVICES_PATH = os.path.join(MANAGER_PATH, SERVICES_DIR)
GLOBAL_SERVICES_PATH = os.path.join(SERVICES_PATH, GLOBAL_SERVICE_FILE_DIR)
GLOBAL_SERVICES_CONFIG_FILE_PATH = os.path.join(GLOBAL_SERVICES_PATH, 'config')
SNAPSHOT_PATH = os.path.join(MANAGER_PATH, 'ioc-snapshot')
TEMPLATE_PATH = os.path.join(MANAGER_PATH, 'templates')
COMPOSE_TEMPLATE_PATH = os.path.join(TEMPLATE_PATH, 'compose')
DB_TEMPLATE_PATH = os.path.join(TEMPLATE_PATH, 'db')
OPERATION_LOG_FILE_PATH = os.path.join(TOOLS_PATH, 'OperationLog')
MOUNT_PATH = os.getenv('MOUNT_PATH', os.path.normpath(os.path.join(MANAGER_PATH, '..', MOUNT_DIR)))

## others ##
OPERATION_LOG_NUM = 1000  # entry numbers of OperationLog

###########################
## IOC Managing Settings ##
#######################################################################################################################

STATE_NORMAL = 'normal'  # IOC state string
STATE_WARNING = 'warning'
STATE_ERROR = 'error'

DB_SUFFIX = ('.db',)  # file name suffix recognized by get_src_file()
PROTO_SUFFIX = ('.proto',)
OTHER_SUFFIX = ('.im',)

MODULES_PROVIDED = ['autosave', 'caputlog', 'status-ioc', 'status-os']
DEFAULT_MODULES = 'autosave, caputlog'  # default modules installed for newly created IOC projects

############################
## Node Managing Settings ##
#######################################################################################################################

CLUSTER_MANAGER_NODES = {
    # "hostname": "ip address",
    'host2': '192.168.1.110',
}
CLUSTER_WORKER_NODES = {
    # "hostname": "ip address",
    'host0': '192.168.1.108',
    'host1': '192.168.1.115',
}
DEFAULT_NODES = {
    # "hostname": "ip address",
    'nfs': '192.168.1.50'
}
REMOTE_USER_NAME = 'zhu'

############################
## Global Deploy settings ##
#######################################################################################################################

PREFIX_STACK_NAME = 'iasf'  # managed stack name in swarm

#########################
## IOC Deploy settings ##
#######################################################################################################################

DEFAULT_IOC = 'ST-IOC'  # default executable IOC in container

CONTAINER_TOP_PATH = os.path.join('/', 'opt', 'EPICS')  # path definition in running container.
CONTAINER_IOC_PATH = os.path.join(CONTAINER_TOP_PATH, 'IOC')
CONTAINER_IOC_RUN_PATH = os.path.join(CONTAINER_TOP_PATH, 'RUN')

RESOURCE_IOC_CPU_LIMIT = '1'  # default resources limit
RESOURCE_IOC_MEMORY_LIMIT = '1G'

#############################
## Service Deploy settings ##
#######################################################################################################################

## registry ##
REGISTRY_COMMON_NAME = f'registry.{PREFIX_STACK_NAME}'  # common name for registry https server
REGISTRY_PORT = 443  # port for registry https server
REGISTRY_CERT_DOCKER_DIR = REGISTRY_COMMON_NAME if REGISTRY_PORT == 443 else f'{REGISTRY_COMMON_NAME}:{REGISTRY_PORT}'
REGISTRY_SHELL_VAR_FILE = 'RegistryVar'  # temp file for shell variables

## alertManager ##
ALERT_MANAGER_SHELL_VAR_FILE = 'AlertManagerVar'
ALERT_MANAGER_MASTER_IP = '192.168.1.51'
ALERT_MANAGER_MASTER_GOSSIP_PORT = '9094'
ALERT_MANAGER_SMTP_SMART_HOST = "smtp.qiye.aliyun.com:465"
ALERT_MANAGER_SMTP_AUTH_USERNAME = "zhujunhua@mail.iasf.ac.cn"
ALERT_MANAGER_SMTP_AUTH_PASSWORD = None
ALERT_MANAGER_SMTP_EMAIL_SEND_ADDRESS = "zhujunhua@mail.iasf.ac.cn"
