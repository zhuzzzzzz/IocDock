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


#################
# Tool settings #
#################

# directory, file and path.
## ---------------------- ##

REPOSITORY_DIR = 'ioc-repository'
TEMPLATES_DIR = 'templates'
TOOLS_DIR = 'imtools'
SERVICES_DIR = 'imsrvs'
GLOBAL_SERVICE_FILE_DIR = 'global-services'
SNAPSHOT_DIR = 'ioc-snapshot'

IOC_CONFIG_FILE = 'ioc.ini'
IOC_STATE_INFO_FILE = '.info.ini'
IOC_SERVICE_FILE = 'compose-swarm.yaml'
OPERATION_LOG_FILE = 'OperationLog'

MANAGER_PATH = os.path.normpath(get_manager_path())
REPOSITORY_PATH = os.path.join(MANAGER_PATH, REPOSITORY_DIR)
TOOLS_PATH = os.path.join(MANAGER_PATH, TOOLS_DIR)
SERVICES_PATH = os.path.join(MANAGER_PATH, SERVICES_DIR)
GLOBAL_SERVICES_PATH = os.path.join(SERVICES_PATH, GLOBAL_SERVICE_FILE_DIR)
SNAPSHOT_PATH = os.path.join(MANAGER_PATH, SNAPSHOT_DIR)
TEMPLATE_PATH = os.path.join(MANAGER_PATH, TEMPLATES_DIR)
COMPOSE_TEMPLATE_PATH = os.path.join(TEMPLATE_PATH, 'compose')
DB_TEMPLATE_PATH = os.path.join(TEMPLATE_PATH, 'db')
OPERATION_LOG_PATH = os.path.join(TOOLS_PATH, OPERATION_LOG_FILE)

# others.
## ---- ##

OPERATION_LOG_NUM = 3000  # entry numbers of OperationLog

#######################
# Management settings #
#######################

# IOC management setting.
## -------------------- ##

# IOC state string
STATE_NORMAL = 'normal'
STATE_WARNING = 'warning'
STATE_ERROR = 'error'

# file name suffix recognized by get_src_file()
DB_SUFFIX = ('.db',)
PROTO_SUFFIX = ('.proto',)
OTHER_SUFFIX = ('.im',)

# modules supported for automatic configuration and installation
MODULES_PROVIDED = ['autosave', 'caputlog', 'status-ioc', 'status-os']
# default modules installed for newly created IOC projects
DEFAULT_MODULES = 'autosave, caputlog'

##############################
# Global Deployment settings #
##############################

# directory, file and path.
## ---------------------- ##

MOUNT_DIR = 'ioc-for-docker'  # top directory for nfs mounting
# MOUNT_DIR = 'IocDock-data'
SWARM_DIR = 'swarm'  # top directory for swarm deploying
LOG_FILE_DIR = 'iocLog'  # directory for running iocLogServer in docker

IOC_BACKUP_DIR = 'ioc-backup'  # backup directory for IOC project files
SWARM_BACKUP_DIR = 'swarm-backup'  # backup directory for swarm

MOUNT_PATH = os.getenv('MOUNT_PATH', os.path.normpath(os.path.join(MANAGER_PATH, '..', MOUNT_DIR)))

# others.
## ---- ##

# managed stack name in swarm
PREFIX_STACK_NAME = 'dals'

###########################
# IOC deployment settings #
###########################

# IOC in container.
## -------------- ##

# default executable IOC in container
DEFAULT_IOC = 'ST-IOC'

# path definition in running container.
CONTAINER_TOP_PATH = os.path.join('/', 'opt', 'EPICS')
CONTAINER_IOC_PATH = os.path.join(CONTAINER_TOP_PATH, 'IOC')
CONTAINER_IOC_RUN_PATH = os.path.join(CONTAINER_TOP_PATH, 'RUN')

# resources limit
RESOURCE_IOC_CPU_LIMIT = '1'
RESOURCE_IOC_MEMORY_LIMIT = '1G'

###############################
# Service deployment settings #
###############################

# registry.
## ------ ##

# REGISTRY_COMMON_NAME = 'registry.{PREFIX_STACK_NAME}'
REGISTRY_COMMON_NAME = f'image.{PREFIX_STACK_NAME}'  # common name for registry https server
REGISTRY_PORT = 443  # port for registry https server
REGISTRY_CERT_DOCKER_DIR = REGISTRY_COMMON_NAME if REGISTRY_PORT == 443 else f'{REGISTRY_COMMON_NAME}:{REGISTRY_PORT}'
REGISTRY_SHELL_VAR_FILE = 'RegistryVar'

# alertManager.
## ---------- ##

ALERT_MANAGER_MASTER_IP = '192.168.1.51'
ALERT_MANAGER_MASTER_PORT = '9094'
ALERT_MANAGER_SHELL_VAR_FILE = 'AlertManagerVar'
