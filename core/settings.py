"""Where IocDock keeps its files. To move something, change it here.

Read these as `settings.NAME`, not `from core.settings import NAME`: the code
looks a path up when it uses it, so a test can point one somewhere else."""

IOC_HOME = "/opt/IocDockHome/IocDock"

# the directory that holds one directory per IOC
IOCS_DIR = IOC_HOME + "/iocs"

# the name of the config file in the directory of an IOC
CONFIG_FILE_NAME = "ioc-config.yaml"

# the SQLite database with the state of the IOCs, see core/ioc_state.py
STATE_DB_FILE_NAME = "ioc-state.db"
DEFAULT_DB_PATH = IOC_HOME + "/" + STATE_DB_FILE_NAME

# the suffixes that tell the kinds of source files apart (in the src/ of an IOC); a
# file with any other suffix is one of the other files
DB_FILE_SUFFIXES = (".db",)
PROTOCOL_FILE_SUFFIXES = (".proto",)

# how many issues an IOC keeps, of each of the two categories (see IssueCategory):
# - the results of the operations the user did (build, export, ...): when there are
#   more the oldest are dropped
# - the problems with the state of the IOC: when there are more, those of the lowest
#   level are dropped first, and of one level the oldest ones
MAX_OPERATION_RECORDS = 50
MAX_STATE_ISSUES = 100
