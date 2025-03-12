import os
from .IMError import IMValueError


def get_manager_path() -> str:
    repository_path = os.environ.get("MANAGER_PATH", default='')
    if repository_path:
        if os.path.isdir(repository_path):
            return repository_path
        else:
            raise IMValueError(f'Incorrect system environment variable: $MANAGER_PATH is not a valid directory.')
    else:
        raise IMValueError(f'Incorrect system environment variable: $MANAGER_PATH is not defined.')


#

# Definition for directory or file names in tool.
TOOLS_DIR = 'imtools'

CONFIG_FILE_NAME = 'ioc.ini'

REPOSITORY_DIR = 'ioc-repository'

MOUNT_DIR = 'ioc-for-docker'  # default directory for docker mounting
MOUNT_PATH = os.getenv('MOUNT_PATH', os.path.join(get_manager_path(), '..', MOUNT_DIR))

IOC_BACKUP_DIR = 'ioc-backup'  # version backup directory for ioc.ini file and other run-time log files

SWARM_BACKUP_DIR = 'swarm-backup'  # version backup directory for swarm

OPERATION_LOG_PATH = 'log'
OPERATION_LOG_FILE = 'OperationLogs'
OPERATION_LOG_NUM = 1000

TEMPLATE_PATH = os.path.join(get_manager_path(), TOOLS_DIR, 'template')
if not os.path.exists(TEMPLATE_PATH):
    print("imtools.IMConsts: Can't find \"template\" directory.")

SNAPSHOT_PATH = os.path.join(get_manager_path(), TOOLS_DIR,
                             'ioc-snapshot')  # path for newest snapshot file of ioc.ini

# source file format used by IOC.get_src_file()
DB_SUFFIX = ('.db',)
PROTO_SUFFIX = ('.proto',)
OTHER_SUFFIX = ('.im',)

# IOC settings.
DEFAULT_IOC = 'ST-IOC'

MODULES_PROVIDED = ['autosave', 'caputlog', 'status-ioc', 'status-os']
# asyn, StreamDevice needs to be set separately for different hosts, so they are not supported by default.
DEFAULT_MODULES = 'autosave, caputlog, status-ioc'

PORT_SUPPORT = ('tcp/ip', 'serial')

# path definition in running container.
CONTAINER_TOP_PATH = os.path.join('/', 'opt', 'EPICS')
CONTAINER_IOC_PATH = os.path.join(CONTAINER_TOP_PATH, 'IOC')
CONTAINER_IOC_RUN_PATH = os.path.join(CONTAINER_TOP_PATH, 'RUN')

LOG_FILE_DIR = 'iocLog'  # directory for running iocLogServer in docker

# swarm orchestration settings.
PREFIX_STACK_NAME = 'dals'

SWARM_DIR = 'swarm'

IOC_SERVICE_FILE = 'compose-swarm.yaml'
GLOBAL_SERVICE_FILE = 'compose-swarm-init.yaml'
