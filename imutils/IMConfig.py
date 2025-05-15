import os
from .IMError import IMInitError


def get_manager_path() -> str:
    repository_path = os.environ.get("MANAGER_PATH", default='')
    if repository_path:
        if os.path.isdir(repository_path):
            return repository_path
        else:
            raise IMInitError(f'Invalid system environment variable "$MANAGER_PATH".')
    else:
        raise IMInitError(f'System environment variable "$MANAGER_PATH" is not defined.')


#
#
# Tool settings
#######################################################################################################################

## directory names
#########################################################################
REPOSITORY_DIR = 'ioc-repository'

TOOLS_DIR = 'imtools'

MOUNT_DIR = 'ioc-for-docker'  # directory for docker mounting

SWARM_DIR = 'swarm'

COMPOSE_SERVICE_FILE_DIR = 'compose-swarm'

LOG_FILE_DIR = 'iocLog'  # directory for running iocLogServer in docker

IOC_BACKUP_DIR = 'ioc-backup'  # backup directory for IOC project files

SWARM_BACKUP_DIR = 'swarm-backup'  # backup directory for swarm

## file names
#########################################################################
IOC_CONFIG_FILE = 'ioc.ini'

IOC_SERVICE_FILE = 'compose-swarm.yaml'

OPERATION_LOG_FILE = 'OperationLog'

## paths
#########################################################################
REPOSITORY_PATH = os.path.normpath(os.path.join(get_manager_path(), REPOSITORY_DIR))

MOUNT_PATH = os.getenv('MOUNT_PATH', os.path.normpath(os.path.join(get_manager_path(), '..', MOUNT_DIR)))

SNAPSHOT_PATH = os.path.join(get_manager_path(), 'ioc-snapshot')

TEMPLATE_PATH = os.path.join(get_manager_path(), 'templates')
if not os.path.exists(TEMPLATE_PATH):
    raise IMInitError(f"Can't find directory \"templates\".")

COMPOSE_TEMPLATE_PATH = os.path.join(TEMPLATE_PATH, 'compose')
if not os.path.exists(COMPOSE_TEMPLATE_PATH):
    raise IMInitError(f"Can't find directory \"templates/compose\".")

DB_TEMPLATE_PATH = os.path.join(TEMPLATE_PATH, 'db')
if not os.path.exists(DB_TEMPLATE_PATH):
    raise IMInitError(f"Can't find directory \"templates/db\".")

OPERATION_LOG_PATH = os.path.join(get_manager_path(), TOOLS_DIR)

## others
#########################################################################
OPERATION_LOG_NUM = 3000  # entry numbers of OperationLog

#
# IOC settings
#######################################################################################################################

## IOC repository setting
#########################################################################
STATE_NORMAL = 'normal'  # IOC state string
STATE_WARNING = 'warning'
STATE_ERROR = 'error'

DB_SUFFIX = ('.db',)  # file name suffix recognized by get_src_file()
PROTO_SUFFIX = ('.proto',)
OTHER_SUFFIX = ('.im',)

MODULES_PROVIDED = ['autosave', 'caputlog', 'status-ioc',
                    'status-os']  # modules supported for automatic configuration and installation

DEFAULT_MODULES = 'autosave, caputlog'  # default modules installed for created IOC projects

## IOC container setting
#########################################################################
DEFAULT_IOC = 'ST-IOC'  # default executable IOC in container

CONTAINER_TOP_PATH = os.path.join('/', 'opt', 'EPICS')  # path definition in running container.
CONTAINER_IOC_PATH = os.path.join(CONTAINER_TOP_PATH, 'IOC')
CONTAINER_IOC_RUN_PATH = os.path.join(CONTAINER_TOP_PATH, 'RUN')

#
# Deploy settings
#######################################################################################################################
PREFIX_STACK_NAME = 'dals'  # stack name in swarm
